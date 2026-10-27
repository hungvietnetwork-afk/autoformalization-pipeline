"""data/MANIFEST.json: what every data file is, where it came from, its licence, size and SHA-256.

The full datasets are not versioned in Git (guide: only legal samples, manifest, checksums and scripts); this
manifest lets anyone check that a re-download / re-ingest reproduces exactly the files used in the experiments.
It also (re)builds data_sample/ (the versioned 100-problem sample) from the full data.

  python scripts/make_manifest.py
"""
from __future__ import annotations

import glob
import hashlib
import json
import os
import sqlite3
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = lambda *p: os.path.join(ROOT, *p)  # noqa: E731

SOURCES = {
    "proofnet_ds.jsonl": ("https://raw.githubusercontent.com/deepseek-ai/DeepSeek-Prover-V1.5/main/datasets/proofnet.jsonl", "MIT"),
    "minif2f_ds.jsonl": ("https://raw.githubusercontent.com/deepseek-ai/DeepSeek-Prover-V1.5/main/datasets/minif2f.jsonl", "MIT / Apache-2.0"),
    "proofnet_orig": ("https://github.com/zhangir-azerbayev/ProofNet (git clone --depth 1)", "MIT"),
    "math_train.jsonl": ("https://media.githubusercontent.com/media/openai/prm800k/main/prm800k/math_splits/train.jsonl", "MIT"),
    "math_test.jsonl": ("https://media.githubusercontent.com/media/openai/prm800k/main/prm800k/math_splits/test.jsonl", "MIT"),
    "gsm8k_train.jsonl": ("https://raw.githubusercontent.com/openai/grade-school-math/master/grade_school_math/data/train.jsonl", "MIT"),
    "gsm8k_test.jsonl": ("https://raw.githubusercontent.com/openai/grade-school-math/master/grade_school_math/data/test.jsonl", "MIT"),
}


