"""Post-hoc analysis: error taxonomy, Pass@k vs token cost, curated corpus export.

  python -m afp.analysis taxonomy --run runs/q_T1K_zeroshot
  python -m afp.analysis passk    --zero runs/q_T1K_zeroshot --few runs/q_T100_fewshot
  python -m afp.analysis corpus   --runs runs/q_T1K_zeroshot runs/q_T100_fewshot
  python -m afp.analysis causes   --run runs/q_T1K_zeroshot     (root cause of every failed candidate)
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
import os
import re

from .aggregator import curate, pass_at_k
from .inference.batchfile import load_units
from .schema import COMPILE_OK
from .store import CandidateStore, ResultStore

from .paths import AUDIT, CANDIDATES_DB, RAW, ROOT, RUNS, TABLES, TIERS_DIR, UNITS, result_path, run_dir
RES = TABLES


def _rows(run_dir: str) -> list[dict]:
    cfg = json.load(open(os.path.join(run_dir, "config.json")))
    return ResultStore(os.path.join(run_dir, "run.db")).rows(cfg["run_id"])


def taxonomy(run_dir: str) -> dict:
    units = load_units(UNITS)
    rows = _rows(run_dir)
    top = collections.Counter(r["status"] for r in rows)
    first_kind = collections.Counter((r["error_kinds"] or "").split(";")[0] or "none" for r in rows)
    by_src = collections.defaultdict(collections.Counter)
    by_dom = collections.defaultdict(collections.Counter)
    by_diff = collections.defaultdict(collections.Counter)
    unknown_ids = collections.Counter()
    for r in rows:
        u = units[r["problem_id"]]
        by_src[u.source][r["status"]] += 1
        by_dom[f"{u.source}/{u.domain}"][r["status"]] += 1
        by_diff[f"{u.source}/{u.metadata.get('difficulty')}"][r["status"]] += 1
        if r["status"] == "UNKNOWN_IDENTIFIER":
            for m in re.findall(r"Unknown (?:identifier|constant) [`'‘]?([^`'’\s]+)", r["compiler_message"] or ""):
                unknown_ids[m] += 1
    examples = {}
    for st in top:
        ex = [r for r in rows if r["status"] == st][:3]
        examples[st] = [{"problem_id": r["problem_id"], "message": (r["compiler_message"] or "")[:300]} for r in ex]
    rep = {"n": len(rows), "status": dict(top), "first_error_kind": dict(first_kind),
           "by_source": {k: dict(v) for k, v in by_src.items()},
           "by_domain": {k: dict(v) for k, v in sorted(by_dom.items())},
           "by_difficulty": {k: dict(v) for k, v in sorted(by_diff.items())},
           "top_unknown_identifiers": unknown_ids.most_common(25), "examples": examples}
    os.makedirs(RES, exist_ok=True)
    json.dump(rep, open(os.path.join(RES, f"taxonomy_{os.path.basename(run_dir)}.json"), "w"), indent=1, ensure_ascii=False)
    return rep


def passk(zero_dir: str, few_dir: str, tier_file: str = "data/tiers/T100.txt") -> list[dict]:
    """Pass@k on the T100 problems: zero-shot k=1 vs few-shot k=1,2,4 (unbiased estimator)."""
    ids = {l.strip() for l in open(os.path.join(ROOT, tier_file)) if l.strip()}
    cs = CandidateStore(CANDIDATES_DB)
    out = []
    for label, d, ks in (("zero-shot", zero_dir, [1]), ("few-shot", few_dir, [1, 2, 4])):
        rows = [r for r in _rows(d) if r["problem_id"] in ids]
        per = collections.defaultdict(list)
        for r in rows:
            per[r["problem_id"]].append(r)
        tok = collections.defaultdict(list)
        for r in rows:
            c = cs.get(r["task_hash"])
            tok[r["problem_id"]].append((c.prompt_tokens or 0) + (c.completion_tokens or 0))
        per_sample_tokens = sum(sum(v) for v in tok.values()) / max(1, sum(len(v) for v in tok.values()))
        for k in ks:
            vals = [pass_at_k(len(v), sum(1 for x in v if x["status"] == COMPILE_OK), k) for v in per.values()]
            out.append({"setting": label, "k": k, "n_problems": len(per), "pass_at_k": round(sum(vals) / len(per), 4),
                        "tokens_per_problem": round(per_sample_tokens * k, 1)})
    with open(os.path.join(RES, "passk_vs_cost.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
        w.writeheader()
        w.writerows(out)
    return out


FLAGGED = {"VACUOUS", "FALSE", "TRIVIAL", "ANSWER_MISSING", "ARITHMETIC_ONLY"}


def corpus(run_dirs: list[str], out_dir: str = None) -> dict:
    """Curated formalized corpus: best compiled candidate per problem (+ semantic verdict) -> Parquet."""
    import pyarrow as pa
    import pyarrow.dataset as pads
    units = load_units(UNITS)
    cs = CandidateStore(CANDIDATES_DB)
    rows, sem = [], {}
    for d in run_dirs:
        rows += _rows(d)
        sp = os.path.join(d, "semantic.jsonl")
        if os.path.exists(sp):
            for line in open(sp, encoding="utf-8"):
                s = json.loads(line)
                sem[s["task_hash"]] = s
    code_of = {r["task_hash"]: (cs.get(r["task_hash"]).lean_code if cs.get(r["task_hash"]) else "") for r in rows}
    best = curate(rows, code_of, {th: s.get("verdict") for th, s in sem.items()})
    attempted = {r["problem_id"] for r in rows}
    recs = []
    for pid in sorted(attempted):
        u = units[pid]
        b = best.get(pid)
        c = cs.get(b["task_hash"]) if b else None
        recs.append({
            "problem_id": pid, "source": u.source, "domain": u.domain, "difficulty": u.metadata.get("difficulty"),
            "natural_statement": u.natural_statement, "answer": u.metadata.get("answer"),
            "formalized": b is not None, "lean_statement": b["lean_code"] if b else None,
            "prompt_version": b["prompt_version"] if b else None, "model": c.model if c else None,
            "check_latency_ms": round(b["latency_ms"], 2) if b else None,
            "semantic_verdict": sem.get(b["task_hash"], {}).get("verdict") if b else None,
            "semantic_flag": (sem.get(b["task_hash"], {}).get("verdict") in FLAGGED) if b else None,
            "task_hash": b["task_hash"] if b else None,
            "gold_formal_statement": u.metadata.get("gold_formal_statement"),
            "sanitizer": "v2", "lean": "v4.35.0", "mathlib": "v4.35.0",
        })
    out_dir = out_dir or os.path.join(ROOT, "data/lake/formalized")
    pads.write_dataset(pa.Table.from_pylist(recs), out_dir, format="parquet",
                       partitioning=pads.partitioning(pa.schema([("source", pa.string()), ("domain", pa.string())]), flavor="hive"),
                       existing_data_behavior="delete_matching")
    with open(os.path.join(ROOT, "data/formalized_corpus.jsonl"), "w", encoding="utf-8") as f:
        for r in recs:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    summ = {"problems": len(recs), "formalized": sum(r["formalized"] for r in recs),
            "by_source": {s: {"problems": sum(1 for r in recs if r["source"] == s),
                              "formalized": sum(1 for r in recs if r["source"] == s and r["formalized"])}
                          for s in sorted({r["source"] for r in recs})},
            "semantic_verdicts": dict(collections.Counter(r["semantic_verdict"] for r in recs if r["formalized"])),
            "formalized_not_flagged": sum(1 for r in recs if r["formalized"] and not r["semantic_flag"]),
            "selection": "per problem: best semantic verdict, then shortest statement, then fastest check"}
    json.dump(summ, open(os.path.join(RES, "corpus_summary.json"), "w"), indent=1)
    return summ


def skew(run_dir: str, partitions: int = 16, workers=(2, 4, 8)) -> dict:
    """Trace-driven check of data skew: per-partition Lean time, and the makespan of static
    partition->worker assignment versus dynamic work stealing (greedy list scheduling) using the
    measured latency of every task."""
    import heapq
    from .schema import partition_index
    rows = _rows(run_dir)
    lat = [(partition_index(r["problem_id"], partitions), r["latency_ms"] / 1000.0) for r in rows]
    per_part = collections.Counter()
    for p, s in lat:
        per_part[p] += s
    total = sum(per_part.values())
    out = {"tasks": len(lat), "total_lean_s": round(total, 2),
           "partition_time_max_over_mean": round(max(per_part.values()) / (total / partitions), 3),
           "task_time_max_s": round(max(s for _, s in lat), 2),
           "share_of_time_in_slowest_1pct_tasks": round(
               sum(sorted((s for _, s in lat), reverse=True)[: max(1, len(lat) // 100)]) / total, 3)}
    for w in workers:
        static = collections.Counter()
        for p, s in per_part.items():
            static[p % w] += s
        heap = [0.0] * w
        for _, s in lat:                       # tasks in queue order, next free worker takes the next task
            t = heapq.heappop(heap)
            heapq.heappush(heap, t + s)
        out[f"w{w}"] = {"ideal_s": round(total / w, 2), "static_partition_makespan_s": round(max(static.values()), 2),
                        "work_stealing_makespan_s": round(max(heap), 2)}
    json.dump(out, open(os.path.join(RES, f"skew_{os.path.basename(run_dir)}.json"), "w"), indent=1)
    return out


# Root cause of a failed candidate: who has to fix it (rule-based, first match wins, from the verified code
# and the compiler message). Owners: pipeline = our post-processing, environment = the fixed header/library,
# model = the generated statement, resource = the verifier's time limit.
_LET_CUT = re.compile(r"(?:^|[\s:(,])(?:let|letI|have|haveI)\s[^;]*:=\s*by sorry\s*$", re.S)
_HEADER_TOKEN = re.compile(r"unexpected token '([α-ωΑ-Ω√!])'")
CAUSES = [
    ("timeout", "resource", lambda st, msg, code: st == "TIMEOUT"),
    ("empty_output", "model", lambda st, msg, code: st == "EMPTY_OUTPUT"),
    ("sanitizer_let_cut", "pipeline", lambda st, msg, code: st == "PARSE_ERROR" and bool(_LET_CUT.search(code))),
    ("header_notation", "environment", lambda st, msg, code: st == "PARSE_ERROR" and bool(_HEADER_TOKEN.search(msg))),
    ("lean4_syntax", "model", lambda st, msg, code: st == "PARSE_ERROR"),
    ("missing_namespace_or_notation", "model",
     lambda st, msg, code: st == "UNKNOWN_IDENTIFIER" or "elaboration function for" in msg),
    ("types_coercions_instances", "model", lambda st, msg, code: st == "TYPE_MISMATCH"),
    ("other", "model", lambda st, msg, code: True),
]


def failure_causes(run_dir: str) -> dict:
    """Classify every failed candidate of a run by root cause, using the exact code the run verified
    (the payloads of its verify queue)."""
    import sqlite3
    con = sqlite3.connect(os.path.join(run_dir, "run.db"))
    code = {th: json.loads(p).get("lean_code") or "" for th, p in con.execute("SELECT task_hash, payload FROM q_verify")}
    rows = _rows(run_dir)
    out = collections.OrderedDict((k, {"cause": k, "owner": o, "n": 0, "problem_ids": []}) for k, o, _ in CAUSES)
    for r in rows:
        if r["status"] == COMPILE_OK:
            continue
        msg = r["compiler_message"] or ""
        for k, _, rule in CAUSES:
            if rule(r["status"], msg, code.get(r["task_hash"], "")):
                out[k]["n"] += 1
                out[k]["problem_ids"].append(r["problem_id"])
                break
    causes = sorted((c for c in out.values() if c["n"]), key=lambda c: -c["n"])
    by_owner = collections.Counter()
    for c in causes:
        by_owner[c["owner"]] += c["n"]
    rep = {"run": os.path.basename(run_dir), "n": len(rows), "n_failed": sum(c["n"] for c in causes),
           "by_owner": dict(by_owner), "causes": causes}
    json.dump(rep, open(os.path.join(RES, f"failure_causes_{os.path.basename(run_dir)}.json"), "w"), indent=1,
              ensure_ascii=False)
    return rep


def semantic_summary(run_dirs: list[str]) -> dict:
    """Verdict counts of afp.semantic per run and per source (only compiled candidates are checked)."""
    units = load_units(UNITS)
    out = {}
    for d in run_dirs:
        rows = [json.loads(line) for line in open(os.path.join(d, "semantic.jsonl"), encoding="utf-8")]
        by_src = collections.defaultdict(collections.Counter)
        for r in rows:
            by_src[units[r["problem_id"]].source][r["verdict"]] += 1
        tot = collections.Counter(r["verdict"] for r in rows)
        flagged = sum(v for k, v in tot.items() if k in FLAGGED)
        checked = sum(v for k, v in tot.items() if k != "NOT_CHECKED_SLOW")
        out[os.path.basename(d)] = {"candidates": len(rows), "checked": checked, "flagged": flagged,
                                    "flagged_share_of_checked": round(flagged / checked, 4) if checked else None,
                                    "verdicts": dict(tot.most_common()),
                                    "by_source": {s: dict(c.most_common()) for s, c in sorted(by_src.items())}}
    json.dump(out, open(os.path.join(RES, "semantic_summary.json"), "w"), indent=1)
    return out


def time_budget(run_dir: str) -> dict:
    """Where the Lean workers' steady-state time went: useful checks, waiting on a timed-out check,
    REPL restarts (after a timeout) and recycles, and the rest (queue, IPC, Python, idle at the tail)."""
    cfg = json.load(open(os.path.join(run_dir, "config.json")))
    m = json.load(open(os.path.join(run_dir, "metrics.json")))
    rows = _rows(run_dir)
    useful = sum(r["latency_ms"] for r in rows if r["status"] != "TIMEOUT") / 1000.0
    timeout_wait = sum(r["latency_ms"] for r in rows if r["status"] == "TIMEOUT") / 1000.0
    restart = recycle = 0.0
    for line in open(os.path.join(run_dir, "events.jsonl"), encoding="utf-8"):
        e = json.loads(line)
        if e["kind"] in ("repl_restarted", "repl_recycled"):
            d = json.loads(e["detail"]) if isinstance(e["detail"], str) else e["detail"]
            if e["kind"] == "repl_restarted":
                restart += d.get("startup_s", 0.0)
            else:
                recycle += d.get("startup_s", 0.0)
    total = cfg["workers"] * m["steady_window_s"]
    # a restart/recycle still running when the last result lands lies partly outside the window: clip it
    room = max(0.0, total - useful - timeout_wait)
    recycle_in = min(recycle, room)
    restart_in = min(restart, room - recycle_in)
    parts = {"useful_check_s": useful, "timeout_wait_s": timeout_wait, "restart_s": restart_in, "recycle_s": recycle_in}
    parts["other_s"] = max(0.0, total - sum(parts.values()))
    return {"run": os.path.basename(run_dir), "workers": cfg["workers"], "batch": cfg["batch"],
            "steady_window_s": m["steady_window_s"], "worker_time_s": round(total, 1),
            "n_timeouts": m["repl_timeouts"], "restart_total_s": round(restart, 1),
            **{k: round(v, 1) for k, v in parts.items()},
            **{k.replace("_s", "_share"): round(v / total, 3) for k, v in parts.items()}}


def time_budgets(prefix: str = "mx_T10K_", out_name: str = "time_budget_T10K.json") -> list[dict]:
    import glob
    rows = [time_budget(d) for d in sorted(glob.glob(os.path.join(RUNS, prefix + "*")))
            if os.path.exists(os.path.join(d, "metrics.json"))]
    json.dump(rows, open(os.path.join(RES, out_name), "w"), indent=1)
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    ss = sub.add_parser("semantic", help="verdict counts of afp.semantic for the given runs")
    ss.add_argument("--runs", nargs="+", required=True)
    b = sub.add_parser("budget", help="where the workers' time went, for every run whose id starts with --prefix")
    b.add_argument("--prefix", default="mx_T10K_")
    b.add_argument("--out", default="time_budget_T10K.json")
    t = sub.add_parser("taxonomy")
    t.add_argument("--run", required=True)
    f = sub.add_parser("causes")
    f.add_argument("--run", required=True)
    p = sub.add_parser("passk")
    p.add_argument("--zero", required=True)
    p.add_argument("--few", required=True)
    c = sub.add_parser("corpus")
    c.add_argument("--runs", nargs="+", required=True)
    s = sub.add_parser("skew")
    s.add_argument("--run", required=True)
    a = ap.parse_args(argv)
    if a.cmd == "skew":
        print(json.dumps(skew(run_dir(a.run)), indent=1))
        return
    if a.cmd == "causes":
        print(json.dumps(failure_causes(run_dir(a.run)), indent=1, ensure_ascii=False))
        return
    if a.cmd == "semantic":
        print(json.dumps(semantic_summary([run_dir(r) for r in a.runs]), indent=1))
        return
    if a.cmd == "budget":
        print(json.dumps(time_budgets(a.prefix, a.out), indent=1))
        return
    if a.cmd == "taxonomy":
        r = taxonomy(run_dir(a.run))
        print(json.dumps({k: r[k] for k in ("n", "status", "first_error_kind", "by_source", "top_unknown_identifiers")},
                         indent=1, ensure_ascii=False))
    elif a.cmd == "passk":
        print(json.dumps(passk(run_dir(a.zero), run_dir(a.few)), indent=1))
    else:
        print(json.dumps(corpus([run_dir(r) for r in a.runs]), indent=1))


if __name__ == "__main__":
    main()
