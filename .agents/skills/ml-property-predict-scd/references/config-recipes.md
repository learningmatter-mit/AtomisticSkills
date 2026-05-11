# Config Recipes

Use the nearest public config as the base case, then change only the fields required by the new dataset and task.

## Molecular SCD pretraining

Closest public baseline:
`configs/pretrain_pcq.yaml`

Expected settings:

- `pretraining: true`
- `self_cond: true`
- `dataset: <new_dataset_name>`
- `energy_weight: 0.0`
- `force_weight: 1.0`
- `denoising_weight: 1.0`
- `noise_scale: 0.04`
- `allow_periodic: false`

Graph mode choice:

- compiled extension available:
  `noise_in_loader: false`
- no compiled extension:
  `noise_in_loader: true`

## Periodic materials SCD pretraining

Closest public baseline:
`configs/pretrain_amp20.yaml`

Expected settings:

- `pretraining: true`
- `self_cond: true`
- `allow_periodic: true`
- `noise_in_loader: true`
- `graph_cutoff: 5.0`
- `max_neighbors: 32`
- optional cell augmentation:
  `p_cell_repeat`, `cell_repeat_iters`, `rep_min_atoms`

## Lightweight frozen-backbone training

This is a custom-script workflow, not a native `train.py --conf ...` workflow.

Use `templates/train_lightweight_head.py` and choose one of three modes.

### 1. `scalar_head`

Recommended choices:

- `--head-mode scalar_head`
- load `ct-scd-pcq` for molecules or `ct-scd-amp` for materials
- use `--reset-head` for a fresh native scalar head on the new target
- use `--set-head-agg sum` or `--set-head-agg mean` depending on the target
- explicitly freeze non-`scalar_head` parameters in the script
- optionally add `--standardize-targets` for typical scalar regression tasks

This path is best for invariant scalar regression.

### 2. `atom_emb_mlp`

Recommended choices:

- `--head-mode atom_emb_mlp`
- choose `--pool sum` or `--pool mean`
- use `--mlp-layers 1` or `2`
- keep the backbone frozen and train only the MLP head
- optionally add `--standardize-targets` for scalar regression

### 3. `mol_emb_mlp`

Recommended choices:

- `--head-mode mol_emb_mlp`
- use `--mlp-layers 1` or `2`
- keep the backbone frozen and train only the MLP head
- optionally add `--standardize-targets` for scalar regression

Graph mode choice for all lightweight modes:

- molecules with compiled extension:
  `noise_in_loader: false`, `allow_periodic: false`
- molecules without compiled extension:
  `noise_in_loader: true`, `allow_periodic: false`
- periodic materials:
  `noise_in_loader: true`, `allow_periodic: true`

## SMILES-based molecular datasets

SMILES-only datasets are not directly ready for SCD. They must first be converted into 3D atomistic structures with `z` and `pos`.

Recommended default:

- use RDKit conformer generation for relatively small, drug-like molecules
- keep this in the dataset loader only when conformer generation is reliable enough for on-the-fly use

Common failure modes:

- invalid SMILES
- unsupported or unusual chemistry
- very large or hard-to-embed molecules

In practice, these datasets may need preprocessing, retry logic, explicit failure logging, and/or filtering before training becomes stable.

See `templates/generate_conformer_rdkit.py` for a simple conformer-generation example.

## Molecular full-model finetuning

Closest public baseline:
`configs/finetune_qm9.yaml`

Expected settings:

- `pretraining: false`
- `self_cond: false`
- `dataset: <new_dataset_name>`
- W&B project naming follows `dataset` through `train.py`, which currently maps this to `SCD_bench_{dataset}` for finetuning runs.
- Set the specific W&B run identifier with `job_id` in the config or via CLI override; `train.py` uses it for both the W&B `name` and `id`.
- `standardize: true` for most scalar regression targets
- choose checkpoint:
  `--load-hf ct-scd-pcq`
- `allow_periodic: false`
- `noise_in_loader: false` if the TorchMD extension is built, otherwise `true`

Reasonable downstream defaults:

- `reset_head: true`
- `reset_embeddings: false`

Those reset recommendations are practical defaults inferred from the code path, not explicit upstream documentation.

General practical additions:

- prefer creating a new finetuning config YAML for each new task or experiment family instead of editing a shared baseline in place
- set `allow_test_clipping: false` when you need the cleanest possible validation/test comparability
- if evaluation depends on stochastic dataset behavior, decide explicitly whether to keep single-pass evaluation or implement repeated-pass aggregation outside the default recipe
- for smaller finetuning datasets, especially around 10k samples or fewer, consider stronger regularization such as higher `weight_decay` and/or higher droppath settings than the large-dataset defaults

## Materials full-model finetuning

Do not treat `configs/finetune_matbench.yaml` as the public baseline unless `StructureCloud` is available.

Instead:

1. start from `templates/finetune_config.template.yaml`
2. set `allow_periodic: true`
3. set `noise_in_loader: true`
4. set `graph_cutoff`, `max_neighbors`, and any cell-repeat augmentation fields
5. load the materials checkpoint with `--load-hf ct-scd-amp`

## Force-aware finetuning

Patterns exist in `models/trainer.py`, `data/datasets/md17.py`, and `data/datasets/omol25.py`.

Key switches:

- `derivative: true`
  predict energy and derive forces
- `direct_force_pred: true`
  predict forces directly from the denoising head

Only enable one intentionally.

## Batch clipping

If large systems cause OOM:

```yaml
max_nodes_per_batch: 4000
batch_clipper_cache_size: 1000
allow_test_clipping: false
```

Prefer disabling test clipping for strict evaluation comparability.

## Good first-run commands

### New molecular pretraining config

```bash
python train.py --conf configs/my_pretrain.yaml --job-id smoke_pretrain --num-steps 2000 --val-interval 1
```

### Scalar-head-only lightweight adaptation

```bash
python templates/train_lightweight_head.py --head-mode scalar_head --model-name ct-scd-pcq --dataset QM9 --dataset-root tmp/qm9 --dataset-arg homo --reset-head --set-head-agg mean --standardize-targets
```

### Pooled-atom-embedding MLP adaptation

```bash
python templates/train_lightweight_head.py --head-mode atom_emb_mlp --model-name ct-scd-pcq --dataset QM9 --dataset-root tmp/qm9 --dataset-arg homo --pool mean --mlp-layers 2 --standardize-targets
```

### `mol_emb` MLP adaptation

```bash
python templates/train_lightweight_head.py --head-mode mol_emb_mlp --model-name ct-scd-pcq --dataset QM9 --dataset-root tmp/qm9 --dataset-arg homo --mlp-layers 2 --standardize-targets
```

### New molecular full-model finetuning config from a public checkpoint

```bash
python train.py --conf configs/my_finetune.yaml --load-hf ct-scd-pcq --job-id smoke_ft --num-steps 2000 --val-interval 1
```

### New materials full-model finetuning config from a public checkpoint

```bash
python train.py --conf configs/my_finetune.yaml --load-hf ct-scd-amp --job-id smoke_ft --num-steps 2000 --val-interval 1
```

Put overrides after `--conf`.

## Minimal smoke test

For a new public finetuning config, prefer a first run like:

```bash
python train.py --conf configs/my_finetune.yaml --job-id smoke_ft --num-steps 100 --val-interval 1
```

Use this before committing to the full schedule.
