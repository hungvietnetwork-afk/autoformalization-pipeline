"""Scalability experiments (PDF section 5).

  python -m afp.experiments matrix   # 3 data tiers x 3 configs x 3 repeats -> median
  python -m afp.experiments scaling  # Lean workers 1, 2, 4, 8 on the 10K tier
  python -m afp.experiments fault    # SIGKILL one worker mid-run -> retry + idempotency check
  python -m afp.experiments determinism  # same input twice -> same output?
  python -m afp.experiments baseline     # required baseline: one problem per request, 1 candidate, 1 worker, no repair
  python -m afp.experiments batch        # batch size 1/8/32 (+ indexed queue at batch 1) at a fixed 2 workers, 3 tiers
  python -m afp.experiments retry        # retry budget 1 vs 3 deliveries under a worker kill
  python -m afp.experiments repro        # the T1K/A cell again (3x) on the machine of 26/10 (hardware comparability)
  python -m afp.experiments release      # ablation: release the rest of a batch before a REPL restart, on vs off

Grids (tiers, configurations, repeats, timeouts, fault settings) are read from configs/experiments.json.

Tiers: T100 and T1K use the real zero-shot candidates. T10K is a trace-replay of the T1K candidates
(10 replicas under new task ids): Lean does real work for all 10,000 tasks, but no model is called,
because LLM inference was limited to 1K problems.
"""
from __future__ import annotations

import csv
import json
import os
import statistics
import sys
import time

from .paths import CONFIGS as CONFIG_DIR, RAW, RUNS, TABLES
from .pipeline import ROOT, run_pipeline


def load_grid(path: str = None) -> dict:
    """Experiment grids: configs/experiments.json (one section per experiment)."""
    with open(path or os.path.join(CONFIG_DIR, "experiments.json"), encoding="utf-8") as f:
        return json.load(f)


G = load_grid()
CONFIGS = G["matrix"]["configs"]
TIERS = G["tiers"]
KEYS = ["makespan_s", "throughput_problems_per_s", "throughput_candidates_per_s", "steady_throughput_candidates_per_s",
        "latency_ms_p50", "latency_ms_p95", "latency_ms_p99", "compile_rate", "pass_at_k", "peak_pool_mb",
        "peak_pool_anon_mb", "peak_rss_sum_mb", "peak_system_used_delta_mb", "peak_swap_mb", "mean_cpu_pct",
        "retried_tasks", "duplicate_result_rows", "repl_timeouts", "dead_letter", "lean_busy_fraction",
        "steady_window_s", "latency_ms_mean"]
RES = TABLES


def _flat(m: dict, extra: dict) -> dict:
    row = {**extra, **{k: m.get(k) for k in KEYS}}
    row["startup_s_mean"] = round(statistics.mean(m["worker_startup_s"]), 2) if m["worker_startup_s"] else None
    row["n_candidates"] = m["n_candidates"]
    return row


