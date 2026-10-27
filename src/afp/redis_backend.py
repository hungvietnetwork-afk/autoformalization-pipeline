"""Network backend: the same queue / result-store interfaces on Redis, so Lean workers on several
machines can pull from one broker (`python -m afp.worker --redis redis://<host>:6379/0 ...`).

Queue  = one Redis Stream per partition (`afp:<run>:<q>:p<k>`) + one consumer group:
  enqueue  SET seen:<hash> NX (idempotent) -> HSET payload, XADD p<k>
  lease    XAUTOCLAIM (messages idle > lease = crashed worker) then XREADGROUP '>' on home partitions,
           then on the other partitions (work stealing); attempts counted with HINCRBY, > 3 -> dead set
  ack      XACK + SADD done      nack  XACK + XADD again (or dead)      extend  XCLAIM (resets idle)
Results = HSET results <hash> <json> (UPSERT by TaskHash) + HINCRBY write_count; events = RPUSH.
"""
from __future__ import annotations

import json
import time
from typing import Iterable, Optional

READY, LEASED, DONE, DEAD = "READY", "LEASED", "DONE", "DEAD"
GROUP = "workers"


def _redis(url: str):
    import redis
    return redis.Redis.from_url(url, decode_responses=True)


class RedisQueue:
    def __init__(self, url: str, name: str = "verify", num_partitions: int = 16, max_attempts: int = 3, run_id: str = "run"):
        self.r = _redis(url)
        self.R, self.max_attempts = num_partitions, max_attempts
        self.ns = f"afp:{run_id}:{name}"
        self.inflight: dict[str, tuple[str, str]] = {}
        for p in range(num_partitions):
            try:
                self.r.xgroup_create(self._s(p), GROUP, id="0", mkstream=True)
            except Exception as e:          # BUSYGROUP: already created by another process
                if "BUSYGROUP" not in str(e):
                    raise

    def _s(self, p: int) -> str:
        return f"{self.ns}:p{p}"

    # ------------------------------------------------------------------ producer
    def enqueue(self, items: Iterable[tuple[str, int, dict]]) -> int:
        items = list(items)
        pipe = self.r.pipeline(transaction=False)
        for th, _, _ in items:
            pipe.set(f"{self.ns}:seen:{th}", 1, nx=True)
        fresh = pipe.execute()
        pipe = self.r.pipeline(transaction=False)
        n = 0
        for (th, p, payload), new in zip(items, fresh):
            if not new:
                continue
            n += 1
            pipe.hset(f"{self.ns}:payload", th, json.dumps(payload, ensure_ascii=False))
            pipe.hset(f"{self.ns}:part", th, p)
            pipe.xadd(self._s(p), {"th": th})
            if len(pipe) > 3000:
                pipe.execute()
        pipe.execute()
        return n

    # ------------------------------------------------------------------ consumer
    def _take(self, stream: str, msgs, out: list, worker_id: str) -> None:
        for mid, fields in msgs:
            th = fields.get("th") if fields else None
            if th is None:                      # deleted entry
                self.r.xack(stream, GROUP, mid)
                continue
            if self.r.sismember(f"{self.ns}:done", th) or self.r.sismember(f"{self.ns}:dead", th):
                self.r.xack(stream, GROUP, mid)
                continue
            att = self.r.hincrby(f"{self.ns}:attempts", th, 1)
            if att > self.max_attempts:
                self.r.xack(stream, GROUP, mid)
                self.r.sadd(f"{self.ns}:dead", th)
                continue
            self.inflight[th] = (stream, mid)
            out.append((th, json.loads(self.r.hget(f"{self.ns}:payload", th)), att))

    def lease(self, worker_id: str, home_partitions: list[int], n: int, lease_s: float = 60.0):
        out: list = []
        order = list(home_partitions) + [p for p in range(self.R) if p not in home_partitions]
        for p in order:                                         # 1) expired leases (crashed workers)
            if len(out) >= n:
                break
            res = self.r.xautoclaim(self._s(p), GROUP, worker_id, min_idle_time=int(lease_s * 1000),
                                    start_id="0-0", count=n - len(out))
            self._take(self._s(p), res[1], out, worker_id)
        # 2) new work, one stream at a time (XREADGROUP's COUNT is per stream): home partitions first
        for p in order:
            if len(out) >= n:
                break
            res = self.r.xreadgroup(GROUP, worker_id, {self._s(p): ">"}, count=n - len(out))
            for stream, msgs in res or []:
                self._take(stream, msgs, out, worker_id)
        return out

    def ack(self, task_hashes: list[str], worker_id: Optional[str] = None) -> None:
        pipe = self.r.pipeline(transaction=False)
        for th in task_hashes:
            sm = self.inflight.pop(th, None)
            if sm:
                pipe.xack(sm[0], GROUP, sm[1])
            pipe.sadd(f"{self.ns}:done", th)
        pipe.execute()

    def nack(self, task_hash: str, error: str) -> None:
        sm = self.inflight.pop(task_hash, None)
        if sm:
            self.r.xack(sm[0], GROUP, sm[1])
        att = int(self.r.hget(f"{self.ns}:attempts", task_hash) or 0)
        if att >= self.max_attempts:
            self.r.sadd(f"{self.ns}:dead", task_hash)
        else:
            p = int(self.r.hget(f"{self.ns}:part", task_hash))
            self.r.xadd(self._s(p), {"th": task_hash})
        self.r.hset(f"{self.ns}:last_error", task_hash, error[:500])

    def release(self, task_hashes: list[str]) -> None:
        """Make in-flight messages claimable by any consumer now: XCLAIM with an IDLE time beyond any lease, so
        the next XAUTOCLAIM takes them (JUSTID: delivery counter untouched); the attempt is given back."""
        for th in task_hashes:
            sm = self.inflight.pop(th, None)
            if not sm:
                continue
            consumer = self.r.xpending_range(sm[0], GROUP, min=sm[1], max=sm[1], count=1)
            if consumer:
                self.r.xclaim(sm[0], GROUP, consumer[0]["consumer"], 0, [sm[1]], idle=10 ** 10, justid=True)
                self.r.hincrby(f"{self.ns}:attempts", th, -1)

    def extend(self, task_hashes: list[str], lease_s: float) -> None:
        for th in task_hashes:
            sm = self.inflight.get(th)
            if sm:   # XCLAIM to ourselves resets the idle time = renews the lease
                consumer = self.r.xpending_range(sm[0], GROUP, min=sm[1], max=sm[1], count=1)
                if consumer:
                    self.r.xclaim(sm[0], GROUP, consumer[0]["consumer"], 0, [sm[1]], justid=True)

    # ------------------------------------------------------------------ monitoring
    def counts(self) -> dict:
        total = self.r.hlen(f"{self.ns}:payload")
        done = self.r.scard(f"{self.ns}:done")
        dead = self.r.scard(f"{self.ns}:dead")
        leased = sum(self.r.xpending(self._s(p), GROUP)["pending"] for p in range(self.R))
        return {READY: max(0, total - done - dead - leased), LEASED: leased, DONE: done, DEAD: dead}

    def pending(self) -> int:
        return self.r.hlen(f"{self.ns}:payload") - self.r.scard(f"{self.ns}:done") - self.r.scard(f"{self.ns}:dead")

    def attempts(self) -> list[int]:
        return [int(v) for v in self.r.hvals(f"{self.ns}:attempts")]

    def partition_sizes(self) -> dict[int, int]:
        return {p: self.r.xlen(self._s(p)) for p in range(self.R)}


