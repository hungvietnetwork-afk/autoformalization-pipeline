"""Print the report's tables (markdown) from results/*.csv|json, so every number in the report has one source.

    python scripts/report_tables.py matrix | scaling | fault | determinism | broker
"""
from __future__ import annotations

import csv
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = os.path.join(ROOT, "results", "figures")


def _res(name: str) -> str:
    """results/figures (script-generated tables) first, then results/raw (raw measurements)."""
    for d in ("figures", "raw"):
        p = os.path.join(ROOT, "results", d, name)
        if os.path.exists(p):
            return p
    return _res(name)
TIER = {"T100": "100 bài", "T1K": "1.000 bài", "T10K": "10.000 bài (replay)"}
CFG = {"A": "A · 1 worker, batch 1", "B": "B · 2 worker, batch 8", "C": "C · 4 worker, batch 32"}


def _read(name):
    with open(_res(name)) as f:
        return list(csv.DictReader(f))


def vn(x: float, d: int = 1) -> str:
    """Vietnamese number format: 1.234,5"""
    s = f"{x:,.{d}f}"
    return s.replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def matrix() -> str:
    med = {(r["tier"], r["config"]): r for r in _read("matrix_median.csv")}
    runs = _read("matrix_runs.csv")
    out = ["| Mức dữ liệu | Cấu hình | Throughput (bài/s) | P95 (ms) | Khởi động REPL (s) | RAM pool (GB) | ΣRSS (GB) | Compile rate | Timeout + restart |",
           "|---|---|---|---|---|---|---|---|---|"]
    for t in TIER:
        for c in CFG:
            r = med.get((t, c))
            if not r:
                continue
            to = [int(float(x["repl_timeouts"])) for x in runs if x["tier"] == t and x["config"] == c]
            out.append(f"| {TIER[t]} | {CFG[c]} | {vn(float(r['throughput_problems_per_s']), 2)} "
                       f"({vn(float(r['throughput_problems_per_s_min']), 2)}–{vn(float(r['throughput_problems_per_s_max']), 2)}) "
                       f"| {vn(float(r['latency_ms_p95']), 0)} | {vn(float(r['startup_s_mean']), 0)} "
                       f"| {vn(float(r['peak_pool_mb']) / 1024, 1)} | {vn(float(r['peak_rss_sum_mb']) / 1024, 1)} "
                       f"| {vn(100 * float(r['compile_rate']), 1)} % | {'/'.join(map(str, to))} |")
    return "\n".join(out)


def scaling() -> str:
    med = sorted(_read("scaling_median.csv"), key=lambda r: int(r["workers"]))
    base = float(med[0]["steady_throughput_candidates_per_s"])
    out = ["| Lean worker | Ổn định (ứng viên/s) | Tăng tốc so với 1 worker | End-to-end (ứng viên/s) | Makespan (s) | P95 (ms) | Lean bận | RAM pool (GB) | ΣRSS (GB) |",
           "|---|---|---|---|---|---|---|---|---|"]
    for r in med:
        s = float(r["steady_throughput_candidates_per_s"])
        out.append(f"| {r['workers']} | {vn(s, 1)} | {vn(s / base, 2)}× | {vn(float(r['throughput_candidates_per_s']), 1)} "
                   f"| {vn(float(r['makespan_s']), 0)} | {vn(float(r['latency_ms_p95']), 0)} "
                   f"| {vn(100 * float(r['lean_busy_fraction']), 0)} % | {vn(float(r['peak_pool_mb']) / 1024, 1)} "
                   f"| {vn(float(r['peak_rss_sum_mb']) / 1024, 1)} |")
    return "\n".join(out)


def _json(name):
    return json.dumps(json.load(open(_res(name))), indent=1, ensure_ascii=False)


if __name__ == "__main__":
    what = sys.argv[1]
    print({"matrix": matrix, "scaling": scaling}[what]() if what in ("matrix", "scaling")
          else _json({"fault": "fault_tolerance.json", "determinism": "determinism.json",
                      "broker": "broker_comparison.json"}[what]))
