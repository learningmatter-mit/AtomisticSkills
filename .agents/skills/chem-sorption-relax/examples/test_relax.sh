#!/usr/bin/env bash
cd $(dirname "$0")

# Build supercell based on a minimum interplanar distance of 12.0 Å
conda run -n base-agent python ../scripts/build_supercell.py \
    --structure test_structure.cif \
    --min-plane-dist 12.0 \
    --output-cif test_structure_supercell.cif

echo "Supercell built successfully!"

export PYTHONPATH=$(dirname $(dirname $(dirname $(dirname "$PWD"))))
conda run -n fairchem-agent python ../scripts/relax_structure.py \
    --structure test_structure_supercell.cif \
    --name test_structure_supercell \
    --calculator fairchem \
    --model-name uma-s-1p1 \
    --task-name omol \
    --steps 50 \
    --output-dir .

echo "Relaxation complete!"
