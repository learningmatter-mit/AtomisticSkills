# React-OT Agent Environment

Environment for the React-OT skill, capable of generating transition state structures using the React-OT model.

## Prerequisites

- Conda/miniforge3 installed
- Python 3.10
- Linux (supports aarch64/ARM64)

## Installation

The installation is automated via `install.sh` due to the complexity of patching the upstream package and compiling dependencies on aarch64.

1. Run the installation script:
```bash
bash install.sh
```

### Manual Installation Steps (if script fails)

If you need to install manually, follow these steps which mirror the script:

1. **Create Environment**:
   ```bash
   conda env create -f env.yaml
   conda activate react-ot-agent
   ```

2. **Install PyTorch**:
   ```bash
   pip install torch==2.2.1 torchvision
   ```

3. **Install PyTorch Geometric (PyG)**:
   For aarch64 (ARM), compile from source (this takes time):
   ```bash
   pip install --no-build-isolation torch-scatter torch-sparse torch-cluster torch-spline-conv
   pip install torch-geometric
   ```

4. **Install Dependencies**:
   ```bash
   pip install pytorch-lightning==2.4.0 pymatgen ase wandb networkx torchdiffeq colored-traceback ipdb lmdb rich timm
   ```

5. **Install React-OT (Patched)**:
   The upstream repository has missing files and deprecated imports.
   ```bash
   # Clone repo to a sibling directory
   cd ../..
   git clone https://github.com/deepprinciple/react-ot.git react-ot
   
   # Patch 1: Add missing __init__.py to submodule
   touch react-ot/reactot/trainer/__init__.py
   
   # Patch 2: Enable namespace packages in pyproject.toml
   # (Edit pyproject.toml: set "namespaces = true" and "include-package-data = true")
   
   # Patch 3: Fix deprecated ASE import
   # (Edit reactot/diffusion/_utils.py: replace "from ase.neb import NEB" with "from ase.mep import NEB")
   
   # Install from local source
   pip install -e react-ot
   ```

## Key Dependencies

| Package | Version |
|---|---|
| Python | 3.10 |
| torch | 2.2.1 |
| torch-geometric | 2.7.0 |
| pytorch-lightning | 2.4.0 |
| react-ot | 0.0.1 (patched) |

## Known Issues & Fixes

1.  **Missing `reactot.trainer`**: The official PyPI package and GitHub source are missing `__init__.py` in the `trainer` directory, causing it to be excluded. We fix this by manually adding the file and enabling namespaces in `pyproject.toml`.
2.  **Deprecated `ase.neb`**: React-OT uses `ase.neb.NEB`, which was moved to `ase.mep.NEB` in recent ASE versions. We patch the import in `reactot/diffusion/_utils.py`.
3.  **aarch64 Compilation**: `torch-cluster` and `torch-spline-conv` must be compiled from source on ARM64 systems, which can take ~20 minutes.
