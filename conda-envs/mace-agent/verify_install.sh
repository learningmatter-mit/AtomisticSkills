#!/bin/bash
# Verification script for mace-agent simplified installation

# Stop on error
set -e

# 0. Clean up previous test environment if it exists
echo "Cleaning up previous test environment..."
conda env remove -n mace-agent-test -y || true

# 1. Create the test environment using the simplified script
echo "Creating mace-agent-test environment..."
conda env create -f conda-envs/mace-agent/core_env.yaml -n mace-agent-test

# 2. Activate
source $(conda info --base)/etc/profile.d/conda.sh
conda activate mace-agent-test

# 3. Install dev dependencies for testing
echo "Installing pytest for verification..."
pip install pytest pytest-cov

# 4. Verification
echo "Verifying imports and conducting test run..."
export PYTHONPATH=$(pwd)
echo "PYTHONPATH set to $PYTHONPATH"

# Run the specific test file
# Note: This might fail on specific hardware if the model download fails or needs CUDA, 
# but we are verifying the environment capability to run the code.
pytest tests/mace/test_mace_server.py -v

echo "Verification complete!"
