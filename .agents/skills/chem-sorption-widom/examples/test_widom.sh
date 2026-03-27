#!/usr/bin/env bash
cd $(dirname "$0")

# Run Widom insertion using UMA
export PYTHONPATH=$(dirname $(dirname $(dirname $(dirname "$PWD"))))
conda run -n fairchem-agent python ../scripts/run_widom.py \
  --structure Hb-DBD-AA_supercell.relaxed.cif \
  --name Hb-DBD-AA \
  --calculator fairchem \
  --model-name uma-s-1p1 \
  --task-name omol \
  --gas CO2 \
  --temperature 298 \
  --num-insertions 5000 \
  --output-dir .

echo "Widom insertion test complete!"
