"""Run record (course guide, Appendix B): one `run_record.json` per run with
run_id, timestamp, git_commit, data_version, machine, software, parameters, seed/timeout, metrics, status/log.

Written by run_pipeline() at the end of every run. Runs made before this module existed get a record from
scripts/backfill_run_records.py, which marks the fields it could not observe directly.
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import sys
import time

from .paths import CANDIDATES_DB, ROOT, TIERS_DIR, UNITS

from .lean.repl import DEFAULT_LEAN_ROOT as LEAN_ROOT
TIER_SEED = 42          # data/tiers/*.txt were drawn once with this seed (stratified by source) and are versioned
METRIC_KEYS = ["n_problems", "n_candidates", "makespan_s", "throughput_problems_per_s", "steady_throughput_candidates_per_s",
               "latency_ms_p50", "latency_ms_p95", "latency_ms_p99", "compile_rate", "pass_at_k", "status_counts",
               "peak_pool_mb", "peak_rss_sum_mb", "repl_timeouts", "repl_restarts", "retried_tasks",
               "duplicate_result_rows", "dead_letter", "lean_busy_fraction"]


def sha256_file(path: str, limit_mb: int = 512) -> str | None:
    if not os.path.exists(path) or os.path.getsize(path) > limit_mb * 2 ** 20:
        return None
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _git(args: list[str], cwd: str) -> str | None:
    try:
        return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, timeout=10).stdout.strip() or None
    except Exception:
        return None


def git_state() -> dict:
    commit = _git(["rev-parse", "HEAD"], ROOT)
    dirty = _git(["status", "--porcelain", "--untracked-files=no", "--", "src", "configs", "scripts"], ROOT)
    return {"commit": commit, "code_dirty": bool(dirty)}


def machine() -> dict:
    cpu = None
    try:
        for line in open("/proc/cpuinfo"):
            if line.startswith("model name"):
                cpu = line.split(":", 1)[1].strip()
                break
    except OSError:
        pass
    mem = swap = None
    try:
        for line in open("/proc/meminfo"):
            if line.startswith("MemTotal"):
                mem = round(int(line.split()[1]) / 2 ** 20, 2)
            elif line.startswith("SwapTotal"):
                swap = round(int(line.split()[1]) / 2 ** 20, 2)
    except OSError:
        pass
    return {"cpu": cpu, "vcpus": os.cpu_count(), "ram_gb": mem, "swap_gb": swap, "gpu": None,
            "os": platform.platform()}


def software() -> dict:
    pk = {}
    for name in ("numpy", "pandas", "pyarrow", "duckdb", "psutil", "redis"):
        try:
            pk[name] = __import__(name).__version__
        except Exception:
            pass
    return {"python": sys.version.split()[0], "packages": pk,
            "lean": "4.35.0", "mathlib": _git(["rev-parse", "HEAD"], os.path.join(LEAN_ROOT, "mathlib4")),
            "mathlib_tag": "v4.35.0", "repl": _git(["rev-parse", "HEAD"], os.path.join(LEAN_ROOT, "repl"))}


def data_version(cfg: dict) -> dict:
    tier_file = os.path.join(TIERS_DIR, f"{cfg['tier']}.txt")
    return {"tier": cfg["tier"], "tier_file": os.path.relpath(tier_file, ROOT), "tier_sha256": sha256_file(tier_file),
            "replicas": cfg.get("replicas", 1), "units_file": os.path.relpath(UNITS, ROOT),
            "candidates_db_sha256": sha256_file(cfg.get("backend", {}).get("db") or CANDIDATES_DB)}


def write(run_dir: str, cfg: dict, metrics: dict, t_start: float, status: str, notes: str | None = None) -> dict:
    params = {k: v for k, v in cfg.items() if k not in ("header", "db")}
    rec = {
        "run_id": cfg["run_id"],
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(t_start)),
        "git_commit": git_state(),
        "data_version": data_version(cfg),
        "machine": machine(),
        "software": software(),
        "parameters": params,
        "seed_timeout": {"tier_seed": TIER_SEED, "llm_sampling_seed": None,
                         "wall_timeout_s": cfg.get("timeout_s"), "max_heartbeats": 400000, "lease_s": cfg.get("lease_s")},
        "metrics": {k: metrics.get(k) for k in METRIC_KEYS},
        "status": status,
        "logs": {n: os.path.relpath(os.path.join(run_dir, n), ROOT)
                 for n in ("raw_results.csv", "events.jsonl", "memory.csv", "metrics.json", "config.json")},
    }
    if notes:
        rec["notes"] = notes
    with open(os.path.join(run_dir, "run_record.json"), "w", encoding="utf-8") as f:
        json.dump(rec, f, indent=1, ensure_ascii=False)
    return rec
