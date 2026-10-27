"""Micro-benchmark of the partitioned SQLite queue alone (no Lean): cost of one lease + ack versus backlog depth.

The matrix showed ~3 ms of queue work per task at the start of a 10K run with batch 1, falling to ~0.8 ms at the end:
each lease sorts the READY rows of its partitions and sweeps the whole table. This measures it in isolation, for the
queue as used in the experiments (indexed=False) and with covering indexes + periodic sweeps (indexed=True).

  python -m afp.bench_queue                    -> results/bench_queue.json
"""
from __future__ import annotations

import json
import os
import statistics
import tempfile
import time

from .queue import PartitionedQueue

from .paths import AUDIT, CANDIDATES_DB, RAW, ROOT, RUNS, TABLES, TIERS_DIR, UNITS, result_path, run_dir


def one(depth: int, indexed: bool, batch: int = 1, n_leases: int = 300, R: int = 16) -> dict:
    with tempfile.TemporaryDirectory() as d:
        q = PartitionedQueue(os.path.join(d, "q.db"), "bench", num_partitions=R, indexed=indexed)
        payload = {"lean_code": "theorem t : (1 : ℕ) + 1 = 2 := by sorry", "problem_id": "p", "prompt_version": "v",
                   "candidate_index": 0}
        q.enqueue((f"h{i:07d}", i % R, payload) for i in range(depth))
        home = [p for p in range(R) if p % 2 == 0]           # worker 0 of 2, as in config B
        lat = []
        for _ in range(n_leases):
            t0 = time.perf_counter()
            got = q.lease("w0", home, batch, lease_s=60)
            q.ack([th for th, _, _ in got])
            lat.append((time.perf_counter() - t0) * 1000)
        q.con.close()
    lat.sort()
    return {"depth": depth, "indexed": indexed, "batch": batch, "leases": n_leases,
            "ms_per_lease_median": round(statistics.median(lat), 3),
            "ms_per_lease_p95": round(lat[int(0.95 * len(lat)) - 1], 3),
            "ms_per_task_median": round(statistics.median(lat) / batch, 3)}


def main(depths=(1_000, 10_000, 100_000), batches=(1, 8, 32)) -> list[dict]:
    rows = []
    for depth in depths:
        for indexed in (False, True):
            for b in batches:
                r = one(depth, indexed, b)
                rows.append(r)
                print(json.dumps(r), flush=True)
    os.makedirs(RAW, exist_ok=True)
    json.dump(rows, open(os.path.join(RAW, "bench_queue.json"), "w"), indent=1)
    return rows


if __name__ == "__main__":
    main()
