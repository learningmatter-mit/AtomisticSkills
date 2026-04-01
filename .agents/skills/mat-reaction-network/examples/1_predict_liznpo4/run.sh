#!/bin/bash
# Validate the synthesis pathways for LiZnPO4 as reported in computational literature.
#
# This script compares the traditional precursors with computationally predicted precursors.

set -e

SCRIPT_PATH="../../scripts/find_pathways.py"

echo "=== 1. Pairwise Reaction A: Zn2P2O7 + Li2O ==="
python -u $SCRIPT_PATH \
    --target LiZnPO4 \
    --precursors Zn2P2O7 Li2O \
    --temperature 1000 \
    --stability-tol 0.0 \
    --output pair_a_output.json

echo "=== 2. Pairwise Reaction B: Zn3(PO4)2 + Li3PO4 ==="
python -u $SCRIPT_PATH \
    --target LiZnPO4 \
    --precursors Zn3\(PO4\)2 Li3PO4 \
    --temperature 1000 \
    --stability-tol 0.0 \
    --output pair_b_output.json

echo "=== 3. Pairwise Reaction C: LiPO3 + ZnO ==="
python -u $SCRIPT_PATH \
    --target LiZnPO4 \
    --precursors LiPO3 ZnO \
    --temperature 1000 \
    --stability-tol 0.0 \
    --output pair_c_output.json

echo "Outputs saved to pair_a_output.json, pair_b_output.json, and pair_c_output.json locally."
