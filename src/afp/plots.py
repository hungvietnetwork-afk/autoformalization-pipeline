"""Static figures (PNG) for the report/slides. Palette & mark specs follow a validated categorical
palette (slots in fixed order), 2px lines, >=8px markers with a surface ring, hairline solid grid,
thin bars, a legend whenever there are >= 2 series, no dual axes.

  python -m afp.plots
"""
from __future__ import annotations

import csv
import json
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from .paths import AUDIT, CANDIDATES_DB, RAW, ROOT, RUNS, TABLES, TIERS_DIR, UNITS, result_path, run_dir
RES = TABLES
FIG = TABLES
SURFACE, INK, INK2, MUTED, GRID, AXIS = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
STATUS_COLORS = {"COMPILE_OK": "#2a78d6", "PARSE_ERROR": "#eb6834", "UNKNOWN_IDENTIFIER": "#1baf7a",
                 "TYPE_MISMATCH": "#eda100", "OTHER_ERROR": "#e87ba4", "TIMEOUT": "#6250d6", "EMPTY_OUTPUT": "#898781"}


def _style():
    plt.rcParams.update({
        "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
        "axes.edgecolor": AXIS, "axes.linewidth": 0.8, "axes.labelcolor": INK2, "text.color": INK,
        "xtick.color": MUTED, "ytick.color": MUTED, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8,
        "grid.linestyle": "-", "axes.spines.top": False, "axes.spines.right": False, "font.size": 10,
        "axes.titlesize": 11, "axes.titleweight": "semibold", "legend.frameon": False, "lines.linewidth": 2,
        "font.family": "DejaVu Sans",
    })


def _read(path):
    with open(path) as f:
        return list(csv.DictReader(f))


def _f(x):
    return float(x) if x not in (None, "", "None") else float("nan")


def fig_matrix():
    rows = _read(os.path.join(RES, "matrix_median.csv"))
    tiers, cfgs = ["T100", "T1K", "T10K"], ["A", "B", "C"]
    label = {"A": "A: 1 worker, batch 1", "B": "B: 2 workers, batch 8", "C": "C: 4 workers, batch 32"}
    for metric, ylab, fname in [("throughput_problems_per_s", "Bài toán / giây (median 3 lần)", "matrix_throughput.png"),
                                ("latency_ms_p95", "P95 latency kiểm chứng (ms)", "matrix_p95.png"),
                                ("peak_pool_mb", "Peak RAM của pool Lean (MB)", "matrix_peak_ram.png")]:
        fig, ax = plt.subplots(figsize=(6.4, 3.6))
        width = 0.22
        for i, c in enumerate(cfgs):
            vals, lo, hi = [], [], []
            for t in tiers:
                r = next((r for r in rows if r["tier"] == t and r["config"] == c), None)
                v = _f(r[metric]) if r else float("nan")
                vals.append(v)
                lo.append(v - _f(r.get(metric + "_min", v)) if r and r.get(metric + "_min") else 0)
                hi.append(_f(r.get(metric + "_max", v)) - v if r and r.get(metric + "_max") else 0)
            xs = [j + (i - 1) * (width + 0.03) for j in range(len(tiers))]
            ax.bar(xs, vals, width=width, color=SERIES[i], label=label[c], yerr=[lo, hi] if any(lo + hi) else None,
                   error_kw={"ecolor": INK2, "elinewidth": 1, "capsize": 2})
        ax.set_xticks(range(len(tiers)), ["100 bài", "1.000 bài", "10.000 bài (replay)"])
        ax.set_ylabel(ylab)
        ax.grid(axis="x", visible=False)
        ax.legend(loc="upper left", fontsize=8.5)
        fig.tight_layout()
        fig.savefig(os.path.join(FIG, fname), dpi=180)
        plt.close(fig)


