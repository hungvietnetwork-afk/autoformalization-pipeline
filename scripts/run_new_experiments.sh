#!/usr/bin/env bash
# Experiments added on 2026-10-26 to cover the course guide (group 5, sections 7-8):
# required baseline (one problem per request), batch size at fixed workers, retry budget, hardware check.
# Resumable: finished runs listed in results/raw/*_runs.csv are skipped.
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONPATH="$PWD/src${PYTHONPATH:+:$PYTHONPATH}"
if [ -z "${AFP_LEAN_ROOT:-}" ]; then
  if [ -d "$HOME/lean/mathlib4" ]; then AFP_LEAN_ROOT="$HOME/lean"; else AFP_LEAN_ROOT=/home/claude/lean; fi
fi
export AFP_LEAN_ROOT
test -x "$AFP_LEAN_ROOT/repl/.lake/build/bin/repl" || { echo "Lean REPL not found under $AFP_LEAN_ROOT (run scripts/setup_lean.sh)"; exit 1; }
log=results/raw/new_experiments_log.txt
step() { echo "== $(date -Is) $*" | tee -a "$log"; }
step baseline;  python -m afp.experiments baseline >> "$log" 2>&1
step semantic-baseline
python -m afp.semantic --run base_T20_1req_A --gold-run gold_check --workers 2 --timeout 10 >> "$log" 2>&1
python -m afp.semantic --run base_T20_batchjob_A --gold-run gold_check --workers 2 --timeout 10 >> "$log" 2>&1
step repro;     python -m afp.experiments repro >> "$log" 2>&1
step retry;     python -m afp.experiments retry >> "$log" 2>&1
step batch;     python -m afp.experiments batch >> "$log" 2>&1
step done
