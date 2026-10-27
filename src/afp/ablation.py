"""One table of every on/off comparison in the project (guide: ablation and error analysis).

Every number is read from a raw or summary file under results/; nothing is typed by hand. A component whose
experiment has not been run yet is listed with `None` values instead of being left out.

    python -m afp.ablation          (also run by `python -m afp.study all`)

Writes results/figures/ablation.json and results/figures/ablation.md (Vietnamese, for the report).
"""
from __future__ import annotations

import csv
import json
import os
import statistics

from .paths import RAW, RUNS, TABLES, TIERS_DIR
from .schema import COMPILE_OK

FLAGS_LEAN = {"VACUOUS", "FALSE", "TRIVIAL"}
FLAGS_HEUR = {"ANSWER_MISSING", "ARITHMETIC_ONLY"}
CONFIRMED = {"EQUIV_GOLD", "PROVED_CONSISTENT"}


# ----------------------------------------------------------------------------------------------- readers
def _json(path: str):
    return json.load(open(path, encoding="utf-8")) if os.path.exists(path) else None


def _csv(path: str) -> list[dict]:
    if not os.path.exists(path):
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _row(rows: list[dict], **where) -> dict | None:
    for r in rows:
        if all(str(r.get(k)) == str(v) for k, v in where.items()):
            return r
    return None


def _runs(run: str):
    p = os.path.join(RUNS, run, "raw_results.csv")
    return _csv(p)


def _semantic(run: str) -> dict:
    p = os.path.join(RUNS, run, "semantic.jsonl")
    if not os.path.exists(p):
        return {}
    return {d["task_hash"]: d for d in map(json.loads, open(p, encoding="utf-8"))}


def _tier(name: str) -> set[str]:
    p = os.path.join(TIERS_DIR, f"{name}.txt")
    return {l.strip() for l in open(p) if l.strip()} if os.path.exists(p) else set()


def _quality(run: str, problems: set[str] | None = None, candidate_index: int | None = None) -> dict | None:
    rows = _runs(run)
    if not rows:
        return None
    if problems is not None:
        rows = [r for r in rows if r["problem_id"] in problems]
    if candidate_index is not None:
        rows = [r for r in rows if int(r["candidate_index"]) == candidate_index]
    sem = _semantic(run)
    comp = [r for r in rows if r["status"] == COMPILE_OK]
    verdict = [(sem.get(r["task_hash"]) or {}).get("verdict") or "" for r in comp]
    return {"candidates": len(rows), "compile_rate": round(len(comp) / len(rows), 4) if rows else None,
            "flagged_share_of_compiled": round(sum(v in FLAGS_LEAN | FLAGS_HEUR for v in verdict) / len(comp), 4)
            if sem and comp else None,
            "lean_confirmed_share_of_compiled": round(sum(v in CONFIRMED for v in verdict) / len(comp), 4)
            if sem and comp else None}


# ----------------------------------------------------------------------------------------------- components
def _warm_repl() -> dict:
    d = _json(os.path.join(RAW, "cold_vs_warm.json")) or {}
    return {"component": "REPL nóng (import Mathlib một lần mỗi worker)",
            "setting": "kiểm một ứng viên, Mathlib v4.35.0",
            "metric": "thời gian kiểm một ứng viên",
            "on": {"warm_check_ms_mean": d.get("warm_check_ms_mean")},
            "off": {"cold_check_s_median": d.get("cold_check_s_median")},
            "effect": {"speedup": d.get("speedup_median_cold_over_mean_warm"),
                       "cpu_10k_warm_min": d.get("cpu_time_10k_warm_min"), "cpu_10k_cold_h": d.get("cpu_time_10k_cold_h")},
            "source": "results/raw/cold_vs_warm.json"}


def _heartbeat_primary() -> dict:
    sc = _row(_csv(os.path.join(TABLES, "scaling_median.csv")), tier="T10K", workers="2")
    mx = _row(_csv(os.path.join(TABLES, "matrix_median.csv")), tier="T10K", config="B")
    return {"component": "Heartbeat là giới hạn chính (wall timeout 30 s thay vì 10 s)",
            "setting": "10.000 task, 2 worker, lô 8",
            "metric": "throughput ổn định (ứng viên/s); số timeout",
            "on": {"steady_throughput_candidates_per_s": _num(sc and sc["steady_throughput_candidates_per_s"]),
                   "repl_timeouts": _num(sc and sc["repl_timeouts"])},
            "off": {"steady_throughput_candidates_per_s": _num(mx and mx["steady_throughput_candidates_per_s"]),
                    "repl_timeouts": _num(mx and mx["repl_timeouts"])},
            "source": "results/figures/scaling_median.csv (sc_T10K_w2), results/figures/matrix_median.csv (mx_T10K_B)"}


