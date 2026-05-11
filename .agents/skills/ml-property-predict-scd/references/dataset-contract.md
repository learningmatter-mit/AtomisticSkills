# Dataset Contract

A new dataset adapter should match the constructor pattern already used by the repo:

```python
class MyDataset(Dataset):
    def __init__(self, root, dataset_arg=None, transform=None, **kwargs):
        ...
```

`data/loaders.py` instantiates datasets as:

```python
getattr(datasets, dataset_name)(dataset_root, dataset_arg=dataset_arg, transform=transform)
```

That constructor signature is the compatibility target.

If a new task needs extra dataset-specific options, adding `**kwargs` to the dataset alone is not enough. The relevant arguments must also be parsed in `train.py` and forwarded by `data/loaders.py`, unless you intentionally encode them inside `dataset_arg`.

## Minimum sample fields

Each `__getitem__` must return a `torch_geometric.data.Data` object.

### Always required

- `pos`
  tensor shaped `[N, 3]`
- `z`
  tensor shaped `[N]` with atomic numbers

### Required for supervised scalar prediction

- `y`
  tensor shaped `[1]` or `[T]`

### Required for energy-plus-force training

- `y`
  scalar energy target
- `dy`
  tensor shaped `[N, 3]`

### Required for periodic workflows

- `cell`
  tensor shaped `[1, 3, 3]`
- `pbc`
  tensor shaped `[1, 3]` of booleans

## Added automatically when missing

`AddStandardKeys()` in `data/datasets/transforms.py` can synthesize:

- `cell` for non-periodic data by building a bounding box
- `pbc` as all-false for non-periodic data
- `natoms`

That means a molecule loader can often return only `pos`, `z`, and optional targets.

## Optional dataset hooks

Implement these only when needed:

- `get_subset(split)`
  required when using `predefined_splits: true`
- `get_atomref(max_z=118)`
  needed if a config uses `prior_model: Atomref`
- `normalize()`
  can return dataset-specific `(mean, std)` to bypass the generic standardization pass

## Recommended metadata fields

These are not strictly required by the trainer, but they are broadly useful:

- `idx`
  stable integer sample id for evaluation, aggregation, and debugging
- `identifier`
  stable string id for export tables, challenge submissions, and human-readable inspection

## SMILES-only datasets

If a dataset starts from SMILES strings rather than atomistic coordinates, it must be converted into 3D structures before SCD training or finetuning.

Practical guidance:

- for relatively small, drug-like molecules, RDKit conformer generation is a reasonable default
- this can be done on the fly inside the dataset loader when the failure rate is low enough
- invalid SMILES, exotic chemistry, and very large molecules can make this path fragile
- expect some debugging, retry logic, or dataset filtering when conformer generation is part of the data pipeline

Use `templates/generate_conformer_rdkit.py` as a minimal starting point for SMILES-to-3D conversion.

## Transform compatibility

The datamodule applies transforms on every access. A dataset should:

- preserve arbitrary extra attributes on `Data`
- tolerate `transform=None`
- avoid mutating shared state inside `__getitem__`

For `noise_in_loader: true`, transforms may:

- add or overwrite `cell`, `pbc`, and `natoms`
- add graph fields like `edge_index`, `edge_distance`, and `edge_distance_vec`
- return tuple samples for self-conditioned workflows

Do not assume the transformed sample always remains a single `Data` object.

## Split strategy

### Random split datasets

Do nothing special. `DataModule.setup()` will create train, val, and test indices from dataset length.

### Dataset-defined splits

Implement `get_subset(split)` and set:

```yaml
predefined_splits: true
train_size: null
val_size: null
test_size: null
```

## Target-shape conventions

- single scalar property:
  prefer `y.shape == [1]`
- multiple targets:
  use `y.shape == [T]`, then select one with `dataset_arg` or a transform
- forces:
  use `dy.shape == [N, 3]`

`models/trainer.py` will unsqueeze one-dimensional `y` during loss computation.

## Recommended onboarding sequence

1. start from `templates/dataset_template.py`
2. adapt only the raw-data loading section first
3. export the class from `data/datasets/__init__.py`
4. wire any extra dataset-specific config arguments through `train.py` and `data/loaders.py`
5. add a config using the nearest finetune or pretrain template
6. run a short smoke test before the full job
