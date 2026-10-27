#!/usr/bin/env bash
# Quick reproduction on the versioned sample: tests, one baseline-configuration run on tier T100
# (1 Lean worker, batch 1, 10 s; candidates come from data/candidates.db, no model call), then the quality table.
# Needs Lean (bash scripts/setup_lean.sh). About 5-8 minutes on 2 vCPU.
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONPATH="$PWD/src${PYTHONPATH:+:$PYTHONPATH}"
if [ -z "${AFP_LEAN_ROOT:-}" ]; then
  if [ -d "$HOME/lean/mathlib4" ]; then AFP_LEAN_ROOT="$HOME/lean"; else AFP_LEAN_ROOT=/home/claude/lean; fi
fi
export AFP_LEAN_ROOT
python -m pytest -q tests
python -m afp.pipeline --run-id quickstart_T100_A --tier T100 --workers 1 --batch 1 --timeout 10 \
  | python -c "import json,sys; m=json.load(sys.stdin); print({k: m[k] for k in ('n_candidates','compile_rate','throughput_problems_per_s','latency_ms_p95')})"
echo "raw logs: results/raw/runs/quickstart_T100_A/ (run_record.json = guide Appendix B)"
python -m afp.demo_one --problem gsm8k:train:04141
