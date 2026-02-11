---
name: mlip-training
description: Benchmark and fine-tune Machine Learning Interatomic Potentials (MLIPs) using data-augmentation.
---

# MLIP Training

## Goal
To evaluate and improve the accuracy of a foundation potential (MACE, MatGL, FairChem) for a specific chemical system or physical property through automated sampling and fine-tuning.

## Instructions

1.  **PES Sampling**: Generate diverse structural configurations using the near-equilibrium or off-equilibrium samplers.
2.  **Labeling**: Obtain high-fidelity energy and forces using DFT (via `prepare_vasp_inputs`) or a high-quality mock potential (UMA).
3.  **Benchmarking**: Predict results on the new labels and generate parity plots using [plot_training_results.py](scripts/plot_training_results.py).
    ```bash
    python scripts/plot_training_results.py --results benchmarking.json
    ```
4.  **Fine-Tuning**: Execute `fine_tune_model` with recommended [hyperparams.json](resources/hyperparams.json).
5.  **Validation**: Plot the training history to verify convergence.
    ```bash
    python scripts/plot_training_results.py --history history.json
    ```

## Examples

Benchmarking MACE-OMAT-0-small on a new Al-Li dataset:
```bash
# After running predictions
python scripts/plot_training_results.py --results results.json --output_dir plots/
```

## Constraints
- **Data Size**: For small datasets (<500 structures), `freeze_backbone=True` is strongly recommended.
- **Units**: Ensure stress labels are in eV/Å³ as per project standards.


Author: Bowen Deng
Contact: github username <bowen-bd>
