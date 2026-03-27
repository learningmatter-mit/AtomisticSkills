---
name: ml-fairchem-finetune
description: Fine-tune Fairchem machine learning interatomic potentials (UMA, ESEN) on custom datasets.
category: [machine-learning]
---
# Fairchem Fine-tuning

## Goal
To evaluate and improve the accuracy of a foundation Fairchem potential (e.g., UMA, ESEN) for a specific chemical system or physical property using the provided Python fine-tuning script.

## Instructions

1.  **Prepare Labeled Dataset**: Obtain diverse structures with high-fidelity labels (energy, forces, stress). See the `/benchmark-finetuning` workflow for details.
2.  **Custom Data Conversion**: Read the source data format and write a customized conversion script if needed, formatting it for the subsequent preparation step.
3.  **Benchmarking**: Predict results on the new labels and benchmark the foundation model using [ml-mlip-benchmark](../ml-mlip-benchmark/SKILL.md).
4.  **Data Preparation**: Execute `scripts/prepare_fairchem_data.py` to convert JSON structures to extxyz, generate native LMDB databases, compute dataset references, and configure a templated `uma_sm_finetune_template.yaml`.
5.  **Fine-Tuning**: Execute `fairchem -c uma_sm_finetune_template.yaml job.run_dir=XXX` natively.
6.  **Validation**: Run `scripts/extract_fairchem_logs.py` to extract curves and verify convergence against the benchmarked foundation metrics.

## Training Configuration

Fairchem fine-tuning relies heavily on the `fairchem` CLI, which uses Hydra for configuration. The script `scripts/prepare_fairchem_data.py` bridges standard data into the complex Fairchem directory structure and generates `.aselmdb` dataset formats automatically.

### Basic Arguments (Data Prep Script)

| Key | Type | Default | Description |
|:----|:-----|:--------|:------------|
| `--data` | str | (Required) | Path to JSON file containing ASE/pymatgen structure dictionaries |
| `--val-data` | str | None | Path to JSON file containing validation split. (Optional, otherwise --val-split is used) |
| `--val-split` | float | 0.1 | Validation split if `--val-data` is not provided |
| `--seed` | int | 42 | Random seed for data splitting and initialization |
| `--model` | str | `uma-s-1p1` | Base model name or path to a checkpoint |
| `--task-name` | str | `omat` | The specific multi-task context to run against (`omat`, `omol`) |
| `--epochs` | int | 10 | Number of training epochs |
| `--lr` | float | 4e-4 | Peak learning rate for training |
| `--batch-size` | int | 2 | Training batch size |
| `--freeze-backbone` | flag | N/A | Add flag to mathematically freeze OCP/UMA interaction layers |
| `--weight-decay` | float | 1e-3 | Weight decay parameter |
| `--warmup-factor` | float | 0.2 | LR warmup factor |
| `--warmup-epochs` | float | 0.01 | Epochs to perform LR warmup |
| `--lr-min-factor` | float | 0.01 | Minimum LR factor after decay |
| `--clip-grad-norm` | float | 100.0 | Gradient clipping threshold |
| `--evaluate-every-n-steps` | int | 100 | Steps frequency for validation evaluation |
| `--checkpoint-every-n-steps` | int | 1000 | Steps frequency for model checkpointing |
| `--ema-decay` | float | 0.999 | Exponential moving average decay parameter |
| `--linref-coeff`| str | None | JSON array of elemental energy linear references. If None, it auto-computes it over the `data`. |
| `--vasp-stress-conversion` | flag | N/A | Add flag to automatically convert kB to eV/Å³ for VASP inputs |
| `--output-dir` | str | `./fairchem_finetuning` | Directory to save the `lmdb_output` intermediate data and run configs |

> [!NOTE]
> If you have created a dedicated research directory for your current workflow (e.g. using the `create_research_dir` tool), you should set the `--output-dir` argument to a folder within that active research directory to keep all artifacts and models organized.
> The data preparation script takes several minutes because it automatically creates `.aselmdb` copies of all structural inputs mapping to specific index structures.

> [!WARNING]
> **Stress Units**: Fairchem expects stress in `eV/Å³`. Raw VASP stress obtained directly via some JSON files may be in kilo-Bar (`kB`), which is ~160x larger and will cause catastrophic training divergence. The Atomate2 MCP tool handles this conversion automatically when `convert_units=True`. However, if your JSON labels contain raw `kB` stress, you MUST pass the `--vasp-stress-conversion` flag to `scripts/prepare_fairchem_data.py` to automatically scale them by `-1/160.2x`. For more details on unit standardization, see @[.agents/skills/general-property-units/SKILL.md].

Usage:
```bash
# 1. Prepare Data and Config
conda run -n fairchem-agent python .agents/skills/ml-fairchem-finetune/scripts/prepare_fairchem_data.py \
    --data /path/to/training_data.json \
    --model uma-s-1p1 \
    --epochs 10 \
    --lr 4e-4 \
    --batch-size 2 \
    --freeze-backbone \
    --output-dir ./research/my_dir/fairchem_finetuning

# 2. Run Training
export PYTHONPATH=/path/to/research/my_dir/fairchem_finetuning/lmdb_output:$PYTHONPATH
cd /path/to/research/my_dir/fairchem_finetuning/lmdb_output
conda run -n fairchem-agent fairchem -c uma_sm_finetune_template.yaml job.run_dir=/path/to/research/my_dir/fairchem_finetuning/runs +job.timestamp_id=run_10ep

# 3. Extract Training Logs (Optional, to create standard training_history.json)
conda run -n fairchem-agent python .agents/skills/ml-fairchem-finetune/scripts/extract_fairchem_logs.py \
    --log /path/to/research/my_dir/fairchem_finetuning/runs/run_10ep/logs/trainer.log \
    --output-dir /path/to/research/my_dir/fairchem_finetuning/results
```

## Constraints
- **Multi-task Setup**: UMA and ESEN are trained explicitly on tasks. Be absolutely sure to specify the right `--task-name` for your datasets (`omat` vs `omol`).
- **Reference Energies (`linref_coeff`)**: If your fine-tuning data is computed using the same DFT functional (e.g., PBE) as the foundation model's original training data, you should extract and pass the foundation model's original `linref_coeff` array instead of allowing the script to automatically re-fit it via Least Squares. This maintains thermodynamic scale compatibility across the periodic table.
- **GPU Overhead**: Fairchem configuration files compile PyTorch networks prior to run and memory overhead can cause execution to take over 5 minutes to generate logs if using data parallel or multi-gpu execution. Disable wandb using the `--debug` parameter within the configuration file if training stalls completely.

---

**Author:** Bowen Deng  
**Contact:** [GitHub @bowen-bd](https://github.com/bowen-bd)
