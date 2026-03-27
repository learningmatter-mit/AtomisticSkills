#!/bin/bash
# Verification script for orca-agent simplified installation
set -e

# 0. Clean up previous test environment if it exists
echo "Cleaning up previous test environment..."
conda env remove -n orca-agent-test -y || true

# 1. Create the test environment
echo "Creating orca-agent-test environment..."
conda env create -f conda-envs/orca-agent/core_env.yaml -n orca-agent-test

# 2. Activate
source $(conda info --base)/etc/profile.d/conda.sh
conda activate orca-agent-test

# 3. Install dev dependencies
echo "Installing pytest..."
pip install pytest pytest-cov

# 4. Verification
echo "Verifying imports and running tests..."
export PYTHONPATH=$(pwd)
# Explicitly check calculator construction
export ORCA_BINARY_PATH=$PWD
python -c "import scine_utilities as su; calc = su.core.get_calculator('dft', 'orca')"

# Run orca tests
pytest tests/orca/ -v
echo "Verification complete!"
