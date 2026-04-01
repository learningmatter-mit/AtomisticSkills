# DiffCSP++ Agent Environment

This environment contains DiffCSP++ for space-group-constrained crystal structure generation.

## Prerequisites

- Conda/miniforge3 installed
- Python 3.11
- CUDA 13.0 compatible GPU (for GPU acceleration)
- DiffCSP++ repo cloned to `/home/bdeng/projects/DiffCSP-PP`

## Installation

1. Create the conda environment:
```bash
conda create -n diffcsp-agent python=3.11 pip uv -y
```

2. Activate and install PyTorch:
```bash
conda activate diffcsp-agent
pip3 install torch torchvision --index-url https://download.pytorch.org/whl/cu130
```

3. Install DiffCSP++ dependencies:
```bash
pip install pymatgen ase pyxtal hydra-core==1.3.2 omegaconf==2.3.0 \
  pytorch-lightning==2.0.3 chemparse p-tqdm python-dotenv smact matminer \
  einops torchdiffeq scikit-learn wandb torch-geometric mcp

# Downgrade setuptools for pkg_resources compatibility
pip install setuptools==69.5.1 --force-reinstall
```

4. Install torch-scatter from source (required for ARM/aarch64):
```bash
export CUDA_HOME=/usr/local/cuda-13.0
export PATH=$CUDA_HOME/bin:$PATH
export LD_LIBRARY_PATH=$CUDA_HOME/lib64:$LD_LIBRARY_PATH
export TORCH_CUDA_ARCH_LIST="12.1"

pip install --no-build-isolation --no-cache-dir git+https://github.com/rusty1s/pytorch_scatter.git
```

5. Download pre-trained checkpoints:
```bash
pip install gdown
cd /home/bdeng/projects/DiffCSP-PP
gdown --folder https://drive.google.com/drive/folders/1FQ_b6CE09KtyGaU_r6uO8_I5JhrQmUFB --remaining-ok -O checkpoints
```

## Available Models

| Model | Type | Description |
|-------|------|-------------|
| `mp_csp` | CSP | Materials Project - composition-constrained generation |
| `mp_gen` | Gen | Materials Project - unconditional generation |
| `perov_csp` | CSP | Perovskite - composition-constrained generation |
| `perov_gen` | Gen | Perovskite - unconditional generation |
| `carbon_gen` | Gen | Carbon - unconditional generation |
| `mpts_csp` | CSP | MPTS-52 - composition-constrained generation |

## MCP Tools

1. **generate_structures_with_symmetry**: Generate structures with exact composition control via space group + Wyckoff positions + atom types
2. **generate_structures**: Unconditional ab initio generation from training distribution

## Key Dependencies

- Python 3.11
- torch 2.10.0+cu130
- torch-geometric
- torch-scatter 2.1.2 (compiled from source)
- pytorch-lightning 2.0.3
- hydra-core 1.3.2
- pyxtal, pymatgen, ase
