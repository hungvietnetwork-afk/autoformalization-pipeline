"""Orchestrator: Queue problems -> Batch Inference -> Lean Verify Pool -> Store / Aggregator.

    python -m afp.pipeline --tier T1K --workers 2 --batch 8 --run-id demo_T1K_B

One run = one fresh SQLite database (runs/<run_id>/run.db) holding the two queues, the result
table and the event log. Raw logs (Appendix-B style) are exported next to it.
"""
from __future__ import annotations

import argparse
import csv
import json
import multiprocessing as mp
import os
import shutil
import threading
import time

import psutil

from .aggregator import aggregate_run
from .inference.batchfile import load_units, read_tier
from .prompts import LEAN_HEADER
from .factory import make_queue, make_store
from .schema import partition_index, task_hash
from .store import ResultStore
from .workers import inference_main, verifier_main

from . import runrecord
from .paths import AUDIT, CANDIDATES_DB, RAW, ROOT, RUNS, TABLES, TIERS_DIR, UNITS, result_path, run_dir


def build_workload(tier: str, prompt_version: str, k: int, replicas: int = 1,
                   units_path: str = None) -> list[dict]:
    """Problem payloads for q_problems.

    replicas > 1 builds a *trace-replay* workload: every problem of the tier is replayed `replicas`
    times under a new id (replay<j>:<problem_id>); each replay re-uses the real candidate of the
    original problem (source_task_hash), so Lean does real work for every task but no model call
    is made. Used for the 10K tier, because inference was run for 1K problems only.
    """
    units = load_units(units_path or UNITS)
    pids = read_tier(os.path.join(TIERS_DIR, f"{tier}.txt"))
    out = []
    for j in range(replicas):
        for pid in pids:
            p = {"problem_id": pid if replicas == 1 else f"replay{j}:{pid}", "source_problem_id": pid,
                 "natural_statement": units[pid].natural_statement, "prompt_version": prompt_version,
                 "k": k, "seed": 0, "source": units[pid].source, "domain": units[pid].domain}
            if replicas > 1:
                p["source_task_hash"] = task_hash(pid, prompt_version, 0)
            out.append(p)
    return out


class MemoryMonitor(threading.Thread):
    """Samples system memory and every Lean REPL process every `interval` s (cheap /proc reads).

    pool_mb = max(RssFile) + sum(RssAnon): the .olean pages are mmapped read-only and shared by all
    REPLs, so they are counted once; the private heap of each REPL is added up. (Summing RSS would
    count the ~4.2 GB of shared pages once per worker.)
    """

    def __init__(self, interval: float = 0.5):
        super().__init__(daemon=True)
        self.interval, self.samples, self.stop_flag = interval, [], threading.Event()
        self.me = psutil.Process()

    @staticmethod
    def _status(pid: int) -> dict:
        d = {}
        try:
            with open(f"/proc/{pid}/status") as f:
                for line in f:
                    if line.startswith(("VmRSS", "RssAnon", "RssFile")):
                        k, v = line.split(":")
                        d[k] = int(v.split()[0]) / 1024.0
        except OSError:
            pass
        return d

    def run(self):
        psutil.cpu_percent(None)
        while not self.stop_flag.is_set():
            vm, sw = psutil.virtual_memory(), psutil.swap_memory()
            anon, files, rss, n = 0.0, 0.0, 0.0, 0
            try:
                kids = [c for c in self.me.children(recursive=True) if c.name() == "repl"]
            except psutil.Error:
                kids = []
            for ch in kids:
                d = self._status(ch.pid)
                if d:
                    anon += d.get("RssAnon", 0.0)
                    files = max(files, d.get("RssFile", 0.0))
                    rss += d.get("VmRSS", 0.0)
                    n += 1
            self.samples.append({"ts": time.time(), "used_mb": round((vm.total - vm.available) / 2**20, 1),
                                 "swap_mb": round(sw.used / 2**20, 1), "pool_mb": round(files + anon, 1),
                                 "repl_anon_mb": round(anon, 1), "repl_file_mb": round(files, 1),
                                 "repl_rss_sum_mb": round(rss, 1), "n_repl": n, "cpu_pct": psutil.cpu_percent(None)})
            self.stop_flag.wait(self.interval)

    def stop(self):
        self.stop_flag.set()


