"""Integration tests that need Lean + Mathlib (skipped otherwise).  python -m pytest -q tests -m lean"""
import os

import pytest

from afp.lean.repl import LeanREPL, ReplTimeout
from afp.lean.classify import classify
from afp.prompts import LEAN_HEADER, FEW_SHOT_EXAMPLES

ROOT = os.environ.get("AFP_LEAN_ROOT", "/home/claude/lean")
pytestmark = pytest.mark.skipif(not os.path.exists(os.path.join(ROOT, "repl/.lake/build/bin/repl")),
                                reason="Lean REPL not installed")


@pytest.fixture(scope="module")
def repl():
    r = LeanREPL(LEAN_HEADER, lean_root=ROOT)
    r.start()
    yield r
    r.close()


def test_few_shot_examples_compile(repl):
    for _, lean in FEW_SHOT_EXAMPLES:
        resp, _ = repl.check(lean)
        assert classify(resp)[0] == "COMPILE_OK", lean


@pytest.mark.parametrize("code,status", [
    ("theorem a : (1 : ℕ) = := by sorry", "PARSE_ERROR"),
    ("theorem b : Nat.foo_bar 3 = 2 := by sorry", "UNKNOWN_IDENTIFIER"),
    ("theorem c (x : ℝ) : x + (\"a\" : String) = 1 := by sorry", "TYPE_MISMATCH"),
    ("open Real in\ntheorem d : (2 : ℝ) ≤ 3 := by sorry", "COMPILE_OK"),
    ("open Nat", "OTHER_ERROR"),            # no declaration -> must not count as COMPILE_OK
])
def test_classification(repl, code, status):
    resp, _ = repl.check(code)
    assert classify(resp)[0] == status


def test_hard_timeout_and_restart(repl):
    slow = ("set_option maxHeartbeats 0 in\nset_option maxRecDepth 100000 in\n"
            "theorem s : (by decide : ∀ n < 200000, n * n ≠ 2) = (by decide : ∀ n < 200000, n * n ≠ 2) := by sorry")
    with pytest.raises(ReplTimeout):
        repl.check(slow, timeout=5)
    repl.restart()
    resp, _ = repl.check("theorem ok (x : ℝ) (h : 2 * x = 6) : x = 3 := by sorry")
    assert classify(resp)[0] == "COMPILE_OK"