class RedisResultStore:
    COLS = ["run_id", "task_hash", "problem_id", "prompt_version", "candidate_index", "status", "error_kinds",
            "compiler_message", "latency_ms", "peak_ram_mb", "worker_id", "attempt", "finished_at", "stmt_chars"]

    def __init__(self, url: str, run_id: str):
        self.r = _redis(url)
        self.ns = f"afp:{run_id}:store"

    def upsert(self, res) -> None:
        row = {k: getattr(res, k) for k in self.COLS}
        row["compiler_message"] = (row["compiler_message"] or "")[:4000]
        pipe = self.r.pipeline(transaction=False)
        pipe.hset(f"{self.ns}:results", res.task_hash, json.dumps(row, ensure_ascii=False))
        pipe.hincrby(f"{self.ns}:write_count", res.task_hash, 1)
        pipe.execute()

    def event(self, run_id: str, worker_id: str, kind: str, detail=""):
        d = json.dumps(detail) if not isinstance(detail, str) else detail
        pipe = self.r.pipeline(transaction=False)
        pipe.rpush(f"{self.ns}:events", json.dumps({"ts": time.time(), "run_id": run_id, "worker_id": worker_id,
                                                      "kind": kind, "detail": d}))
        pipe.sadd(f"{self.ns}:event_kinds", kind)
        pipe.execute()

    def has_event(self, kind: str) -> bool:
        return bool(self.r.sismember(f"{self.ns}:event_kinds", kind))

    def count(self) -> int:
        return self.r.hlen(f"{self.ns}:results")

    def rows(self, run_id: Optional[str] = None) -> list[dict]:
        wc = self.r.hgetall(f"{self.ns}:write_count")
        out = []
        for th, js in self.r.hgetall(f"{self.ns}:results").items():
            d = json.loads(js)
            d["write_count"] = int(wc.get(th, 1))
            out.append(d)
        return out

    def events(self, run_id: Optional[str] = None) -> list[dict]:
        return [json.loads(x) for x in self.r.lrange(f"{self.ns}:events", 0, -1)]
