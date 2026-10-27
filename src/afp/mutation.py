"""Mutation testing of the semantic checker: how often does it catch a statement that COMPILES but is WRONG?

Take human gold statements that compile, inject one known error, keep the mutant only if it still
compiles, then run afp.semantic's checks against the original gold.

  ANSWER_CHANGE  `… = 93`  ->  `… = 94`                (wrong answer)
  DROP_HYP       remove the last hypothesis binder        (missing assumption)
  FLIP_REL       first top-level `≤`/`<`/`=` flipped      (different claim)
  VACUOUS        add `(h_bad : (1 : ℕ) = 0)`              (contradictory assumptions)
  TRIVIAL        conclusion replaced by `True`            (trivialised)
  CONTROL        unchanged gold                           (false-positive rate)

  python -m afp.mutation --n 120 --workers 2
"""
from __future__ import annotations

import argparse
import collections
import json
import multiprocessing as mp
import os
import random
import re
import time

from .gold import gold_code
from .inference.batchfile import load_units
from .semantic import _worker, build_checks, heuristics, split_signature, verdict
from .store import ResultStore

from .paths import AUDIT, CANDIDATES_DB, RAW, ROOT, RUNS, TABLES, TIERS_DIR, UNITS, result_path, run_dir
_OPEN, _CLOSE = "([{⟨⦃", ")]}⟩⦄"


def _groups(binders: str) -> list[str]:
    out, depth, cur = [], 0, ""
    for ch in binders:
        if ch in _OPEN:
            if depth == 0 and cur.strip():
                out.append(cur.strip())
                cur = ""
            depth += 1
        cur += ch
        if ch in _CLOSE:
            depth -= 1
            if depth == 0:
                out.append(cur.strip())
                cur = ""
    if cur.strip():
        out.append(cur.strip())
    return out


def _top_level_find(s: str, pats: list[str]) -> tuple[int, str] | None:
    depth = 0
    for i, ch in enumerate(s):
        if ch in _OPEN:
            depth += 1
        elif ch in _CLOSE:
            depth -= 1
        elif depth == 0:
            for p in pats:
                if s.startswith(p, i):
                    return i, p
    return None


def mutate(code: str, kind: str) -> str | None:
    sig = split_signature(code)
    if not sig:
        return None
    prefix, name, binders, concl = sig
    pre = (prefix + "\n") if prefix else ""
    if kind == "CONTROL":
        return code
    if kind == "ANSWER_CHANGE":
        m = re.search(r"=\s*(\d+)\s*$", concl)
        if not m:
            return None
        concl = concl[: m.start(1)] + str(int(m.group(1)) + 1) + concl[m.end(1):]
    elif kind == "DROP_HYP":
        gs = _groups(binders)
        hyp = [i for i, g in enumerate(gs) if re.match(r"\(\s*h\S*\s*:", g)]
        if not hyp:
            return None
        gs.pop(hyp[-1])
        binders = " ".join(gs)
    elif kind == "FLIP_REL":
        f = _top_level_find(concl, [" ≤ ", " < ", " = ", " ≥ ", " > "])
        if not f:
            return None
        i, p = f
        rep = {" ≤ ": " < ", " < ": " ≤ ", " = ": " ≠ ", " ≥ ": " > ", " > ": " ≥ "}[p]
        concl = concl[:i] + rep + concl[i + len(p):]
    elif kind == "VACUOUS":
        binders = (binders + " (h_bad : (1 : ℕ) = 0)").strip()
    elif kind == "TRIVIAL":
        concl = "True"
    return f"{pre}theorem {name} {binders} : {concl} := by sorry"


KINDS = ["CONTROL", "ANSWER_CHANGE", "DROP_HYP", "FLIP_REL", "VACUOUS", "TRIVIAL"]
SLOW_MS = 2000   # a statement that alone takes > 2 s to elaborate makes every check on it hit the wall timeout


