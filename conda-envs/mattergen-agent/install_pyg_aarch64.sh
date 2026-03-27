#!/bin/bash
# Installation script for torch-scatter on NVIDIA DGX Spark (ARM/aarch64)
# 
# This script installs PyG ecosystem packages (torch-scatter, torch-cluster, torch-sparse)
# for use with MatterGen on ARM-based systems like DGX Spark.
#
# CRITICAL: Setting CUDA_HOME is essential for successful compilation on ARM systems

set -e

# Check if in correct conda environment
if [[ "$CONDA_DEFAULT_ENV" != "mattergen-agent" ]]; then
    echo "Error: Please activate mattergen-agent environment first:"
    echo "  conda activate mattergen-agent"
    exit 1
fi

# Set CUDA environment variables
export CUDA_HOME=/usr/local/cuda-13.0
export PATH=$CUDA_HOME/bin:$PATH
export LD_LIBRARY_PATH=$CUDA_HOME/lib64:$LD_LIBRARY_PATH

echo "==================================="
echo "CUDA Environment Setup"
echo "==================================="
echo "CUDA_HOME=$CUDA_HOME"
echo "nvcc version:"
nvcc --version
echo ""

# Install torch-scatter (REQUIRED for MatterGen)
echo "==================================="
echo "Installing torch-scatter..."
echo "==================================="
pip install git+https://github.com/rusty1s/pytorch_scatter.git --no-cache-dir
echo "✓ torch-scatter installed!"
echo ""

# Install torch-cluster (REQUIRED for MatterGen)
echo "==================================="
echo "Installing torch-cluster..."
echo "==================================="
pip install git+https://github.com/rusty1s/pytorch_cluster.git --no-cache-dir
echo "✓ torch-cluster installed!"
echo ""

# Install torch-sparse (REQUIRED for MatterGen)
echo "==================================="
echo "Installing torch-sparse..."
echo "==================================="
# Note: torch-sparse may fail - needs investigation
pip install git+https://github.com/rusty1s/pytorch_sparse.git --no-cache-dir || echo "⚠ torch-sparse installation failed - may need alternative approach"
echo ""

# Verify installations
echo "==================================="
echo "Verifying Installations"
echo "==================================="
python -c "import torch_scatter; print('✓ torch-scatter:', torch_scatter.__version__)"
python -c "import torch_cluster; print('✓ torch-cluster:', torch_cluster.__version__)" || echo "⚠ torch-cluster not available"
python -c "import torch_sparse; print('✓ torch-sparse:', torch_sparse.__version__)" || echo "⚠ torch-sparse not available"
echo ""

echo "==================================="
echo "Installation Complete!"
echo "==================================="
echo "You can now test MatterGen with:"
echo "  python .agents/test/test_mattergen.py"