def _release() -> dict:
    d = _json(os.path.join(TABLES, "release_ablation.json")) or {}

    def pick(side):
        s = d.get(side) or {}
        return {k: (s.get(k) or {}).get("median") for k in ("steady_window_s", "makespan_s", "repl_timeouts",
                                                             "retried_tasks", "duplicate_result_rows")} | \
               {"runs": s.get("runs")}
    return {"component": "Trả lại phần còn lại của lô trước khi khởi động lại REPL (release)",
            "setting": "1.000 task, 2 worker, lô 8, timeout 10 s, 3 lần mỗi bên",
            "metric": "thời gian ổn định (s, median); số timeout",
            "on": pick("release_on"), "off": pick("release_off"),
            "source": "results/raw/release_runs.csv, results/figures/release_ablation.json"}


def _queue_index() -> dict:
    bench = _json(os.path.join(RAW, "bench_queue.json")) or []
    b = {(r["depth"], r["indexed"], r["batch"]): r for r in bench}
    bm = _csv(os.path.join(TABLES, "batch_median.csv"))
    e2e = {}
    for tier in ("T100", "T1K", "T10K"):
        on, off = _row(bm, tier=tier, config="b1_idx"), _row(bm, tier=tier, config="b1")
        if on and off:
            e2e[tier] = {"indexed": _num(on["throughput_problems_per_s"]), "plain": _num(off["throughput_problems_per_s"])}
    return {"component": "Index phủ cho hàng đợi (chế độ indexed)",
            "setting": "lease 1 task khi hàng đợi còn 100.000 task; đầu cuối: lô 1, 2 worker, timeout 30 s",
            "metric": "ms mỗi lần lease; throughput đầu cuối (bài/s)",
            "on": {"ms_per_lease_100k": (b.get((100000, True, 1)) or {}).get("ms_per_lease_median"),
                   "end_to_end_problems_per_s": {t: v["indexed"] for t, v in e2e.items()} or None},
            "off": {"ms_per_lease_100k": (b.get((100000, False, 1)) or {}).get("ms_per_lease_median"),
                    "end_to_end_problems_per_s": {t: v["plain"] for t, v in e2e.items()} or None},
            "source": "results/raw/bench_queue.json, results/figures/batch_median.csv (bs_*_b1_idx vs bs_*_b1)"}


def _work_stealing() -> dict:
    d = _json(os.path.join(TABLES, "skew_q_T1K_zeroshot.json")) or {}
    w8 = d.get("w8") or {}
    return {"component": "Work stealing (worker rảnh lấy task của partition khác)",
            "setting": "mô phỏng trên 1.000 latency thật của T1K zero-shot, 8 worker",
            "metric": "makespan mô phỏng (s)",
            "on": {"makespan_s": w8.get("work_stealing_makespan_s"), "ideal_s": w8.get("ideal_s")},
            "off": {"makespan_s": w8.get("static_partition_makespan_s")},
            "effect": {"share_of_time_in_slowest_1pct_tasks": d.get("share_of_time_in_slowest_1pct_tasks")},
            "source": "results/figures/skew_q_T1K_zeroshot.json"}


def _retry_budget() -> dict:
    d = _json(os.path.join(TABLES, "retry_ablation.json")) or {}

    def pick(key):
        s = d.get(key) or {}
        med = {k: round(statistics.median(v), 3) for k, v in s.items() if isinstance(v, list) and v}
        return med | {"runs": s.get("runs")}
    return {"component": "Giao lại task khi lease hết hạn (retry hệ thống, tối đa 3 lần)",
            "setting": "1.000 task, 2 worker, lô 8, giết 1 worker sau 300 kết quả, lease 30 s, 3 lần mỗi bên",
            "metric": "số bài có kết quả; dead-letter; dòng trùng; makespan (s)",
            "on": pick("max_attempts_3"), "off": pick("max_attempts_1"),
            "source": "results/raw/retry_runs.csv, results/figures/retry_ablation.json"}


