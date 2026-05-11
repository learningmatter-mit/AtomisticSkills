#!/bin/bash

# Example script demonstrating how to use the chem-docking-void Skill
# This test docks N,N,N-trimethyladamantan-1-aminium (TMAda) into Chabazite (CHA).

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." &> /dev/null && pwd)"
SCRIPT_PATH="$SKILL_DIR/scripts/run_docking.py"

# We use the CHA.cif supplied in the original VOID repository examples
CHA_CIF="./CHA.cif"

# The SMILES string for N,N,N-trimethyladamantan-1-aminium
TMADA_SMILES="C[N+](C)(C)C12CC3CC(C1)CC(C2)C3"

OUTPUT_DIR="./example_output"

echo "Running Voronoi Docking on CHA with TMAda..."
echo "SMILES: $TMADA_SMILES"
echo "Host CIF: $CHA_CIF"
echo ""

python "$SCRIPT_PATH" \
  --smiles "$TMADA_SMILES" \
  --host_cif "$CHA_CIF" \
  --output_dir "$OUTPUT_DIR" \
  --num_conformers 5 \
  --threshold 1.25 \
  --attempts 50 \
  --structs_per_loading 2 \
  --num_clusters 5 \
  --min_radius 3.0 \
  --probe_radius 0.1 \
  --max_subdock 1 \
  --max_loading 20

echo ""
echo "Example run finished. Please check the $OUTPUT_DIR directory for results."
