#!/bin/bash
# Example: Retrieve Li-O binary phase diagram from Materials Project
#
# This example demonstrates:
# 1. Basic phase diagram retrieval
# 2. Generating a visualization
# 3. Interpreting the results

set -e

echo "========================================="
echo "Li-O Phase Diagram Retrieval Example"
echo "========================================="
echo

# Check MP_API_KEY
if [ -z "$MP_API_KEY" ]; then
    echo "Error: MP_API_KEY environment variable not set"
    echo "Please set your Materials Project API key:"
    echo "  export MP_API_KEY='your_api_key_here'"
    exit 1
fi

# Create output directory
mkdir -p li_o_phase_diagram
cd li_o_phase_diagram

echo "Step 1: Retrieve Li-O phase diagram with visualization"
echo "--------------------------------------------------------"
python ../../../scripts/get_phase_diagram.py \
    --chemsys "Li-O" \
    --output li_o_pd.json \
    --plot li_o_pd.png

echo
echo "Step 2: Check specific material stability (Li2O)"
echo "--------------------------------------------------------"
python ../../../../mat-db-mp/scripts/query_mp.py \
    --formula "Li2O" \
    --properties energy_above_hull formation_energy_per_atom \
    --output li2o_stability.json

echo
echo "========================================="
echo "✓ Phase Diagram Retrieval Complete"
echo "========================================="
echo
echo "Output files:"
echo "  - li_o_pd.json       : Phase diagram data"
echo "  - li_o_pd.png        : Phase diagram plot"
echo "  - li2o_stability.json: Li2O stability data"
echo
echo "Expected results:"
echo "  - Li2O should be on the convex hull (energy_above_hull = 0.0)"
echo "  - Li2O is the only stable binary compound in Li-O system"
echo "  - Other Li-O phases (e.g., LiO2) will be above the hull"
