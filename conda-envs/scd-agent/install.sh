#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

ENV_NAME=$(grep -e '^name:' core_env.yaml | awk '{print $2}')
WORKSPACE_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
DEFAULT_REPO_DIR="$WORKSPACE_ROOT/SelfConditionedDenoisingAtoms"

SCD_REPO_URL="${SCD_REPO_URL:-https://github.com/TyJPerez/SelfConditionedDenoisingAtoms.git}"
SCD_REPO_DIR="${SCD_REPO_DIR:-$DEFAULT_REPO_DIR}"
TORCH_INDEX_URL="${TORCH_INDEX_URL:-https://download.pytorch.org/whl/cu124}"
PYG_WHEEL_URL="${PYG_WHEEL_URL:-https://data.pyg.org/whl/torch-2.6.0+cu124.html}"
TORCH_PACKAGES="${TORCH_PACKAGES:-torch==2.6.0 torchvision torchaudio}"
BUILD_TORCHMD_KERNEL="${BUILD_TORCHMD_KERNEL:-0}"

echo "Creating Conda environment $ENV_NAME without pip dependencies..."

sed '/^[[:space:]]*- pip:/,$d' core_env.yaml > conda_only_env.yaml
conda env remove -n "$ENV_NAME" -y || true
conda env create -f conda_only_env.yaml

sed -n '/^[[:space:]]*- pip:/,$p' core_env.yaml   | grep -v 'pip:'   | sed 's/^[[:space:]]*- //'   | tr -d '"'   | tr -d "'" > uv_requirements.txt

if ! command -v uv &> /dev/null; then
    echo "Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.cargo/bin:$HOME/.local/bin:$PATH"
fi

source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate "$ENV_NAME"

echo "Installing PyTorch packages from $TORCH_INDEX_URL..."
uv pip install --index-url "$TORCH_INDEX_URL" $TORCH_PACKAGES

echo "Installing PyG extension wheels from $PYG_WHEEL_URL..."
uv pip install --find-links "$PYG_WHEEL_URL" torch-scatter torch-cluster torch-sparse

echo "Installing remaining Python dependencies..."
uv pip install -r uv_requirements.txt
uv pip install torch-geometric

if [ ! -d "$SCD_REPO_DIR/.git" ]; then
    echo "Cloning SelfConditionedDenoisingAtoms into $SCD_REPO_DIR..."
    mkdir -p "$(dirname "$SCD_REPO_DIR")"
    git clone "$SCD_REPO_URL" "$SCD_REPO_DIR"
else
    echo "Using existing repository at $SCD_REPO_DIR"
fi

if [ -f "$SCD_REPO_DIR/requirements.txt" ]; then
    echo "Installing upstream repo requirements for compatibility..."
    uv pip install -r "$SCD_REPO_DIR/requirements.txt"
fi

if [ "$BUILD_TORCHMD_KERNEL" = "1" ]; then
    echo "Building optional TorchMD graph kernel..."
    (
        cd "$SCD_REPO_DIR/models/ET_models"
        python setup.py build_ext --inplace
    )
else
    echo "Skipping optional TorchMD graph kernel build."
    echo "Set BUILD_TORCHMD_KERNEL=1 if you want the faster non-periodic graph path."
fi

rm -f conda_only_env.yaml uv_requirements.txt

echo "Environment $ENV_NAME created successfully."
echo "Repository location: $SCD_REPO_DIR"
