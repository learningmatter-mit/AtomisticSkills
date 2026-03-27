# ADiT Agent Environment

Environment for the All-atom Diffusion Transformer (ADiT) — a unified latent diffusion model for generating both periodic crystals and non-periodic molecules.

## Prerequisites

- Conda/miniforge3 installed
- Python 3.10
- CUDA 13.0 compatible GPU

## Installation

1. Create the conda environment:
```bash
conda env create -f core_env.yaml
conda activate adit-agent
```

2. Install PyTorch 2.9.1+cu130:
```bash
pip install torch==2.9.1 torchvision --index-url https://download.pytorch.org/whl/cu130
```

3. Install PyG and extensions:
```bash
pip install torch-geometric
```

> **GB10 / ARM / CUDA 13.0 users**: torch-scatter and torch-cluster must be compiled from source. Follow the **"Installation on ARM"** section in [`conda-envs/mattergen-agent/README.md`](../mattergen-agent/README.md) for `CUDA_HOME`, `TORCH_CUDA_ARCH_LIST`, and build commands.

4. Install remaining dependencies:
```bash
pip install lightning==2.4.0 hydra-core hydra-colorlog
pip install e3nn==0.5.1 einops rootutils rich omegaconf torchdiffeq huggingface_hub
pip install pymatgen ase rdkit pyxtal tqdm scipy pandas matplotlib torchmetrics
pip install timm lmdb wandb pathos p-tqdm download
pip install smact matminer importlib_resources
pip install mcp fastmcp
```

5. Clone the AADT repository:
```bash
git clone https://github.com/facebookresearch/all-atom-diffusion-transformer /home/bdeng/projects/adit
```

## MCP Tool

| Tool | Description |
|---|---|
| `generate_structures` | Generate crystals (MP20) or molecules (QM9) unconditionally |

**Parameters**: `generation_type` (`crystals` / `molecules`), `num_structures`, `cfg_scale`, `batch_size`, `device`, `output_dir`

## Checkpoints

Pre-trained checkpoints are auto-downloaded from HuggingFace on first use:
- Repository: `chaitjo/all-atom-diffusion-transformer`
- `ckpts/ldm.ckpt` — Latent diffusion model
- `ckpts/vae.ckpt` — Variational autoencoder

## Key Dependencies

| Package | Version |
|---|---|
| Python | 3.10 |
| torch | 2.9.1+cu130 |
| torch-geometric | 2.7.0 |
| lightning | 2.4.0 |
| e3nn | 0.5.1 |
| pymatgen, ase | latest |

## Post-Clone Patches

After cloning the AADT repository, apply these patches to allow inference without `openbabel` (which is only needed for evaluation, not generation):

1. **`src/eval/molecule_reconstruction.py`** — Make `openbabel` import optional:
```python
# Replace (line ~21):
#   from openbabel import openbabel
#   openbabel.obErrorLog.StopLogging()
# With:
try:
    from openbabel import openbabel
    openbabel.obErrorLog.StopLogging()
except ImportError:
    openbabel = None
```

2. **`src/eval/molecule_generation.py`** — Make `openbabel` and `posebusters` imports optional:
```python
# Replace (line ~11):
#   from openbabel import openbabel
#   from posebusters import PoseBusters
# With:
try:
    from openbabel import openbabel
    openbabel.obErrorLog.StopLogging()
except ImportError:
    openbabel = None
try:
    from posebusters import PoseBusters
except ImportError:
    PoseBusters = None
```

3. **`src/models/vae_module.py`** — Defer evaluator instantiation to avoid openbabel at model load time:
```python
# In __init__ (line ~177), replace eager evaluator creation:
#   self.val_reconstruction_evaluators = { "mp20": ..., "qm9": MoleculeReconstructionEvaluator(), ... }
#   self.test_reconstruction_evaluators = { ... }
# With:
self.val_reconstruction_evaluators = None
self.test_reconstruction_evaluators = None

# In on_evaluation_epoch_start(), add lazy init before existing code:
if self.val_reconstruction_evaluators is None:
    self.val_reconstruction_evaluators = { ... }
if self.test_reconstruction_evaluators is None:
    self.test_reconstruction_evaluators = { ... }
```

## Notes

- The AADT repository is auto-discovered as a sibling directory (e.g. `../adit` relative to the project root)
- First run downloads ~1-2 GB of model checkpoints from HuggingFace
- ADiT supports **dataset-type** (crystals vs molecules) and **spacegroup** conditioning only — no composition or property conditioning