def run(n: int = 120, workers: int = 2, seed: int = 3, gold_run: str = "runs/gold_check") -> dict:
    from .lean.repl import LeanREPL
    from .lean.classify import classify
    from .prompts import LEAN_HEADER
    units = load_units(UNITS)
    ok = {r["problem_id"] for r in ResultStore(os.path.join(run_dir(gold_run), "run.db")).rows() if r["status"] == "COMPILE_OK"}
    pool = sorted(p for p in ok if not units[p].metadata["gold_formal_statement"].lstrip().startswith(("def", "noncomputable")))
    rng = random.Random(seed)
    pids = rng.sample(pool, min(n, len(pool)))
    # 1) build mutants and keep those that still compile
    repl = LeanREPL(LEAN_HEADER)
    repl.start()
    items = []
    for pid in pids:
        u = units[pid]
        g = gold_code(u, "gold_ref")
        cand = gold_code(u, "cand_" + re.sub(r"\W", "_", pid)[-40:])
        for kind in KINDS:
            m = mutate(cand, kind)
            if not m:
                continue
            try:
                resp, ms = repl.check(m, 20)
            except Exception:
                repl.restart()
                continue
            if classify(resp)[0] != "COMPILE_OK" or ms > SLOW_MS:
                continue
            items.append({"key": f"{pid}|{kind}", "problem_id": pid, "kind": kind, "code": m, "gold": g})
    repl.close()
    # 2) semantic checks against the original gold statement
    tasks = []
    for it in items:
        for name, code in build_checks(it["code"], it["gold"]).items():
            tasks.append((it["key"], name, code))
    ctx = mp.get_context("spawn")
    q = ctx.Queue()
    print(f"{len(items)} compiled mutants/controls, {len(tasks)} checks", flush=True)
    procs = [ctx.Process(target=_worker, args=(tasks[i::workers], q, 10.0)) for i in range(workers)]
    for p in procs:
        p.start()
    res = collections.defaultdict(dict)
    done, n_got, n_to, t0 = 0, 0, 0, time.time()
    while done < workers:
        x = q.get()
        if x is None:
            done += 1
            continue
        key, check, ok_, ms, err = x
        res[key][check] = ok_
        n_got += 1
        n_to += err == "timeout"
        if n_got % 250 == 0:
            print(f"  {n_got}/{len(tasks)} checks, {n_to} wall timeouts, {time.time() - t0:.0f}s", flush=True)
    for p in procs:
        p.join()
    rows = []
    for it in items:
        f = res[it["key"]]
        f.update(heuristics(it["code"], units[it["problem_id"]]))
        v = verdict(f, units[it["problem_id"]])
        strong = v in ("VACUOUS", "FALSE", "TRIVIAL")
        equiv = bool(f.get("gold_to_cand")) and bool(f.get("cand_to_gold"))
        rows.append({"problem_id": it["problem_id"], "source": units[it["problem_id"]].source, "kind": it["kind"],
                     "verdict": v, "strong_flag": strong, "equiv_gold": equiv, "flagged_any": strong or not equiv,
                     **{k: f.get(k) for k in ("auto_prove", "vacuous", "refuted", "gold_to_cand", "cand_to_gold")}})
    os.makedirs(RAW, exist_ok=True)
    os.makedirs(TABLES, exist_ok=True)
    with open(os.path.join(RAW, "mutation_rows.jsonl"), "w") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")
    summ = {}
    for kind in KINDS:
        rs = [r for r in rows if r["kind"] == kind]
        if rs:
            summ[kind] = {"n": len(rs), "strong_flag_rate": round(sum(r["strong_flag"] for r in rs) / len(rs), 3),
                          "flagged_any_rate": round(sum(r["flagged_any"] for r in rs) / len(rs), 3),
                          "verdicts": dict(collections.Counter(r["verdict"] for r in rs))}
    json.dump(summ, open(os.path.join(TABLES, "mutation_summary.json"), "w"), indent=1)
    return summ


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=120)
    ap.add_argument("--workers", type=int, default=2)
    a = ap.parse_args()
    t0 = time.time()
    print(json.dumps(run(a.n, a.workers), indent=1))
    print(f"{time.time() - t0:.0f}s")
