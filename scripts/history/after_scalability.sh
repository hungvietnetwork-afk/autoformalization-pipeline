#!/usr/bin/env bash
export PYTHONPATH="$(cd "$(dirname "$0")/.." && pwd)/src${PYTHONPATH:+:$PYTHONPATH}"
# Runs after the scalability experiments (they need the CPU to themselves and a fixed workload).
#  1) keep the sanitizer-v1 quality runs for comparison
#  2) re-apply the sanitizer (v2: a `let ... :=` inside a statement no longer marks the proof start) to the
#     stored raw model outputs -> 8 of 1,400 candidates change; no model call is repeated
#  3) quality runs again, analyses, semantic checks, curated corpus, mutation test
set -uo pipefail
cd "$(dirname "$0")/.."
log=results/raw/chain_log.txt
step() { echo "=== $1 $(date -u +%H:%M:%S)" >> "$log"; }

step "keep sanitizer-v1 quality runs"
for r in q_T1K_zeroshot q_T100_fewshot; do
  rm -rf "results/raw/runs/${r}_sanitizer_v1" && cp -r "results/raw/runs/$r" "results/raw/runs/${r}_sanitizer_v1"
done
cp results/figures/taxonomy_q_T1K_zeroshot.json results/figures/taxonomy_q_T1K_zeroshot_sanitizer_v1.json
cp results/figures/taxonomy_q_T100_fewshot.json results/figures/taxonomy_q_T100_fewshot_sanitizer_v1.json
cp results/figures/passk_vs_cost.csv results/figures/passk_vs_cost_sanitizer_v1.csv
cp results/figures/failure_causes_q_T1K_zeroshot.json results/figures/failure_causes_q_T1K_zeroshot_sanitizer_v1.json
cp results/figures/failure_causes_q_T100_fewshot.json results/figures/failure_causes_q_T100_fewshot_sanitizer_v1.json

step "re-import with sanitizer v2"
python3 -m afp.inference.batchfile import --jobs data/jobs/v1_zeroshot --model claude-haiku-5.5 >> "$log" 2>&1
python3 -m afp.inference.batchfile import --jobs data/jobs/v2_fewshot --model claude-haiku-5.5 >> "$log" 2>&1

step "quality runs (sanitizer v2)"
python3 -m afp.pipeline --run-id q_T1K_zeroshot --tier T1K --workers 2 --batch 8 > results/raw/q_T1K_zeroshot_metrics.txt 2>> "$log"
python3 -m afp.pipeline --run-id q_T100_fewshot --tier T100 --workers 2 --batch 8 --prompt-version v2_fewshot --k 4 \
  > results/raw/q_T100_fewshot_metrics.txt 2>> "$log"
python3 -m afp.analysis taxonomy --run results/raw/runs/q_T1K_zeroshot > /dev/null 2>> "$log"
python3 -m afp.analysis taxonomy --run results/raw/runs/q_T100_fewshot > /dev/null 2>> "$log"
python3 -m afp.analysis causes --run results/raw/runs/q_T1K_zeroshot > /dev/null 2>> "$log"
python3 -m afp.analysis causes --run results/raw/runs/q_T100_fewshot > /dev/null 2>> "$log"
python3 -m afp.analysis skew --run results/raw/runs/q_T1K_zeroshot > /dev/null 2>> "$log"
python3 -m afp.analysis passk --zero results/raw/runs/q_T1K_zeroshot --few results/raw/runs/q_T100_fewshot >> "$log" 2>&1

step "semantic T1K"
python3 -m afp.semantic --run results/raw/runs/q_T1K_zeroshot --gold-run results/raw/runs/gold_check --workers 2 --timeout 10 >> "$log" 2>&1
step "semantic T100 few-shot"
python3 -m afp.semantic --run results/raw/runs/q_T100_fewshot --gold-run results/raw/runs/gold_check --workers 2 --timeout 10 >> "$log" 2>&1
step "corpus"
python3 -m afp.analysis corpus --runs results/raw/runs/q_T1K_zeroshot results/raw/runs/q_T100_fewshot >> "$log" 2>&1
step "mutation"
python3 -m afp.mutation --n 100 --workers 2 >> results/raw/mutation_log.txt 2>&1
step "done"
