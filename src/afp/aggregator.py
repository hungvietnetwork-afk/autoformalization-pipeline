"""Aggregator / Reducer (PDF section 3): group results by problem_id.

* Pass@k(P_i) = 1 if at least one candidate is COMPILE_OK else 0   (+ unbiased pass@k estimator
  1 - C(n-c,k)/C(n,k) when n > k samples exist)
* Curated output: among COMPILE_OK candidates pick the shortest code, then the fastest check
* Global metrics: throughput, P95 latency, peak RAM, compile rate, token cost
"""
from __future__ import annotations

import collections
import json
import math
import os
from typing import Iterable

import numpy as np

from .schema import COMPILE_OK
from .factory import make_queue, make_store


def pass_at_k(n: int, c: int, k: int) -> float:
    if n - c < k:
        return 1.0
    return 1.0 - math.comb(n - c, k) / math.comb(n, k)


def pct(values: Iterable[float], q: float) -> float:
    v = list(values)
    return float(np.percentile(v, q)) if v else float("nan")


# semantic verdicts, best first (afp.semantic); unknown / unchecked sit in the middle
VERDICT_RANK = {"EQUIV_GOLD": 0, "PROVED_CONSISTENT": 1, "NO_EVIDENCE_OF_ERROR": 2, "NOT_CHECKED_SLOW": 3, None: 3,
                "ANSWER_MISSING": 4, "ARITHMETIC_ONLY": 4, "TRIVIAL": 5, "FALSE": 6, "VACUOUS": 6}


def curate(rows: list[dict], code_of: dict[str, str], verdict_of: dict[str, str] | None = None) -> dict[str, dict]:
    """problem_id -> best compiled candidate: best semantic verdict (if known), then shortest code, then lowest
    latency. Without verdicts this is the plain 'shortest compiled statement' rule."""
    verdict_of = verdict_of or {}
    best = {}
    for r in rows:
        if r["status"] != COMPILE_OK:
            continue
        key = (VERDICT_RANK.get(verdict_of.get(r["task_hash"]), 3), len(code_of.get(r["task_hash"], "")), r["latency_ms"])
        cur = best.get(r["problem_id"])
        if cur is None or key < cur["_key"]:
            best[r["problem_id"]] = {**r, "_key": key, "lean_code": code_of.get(r["task_hash"], "")}
    for v in best.values():
        v.pop("_key", None)
    return best


def aggregate_run(run_dir: str, t_start: float, t_end: float, mem_samples: list[dict], cfg: dict) -> dict:
    rs = make_store(cfg)
    rows = rs.rows(cfg["run_id"])
    events = rs.events(cfg["run_id"])
    qv = make_queue(cfg, "verify")
    q_counts = {k: v for k, v in qv.counts().items() if v}
    attempts = qv.attempts()
    n_problems = cfg["n_problems"]
    by_problem = collections.defaultdict(list)
    for r in rows:
        by_problem[r["problem_id"]].append(r)
    status = collections.Counter(r["status"] for r in rows)
    checked = [r["latency_ms"] for r in rows if r["latency_ms"] > 0]
    finished = [r["finished_at"] for r in rows if r["finished_at"]]
    ready = [json.loads(e["detail"]) for e in events if e["kind"] == "worker_ready"]
    first_ready = min((e["ts"] for e in events if e["kind"] == "worker_ready"), default=t_start)
    makespan = (max(finished) if finished else t_end) - t_start
    steady = (max(finished) - first_ready) if finished else float("nan")
    n_cands = len(rows)
    passk = [1 if any(r["status"] == COMPILE_OK for r in rs_) else 0 for rs_ in by_problem.values()]
    base_used = mem_samples[0]["used_mb"] if mem_samples else 0.0
    inf_done = [json.loads(e["detail"]) for e in events if e["kind"] == "inference_done"]
    m = {
        "run_id": cfg["run_id"], "tier": cfg["tier"], "workers": cfg["workers"], "batch": cfg["batch"],
        "replicas": cfg.get("replicas", 1), "prompt_version": cfg["prompt_version"], "k": cfg["k"],
        "n_problems": n_problems, "n_candidates": n_cands,
        "n_problems_with_result": len(by_problem),
        "makespan_s": round(makespan, 3),
        "throughput_problems_per_s": round(n_problems / makespan, 3) if makespan > 0 else None,
        "throughput_candidates_per_s": round(n_cands / makespan, 3) if makespan > 0 else None,
        "steady_window_s": round(steady, 3),
        "steady_throughput_candidates_per_s": round(n_cands / steady, 3) if steady and steady > 0 else None,
        "latency_ms_p50": round(pct(checked, 50), 2), "latency_ms_p95": round(pct(checked, 95), 2),
        "latency_ms_p99": round(pct(checked, 99), 2), "latency_ms_max": round(max(checked), 2) if checked else None,
        "latency_ms_mean": round(float(np.mean(checked)), 2) if checked else None,
        "lean_busy_s": round(sum(checked) / 1000.0, 2),
        # share of the workers' steady-state time actually spent inside Lean (rest: queue, IPC, Python)
        "lean_busy_fraction": round(sum(checked) / 1000.0 / (cfg["workers"] * steady), 3) if steady and steady > 0 else None,
        "compile_rate": round(status.get(COMPILE_OK, 0) / n_cands, 4) if n_cands else None,
        "pass_at_k": round(sum(passk) / n_problems, 4) if n_problems else None,
        "status_counts": dict(status),
        "worker_startup_s": [r["startup_s"] for r in ready],
        "peak_pool_mb": max((s["pool_mb"] for s in mem_samples), default=0.0),
        "peak_pool_anon_mb": max((s["repl_anon_mb"] for s in mem_samples), default=0.0),
        "peak_rss_sum_mb": max((s["repl_rss_sum_mb"] for s in mem_samples), default=0.0),
        "peak_system_used_mb": max((s["used_mb"] for s in mem_samples), default=0.0),
        "peak_system_used_delta_mb": round(max((s["used_mb"] for s in mem_samples), default=base_used) - base_used, 1),
        "peak_swap_mb": max((s["swap_mb"] for s in mem_samples), default=0.0),
        "mean_cpu_pct": round(float(np.mean([s["cpu_pct"] for s in mem_samples])), 1) if mem_samples else None,
        "peak_worker_rss_mb": max((r["peak_ram_mb"] for r in rows), default=0.0),
        "queue_final": q_counts, "dead_letter": q_counts.get("DEAD", 0),
        "retried_tasks": sum(1 for a in attempts if a > 1),
        "duplicate_result_rows": n_cands - len({r["task_hash"] for r in rows}),
        "overwritten_results": sum(1 for r in rows if r.get("write_count", 1) > 1),
        "repl_timeouts": sum(1 for e in events if e["kind"] == "repl_timeout"),
        "repl_crashes": sum(1 for e in events if e["kind"] == "repl_crash"),
        "repl_restarts": sum(1 for e in events if e["kind"] in ("repl_restarted", "repl_recycled")),
        "inference": inf_done[0] if inf_done else None,
    }
    return m
