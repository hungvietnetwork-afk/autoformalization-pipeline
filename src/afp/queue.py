"""Durable partitioned work queue (SQLite WAL), SQS/Redis-Streams-like semantics.

* enqueue      : INSERT OR IGNORE keyed by TaskHash -> enqueueing the same task twice is a no-op
* lease        : a worker atomically takes up to `n` READY tasks (or tasks whose lease expired,
                 e.g. because the previous worker crashed) from its home partitions first, then
                 steals from the other partitions (work stealing -> no idle worker while others lag)
* ack          : DONE
* nack         : back to READY (retry); after `max_attempts` (3) the task goes to DEAD (dead-letter)
* lease expiry : a crashed worker never acks; when its lease (visibility timeout) expires the task is
                 automatically leased again -> at-least-once delivery. Combined with UPSERT on
                 TaskHash in the result store this gives effectively-once results.

partition = hash(problem_id) mod R  (see schema.partition_index)
"""
from __future__ import annotations

import json
import time
from typing import Iterable, Optional

from .store import connect

READY, LEASED, DONE, DEAD = "READY", "LEASED", "DONE", "DEAD"


class PartitionedQueue:
    def __init__(self, path: str, name: str = "verify", num_partitions: int = 16, max_attempts: int = 3,
                 indexed: bool = False, sweep_every_s: float = 1.0):
        """indexed=False is the queue every experiment of the report ran with: each lease sorts the READY rows of its
        partitions and sweeps expired leases / exhausted tasks, so its cost grows with the backlog (~3 ms per lease
        at 10K READY tasks, see afp/bench_queue.py). indexed=True adds covering indexes for the lease order and runs
        the two sweeps at most every `sweep_every_s` seconds instead of on every lease."""
        self.path, self.name, self.R, self.max_attempts = path, name, num_partitions, max_attempts
        self.indexed, self.sweep_every_s, self._last_sweep = indexed, sweep_every_s, 0.0
        self.con = connect(path)
        t = self.table = f"q_{name}"
        self.con.execute(f"""CREATE TABLE IF NOT EXISTS {t}(
            task_hash TEXT PRIMARY KEY, partition INT, payload TEXT, state TEXT, attempts INT DEFAULT 0,
            lease_owner TEXT, lease_expires REAL, enqueued_at REAL, updated_at REAL, last_error TEXT)""")
        self.con.execute(f"CREATE INDEX IF NOT EXISTS ix_{t}_state ON {t}(state, partition)")
        if indexed:
            self.con.execute(f"CREATE INDEX IF NOT EXISTS ix_{t}_order ON {t}(state, partition, enqueued_at, task_hash)")
            self.con.execute(f"CREATE INDEX IF NOT EXISTS ix_{t}_steal ON {t}(state, enqueued_at, task_hash)")

    # ------------------------------------------------------------------ producer
    def enqueue(self, items: Iterable[tuple[str, int, dict]]) -> int:
        now = time.time()
        rows = [(th, p, json.dumps(payload, ensure_ascii=False), READY, 0, None, None, now, now, None)
                for th, p, payload in items]
        cur = self.con.cursor()
        cur.execute("BEGIN IMMEDIATE")
        before = self.con.total_changes
        cur.executemany(f"INSERT OR IGNORE INTO {self.table} VALUES(?,?,?,?,?,?,?,?,?,?)", rows)
        cur.execute("COMMIT")
        return self.con.total_changes - before

    # ------------------------------------------------------------------ consumer
    def lease(self, worker_id: str, home_partitions: list[int], n: int, lease_s: float = 60.0) -> list[tuple[str, dict, int]]:
        """Return up to n (task_hash, payload, attempt) tuples."""
        now = time.time()
        cur = self.con.cursor()
        for _ in range(20):
            try:
                cur.execute("BEGIN IMMEDIATE")
                break
            except Exception:
                time.sleep(0.05)
        try:
            if not self.indexed or now - self._last_sweep >= self.sweep_every_s:
                self._last_sweep = now
                # expired leases: tasks of crashed / stuck workers
                cur.execute(f"""UPDATE {self.table} SET state=?, last_error='lease expired', updated_at=?
                                WHERE state=? AND lease_expires < ?""", (READY, now, LEASED, now))
                # tasks that already used all attempts -> dead letter
                cur.execute(f"""UPDATE {self.table} SET state=?, updated_at=? WHERE state=? AND attempts >= ?""",
                            (DEAD, now, READY, self.max_attempts))
            ph = ",".join("?" * len(home_partitions)) or "NULL"
            # indexed mode sweeps only periodically, so it filters exhausted tasks itself (never a 4th attempt)
            cap, capv = (" AND attempts < ?", (self.max_attempts,)) if self.indexed else ("", ())
            rows = cur.execute(f"""SELECT task_hash, payload, attempts FROM {self.table}
                                   WHERE state=? AND partition IN ({ph}){cap} ORDER BY partition, enqueued_at, task_hash LIMIT ?""",
                               (READY, *home_partitions, *capv, n)).fetchall()
            if len(rows) < n:   # work stealing
                rows += cur.execute(f"""SELECT task_hash, payload, attempts FROM {self.table}
                                        WHERE state=? AND partition NOT IN ({ph}){cap} ORDER BY enqueued_at, task_hash LIMIT ?""",
                                    (READY, *home_partitions, *capv, n - len(rows))).fetchall()
            out = []
            for th, payload, attempts in rows:
                cur.execute(f"""UPDATE {self.table} SET state=?, attempts=attempts+1, lease_owner=?, lease_expires=?,
                                updated_at=? WHERE task_hash=?""", (LEASED, worker_id, now + lease_s, now, th))
                out.append((th, json.loads(payload), attempts + 1))
            cur.execute("COMMIT")
            return out
        except Exception:
            cur.execute("ROLLBACK")
            raise

    def ack(self, task_hashes: list[str], worker_id: Optional[str] = None) -> None:
        now = time.time()
        self.con.executemany(f"UPDATE {self.table} SET state=?, updated_at=? WHERE task_hash=?",
                             [(DONE, now, th) for th in task_hashes])

    def nack(self, task_hash: str, error: str) -> None:
        now = time.time()
        self.con.execute(f"""UPDATE {self.table} SET state=CASE WHEN attempts >= ? THEN ? ELSE ? END,
                             last_error=?, updated_at=?, lease_owner=NULL WHERE task_hash=?""",
                         (self.max_attempts, DEAD, READY, error[:500], now, task_hash))

    def release(self, task_hashes: list[str]) -> None:
        """Hand leased tasks back as READY without charging an attempt. Used when a worker cannot make progress
        for a while (REPL restart, ~40 s): the rest of its batch goes to other workers at once instead of
        waiting for the restart or for the lease to expire."""
        now = time.time()
        self.con.executemany(f"""UPDATE {self.table} SET state=?, attempts=MAX(attempts - 1, 0), lease_owner=NULL,
                                 updated_at=? WHERE task_hash=? AND state=?""",
                             [(READY, now, th, LEASED) for th in task_hashes])

    def extend(self, task_hashes: list[str], lease_s: float) -> None:
        exp = time.time() + lease_s
        self.con.executemany(f"UPDATE {self.table} SET lease_expires=? WHERE task_hash=? AND state=?",
                             [(exp, th, LEASED) for th in task_hashes])

    # ------------------------------------------------------------------ monitoring
    def counts(self) -> dict:
        rows = self.con.execute(f"SELECT state, COUNT(*) FROM {self.table} GROUP BY state").fetchall()
        d = {READY: 0, LEASED: 0, DONE: 0, DEAD: 0}
        d.update(dict(rows))
        return d

    def pending(self) -> int:
        c = self.counts()
        return c[READY] + c[LEASED]

    def attempts(self) -> list[int]:
        return [a for (a,) in self.con.execute(f"SELECT attempts FROM {self.table}")]

    def partition_sizes(self) -> dict[int, int]:
        return dict(self.con.execute(f"SELECT partition, COUNT(*) FROM {self.table} GROUP BY partition").fetchall())
