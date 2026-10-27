"""Analyses that answer the course guide's questions for group 5 directly (all from raw files, no hand-typed numbers).

  python -m afp.study inference    # problems per LLM request vs tokens/problem and failures; with/without request retry
  python -m afp.study candidates   # 1 vs k candidates and resample-on-failure retry (few-shot T100, 4 samples/problem)
  python -m afp.study quality      # parse rate, compile rate, Pass@k, semantic flags, latency for every quality run
  python -m afp.study layers       # semantic checker ablation: Lean checks vs heuristics, against the audit sample
  python -m afp.study baseline     # required baseline (1 problem/request) vs batch-job generation on the same 20 problems
  python -m afp.study ablation     # one table of every on/off comparison, with the file each number comes from
  python -m afp.study runs         # results/raw/runs_manifest.csv: one line per run (guide Appendix B fields)
  python -m afp.study all
Outputs go to results/figures/<name>.json (+ .md for the ablation table).
"""
from __future__ import annotations

import collections
import csv
import glob
import json
import math
import os
import statistics
import sys

from .aggregator import pass_at_k
from .paths import AUDIT, CANDIDATES_DB, RAW, ROOT, RUNS, TABLES, result_path
from .schema import COMPILE_OK

FLAGS_LEAN = {"VACUOUS", "FALSE", "TRIVIAL"}            # layer 1: proved by Lean (or Lean-solved ProofNet theorem)
FLAGS_HEUR = {"ANSWER_MISSING", "ARITHMETIC_ONLY"}       # layer 2: cheap heuristics
CONFIRMED = {"EQUIV_GOLD", "PROVED_CONSISTENT"}          # Lean evidence that the statement is right


