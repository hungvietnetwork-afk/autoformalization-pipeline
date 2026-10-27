#!/usr/bin/env bash
export PYTHONPATH="$(cd "$(dirname "$0")/.." && pwd)/src${PYTHONPATH:+:$PYTHONPATH}"
# Scalability experiments only (resumable: finished runs listed in results/raw/*_runs.csv are skipped).
set -uo pipefail
cd "$(dirname "$0")/.."
log=results/raw/scalability_log.txt
echo "=== start $(date -u +%H:%M:%S)" >> "$log"
python3 -m afp.experiments matrix  >> "$log" 2>&1 && echo "=== matrix done $(date -u +%H:%M:%S)" >> "$log"
python3 -m afp.experiments scaling >> "$log" 2>&1 && echo "=== scaling done $(date -u +%H:%M:%S)" >> "$log"
python3 -m afp.experiments fault   >> "$log" 2>&1 && echo "=== fault done $(date -u +%H:%M:%S)" >> "$log"
python3 -m afp.experiments determinism >> "$log" 2>&1
python3 -m afp.experiments broker  >> "$log" 2>&1 && echo "=== broker done $(date -u +%H:%M:%S)" >> "$log"
echo "=== ALL DONE $(date -u +%H:%M:%S)" >> "$log"
