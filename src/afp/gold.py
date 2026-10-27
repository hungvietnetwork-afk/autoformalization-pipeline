"""Load the human-written ("gold") Lean 4 statements of ProofNet / miniF2F as candidates.

Uses: (1) validate the Lean/Mathlib environment (gold should compile), (2) reference for the
semantic-equivalence check of model candidates (afp.semantic).

  python -m afp.gold
"""
from __future__ import annotations

import os
import re

from .inference.batchfile import load_units
from .prompts import migrate_bigop, sanitize
from .schema import Candidate, task_hash
from .store import CandidateStore

from .paths import AUDIT, CANDIDATES_DB, RAW, ROOT, RUNS, TABLES, TIERS_DIR, UNITS, result_path, run_dir


def opens_of(header: str) -> str:
    """Keep the `open ...` lines of a dataset header (imports are already in the worker header)."""
    return "\n".join(l for l in (header or "").splitlines() if l.strip().startswith("open "))


def gold_code(unit, name: str) -> str:
    stmt = migrate_bigop(sanitize(unit.metadata["gold_formal_statement"], name))
    o = opens_of(unit.metadata.get("gold_header"))
    return (o + "\n" + stmt) if o else stmt


def main():
    units = load_units(UNITS)
    store = CandidateStore(CANDIDATES_DB)
    ids = []
    for pid, u in units.items():
        if u.metadata.get("gold_formal_statement"):
            th = task_hash(pid, "gold", 0)
            store.upsert(Candidate(th, pid, "gold", 0, gold_code(u, "gold_" + th[:12]), "human"), u.metadata["gold_formal_statement"], "gold")
            ids.append(pid)
    with open(os.path.join(TIERS_DIR, "GOLD.txt"), "w") as f:
        f.write("\n".join(sorted(ids)) + "\n")
    print(len(ids), "gold candidates")


if __name__ == "__main__":
    main()
