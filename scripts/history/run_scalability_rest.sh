#!/usr/bin/env bash
export PYTHONPATH="$(cd "$(dirname "$0")/.." && pwd)/src${PYTHONPATH:+:$PYTHONPATH}"
# Second half of the scalability block (after the matrix): fault injection, determinism, broker comparison,
# queue micro-benchmark. Each step is short; the worker curve (`afp.experiments scaling`) runs before this.
set -uo pipefail
cd "$(dirname "$0")/.."
log=results/raw/scalability_log.txt
step() { echo "=== $1 $(date -u +%H:%M:%S)" >> "$log"; }
step "fault start";        python3 -m afp.experiments fault       >> "$log" 2>&1
step "determinism start";  python3 -m afp.experiments determinism >> "$log" 2>&1
step "broker start";       python3 -m afp.experiments broker      >> "$log" 2>&1
step "bench_queue start";  python3 -m afp.bench_queue             >> "$log" 2>&1
python3 -m afp.analysis budget --prefix mx_T10K_ --out time_budget_T10K.json > /dev/null 2>> "$log"
python3 -m afp.analysis budget --prefix sc_T10K_ --out time_budget_scaling.json > /dev/null 2>> "$log"
step "rest done"
