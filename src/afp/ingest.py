"""Ingest raw datasets -> DataUnit JSONL + Parquet lake partitioned by source/domain.

Sources (all downloaded from GitHub, see scripts/download_data.sh):
  * ProofNet (Lean 4 port in deepseek-ai/DeepSeek-Prover-V1.5, 371 problems, gold statements)
    + original zhangir-azerbayev/ProofNet (to recover the textbook of each exercise)
  * miniF2F (Lean 4 port in deepseek-ai/DeepSeek-Prover-V1.5, 488 problems, gold statements)
  * MATH (openai/prm800k math_splits: 12,000 train + 500 test, every problem has an answer)
  * GSM8K (openai/grade-school-math: 7,473 train + 1,319 test, every problem has an answer)

Usage:  python -m afp.ingest --raw data/raw --out data
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import random
import re
from typing import Iterable

from .schema import DataUnit

CHARS_PER_TOKEN = 3.5   # rough estimate for English + LaTeX (no tokenizer available offline)

PROOFNET_BOOK_DOMAIN = {
    "Rudin": "real_analysis", "Pugh": "real_analysis", "Munkres": "topology",
    "Dummit-Foote": "abstract_algebra", "Herstein": "abstract_algebra", "Artin": "abstract_algebra",
    "Axler": "linear_algebra", "Ireland-Rosen": "number_theory", "Shakarchi": "complex_analysis",
    "Putnam": "competition",
}
MATH_SUBJECT_DOMAIN = {
    "Algebra": "algebra", "Intermediate Algebra": "intermediate_algebra", "Prealgebra": "prealgebra",
    "Number Theory": "number_theory", "Geometry": "geometry", "Precalculus": "precalculus",
    "Counting & Probability": "counting_probability",
}
LICENSES = {
    "proofnet": "MIT (ProofNet) + MIT (DeepSeek-Prover-V1.5 Lean 4 port)",
    "minif2f": "Apache-2.0 (miniF2F Lean) + MIT (DeepSeek-Prover-V1.5 Lean 4 port)",
    "math": "MIT (MATH, Hendrycks et al.; split from openai/prm800k)",
    "gsm8k": "MIT (openai/grade-school-math)",
}


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def _strip_doc_comment(s: str) -> str:
    s = s.strip()
    if s.startswith("/--"):
        s = s[3:]
    if s.endswith("-/"):
        s = s[:-2]
    return s.strip()


def est_tokens(text: str) -> int:
    return max(1, round(len(text) / CHARS_PER_TOKEN))


def _read_jsonl(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def minif2f_domain(name: str) -> tuple[str, str]:
    """(domain, difficulty) from the miniF2F problem name."""
    if name.startswith("mathd_algebra"):
        return "algebra", "MATH"
    if name.startswith("mathd_numbertheory"):
        return "number_theory", "MATH"
    if name.startswith("algebra_"):
        return "algebra", "custom"
    if name.startswith("numbertheory_"):
        return "number_theory", "custom"
    if name.startswith("induction_"):
        return "induction", "custom"
    for tier in ("amc12", "aime", "imo"):
        if name.startswith(tier):
            return "competition", tier.upper()
    return "competition", "custom"


def load_proofnet(raw: str) -> list[DataUnit]:
    ds = _read_jsonl(os.path.join(raw, "proofnet_ds.jsonl"))
    orig = []
    for split in ("test", "valid"):
        orig += _read_jsonl(os.path.join(raw, "proofnet_orig", "benchmark", f"{split}.jsonl"))
    # map (name, normalised NL) -> book; NL texts are identical between the two versions
    by_key = {}
    by_name = collections.defaultdict(list)
    for o in orig:
        book, name = o["id"].split("|", 1)
        by_key[(name, _norm(o["nl_statement"]))] = book
        by_name[name].append(book)
    units = []
    for r in ds:
        nl = _strip_doc_comment(r["informal_prefix"])
        book = by_key.get((r["name"], _norm(nl)))
        if book is None:                       # fall back to the name if unique
            books = by_name.get(r["name"], [])
            book = books[0] if len(books) == 1 else "unknown"
        pid = f"proofnet:{book}:{r['name']}"
        units.append(DataUnit(
            problem_id=pid, source="proofnet", natural_statement=nl,
            domain=PROOFNET_BOOK_DOMAIN.get(book, "unknown"),
            metadata={
                "split": r["split"], "book": book, "difficulty": "undergraduate",
                "answer": None, "has_answer": False,
                "gold_formal_statement": r["formal_statement"], "gold_header": r["header"],
                "length_chars": len(nl), "est_tokens": est_tokens(nl),
                "license": LICENSES["proofnet"], "origin": "deepseek-ai/DeepSeek-Prover-V1.5/datasets/proofnet.jsonl",
            }))
    return units


def load_minif2f(raw: str) -> list[DataUnit]:
    units = []
    for r in _read_jsonl(os.path.join(raw, "minif2f_ds.jsonl")):
        nl = _strip_doc_comment(r["informal_prefix"])
        domain, diff = minif2f_domain(r["name"])
        units.append(DataUnit(
            problem_id=f"minif2f:{r['split']}:{r['name']}", source="minif2f", natural_statement=nl,
            domain=domain,
            metadata={
                "split": r["split"], "difficulty": diff, "answer": None, "has_answer": False,
                "gold_formal_statement": r["formal_statement"], "gold_header": r["header"],
                "length_chars": len(nl), "est_tokens": est_tokens(nl),
                "license": LICENSES["minif2f"], "origin": "deepseek-ai/DeepSeek-Prover-V1.5/datasets/minif2f.jsonl",
            }))
    return units


def load_math(raw: str) -> list[DataUnit]:
    units = []
    for split in ("train", "test"):
        for r in _read_jsonl(os.path.join(raw, f"math_{split}.jsonl")):
            uid = r["unique_id"].removesuffix(".json")
            nl = f"{r['problem'].strip()}\nAnswer: {r['answer']}"
            units.append(DataUnit(
                problem_id=f"math:{uid}", source="math", natural_statement=nl,
                domain=MATH_SUBJECT_DOMAIN[r["subject"]],
                metadata={
                    "split": "prm800k_" + split, "difficulty": f"L{r['level']}",
                    "answer": r["answer"], "has_answer": True, "problem": r["problem"],
                    "gold_formal_statement": None, "gold_header": None,
                    "length_chars": len(nl), "est_tokens": est_tokens(nl),
                    "license": LICENSES["math"], "origin": "openai/prm800k/prm800k/math_splits",
                }))
    return units


def load_gsm8k(raw: str) -> list[DataUnit]:
    units = []
    for split in ("train", "test"):
        for i, r in enumerate(_read_jsonl(os.path.join(raw, f"gsm8k_{split}.jsonl"))):
            ans = r["answer"].split("####")[-1].strip().replace(",", "")
            nl = f"{r['question'].strip()}\nAnswer: {ans}"
            units.append(DataUnit(
                problem_id=f"gsm8k:{split}:{i:05d}", source="gsm8k", natural_statement=nl,
                domain="arithmetic_word_problem",
                metadata={
                    "split": split, "difficulty": "grade_school", "answer": ans, "has_answer": True,
                    "problem": r["question"].strip(),
                    "gold_formal_statement": None, "gold_header": None,
                    "length_chars": len(nl), "est_tokens": est_tokens(nl),
                    "license": LICENSES["gsm8k"], "origin": "openai/grade-school-math",
                }))
    return units


def stratified_sample(ids_by_stratum: dict[str, list[str]], quota: dict[str, int], rng: random.Random) -> list[str]:
    out = []
    for stratum, ids in sorted(ids_by_stratum.items()):
        k = quota.get(stratum, 0)
        ids = sorted(ids)
        out += rng.sample(ids, k) if k < len(ids) else ids
    return out


def make_tiers(units: list[DataUnit], seed: int = 42) -> dict[str, list[str]]:
    """Nested tiers T100 ⊂ T1K ⊂ T10K with (approximately) the same source mix."""
    rng = random.Random(seed)
    by_src = collections.defaultdict(list)
    for u in units:
        by_src[u.source].append(u.problem_id)
    t10k_quota = {"proofnet": 371, "minif2f": 488, "gsm8k": 1000}
    t10k_quota["math"] = 10_000 - sum(t10k_quota.values())
    t10k = stratified_sample(by_src, t10k_quota, rng)
    src_of = {u.problem_id: u.source for u in units}

    def shrink(ids: list[str], total: int) -> list[str]:
        g = collections.defaultdict(list)
        for i in ids:
            g[src_of[i]].append(i)
        n = len(ids)
        quota = {s: max(1, round(len(v) * total / n)) for s, v in g.items()}
        diff = total - sum(quota.values())
        quota[max(quota, key=quota.get)] += diff      # fix rounding on the largest stratum
        return stratified_sample(g, quota, rng)

    t1k = shrink(t10k, 1000)
    t100 = shrink(t1k, 100)
    assert set(t100) <= set(t1k) <= set(t10k)
    return {"T100": sorted(t100), "T1K": sorted(t1k), "T10K": sorted(t10k)}


def write_parquet_lake(units: Iterable[DataUnit], lake_dir: str) -> None:
    import pyarrow as pa
    import pyarrow.dataset as pads
    rows = []
    for u in units:
        m = u.metadata
        rows.append({
            "problem_id": u.problem_id, "source": u.source, "domain": u.domain,
            "natural_statement": u.natural_statement,
            "split": m.get("split"), "difficulty": m.get("difficulty"),
            "answer": m.get("answer"), "has_answer": bool(m.get("has_answer")),
            "gold_formal_statement": m.get("gold_formal_statement"),
            "length_chars": m.get("length_chars"), "est_tokens": m.get("est_tokens"),
            "license": m.get("license"),
        })
    table = pa.Table.from_pylist(rows)
    pads.write_dataset(table, lake_dir, format="parquet",
                       partitioning=pads.partitioning(pa.schema([("source", pa.string()), ("domain", pa.string())]), flavor="hive"),
                       existing_data_behavior="delete_matching")


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default="data/raw")
    ap.add_argument("--out", default="data")
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args(argv)
    raw_units = load_proofnet(a.raw) + load_minif2f(a.raw) + load_math(a.raw) + load_gsm8k(a.raw)
    # de-duplicate on problem_id (MATH train contains a few repeated unique_ids) - keep first
    seen, units, dropped = set(), [], []
    for u in raw_units:
        if u.problem_id in seen:
            dropped.append(u.problem_id)
            continue
        seen.add(u.problem_id)
        units.append(u)
    print(f"raw={len(raw_units)} dedup_dropped={len(dropped)} {dropped[:5]}")
    nl_dups = sum(c - 1 for c in collections.Counter(_norm(u.natural_statement) for u in units).values() if c > 1)
    print(f"exact duplicate natural statements (kept, flagged in data card): {nl_dups}")
    os.makedirs(os.path.join(a.out, "units"), exist_ok=True)
    with open(os.path.join(a.out, "units", "all_units.jsonl"), "w", encoding="utf-8") as f:
        for u in units:
            f.write(u.to_json() + "\n")
    tiers = make_tiers(units, a.seed)
    os.makedirs(os.path.join(a.out, "tiers"), exist_ok=True)
    for name, t in tiers.items():
        with open(os.path.join(a.out, "tiers", f"{name}.txt"), "w") as f:
            f.write("\n".join(t) + "\n")
    write_parquet_lake(units, os.path.join(a.out, "lake", "units"))
    c = collections.Counter((u.source, u.domain) for u in units)
    print(f"{len(units)} units written")
    for (s, d), n in sorted(c.items()):
        print(f"  {s:9s} {d:26s} {n}")
    unknown = [u.problem_id for u in units if u.domain == "unknown"]
    print("unknown domain:", len(unknown), unknown[:5])
    for name, t in tiers.items():
        print(name, len(t), collections.Counter(i.split(":")[0] for i in t))


if __name__ == "__main__":
    main()
