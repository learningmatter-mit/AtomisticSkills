---
name: ml-mace-finetune
description: Fine-tune MACE machine learning interatomic potentials on custom datasets.
category: [machine-learning]
---
# MACE Fine-tuning

## Goal
To evaluate and improve the accuracy of a foundation MACE potential for a specific chemical system or physical property using the provided Python fine-tuning script and data-augmentation.

## Instructions

1.  **Prepare Labeled Dataset**: Obtain diverse structures with high-fidelity labels (energy, forces, stress). See the `/benchmark-finetuning` workflow for details.
2.  **Custom Data Conversion**: Read the source data format and write a customized conversion script if needed, formatting it for the subsequent preparation step.
3.  **Benchmarking**: Predict results on the new labels and benchmark the foundation model using [ml-mlip-benchmark](../ml-mlip-benchmark/SKILL.md).
16. **Data Preparation**: Execute `scripts/prepare_mace_data.py` to convert JSON structures to `.xyz` data files.
17. **Config Generation**: Execute `scripts/generate_mace_config.py` using the `.xyz` data to produce `finetune_config.yaml`.
18. **Fine-Tuning**: Execute `mace_run_train --config /path/to/finetune_config.yaml` to begin fine-tuning natively on the GPU.
19. **Validation**: Verify convergence and compare against the benchmarked foundation metrics.
20. **Registration**: Use the `register_model` tool to register the newly fine-tuned model checkpoint into the local registry so future research tasks can discover and reuse it.

## Training Configuration

MACE fine-tuning is divided into a data preparation step, a configuration generation step, and a standard native training run. The script `scripts/prepare_mace_data.py` generates `.xyz` files, and `scripts/generate_mace_config.py` converts arguments into a fully-formed `finetune_config.yaml` configuration compatible with the MACE default parser.

### Basic Arguments (Data Prep Script)

| Key | Type | Default | Description |
|:----|:-----|:--------|:------------|
| `--data` | str | (Required) | Path to JSON file containing ASE/pymatgen structure dictionaries |
| `--output-dir` | str | `./fine_tuning_data` | Directory to save the converted .xyz data |
| `--val-split` | float | 0.1 | Fraction of data to set aside for validation |
| `--seed` | int | 42 | Random seed for validation splitting |
| `--vasp-stress-conversion`| flag | - | If set, multiplies stress values by -1/160.2x to convert VASP raw kB to eV/Å³ |

### Basic Arguments (Configuration Generation Script)

| Key | Type | Default | Description |
|:----|:-----|:--------|:------------|
| `--train-file` | str | (Required) | Path to the converted `train.xyz` data |
| `--valid-file` | str | None | Path to the `valid.xyz` data |
| `--model` | str | `MACE-MP-small` | Base model name or path to a checkpoint |
| `--epochs` | int | 100 | Number of training epochs |
| `--lr` | float | 0.01 | Peak learning rate for training |
| `--batch-size` | int | 2 | Training batch size |
| `--output-dir` | str | `./fine_tuning` | Directory to save the fine-tuned model and logs |
| `--device` | str | `cuda` | Target compute device (`cuda` or `cpu`) |

> [!NOTE]
> If you have created a dedicated research directory for your current workflow (e.g. using the `create_research_dir` tool), you should set the `--output-dir` argument to a folder within that active research directory to keep all artifacts and models organized.

### Model Freezing and Heads (Configuration Generation Script)

| Key | Type | Default | Choices | Description |
|:----|:-----|:--------|:--------|:------------|
| `--freeze-backbone` | flag | N/A | Add flag | Freeze backbone (interaction blocks); only readout heads are trained. |
| `--reinit-head` | flag | N/A | Add flag | Re-initialize readout weights. When absent (default), pre-trained readout is preserved. |
| `--multiheads` | flag | N/A | Add flag | Enable multi-head fine-tuning (adds new head while keeping existing ones). |

### Advanced Parameters (Manual YAML Injection)

> [!IMPORTANT]
> The following parameters govern Optimizer, Regularization, and Scheduling. They are **NOT** exposed via the `prepare_mace_data.py` CLI. Note that `prepare_mace_data.py` exposes `--energy-weight`, `--forces-weight` (default 10.0), and `--stress-weight` which inject cleanly into the initial YAML. For all other properties below, you must manually append the keys to the generated `finetune_config.yaml` file prior to running `mace_run_train`. 

#### Optimizer & Regularization

| Key | Type | Default | Choices / Range | Description |
|:----|:-----|:--------|:----------------|:------------|
| `optimizer` | str | `"adam"` | `"adam"`, `"adamw"`, `"schedulefree"` | Optimizer type. |
| `weight_decay` | float | 5e-7 | ≥0 | L2 weight decay. |
| `amsgrad` | bool | True | `True`, `False` | Use AMSGrad variant of Adam. |
| `clip_grad` | float | 10.0 | >0 or None | Maximum gradient norm for clipping. Set to None to disable. |
| `ema` | bool | True | `True`, `False` | Enable exponential moving average of model weights. |
| `ema_decay` | float | 0.99 | 0–1 | EMA decay rate. Higher = more smoothing. |

### LR Scheduler