def _inference_resume() -> dict:
    d = (_json(os.path.join(TABLES, "inference_batching.json")) or {}).get("retry") or {}
    return {"component": "Gửi lại phần thiếu của batch job (retry ở tầng inference)",
            "setting": "1.400 ứng viên dự kiến (1.000 zero-shot + 400 few-shot)",
            "metric": "số ứng viên nhận được",
            "on": {"answered": d.get("answered_with_retry"), "planned": d.get("planned_candidates")},
            "off": {"answered": d.get("answered_by_first_requests"), "share": d.get("share_without_retry")},
            "source": "results/figures/inference_batching.json"}


def _problems_per_request() -> dict:
    d = (_json(os.path.join(TABLES, "inference_batching.json")) or {}).get("by_problems_per_request") or {}

    def pick(c):
        s = d.get(c) or {}
        return {"tokens_per_problem": s.get("zeroshot_tokens_per_problem"),
                "request_failure_share": s.get("request_failure_share", 0.0 if s else None),
                "requests": s.get("requests")}
    return {"component": "Gom nhiều bài vào một request LLM (20–26 bài)",
            "setting": "cùng prompt zero-shot; token tính cả ngữ cảnh cố định khoảng 80K mỗi request",
            "metric": "token mỗi bài; tỷ lệ request thất bại",
            "on": pick("20-26") | {"size": "20-26"}, "off": pick("1") | {"size": "1"},
            "extra": {"9": pick("9"), "100-142": pick("100-142")},
            "source": "results/figures/inference_batching.json"}


def _fewshot() -> dict:
    t100 = _tier("T100")
    few = _quality("q_T100_fewshot", candidate_index=0)
    zero = _quality("q_T1K_zeroshot", problems=t100)
    cost = {r["setting"]: _num(r["tokens_per_problem"]) for r in _csv(os.path.join(TABLES, "passk_vs_cost.csv"))
            if r.get("k") == "1"}
    return {"component": "Few-shot (6 ví dụ) thay cho zero-shot",
            "setting": "100 bài của T100, mẫu đầu tiên của mỗi bài",
            "metric": "compile rate; tỷ lệ bị gắn cờ ngữ nghĩa trong số compile được; token ước tính mỗi bài",
            "on": (few or {}) | {"est_tokens_per_problem": cost.get("few-shot")},
            "off": (zero or {}) | {"est_tokens_per_problem": cost.get("zero-shot")},
            "source": "results/raw/runs/q_T100_fewshot, results/raw/runs/q_T1K_zeroshot (lọc 100 bài T100), "
                      "results/figures/passk_vs_cost.csv"}


def _k_candidates() -> dict:
    d = _json(os.path.join(TABLES, "candidates_retry.json")) or {}
    pk = d.get("pass_at_k") or {}
    pol = d.get("policies") or {}
    return {"component": "4 ứng viên mỗi bài thay cho 1",
            "setting": "few-shot, 100 bài, 4 mẫu mỗi bài",
            "metric": "Pass@k; token ước tính mỗi bài; tỷ lệ bị gắn cờ",
            "on": {"pass_at_k": pk.get("4"), "est_tokens_per_problem": (pol.get("best_of_4") or {}).get("est_tokens_per_problem"),
                   "flagged_share_of_compiled": (pol.get("best_of_4") or {}).get("flagged_share_of_compiled")},
            "off": {"pass_at_k": pk.get("1"), "est_tokens_per_problem": (pol.get("retry_0") or {}).get("est_tokens_per_problem"),
                    "flagged_share_of_compiled": (pol.get("retry_0") or {}).get("flagged_share_of_compiled")},
            "source": "results/figures/candidates_retry.json"}


def _sanitizer() -> dict:
    def pick(run):
        m = _json(os.path.join(RUNS, run, "metrics.json")) or {}
        return {"compile_rate": m.get("compile_rate"), "parse_errors": (m.get("status_counts") or {}).get("PARSE_ERROR", 0)}
    return {"component": "Sanitizer v2 (không cắt `:=` của `let`/`have`)",
            "setting": "1.000 ứng viên zero-shot T1K, cùng output thô",
            "metric": "compile rate; số lỗi cú pháp",
            "on": pick("q_T1K_zeroshot"), "off": pick("q_T1K_zeroshot_sanitizer_v1"),
            "source": "results/raw/runs/q_T1K_zeroshot, results/raw/runs/q_T1K_zeroshot_sanitizer_v1"}


