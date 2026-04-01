# Installing MatterGen on NVIDIA Blackwell GPU (GB10) Hardware

## Overview

This guide provides complete installation instructions for MatterGen on NVIDIA DGX Spark systems with Blackwell GB10 GPUs (ARM/aarch64 architecture, CUDA 13.0).

> **For users with older x86_64 hardware**: Follow the standard [MatterGen README](https://github.com/microsoft/mattergen) installation instructions.

## System Requirements

- **Architecture**: ARM/aarch64 (NVIDIA DGX Spark)
- **GPU**: NVIDIA Blackwell GB10 (compute capability 12.1)
- **CUDA**: 13.0
- **Python**: 3.10
- **OS**: Linux

## Why This Guide Exists

The standard MatterGen installation assumes x86_64 architecture and CUDA 11.8. Blackwell GPU systems require:

1. **CUDA 13.0 compatibility**: Default MatterGen uses torch 2.2.1+cu118, but GB10 requires CUDA 13.0
2. **ARM architecture**: PyTorch Geometric dependencies must be compiled from source (no prebuilt wheels)
3. **Compute capability 12.1**: Must be explicitly set during PyG compilation

## Installation Steps

### 1. Create Conda Environment

```bash
conda create -n mattergen-agent python=3.10 -y
conda activate mattergen-agent
```

### 2. Install Core Dependencies

```bash
# Install uv and mcp
pip install uv mcp

# Install CUDA 13.0 compatible PyTorch
pip uninstall -y torch torchvision torchaudio
pip install torch==2.9.1+cu130 torchvision==0.24.1 --index-url https://download.pytorch.org/whl/cu130

# Install torch-geometric (base package)
pip install torch-geometric==2.7.0

# Downgrade setuptools for compatibility
pip install setuptools==69.5.1 --force-reinstall
```

### 3. Set CUDA Environment Variables

**CRITICAL**: These must be set before compiling PyG dependencies.

```bash
export CUDA_HOME=/usr/local/cuda-13.0
export PATH=$CUDA_HOME/bin:$PATH
export LD_LIBRARY_PATH=$CUDA_HOME/lib64:$LD_LIBRARY_PATH

# REQUIRED for GB10 GPU (compute capability 12.1)
# Without this, you'll get "CUDA error: no kernel image is available"
export TORCH_CUDA_ARCH_LIST="12.1"
```

**Verify CUDA setup**:
```bash
echo "CUDA_HOME=$CUDA_HOME"
nvcc --version
```

### 4. Compile PyG Dependencies from Source

> **Warning**: Each package takes 20-30 minutes to compile. Total time: ~1.5-2 hours.

```bash
# torch-scatter (~20-30 min)
pip install --no-build-isolation --no-cache-dir git+https://github.com/rusty1s/pytorch_scatter.git

# torch-cluster (~20-30 min)
pip install --no-build-isolation --no-cache-dir git+https://github.com/rusty1s/pytorch_cluster.git

# torch-sparse (~20-30 min, may fail - investigation needed)
pip install --no-build-isolation --no-cache-dir git+https://github.com/rusty1s/pytorch_sparse.git || echo "torch-sparse failed, continuing..."
```

**Automated script** (optional):
```bash
cd /path/to/AtomisticSkills
bash conda-envs/mattergen-agent/install_pyg_aarch64.sh
```

### 5. Apply MatterGen Patch for CUDA 13.0

**File**: `/home/bdeng/projects/mattergen/pyproject.toml`

Edit the dependencies section:

```diff
# Replace these lines (around line 71-76):
-"torch==2.2.1+cu118; sys_platform == 'linux'", 
-"torchvision==0.17.1+cu118; sys_platform == 'linux'",
-"torchaudio==2.2.1+cu118; sys_platform == 'linux'",
-"torch==2.4.1; sys_platform == 'darwin'",
-"torchvision==0.19.1; sys_platform == 'darwin'",
-"torchaudio==2.4.1; sys_platform == 'darwin'",

# With these:
+"torch>=2.0",
+"torchvision>=0.15",
```

**Also remove** the entire `[tool.uv.sources]` section (lines 99-125):

```diff
-[tool.uv.sources]
-torch = { index = "pytorch_linux",  marker = "sys_platform == 'linux'" }
-...
-[[tool.uv.index]]
-name = "pytorch_linux"
-url = "https://download.pytorch.org/whl/cu118"
-explicit = true

+# Removed strict uv.sources to allow flexible torch versions
```

**Why**: This patch allows MatterGen to install with torch 2.9.1+cu130 instead of being locked to 2.2.1+cu118.

### 6. Install MatterGen

```bash
cd /home/bdeng/projects/mattergen  # Or your MatterGen repository path
pip install -e . --no-deps

# Install remaining dependencies
pip install ase pymatgen hydra-core omegaconf pytorch-lightning==2.0.6 \
    huggingface-hub lmdb mattersim wandb SMACT emmet-core seaborn \
    matscipy monty cachetools fire contextlib2
```

### 7. Verify Installation

```bash
python -c "
import mattergen
import torch
import torch_geometric
import torch_scatter
import ase
print('✓ MatterGen environment ready')
print(f'  PyTorch: {torch.__version__}')
print(f'  CUDA available: {torch.cuda.is_available()}')
print(f'  PyG: {torch_geometric.__version__}')
print(f'  ASE: {ase.__version__}')
"
```

**Expected output**:
```
✓ MatterGen environment ready
  PyTorch: 2.9.1+cu130
  CUDA available: True
  PyG: 2.7.0
  ASE: 3.27.0
```

### 8. Export Environment (Optional)

```bash
cd /path/to/AtomisticSkills
conda env export --no-builds > conda-envs/mattergen-agent/example_full_env.yaml
```

## Troubleshooting

### Issue: "CUDA_HOME environment variable is not set"

**Solution**: Export CUDA_HOME before installing PyG dependencies:
```bash
export CUDA_HOME=/usr/local/cuda-13.0
```

### Issue: "CUDA error: no kernel image is available for execution on the device"

**Cause**: PyG was compiled without the correct CUDA architecture.

**Solution**: Set `TORCH_CUDA_ARCH_LIST="12.1"` before compiling:
```bash
export TORCH_CUDA_ARCH_LIST="12.1"
pip uninstall -y torch_scatter torch_cluster torch_sparse
# Reinstall from source with CUDA_HOME and TORCH_CUDA_ARCH_LIST set
```

### Issue: Compilation takes too long or hangs

- **Expected**: 20-30 minutes per package is normal for CUDA extension compilation
- **Monitor**: Use `htop` or `top` to verify compilation is active
- **Resources**: Ensure sufficient RAM (recommend 32GB+)

### Issue: "No module named 'torch'" during PyG build

This can occur with `--no-build-isolation`. Try:
```bash
pip install git+https://github.com/rusty1s/pytorch_scatter.git --no-cache-dir
```

### Issue: torch version mismatch after installation

If `pip` installs `torch 2.10.0+cpu` during dependency resolution:

```bash
pip install torch==2.9.1+cu130 --index-url https://download.pytorch.org/whl/cu130 --force-reinstall --no-deps
```

## Quick Reference: Complete Installation Script

```bash
#!/bin/bash
# Complete MatterGen installation for Blackwell GB10

# 1. Create environment
conda create -n mattergen-agent python=3.10 -y
conda activate mattergen-agent
pip install uv mcp

# 2. Install PyTorch CUDA 13.0
pip uninstall -y torch torchvision torchaudio
pip install torch==2.9.1+cu130 torchvision==0.24.1 --index-url https://download.pytorch.org/whl/cu130
pip install torch-geometric==2.7.0
pip install setuptools==69.5.1 --force-reinstall

# 3. Set CUDA environment
export CUDA_HOME=/usr/local/cuda-13.0
export PATH=$CUDA_HOME/bin:$PATH
export LD_LIBRARY_PATH=$CUDA_HOME/lib64:$LD_LIBRARY_PATH
export TORCH_CUDA_ARCH_LIST="12.1"  # CRITICAL for GB10

# 4. Compile PyG from source (~1.5-2 hours total)
pip install --no-build-isolation --no-cache-dir git+https://github.com/rusty1s/pytorch_scatter.git
pip install --no-build-isolation --no-cache-dir git+https://github.com/rusty1s/pytorch_cluster.git
pip install --no-build-isolation --no-cache-dir git+https://github.com/rusty1s/pytorch_sparse.git || true

# 5. Apply patch to /home/bdeng/projects/mattergen/pyproject.toml
# (See "Apply MatterGen Patch" section above)

# 6. Install MatterGen
cd /home/bdeng/projects/mattergen
pip install -e . --no-deps
pip install ase pymatgen hydra-core omegaconf pytorch-lightning==2.0.6 \
    huggingface-hub lmdb mattersim wandb SMACT emmet-core seaborn \
    matscipy monty cachetools fire contextlib2

# 7. Verify
python -c "import mattergen, torch, torch_geometric, torch_scatter; print('✓ Installation successful')"
```

## Key Differences from Standard Installation

| Aspect | Standard (x86_64) | Blackwell GB10 (ARM) |
|--------|-------------------|----------------------|
| PyTorch version | 2.2.1+cu118 | 2.9.1+cu130 |
| PyG installation | `pip install` (wheels) | Source compilation |
| Compilation time | <5 minutes | ~1.5-2 hours |
| CUDA arch | Auto-detect | Must set `12.1` |
| Patch required | No | Yes (pyproject.toml) |

## References

- MatterGen GitHub: https://github.com/microsoft/mattergen
- PyTorch Geometric: https://github.com/pyg-team/pytorch_geometric
- NVIDIA Blackwell Architecture: https://www.nvidia.com/en-us/data-center/grace-blackwell-platform/
- CUDA Compute Capabilities: https://developer.nvidia.com/cuda-gpus

---

**Last Updated**: 2026-02-13  
**Tested On**: NVIDIA DGX Spark with GB10 GPU (ARM/aarch64)  
**Author**: Bowen Deng  
**Contact**: github.com/bowen-bd