| Key | Type | Default | Choices / Range | Description |
|:----|:-----|:--------|:----------------|:------------|
| `scheduler` | str | `"ReduceLROnPlateau"` | `"ReduceLROnPlateau"`, `"ExponentialLR"` | LR scheduler type. |
| `lr_factor` | float | 0.8 | 0–1 | Factor by which LR is reduced on plateau (for ReduceLROnPlateau). |
| `scheduler_patience` | int | 50 | ≥1 | Epochs without improvement before reducing LR (for ReduceLROnPlateau). |
| `lr_scheduler_gamma` | float | 0.9993 | 0–1 | Per-epoch multiplicative decay factor (for ExponentialLR). |

**ReduceLROnPlateau** (default): Monitors validation loss. When loss stops improving for `scheduler_patience` epochs, LR is multiplied by `lr_factor`.

**ExponentialLR**: LR decays every epoch by `lr_scheduler_gamma`. At epoch *n*: `LR = learning_rate × lr_scheduler_gamma^n`.

### Early Stopping

| Key | Type | Default | Choices / Range | Description |
|:----|:-----|:--------|:----------------|:------------|
| `patience` | int | 2048 | ≥1 | Stop training after this many epochs without improvement. |

> [!NOTE]
> Default `patience=2048` effectively disables early stopping. Set lower (e.g., 100–200) if you want to stop early.

### Loss Function

| Key | Type | Default | Choices | Description |
|:----|:-----|:--------|:--------|:------------|
| `loss` | str | `"weighted"` | `"weighted"`, `"universal"`, etc. | Loss function type. `"universal"` is auto-set by data script when stress data is detected. |
| `energy_weight` | float | 1.0 | ≥0 | Weight for energy loss (exposed via CLI). |
| `forces_weight` | float | 10.0 | ≥0 | Weight for forces loss (exposed via CLI). |
| `stress_weight` | float | 1.0 | ≥0 | Weight for stress loss (exposed via CLI). |
| `compute_forces` | bool | True | `True`, `False` | Include forces in training. |
| `compute_stress` | bool | False | `True`, `False` | Include stress in training (auto-enabled by data script). |

> [!WARNING]
> **Stress Units**: MACE expects stress in `eV/Å³`. Raw VASP stress obtained directly via some JSON files may be in kilo-Bar (`kB`), which is ~160x larger and will cause catastrophic training divergence. The Atomate2 MCP tool handles this conversion automatically when `convert_units=True`. However, if your JSON labels contain raw `kB` stress, you MUST pass the `--vasp-stress-conversion` flag to `scripts/prepare_mace_data.py` to automatically scale them by `-1/160.2x`. For more details on unit standardization, see @[.agents/skills/general-property-units/SKILL.md].

> [!WARNING]
> **Learning rate sensitivity for MACE-OMAT**: The official MACE docs recommend `lr=0.01` for MACE-MP-0, but MACE-OMAT-0-small requires `lr=1e-4` to avoid divergence. Higher values (1e-3, 0.01) cause catastrophic forgetting even with frozen backbone + EMA.

> [!IMPORTANT]
> The generated `finetune_config.yaml` maps exactly to `mace_run_train` arguments. You can open and manually modify the YAML file before running `mace_run_train` to inject any advanced parameter.

- [MACE Si-O fine-tuning with frozen backbone](examples/mace-sio-frozen/) — MACE-OMAT-0-small, 10 epochs

Usage:
```bash
# 1. Prepare Data
conda run -n mace-agent python .agents/skills/ml-mace-finetune/scripts/prepare_mace_data.py \
    --data /path/to/training_data.json \
    --output-dir ./mace_finetuned_data

# 2. Generate Configuration
conda run -n mace-agent python .agents/skills/ml-mace-finetune/scripts/generate_mace_config.py \
    --train-file ./mace_finetuned_data/train.xyz \
    --valid-file ./mace_finetuned_data/valid.xyz \
    --model MACE-OMAT-0-small \
    --epochs 10 \
    --lr 1e-4 \
    --batch-size 2 \
    --freeze-backbone \
    --output-dir ./mace_finetuned

# 3. Run Training
conda run -n mace-agent mace_run_train --config ./mace_finetuned/finetune_config.yaml

# 4. Extract Training Logs (Optional, to create standard training_history.json)
conda run -n base-agent python .agents/skills/ml-mace-finetune/scripts/extract_mace_logs.py \
    --results-dir ./mace_finetuned/results
```

## Examples

See the [mace-wbm-finetune](examples/mace-wbm-finetune/README.md) directory for a complete, runnable example of 10-epoch fine-tuning on high-energy crystal structures (WBM dataset), including exact usage of the `--vasp-stress-conversion` flag and diagnostic output artifacts.

## Constraints
- **Data Size**: For small datasets (<500 structures), `freeze_backbone=True` is strongly recommended.
- **Reference Energies (E0s)**: If your fine-tuning data is computed using the same DFT functional (e.g., PBE) as the foundation model's original training data, you should reuse the foundation model's original isolated atom reference energies (E0s) instead of re-fitting them. This maintains thermodynamic compatibility across the periodic table for elements not in your fine-tuning set.
- **Units (input)**: Stress labels must be in eV/Å³ as per project standards.
- **Units (output)**: All `training_history.json` files use **meV** units: energy MAE in meV/atom, force MAE in meV/Å, stress MAE in meV/Å³.

---

**Author:** Bowen Deng  
**Contact:** [GitHub @bowen-bd](https://github.com/bowen-bd)
