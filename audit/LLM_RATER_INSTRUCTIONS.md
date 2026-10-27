# Instructions for an (LLM) annotator – semantic audit of autoformalization

You are an expert in Lean 4 / Mathlib and in competition and undergraduate mathematics, acting as one
INDEPENDENT annotator in a semantic audit. Every item contains:

* `[PROBLEM]` – the natural-language problem. For problems with a final answer, the line `Answer: ...` is
  part of the problem: a faithful formal statement must assert this answer for the quantity asked.
* `[LEAN]` – a candidate Lean 4 statement (Mathlib, 2026). It already COMPILES; the proof is `sorry`.
  The header `open BigOperators Real Nat Topology Rat` is in effect.
* optionally `[REFERENCE]` – a human-written statement for an older Mathlib (only a hint; it may differ in
  notation and is not necessarily the only correct formalization).

Label each item with exactly one of:

* `DUNG` – faithful: every hypothesis and the exact conclusion of the problem are captured, with correct
  types; for answer problems the statement asserts the given answer for the asked quantity.
* `GAN_DUNG` – the mathematical content is kept but with a minor deviation (a harmless extra/missing side
  condition, a slightly different but equivalent phrasing, ℕ instead of ℤ when all values are positive).
* `SAI` – wrong meaning: missing important hypotheses or contradictory hypotheses, a different / weaker /
  trivial conclusion, the problem reduced to a bare arithmetic identity that no longer models the question,
  a wrong answer or the answer asserted for the wrong quantity, or a type that changes the meaning
  (truncating ℕ subtraction/division, integer division).

Rule fixed after the pilot (v2 of this guide): a statement that only restates the computation of the solution
(e.g. `14 - (2 + 4) = 8`), with no variable or hypothesis standing for the quantities of the problem, is `SAI`
even when the numbers follow the story: its truth then depends on the formalizer having solved the problem.
The two pilot LLM raters labelled the 100 items with v1 of the guide, which did not spell this out.

Write a CSV file with header `audit_id,label,reason` (reason ≤ 20 words, no commas inside the reason),
one row per item, in the order of the items. Judge each item on its own.
