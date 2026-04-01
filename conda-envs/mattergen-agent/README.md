# MatterGen Agent Environment

This environment contains MatterGen for material structure generation.

## Prerequisites

> **ARM/aarch64 Support**: This environment works on ARM systems (e.g., NVIDIA DGX Spark) but requires manual compilation of PyG dependencies with CUDA_HOME configured. See "Installation on ARM" section below.

- Conda/miniforge3 installed
- Python 3.10 (required by MatterGen)
- CUDA 13.0 compatible GPU (for GPU acceleration)

## Installation

1. Create the conda environment:
```bash
conda env create -f core_env.yaml
```

2. Activate the environment:
```bash
conda activate mattergen-agent
```

3. Install MatterGen and dependencies:
```bash
cd /path/to/AtomisticSkills/.agents/tmp/mattergen

# Install mattergen
uv pip install -e .

# Upgrade to CUDA 13.0 compatible torch (required for GB10 GPU)
pip uninstall -y torch torchvision torchaudio
pip install torch==2.9.1+cu130 torchvision==0.24.1 --index-url https://download.pytorch.org/whl/cu130

# Install torch-geometric
pip install torch-geometric==2.7.0

# Downgrade setuptools for pkg_resources compatibility
pip install setuptools==69.5.1 --force-reinstall

# Install PyG dependencies from source (required for ARM)
export CUDA_HOME=/usr/local/cuda-13.0
export PATH=$CUDA_HOME/bin:$PATH
export LD_LIBRARY_PATH=$CUDA_HOME/lib64:$LD_LIBRARY_PATH

# REQUIRED for GB10 GPU: Set CUDA architecture (compute capability 12.1)
# For other GPUs, check: https://developer.nvidia.com/cuda-gpus
export TORCH_CUDA_ARCH_LIST="12.1"

pip install --no-build-isolation --no-cache-dir git+https://github.com/rusty1s/pytorch_scatter.git
pip install --no-build-isolation --no-cache-dir git+https://github.com/rusty1s/pytorch_cluster.git
pip install --no-build-isolation --no-cache-dir git+https://github.com/rusty1s/pytorch_sparse.git
```

> **Note**: PyG compilation takes ~4-5 hours total on ARM with GB10 GPU. If you skip `TORCH_CUDA_ARCH_LIST`, you'll encounter `CUDA error: no kernel image is available` during GPU inference.

```bash

4. Export environment state:
```bash
conda env export --no-builds > example_full_env.yaml
```

## Available Models

MatterGen provides several pretrained models:
- `mattergen_base`: Base generative model
- `mp_20_base`: Materials Project base model  
- `dft_mag_density`: Model for magnetic density conditioning
- `chemical_system`: Model for chemical system conditioning

## Usage

The environment is configured to run the MatterGen MCP server:

```bash
# The server is automatically configured in mcp_config.json
# You can call MatterGen tools via the MCP interface
```

### MCP Tools

1. **load_model**: Load a pretrained MatterGen model
2. **generate_structures**: Generate material structures (conditional or unconditional)
3. **fine_tune_model**: Fine-tune models on custom datasets
4. **get_info**: Get information about loaded model

## Key Dependencies

- Python 3.10
- torch 2.9.1+cu130 (CUDA 13.0)
- torch-geometric 2.7.0
- mattergen (from source)
- pymatgen
- ase

## Installation on ARM/aarch64 (DGX Spark)

For ARM-based systems, PyG ecosystem packages must be compiled from source:

```bash
# Set CUDA environment (CRITICAL for successful compilation)
export CUDA_HOME=/usr/local/cuda-13.0
export PATH=$CUDA_HOME/bin:$PATH
export LD_LIBRARY_PATH=$CUDA_HOME/lib64:$LD_LIBRARY_PATH

# Install PyG dependencies from source (~20-30 min each)
pip install git+https://github.com/rusty1s/pytorch_scatter.git --no-cache-dir
pip install git+https://github.com/rusty1s/pytorch_cluster.git --no-cache-dir
pip install git+https://github.com/rusty1s/pytorch_sparse.git --no-cache-dir || echo "torch-sparse may fail - needs investigation"
```

Or use the automated script:
```bash
bash conda-envs/mattergen-agent/install_pyg_aarch64.sh
```

For installing MatterGen on ARM/aarch64 machine, see [`INSTALL_BLACKWELL.md`](file:///home/bdeng/projects/AtomisticSkills/conda-envs/mattergen-agent/INSTALL_BLACKWELL.md) in this directory

## Notes

- This environment uses Python 3.10 (required by MatterGen)
- Torch 2.9.1+cu130 is used for CUDA 13.0 compatibility
- The vanilla `core_env.yaml` references default MatterGen dependencies
- The `example_full_env.yaml` reflects the actual working environment after manual torch upgrade
- **ARM systems**: PyG packages require source compilation with CUDA_HOME set
