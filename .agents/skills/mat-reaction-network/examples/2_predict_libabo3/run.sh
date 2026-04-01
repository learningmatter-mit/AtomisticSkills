#!/bin/bash
# Validate the synthesis pathways for BaLiBO3 as reported in computational literature.
#
# This script compares the traditional solid-state precursors with the predicted optimal precursors.

set -e

SCRIPT_PATH="../../scripts/find_pathways.py"

echo "=== 1. Traditional Precursors (B2O3 + BaO + Li2O) ==="
conda run --no-capture-output -n base-agent python -u $SCRIPT_PATH \
    --target BaLiBO3 \
    --precursors B2O3 BaO Li2O \
    --temperature 1000 \
    --stability-tol 0.0 \
    --output traditional_output.json

echo "=== 2. Predicted Precursors (LiBO2 + BaO) ==="
conda run --no-capture-output -n base-agent python -u $SCRIPT_PATH \
    --target BaLiBO3 \
    --precursors LiBO2 BaO \
    --temperature 1000 \
    --stability-tol 0.1 \
    --output predicted_output.json

echo "Outputs saved to traditional_output.json and predicted_output.json locally."
