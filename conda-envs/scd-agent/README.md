# SCD Agent Environment

Environment for the `SelfConditionedDenoisingAtoms` repo and its public pretrained SCD checkpoints.

## Quick Installation

Most users should install with the bundled script:

```bash
bash install.sh
```

This will:

- create the `scd-agent` conda environment
- clone `https://github.com/TyJPerez/SelfConditionedDenoisingAtoms.git` into a sibling directory `../SelfConditionedDenoisingAtoms` if it is missing
- install PyTorch 2.6.0 wheels from the CUDA 12.4 index by default
- install PyG extension wheels and the remaining SCD dependencies
- skip the optional TorchMD graph-kernel build unless you request it

After installation:

```bash
conda activate scd-agent
```

## Custom Installation

You can override the default clone path or request the optional TorchMD kernel build:

```bash
SCD_REPO_DIR=/path/to/SelfConditionedDenoisingAtoms BUILD_TORCHMD_KERNEL=1 bash install.sh
```

## Important Environment Variables

- `SCD_REPO_DIR`: where the upstream repo should live. Default is a sibling checkout `../SelfConditionedDenoisingAtoms`.
- `SCD_REPO_URL`: alternate git remote. Default is `https://github.com/TyJPerez/SelfConditionedDenoisingAtoms.git`.
- `TORCH_INDEX_URL`: PyTorch wheel index. Default is `https://download.pytorch.org/whl/cu124`.
- `PYG_WHEEL_URL`: PyG extension wheel index. Default is `https://data.pyg.org/whl/torch-2.6.0+cu124.html`.
- `TORCH_PACKAGES`: override the PyTorch package string if you need a different CUDA or CPU build.
- `BUILD_TORCHMD_KERNEL`: set to `1` to compile `models/ET_models/setup.py`.

## Public Checkpoints

Use these checkpoints by default:

- `ct-scd-pcq`: molecular property prediction and molecular embeddings
- `ct-scd-amp`: materials property prediction and materials embeddings

They are public on Hugging Face and are downloaded on first use through either:

```bash
python train.py --conf <config>.yaml --load-hf ct-scd-pcq
python train.py --conf <config>.yaml --load-hf ct-scd-amp
```

or direct `hf_hub_download(...)` calls in Python.

## Weights & Biases

`train.py` always creates a `WandbLogger`, so decide before a run whether you want offline logging or online sync.

For online sync inside `scd-agent`, first log in with one of these patterns:

```bash
conda activate scd-agent
wandb login
```

or, without activating the environment:

```bash
conda run -n scd-agent wandb login
```

If you prefer non-interactive setup on a remote machine, set an API key explicitly:

```bash
conda run -n scd-agent env WANDB_API_KEY=your_key_here wandb status
```

Useful checks:

```bash
conda run -n scd-agent wandb status
conda run -n scd-agent python -c "import os; print(bool(os.environ.get('WANDB_API_KEY')))"
```

`wandb status` may still report `api_key: null` even when credentials are successfully loaded from `~/.netrc`. If you need a definitive online check, run a tiny probe such as:

```bash
conda run --no-capture-output -n scd-agent python -c "import time, wandb; run = wandb.init(project='scd-agent-smoke', name=f'connectivity-{int(time.time())}', mode='online'); print(run.url); run.finish()"
```

Typical run modes:

- Offline: set `WANDB_MODE=offline`
- Online: either leave `WANDB_MODE` unset or set `WANDB_MODE=online` after logging in
- Disabled: set `WANDB_MODE=disabled` if you want local execution without W&B syncing

## Notes

- If you do not build the optional TorchMD kernel, set `noise_in_loader: true` for molecular training and inference configs.
- For periodic materials, use `noise_in_loader: true` and `allow_periodic: true`.
- `train.py` in the upstream repo assumes GPU training and always creates a `WandbLogger`.
- `configs/finetune_matbench.yaml` in the upstream repo depends on unreleased `StructureCloud` utilities. For new public materials tasks, start from a copied finetuning template instead of relying on that config directly.