def run_pipeline(run_id: str, tier: str, workers: int, batch: int, prompt_version: str = "v1_zeroshot",
                 k: int = 1, replicas: int = 1, partitions: int = 16, timeout_s: float = 10.0,
                 lease_s: float = 60.0, runs_dir: str = None, candidates_db: str = None,
                 backend: dict | None = None, extra: dict | None = None, fault: dict | None = None,
                 broker: dict | None = None) -> dict:
    runs_dir = runs_dir or RUNS
    run_dir = os.path.join(runs_dir, run_id)
    if os.path.exists(run_dir):
        shutil.rmtree(run_dir)
    os.makedirs(run_dir)
    db = os.path.join(run_dir, "run.db")
    cfg = {"run_id": run_id, "db": db, "tier": tier, "workers": workers, "batch": batch, "partitions": partitions,
           "timeout_s": timeout_s, "lease_s": lease_s, "header": LEAN_HEADER, "prompt_version": prompt_version,
           "k": k, "replicas": replicas,
           "backend": backend or {"kind": "cache", "db": candidates_db or CANDIDATES_DB},
           "broker": broker or {"kind": "sqlite"}, **(extra or {})}
    payloads = build_workload(tier, prompt_version, k, replicas)
    cfg["n_problems"] = len(payloads)
    with open(os.path.join(run_dir, "config.json"), "w") as f:
        json.dump({kk: v for kk, v in cfg.items() if kk != "header"}, f, indent=1)

    if cfg["broker"]["kind"] == "redis":      # fresh namespace; remote workers read the run config from it
        import redis
        rc = redis.Redis.from_url(cfg["broker"]["url"])
        for key in rc.scan_iter(f"afp:{run_id}:*", count=1000):
            rc.delete(key)
        rc.set(f"afp:{run_id}:cfg", json.dumps(cfg))
    rs = make_store(cfg)
    qp = make_queue(cfg, "problems")
    make_queue(cfg, "verify")
    mon = MemoryMonitor()
    mon.start()
    t_start = time.time()
    rs.event(run_id, "orchestrator", "run_start", {"n_problems": len(payloads)})
    qp.enqueue([(p["problem_id"], partition_index(p["problem_id"], partitions), p) for p in payloads])
    rs.event(run_id, "orchestrator", "problems_enqueued", {"partition_sizes": qp.partition_sizes()})

    ctx = mp.get_context("spawn")
    procs = [ctx.Process(target=verifier_main, args=(cfg, i), name=f"lean-{i}") for i in range(workers)]
    procs.append(ctx.Process(target=inference_main, args=(cfg,), name="inf-0"))
    for p in procs:
        p.start()

    killed = None
    if fault:   # fault injection: SIGKILL one verifier after `after_results` results were written
        while killed is None and any(p.is_alive() for p in procs):
            n = rs.count()
            if n >= fault["after_results"]:
                victim = procs[fault.get("worker", 0)]
                for ch in psutil.Process(victim.pid).children(recursive=True):
                    ch.kill()
                victim.kill()
                killed = {"worker": victim.name, "at_results": n, "ts": time.time()}
                rs.event(run_id, "orchestrator", "fault_injected", killed)
            time.sleep(0.05)
        if killed and fault.get("restart", False):
            # a replacement worker joins later, like an autoscaler would do
            rp = ctx.Process(target=verifier_main, args=(cfg, fault.get("worker", 0)), name="lean-replacement")
            rp.start()
            procs.append(rp)

    for p in procs:
        p.join()
    t_end = time.time()
    mon.stop()
    mon.join()
    rs.event(run_id, "orchestrator", "run_end", {"exitcodes": {p.name: p.exitcode for p in procs}})

    # ---------------- raw logs (Appendix B): one row per verification, plus events and memory timeline
    rows = rs.rows(run_id)
    with open(os.path.join(run_dir, "raw_results.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else ResultStore.COLS)
        w.writeheader()
        for r in rows:
            w.writerow({**r, "compiler_message": (r["compiler_message"] or "")[:300].replace("\n", " ")})
    with open(os.path.join(run_dir, "raw_results.jsonl"), "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    with open(os.path.join(run_dir, "events.jsonl"), "w", encoding="utf-8") as f:
        for e in rs.events(run_id):
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
    with open(os.path.join(run_dir, "memory.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["ts", "used_mb", "swap_mb", "pool_mb", "repl_anon_mb", "repl_file_mb", "repl_rss_sum_mb", "n_repl", "cpu_pct"])
        w.writeheader()
        w.writerows(mon.samples)
    metrics = aggregate_run(run_dir, t_start, t_end, mon.samples, cfg)
    metrics["fault"] = killed
    with open(os.path.join(run_dir, "metrics.json"), "w") as f:
        json.dump(metrics, f, indent=1)
    exitcodes = {p.name: p.exitcode for p in procs}
    complete = metrics["n_problems_with_result"] == metrics["n_problems"] and not metrics.get("dead_letter")
    status = "ok" if complete and all(c == 0 for c in exitcodes.values()) else \
        ("ok_with_worker_failures" if complete else "incomplete")
    runrecord.write(run_dir, cfg, metrics, t_start, status,
                    notes=f"exit codes {exitcodes}" if status != "ok" else None)
    return metrics


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--tier", default="T100")
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--batch", type=int, default=1)
    ap.add_argument("--prompt-version", default="v1_zeroshot")
    ap.add_argument("--k", type=int, default=1)
    ap.add_argument("--replicas", type=int, default=1)
    ap.add_argument("--partitions", type=int, default=16)
    ap.add_argument("--timeout", type=float, default=10.0)
    ap.add_argument("--redis", help="redis://host:6379/0 -> use Redis as broker/result store (multi-machine)")
    a = ap.parse_args(argv)
    m = run_pipeline(a.run_id, a.tier, a.workers, a.batch, a.prompt_version, a.k, a.replicas, a.partitions, a.timeout,
                     broker={"kind": "redis", "url": a.redis} if a.redis else None)
    print(json.dumps({k: v for k, v in m.items() if k not in ("status_counts_by_source",)}, indent=1))


if __name__ == "__main__":
    main()
