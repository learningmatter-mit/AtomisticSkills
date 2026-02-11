#!/bin/bash
# Verification script for base-agent simplified installation
set -e

# 0. Clean up previous test environment if it exists
echo "Cleaning up previous test environment..."
conda env remove -n base-agent-test -y || true

# 1. Create the test environment
echo "Creating base-agent-test environment..."
conda env create -f conda-envs/base-agent/core_env.yaml -n base-agent-test

# 2. Activate
source $(conda info --base)/etc/profile.d/conda.sh
conda activate base-agent-test

# 3. Install dev dependencies
echo "Installing pytest..."
pip install pytest pytest-cov

# 4. Verification
echo "Verifying imports and running tests..."
export PYTHONPATH=$(pwd)
# Explicitly check mp_api import
python -c "import mp_api.client; print('mp_api imported successfully')"

# Run base tests
pytest tests/base/ -v
echo "Verification complete!"
