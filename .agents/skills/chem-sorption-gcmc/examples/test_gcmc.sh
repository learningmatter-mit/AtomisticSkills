#!/usr/bin/env bash
cd $(dirname "$0")

# Run Single Component GCMC using UMA
export PYTHONPATH=$(dirname $(dirname $(dirname $(dirname "$PWD"))))
conda run -n fairchem-agent python ../scripts/run_gcmc.py \
  --cif test_structure_supercell.relaxed.cif \
  --calculator fairchem \
  --model-name uma-s-1p1 \
  --task-name omol \
  --steps 100 \
  --temperature-K 298 \
  --pressure-bar 1.0 \
  --adsorbate CO2 \
  --output-dir ./single_gas

# Run Multi Component GCMC using UMA
conda run -n fairchem-agent python ../scripts/run_gcmc_multi.py \
  --cif test_structure_supercell.relaxed.cif \
  --calculator fairchem \
  --model-name uma-s-1p1 \
  --task-name omol \
  --steps 100 \
  --temperature-K 298 \
  --gases CO2 N2 \
  --y 0.15 0.85 \
  --p-total-bar 1.0 \
  --output-dir ./multi_gas

echo "GCMC test complete!"
