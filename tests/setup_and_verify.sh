#!/bin/bash
set -e

# Define paths
ENV_NAME="htvs-agent"
ENV_FILE=../conda-envs/htvs-agent.yml
VERIFY_SCRIPT=tests/verify_htvs_tools.py

echo "--- Checking for Conda environment: $ENV_NAME ---"
if conda info --envs | grep -q "$ENV_NAME"; then
    echo "Environment $ENV_NAME exists."
else
    echo "Environment $ENV_NAME not found. Attempting to create..."
    echo "Note: This might take a while if dependencies are complex."
    mamba env create -f $ENV_FILE || conda env create -f $ENV_FILE
fi

# Locate python in the new env
# Try standard location or activate
# Assuming miniforge3 structure from other files
PYTHON_EXEC=$(conda run -n $ENV_NAME which python)
echo "Using Python: $PYTHON_EXEC"

echo "--- Installing local htvs if needed ---"
# Check if htvs is importable
$PYTHON_EXEC -c "import htvs" 2>/dev/null || echo "htvs not found in env, assuming it's in pythonpath or needs install."

# Run verification
echo "--- Running Verification Script ---"
# We need to set PYTHONPATH to include simulation_mcp root and htvs root
export PYTHONPATH=$PYTHONPATH:$(pwd)/..:/mnt/data0/hojechun/repos/htvs
export HTVS_DJANGOCHEM_DIR=/mnt/data0/hojechun/repos/htvs/djangochem

$PYTHON_EXEC $VERIFY_SCRIPT
