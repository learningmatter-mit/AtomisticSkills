#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

python ../../scripts/verify_irc_sella.py \
  --reactant reactant_optimized.xyz \
  --product product_optimized.xyz \
  --ts ts_optimized.xyz \
  --model_type fairchem \
  --model_name uma-s-1p1 \
  --task_name omol \
  --fmax 0.02 \
  --steps 400 \
  --rmsd_threshold 0.20 \
  --relax_endpoints true \
  --endpoint_relax_fmax 0.02 \
  --output_dir output
