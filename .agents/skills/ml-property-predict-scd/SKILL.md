---
name: ml-property-predict-scd
description: Train a model to predict custom properties of molecules or periodic materials using pretrained SelfConditionedDenoisingAtoms (SCD) foundation models.
category: [machine-learning, materials, chemistry]
---

# ml-property-predict-scd

## Goal

Use `SelfConditionedDenoisingAtoms` for four related workflows:

- apply a frozen SCD checkpoint as a live atomistic encoder
- train a lightweight head on top of a frozen SCD backbone
- fine-tune an entire pretrained SCD checkpoint on a new property task
- pretrain a new SCD model or add a new dataset adapter

## First Checks

1. Use the `scd-agent` environment from `conda-envs/scd-agent/`.
2. Confirm the upstream repo exists at `../SelfConditionedDenoisingAtoms` relative to `AtomisticSkills`, or create it with `conda-envs/scd-agent/install.sh`.
3. Read the upstream `README.md` and `examples.ipynb`.
4. Then read the local references in this skill:
   - `references/repo-map.md`
   - `references/transfer-recipes.md`
   - `references/config-recipes.md`
   - `references/dataset-contract.md` if a new dataset is involved

## Checkpoint Selection

- Use `ct-scd-pcq` for molecule property prediction, molecule embeddings, and molecule-side transfer learning.
- Use `ct-scd-amp` for materials property prediction, periodic materials embeddings, and materials-side transfer learning.

Do not swap these by default. The public checkpoints were pretrained on different domains.

## Instructions

### 1. Frozen backbone embeddings

Default to `out["mol_emb"]` for graph-level downstream ML.

- Use `return_atom_embs=True` only when the downstream task needs atom- or site-level features.
- Keep the checkpoint frozen and in `eval()` mode.
- Disable the denoising head for this workflow to avoid wasted compute.
- Pass `graph_batch=batch` only when `allow_periodic` or `noise_in_loader` is enabled. Do not force `graph_batch` on the fast molecular path.
- Reuse `templates/extract_embeddings.py` as the starting point. It keeps the model live and returns embeddings on demand instead of defaulting to a frozen feature dump.

### 2. Lightweight training with a frozen SCD backbone

Use `templates/train_lightweight_head.py` for three lightweight options:

1. `scalar_head`
   Appropriate for invariant scalar regression targets. This path trains only the model's native `scalar_head` using pretrained backbone weights.
2. `atom_emb_mlp`
   Pools `atom_embs` with `sum` or `mean`, then trains a 1- or 2-layer MLP head.
3. `mol_emb_mlp`
   Uses `mol_emb` directly, then trains a 1- or 2-layer MLP head.

Important details:

- `scalar_head` is usually the lightest path for standard scalar property prediction.
- `reset_head()` is a sensible default for `scalar_head` mode when switching to a new target.
- `set_head_agg` controls the native scalar-head reduction and should be set through the checkpoint-loading path, not by editing tensors after the fact.
- the upstream model exposes `finetune()` and `reset_head()`, but `finetune()` does not by itself implement scalar-head-only training; explicitly freeze non-`scalar_head` parameters in the lightweight script.
- the lightweight `scalar_head` path should reset the checkpoint's output affine buffers to identity because pretrained `mean/std` buffers are not downstream target statistics.
- for `atom_emb_mlp`, either `sum` or `mean` pooling may work better depending on whether the target behaves more like an extensive or intensive quantity.
- `atom_emb_mlp` and `mol_emb_mlp` should compute frozen-backbone features on the fly, not treat a static embedding cache as the default workflow.
- `mol_emb_mlp` is the cleanest external-head baseline on the pretrained graph representation.

### 3. Full-model finetuning

Use the native training path when you want all model weights updated:

```bash
# Env: scd-agent
cd ../SelfConditionedDenoisingAtoms
python train.py --conf configs/my_finetune.yaml --load-hf ct-scd-pcq --job-id my_run
```

or

```bash
# Env: scd-agent
cd ../SelfConditionedDenoisingAtoms
python train.py --conf configs/my_finetune.yaml --load-hf ct-scd-amp --job-id my_run
```

Start from:

- `templates/finetune_config.template.yaml`
- `configs/finetune_qm9.yaml` for public molecular examples

For public materials finetuning, do not rely on `configs/finetune_matbench.yaml` unless the private `StructureCloud` dependency is available. Copy the template and configure the periodic settings yourself.

Full-model finetuning usually gives better results than the lightweight frozen-backbone options, but it costs more GPU memory and more wall time.

### 4. Pretraining from scratch

Use the native training path:

```bash
# Env: scd-agent
cd ../SelfConditionedDenoisingAtoms
python train.py --conf configs/my_pretrain.yaml --job-id my_pretrain
```

Start from:

- `templates/pretrain_config.template.yaml`
- `configs/pretrain_pcq.yaml` for molecules
- `configs/pretrain_amp20.yaml` for periodic materials

## Dataset Onboarding

When adding a new dataset class under `SelfConditionedDenoisingAtoms/data/datasets/`:

