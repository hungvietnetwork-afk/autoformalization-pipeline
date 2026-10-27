"""Unit tests for the queue, hashing, sanitiser and the OpenAI-compatible backend (mock server).

    python -m pytest -q tests
"""
import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from afp.prompts import sanitize
from afp.queue import DEAD, DONE, LEASED, READY, PartitionedQueue
from afp.schema import partition_index, task_hash
from afp.store import CandidateStore, ResultStore
from afp.schema import VerifyResult


def test_task_hash_is_deterministic_and_distinct():
    a = task_hash("math:test/algebra/1", "v1_zeroshot", 0)
    assert a == task_hash("math:test/algebra/1", "v1_zeroshot", 0)
    assert a != task_hash("math:test/algebra/1", "v1_zeroshot", 1)
    assert a != task_hash("math:test/algebra/1", "v2_fewshot", 0)
    assert len(a) == 64


def test_partition_index_stable_and_balanced():
    ids = [f"p{i}" for i in range(16000)]
    parts = [partition_index(i, 16) for i in ids]
    assert parts == [partition_index(i, 16) for i in ids]          # stable across calls/processes
    counts = [parts.count(p) for p in range(16)]
    assert max(counts) / min(counts) < 1.15                          # ~uniform


def test_queue_lease_ack_retry_deadletter(tmp_path):
    q = PartitionedQueue(str(tmp_path / "q.db"), "t", num_partitions=4, max_attempts=3)
    assert q.enqueue([(f"h{i}", i % 4, {"i": i}) for i in range(10)]) == 10
    assert q.enqueue([("h0", 0, {"i": 0})]) == 0                      # idempotent enqueue
    got = q.lease("w0", [0], 3, lease_s=60)
    assert [p["i"] % 4 for _, p, _ in got] == [0, 0, 0]               # home partition first
    more = q.lease("w0", [0], 5, lease_s=60)                          # then work stealing
    assert len(more) == 5
    q.ack([th for th, _, _ in got])
    assert q.counts()[DONE] == 3
    # a task nacked 3 times goes to the dead-letter state
    th = more[0][0]
    q.nack(th, "crash 1")
    for _ in range(2):
        t = [x for x in q.lease("w1", [0, 1, 2, 3], 10, 60) if x[0] == th]
        assert t, "task must come back after nack"
        q.nack(th, "crash")
    assert q.con.execute("SELECT state FROM q_t WHERE task_hash=?", (th,)).fetchone()[0] == DEAD


def test_queue_lease_expiry_redelivers(tmp_path):
    q = PartitionedQueue(str(tmp_path / "q.db"), "t", num_partitions=2)
    q.enqueue([("a", 0, {}), ("b", 1, {})])
    first = q.lease("crashed-worker", [0, 1], 2, lease_s=0.2)
    assert len(first) == 2 and q.lease("w2", [0, 1], 2, 60) == []
    time.sleep(0.3)                                                   # visibility timeout passes
    again = q.lease("w2", [0, 1], 2, 60)
    assert sorted(t for t, _, _ in again) == ["a", "b"] and all(a == 2 for _, _, a in again)


def test_queue_release_hands_back_without_charging_attempt(tmp_path):
    q = PartitionedQueue(str(tmp_path / "q.db"), "t", num_partitions=2)
    q.enqueue([("a", 0, {}), ("b", 0, {}), ("c", 1, {})])
    got = q.lease("w0", [0], 3, lease_s=60)                          # a, b (home) + c (stolen)
    q.release([th for th, _, _ in got[1:]])                         # worker restarting: give the rest back
    other = q.lease("w1", [1], 5, lease_s=60)
    assert {t for t, _, _ in other} == {t for t, _, _ in got[1:]}    # available at once, no lease expiry
    assert all(a == 1 for _, _, a in other)                          # not counted as a retry


def test_indexed_queue_same_semantics(tmp_path):
    q = PartitionedQueue(str(tmp_path / "q.db"), "t", num_partitions=4, max_attempts=3, indexed=True, sweep_every_s=60)
    q.enqueue([(f"h{i}", i % 4, {"i": i}) for i in range(10)])
    got = q.lease("w0", [0], 3, lease_s=60)
    assert [p["i"] % 4 for _, p, _ in got] == [0, 0, 0]               # home partition first
    assert len(q.lease("w0", [0], 5, lease_s=60)) == 5               # then work stealing
    # a task whose lease expired 3 times goes to the dead-letter state, never to a 4th attempt
    q2 = PartitionedQueue(str(tmp_path / "q2.db"), "t", num_partitions=1, max_attempts=3, indexed=True, sweep_every_s=0)
    q2.enqueue([("x", 0, {})])
    for _ in range(3):
        assert q2.lease("w", [0], 1, lease_s=0.01)
        time.sleep(0.02)
    assert q2.lease("w", [0], 1, lease_s=60) == []
    assert q2.con.execute("SELECT state FROM q_t WHERE task_hash='x'").fetchone()[0] == DEAD


def test_result_upsert_is_idempotent(tmp_path):
    rs = ResultStore(str(tmp_path / "r.db"))
    r = VerifyResult("h", "p", "v1", 0, "COMPILE_OK", "", 12.0, 100.0, "w0", "run", 1)
    rs.upsert(r)
    r.attempt, r.worker_id = 2, "w1"
    rs.upsert(r)
    rows = rs.rows("run")
    assert len(rows) == 1 and rows[0]["write_count"] == 2 and rows[0]["worker_id"] == "w1"