def _semantic_layers() -> dict:
    d = _json(os.path.join(TABLES, "semantic_layers.json")) or {}
    va = (d.get("vs_audit") or {}).get("llm_A") or {}
    return {"component": "Kết hợp hai lớp kiểm tra tự động (Lean + heuristic)",
            "setting": "100 mẫu audit của T1K zero-shot; nhãn tham chiếu: người chấm thử A",
            "metric": "precision / recall khi coi 'không ĐÚNG' là dương tính",
            "on": va.get("both"), "off": {"heuristic_only": va.get("heuristic"), "lean_only": va.get("lean")},
            "source": "results/figures/semantic_layers.json"}


def _gold() -> dict:
    d = _json(os.path.join(TABLES, "mutation_summary.json")) or {}
    kinds = ("ANSWER_CHANGE", "FLIP_REL", "DROP_HYP", "VACUOUS", "TRIVIAL")
    return {"component": "Kiểm tra tương đương với phát biểu gold",
            "setting": "mutation test trên phát biểu gold đã compile: 5 loại lỗi cài sẵn + mẫu đối chứng",
            "metric": "tỷ lệ phát hiện theo loại lỗi; báo động nhầm trên mẫu đối chứng",
            "on": {k: (d.get(k) or {}).get("flagged_any_rate") for k in kinds}
            | {"false_alarm": (d.get("CONTROL") or {}).get("flagged_any_rate")},
            "off": {k: (d.get(k) or {}).get("strong_flag_rate") for k in kinds}
            | {"false_alarm": (d.get("CONTROL") or {}).get("strong_flag_rate")},
            "source": "results/figures/mutation_summary.json"}


COMPONENTS = [_warm_repl, _heartbeat_primary, _release, _queue_index, _work_stealing, _retry_budget, _inference_resume,
              _problems_per_request, _fewshot, _k_candidates, _sanitizer, _semantic_layers, _gold]


# ----------------------------------------------------------------------------------------------- markdown
def vn(x, nd: int = 1, pct: bool = False) -> str:
    """Vietnamese number format: 1.234,5 ; None -> '–'."""
    if x is None:
        return "–"
    x = float(x) * (100 if pct else 1)
    s = f"{x:,.{nd}f}".replace(",", "_").replace(".", ",").replace("_", ".")
    if nd and "," in s:
        s = s.rstrip("0").rstrip(",")
    return s + (" %" if pct else "")


