"""Automatic semantic checks for statements that COMPILE (answer to: "compile được nhưng sai nghĩa:
hệ thống phải phát hiện thế nào?").

Lean only guarantees that a statement is well-typed. A compiled statement can still be wrong:
  * VACUOUS   - the hypotheses are contradictory, so the theorem is true for a silly reason
  * FALSE     - the negation of the conclusion is provable under the hypotheses (wrong formula / answer)
  * TRIVIAL   - an undergraduate theorem (ProofNet) that cheap automation closes immediately
                -> the model probably dropped the hard part
  * ANSWER_MISSING - an answer problem whose reference answer does not appear in the statement
  * NOT_EQUIV_GOLD - automation cannot show candidate <-> human gold statement (only a weak signal)
Each check is one Lean command run in the warm REPL (header env), bounded by maxHeartbeats and a
wall-clock timeout. A *proved* check is hard evidence; a failed check proves nothing.

  python -m afp.semantic --run runs/<run_id> --workers 2
"""
from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import os
import re
import sys
import time

from .gold import gold_code
from .inference.batchfile import load_units
from .lean.repl import LeanREPL, ReplCrash, ReplTimeout
from .prompts import LEAN_HEADER
from .schema import COMPILE_OK
from .store import CandidateStore, ResultStore

from .paths import AUDIT, CANDIDATES_DB, RAW, ROOT, RUNS, TABLES, TIERS_DIR, UNITS, result_path, run_dir

# `decide` is left out on purpose: kernel reduction is not bounded by maxHeartbeats, so a big decidable
# proposition runs into the wall-clock timeout and costs a REPL restart (~35 s).
AUTO = ("first | (norm_num; done) | (simp_all; done) | (omega; done) | (linarith; done)"
        " | (nlinarith; done) | (positivity; done) | (aesop; done)")
AUTO_FALSE = ("first | (simp_all; done) | (linarith; done) | (omega; done) | (norm_num at *; done)"
              " | (nlinarith; done) | contradiction")
AUTO_NEG = "first | (norm_num; done) | (simp_all; done) | (omega; done) | (push_neg; norm_num; done)"


def AUTO_USING(h: str) -> str:
    return (f"first | (exact {h}) | (simpa using {h}) | (apply {h} <;> assumption) | (simp_all; done)"
            f" | (aesop; done)")


_OPEN, _CLOSE = "([{⟨⦃", ")]}⟩⦄"


def split_signature(code: str):
    """'<prefix>\\ntheorem name binders : concl := by sorry' -> (prefix, name, binders, concl)."""
    m = re.search(r"^theorem\s+(\S+)", code, re.M)
    if not m:
        return None
    prefix, rest = code[: m.start()].strip(), code[m.end():]
    body_end = rest.rfind(":= by sorry")
    if body_end < 0:
        return None
    sig = rest[:body_end]
    depth = 0
    for i, ch in enumerate(sig):
        if ch in _OPEN:
            depth += 1
        elif ch in _CLOSE:
            depth -= 1
        elif ch == ":" and depth == 0 and not sig.startswith(":=", i):
            return prefix, m.group(1), sig[:i].strip(), sig[i + 1:].strip()
    return None


def build_checks(code: str, gold: str | None) -> dict[str, str]:
    s = split_signature(code)
    if not s:
        return {}
    prefix, name, binders, concl = s
    pre = (prefix + "\n") if prefix else ""
    hb = "set_option maxHeartbeats 100000 in\n"
    checks = {
        "auto_prove": f"{pre}{hb}theorem {name}_auto {binders} : {concl} := by\n  {AUTO}",
        "vacuous": f"{pre}{hb}theorem {name}_vac {binders} : False := by\n  {AUTO_FALSE}",
        "refuted": f"{pre}{hb}theorem {name}_neg {binders} : ¬ ({concl}) := by\n  {AUTO_NEG}",
    }
    g = split_signature(gold) if gold else None
    if g:
        gprefix, gname, gbinders, gconcl = g
        gpre = (gprefix + "\n") if gprefix else ""
        checks["gold_to_cand"] = (f"{gpre}{gold}\n{pre}{hb}theorem {name}_g2c {binders} : {concl} := by\n"
                                  f"  have hg := @{gname}\n  {AUTO_USING('hg')}")
        checks["cand_to_gold"] = (f"{pre}{code}\n{gpre}{hb}theorem {name}_c2g {gbinders} : {gconcl} := by\n"
                                  f"  have hc := @{name}\n  {AUTO_USING('hc')}")
    return checks


