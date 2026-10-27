#!/usr/bin/env bash
# Steps that run once every LLM batch job has answered: import, quality runs, analysis, audit sample.
set -euo pipefail
export PYTHONPATH="$(cd "$(dirname "$0")/.." && pwd)/src${PYTHONPATH:+:$PYTHONPATH}"
cd "$(dirname "$0")/.."
python3 -m afp.inference.batchfile import --jobs data/jobs/v1_zeroshot --model claude-haiku-5.5
python3 -m afp.inference.batchfile import --jobs data/jobs/v2_fewshot --model claude-haiku-5.5
python3 -m afp.pipeline --run-id q_T1K_zeroshot --tier T1K --workers 2 --batch 8 > results/raw/q_T1K_zeroshot_metrics.txt
python3 -m afp.analysis taxonomy --run results/raw/runs/q_T1K_zeroshot > /dev/null
python3 -m afp.analysis skew --run results/raw/runs/q_T1K_zeroshot > /dev/null
python3 -m afp.analysis passk --zero results/raw/runs/q_T1K_zeroshot --few results/raw/runs/q_T100_fewshot
python3 -m afp.audit sample --run results/raw/runs/q_T1K_zeroshot