def fig_scaling():
    rows = sorted(_read(os.path.join(RES, "scaling_median.csv")), key=lambda r: int(r["workers"]))
    w = [int(r["workers"]) for r in rows]
    steady = [_f(r["steady_throughput_candidates_per_s"]) for r in rows]
    e2e = [_f(r["throughput_candidates_per_s"]) for r in rows]
    fig, ax = plt.subplots(figsize=(6.4, 3.8))
    ideal = [steady[0] * x for x in w]
    ax.plot(w, ideal, color=MUTED, linewidth=1, label="Lý tưởng (tuyến tính)")
    ax.plot(w, steady, color=SERIES[0], marker="o", markersize=8, markeredgecolor=SURFACE, markeredgewidth=2,
            label="Ổn định (không tính khởi động REPL)")
    ax.plot(w, e2e, color=SERIES[1], marker="o", markersize=8, markeredgecolor=SURFACE, markeredgewidth=2,
            label="End-to-end (gồm khởi động)")
    top = max(steady + e2e) * 1.35
    ax.set_ylim(0, top)                       # the ideal line leaves the plot: the data, not the ideal, sets the scale
    ax.axvline(2, color=AXIS, linewidth=1)
    ax.text(2.08, top * 0.06, "2 vCPU", color=INK2, fontsize=8.5)
    ax.set_xscale("log", base=2)
    ax.set_xticks(w, [str(x) for x in w])
    ax.set_xlabel("Số Lean worker")
    ax.set_ylabel("Ứng viên kiểm chứng / giây")
    ax.legend(loc="upper right", fontsize=8.5)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "scaling_workers.png"), dpi=180)
    plt.close(fig)
    # memory: shared .olean pages vs private heap vs (misleading) RSS sum
    fig, ax = plt.subplots(figsize=(6.4, 3.6))
    anon = [_f(r["peak_pool_anon_mb"]) / 1024 for r in rows]
    pool = [_f(r["peak_pool_mb"]) / 1024 for r in rows]
    rss = [_f(r["peak_rss_sum_mb"]) / 1024 for r in rows]
    ax.plot(w, rss, color=SERIES[1], marker="o", markersize=8, markeredgecolor=SURFACE, markeredgewidth=2,
            label="Tổng RSS (đếm trùng trang dùng chung)")
    ax.plot(w, pool, color=SERIES[0], marker="o", markersize=8, markeredgecolor=SURFACE, markeredgewidth=2,
            label="Footprint thực = trang .olean chung + heap riêng")
    ax.plot(w, anon, color=SERIES[2], marker="o", markersize=8, markeredgecolor=SURFACE, markeredgewidth=2,
            label="Chỉ heap riêng (RssAnon)")
    ax.axhline(7.84, color=AXIS, linewidth=1)
    ax.text(w[0], 8.1, "RAM máy ≈ 7,8 GB", color=INK2, fontsize=8.5)
    ax.set_xscale("log", base=2)
    ax.set_xticks(w, [str(x) for x in w])
    ax.set_xlabel("Số Lean worker")
    ax.set_ylabel("GB")
    ax.legend(loc="upper left", fontsize=8.5)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "scaling_memory.png"), dpi=180)
    plt.close(fig)


def fig_taxonomy(run_name: str):
    tx = json.load(open(os.path.join(RES, f"taxonomy_{run_name}.json")))
    order = ["COMPILE_OK", "PARSE_ERROR", "UNKNOWN_IDENTIFIER", "TYPE_MISMATCH", "OTHER_ERROR", "TIMEOUT", "EMPTY_OUTPUT"]
    srcs = [s for s in ["proofnet", "minif2f", "math", "gsm8k"] if s in tx["by_source"]]
    fig, ax = plt.subplots(figsize=(6.8, 3.4))
    left = [0.0] * len(srcs)
    for st in order:
        vals = []
        for s in srcs:
            d = tx["by_source"][s]
            vals.append(100.0 * d.get(st, 0) / max(1, sum(d.values())))
        if not any(vals):
            continue
        ax.barh(srcs, vals, left=left, height=0.5, color=STATUS_COLORS[st], label=st, edgecolor=SURFACE, linewidth=2)
        left = [a + b for a, b in zip(left, vals)]
    ax.set_xlim(0, 100)
    ax.set_xlabel("% ứng viên")
    ax.invert_yaxis()
    ax.grid(axis="y", visible=False)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.22), ncol=4, fontsize=8)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "error_taxonomy.png"), dpi=180)
    plt.close(fig)


