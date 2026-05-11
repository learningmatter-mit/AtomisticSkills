---
name: ml-property-predictor
description: Train a property predictor head on top of a Machine Learning Interatomic Potential (MLIP) backbone (MACE or MatGL) to predict custom intensive or extensive properties from crystal or molecular structures.
category: [machine-learning, materials, chemistry]
---

# MLIP Property Predictor Training

## Goal

To leverage pre-trained GNN representations from MLIPs to train an independent readout head for any custom scalar target property (e.g., bulk modulus, bandgap, formation energy, or spin states) directly from crystal or molecular structures.

## Overview

This skill allows you to leverage pre-trained GNN representations from MLIPs to train an independent readout head for any custom scalar target property, such as bulk modulus, bandgap, formation energy, or spin states. 

To keep the core MLIP wrappers clean, property prediction in AtomisticSkills is handled by standalone training scripts located in the `.agents/skills/ml-property-predictor/scripts/` directory.

## Workflow

1. **Prepare Data**: Build a `.json` or `.xyz` dataset containing structures and the corresponding scalar property labels. JSON datasets should be lists of dicts containing a `structure` key (Pymatgen format) and your target property key.
2. **Determine Property Type**: Determine if the property is `"intensive"` (e.g. Bandgap, Bulk Modulus) or `"extensive"` (e.g. Total Energy). 
   - *MatGL logic*: For intensive targets, node features undergo a global graph readout (like `Set2Set`) before passing through an MLP. For extensive targets, the MLP outputs atomic properties which are then sum-pooled.
   - *MACE logic*: MACE natively supports extensive targets by predicting site-wise scalar outputs and sum-pooling them. When intensive properties are targeted, MACE still sum-pools site-wise outputs, forcing the model to internally learn the intensive invariant.
3. **Execute Script**: Run the MACE or MatGL property prediction script in their respective Conda environments.

---

## Example 1: Training a MACE Property Predictor

MACE property training is handled by `scripts/train_mace_property.py`. It dynamically patches the `mace.cli.run_train` module to freeze the backbone (if requested) and inject a custom intensive/extensive property readout.

```bash
# Env: mace-agent

# Run the standalone MACE property training script
python .agents/skills/ml-property-predictor/scripts/train_mace_property.py \
    --data_path .agents/test/mp_bulk_modulus.json \
    --model_name MACE-OMAT-0-small \
    --target_property bulk_modulus \
    --property_type intensive \
    --epochs 30 \
    --batch_size 16 \
    --lr 0.001 \
    --output_dir custom_mace_results/
```

- Adds `--freeze_backbone` automatically by default to preserve the MACE representation and avoid catastrophic forgetting.
- The custom weights will be saved to `custom_mace_results/`.

---

## Example 2: Training a MatGL (M3GNet) Property Predictor

MatGL property training is handled by `scripts/train_matgl_property.py`. It loads a pretrained `M3GNet` model, replaces the data collater to safely handle graph caching, and trains the property explicitly.

```bash
# Env: matgl-agent

# Run the standalone MatGL property training script
python .agents/skills/ml-property-predictor/scripts/train_matgl_property.py \
    --data_path .agents/test/mp_bulk_modulus.json \
    --model_name M3GNet-MP-2021.2.8-PES \
    --target_property bulk_modulus \
    --property_type intensive \
    --epochs 30 \
    --batch_size 32 \
    --lr 0.001 \
    --freeze_backbone \
    --output_dir custom_matgl_results/
```

- `--freeze_backbone` is optional (defaults to `False` for MatGL). If passed, only the final `readout` MLP layers of the M3GNet model will be fine-tuned.
- Intensive extensive targets are handled seamlessly without breaking the pretrained model architecture.
- Model checkpoints are securely saved in `custom_matgl_results/matgl_model/`.

## Constraints

- **Environments**: MACE predictor strictly requires `mace-agent`, and MatGL requires `matgl-agent`. **Each code block MUST specify the environment.**
- **Data Format**: The dataset must be `.json` or XYZ formatted with the raw structures or ASE atoms.
- **Subprocess Dependency**: The `train_mace_property.py` script spawns an underlying `mace.cli.run_train` subprocess to maintain compatibility with MACE's native optimizers.
- **Pre-trained Architecture**: For MatGL, changing the intensive/extensive nature of a pre-trained model changes the head dimensions. Extensive model predictions are mathematically scaled down by the number of atoms dynamically at training time if an intensive property is targeted.

## References

- Batatia et al., "MACE: Higher Order Equivariant Message Passing Neural Networks for Fast and Accurate Force Fields", *NeurIPS*, 2022. [DOI](https://doi.org/10.48550/arXiv.2206.07697)
- Chen et al., "Universal potential energy machine learning models", *Nat. Comput. Sci.*, 2022. [DOI](https://doi.org/10.1038/s43588-022-00349-3)

---

**Author:** Bowen Deng  
**Contact:** [GitHub @bowen-bd](https://github.com/bowen-bd)
