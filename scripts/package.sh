#!/usr/bin/env bash
# Build the hand-in archive: the repository with its Git history (code, configs, data sample and candidates, results,
# docs, report, slides link) and the raw logs of every run.
# Not included: the Lean toolchain/Mathlib (~10 GB, rebuilt by scripts/setup_lean.sh), the raw downloads and the full
# normalized dataset (scripts/download_data.sh && python -m afp.ingest; the archive keeps data_sample/), the per-run SQLite files (their content is in raw_results.* and run_record.json),
# debug runs, and the JSONL copy of raw results for the repeated scalability runs (the CSV holds the same rows,
# compiler messages cut at 300 characters).
set -euo pipefail
cd "$(dirname "$0")/.."
name=nhom5-autoformalization-pipeline
out=${1:-$(dirname "$PWD")/$name.zip}
rm -f "$out"
tmp=$(mktemp -d)
ln -s "$PWD" "$tmp/$name"
R="$name/results/raw/runs"
(cd "$tmp" && zip -qr "$out" "$name" -x "$name/data/raw" "$name/data/raw/*" "*/__pycache__/*" "*/.pytest_cache/*" \
     "$name/data/lake/units" "$name/data/lake/units/*" "$name/data/units" "$name/data/units/*" "*.zip" \
     "$R/*/run.db" "$R/*/run.db-*" "$R/debug_*" \
     "$R/mx_*/raw_results.jsonl" "$R/sc_*/raw_results.jsonl" "$R/fault_*/raw_results.jsonl" \
     "$R/broker_*/raw_results.jsonl" "$R/bs_*/raw_results.jsonl" "$R/rt_*/raw_results.jsonl" \
     "$R/ab_release_*/raw_results.jsonl" "$R/repro_*/raw_results.jsonl")
rm -rf "$tmp"
ls -la "$out"