def fig_failure_causes(run_name: str):
    fc = json.load(open(os.path.join(RES, f"failure_causes_{run_name}.json")))
    label = {"sanitizer_let_cut": "Sanitizer v1 cắt nhầm let … :=", "types_coercions_instances": "Kiểu, coercion, instance",
             "lean4_syntax": "Cú pháp Lean 4", "missing_namespace_or_notation": "Thiếu namespace / notation",
             "timeout": "Quá hạn 10 s", "header_notation": "Header mở Nat (φ)", "empty_output": "Không có khai báo",
             "other": "Khác"}
    owner = {"pipeline": "Pipeline của nhóm", "model": "Model", "environment": "Môi trường Lean", "resource": "Giới hạn tài nguyên"}
    order = [o for o in ("pipeline", "model", "environment", "resource") if any(c["owner"] == o for c in fc["causes"])]
    causes = fc["causes"][::-1]
    fig, ax = plt.subplots(figsize=(6.8, 0.42 * len(causes) + 1.2))
    for c in causes:
        ax.barh(label[c["cause"]], c["n"], height=0.55, color=SERIES[order.index(c["owner"])], edgecolor=SURFACE, linewidth=2)
        ax.annotate(str(c["n"]), (c["n"], label[c["cause"]]), textcoords="offset points", xytext=(6, -3), fontsize=9)
    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(color=SERIES[i], label=owner[o]) for i, o in enumerate(order)], loc="lower right", fontsize=8)
    ax.set_xlabel(f"Số ứng viên không compile ({fc['n_failed']} / {fc['n']})")
    ax.grid(axis="y", visible=False)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, f"failure_causes_{run_name}.png"), dpi=180)
    plt.close(fig)


def fig_passk():
    rows = _read(os.path.join(RES, "passk_vs_cost.csv"))
    fig, ax = plt.subplots(figsize=(6.0, 3.6))
    for i, setting in enumerate(["zero-shot", "few-shot"]):
        rs = [r for r in rows if r["setting"] == setting]
        x = [_f(r["tokens_per_problem"]) for r in rs]
        y = [100 * _f(r["pass_at_k"]) for r in rs]
        ax.plot(x, y, color=SERIES[i], marker="o", markersize=8, markeredgecolor=SURFACE, markeredgewidth=2,
                label=setting)
        for r, xx, yy in zip(rs, x, y):
            ax.annotate(f"k={r['k']}", (xx, yy), textcoords="offset points", xytext=(6, -12), fontsize=8, color=INK2)
    ax.set_xlabel("Token ước tính / bài (prompt + output, k mẫu)")
    ax.set_ylabel("Pass@k (%) - compile")
    ax.legend(loc="lower right", fontsize=8.5)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "passk_vs_tokens.png"), dpi=180)
    plt.close(fig)


def fig_latency(run_dir: str):
    import numpy as np
    rows = [json.loads(l) for l in open(os.path.join(run_dir, "raw_results.jsonl"))]
    lat = np.sort([r["latency_ms"] for r in rows if r["latency_ms"] > 0])
    fig, ax = plt.subplots(figsize=(6.0, 3.4))
    ax.plot(lat, np.arange(1, len(lat) + 1) / len(lat) * 100, color=SERIES[0])
    for q in (50, 95, 99):
        v = float(np.percentile(lat, q))
        ax.plot([v], [q], marker="o", markersize=8, color=SERIES[0], markeredgecolor=SURFACE, markeredgewidth=2)
        ax.annotate(f"P{q} = {v:.0f} ms", (v, q), textcoords="offset points", xytext=(8, -4), fontsize=8, color=INK2)
    ax.set_xscale("log")
    ax.set_xlabel("Thời gian kiểm chứng một ứng viên (ms, log)")
    ax.set_ylabel("% ứng viên (CDF)")
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "latency_cdf.png"), dpi=180)
    plt.close(fig)


def fig_inference_batching():
    """Problems per LLM request vs tokens per problem and failed requests (two panels, one measure each)."""
    d = json.load(open(os.path.join(RES, "inference_batching.json")))["by_problems_per_request"]
    cls = [c for c in ("1", "9", "20-26", "100-142") if c in d]
    labels = [c.replace("-", "–") for c in cls]
    tok = [d[c]["zeroshot_tokens_per_problem"] for c in cls]
    fail = [100 * d[c].get("request_failure_share", 0.0) for c in cls]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(7.2, 3.3))
    a1.bar(labels, tok, width=0.55, color=SERIES[0])
    a1.set_yscale("log")
    a1.set_title("Token mỗi bài (zero-shot)")
    for i, v in enumerate(tok):
        a1.text(i, v * 1.12, f"{v:,.0f}".replace(",", "."), ha="center", fontsize=8.5, color=INK)
    a2.bar(labels, fail, width=0.55, color=SERIES[1])
    a2.set_title("Request thất bại hoặc thiếu (%)")
    a2.set_ylim(0, max(fail + [10]) * 1.2)
    for i, v in enumerate(fail):
        a2.text(i, v + 1.5, f"{v:.1f}".replace(".", ",").replace(",0", ""), ha="center", fontsize=8.5, color=INK)
    for a in (a1, a2):
        a.set_xlabel("Số bài trong một request")
        a.grid(axis="x", visible=False)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "inference_batching.png"), dpi=180)
    plt.close(fig)