1. Start from `templates/dataset_template.py`.
2. Preserve the constructor signature `__init__(root, dataset_arg=None, transform=None, **kwargs)`.
3. Return `torch_geometric.data.Data` objects with the required fields for the training mode.
4. Expose a stable per-sample identifier such as `idx` and optionally a human-readable `identifier` on each `Data` object when practical.
5. Export the dataset from `data/datasets/__init__.py`, or `train.py --dataset ...` will reject it.
6. If the task needs dataset-specific config knobs beyond `root`, `dataset_arg`, and `transform`, wire them through `train.py` argparse and `data/loaders.py`.
7. Prefer creating a new run config YAML instead of editing a shared baseline config in place. This makes experiment tracking and diffs much clearer.
8. Add the new config file and smoke-test the run with a short `--num-steps` override.

## Smoke Test

Before launching a full run:

1. check `nvidia-smi` first to confirm CUDA-visible GPUs exist on the real machine and to see whether another job is already using them
2. ask the user whether they want a single GPU or all available GPUs before choosing device placement
3. if the user wants a single GPU, prefer a GPU with no active compute process and low memory usage instead of one that is already busy
4. import the dataset class successfully in the target environment
5. instantiate one dataset split and inspect one sample
6. build one dataloader batch through `data/loaders.py`
7. run a short `train.py --conf ... --num-steps 100` or `200` check while actively watching live command-line output
8. confirm checkpoints and W&B logging land in the expected run directory

Treat live stdout visibility as general guidance for SCD runs, not just these example wrappers. When possible, launch smoke tests and full runs with unbuffered stdout and without command-capture layers so startup messages stay visible.

- Use `nvidia-smi` both before launch and during launch: before launch to choose devices, during launch to verify the intended GPU or GPUs are actually being used.
- Do not default to grabbing every GPU on a shared workstation. Ask first.
- Prefer `python -u ...` and a TTY-capable shell session for smoke runs.
- If using `conda run`, prefer `conda run --no-capture-output ...` so dataset downloads, checkpoint downloads, split generation, and normalization work are visible immediately.
- Treat an initially quiet terminal as ambiguous until you have checked live stdout. For first-run workflows, several minutes of startup can be legitimate while data or checkpoints are prepared.
- For the fastest smoke tests, copy the target config and disable expensive reporting such as `parity_plot: true` before launching. Otherwise a `max_steps=2` run can still spend significant extra time on parity-plot generation and repeated evaluation passes.
- Expect QM9-like runs to spend real wall time computing dataset `mean/std`, sometimes more than once across train and test setup. This is startup work, not necessarily a hang.
- When launching on one physical GPU, set `CUDA_VISIBLE_DEVICES=<gpu_id>` and pass `--use-devices 0` so the upstream trainer uses only that logical device.
- When launching on multiple GPUs, set `CUDA_VISIBLE_DEVICES` to the chosen physical ids and pass `--use-devices 0 1 ...` across the visible logical devices.

## Examples

Check the detailed, reproducible examples in the `examples/` directory:
- [QM9 Lightweight Tuning](examples/CT-SCD_QM9/README.md): Finetuning example on molecular targets.
- [Matbench Lightweight Tuning](examples/CT-SCD_matbench/README.md): Finetuning example on periodic materials.

## Constraints

- **Environments**: Scripts require the `scd-agent` Conda environment. Each code block MUST specify the environment.

- `train.py` always creates a `WandbLogger`.
- For finetuning runs, `train.py` derives the W&B project from the config `dataset` field, currently as `SCD_bench_{dataset}`.
- The W&B run `name` and `id` both come from `job_id`, so set the specific run identifier in the config file or override it on the CLI.
- `train.py` is configured with `accelerator="gpu"`.
- Native `train.py` handles standard pretraining and finetuning loops well, but special prediction/export flows or custom evaluation loops may still need a small wrapper script.
- `noise_in_loader: true` is required for periodic materials and is the fallback when the optional TorchMD CUDA extension is not built.
- Public repo examples cover `PCQM4MV2`, `AlexMP20`, `QM9`, `MD17`, and `OMOL25` best.
- The public checkpoints are downloaded as `last.ckpt` files from Hugging Face.
- The upstream pretraining path freezes the scalar head, so `reset_head: true` is a reasonable downstream default when switching to a new scalar property during full-model finetuning. That is an inference from the code path, not a documented upstream requirement.

## Troubleshooting

- Unknown keys in a run YAML fail fast during `--conf` parsing.
- A dataset is not selectable from `--dataset` until it is exported from `data/datasets/__init__.py`.
- If the TorchMD extension is not built, prefer `noise_in_loader: true` for molecular runs.
- The default trainer is GPU-oriented, so verify the intended environment before debugging dataset code.
- If a run appears to hang at startup, first rerun it with visible live stdout before assuming the trainer is stuck. First-use QM9 or checkpointed runs may still be downloading data, creating splits, or computing dataset statistics.
- If GPU availability is unclear, rerun `nvidia-smi` outside any restrictive sandbox before concluding that CUDA is unavailable.
- If the workstation is shared, check `nvidia-smi` memory use and active compute processes before choosing devices. A GPU with near-zero utilization but several GiB already allocated may still belong to another live job.
- `wandb status` may be inconclusive even when online login works through `~/.netrc`. If you need certainty, run a tiny online `wandb.init(..., mode="online")` probe or observe the live W&B login lines during a real run.

## References

- SelfConditionedDenoisingAtoms reference implementation.

---

**Author:** Ty Perez  
**Contact:** [tyjperez@gmail.com](mailto:tyjperez@gmail.com)
