#!/bin/bash
# Example: LiCoO2 Li-ion migration barrier using MACE

# Ensure we are in the script directory
cd "$(dirname "$0")"

echo "1. Preparing structures (Relaxing start/end)..."
python prepare_licoo2.py

echo "2. Running NEB with IDPP..."
# Note: Paths are relative to where this script is run
python ../../scripts/calculate_barrier.py \
    --start_structure neb_input/start.cif \
    --end_structure neb_input/end.cif \
    --model_type mace \
    --model_name "MACE-OMAT-0-small" \
    --n_images 7 \
    --fmax 0.05 \
    --output_dir output

echo "Done! Results in output/"
