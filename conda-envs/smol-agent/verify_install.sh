#!/bin/bash
# Verification script for smol-agent simplified installation
set -e

echo "Cleaning up previous test environment..."
conda env remove -n smol-agent-test -y || true

echo "Creating smol-agent-test environment..."
conda env create -f conda-envs/smol-agent/core_env.yaml -n smol-agent-test

source $(conda info --base)/etc/profile.d/conda.sh
conda activate smol-agent-test

echo "Installing pytest..."
pip install pytest pytest-cov

echo "Verifying imports and running tests..."
export PYTHONPATH=$(pwd)
pytest tests/test_smol_enumeration.py -v
echo "Verification complete!"
