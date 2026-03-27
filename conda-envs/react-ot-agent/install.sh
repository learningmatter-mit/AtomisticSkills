#!/bin/bash
set -e

# Get the directory of the script (conda-envs/react-ot-agent)
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
# Project root is two levels up
PROJECT_ROOT="$( dirname "$( dirname "$SCRIPT_DIR" )" )"

# Remove existing environment if it exists (or just update it)
conda env remove -n react-ot-agent -y || true

# Create the environment with basic dependencies
echo "Creating conda environment 'react-ot-agent'..."
conda env create -f "$SCRIPT_DIR/env.yaml"

echo "Activating environment..."
source $(conda info --base)/etc/profile.d/conda.sh
conda activate react-ot-agent

# Install dependencies in order
echo "Installing PyTorch..."
# Using pip to install torch 2.2.1
pip install torch==2.2.1 torchvision

echo "Installing PyTorch Geometric dependencies..."
# Use --no-build-isolation to ensure it uses the installed torch
pip install --no-build-isolation torch-scatter torch-sparse torch-cluster torch-spline-conv || {
    echo "Build from source failed with isolation. Trying with wheels if available or verbose..."
    # Fallback or debug
    exit 1
}
# Then install geom
pip install torch-geometric

echo "Installing other dependencies..."
pip install pytorch-lightning==2.4.0 pymatgen ase wandb networkx torchdiffeq colored-traceback ipdb lmdb rich timm

echo "Cloning and Installing React-OT (Patched)..."

# Clone to a sibling directory of the project root
# e.g., if PROJECT_ROOT is /path/to/AtomisticSkills, this clones to /path/to/react-ot
REACT_OT_DIR="$PROJECT_ROOT/../react-ot"

if [ -d "$REACT_OT_DIR" ]; then
    echo "React-OT directory already exists at $REACT_OT_DIR. Updating..."
    # Optionally pull latest changes, but we might have local patches so be careful.
    # ideally we re-clone to be clean or just pull.
    # git -C "$REACT_OT_DIR" pull
else
    git clone https://github.com/deepprinciple/react-ot.git "$REACT_OT_DIR"
fi

# Apply patches
echo "Applying patches to $REACT_OT_DIR..."

# Patch 1: Add missing __init__.py to reactot/trainer
if [ ! -f "$REACT_OT_DIR/reactot/trainer/__init__.py" ]; then
    touch "$REACT_OT_DIR/reactot/trainer/__init__.py"
    echo "Patched: Added __init__.py to reactot/trainer"
fi

# Patch 2: Enable namespace packages in pyproject.toml
# Check if already patched to avoid duplicate appending or sed issues
if ! grep -q "namespaces = true" "$REACT_OT_DIR/pyproject.toml"; then
    # Use python to safely replace or sed
    # Simple sed for the specific lines we know
    sed -i 's/include-package-data = false/include-package-data = true/' "$REACT_OT_DIR/pyproject.toml"
    sed -i 's/namespaces = false/namespaces = true/' "$REACT_OT_DIR/pyproject.toml"
    echo "Patched: Enabled namespaces in pyproject.toml"
fi

# Patch 3: Fix deprecated ASE import
# Check if already patched
if grep -q "from ase.neb import NEB" "$REACT_OT_DIR/reactot/diffusion/_utils.py"; then
    sed -i 's/from ase.neb import NEB/from ase.mep import NEB/' "$REACT_OT_DIR/reactot/diffusion/_utils.py"
    echo "Patched: Fixed deprecated ASE import in _utils.py"
fi

# Install from local source
echo "Installing React-OT from $REACT_OT_DIR..."
pip install -e "$REACT_OT_DIR"

echo "Environment 'react-ot-agent' created successfully!"
