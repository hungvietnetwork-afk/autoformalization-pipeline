"""Live terminal demo: a small end-to-end run with progress, then a few examples.

    python -m afp.demo --n 20 --workers 2 --batch 4
    python -m afp.demo --n 20 --workers 2 --kill-after 8      # also show crash recovery
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import threading
import time

from .inference.batchfile import load_units, read_tier
from .paths import CANDIDATES_DB, RUNS, TIERS_DIR, UNITS
from .pipeline import ROOT, run_pipeline

C = {"COMPILE_OK": "\033[32m", "TIMEOUT": "\033[35m", "EMPTY_OUTPUT": "\033[90m"}
RST = "\033[0m"


def pick(n: int) -> list[str]:
    ids = read_tier(os.path.join(TIERS_DIR, "T100.txt"))
    by = {}
    for i in ids:
        by.setdefault(i.split(":")[0], []).append(i)
    want = {"proofnet": 3, "minif2f": 3, "gsm8k": 2}
    out = [x for s, k in want.items() for x in by.get(s, [])[:k]]
    out += [x for x in by.get("math", [])][: max(0, n - len(out))]
    return out[:n]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--batch", type=int, default=4)
    ap.add_argument("--kill-after", type=int, default=0, help="SIGKILL worker 0 after this many results")
    a = ap.parse_args(argv)
    ids = pick(a.n)
    tier = "DEMO"
    with open(os.path.join(TIERS_DIR, f"{tier}.txt"), "w") as f:
        f.write("\n".join(ids) + "\n")
    run_id = f"demo_{int(time.time())}"
    db = os.path.join(RUNS, run_id, "run.db")
    box = {}
    fault = {"after_results": a.kill_after, "worker": 0} if a.kill_after else None
    th = threading.Thread(target=lambda: box.update(m=run_pipeline(run_id, tier, a.workers, a.batch, fault=fault,
                                                                   lease_s=20)))
    print(f"== Autoformalization pipeline demo: {len(ids)} bài, {a.workers} Lean workers, batch={a.batch}")
    print("   Queue problems -> Batch Inference -> Lean Verify Pool -> Store/Aggregator\n")
    th.start()
    t0, seen = time.time(), set()
    while th.is_alive():
        time.sleep(1.0)
        if not os.path.exists(db):
            continue
        try:
            con = sqlite3.connect(db, timeout=5)
            q = dict(con.execute("SELECT state, COUNT(*) FROM q_verify GROUP BY state").fetchall())
            ready = con.execute("SELECT COUNT(*) FROM events WHERE kind='worker_ready'").fetchone()[0]
            rows = con.execute("SELECT task_hash, problem_id, status, latency_ms, worker_id FROM results").fetchall()
            ev = con.execute("SELECT kind, worker_id FROM events WHERE kind IN ('fault_injected','repl_crash')").fetchall()
            con.close()
        except sqlite3.Error:
            continue
        for h, pid, st, ms, wid in rows:
            if h not in seen:
                seen.add(h)
                print(f"   {C.get(st, chr(27) + '[31m')}{st:20s}{RST} {ms:7.1f} ms  {wid:7s} {pid}")
        for kind, wid in ev:
            if ("ev", kind) not in seen:
                seen.add(("ev", kind))
                print(f"   !! {kind} ({wid}) - leased tasks will be re-delivered after the lease expires")
        print(f"   [t={time.time() - t0:5.1f}s] workers ready={ready}/{a.workers}  queue={q}", flush=True)
    th.join()
    m = box["m"]
    print("\n== Kết quả")
    for k in ["n_problems", "makespan_s", "throughput_problems_per_s", "latency_ms_p95", "compile_rate",
              "retried_tasks", "duplicate_result_rows", "dead_letter", "peak_pool_mb"]:
        print(f"   {k:28s} {m.get(k)}")
    units = load_units(UNITS)
    con = sqlite3.connect(db)
    cand = sqlite3.connect(CANDIDATES_DB)
    print("\n== Ví dụ")
    for pid, st, msg, h in con.execute("SELECT problem_id, status, compiler_message, task_hash FROM results LIMIT 4"):
        code = cand.execute("SELECT lean_code FROM candidates WHERE task_hash=?", (h,)).fetchone()
        print(f"-- {pid} [{st}]\n   NL  : {units[pid].natural_statement[:160]!r}")
        print("   Lean: " + (code[0] if code and code[0] else "<empty>").replace("\n", "\n         "))
        if st != "COMPILE_OK":
            print(f"   Lean says: {(msg or '')[:160]!r}")


if __name__ == "__main__":
    main()
