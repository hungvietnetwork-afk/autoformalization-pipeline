#!/usr/bin/env bash
# Re-run every experiment of the report, in the order used for the report
# (after the candidates are in data/candidates.db: see README, "Sinh ứng viên").
# The scalability block needs the CPU to itself; on a machine with a 2 h limit per command, run its lines one by one
# (every experiment is resumable: finished runs listed in results/raw/*_runs.csv are skipped).
set -euo pipefail
export PYTHONPATH="$(cd "$(dirname "$0")/.." && pwd)/src${PYTHONPATH:+:$PYTHONPATH}"
cd "$(dirname "$0")/.."
step() { echo; echo "=== $* ($(date -u +%H:%M:%S))"; }

step "gold statements (environment check)"
python -m afp.gold
python -m afp.pipeline --run-id gold_check --tier GOLD --workers 2 --batch 8 --prompt-version gold > /dev/null

step "quality runs: T1K zero-shot (baseline) and T100 few-shot k=4"
python -m afp.pipeline --run-id q_T1K_zeroshot --tier T1K --workers 2 --batch 8 > results/raw/q_T1K_zeroshot_metrics.txt
python -m afp.pipeline --run-id q_T100_fewshot --tier T100 --workers 2 --batch 8 --prompt-version v2_fewshot --k 4 \
  > results/raw/q_T100_fewshot_metrics.txt

step "analysis: taxonomy, root causes, skew, Pass@k vs tokens"
for r in q_T1K_zeroshot q_T100_fewshot; do
  python -m afp.analysis taxonomy --run results/raw/runs/$r > /dev/null
  python -m afp.analysis causes --run results/raw/runs/$r > /dev/null
done
python -m afp.analysis skew --run results/raw/runs/q_T1K_zeroshot > /dev/null
python -m afp.analysis passk --zero results/raw/runs/q_T1K_zeroshot --few results/raw/runs/q_T100_fewshot

step "scalability: matrix 3 tiers x 3 configs x 3 repeats, worker curve, faults, determinism, broker"
python -m afp.experiments matrix
python -m afp.experiments scaling
python -m afp.experiments fault
python -m afp.experiments determinism
python -m afp.experiments broker          # needs Redis at redis://localhost:6390/0

step "semantic checks, curated corpus, mutation test"
python -m afp.semantic --run results/raw/runs/q_T1K_zeroshot --gold-run results/raw/runs/gold_check
python -m afp.semantic --run results/raw/runs/q_T100_fewshot --gold-run results/raw/runs/gold_check
python -m afp.analysis corpus --runs results/raw/runs/q_T1K_zeroshot results/raw/runs/q_T100_fewshot
python -m afp.mutation --n 100 --workers 2

step "audit: fixed sample (seed 7); sheets that already hold labels are never overwritten"
python -m afp.audit sample --run results/raw/runs/q_T1K_zeroshot
if python - <<'EOF'
import sys
from afp.audit import _read_labels
sys.exit(0 if _read_labels("audit/rater1.xlsx") and _read_labels("audit/rater2.xlsx") else 1)
EOF
then
  python -m afp.audit kappa --a audit/rater1.xlsx --b audit/rater2.xlsx --out results/figures/audit_kappa_human.json
  python -m afp.audit compare --rater audit/rater1.xlsx --sem results/raw/runs/q_T1K_zeroshot/semantic.jsonl \
    --out results/figures/audit_auto_vs_rater1.json
else
  echo "human audit sheets not filled yet: audit/rater1.xlsx, audit/rater2.xlsx"
fi

step "experiments added for the course guide (26-27/10): baseline, batch size, retry budget, release ablation, hardware check"
python -m afp.experiments baseline        # zero-shot, one problem per request, 1 candidate, 1 worker, no repair (T20)
python -m afp.semantic --run results/raw/runs/base_T20_1req_A --gold-run results/raw/runs/gold_check --workers 2 --timeout 10
python -m afp.semantic --run results/raw/runs/base_T20_batchjob_A --gold-run results/raw/runs/gold_check --workers 2 --timeout 10
python -m afp.experiments repro           # matrix cell T1K/A, 3 times, on the current machine
python -m afp.experiments retry           # worker kill with max_attempts 1 vs 3
python -m afp.experiments release         # release the rest of a batch before a REPL restart: on vs off
python -m afp.experiments batch           # batch size 1/8/32 (+ indexed queue) at 2 workers, 3 tiers, 3 repeats

step "study tables: inference batching, candidates, quality, semantic layers, baseline, ablation, run manifest"
python -m afp.study all

step "figures"
python -m afp.plots