# ---------------------------------------------------------------------- text heuristics
def norm_answer(ans: str) -> list[str]:
    """Plausible Lean spellings of a LaTeX answer (heuristic)."""
    a = ans.strip().strip("$").replace("\\!", "").replace(" ", "")
    a = re.sub(r"\\(d|t)?frac\{([^{}]+)\}\{([^{}]+)\}", r"\2/\3", a)
    a = re.sub(r"\\sqrt\{([^{}]+)\}", r"√\1", a)
    a = a.replace("\\pi", "π").replace("\\left", "").replace("\\right", "").replace("^\\circ", "")
    a = a.replace("{", "").replace("}", "").replace(",", "")
    outs = {a}
    if a.startswith("√"):
        outs.add("Real.sqrt" + a[1:])
        outs.add("sqrt" + a[1:])
    if re.fullmatch(r"-?\d+\.\d+", a):
        outs.add(a.rstrip("0").rstrip("."))
    return [o for o in outs if o]


def answer_present(answer: str | None, code: str) -> bool | None:
    if not answer:
        return None
    flat = re.sub(r"[\s()]", "", code)
    return any(re.sub(r"[()]", "", f) in flat for f in norm_answer(answer))


def heuristics(code: str, unit) -> dict:
    s = split_signature(code)
    binders, concl = (s[2], s[3]) if s else ("", "")
    ans = unit.metadata.get("answer")
    return {
        "has_binders": bool(binders.strip()),
        "concl_is_true": concl.strip() in ("True", "true = true"),
        "answer_present": answer_present(ans, concl + " " + binders),
        "nat_only": bool(ans) and bool(re.search(r"[-/.]|sqrt|frac|pi", ans)) and "ℕ" in code
                    and "ℝ" not in code and "ℚ" not in code and "ℤ" not in code,
    }


def verdict(flags: dict, unit) -> str:
    src = unit.source
    if flags.get("vacuous"):
        return "VACUOUS"
    if flags.get("refuted"):
        return "FALSE"
    if flags.get("concl_is_true"):
        return "TRIVIAL"
    if src == "proofnet" and flags.get("auto_prove"):
        return "TRIVIAL"
    if flags.get("answer_present") is False:
        return "ANSWER_MISSING"
    if src == "gsm8k" and not flags.get("has_binders"):
        return "ARITHMETIC_ONLY"      # the word problem was reduced to a bare computation
    if flags.get("gold_to_cand") and flags.get("cand_to_gold"):
        return "EQUIV_GOLD"
    if unit.metadata.get("has_answer") and flags.get("auto_prove"):
        return "PROVED_CONSISTENT"    # Lean derives the stated answer from the stated hypotheses
    return "NO_EVIDENCE_OF_ERROR"


# ---------------------------------------------------------------------- runner
def _worker(tasks, out_q, timeout_s):
    """One checker process. Keeps a hot spare REPL so a timeout costs ~timeout_s, not a ~35 s restart,
    and stops checking a candidate after its first timeout (its other checks would time out too)."""
    import threading
    repl = LeanREPL(LEAN_HEADER)
    repl.start()
    box = {}

    def warm():
        r = LeanREPL(LEAN_HEADER, env=repl.env)
        r.start()
        box["spare"] = r

    th = threading.Thread(target=warm, daemon=True)
    th.start()
    bad = set()
    for key, check, code in tasks:
        if key in bad:
            out_q.put((key, check, False, 0.0, "skipped_after_timeout"))
            continue
        t0 = time.time()
        try:
            resp, ms = repl.check(code, timeout_s)
            errs = [m for m in resp.get("messages", []) if m.get("severity") == "error"]
            ok = not errs and "message" not in resp
            out_q.put((key, check, ok, round(ms, 1), (errs[0]["data"][:200] if errs else "")))
            continue
        except ReplTimeout:
            print(f"TIMEOUT check={check} key={key[:60]}", file=sys.stderr, flush=True)
            out_q.put((key, check, False, timeout_s * 1000, "timeout"))
        except ReplCrash as e:
            out_q.put((key, check, False, (time.time() - t0) * 1000, f"crash {e}"[:200]))
        bad.add(key)
        repl.kill()
        th.join()                      # the spare is normally ready long before it is needed
        repl = box.pop("spare")
        th = threading.Thread(target=warm, daemon=True)
        th.start()
    th.join()
    box.pop("spare", repl).close()
    repl.close()
    out_q.put(None)


