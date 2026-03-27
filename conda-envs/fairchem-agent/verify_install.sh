#!/bin/bash
# Verification script for fairchem-agent simplified installation
set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${REPO_ROOT}"

echo "Cleaning up previous test environment..."
conda env remove -n fairchem-agent-test -y || true

echo "Creating fairchem-agent-test environment..."
conda env create -f conda-envs/fairchem-agent/core_env.yaml -n fairchem-agent-test

source $(conda info --base)/etc/profile.d/conda.sh
conda activate fairchem-agent-test

echo "Installing pytest..."
pip install pytest pytest-cov

echo "Verifying imports and running tests..."
export PYTHONPATH=$(pwd)
pytest tests/fairchem/test_fairchem_server.py -v
echo "Verification complete!"
