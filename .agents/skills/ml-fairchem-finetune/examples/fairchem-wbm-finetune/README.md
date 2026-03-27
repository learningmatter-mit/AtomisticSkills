# FAIRChem Fine-Tuning Example: Softening Dataset

This example demonstrates how to fine-tune the `uma-s-1p1` foundation model on a [softening dataset](https://figshare.com/articles/dataset/WBM_high_energy_states/27307776?file=50005317) containing high-energy crystal structures. 

## Goal
To document a functional 10-epoch fine-tuning workflow on challenging high-energy VASP data, proving the stability of the FAIRChem fine-tuning when thermodynamic constraints (energy, forces, and particularly stress units) are aligned correctly.

## Instructions

### 1. Prepare Training Data 
The dataset is processed using the `prepare_fairchem_data.py` script. The training data must contain `structure` (pymatgen dict) or `atoms`, along with labeled properties.

Because the raw `vasp_s` labels in this WBM extraction are recorded in `kB`, we MUST pass the `--vasp-stress-conversion` flag to multiply them by `-1/1602.1766208` during extraction. The script also automatically unravels multi-layer dictionaries (e.g., `{wbm_id: [{config_id: {data}}]}`).

```bash
# Env: fairchem-agent
conda activate fairchem-agent

# Execute the data preparation and runner script
bash .agents/skills/ml-fairchem-finetune/examples/fairchem-wbm-finetune/run.sh
```

Under the hood, the `run.sh` script executes the following data preparation command:
```bash
python .agents/skills/ml-fairchem-finetune/scripts/prepare_fairchem_data.py \
    --data private_data/WBM_subset_200_configs.json \
    --model uma-s-1p1 \
    --task-name omat \
    --epochs 10 \
    --lr 1e-4 \
    --batch-size 2 \
    --freeze-backbone \
    --output-dir .agents/skills/ml-fairchem-finetune/examples/fairchem-wbm-finetune \
    --vasp-stress-conversion
```

### 2. Run FAIRChem Trainer
The script generates a `uma_sm_finetune_template.yaml` file compatible with the `fairchem-train` CLI. Run the actual training loop:

```bash
# Env: fairchem-agent
cd .agents/skills/ml-fairchem-finetune/examples/fairchem-wbm-finetune
conda run -n fairchem-agent fairchem-train --config-yml uma_sm_finetune_template.yaml
```

### 3. Extract Training Logs
Once training converges, extract the diagnostic learning curves (energy, forces, and stress MAE) from the generated logs to evaluate performance.

```bash
# Env: fairchem-agent
conda run -n fairchem-agent python .agents/skills/ml-fairchem-finetune/scripts/extract_fairchem_logs.py \
    --log-file .agents/skills/ml-fairchem-finetune/examples/fairchem-wbm-finetune/tensorboard/uma_sm_finetune*/train.log \
    --output-dir .agents/skills/ml-fairchem-finetune/examples/fairchem-wbm-finetune
```

## Expected Outputs
This directory contains the artifacts generated from a 10-epoch execution of the above commands over the isolated 200 structures (split structurally 90/10 into train/validation).

- `lmdb_output/`: Contains the generated LMDB datasets and the `uma_sm_finetune_template.yaml` configuration file.
- `runs/run_10ep/`: Contains the FairChem native training outputs, checkpoints, and logs.
- `training_history.json`: Parsed loss and MAE metrics extracted across epochs natively from FairChem's logs.
- `training_history.png`: Standardized loss degradation 2x2 grid plot proving model convergence without catastrophic divergence.

---

**Author:** Bowen Deng  
**Contact:** [GitHub @bowen-bd](https://github.com/bowen-bd)
