"""SQLite stores.

* CandidateStore  (data/candidates.db): inference cache keyed by TaskHash. Re-running the
  pipeline never calls the model again for a TaskHash that is already present -> no extra
  token cost (idempotent inference).
* ResultStore     (runs/<run_id>/run.db): verification results, UPSERT on (run_id, task_hash)
  so a retried task overwrites its previous row instead of creating a duplicate.
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from typing import Iterable, Optional

from .schema import Candidate, VerifyResult


def connect(path: str) -> sqlite3.Connection:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    con = sqlite3.connect(path, timeout=60, isolation_level=None, check_same_thread=False)  # autocommit
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA synchronous=NORMAL")
    con.execute("PRAGMA busy_timeout=60000")
    return con


class CandidateStore:
    def __init__(self, path: str):
        self.path = path
        self.con = connect(path)
        self.lock = threading.Lock()      # the online backend calls the store from a thread pool
        self.con.execute("""CREATE TABLE IF NOT EXISTS candidates(
            task_hash TEXT PRIMARY KEY, problem_id TEXT, prompt_version TEXT, candidate_index INT,
            raw_output TEXT, lean_code TEXT, model TEXT, job_id TEXT,
            prompt_tokens INT, completion_tokens INT, created_at REAL)""")
        self.con.execute("CREATE INDEX IF NOT EXISTS ix_cand_pid ON candidates(problem_id)")

    def upsert(self, c: Candidate, raw_output: str, job_id: str) -> None:
        with self.lock:
            self._upsert(c, raw_output, job_id)

    def _upsert(self, c: Candidate, raw_output: str, job_id: str) -> None:
        self.con.execute("""INSERT INTO candidates VALUES(?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(task_hash) DO UPDATE SET raw_output=excluded.raw_output, lean_code=excluded.lean_code,
              model=excluded.model, job_id=excluded.job_id, prompt_tokens=excluded.prompt_tokens,
              completion_tokens=excluded.completion_tokens, created_at=excluded.created_at""",
                         (c.task_hash, c.problem_id, c.prompt_version, c.candidate_index, raw_output,
                          c.lean_code, c.model, job_id, c.prompt_tokens, c.completion_tokens, time.time()))

    def get(self, task_hash: str) -> Optional[Candidate]:
        with self.lock:
            r = self.con.execute("SELECT task_hash, problem_id, prompt_version, candidate_index, lean_code, model,"
                                 " prompt_tokens, completion_tokens FROM candidates WHERE task_hash=?", (task_hash,)).fetchone()
        return Candidate(*r) if r else None

    def all(self, prompt_version: Optional[str] = None) -> list[Candidate]:
        q = ("SELECT task_hash, problem_id, prompt_version, candidate_index, lean_code, model,"
             " prompt_tokens, completion_tokens FROM candidates")
        rows = self.con.execute(q + (" WHERE prompt_version=?" if prompt_version else ""),
                                (prompt_version,) if prompt_version else ()).fetchall()
        return [Candidate(*r) for r in rows]


class ResultStore:
    COLS = ["run_id", "task_hash", "problem_id", "prompt_version", "candidate_index", "status", "error_kinds",
            "compiler_message", "latency_ms", "peak_ram_mb", "worker_id", "attempt", "finished_at", "stmt_chars"]

    def __init__(self, path: str):
        self.path = path
        self.con = connect(path)
        self.con.execute("""CREATE TABLE IF NOT EXISTS results(
            run_id TEXT, task_hash TEXT, problem_id TEXT, prompt_version TEXT, candidate_index INT,
            status TEXT, error_kinds TEXT, compiler_message TEXT, latency_ms REAL, peak_ram_mb REAL,
            worker_id TEXT, attempt INT, finished_at REAL, stmt_chars INT, write_count INT DEFAULT 1,
            PRIMARY KEY(run_id, task_hash))""")
        self.con.execute("""CREATE TABLE IF NOT EXISTS events(
            ts REAL, run_id TEXT, worker_id TEXT, kind TEXT, detail TEXT)""")

    def upsert(self, r: VerifyResult) -> None:
        vals = (r.run_id, r.task_hash, r.problem_id, r.prompt_version, r.candidate_index, r.status, r.error_kinds,
                r.compiler_message[:4000], r.latency_ms, r.peak_ram_mb, r.worker_id, r.attempt, r.finished_at,
                r.stmt_chars)
        self.con.execute(f"""INSERT INTO results({','.join(self.COLS)}) VALUES({','.join('?' * len(self.COLS))})
            ON CONFLICT(run_id, task_hash) DO UPDATE SET status=excluded.status, error_kinds=excluded.error_kinds,
              compiler_message=excluded.compiler_message, latency_ms=excluded.latency_ms,
              peak_ram_mb=excluded.peak_ram_mb, worker_id=excluded.worker_id, attempt=excluded.attempt,
              finished_at=excluded.finished_at, write_count=results.write_count+1""", vals)

    def event(self, run_id: str, worker_id: str, kind: str, detail: dict | str = "") -> None:
        self.con.execute("INSERT INTO events VALUES(?,?,?,?,?)",
                         (time.time(), run_id, worker_id, kind, json.dumps(detail) if not isinstance(detail, str) else detail))

    def has_event(self, kind: str) -> bool:
        return bool(self.con.execute("SELECT 1 FROM events WHERE kind=? LIMIT 1", (kind,)).fetchone())

    def count(self) -> int:
        return self.con.execute("SELECT COUNT(*) FROM results").fetchone()[0]

    def rows(self, run_id: Optional[str] = None) -> list[dict]:
        q = f"SELECT {','.join(self.COLS)}, write_count FROM results"
        cur = self.con.execute(q + (" WHERE run_id=?" if run_id else ""), (run_id,) if run_id else ())
        names = [d[0] for d in cur.description]
        return [dict(zip(names, row)) for row in cur.fetchall()]

    def events(self, run_id: Optional[str] = None) -> list[dict]:
        cur = self.con.execute("SELECT ts, run_id, worker_id, kind, detail FROM events"
                               + (" WHERE run_id=?" if run_id else ""), (run_id,) if run_id else ())
        return [dict(zip(["ts", "run_id", "worker_id", "kind", "detail"], r)) for r in cur.fetchall()]
