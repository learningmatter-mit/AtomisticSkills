---
name: ml-matgl-finetune
description: Fine-tune MatGL machine learning interatomic potentials on custom datasets.
category: [machine-learning]
---
# MatGL Fine-tuning

## Goal
To evaluate and improve the accuracy of a foundation MatGL potential (e.g., CHGNet, M3GNet, TensorNet) for a specific chemical system or physical property using the provided Python fine-tuning script.

## Instructions

1.  **Prepare Labeled Dataset**: Obtain diverse structures with high-fidelity labels (energy, forces, stress). See the `/benchmark-finetuning` workflow for details.
2.  **Custom Data Conversion**: Read the source data format and write a customized conversion script if needed, formatting it for the subsequent preparation step.
3.  **Data Preparation**: Execute `scripts/prepare_matgl_data.py` to process JSON structures and split into training and validation sets.
4.  **Fine-Tuning**: Execute `scripts/train_matgl.py` to begin fine-tuning natively on the GPU using PyTorch Lightning.
5.  **Validation**: Verify convergence and compare against the benchmarked foundation metrics.
6.  **Registration**: Use the `register_model` tool to register the newly fine-tuned model checkpoint into the local registry so future research tasks can discover and reuse it.

## Usage

### 1. Data Preparation
Convert your dataset into the appropriate JSON format for MatGL training:
```bash
conda run -n matgl-agent python .agents/skills/ml-matgl-finetune/scripts/prepare_matgl_data.py \
    --data /path/to/training_data.json \
    --model CHGNet-MatPES-PBE-2025.2.10-2.7M-PES \
    --val-split 0.1 \
    --output-dir ./matgl_finetuned
```

### 2. Run Training
Fine-tune the model using the prepared data:
```bash
conda run -n matgl-agent python .agents/skills/ml-matgl-finetune/scripts/train_matgl.py \
    --train-data ./matgl_finetuned/train_data.json \
    --val-data ./matgl_finetuned/val_data.json \
    --model CHGNet-MatPES-PBE-2025.2.10-2.7M-PES \
    --epochs 10 \
    --lr 1e-3 \
    --batch-size 4 \
    --freeze-backbone \
    --output-dir ./matgl_finetuned
```

## Training Configuration

MatGL fine-tuning is divided into a data preparation step (formatting nested dictionaries and converting lists) and a native training run utilizing PyTorch Lightning. 

### Data Preparation Arguments (`prepare_matgl_data.py`)

| Key | Type | Default | Description |
|:----|:-----|:--------|:------------|
| `--data` | str | (Required) | Path to JSON file containing ASE/pymatgen structure dictionaries |
| `--model` | str | `CHGNet-MatPES-PBE-2025...` | Base model name or path to a checkpoint |
| `--output-dir` | str | `./fine_tuning` | Directory to save the processed data |
| `--val-split` | float | 0.1 | Fraction of data to set aside for validation |
| `--seed` | int | 42 | Random seed for splitting validation data |
| `--vasp-stress-conversion`| flag | - | If set, multiplies stress values by -1/160.2x to convert VASP raw kB to eV/Å³ |

### Training Arguments (`train_matgl.py`)

| Key | Type | Default | Description |
|:----|:-----|:--------|:------------|
| `--train-data` | str | (Required) | Path to JSON file containing training data |
| `--val-data` | str | None | Path to JSON file containing validation data (optional) |
| `--model` | str | `CHGNet-MatPES-PBE-2025...` | Base model name or path to a checkpoint |
| `--epochs` | int | 10 | Number of training epochs |
| `--lr` | float | 1e-3 | Learning rate |
| `--batch-size` | int | 4 | Training batch size |
| `--device` | str | `auto` | Target compute device (`cuda` or `cpu`) |
| `--output-dir` | str | `./fine_tuning` | Directory to save the fine-tuned model and logs |
| `--freeze-backbone` | flag | - | Freeze backbone (interaction blocks); only readout heads are trained |
| `--reinit-head` | flag | - | Re-initialize readout head weights |
| `--scheduler` | str | `CosineAnnealingLR` | `CosineAnnealingLR` or `ReduceLROnPlateau` |
| `--patience` | int | None | Early stopping patience (epochs) |
| `--energy-weight` | float | 1.0 | Loss weight for energy |
| `--force-weight` | float | 1.0 | Loss weight for forces |
| `--stress-weight` | float | 0.1 | Loss weight for stress |

## Constraints
- **Data Size**: For small datasets, `--freeze-backbone` is strongly recommended to prevent catastrophic forgetting.
- **Reference Energies (`element_refs`)**: If your fine-tuning data is computed using the same DFT functional (e.g., PBE) as the foundation model's original training data, you should reuse the foundation model's original isolated atom reference energies instead of re-fitting them. This maintains thermodynamic compatibility across the periodic table.
- **Environment**: Must be executed within the `matgl-agent` conda environment where MatGL and DGL are properly configured.
- **Stress Units**: MatGL inherently converts stress internally to GPa, however the standard expected inputs directly into its JSON files are `eV/Å³`. Raw VASP stress obtained directly via some JSON files may be in kilo-Bar (`kB`). The Atomate2 MCP tool handles this conversion automatically when `convert_units=True`. However, if your JSON labels contain raw `kB` stress, you MUST pass the `--vasp-stress-conversion` flag to `scripts/prepare_matgl_data.py` to automatically scale them by `-1/160.2x`. For more details on unit standardization, see @[.agents/skills/general-property-units/SKILL.md].

---

**Author:** Bowen Deng  
**Contact:** [GitHub @bowen-bd](https://github.com/bowen-bd)
