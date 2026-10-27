"""Prompt versions + output sanitiser.

prompt_version is part of TaskHash, so changing a prompt creates new tasks instead of
silently overwriting old results (reproducibility).
"""
from __future__ import annotations

import re

# Header prepended once per Lean worker (warm REPL environment 0).
LEAN_HEADER = """import Mathlib
import Aesop
set_option maxHeartbeats 400000
open BigOperators Real Nat Topology Rat
"""

_INSTRUCTIONS = """You are an autoformalization system. Translate the natural-language mathematical statement into ONE Lean 4 theorem statement that uses Mathlib (Lean v4.35, Mathlib 2026).
The following header is already in place (do not repeat it):
""" + LEAN_HEADER + """
Requirements:
- Output only the theorem, in the form `theorem <name> <binders> : <proposition> := by sorry`.
- No proof, no comments, no imports, no markdown.
- If the problem ends with "Answer: ...", the theorem must assert that this answer is correct
  (e.g. the requested quantity equals the answer, or the solution set equals the given set).
- Keep every hypothesis and the exact conclusion of the original statement; do not simplify or weaken it.
"""

FEW_SHOT_EXAMPLES = [
    ("What is the sum of all real solutions of $x^2-5x+6=0$?\nAnswer: 5",
     "theorem ex1 (S : Finset ℝ) (hS : ∀ x : ℝ, x ∈ S ↔ x ^ 2 - 5 * x + 6 = 0) :\n    ∑ x ∈ S, x = 5 := by sorry"),
    ("How many positive divisors does $36$ have?\nAnswer: 9",
     "theorem ex2 : (Nat.divisors 36).card = 9 := by sorry"),
    ("A shop sells pens at $3 each. Tom buys 7 pens and pays with a $50 bill. How much change does he get?\nAnswer: 29",
     "theorem ex3 (price n paid change : ℕ) (h₀ : price = 3) (h₁ : n = 7) (h₂ : paid = 50)\n    (h₃ : change = paid - price * n) : change = 29 := by sorry"),
    ("Find the real number $x$ such that $2^{x+1}=32$.\nAnswer: 4",
     "theorem ex4 (x : ℝ) (h : (2 : ℝ) ^ (x + 1) = 32) : x = 4 := by sorry"),
    ("Prove that if every element $g$ of a group $G$ satisfies $g^2=1$, then $G$ is abelian.",
     "theorem ex5 {G : Type*} [Group G] (h : ∀ g : G, g ^ 2 = 1) :\n    ∀ a b : G, a * b = b * a := by sorry"),
    ("Let $f:\\mathbb{R}\\to\\mathbb{R}$ be continuous and satisfy $f(x)=f(x+1)$ for all $x$. Prove that $f$ is bounded.",
     "theorem ex6 (f : ℝ → ℝ) (hf : Continuous f) (hp : ∀ x, f x = f (x + 1)) :\n    ∃ M, ∀ x, |f x| ≤ M := by sorry"),
]

PROMPT_VERSIONS = {
    # Zero-shot, one sample per problem, generated as batch jobs (9-142 problems per job request)
    "v1_zeroshot": {"few_shot": 0, "k": 1, "problems_per_request": "batch job"},
    # Required baseline (guide, group 5, section 7): same prompt text as v1_zeroshot, but ONE problem per
    # request, one candidate, no repair. A separate version id so its TaskHashes never overwrite v1_zeroshot.
    "v1_zeroshot_1req": {"few_shot": 0, "k": 1, "problems_per_request": 1},
    # Improved: 6 hand-written examples (none taken from the evaluation data), k samples
    "v2_fewshot": {"few_shot": len(FEW_SHOT_EXAMPLES), "k": 4, "problems_per_request": "batch job"},
}


def system_prompt(version: str) -> str:
    spec = PROMPT_VERSIONS[version]
    if spec["few_shot"] == 0:
        return _INSTRUCTIONS
    shots = "\n\n".join(f"Problem:\n{nl}\nLean:\n{lean}" for nl, lean in FEW_SHOT_EXAMPLES[: spec["few_shot"]])
    return _INSTRUCTIONS + "\nExamples:\n\n" + shots + "\n"