def run_semantic(run_dir: str, workers: int = 2, timeout_s: float = 20.0, limit: int | None = None,
                 gold_ok: set | None = None) -> str:
    cfg = json.load(open(os.path.join(run_dir, "config.json")))
    rs = ResultStore(os.path.join(run_dir, "run.db"))
    cs = CandidateStore(CANDIDATES_DB)
    units = load_units(UNITS)
    rows = [r for r in rs.rows(cfg["run_id"]) if r["status"] == COMPILE_OK]
    rows = rows[:limit] if limit else rows
    slow = [r for r in rows if r["latency_ms"] > 2000]   # every check on these would hit the wall timeout
    rows = [r for r in rows if r["latency_ms"] <= 2000]
    tasks, meta = [], {}
    for r in rows:
        c = cs.get(r["task_hash"])
        u = units[r["problem_id"].split(":", 1)[1] if r["problem_id"].startswith("replay") else r["problem_id"]]
        gold = None
        if u.metadata.get("gold_formal_statement") and (gold_ok is None or u.problem_id in gold_ok):
            gold = gold_code(u, "gold_ref")
        checks = build_checks(c.lean_code, gold)
        meta[r["task_hash"]] = {"problem_id": u.problem_id, "source": u.source, "domain": u.domain,
                                "prompt_version": r["prompt_version"], "candidate_index": r["candidate_index"],
                                "lean_code": c.lean_code, "has_gold": gold is not None,
                                **heuristics(c.lean_code, u)}
        for name, code in checks.items():
            tasks.append((r["task_hash"], name, code))
    ctx = mp.get_context("spawn")
    q = ctx.Queue()
    shards = [tasks[i::workers] for i in range(workers)]
    procs = [ctx.Process(target=_worker, args=(s, q, timeout_s)) for s in shards]
    for p in procs:
        p.start()
    done, t0, n_got, n_to = 0, time.time(), 0, 0
    while done < workers:
        item = q.get()
        if item is None:
            done += 1
            continue
        key, check, ok, ms, err = item
        meta[key][check] = ok
        meta[key][check + "_ms"] = ms
        n_got += 1
        n_to += err == "timeout"
        if n_got % 250 == 0:
            print(f"  {n_got}/{len(tasks)} checks, {n_to} wall timeouts, {time.time() - t0:.0f}s", flush=True)
    for p in procs:
        p.join()
    out = os.path.join(run_dir, "semantic.jsonl")
    for r in slow:
        meta[r["task_hash"]] = {"problem_id": r["problem_id"], "skipped": "slow_to_elaborate", "latency_ms": r["latency_ms"]}
    with open(out, "w", encoding="utf-8") as f:
        for th, m in meta.items():
            if m.get("skipped"):
                f.write(json.dumps({"task_hash": th, **m, "verdict": "NOT_CHECKED_SLOW"}, ensure_ascii=False) + "\n")
                continue
            m["verdict"] = verdict(m, units[m["problem_id"]])
            f.write(json.dumps({"task_hash": th, **m}, ensure_ascii=False) + "\n")
    print(f"{len(meta)} compiled candidates, {len(tasks)} checks in {time.time() - t0:.0f}s -> {out}")
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--timeout", type=float, default=20.0)
    ap.add_argument("--limit", type=int)
    ap.add_argument("--gold-run", help="run dir of the gold run: only gold statements that compiled are used")
    a = ap.parse_args(argv)
    gold_ok = None
    if a.gold_run:
        g = ResultStore(os.path.join(run_dir(a.gold_run), "run.db"))
        gold_ok = {r["problem_id"] for r in g.rows() if r["status"] == COMPILE_OK}
    run_semantic(run_dir(a.run), a.workers, a.timeout, a.limit, gold_ok)


if __name__ == "__main__":
    main()