@pytest.mark.parametrize("raw,expected", [
    ("```lean\nimport Mathlib\ntheorem foo (x : ℝ) : x = x := by\n  rfl\n```", "theorem N (x : ℝ) : x = x := by sorry"),
    ("lemma bar : (2 : ℕ) + 2 = 4 := by norm_num", "theorem N : (2 : ℕ) + 2 = 4 := by sorry"),
    ("example : True := by trivial", "theorem N : True := by sorry"),
    ("theorem t {G : Type*} [Group G] : ∀ a b : G, a * b = b * a :=", "theorem N {G : Type*} [Group G] : ∀ a b : G, a * b = b * a := by sorry"),
    ("def d : CommRing ℤ :=", "noncomputable def N : CommRing ℤ := by sorry"),
    # a `let` inside the statement owns its ':=' (sanitizer v1 cut there)
    ("theorem t : let K : Set ℝ := {x | 0 < x}; (1 : ℝ) ∈ K := by\n  simp", "theorem N : let K : Set ℝ := {x | 0 < x}; (1 : ℝ) ∈ K := by sorry"),
    ("theorem t (complete_let : ℕ) : complete_let = complete_let := rfl", "theorem N (complete_let : ℕ) : complete_let = complete_let := by sorry"),
    ("no lean here", ""),
])
def test_sanitize(raw, expected):
    assert sanitize(raw, "N") == expected


class _MockLLM(BaseHTTPRequestHandler):
    calls = 0

    def do_POST(self):
        _MockLLM.calls += 1
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        if _MockLLM.calls % 3 == 1:                        # every 3rd call is rate limited
            self.send_response(429)
            self.send_header("Retry-After", "0.05")
            self.end_headers()
            return
        out = {"choices": [{"message": {"content": "theorem x : (1 : ℕ) + 1 = 2 := by norm_num"}}],
               "usage": {"prompt_tokens": 100, "completion_tokens": 20}}
        data = json.dumps(out).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):
        pass


def test_openai_compat_backend_retries_and_caches(tmp_path, monkeypatch):
    from afp.inference.backends import OpenAICompatBackend
    srv = HTTPServer(("127.0.0.1", 0), _MockLLM)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    monkeypatch.setenv("NO_PROXY", "127.0.0.1")
    monkeypatch.setenv("no_proxy", "127.0.0.1")
    b = OpenAICompatBackend(f"http://127.0.0.1:{srv.server_port}/v1", "mock", str(tmp_path / "c.db"), max_concurrency=2)
    payloads = [{"problem_id": f"p{i}", "natural_statement": "1+1=2", "prompt_version": "v1_zeroshot", "k": 1} for i in range(4)]
    out = b.generate_batch(payloads)
    assert len(out) == 4 and all(o["lean_code"].endswith(":= by sorry") for o in out)
    assert b.stats()["retries_429_5xx"] >= 1
    calls = b.stats()["model_calls"]
    b.generate_batch(payloads)                                  # second time: all cache hits, no new calls
    assert b.stats()["model_calls"] == calls and b.stats()["cache_hits"] == 4
    srv.shutdown()


def _redis_ok():
    try:
        import redis
        return redis.Redis(port=6390).ping()
    except Exception:
        return False


@pytest.mark.skipif(not _redis_ok(), reason="no redis on :6390")
def test_redis_queue_semantics():
    import uuid
    from afp.redis_backend import RedisQueue, RedisResultStore
    run = "t" + uuid.uuid4().hex[:8]
    q = RedisQueue("redis://localhost:6390/0", "t", num_partitions=4, max_attempts=3, run_id=run)
    assert q.enqueue([(f"h{i}", i % 4, {"i": i}) for i in range(10)]) == 10
    assert q.enqueue([("h0", 0, {"i": 0})]) == 0                      # idempotent
    got = q.lease("w0", [0], 3, 60)
    assert len(got) == 3 and got[0][1]["i"] % 4 == 0                  # home partition first
    more = q.lease("w0", [0], 5, 60)                                  # stealing from other partitions
    assert len(more) == 5
    q.ack([t for t, _, _ in got])
    assert q.counts()["DONE"] == 3
    # crashed consumer: its leased messages come back after the lease (XAUTOCLAIM)
    q2 = RedisQueue("redis://localhost:6390/0", "t", 4, 3, run_id=run)
    lost = q2.lease("crashed", [1, 2, 3], 2, 60)
    time.sleep(0.3)
    q3 = RedisQueue("redis://localhost:6390/0", "t", 4, 3, run_id=run)
    back = q3.lease("w3", [1, 2, 3], 10, lease_s=0.2)
    assert {t for t, _, _ in lost} <= {t for t, _, _ in back}
    # nack -> retry -> dead letter after 3 attempts
    th = back[0][0]
    q3.nack(th, "x")
    for _ in range(4):
        again = [x for x in q3.lease("w3", [0, 1, 2, 3], 20, 60) if x[0] == th]
        if not again:
            break
        q3.nack(th, "x")
    assert q3.r.sismember(f"{q3.ns}:dead", th)
    # release: messages are claimable by another consumer at once, attempt not charged
    q4 = RedisQueue("redis://localhost:6390/0", "rel", 2, 3, run_id=run)
    q4.enqueue([("x", 0, {}), ("y", 1, {})])
    held = q4.lease("w4", [0, 1], 2, 60)
    q4.release([t for t, _, _ in held])
    q5 = RedisQueue("redis://localhost:6390/0", "rel", 2, 3, run_id=run)
    back = q5.lease("w5", [0, 1], 2, 60)
    assert sorted(t for t, _, _ in back) == ["x", "y"] and all(a == 1 for _, _, a in back)
    rs = RedisResultStore("redis://localhost:6390/0", run)
    r = VerifyResult("h", "p", "v1", 0, "COMPILE_OK", "", 12.0, 100.0, "w0", run, 1)
    rs.upsert(r)
    rs.upsert(r)
    rows = rs.rows()
    assert len(rows) == 1 and rows[0]["write_count"] == 2
