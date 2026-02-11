#!/bin/bash
# Verification script for matgl-agent simplified installation
set -e

echo "Cleaning up previous test environment..."
conda env remove -n matgl-agent-test -y || true

echo "Creating matgl-agent-test environment..."
conda env create -f conda-envs/matgl-agent/core_env.yaml -n matgl-agent-test

source $(conda info --base)/etc/profile.d/conda.sh
conda activate matgl-agent-test

echo "Installing pytest..."
pip install pytest pytest-cov

echo "Verifying imports and running tests..."
export PYTHONPATH=$(pwd)
pytest tests/matgl/ -v
echo "Verification complete!"
