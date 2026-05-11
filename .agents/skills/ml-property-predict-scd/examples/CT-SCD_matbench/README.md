# CT-SCD_matbench Tutorial

This directory contains a small example showing how to fine-tune the pretrained `ct-scd-amp` checkpoint on the Matbench `MBgap` task using the native `SelfConditionedDenoisingAtoms/train.py` entrypoint and the upstream `configs/finetune_matbench.yaml` recipe.

This example mirrors the intended upstream flow:

```bash
python train.py --conf configs/finetune_matbench.yaml --load-hf ct-scd-amp --job-id CT-SCD_matbench_fold0
```

## Important Availability Note

The public `SelfConditionedDenoisingAtoms/README.md` explicitly notes that `configs/finetune_matbench.yaml` depends on the unreleased `StructureCloud` utilities. Treat this example as the correct pattern for checkouts where the Matbench dataset wrapper is available, not as a guaranteed public quickstart.

## Contents

1. `run_ct_scd_matbench.py`: a wrapper script that locates the `SelfConditionedDenoisingAtoms` checkout, relaunches itself inside the `scd-agent` environment when needed, and runs a safe smoke test by default.

## Running the Example

From a general environment, let the script restart itself inside `scd-agent`:

```bash
python run_ct_scd_matbench.py --dry-run
```

Inside `scd-agent`, you can run it directly:

```bash
python run_ct_scd_matbench.py
```

Use `--dry-run` first to confirm the resolved config, fold, and dataset wrapper without launching training:

```bash
python run_ct_scd_matbench.py --dry-run --fold 2
```

Before launching, check GPU availability and current usage. As with the QM9 example, preferring live stdout over buffered wrappers is general guidance for SCD runs, not just this script:

```bash
nvidia-smi
```

On shared machines, prefer a GPU with no active compute job and low memory usage. Do not assume that a low-utilization GPU is free if another process already has memory allocated.

To run on one selected GPU:

```bash
conda run --no-capture-output -n scd-agent env WANDB_MODE=offline CUDA_VISIBLE_DEVICES=2 python -u run_ct_scd_matbench.py --num-steps 2 --val-interval 1
```

To run on all selected visible GPUs:

```bash
conda run --no-capture-output -n scd-agent env WANDB_MODE=offline CUDA_VISIBLE_DEVICES=0,1,2,3 python -u run_ct_scd_matbench.py --num-steps 2 --val-interval 1 --use-all-visible-gpus
```

The wrapper defaults to a single visible GPU unless `--use-all-visible-gpus` is requested.

For smoke tests without a live W&B session, pass:

```bash
python run_ct_scd_matbench.py --wandb-mode offline
```

For W&B online mode, first log in inside `scd-agent`:

```bash
conda run -n scd-agent wandb login
```

Then launch without `WANDB_MODE=offline`, or set `WANDB_MODE=online` explicitly.

By default this example performs a short smoke test with `--num-steps 100`. To launch the full upstream schedule instead:

```bash
python run_ct_scd_matbench.py --full-run
```

For the quickest smoke tests, consider copying `configs/finetune_matbench.yaml` into a task-specific smoke config and disabling expensive reporting such as `parity_plot` if you add it. Short `max_steps` runs can still spend significant time in evaluation or plotting callbacks.

The example uses Matbench fold `0` by default. To change folds:

```bash
python run_ct_scd_matbench.py --fold 1
python run_ct_scd_matbench.py --fold 2
```

## Other Matbench Properties

In the current upstream recipe, `finetune_matbench.yaml` is specifically wired for `dataset: MBgap`, and `dataset_arg` selects the fold rather than the property.

To train on another Matbench property:

1. create a sibling dataset wrapper in `SelfConditionedDenoisingAtoms/data/datasets/matbench.py` similar to `mbench_gap`, but pointing to another task from `MBDataset_base.avail_tasks`
2. export that new wrapper from `SelfConditionedDenoisingAtoms/data/datasets/__init__.py`
3. copy `configs/finetune_matbench.yaml` into a new task-specific config YAML
4. run this example script with `--dataset-class <NewWrapper>` and `--config <new_config.yaml>`

For example, once a new wrapper is exported:

```bash
python run_ct_scd_matbench.py --dataset-class MBdielectric --config configs/finetune_matbench_dielectric.yaml
```

## Notes

- Actual training requires a CUDA-visible GPU. On CPU-only hosts the wrapper now exits early with a clear message instead of letting `train.py` fail later inside PyTorch Lightning.
- If the default Matplotlib config directory is not writable, the wrapper automatically uses a temporary `MPLCONFIGDIR`.
- This example follows the upstream material finetuning settings: `noise_in_loader=True`, `allow_periodic=True`, and `set_head_agg: mean`.
- The default target environment is `scd-agent`, matching the environment created in `AtomisticSkills/conda-envs/scd-agent`.
- Training outputs are written under `SelfConditionedDenoisingAtoms/experiments/<job_id>`.
- The W&B project is derived by `train.py` from the dataset class name, so the default `MBgap` run appears under `SCD_bench_MBgap`.
- On this public checkout, the Matbench dataset path still depends on `StructureCloud`, so W&B login alone is not enough to make the example runnable.
- As with QM9, live stdout is the best way to distinguish real startup work from a genuine hang.