def _dump(name: str, obj) -> dict:
    os.makedirs(TABLES, exist_ok=True)
    with open(os.path.join(TABLES, name), "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=1, ensure_ascii=False)
    return obj


def _csv(path: str) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _semantic(run: str) -> dict:
    p = os.path.join(RUNS, run, "semantic.jsonl")
    if not os.path.exists(p):
        return {}
    return {d["task_hash"]: d for d in map(json.loads, open(p, encoding="utf-8"))}


def _results(run: str) -> list[dict]:
    return _csv(os.path.join(RUNS, run, "raw_results.csv"))


def _q(vals, q):
    vals = sorted(vals)
    if not vals:
        return None
    k = (len(vals) - 1) * q / 100
    f, c = math.floor(k), math.ceil(k)
    return vals[f] if f == c else vals[f] + (vals[c] - vals[f]) * (k - f)


# ----------------------------------------------------------------------------------------------- inference batching
# Request size = problems sent in ONE request to the model (a batch-job file, or a single problem). The job log
# (results/raw/inference_jobs.json) is free text per job; this table maps each entry to its size class and outcome.
JOB_CLASS = {
    "v1_zeroshot_s0_p00": ("100-142", "ok"), "v1_zeroshot_s0_p01": ("100-142", "ok"),
    "v1_zeroshot_s0_p05": ("100-142", "ok"), "v1_zeroshot_s0_p06": ("100-142", "ok"),
    "v1_zeroshot_s0_p04": ("100-142", "ok"),
    "v1_zeroshot_s0_p03": ("100-142", "failed"), "v1_zeroshot_s0_p07": ("100-142", "failed"),
    "v2_fewshot_s1_p00": ("100-142", "failed"), "v2_fewshot_s2_p00": ("100-142", "failed"),
    "v2_fewshot_s0_p00": ("100-142", "partial"), "v2_fewshot_s3_p00": ("100-142", "partial"),
    "v1_zeroshot_s0_p02": ("100-142", "partial"),
    "v1_zeroshot_s0_p07 (resume, 6 sub-jobs)": ("20-26", "ok"), "v1_zeroshot_s0_p03 (resume, 5 sub-jobs)": ("20-26", "ok"),
    "v2_fewshot_s2_p00 (resume, 4 sub-jobs)": ("20-26", "ok"), "v2_fewshot_s1_p00 (resume, 4 sub-jobs)": ("20-26", "ok"),
    "v2_fewshot_s0_p00 (resume, 2 sub-jobs)": ("20-26", "ok"), "v2_fewshot_s3_p00 (resume, 3 sub-jobs)": ("20-26", "ok"),
    "v1_zeroshot_s0_p02 resume (2 sub-jobs of 26/25)": ("20-26", "failed"),
    "v1_zeroshot_s0_p02 resume B (3 sub-jobs of 9, 'think briefly')": ("9", "ok"),
    "v1_zeroshot_s0_p02 resume A (3 sub-jobs of 9, 'think briefly')": ("9", "ok"),
}
# requests per log entry (a resume entry groups several sub-job requests)
JOB_REQUESTS = {"v1_zeroshot_s0_p07 (resume, 6 sub-jobs)": 6, "v1_zeroshot_s0_p03 (resume, 5 sub-jobs)": 5,
                "v2_fewshot_s2_p00 (resume, 4 sub-jobs)": 4, "v2_fewshot_s1_p00 (resume, 4 sub-jobs)": 4,
                "v2_fewshot_s0_p00 (resume, 2 sub-jobs)": 2, "v2_fewshot_s3_p00 (resume, 3 sub-jobs)": 3,
                "v1_zeroshot_s0_p02 resume (2 sub-jobs of 26/25)": 2,
                "v1_zeroshot_s0_p02 resume B (3 sub-jobs of 9, 'think briefly')": 3,
                "v1_zeroshot_s0_p02 resume A (3 sub-jobs of 9, 'think briefly')": 3}


def inference() -> dict:
    log = json.load(open(os.path.join(RAW, "inference_jobs.json"), encoding="utf-8"))
    man = json.load(open(os.path.join(ROOT, "data/jobs/v1_zeroshot_1req/v1_zeroshot_1req_s0_t20.manifest.json"),
                         encoding="utf-8"))
    classes = collections.OrderedDict((k, {"requests": 0, "requests_ok": 0, "requests_partial": 0, "requests_failed": 0,
                                           "problems_answered": 0, "zeroshot_tokens": 0, "zeroshot_problems": 0,
                                           "zeroshot_wall_s": 0.0, "all_tokens": 0, "all_problems": 0})
                                      for k in ("1", "9", "20-26", "100-142"))
    unknown = []
    for j in log["jobs"]:
        if j["job"] not in JOB_CLASS:
            unknown.append(j["job"])
            continue
        size, outcome = JOB_CLASS[j["job"]]
        c = classes[size]
        n_req = JOB_REQUESTS.get(j["job"], 1)
        c["requests"] += n_req
        c[f"requests_{outcome}"] += n_req
        c["problems_answered"] += j.get("problems", 0)
        if j.get("subagent_tokens"):
            c["all_tokens"] += j["subagent_tokens"]
            c["all_problems"] += j["problems"]
            if j["job"].startswith("v1_zeroshot"):
                c["zeroshot_tokens"] += j["subagent_tokens"]
                c["zeroshot_problems"] += j["problems"]
                c["zeroshot_wall_s"] += j.get("duration_s", 0.0)
    one = classes["1"]
    reqs = man["requests"]
    one.update(requests=len(reqs), requests_ok=len(reqs), problems_answered=len(reqs),
               zeroshot_tokens=sum(r["subagent_tokens"] for r in reqs), zeroshot_problems=len(reqs),
               zeroshot_wall_s=sum(r["duration_ms"] for r in reqs) / 1000.0,
               all_tokens=sum(r["subagent_tokens"] for r in reqs), all_problems=len(reqs),
               tokens_per_request_median=statistics.median(r["subagent_tokens"] for r in reqs),
               wall_s_per_request_median=round(statistics.median(r["duration_ms"] for r in reqs) / 1000.0, 1))
    for c in classes.values():
        c["zeroshot_tokens_per_problem"] = round(c["zeroshot_tokens"] / c["zeroshot_problems"]) if c["zeroshot_problems"] else None
        c["zeroshot_wall_s_per_problem"] = round(c["zeroshot_wall_s"] / c["zeroshot_problems"], 2) if c["zeroshot_problems"] else None
        c["tokens_per_problem_all_prompts"] = round(c["all_tokens"] / c["all_problems"]) if c["all_problems"] else None
        c["request_failure_share"] = round((c["requests_failed"] + c["requests_partial"]) / c["requests"], 3) if c["requests"] else None
    planned = log["totals"]["candidates_generated"]
    first = sum(j.get("problems", 0) for j in log["jobs"] if JOB_CLASS.get(j["job"], ("", ""))[0] == "100-142")
    out = {"by_problems_per_request": classes,
           "retry": {"planned_candidates": planned, "answered_by_first_requests": first,
                     "share_without_retry": round(first / planned, 3), "answered_with_retry": planned,
                     "retry_mechanism": "missing keys re-sent in smaller sub-jobs keyed by TaskHash (afp.inference.batchfile resume)"},
           "note": ("tokens are the agent's total tokens (its fixed context is ~80K per request); wall time is the agent's "
                    "time for the whole request, problems inside a request are answered one after another; the 9-problem "
                    "requests had an extra 'think briefly' line; unmatched log entries: " + (", ".join(unknown) or "none"))}
    return _dump("inference_batching.json", out)


# ----------------------------------------------------------------------------------------------- candidates and retry
def candidates(run: str = "q_T100_fewshot") -> dict:
    import sqlite3
    rows = _results(run)
    sem = _semantic(run)
    tok = {th: (pt or 0) + (ct or 0) for th, pt, ct in
           sqlite3.connect(CANDIDATES_DB).execute("SELECT task_hash, prompt_tokens, completion_tokens FROM candidates")}
    by = collections.defaultdict(dict)
    for r in rows:
        by[r["problem_id"]][int(r["candidate_index"])] = r
    n_per = max(len(v) for v in by.values())
    probs = sorted(by)
    out = {"run": run, "problems": len(probs), "samples_per_problem": n_per}
    out["pass_at_k"] = {}
    for k in range(1, n_per + 1):
        vals = [pass_at_k(len(by[p]), sum(1 for r in by[p].values() if r["status"] == COMPILE_OK), k) for p in probs]
        out["pass_at_k"][str(k)] = round(sum(vals) / len(vals), 4)
    mean_tok = statistics.mean(tok[r["task_hash"]] for r in rows if r["task_hash"] in tok)
    policies = {}
    for budget in range(n_per):                      # resample on compile failure, at most `budget` extra requests
        ok = used = flagged = 0
        for p in probs:
            tried = 0
            chosen = None
            for i in range(budget + 1):
                tried += 1
                if by[p][i]["status"] == COMPILE_OK:
                    chosen = by[p][i]
                    break
            used += tried
            if chosen is not None:
                ok += 1
                if (sem.get(chosen["task_hash"], {}).get("verdict") or "") in FLAGS_LEAN | FLAGS_HEUR:
                    flagged += 1
        policies[f"retry_{budget}"] = {"compile_rate": round(ok / len(probs), 4),
                                        "candidates_per_problem": round(used / len(probs), 3),
                                        "est_tokens_per_problem": round(used / len(probs) * mean_tok),
                                        "flagged_share_of_compiled": round(flagged / ok, 4) if ok else None}
    # always generate all samples, keep the best by semantic verdict (the curation rule of the corpus)
    rank = {"EQUIV_GOLD": 0, "PROVED_CONSISTENT": 1, "NO_EVIDENCE_OF_ERROR": 2}
    ok = flagged = 0
    for p in probs:
        comp = [r for r in by[p].values() if r["status"] == COMPILE_OK]
        if not comp:
            continue
        ok += 1
        best = min(comp, key=lambda r: rank.get(sem.get(r["task_hash"], {}).get("verdict"), 5))
        if (sem.get(best["task_hash"], {}).get("verdict") or "") in FLAGS_LEAN | FLAGS_HEUR:
            flagged += 1
    policies[f"best_of_{n_per}"] = {"compile_rate": round(ok / len(probs), 4), "candidates_per_problem": n_per,
                                     "est_tokens_per_problem": round(n_per * mean_tok),
                                     "flagged_share_of_compiled": round(flagged / ok, 4) if ok else None}
    out["policies"] = policies
    out["mean_est_tokens_per_candidate"] = round(mean_tok, 1)
    out["note"] = "tokens = prompt + output estimated as characters / 3.5 (API-equivalent, without agent overhead)"
    return _dump("candidates_retry.json", out)


# ----------------------------------------------------------------------------------------------- quality metrics
QUALITY_RUNS = ["q_T1K_zeroshot", "q_T100_fewshot", "base_T20_1req_A", "base_T20_batchjob_A"]


def _audit_accuracy() -> dict:
    out = {}
    for r in ("A", "B"):
        p = os.path.join(AUDIT, f"llm_rater_{r}.csv")
        if os.path.exists(p):
            labs = [x["label"] for x in _csv(p)]
            out[f"llm_rater_{r}"] = {"n": len(labs), "DUNG": round(labs.count("DUNG") / len(labs), 3),
                                     "DUNG_or_GAN_DUNG": round((labs.count("DUNG") + labs.count("GAN_DUNG")) / len(labs), 3)}
    for r in ("1", "2"):
        p = os.path.join(AUDIT, f"rater{r}.xlsx")
        try:
            from .audit import _read_labels
            labs = list(_read_labels(p).values())
        except Exception:
            labs = []
        out[f"human_rater_{r}"] = ({"n": len(labs), "DUNG": round(labs.count("DUNG") / len(labs), 3)}
                                   if labs else "chưa chấm")
    return out


def quality() -> dict:
    out = {}
    for run in QUALITY_RUNS:
        if not os.path.exists(os.path.join(RUNS, run, "raw_results.csv")):
            continue
        rows = _results(run)
        sem = _semantic(run)
        st = collections.Counter(r["status"] for r in rows)
        n = len(rows)
        lat = [float(r["latency_ms"]) for r in rows if float(r["latency_ms"]) > 0]
        by = collections.defaultdict(list)
        for r in rows:
            by[r["problem_id"]].append(r["status"] == COMPILE_OK)
        comp = [r for r in rows if r["status"] == COMPILE_OK]
        flagged = sum(1 for r in comp if (sem.get(r["task_hash"], {}).get("verdict") or "") in FLAGS_LEAN | FLAGS_HEUR)
        confirmed = sum(1 for r in comp if (sem.get(r["task_hash"], {}).get("verdict") or "") in CONFIRMED)
        out[run] = {
            "candidates": n, "problems": len(by),
            "parse_rate": round(1 - (st.get("PARSE_ERROR", 0) + st.get("EMPTY_OUTPUT", 0)) / n, 4),
            "compile_rate": round(st.get(COMPILE_OK, 0) / n, 4),
            "pass_at_1": round(statistics.mean(pass_at_k(len(v), sum(v), 1) for v in by.values()), 4),
            "pass_at_all": round(statistics.mean(1.0 if any(v) else 0.0 for v in by.values()), 4),
            "failure_by_type": {k: v for k, v in st.items() if k != COMPILE_OK},
            "semantic_checked": bool(sem),
            "flagged_share_of_compiled": round(flagged / len(comp), 4) if sem and comp else None,
            "lean_confirmed_share_of_compiled": round(confirmed / len(comp), 4) if sem and comp else None,
            "latency_ms_p50": round(_q(lat, 50), 1) if lat else None, "latency_ms_p95": round(_q(lat, 95), 1) if lat else None,
        }
    out["semantic_accuracy_on_audit_set"] = _audit_accuracy()
    out["note"] = ("semantic accuracy = share labelled DUNG on the 100-item audit sample of q_T1K_zeroshot; the LLM "
                   "raters are a pilot of the procedure, the human ratings (rater1/rater2.xlsx) replace them")
    return _dump("quality_metrics.json", out)


# ----------------------------------------------------------------------------------------------- semantic layers
def layers(run: str = "q_T1K_zeroshot") -> dict:
    sem = _semantic(run)
    verdicts = collections.Counter(d["verdict"] for d in sem.values())
    key = _csv(os.path.join(AUDIT, "audit_key.csv"))
    raters = {}
    for r in ("A", "B"):
        p = os.path.join(AUDIT, f"llm_rater_{r}.csv")
        if os.path.exists(p):
            raters[f"llm_{r}"] = {x["audit_id"]: x["label"] for x in _csv(p)}
    for r in ("1", "2"):
        try:
            from .audit import _read_labels
            labs = _read_labels(os.path.join(AUDIT, f"rater{r}.xlsx"))
            if labs:
                raters[f"human_{r}"] = labs
        except Exception:
            pass

    def flag(layer, v):
        return v in (FLAGS_LEAN if layer == "lean" else FLAGS_HEUR if layer == "heuristic" else FLAGS_LEAN | FLAGS_HEUR)

    out = {"run": run, "compiled_checked": len(sem), "verdicts": dict(verdicts),
           "flagged": {"lean": sum(v for k, v in verdicts.items() if k in FLAGS_LEAN),
                       "heuristic": sum(v for k, v in verdicts.items() if k in FLAGS_HEUR),
                       "lean_confirmed_correct": sum(v for k, v in verdicts.items() if k in CONFIRMED)},
           "vs_audit": {}}
    for name, labs in raters.items():
        res = {}
        for layer in ("lean", "heuristic", "both"):
            tp = fp = fn = 0
            for k in key:
                lab = labs.get(k["audit_id"])
                if lab is None:
                    continue
                wrong = lab != "DUNG"
                f = flag(layer, (sem.get(k["task_hash"]) or {}).get("verdict"))
                tp += f and wrong
                fp += f and not wrong
                fn += (not f) and wrong
            res[layer] = {"flagged": tp + fp, "true_pos": tp, "precision": round(tp / (tp + fp), 3) if tp + fp else None,
                          "recall": round(tp / (tp + fn), 3) if tp + fn else None}
        out["vs_audit"][name] = res
    out["note"] = "positive = rater did not label DUNG (SAI or GAN_DUNG); llm_* are the pilot raters"
    return _dump("semantic_layers.json", out)


# ----------------------------------------------------------------------------------------------- baseline
def _norm(code: str) -> str:
    import re
    code = re.sub(r"theorem\s+\S+", "theorem X", code or "")
    return " ".join(code.split())


def baseline() -> dict:
    import sqlite3
    con = sqlite3.connect(CANDIDATES_DB)
    cand = {th: (pid, pv, code, raw) for th, pid, pv, code, raw in
            con.execute("SELECT task_hash, problem_id, prompt_version, lean_code, raw_output FROM candidates")}
    runs = {"v1_zeroshot_1req": "base_T20_1req_A", "v1_zeroshot": "base_T20_batchjob_A"}
    out = {"problems": None, "by_mode": {}}
    stmts = {}
    for pv, run in runs.items():
        if not os.path.exists(os.path.join(RUNS, run, "raw_results.csv")):
            continue
        rows = _results(run)
        sem = _semantic(run)
        out["problems"] = len(rows)
        st = collections.Counter(r["status"] for r in rows)
        v = collections.Counter((sem.get(r["task_hash"]) or {}).get("verdict", "NOT_CHECKED") for r in rows
                                if r["status"] == COMPILE_OK)
        stmts[pv] = {r["problem_id"]: _norm(cand[r["task_hash"]][2]) for r in rows if r["task_hash"] in cand}
        lens = [len(cand[r["task_hash"]][2]) for r in rows if r["task_hash"] in cand]
        out["by_mode"][pv] = {"run": run, "status": dict(st), "compile_rate": round(st.get(COMPILE_OK, 0) / len(rows), 3),
                              "semantic_verdicts": dict(v),
                              "flagged": sum(c for k, c in v.items() if k in FLAGS_LEAN | FLAGS_HEUR),
                              "lean_confirmed": sum(c for k, c in v.items() if k in CONFIRMED),
                              "mean_statement_chars": round(statistics.mean(lens), 1) if lens else None}
    if len(stmts) == 2:
        a, b = stmts["v1_zeroshot_1req"], stmts["v1_zeroshot"]
        out["identical_statements_after_renaming"] = sum(1 for p in a if a[p] == b.get(p))
    inf = json.load(open(os.path.join(TABLES, "inference_batching.json"))) if os.path.exists(
        os.path.join(TABLES, "inference_batching.json")) else inference()
    out["cost"] = {"one_problem_per_request": inf["by_problems_per_request"]["1"],
                   "batch_jobs_100_142": inf["by_problems_per_request"]["100-142"]}
    return _dump("baseline_compare.json", out)


# ----------------------------------------------------------------------------------------------- run manifest
MANIFEST_FIELDS = ["run_id", "timestamp", "git_commit", "data_version", "machine", "software", "parameters",
                   "seed_timeout", "metrics", "status", "log"]


def runs_manifest() -> list[dict]:
    rows = []
    for d in sorted(glob.glob(os.path.join(RUNS, "*"))):
        p = os.path.join(d, "run_record.json")
        if not os.path.exists(p):
            continue
        r = json.load(open(p, encoding="utf-8"))
        m, prm = r.get("metrics") or {}, r.get("parameters") or {}
        rows.append({
            "run_id": r["run_id"], "timestamp": r["timestamp"],
            "git_commit": ((r.get("git_commit") or {}).get("commit") or "")[:12] or "none",
            "data_version": f"{r['data_version'].get('tier')}x{r['data_version'].get('replicas', 1)} "
                            f"tier_sha256={str(r['data_version'].get('tier_sha256'))[:12]}",
            "machine": f"{r['machine'].get('vcpus')} vCPU, {r['machine'].get('ram_gb')} GB RAM",
            "software": f"Python {r['software'].get('python')}, Lean {r['software'].get('lean')}, Mathlib {r['software'].get('mathlib_tag')}",
            "parameters": f"workers={prm.get('workers')} batch={prm.get('batch')} prompt={prm.get('prompt_version')} "
                          f"k={prm.get('k')} broker={json.dumps(prm.get('broker'))}",
            "seed_timeout": f"tier_seed={r['seed_timeout'].get('tier_seed')} wall={r['seed_timeout'].get('wall_timeout_s')}s "
                            f"heartbeats={r['seed_timeout'].get('max_heartbeats')}",
            "metrics": f"thr={m.get('throughput_problems_per_s')} p95={m.get('latency_ms_p95')} compile={m.get('compile_rate')}",
            "status": r.get("status"), "log": os.path.relpath(d, ROOT)})
    with open(os.path.join(RAW, "runs_manifest.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=MANIFEST_FIELDS)
        w.writeheader()
        w.writerows(rows)
    return rows


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    cmd = argv[0] if argv else "all"
    fns = {"inference": inference, "candidates": candidates, "quality": quality, "layers": layers,
           "baseline": baseline, "runs": runs_manifest}
    if cmd == "ablation":
        from .ablation import build
        print(build())
        return
    if cmd == "all":
        for name, fn in fns.items():
            try:
                fn()
                print("ok", name)
            except FileNotFoundError as e:
                print("skip", name, e)
        from .ablation import build
        build()
        print("ok ablation")
        return
    print(json.dumps(fns[cmd](), indent=1, ensure_ascii=False, default=str)[:4000])


if __name__ == "__main__":
    main()
