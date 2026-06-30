#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

python scripts/run_mvc_experiment_1_2_formal.py \
  --source-input-dir data/mvc_mk01_15_2vc4sru_integrated_mechanism \
  --out-root reports/mvc_mk01_15_integrated_mechanism_medium_exp1_exp2 \
  --prepared-input-name mk01_15_integrated_mechanism \
  --expected-instances 15 \
  --seeds 20260428,20260429 \
  --popsize 50 \
  --max-iter 50 \
  --time-limit 600 \
  --objective-dim 2 \
  --resume
