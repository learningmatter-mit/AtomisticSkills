#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

python ../../scripts/optimize_ts_sella.py \
  --ts_guess ts_guess.xyz \
  --model_type fairchem \
  --model_name uma-s-1p1 \
  --task_name omol \
  --fmax 0.02 \
  --steps 500 \
  --vib_delta 0.01 \
  --vib_nfree 2 \
  --imag_cutoff_cm1 -50.0 \
  --output_dir output