def _append(path: str, row: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    new = not os.path.exists(path)
    with open(path, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(row.keys()))
        if new:
            w.writeheader()
        w.writerow(row)


def _done_ids(path: str) -> set:
    if not os.path.exists(path):
        return set()
    with open(path) as f:
        return {r["run_id"] for r in csv.DictReader(f)}


def matrix(repeats: int = G["matrix"]["repeats"], tiers: tuple = tuple(TIERS),
           timeout_s: float = G["matrix"]["timeout_s"]) -> None:
    out = os.path.join(RAW, "matrix_runs.csv")
    done = _done_ids(out)
    for rep in range(repeats):                 # repeat loop outermost -> drift spreads over all cells
        for tname, t in TIERS.items():
            if tname not in tiers:
                continue
            for cname, c in CONFIGS.items():
                rid = f"mx_{tname}_{cname}_r{rep}"
                if rid in done:
                    continue
                t0 = time.time()
                m = run_pipeline(rid, t["tier"], c["workers"], c["batch"], replicas=t["replicas"], timeout_s=timeout_s)
                _append(out, _flat(m, {"run_id": rid, "tier": tname, "config": cname, "repeat": rep,
                                       "workers": c["workers"], "batch": c["batch"]}))
                print(f"{rid}: {time.time() - t0:.0f}s thr={m['throughput_problems_per_s']} p95={m['latency_ms_p95']}",
                      flush=True)
    summarize(out, os.path.join(RES, "matrix_median.csv"), ["tier", "config", "workers", "batch"])


def scaling(workers=tuple(G["scaling"]["workers"]), repeats: int = G["scaling"]["repeats"],
            batch: int = G["scaling"]["batch"], tier: str = G["scaling"]["tier"],
            timeout_s: float = G["scaling"]["timeout_s"]) -> None:
    """Worker curve on the 10K tier. Runs with a 30 s wall timeout: the matrix (week-2 design, 10 s) showed that under
    CPU contention a 10 s wall clock turns a deterministic heartbeat error (~4 s alone) into TIMEOUT + a ~40 s REPL
    restart, so with 10 s the curve would mostly measure restarts. Heartbeats (400k) stay the primary limit."""
    out = os.path.join(RAW, "scaling_runs.csv")
    done = _done_ids(out)
    t = TIERS[tier]
    for rep in range(repeats):
        for w in workers:
            rid = f"sc_{tier}_w{w}_r{rep}"
            if rid in done:
                continue
            t0 = time.time()
            m = run_pipeline(rid, t["tier"], w, batch, replicas=t["replicas"], timeout_s=timeout_s)
            _append(out, _flat(m, {"run_id": rid, "tier": tier, "workers": w, "batch": batch, "repeat": rep,
                                   "timeout_s": timeout_s}))
            print(f"{rid}: {time.time() - t0:.0f}s thr={m['throughput_problems_per_s']} steady={m['steady_throughput_candidates_per_s']}",
                  flush=True)
    summarize(out, os.path.join(RES, "scaling_median.csv"), ["tier", "workers", "batch", "timeout_s"])


def summarize(src: str, dst: str, group: list[str]) -> None:
    with open(src) as f:
        rows = list(csv.DictReader(f))
    groups: dict[tuple, list[dict]] = {}
    for r in rows:
        groups.setdefault(tuple(r[g] for g in group), []).append(r)
    out = []
    for key, rs in groups.items():
        row = dict(zip(group, key))
        row["n_runs"] = len(rs)
        for k in KEYS + ["startup_s_mean", "n_candidates"]:
            vals = [float(r[k]) for r in rs if r.get(k) not in (None, "", "None")]
            row[k] = round(statistics.median(vals), 4) if vals else None
            if k in ("throughput_problems_per_s", "latency_ms_p95", "steady_throughput_candidates_per_s") and len(vals) > 1:
                row[k + "_min"], row[k + "_max"] = round(min(vals), 4), round(max(vals), 4)
        out.append(row)
    keys = sorted({k for r in out for k in r}, key=lambda k: (k not in group, k != "n_runs", k))
    with open(dst, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(out)
    print("wrote", dst)


def fault() -> None:
    """Kill lean-0 (and its REPL) after 300 results; the survivor must finish everything exactly once."""
    g = G["fault"]
    ref = run_pipeline("fault_ref_T1K_B", g["tier"], g["workers"], g["batch"])
    m = run_pipeline("fault_kill_T1K_B", g["tier"], g["workers"], g["batch"],
                     fault={"after_results": g["kill_after_results"], "worker": g["kill_worker"]}, lease_s=g["lease_s"])
    import sqlite3
    a = dict(sqlite3.connect(os.path.join(RUNS, "fault_ref_T1K_B/run.db")).execute(
        "SELECT task_hash, status FROM results").fetchall())
    b = dict(sqlite3.connect(os.path.join(RUNS, "fault_kill_T1K_B/run.db")).execute(
        "SELECT task_hash, status FROM results").fetchall())
    same = sum(1 for k in a if b.get(k) == a[k])
    rep = {"ref_candidates": len(a), "fault_candidates": len(b), "same_status": same,
           "retried_tasks": m["retried_tasks"], "overwritten_results": m["overwritten_results"],
           "duplicate_result_rows": m["duplicate_result_rows"], "dead_letter": m["dead_letter"],
           "inference": m["inference"], "fault": m["fault"], "makespan_ref_s": ref["makespan_s"],
           "makespan_fault_s": m["makespan_s"]}
    os.makedirs(RES, exist_ok=True)
    json.dump(rep, open(os.path.join(RES, "fault_tolerance.json"), "w"), indent=1)
    print(json.dumps(rep, indent=1))


def determinism() -> None:
    """Same input -> same output? Compare the statuses of the 9 T1K runs of the matrix (configs A, B, C x 3 repeats):
    within a configuration (pure repeat) and across configurations (different load on the same 2 vCPUs)."""
    import sqlite3
    runs = [f"mx_T1K_{c}_r{i}" for c in CONFIGS for i in range(3)]
    st, pid = {}, {}
    for r in runs:
        p = os.path.join(RUNS, r, "run.db")
        if not os.path.exists(p):
            continue
        rows = sqlite3.connect(p).execute("SELECT task_hash, status, problem_id, latency_ms FROM results").fetchall()
        st[r] = {th: s for th, s, _, _ in rows}
        pid.update({th: (p_, ms) for th, _, p_, ms in rows})
    keys = set.intersection(*(set(v) for v in st.values()))

    def agree(names):
        return sum(1 for k in keys if len({st[n][k] for n in names}) == 1)
    within = {c: agree([r for r in st if r.startswith(f"mx_T1K_{c}_")]) for c in CONFIGS}
    across = [k for k in keys if len({st[n][k] for n in st}) > 1]
    rep = {"runs": list(st), "tasks": len(keys), "identical_within_config": within,
           "identical_across_all_runs": len(keys) - len(across),
           "disagreements": [{"problem_id": pid[k][0], "status_by_run": {n: st[n][k] for n in st}} for k in across]}
    json.dump(rep, open(os.path.join(RES, "determinism.json"), "w"), indent=1)
    print(json.dumps(rep, indent=1))


def broker(url: str = G["broker"]["redis_url"]) -> None:
    """Same workload on the SQLite broker vs the Redis broker, plus a worker that joins from 'another
    machine' (a separate `python -m afp.worker` process that only knows the Redis URL and run id)."""
    import subprocess
    import threading
    out = {}
    for kind in ("sqlite", "redis"):
        b = {"kind": "redis", "url": url} if kind == "redis" else None
        g = G["broker"]
        m = run_pipeline(f"broker_{kind}_T1K_B", g["tier"], g["workers"], g["batch"], broker=b)
        out[kind] = {k: m[k] for k in ("makespan_s", "steady_throughput_candidates_per_s", "latency_ms_p95",
                                       "compile_rate", "duplicate_result_rows", "retried_tasks")}
    # remote join: 1 local worker + 1 worker started later as an independent process
    rid = "broker_redis_join_T1K"
    box = {}
    th = threading.Thread(target=lambda: box.update(m=run_pipeline(rid, "T1K", 1, 8, broker={"kind": "redis", "url": url})))
    th.start()
    time.sleep(8)
    p = subprocess.Popen([sys.executable, "-m", "afp.worker", "--redis", url, "--run-id", rid, "--idx", "1", "--of", "2"],
                         cwd=ROOT)
    th.join()
    p.wait(600)
    import collections
    from .redis_backend import RedisResultStore
    per_worker = collections.Counter(r["worker_id"] for r in RedisResultStore(url, rid).rows())
    out["remote_join"] = {"makespan_s": box["m"]["makespan_s"], "results_per_worker": dict(per_worker),
                          "duplicate_result_rows": box["m"]["duplicate_result_rows"], "n_candidates": box["m"]["n_candidates"]}
    json.dump(out, open(os.path.join(RES, "broker_comparison.json"), "w"), indent=1)
    print(json.dumps(out, indent=1))


def baseline() -> None:
    """Required baseline (guide, group 5, section 7): zero-shot, ONE problem per request, one candidate, one Lean
    worker, no repair. 20 problems (stratified subset of T100: data/jobs/v1_zeroshot_1req/SUBSET_20.json) were sent
    as 20 separate requests (prompt v1_zeroshot_1req = same text as v1_zeroshot). The batch-job candidates of the
    same 20 problems are verified with the same configuration A (1 worker, batch 1, 10 s) for comparison."""
    out, g = {}, G["baseline"]
    for rid, pv in g["runs"].items():
        m = run_pipeline(rid, g["tier"], g["workers"], g["batch"], prompt_version=pv, timeout_s=g["timeout_s"])
        out[pv] = {k: m[k] for k in ("run_id", "n_candidates", "compile_rate", "pass_at_k", "status_counts",
                                     "latency_ms_p50", "latency_ms_p95", "makespan_s")}
        print(rid, json.dumps(out[pv]), flush=True)
    os.makedirs(TABLES, exist_ok=True)
    json.dump(out, open(os.path.join(TABLES, "baseline_runs.json"), "w"), indent=1)


BATCH_SWEEP = G["batch_sweep"]["configs"]


def batch(repeats: int = G["batch_sweep"]["repeats"], tiers: tuple = tuple(G["batch_sweep"]["tiers"]),
          workers: int = G["batch_sweep"]["workers"], timeout_s: float = G["batch_sweep"]["timeout_s"]) -> None:
    """Batch size at a FIXED worker count (the matrix changes both at once). 2 workers = the number of vCPUs, wall
    timeout 30 s so heartbeats stay the primary limit (as in the worker curve). b1_idx = batch 1 with the indexed
    queue (covering indexes + periodic sweeps): the end-to-end effect of the queue fix found by bench_queue."""
    out = os.path.join(RAW, "batch_runs.csv")
    done = _done_ids(out)
    for rep in range(repeats):
        for tname in tiers:
            t = TIERS[tname]
            for cname, c in BATCH_SWEEP.items():
                rid = f"bs_{tname}_{cname}_r{rep}"
                if rid in done:
                    continue
                broker = {"kind": "sqlite", "indexed": True} if c.get("indexed") else None
                t0 = time.time()
                m = run_pipeline(rid, t["tier"], workers, c["batch"], replicas=t["replicas"], timeout_s=timeout_s,
                                 broker=broker)
                _append(out, _flat(m, {"run_id": rid, "tier": tname, "config": cname, "repeat": rep, "workers": workers,
                                       "batch": c["batch"], "indexed": bool(c.get("indexed")), "timeout_s": timeout_s}))
                print(f"{rid}: {time.time() - t0:.0f}s thr={m['throughput_problems_per_s']} "
                      f"steady={m['steady_throughput_candidates_per_s']}", flush=True)
    summarize(out, os.path.join(TABLES, "batch_median.csv"), ["tier", "config", "workers", "batch", "indexed", "timeout_s"])


def retry(repeats: int = G["retry"]["repeats"]) -> None:
    """Retry budget (guide: 'co/khong retry'): the same worker kill as `fault`, with max_attempts 1 (no re-delivery:
    an expired lease sends the task to dead-letter) vs 3 (default)."""
    out, g = os.path.join(RAW, "retry_runs.csv"), G["retry"]
    done = _done_ids(out)
    for rep in range(repeats):
        for budget in g["max_attempts"]:
            rid = f"rt_T1K_B_kill_max{budget}_r{rep}"
            if rid in done:
                continue
            m = run_pipeline(rid, g["tier"], g["workers"], g["batch"],
                             fault={"after_results": g["kill_after_results"], "worker": g["kill_worker"]},
                             lease_s=g["lease_s"], broker={"kind": "sqlite", "max_attempts": budget})
            row = {"run_id": rid, "max_attempts": budget, "repeat": rep, "n_problems": m["n_problems"],
                   "results": m["n_problems_with_result"], "dead_letter": m["dead_letter"],
                   "retried_tasks": m["retried_tasks"], "overwritten_results": m["overwritten_results"],
                   "duplicate_result_rows": m["duplicate_result_rows"], "makespan_s": m["makespan_s"],
                   "killed_at_results": (m.get("fault") or {}).get("at_results")}
            _append(out, row)
            print(json.dumps(row), flush=True)
    with open(out) as f:
        rows = list(csv.DictReader(f))
    summ = {}
    for b in sorted({r["max_attempts"] for r in rows}):
        rs = [r for r in rows if r["max_attempts"] == b]
        summ[f"max_attempts_{b}"] = {k: [float(r[k]) for r in rs] for k in
                                     ("results", "dead_letter", "retried_tasks", "overwritten_results",
                                      "duplicate_result_rows", "makespan_s")}
        summ[f"max_attempts_{b}"]["runs"] = len(rs)
    json.dump(summ, open(os.path.join(TABLES, "retry_ablation.json"), "w"), indent=1)
    print(json.dumps(summ, indent=1))


def _check_time_s(run: str) -> dict:
    """Lean time spent on candidates that did NOT hit the wall timeout (the 'useful' checking work), and the
    number of timeouts, from the raw results of one run."""
    p = os.path.join(RUNS, run, "raw_results.csv")
    if not os.path.exists(p):
        return {}
    with open(p) as f:
        rows = list(csv.DictReader(f))
    ok = [float(r["latency_ms"]) for r in rows if r["status"] != "TIMEOUT"]
    return {"useful_check_time_s": round(sum(ok) / 1000, 2), "timeouts": sum(r["status"] == "TIMEOUT" for r in rows)}


REPRO_KEYS = ("throughput_problems_per_s", "steady_throughput_candidates_per_s", "latency_ms_p50", "latency_ms_p95",
              "compile_rate", "makespan_s", "repl_timeouts")


def repro(repeats: int = G["repro"]["repeats"]) -> None:
    """Re-run one matrix cell (T1K, config A: 1 worker, batch 1, 10 s) on the machine used on 26/10, 3 times, to
    check that results from the two sessions are comparable (same vCPU count and RAM). The first repeat keeps its
    original id `repro_T1K_A`. Also reports the Lean time of the non-timeout candidates, which separates hardware
    speed from rare events (one TIMEOUT costs the 10 s wall clock plus a ~40 s REPL restart)."""
    ids = ["repro_T1K_A"] + [f"repro_T1K_A_r{i}" for i in range(1, repeats)]
    runs = {}
    for rid in ids:
        mp_ = os.path.join(RUNS, rid, "metrics.json")
        g = G["repro"]
        m = json.load(open(mp_)) if os.path.exists(mp_) else run_pipeline(rid, g["tier"], g["workers"], g["batch"],
                                                                          timeout_s=g["timeout_s"])
        runs[rid] = {**{k: m.get(k) for k in REPRO_KEYS}, **_check_time_s(rid)}
        print(rid, json.dumps(runs[rid]), flush=True)
    matrix_runs = {f"mx_T1K_A_r{i}": {**_metrics_of(f"mx_T1K_A_r{i}"), **_check_time_s(f"mx_T1K_A_r{i}")}
                   for i in range(3)}

    def med(rs: dict, k: str):
        vals = [r[k] for r in rs.values() if r.get(k) is not None]
        return round(statistics.median(vals), 3) if vals else None
    keys = REPRO_KEYS + ("useful_check_time_s", "timeouts")
    rep = {"machine_2026_10_26": runs, "machine_2026_10_16_matrix": matrix_runs,
           "median": {"new": {k: med(runs, k) for k in keys}, "matrix": {k: med(matrix_runs, k) for k in keys}}}
    json.dump(rep, open(os.path.join(TABLES, "repro_T1K_A.json"), "w"), indent=1)
    print(json.dumps(rep["median"], indent=1))


def _metrics_of(run: str) -> dict:
    p = os.path.join(RUNS, run, "metrics.json")
    if not os.path.exists(p):
        return {}
    m = json.load(open(p))
    return {k: m.get(k) for k in REPRO_KEYS}


def release(repeats: int = G["release"]["repeats"]) -> None:
    """Ablation of the release-on-restart fix (docs/CHANGELOG.md, 16/10): T1K, config B (2 workers, batch 8, 10 s),
    release on (current code) vs off (the worker keeps the rest of its batch through a ~40 s REPL restart)."""
    out, g = os.path.join(RAW, "release_runs.csv"), G["release"]
    done = _done_ids(out)
    for rep in range(repeats):
        for flag in (True, False):
            rid = f"ab_release_{'on' if flag else 'off'}_T1K_B_r{rep}"
            if rid in done:
                continue
            m = run_pipeline(rid, g["tier"], g["workers"], g["batch"], timeout_s=g["timeout_s"],
                             extra={"release_on_restart": flag})
            row = _flat(m, {"run_id": rid, "release_on_restart": flag, "repeat": rep, "workers": g["workers"],
                            "batch": g["batch"], "timeout_s": g["timeout_s"]})
            row["repl_restarts"] = m.get("repl_restarts")
            _append(out, row)
            print(f"{rid}: steady_window={m.get('steady_window_s')}s makespan={m['makespan_s']}s "
                  f"timeouts={m.get('repl_timeouts')}", flush=True)
    with open(out) as f:
        rows = list(csv.DictReader(f))
    summ = {}
    for flag in ("True", "False"):
        rs = [r for r in rows if r["release_on_restart"] == flag]
        if not rs:
            continue
        d = {"runs": len(rs)}
        for k in ("steady_window_s", "makespan_s", "steady_throughput_candidates_per_s", "throughput_problems_per_s",
                  "latency_ms_p95", "repl_timeouts", "retried_tasks", "duplicate_result_rows", "dead_letter"):
            vals = [float(r[k]) for r in rs if r.get(k) not in (None, "", "None")]
            d[k] = {"median": round(statistics.median(vals), 3), "min": min(vals), "max": max(vals)} if vals else None
        summ["release_on" if flag == "True" else "release_off"] = d
    json.dump(summ, open(os.path.join(TABLES, "release_ablation.json"), "w"), indent=1)
    print(json.dumps(summ, indent=1))


if __name__ == "__main__":
    cmd, args = sys.argv[1], sys.argv[2:]
    if cmd == "matrix" and args:               # e.g. `matrix T100,T1K` then `matrix T10K` (each < 2 h)
        matrix(tiers=tuple(args[0].split(",")))
    else:
        {"matrix": matrix, "scaling": scaling, "fault": fault, "determinism": determinism, "broker": broker,
         "baseline": baseline, "batch": batch, "retry": retry, "repro": repro, "release": release}[cmd]()
