#!/bin/bash
# macOS install for mace-agent (Apple Silicon / Intel).
# Uses core_env_macos.yaml (CPU/MPS PyTorch) instead of the CUDA-pinned core_env.yaml.
set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

YAML=core_env_macos.yaml
ENV_NAME=$(grep -e '^name:' "$YAML" | awk '{print $2}')
echo "Creating Conda environment $ENV_NAME (macOS) without pip dependencies..."

sed '/^[[:space:]]*- pip:/,$d' "$YAML" | grep -v '^[[:space:]]*#' > conda_only_env.yaml

conda env remove -n "$ENV_NAME" -y || true
conda env create -f conda_only_env.yaml

sed -n '/^[[:space:]]*- pip:/,$p' "$YAML" | grep -v 'pip:' | grep -v '^[[:space:]]*#' | sed 's/^[[:space:]]*- //' | tr -d '"' | tr -d "'" > uv_requirements.txt

source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate "$ENV_NAME"

echo "Installing pip dependencies..."
python -m pip install -r uv_requirements.txt

rm -f conda_only_env.yaml uv_requirements.txt
echo "Environment $ENV_NAME (macOS) created successfully!"
