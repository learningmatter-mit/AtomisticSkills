# CT-SCD_QM9 Tutorial

This directory contains a small, practical example showing how to fine-tune the pretrained `ct-scd-pcq` checkpoint on the QM9 `homo` property using the native `SelfConditionedDenoisingAtoms/train.py` entrypoint and the upstream `configs/finetune_qm9.yaml` recipe.

The example follows the public `SelfConditionedDenoisingAtoms/README.md` finetuning instructions:

```bash
python train.py --conf configs/finetune_qm9.yaml --load-hf ct-scd-pcq --job-id scd-pcq_qm9-homo
```

## Contents

1. `run_ct_scd_qm9.py`: a wrapper script that locates the `SelfConditionedDenoisingAtoms` checkout, relaunches itself inside the `scd-agent` environment when needed, and runs a safe smoke test by default.

## Running the Example

From a general environment, let the script restart itself inside `scd-agent`:

```bash
python run_ct_scd_qm9.py --dry-run
```

Inside `scd-agent`, you can run it directly:

```bash
python run_ct_scd_qm9.py
```

For first-run smoke tests, prefer observing live stdout instead of launching through buffered wrappers. This is general guidance for SCD runs, not just this example. A good pattern is:

```bash
conda run --no-capture-output -n scd-agent env WANDB_MODE=offline CUDA_VISIBLE_DEVICES=0 python -u run_ct_scd_qm9.py --num-steps 2 --val-interval 1
```

This makes checkpoint downloads, dataset downloads, split creation, and normalization startup visible in the terminal.

Before launching, check GPU availability and current usage:

```bash
nvidia-smi
```

On shared machines, prefer a GPU with no active compute job and low memory usage. Do not assume that a low-utilization GPU is free if another process already has memory allocated.

If you want one selected GPU, expose it explicitly:

```bash
conda run --no-capture-output -n scd-agent env WANDB_MODE=offline CUDA_VISIBLE_DEVICES=2 python -u run_ct_scd_qm9.py --num-steps 2 --val-interval 1
```

If you want all selected visible GPUs, expose them and tell the wrapper to use them all:

```bash
conda run --no-capture-output -n scd-agent env WANDB_MODE=offline CUDA_VISIBLE_DEVICES=0,1,2,3 python -u run_ct_scd_qm9.py --num-steps 2 --val-interval 1 --use-all-visible-gpus
```

The wrapper defaults to a single visible GPU unless `--use-all-visible-gpus` is requested.

Use `--dry-run` first to verify the resolved command, repo root, and conda environment without launching training:

```bash
python run_ct_scd_qm9.py --dry-run --property gap
```

For smoke tests on a machine where you do not want to log into W&B, pass:

```bash
python run_ct_scd_qm9.py --wandb-mode offline
```

By default this example performs a short smoke test with `--num-steps 100`. To launch the full upstream schedule instead:

```bash
python run_ct_scd_qm9.py --full-run
```

For the quickest smoke tests, consider copying `configs/finetune_qm9.yaml` into a task-specific smoke config and setting `parity_plot: false`. The upstream QM9 recipe enables parity plots, which can add noticeable extra runtime even after `max_steps` is reached.

## Other QM9 Properties

The script exposes `--property`, which maps directly to `--dataset-arg` for the QM9 loader. For example:

```bash
python run_ct_scd_qm9.py --property lumo
python run_ct_scd_qm9.py --property gap
python run_ct_scd_qm9.py --property cv
```

Common QM9 property names from `data/datasets/qm9.py` include:

- `alpha`
- `homo`
- `lumo`
- `gap`
- `zpve`
- `cv`
- `mu`
- `R2`
- `u0`
- `u298`
- `h298`
- `g298`
- `u0_atom`
- `u298_atom`
- `h298_atom`
- `g298_atom`

For most QM9 targets, changing `--property` is the main change. For targets with different normalization or prior behavior, inspect `SelfConditionedDenoisingAtoms/data/datasets/qm9.py` and consider copying `configs/finetune_qm9.yaml` into a new task-specific config YAML before a full run.

If you create a task-specific config, pass it with `--config`:

```bash
python run_ct_scd_qm9.py --property lumo --config configs/finetune_qm9_lumo.yaml
```

## Notes

- Actual training requires a CUDA-visible GPU. On CPU-only hosts the wrapper now exits early with a clear message instead of letting `train.py` fail later inside PyTorch Lightning.
- If the default Matplotlib config directory is not writable, the wrapper automatically uses a temporary `MPLCONFIGDIR`.
- If the TorchMD compiled graph kernel is not built, the wrapper automatically adds `--noise_in_loader True`, matching the upstream README guidance.
- The default target environment is `scd-agent`, matching the environment created in `AtomisticSkills/conda-envs/scd-agent`.
- Training outputs are written under `SelfConditionedDenoisingAtoms/experiments/<job_id>`.
- The W&B project for this example is derived by `train.py` from `dataset: QM9`, so it appears as `SCD_bench_QM9`.
- In practice, QM9 smoke runs can spend substantial startup time computing dataset normalization statistics before the short training loop begins.
