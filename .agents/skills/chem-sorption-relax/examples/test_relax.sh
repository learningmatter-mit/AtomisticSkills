#!/usr/bin/env bash
cd $(dirname "$0")

# Build supercell based on a minimum interplanar distance of 12.0 Å
conda run -n base-agent python ../scripts/build_supercell.py \
    --structure Hb-DBD-AA.cif \
    --min-plane-dist 12.0 \
    --output-cif Hb-DBD-AA_supercell.cif

echo "Supercell built successfully!"