def sha(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def tree_sha(paths: list[str]) -> str:
    h = hashlib.sha256()
    for p in sorted(paths):
        h.update(os.path.relpath(p, ROOT).encode())
        h.update(sha(p).encode())
    return h.hexdigest()


def lines(path: str) -> int:
    with open(path, "rb") as f:
        return sum(1 for _ in f)


def entry(path: str, **kw) -> dict:
    e = {"path": os.path.relpath(path, ROOT), "bytes": os.path.getsize(path), "sha256": sha(path)}
    if path.endswith((".jsonl", ".txt", ".csv")):
        e["lines"] = lines(path)
    e.update(kw)
    return e


# problems used by docs/DEMO_SCRIPT.md that are not in T100 (their candidates are in data/candidates.db)
DEMO_IDS = ["gsm8k:train:02691", "gsm8k:train:04141", "math:test/algebra/2167"]


def build_sample() -> list[str]:
    """data_sample/: the 100 DataUnits of tier T100, their candidates and their corpus records, plus the demo problems."""
    os.makedirs(D("data_sample"), exist_ok=True)
    ids = [l.strip() for l in open(D("data/tiers/T100.txt")) if l.strip()]
    keep = set(ids)
    out = []
    with open(D("data/units/all_units.jsonl"), encoding="utf-8") as f, \
            open(D("data_sample/units_T100.jsonl"), "w", encoding="utf-8") as g:
        for line in f:
            if json.loads(line)["problem_id"] in keep:
                g.write(line)
    out.append(D("data_sample/units_T100.jsonl"))
    con = sqlite3.connect(D("data/candidates.db"))
    cols = ["task_hash", "problem_id", "prompt_version", "candidate_index", "model", "job_id", "prompt_tokens",
            "completion_tokens", "lean_code", "raw_output"]
    with open(D("data_sample/candidates_T100.jsonl"), "w", encoding="utf-8") as g:
        q = f"SELECT {', '.join(cols)} FROM candidates WHERE prompt_version != 'gold' ORDER BY problem_id, prompt_version, candidate_index"
        for row in con.execute(q):
            if row[1] in keep:
                g.write(json.dumps(dict(zip(cols, row)), ensure_ascii=False) + "\n")
    out.append(D("data_sample/candidates_T100.jsonl"))
    with open(D("data/formalized_corpus.jsonl"), encoding="utf-8") as f, \
            open(D("data_sample/corpus_T100.jsonl"), "w", encoding="utf-8") as g:
        for line in f:
            if json.loads(line)["problem_id"] in keep:
                g.write(line)
    out.append(D("data_sample/corpus_T100.jsonl"))
    demo = set(DEMO_IDS)
    with open(D("data/units/all_units.jsonl"), encoding="utf-8") as f, \
            open(D("data_sample/units_demo.jsonl"), "w", encoding="utf-8") as g:
        for line in f:
            if json.loads(line)["problem_id"] in demo:
                g.write(line)
    out.append(D("data_sample/units_demo.jsonl"))
    return out


def main() -> None:
    sample = build_sample() if os.path.exists(D("data/units/all_units.jsonl")) else \
        sorted(glob.glob(D("data_sample", "*.jsonl")))
    raw = []
    for name, (url, lic) in SOURCES.items():
        p = D("data/raw", name)
        if os.path.isdir(p):
            files = [f for f in glob.glob(os.path.join(p, "**", "*"), recursive=True) if os.path.isfile(f) and "/.git/" not in f]
            raw.append({"path": os.path.relpath(p, ROOT), "source": url, "license": lic, "files": len(files),
                        "tree_sha256": tree_sha(files)})
        elif os.path.exists(p):
            raw.append(entry(p, source=url, license=lic))
        else:
            raw.append({"path": os.path.relpath(p, ROOT), "source": url, "license": lic, "missing": True})
    lake = sorted(glob.glob(D("data/lake/units/**/*.parquet"), recursive=True))
    corpus_pq = sorted(glob.glob(D("data/lake/formalized/**/*.parquet"), recursive=True))
    jobs = sorted(f for f in glob.glob(D("data/jobs/**/*"), recursive=True) if os.path.isfile(f))
    con = sqlite3.connect(D("data/candidates.db"))
    by_version = dict(con.execute("SELECT prompt_version, count(*) FROM candidates GROUP BY 1").fetchall())
    man = {
        "generated": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "versioned_in_git": ["data/tiers/", "data/candidates.db", "data/jobs/", "data/formalized_corpus.jsonl",
                             "data/lake/formalized/", "data_sample/"],
        "rebuilt_by_scripts": {"data/raw/": "bash scripts/download_data.sh",
                               "data/units/ + data/lake/units/ + data/tiers/": "python -m afp.ingest (seed 42)"},
        "raw_downloads": raw,
        "units": entry(D("data/units/all_units.jsonl"), records=22150) if os.path.exists(D("data/units/all_units.jsonl")) else None,
        "lake_units_parquet": {"files": len(lake), "tree_sha256": tree_sha(lake) if lake else None,
                               "layout": "data/lake/units/source=<s>/domain=<d>/part-0.parquet"},
        "tiers": [entry(p, seed=42) for p in sorted(glob.glob(D("data/tiers/*.txt")))],
        "candidate_store": {**entry(D("data/candidates.db")), "candidates_by_prompt_version": by_version},
        "inference_jobs": {"files": len(jobs), "tree_sha256": tree_sha(jobs)},
        "formalized_corpus": entry(D("data/formalized_corpus.jsonl")),
        "formalized_corpus_parquet": {"files": len(corpus_pq), "tree_sha256": tree_sha(corpus_pq) if corpus_pq else None},
        "data_sample": [entry(p) for p in sample],
    }
    with open(D("data/MANIFEST.json"), "w", encoding="utf-8") as f:
        json.dump(man, f, indent=1, ensure_ascii=False)
    print("wrote data/MANIFEST.json;", len(sample), "sample files")


if __name__ == "__main__":
    main()
