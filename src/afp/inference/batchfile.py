"""Offline batch-job inference backend (same pattern as provider Batch APIs).

export : partition the problems with hash(problem_id) mod R and write one job file per
         (prompt_version, sample_index, partition) + a manifest that maps short ids to TaskHash.
run    : an external batch worker (any LLM) reads the job file and writes `<job>.out.txt`
         in the format   ### P001 \n <lean statement> \n ### P002 ...
import : parse outputs, sanitise, and UPSERT into the candidate cache keyed by TaskHash.

Usage:
  python -m afp.inference.batchfile export --tier data/tiers/T1K.txt --version v1_zeroshot --k 1 --partitions 8
  python -m afp.inference.batchfile import --jobs data/jobs/v1_zeroshot --model claude-haiku
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re

from ..prompts import PROMPT_VERSIONS, sanitize, system_prompt, user_prompt
from ..schema import Candidate, DataUnit, partition_index, task_hash
from ..ingest import est_tokens
from ..store import CandidateStore


def load_units(path: str = "data/units/all_units.jsonl") -> dict[str, DataUnit]:
    with open(path, encoding="utf-8") as f:
        return {u.problem_id: u for u in (DataUnit.from_dict(json.loads(l)) for l in f)}


def read_tier(path: str) -> list[str]:
    with open(path) as f:
        return [l.strip() for l in f if l.strip()]


def export_jobs(problem_ids: list[str], units: dict[str, DataUnit], version: str, k: int,
                partitions: int, out_dir: str) -> list[str]:
    jobs = []
    sys_prompt = system_prompt(version)
    for s in range(k):
        groups: dict[int, list[str]] = {}
        for pid in problem_ids:
            groups.setdefault(partition_index(pid, partitions), []).append(pid)
        for p, pids in sorted(groups.items()):
            job_id = f"{version}_s{s}_p{p:02d}"
            d = os.path.join(out_dir, version)
            os.makedirs(d, exist_ok=True)
            manifest, body = [], []
            for j, pid in enumerate(sorted(pids), 1):
                key = f"P{j:03d}"
                th = task_hash(pid, version, s)
                manifest.append({"key": key, "task_hash": th, "problem_id": pid, "candidate_index": s,
                                 "prompt_tokens": est_tokens(sys_prompt + user_prompt(units[pid].natural_statement))})
                body.append(f"### {key}\n{units[pid].natural_statement.strip()}\n")
            with open(os.path.join(d, f"{job_id}.txt"), "w", encoding="utf-8") as f:
                f.write("\n".join(body))
            with open(os.path.join(d, f"{job_id}.manifest.json"), "w", encoding="utf-8") as f:
                json.dump({"job_id": job_id, "prompt_version": version, "sample_index": s, "partition": p,
                           "system_prompt": sys_prompt, "tasks": manifest}, f, ensure_ascii=False, indent=1)
            jobs.append(job_id)
    with open(os.path.join(out_dir, version, "SYSTEM_PROMPT.txt"), "w", encoding="utf-8") as f:
        f.write(sys_prompt)
    return jobs


_SECTION = re.compile(r"^###\s*(P\d{3})\s*$", re.M)


def parse_output(text: str) -> dict[str, str]:
    parts = _SECTION.split(text)
    out = {}
    for i in range(1, len(parts) - 1, 2):
        out[parts[i]] = parts[i + 1].strip()
    return out


def import_jobs(job_dir: str, model: str, store: CandidateStore) -> dict:
    stats = {"jobs": 0, "tasks": 0, "answered": 0, "empty_after_sanitize": 0, "missing_output_files": []}
    for mpath in sorted(glob.glob(os.path.join(job_dir, "*.manifest.json"))):
        man = json.load(open(mpath, encoding="utf-8"))
        opath = mpath.replace(".manifest.json", ".out.txt")
        outs = ([opath] if os.path.exists(opath) else []) + sorted(glob.glob(mpath.replace(".manifest.json", "__r*.out.txt")))
        if not outs:
            stats["missing_output_files"].append(os.path.basename(opath))
            continue
        answers = {}
        for op in reversed(outs):           # main file wins over resume chunks
            answers.update({k: v for k, v in parse_output(open(op, encoding="utf-8").read()).items() if v})
        stats["jobs"] += 1
        for t in man["tasks"]:
            stats["tasks"] += 1
            raw = answers.get(t["key"], "")
            if raw:
                stats["answered"] += 1
            lean = sanitize(raw, "cand_" + t["task_hash"][:12]) if raw else ""
            if raw and not lean:
                stats["empty_after_sanitize"] += 1
            c = Candidate(task_hash=t["task_hash"], problem_id=t["problem_id"],
                          prompt_version=man["prompt_version"], candidate_index=t["candidate_index"],
                          lean_code=lean, model=model, prompt_tokens=t["prompt_tokens"],
                          completion_tokens=est_tokens(raw) if raw else 0)
            store.upsert(c, raw, man["job_id"])
    return stats


def resume_jobs(job_dir: str, chunk: int = 25, only: list[str] | None = None) -> list[str]:
    """Write sub-jobs for the keys a job has not answered yet (e.g. after the worker hit its output limit)."""
    made = []
    for mpath in sorted(glob.glob(os.path.join(job_dir, "*.manifest.json"))):
        man = json.load(open(mpath, encoding="utf-8"))
        if only and man["job_id"] not in only:
            continue
        base = mpath.replace(".manifest.json", "")
        done = {}
        for op in [base + ".out.txt"] + sorted(glob.glob(base + "__r*.out.txt")):
            if os.path.exists(op):
                done.update({k: v for k, v in parse_output(open(op, encoding="utf-8").read()).items() if v})
        body = open(base + ".txt", encoding="utf-8").read()
        sections = {k: v for k, v in zip(_SECTION.findall(body), _SECTION.split(body)[2::2])}
        missing = [t["key"] for t in man["tasks"] if t["key"] not in done]
        if not missing:
            continue
        existing = len(glob.glob(base + "__r*.txt")) - len(glob.glob(base + "__r*.out.txt"))
        start = len(glob.glob(base + "__r*.out.txt")) + max(0, existing)
        for i in range(0, len(missing), chunk):
            sub = f"{base}__r{start + i // chunk:02d}.txt"
            with open(sub, "w", encoding="utf-8") as f:
                f.write("\n".join(f"### {k}\n{sections[k].strip()}\n" for k in missing[i:i + chunk]))
            made.append(sub)
    return made


def main(argv=None):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("export")
    e.add_argument("--tier", required=True)
    e.add_argument("--version", required=True, choices=list(PROMPT_VERSIONS))
    e.add_argument("--k", type=int, default=None)
    e.add_argument("--partitions", type=int, default=8)
    e.add_argument("--out", default="data/jobs")
    e.add_argument("--units", default="data/units/all_units.jsonl")
    r = sub.add_parser("resume")
    r.add_argument("--jobs", required=True)
    r.add_argument("--chunk", type=int, default=25)
    r.add_argument("--only", nargs="*")
    i = sub.add_parser("import")
    i.add_argument("--jobs", required=True)
    i.add_argument("--model", required=True)
    i.add_argument("--db", default="data/candidates.db")
    a = ap.parse_args(argv)
    if a.cmd == "resume":
        for m in resume_jobs(a.jobs, a.chunk, a.only):
            print(m)
        return
    if a.cmd == "export":
        units = load_units(a.units)
        k = a.k or PROMPT_VERSIONS[a.version]["k"]
        jobs = export_jobs(read_tier(a.tier), units, a.version, k, a.partitions, a.out)
        print(f"{len(jobs)} job files written to {a.out}/{a.version}")
    else:
        print(json.dumps(import_jobs(a.jobs, a.model, CandidateStore(a.db)), indent=1))


if __name__ == "__main__":
    main()
