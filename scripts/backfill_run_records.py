"""Write run_record.json (guide, Appendix B) for runs made before run records existed (16/10/2026).

Every field comes from the run's own files (config.json, metrics.json, events.jsonl) except the ones the run did
not record; those are filled with what is known and listed in `backfilled_fields`.

  python scripts/backfill_run_records.py          # only runs without a record
"""
from __future__ import annotations

import glob
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
from afp import runrecord  # noqa: E402
from afp.paths import RUNS  # noqa: E402

SNAPSHOT = "c031d89"


def main() -> None:
    sw = runrecord.software()
    done = 0
    for d in sorted(glob.glob(os.path.join(RUNS, "*"))):
        if os.path.exists(os.path.join(d, "run_record.json")) or not os.path.exists(os.path.join(d, "metrics.json")):
            continue
        cfg = json.load(open(os.path.join(d, "config.json")))
        m = json.load(open(os.path.join(d, "metrics.json")))
        ev = [json.loads(line) for line in open(os.path.join(d, "events.jsonl"), encoding="utf-8")]
        t0 = min((e["ts"] for e in ev), default=os.path.getmtime(os.path.join(d, "metrics.json")))
        ends = [json.loads(e["detail"]) for e in ev if e["kind"] == "run_end"]
        exitcodes = (ends[0].get("exitcodes") if ends else {}) or {}
        complete = m.get("n_problems_with_result") == m.get("n_problems") and not m.get("dead_letter")
        status = "ok" if complete and all(c == 0 for c in exitcodes.values()) else \
            ("ok_with_worker_failures" if complete else "incomplete")
        rec = {
            "run_id": cfg["run_id"],
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S+0000", time.gmtime(t0)),
            "git_commit": {"commit": None, "code_dirty": None,
                           "note": f"run of 16/10/2026, before the repository used Git; closest code: commit {SNAPSHOT} "
                                   "(changes of that day: docs/CHANGELOG.md)"},
            "data_version": {"tier": cfg["tier"], "tier_file": f"data/tiers/{cfg['tier']}.txt",
                             "tier_sha256": runrecord.sha256_file(os.path.join(ROOT, "data/tiers", f"{cfg['tier']}.txt")),
                             "replicas": cfg.get("replicas", 1), "candidates_db_sha256": None,
                             "note": "candidates are keyed by TaskHash and were not changed since; the store gained "
                                     "20 v1_zeroshot_1req candidates on 26/10, so its file hash differs"},
            "machine": {"cpu": None, "vcpus": 2, "ram_gb": 7.8, "swap_gb": None, "gpu": None,
                        "os": "Linux (cloud VM, Ubuntu)", "note": "same machine for every run of 16/10"},
            "software": {**sw, "packages": None},
            "parameters": {k: v for k, v in cfg.items() if k not in ("db",)},
            "seed_timeout": {"tier_seed": runrecord.TIER_SEED, "llm_sampling_seed": None,
                             "wall_timeout_s": cfg.get("timeout_s"), "max_heartbeats": 400000, "lease_s": cfg.get("lease_s")},
            "metrics": {k: m.get(k) for k in runrecord.METRIC_KEYS},
            "status": status,
            "logs": {n: os.path.relpath(os.path.join(d, n), ROOT) for n in
                     ("raw_results.csv", "events.jsonl", "memory.csv", "metrics.json", "config.json")},
            "backfilled": True,
            "backfilled_fields": ["git_commit", "machine", "software", "data_version.candidates_db_sha256"],
        }
        if exitcodes and status != "ok":
            rec["notes"] = f"exit codes {exitcodes}"
        with open(os.path.join(d, "run_record.json"), "w", encoding="utf-8") as f:
            json.dump(rec, f, indent=1, ensure_ascii=False)
        done += 1
    print(f"backfilled {done} run records")


if __name__ == "__main__":
    main()
