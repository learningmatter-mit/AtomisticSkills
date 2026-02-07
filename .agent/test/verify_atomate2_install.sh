#!/bin/bash
# Verification script for atomate2-agent simplified installation
set -e

echo "Cleaning up previous test environment..."
conda env remove -n atomate2-agent-test -y || true

echo "Creating atomate2-agent-test environment..."
conda env create -f conda-envs/atomate2-agent/core_env.yaml -n atomate2-agent-test

source $(conda info --base)/etc/profile.d/conda.sh
conda activate atomate2-agent-test

echo "Installing pytest..."
pip install pytest pytest-cov

echo "Verifying imports and running tests..."
export PYTHONPATH=$(pwd)
pytest tests/atomate2/ -v
echo "Verification complete!"
