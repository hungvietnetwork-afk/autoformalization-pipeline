#!/usr/bin/env bash
# Download the raw datasets (all from GitHub) into data/raw.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p data/raw && cd data/raw
get() { curl -sSL --fail -o "$2" "$1" && echo "ok $2 ($(wc -l < "$2") lines)"; }
# ProofNet + miniF2F, Lean 4 ports (DeepSeek-Prover-V1.5, MIT)
get https://raw.githubusercontent.com/deepseek-ai/DeepSeek-Prover-V1.5/main/datasets/proofnet.jsonl proofnet_ds.jsonl
get https://raw.githubusercontent.com/deepseek-ai/DeepSeek-Prover-V1.5/main/datasets/minif2f.jsonl minif2f_ds.jsonl
# original ProofNet (textbook of each exercise)
[ -d proofnet_orig ] || git clone --depth 1 -q https://github.com/zhangir-azerbayev/ProofNet.git proofnet_orig
# MATH (12,000 train + 500 test) via the PRM800K splits (Git LFS media host)
get https://media.githubusercontent.com/media/openai/prm800k/main/prm800k/math_splits/train.jsonl math_train.jsonl
get https://media.githubusercontent.com/media/openai/prm800k/main/prm800k/math_splits/test.jsonl math_test.jsonl
# GSM8K
get https://raw.githubusercontent.com/openai/grade-school-math/master/grade_school_math/data/train.jsonl gsm8k_train.jsonl
get https://raw.githubusercontent.com/openai/grade-school-math/master/grade_school_math/data/test.jsonl gsm8k_test.jsonl
