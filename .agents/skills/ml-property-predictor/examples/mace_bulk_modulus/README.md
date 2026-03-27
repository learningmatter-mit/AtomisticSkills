# MACE Bulk Modulus Property Predictor Tutorial

This directory contains a complete, self-contained example demonstrating how to use the `.agents/skills/ml-property-predictor/scripts/train_mace_property.py` script to fine-tune a MACE internal property head to predict materials' **bulk modulus** (an intensive property).

## Contents
1. `run_mace.py`: A Python wrapper script that automates generating the training curve, running the `.agents/test/mp_bulk_modulus.json` dataset through `mace-agent`, and crucially **automatically cleaning up** the massive `epoch_*.pt` internal model checkpoints to save disk space, leaving only the final `*.model` compiled blueprint for inference!

## Running the Example
First, ensure you are operating from the `base-agent` environment to kick off the master pipeline. The script will automatically trigger a sub-process inside the designated `mace-agent` conda environment.

```bash
conda run -n base-agent python run_mace.py
```

### Outputs
After successful execution (typically taking ~2 minutes on CPU to run 25 epochs across 1000 structures), this script will essentially:
- Create `mace_results/` natively hosting the outputs and logs.
- Test evaluate reloading the model accuracy over the JSON input structures array natively bypassing ASE integration.
- **Delete** the newly created `*.pt` and `*.model` PyTorch parameters from your local filesystem—as MACE models are extremely heavy (>300MB), the script cleans up after itself to maintain a lightweight `AtomisticSkills` installation footprint.
