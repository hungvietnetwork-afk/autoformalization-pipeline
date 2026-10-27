"""Build demo/explorer.html: a self-contained browser for the formalized T1K corpus.

    python scripts/build_explorer.py results/raw/runs/q_T1K_zeroshot
"""
from __future__ import annotations

import collections
import json
import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def records(run_dir: str) -> list[dict]:
    units = {}
    for line in open(os.path.join(ROOT, "data/units/all_units.jsonl"), encoding="utf-8"):
        u = json.loads(line)
        units[u["problem_id"]] = u
    cand = sqlite3.connect(os.path.join(ROOT, "data/candidates.db"))
    code = dict(cand.execute("SELECT task_hash, lean_code FROM candidates"))
    sem = {}
    sp = os.path.join(run_dir, "semantic.jsonl")
    if os.path.exists(sp):
        for line in open(sp, encoding="utf-8"):
            d = json.loads(line)
            sem[d["task_hash"]] = d.get("verdict", "")
    aud = {}
    key = os.path.join(ROOT, "audit/audit_key.csv")
    if os.path.exists(key):
        import csv
        labs = {}
        for r_ in ("A", "B"):
            p = os.path.join(ROOT, f"audit/llm_rater_{r_}.csv")
            if os.path.exists(p):
                labs[r_] = {x["audit_id"]: x["label"] for x in csv.DictReader(open(p, encoding="utf-8"))}
        for x in csv.DictReader(open(key, encoding="utf-8")):
            if labs:
                aud[x["task_hash"]] = {"id": x["audit_id"], "a": labs.get("A", {}).get(x["audit_id"], ""),
                                       "b": labs.get("B", {}).get(x["audit_id"], "")}
    out = []
    for line in open(os.path.join(run_dir, "raw_results.jsonl"), encoding="utf-8"):
        r = json.loads(line)
        u = units[r["problem_id"]]
        msg = (r["compiler_message"] or "") if r["status"] != "COMPILE_OK" else ""
        out.append({"id": r["problem_id"], "src": u["source"], "dom": u["domain"],
                    "diff": u["metadata"].get("difficulty") or "", "nl": u["natural_statement"],
                    "lean": code.get(r["task_hash"], ""), "st": r["status"], "ms": round(r["latency_ms"], 1),
                    "msg": msg[:400], "sem": sem.get(r["task_hash"], ""), "aud": aud.get(r["task_hash"])})
    out.sort(key=lambda x: (x["src"], x["id"]))
    return out


TEMPLATE = open(os.path.join(ROOT, "scripts", "explorer_template.html"), encoding="utf-8").read()

if __name__ == "__main__":
    run = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "results/raw/runs/q_T1K_zeroshot")
    recs = records(run)
    os.makedirs(os.path.join(ROOT, "demo"), exist_ok=True)
    data = json.dumps(recs, ensure_ascii=False).replace("</", "<\\/")
    html = TEMPLATE.replace("/*__DATA__*/[]", data)
    open(os.path.join(ROOT, "demo/explorer.html"), "w", encoding="utf-8").write(html)
    c = collections.Counter(r["st"] for r in recs)
    print(len(recs), "records", dict(c), f"{len(html) / 1e6:.2f} MB")
