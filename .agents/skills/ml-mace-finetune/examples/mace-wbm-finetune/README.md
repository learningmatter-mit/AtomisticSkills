# MACE Fine-Tuning Example: Softening Dataset

This example demonstrates how to fine-tune the `MACE-OMAT-0-small` foundation model on a [softening dataset](https://figshare.com/articles/dataset/WBM_high_energy_states/27307776?file=50005317) containing high-energy crystal structures.

## Goal
To document a functional 10-epoch fine-tuning workflow on challenging high-energy VASP data, proving the stability of the MACE fine-tuning when thermodynamic constraints (energy, forces, and particularly stress units) are aligned correctly.

## Instructions

### 1. Prepare Training Data 
The dataset is processed using the `prepare_mace_data.py` script. The training data must contain `structure` (pymatgen dict) or `atoms`, along with labeled properties.

Because the raw `vasp_s` labels in this WBM extraction are recorded in `kB`, we MUST pass the `--vasp-stress-conversion` flag to multiply them by `-1/1602.1766208` during extraction. The script also automatically unravels multi-layer dictionaries (e.g., `{wbm_id: [{config_id: {data}}]}`).

```bash
# Env: mace-agent
conda run -n mace-agent python .agents/skills/ml-mace-finetune/scripts/prepare_mace_data.py \
    --data private_data/WBM_subset_200_configs.json \
    --model MACE-OMAT-0-small \
    --epochs 10 \
    --lr 1e-4 \
    --batch-size 8 \
    --freeze-backbone \
    --output-dir .agents/skills/ml-mace-finetune/examples/mace-wbm-finetune \
    --vasp-stress-conversion
```

### 2. Run MACE Trainer
The script generates a `finetune_config.yaml` file natively compatible with the `mace_run_train` CLI. Run the actual training loop:

```bash
# Env: mace-agent
cd .agents/skills/ml-mace-finetune/examples/mace-wbm-finetune
conda run -n mace-agent mace_run_train --config finetune_config.yaml
```

### 3. Extract Training Logs
Once training converges, extract the diagnostic learning curves (energy, forces, and stress MAE) from the generated logs to evaluate performance.

```bash
# Env: mace-agent
cd /path/to/project_root
conda run -n mace-agent python .agents/skills/ml-mace-finetune/scripts/extract_mace_logs.py \
    --results-dir .agents/skills/ml-mace-finetune/examples/mace-wbm-finetune/results
```

## Expected Outputs
This directory contains the artifacts generated from a 10-epoch execution of the above commands over the isolated 200 structures (split structurally 90/10 into train/validation).

- `finetune_config.yaml`: The exact configuration generated for `mace_run_train`.
- `training_history.json`: Parsed loss and MAE metrics extracted across epochs natively from MACE's logs.
- `training_history.png`: Standardized loss degradation 2x2 grid plot proving model convergence without catastrophic divergence.

---

**Author:** Bowen Deng  
**Contact:** [GitHub @bowen-bd](https://github.com/bowen-bd)
