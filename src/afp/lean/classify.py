"""Map Lean messages to the status taxonomy of the design (PDF section 2 & 6).

Top-level statuses: COMPILE_OK | PARSE_ERROR | UNKNOWN_IDENTIFIER | TYPE_MISMATCH | TIMEOUT | OTHER_ERROR
The primary status is the kind of the *first* error (by position) - in Lean the first error is
usually the root cause, later ones are often consequences. All kinds are kept for the taxonomy.
"""
from __future__ import annotations

import re

from ..schema import (COMPILE_OK, OTHER_ERROR, PARSE_ERROR, TIMEOUT, TYPE_MISMATCH,
                      UNKNOWN_IDENTIFIER)

# (sub_kind, top_status, regex) - checked in order, case-insensitive
RULES = [
    ("deterministic_timeout", TIMEOUT, r"\(deterministic\) timeout|maximum recursion depth|heartbeats"),
    ("unknown_identifier", UNKNOWN_IDENTIFIER, r"unknown (identifier|constant|declaration)"),
    ("unknown_namespace", UNKNOWN_IDENTIFIER, r"unknown namespace|unknown universe"),
    ("invalid_field", UNKNOWN_IDENTIFIER, r"invalid field|does not have a field|is not a structure"),
    ("parse_error", PARSE_ERROR, r"^unexpected |expected term|expected '|expected command|unterminated|"
                                 r"invalid 'import'|missing end of|unexpected end of input"),
    ("type_mismatch", TYPE_MISMATCH, r"type mismatch|application type mismatch|has type .* but is expected"),
    ("failed_to_synthesize", TYPE_MISMATCH, r"failed to synthesize"),
    ("function_expected", TYPE_MISMATCH, r"function expected"),
    ("ambiguous", OTHER_ERROR, r"ambiguous, possible interpretations|ambiguous term"),
    ("placeholder", OTHER_ERROR, r"don't know how to synthesize|typeclass instance problem is stuck"),
    ("already_declared", OTHER_ERROR, r"has already been declared"),
]
_COMPILED = [(k, s, re.compile(p, re.I | re.M)) for k, s, p in RULES]


def kind_of(msg: str) -> tuple[str, str]:
    for k, status, rx in _COMPILED:
        if rx.search(msg):
            return k, status
    return "other_error", OTHER_ERROR


def classify(resp: dict) -> tuple[str, str, str, int]:
    """Return (status, error_kinds, compiler_message, n_warnings)."""
    if "message" in resp and "messages" not in resp:      # REPL-level error
        k, st = kind_of(resp["message"])
        return st, k, resp["message"], 0
    msgs = resp.get("messages", [])
    errs = [m for m in msgs if m.get("severity") == "error"]
    warns = [m for m in msgs if m.get("severity") == "warning"]
    if not errs:
        # safety net: a real declaration elaborated with `sorry` always reports a sorry warning/goal
        if not resp.get("sorries") and not any("sorry" in m.get("data", "") for m in warns):
            return OTHER_ERROR, "no_declaration", "no declaration was elaborated", len(warns)
        return COMPILE_OK, "", "\n".join(m.get("data", "") for m in warns)[:2000], len(warns)
    errs.sort(key=lambda m: (m.get("pos", {}).get("line", 0), m.get("pos", {}).get("column", 0)))
    kinds = [kind_of(m.get("data", "")) for m in errs]
    status = kinds[0][1]
    text = "\n---\n".join(m.get("data", "") for m in errs)[:4000]
    return status, ";".join(k for k, _ in kinds), text, len(warns)