def user_prompt(natural_statement: str) -> str:
    return f"Problem:\n{natural_statement}\nLean:"


# ---------------------------------------------------------------- sanitiser
_FENCE = re.compile(r"```(?:lean4?|Lean4?)?\s*\n(.*?)```", re.S)
_DECL = re.compile(r"^\s*(?:@\[[^\]]*\]\s*)?(?:private\s+|protected\s+)?(?:noncomputable\s+)?(theorem|lemma|example|def|abbrev)\b", re.M)
_OPENERS, _CLOSERS = "([{⟨⦃", ")]}⟩⦄"


_LET = re.compile(r"(let|letI|have|haveI)(?![\w'])")


def _cut_proof(stmt: str) -> str:
    """Replace whatever follows the top-level ':=' of the declaration with 'by sorry'.

    A top-level `let x : T := v;` (also letI/have/haveI) inside the statement owns the next top-level ':=';
    sanitizer v1 cut there, which broke 7 of the 1,000 zero-shot statements (found by the error taxonomy)."""
    depth, pending_let, i = 0, 0, 0
    while i < len(stmt):
        ch = stmt[i]
        if ch in _OPENERS:
            depth += 1
        elif ch in _CLOSERS:
            depth = max(0, depth - 1)
        elif depth == 0:
            m = _LET.match(stmt, i)
            if m and (i == 0 or not (stmt[i - 1].isalnum() or stmt[i - 1] in "_.'")):
                pending_let += 1
                i = m.end()
                continue
            if stmt.startswith(":=", i):
                if pending_let:
                    pending_let -= 1
                    i += 2
                    continue
                return stmt[:i].rstrip() + " := by sorry"
        i += 1
    return stmt.rstrip() + " := by sorry"


def sanitize(raw: str, new_name: str) -> str:
    """Deterministic post-processing of a model answer.

    * keep the content of the first ```lean fence if present
    * drop `import` lines (the header is fixed), keep `open`/`variable` lines
    * keep the first theorem/lemma declaration, rename it (avoids clashes with Mathlib names)
    * force the proof to be `by sorry` (we verify statements, not proofs)
    Returns "" if no declaration is found (-> EMPTY_OUTPUT).
    """
    text = raw.strip()
    m = _FENCE.search(text)
    if m:
        text = m.group(1)
    lines = [ln for ln in text.splitlines() if not ln.strip().startswith("import ")]
    text = "\n".join(lines)
    m = _DECL.search(text)
    if not m:
        return ""
    prefix = "\n".join(ln for ln in text[: m.start()].splitlines()
                       if ln.strip().startswith(("open ", "variable", "noncomputable", "namespace", "section")))
    decl = text[m.start():]
    # stop at the next top-level declaration, if the model produced several
    nxt = _DECL.search(decl, pos=1)
    if nxt:
        decl = decl[: nxt.start()]
    kw = m.group(1)
    if kw == "example":
        decl = re.sub(r"^\s*example", f"theorem {new_name}", decl, count=1)
    elif kw in ("def", "abbrev"):   # data-valued statements, e.g. `def foo : CommRing R` (ProofNet uses a few)
        decl = re.sub(r"^\s*(?:@\[[^\]]*\]\s*)?(?:private\s+|protected\s+)?(?:noncomputable\s+)?(?:def|abbrev)\s+[^\s:({\[⦃]+",
                      f"noncomputable def {new_name}", decl, count=1)
    else:
        decl = re.sub(r"^\s*(?:@\[[^\]]*\]\s*)?(?:private\s+|protected\s+)?(theorem|lemma)\s+[^\s:({\[⦃]+",
                      f"theorem {new_name}", decl, count=1)
    decl = _cut_proof(decl.strip())
    return (prefix + "\n" + decl).strip() if prefix else decl


# ---------------------------------------------------------------- library-drift repair
_BIGOP_IN = re.compile(r"([∑∏]\s*[^,∑∏]*?)\s+in\s+")


def migrate_bigop(code: str) -> str:
    """`∑ x in s, f x` (deprecated, removed from Mathlib in 2025) -> `∑ x ∈ s, f x`."""
    return _BIGOP_IN.sub(lambda m: m.group(1) + " ∈ ", code)