def fig_batch_sweep():
    """End-to-end throughput by verification batch size at 2 workers, one panel per tier (median, min-max)."""
    rows = _read(os.path.join(RES, "batch_median.csv"))
    tiers = [t for t in ("T100", "T1K", "T10K") if any(r["tier"] == t for r in rows)]
    cfgs = [("b1", "lô 1"), ("b1_idx", "lô 1 + index"), ("b8", "lô 8"), ("b32", "lô 32")]
    tl = {"T100": "100 bài", "T1K": "1.000 bài", "T10K": "10.000 bài (replay)"}
    fig, axes = plt.subplots(1, len(tiers), figsize=(7.6, 3.2), squeeze=False)
    for ax, t in zip(axes[0], tiers):
        for i, (c, lab) in enumerate(cfgs):
            r = next((r for r in rows if r["tier"] == t and r["config"] == c), None)
            if not r:
                continue
            v = _f(r["throughput_problems_per_s"])
            lo = v - _f(r.get("throughput_problems_per_s_min") or v)
            hi = _f(r.get("throughput_problems_per_s_max") or v) - v
            ax.bar(i, v, width=0.6, color=SERIES[i], label=lab, yerr=[[lo], [hi]],
                   error_kw={"ecolor": INK2, "elinewidth": 1, "capsize": 2})
            ax.text(i, v + hi + 0.02 * max(1.0, v), f"{v:.1f}".replace(".", ","), ha="center", fontsize=8, color=INK)
        ax.set_title(tl[t])
        ax.set_xticks([])
        ax.grid(axis="x", visible=False)
    axes[0][0].set_ylabel("Bài / giây (median 3 lần)")
    h, l = axes[0][0].get_legend_handles_labels()
    fig.legend(h, l, loc="lower center", ncol=4, fontsize=8.5)
    fig.tight_layout(rect=(0, 0.1, 1, 1))
    fig.savefig(os.path.join(FIG, "batch_sweep.png"), dpi=180)
    plt.close(fig)


def main():
    import sys
    _style()
    os.makedirs(FIG, exist_ok=True)
    todo = sys.argv[1:] or ["matrix", "scaling", "taxonomy", "causes", "passk", "latency", "inference", "batch"]
    if "matrix" in todo and os.path.exists(os.path.join(RES, "matrix_median.csv")):
        fig_matrix()
    if "scaling" in todo and os.path.exists(os.path.join(RES, "scaling_median.csv")):
        fig_scaling()
    if "taxonomy" in todo and os.path.exists(os.path.join(RES, "taxonomy_q_T1K_zeroshot.json")):
        fig_taxonomy("q_T1K_zeroshot")
    for rn in ("q_T1K_zeroshot_sanitizer_v1", "q_T1K_zeroshot"):
        if "causes" in todo and os.path.exists(os.path.join(RES, f"failure_causes_{rn}.json")):
            fig_failure_causes(rn)
    if "passk" in todo and os.path.exists(os.path.join(RES, "passk_vs_cost.csv")):
        fig_passk()
    if "latency" in todo and os.path.exists(os.path.join(RUNS, "q_T1K_zeroshot/raw_results.jsonl")):
        fig_latency(os.path.join(RUNS, "q_T1K_zeroshot"))
    if "inference" in todo and os.path.exists(os.path.join(RES, "inference_batching.json")):
        fig_inference_batching()
    if "batch" in todo and os.path.exists(os.path.join(RES, "batch_median.csv")):
        fig_batch_sweep()
    print("figures in", FIG, sorted(os.listdir(FIG)))


if __name__ == "__main__":
    main()