def _md_cells(r: dict) -> tuple[str, str]:
    c, on, off = r["component"], r["on"] or {}, r["off"] or {}
    if c.startswith("REPL"):
        return f"{vn(on.get('warm_check_ms_mean'))} ms", f"{vn(off.get('cold_check_s_median'))} s (nhanh hơn {vn((r.get('effect') or {}).get('speedup'), 0)} lần)"
    if c.startswith("Heartbeat"):
        return (f"{vn(on.get('steady_throughput_candidates_per_s'))} ứng viên/s, {vn(on.get('repl_timeouts'), 0)} timeout",
                f"{vn(off.get('steady_throughput_candidates_per_s'))} ứng viên/s, {vn(off.get('repl_timeouts'), 0)} timeout")
    if c.startswith("Trả lại"):
        return (f"{vn(on.get('steady_window_s'))} s, {vn(on.get('repl_timeouts'), 0)} timeout",
                f"{vn(off.get('steady_window_s'))} s, {vn(off.get('repl_timeouts'), 0)} timeout")
    if c.startswith("Index"):
        e_on, e_off = on.get("end_to_end_problems_per_s") or {}, off.get("end_to_end_problems_per_s") or {}
        t = "T10K" if "T10K" in e_on else (next(iter(e_on), None))
        tail_on = f"; {t}: {vn(e_on[t])} bài/s" if t else ""
        tail_off = f"; {t}: {vn(e_off[t])} bài/s" if t else ""
        return (f"{vn(on.get('ms_per_lease_100k'), 2)} ms/lease{tail_on}", f"{vn(off.get('ms_per_lease_100k'), 1)} ms/lease{tail_off}")
    if c.startswith("Work stealing"):
        return (f"{vn(on.get('makespan_s'))} s (lý tưởng {vn(on.get('ideal_s'))} s)", f"chia tĩnh: {vn(off.get('makespan_s'))} s")
    if c.startswith("Giao lại"):
        return (f"{vn(on.get('results'), 0)}/1.000 bài, {vn(on.get('dead_letter'), 0)} dead-letter, {vn(on.get('duplicate_result_rows'), 0)} dòng trùng, {vn(on.get('makespan_s'))} s",
                f"{vn(off.get('results'), 0)}/1.000 bài, {vn(off.get('dead_letter'), 0)} dead-letter, {vn(off.get('makespan_s'))} s")
    if c.startswith("Gửi lại"):
        return (f"{vn(on.get('answered'), 0)}/{vn(on.get('planned'), 0)}", f"{vn(off.get('answered'), 0)} ({vn(off.get('share'), 0, pct=True)})")
    if c.startswith("Gom"):
        return (f"{vn(on.get('tokens_per_problem'), 0)} token/bài, {vn(on.get('request_failure_share'), 1, pct=True)} request lỗi",
                f"{vn(off.get('tokens_per_problem'), 0)} token/bài, {vn(off.get('request_failure_share'), 0, pct=True)} request lỗi")
    if c.startswith("Few-shot"):
        return (f"compile {vn(on.get('compile_rate'), 1, pct=True)}, cờ {vn(on.get('flagged_share_of_compiled'), 1, pct=True)}, {vn(on.get('est_tokens_per_problem'), 0)} token",
                f"compile {vn(off.get('compile_rate'), 1, pct=True)}, cờ {vn(off.get('flagged_share_of_compiled'), 1, pct=True)}, {vn(off.get('est_tokens_per_problem'), 0)} token")
    if c.startswith("4 ứng viên"):
        return (f"Pass@4 {vn(on.get('pass_at_k'), 3)}, {vn(on.get('est_tokens_per_problem'), 0)} token, cờ {vn(on.get('flagged_share_of_compiled'), 0, pct=True)}",
                f"Pass@1 {vn(off.get('pass_at_k'), 4)}, {vn(off.get('est_tokens_per_problem'), 0)} token, cờ {vn(off.get('flagged_share_of_compiled'), 0, pct=True)}")
    if c.startswith("Sanitizer"):
        return (f"compile {vn(on.get('compile_rate'), 1, pct=True)}, {vn(on.get('parse_errors'), 0)} lỗi cú pháp",
                f"compile {vn(off.get('compile_rate'), 1, pct=True)}, {vn(off.get('parse_errors'), 0)} lỗi cú pháp")
    if c.startswith("Kết hợp"):
        h, l = off.get("heuristic_only") or {}, off.get("lean_only") or {}
        return (f"P {vn(on.get('precision'), 2)}, R {vn(on.get('recall'), 2)}",
                f"chỉ heuristic: P {vn(h.get('precision'), 2)}, R {vn(h.get('recall'), 2)}; chỉ Lean: P {vn(l.get('precision'), 2)}, R {vn(l.get('recall'), 2)}")
    if c.startswith("Kiểm tra tương đương"):
        return (f"bắt 100 % mỗi loại lỗi cài sẵn; báo động nhầm {vn(on.get('false_alarm'), 0, pct=True)}"
                if all((on.get(k) or 0) >= 1.0 for k in ("ANSWER_CHANGE", "FLIP_REL", "DROP_HYP", "VACUOUS", "TRIVIAL"))
                else ", ".join(f"{k} {vn(v, 0, pct=True)}" for k, v in on.items()),
                f"đáp án sai {vn(off.get('ANSWER_CHANGE'), 0, pct=True)}, đảo quan hệ {vn(off.get('FLIP_REL'), 0, pct=True)}, "
                f"bỏ giả thiết {vn(off.get('DROP_HYP'), 0, pct=True)}, giả thiết mâu thuẫn {vn(off.get('VACUOUS'), 0, pct=True)}, "
                f"tầm thường {vn(off.get('TRIVIAL'), 0, pct=True)}")
    return json.dumps(on, ensure_ascii=False), json.dumps(off, ensure_ascii=False)


def to_markdown(rows: list[dict]) -> str:
    out = ["| Thành phần | Thiết lập | Có | Không có | Nguồn |", "| --- | --- | --- | --- | --- |"]
    for r in rows:
        on, off = _md_cells(r)
        src = r["source"].split(",")[0].strip()
        out.append(f"| {r['component']} | {r['setting']} | {on} | {off} | `{src}` |")
    return "\n".join(out) + "\n"


def build() -> list[dict]:
    rows = [f() for f in COMPONENTS]
    os.makedirs(TABLES, exist_ok=True)
    with open(os.path.join(TABLES, "ablation.json"), "w", encoding="utf-8") as f:
        json.dump(rows, f, indent=1, ensure_ascii=False)
    with open(os.path.join(TABLES, "ablation.md"), "w", encoding="utf-8") as f:
        f.write(to_markdown(rows))
    return rows


if __name__ == "__main__":
    for r in build():
        print(r["component"], "|", *_md_cells(r), sep=" ")
