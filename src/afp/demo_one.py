"""Demo NL -> Lean -> checker for one problem (course guide, group 5, week 10).

  python -m afp.demo_one                                   # first problem of the baseline subset
  python -m afp.demo_one --problem gsm8k:train:04141       # a statement that compiles but lost the problem
  python -m afp.demo_one --problem math:test/algebra/2167  # hypotheses with no real solution
  python -m afp.demo_one --problem <id> --lean "theorem t (x : ℝ) (h : 2 * x = 6) : x = 3 := by sorry"

Shows the natural-language problem, the stored candidates (model + prompt version, from the candidate store),
then checks one statement live in a warm Lean REPL: compile status and time, then the automatic semantic checks
(Lean: contradictory hypotheses / refutation / automatic proof / equivalence with the gold statement; heuristics:
answer present, bare arithmetic, truncating ℕ). New problems need an LLM backend (afp.inference.backends);
the demo uses the cached candidates, so it runs offline.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import time

from .gold import gold_code
from .inference.batchfile import load_units
from .lean.classify import classify
from .lean.repl import LeanREPL, ReplTimeout
from .paths import CANDIDATES_DB, DATA_SAMPLE, UNITS
from .prompts import LEAN_HEADER, sanitize
from .semantic import build_checks, heuristics, verdict

DEFAULT = "gsm8k:train:01484"


def line(t: str = "") -> None:
    print(t, flush=True)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--problem", default=DEFAULT)
    ap.add_argument("--version", default=None, help="prompt version of the stored candidate to check")
    ap.add_argument("--lean", default=None, help="check this statement instead of a stored candidate")
    ap.add_argument("--timeout", type=float, default=10.0)
    a = ap.parse_args(argv)

    units = load_units(UNITS)
    demo_units = os.path.join(DATA_SAMPLE, "units_demo.jsonl")     # demo problems outside T100 (sample-only checkout)
    if a.problem not in units and os.path.exists(demo_units):
        units.update(load_units(demo_units))
    u = units[a.problem]
    line(f"=== 1. Đề bài ({u.source}, {u.domain})")
    line(u.natural_statement.strip())
    con = sqlite3.connect(CANDIDATES_DB)
    rows = con.execute("SELECT prompt_version, candidate_index, model, lean_code FROM candidates WHERE problem_id=? "
                       "ORDER BY prompt_version, candidate_index", (a.problem,)).fetchall()
    line(f"\n=== 2. Ứng viên Lean trong candidate store ({len(rows)})")
    for pv, idx, model, code in rows:
        line(f"--- {pv} #{idx} ({model})")
        line(code)
    if a.lean:
        code = sanitize(a.lean, "cand_demo")
        line("\n--- statement typed for the demo (sanitised):")
        line(code)
    else:
        pick = [r for r in rows if a.version in (None, r[0])]
        if not pick:
            raise SystemExit("no stored candidate for this problem/version")
        code = pick[0][3]
    line("\n=== 3. Lean checker (REPL nóng: import Mathlib một lần, rồi kiểm từng phát biểu)")
    t0 = time.time()
    repl = LeanREPL(LEAN_HEADER)
    repl.start()
    line(f"REPL sẵn sàng sau {time.time() - t0:.1f} s")
    try:
        resp, ms = repl.check(code, a.timeout)
        status, kinds, msg, _ = classify(resp)
    except ReplTimeout:
        status, kinds, msg, ms = "TIMEOUT", [], f"hard timeout {a.timeout} s", a.timeout * 1000
    line(f"trạng thái: {status}   ({ms:.1f} ms)   {msg[:160]}")
    if status != "COMPILE_OK":
        repl.close()
        return
    line("\n=== 4. Kiểm tra ngữ nghĩa tự động (compile được chưa chắc đúng nghĩa)")
    gold = gold_code(u, "gold_demo") if u.metadata.get("gold_formal_statement") else None
    flags = {}
    for name, cmd in build_checks(code, gold).items():
        try:
            r, cms = repl.check(cmd, a.timeout)
            ok = not [m for m in r.get("messages", []) if m.get("severity") == "error"] and "message" not in r
        except ReplTimeout:
            ok, cms = False, a.timeout * 1000
            repl.kill()
            repl = LeanREPL(LEAN_HEADER)
            repl.start()
        flags[name] = ok
        line(f"  {name:14s} {'CHỨNG MINH ĐƯỢC' if ok else 'không chứng minh được':24s} {cms:7.1f} ms")
    h = heuristics(code, u)
    flags.update(h)
    line(f"  heuristic      {json.dumps(h, ensure_ascii=False)}")
    line(f"\n=> kết luận tự động: {verdict(flags, u)}"
         "   (cờ: VACUOUS / FALSE / TRIVIAL / ANSWER_MISSING / ARITHMETIC_ONLY; không có cờ chưa có nghĩa là đúng)")
    repl.close()


if __name__ == "__main__":
    main()
