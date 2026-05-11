---
name: ml-committee-uncertainty
description: Quantify prediction uncertainty of MACE MLIPs using committee (ensemble) models; flag high-uncertainty structures for DFT verification.
category: [machine-learning, materials, chemistry]
---

# MACE Committee Model Uncertainty Quantification

## Goal
To estimate the epistemic uncertainty of a MACE MLIP by running inference with a committee (ensemble) of independently trained models. Structures where the committee disagrees strongly (high energy or force variance) are flagged as candidates for DFT labelling, supporting active learning workflows and validating MLIP reliability in under-sampled regions of configuration space.

The uncertainty estimate is:
- **Energy uncertainty**: standard deviation of predicted energies across committee members (meV/atom)
- **Force uncertainty**: RMS of per-atom force standard deviations across committee members (meV/Å)

## Instructions

### 1. Obtain Committee Models

A committee requires **N ≥ 3** independently trained MACE checkpoints covering the same chemical system. There are two ways to obtain them:

**Option A — Train with different random seeds (recommended for fine-tuned models)**

Run [ml-mace-finetune](../ml-mace-finetune/SKILL.md) N times, varying only the random seed via the `--seed` flag in `generate_mace_config.py`. Save each checkpoint to a separate directory:

```bash
# Env: mace-agent
# Run for seed=0, seed=1, seed=2 (at minimum)
for SEED in 0 1 2; do
    conda run -n mace-agent python .agents/skills/ml-mace-finetune/scripts/generate_mace_config.py \
        --train-file ./mace_data/train.xyz \
        --valid-file ./mace_data/valid.xyz \
        --model MACE-MH-1 \
        --epochs 200 \
        --lr 1e-4 \
        --batch-size 4 \
        --freeze-backbone \
        --seed ${SEED} \
        --output-dir ./committee_models/seed_${SEED}
    conda run -n mace-agent mace_run_train \
        --config ./committee_models/seed_${SEED}/finetune_config.yaml
done
```

**Option B — Use pre-existing models from the registry**

```bash
mcp_base_search_model_registry(
    chemical_system="Li-Fe-P-O",
    backend="mace",
)
# If multiple models exist for the same system, they can form a committee.
```

### 2. Run Committee Inference

Pass all checkpoint paths to the inference script. It will run each model independently and compute mean ± std across the committee.

```bash
# Env: mace-agent
python .agents/skills/ml-committee-uncertainty/scripts/run_committee_inference.py \
    --structures /path/to/structures_dir_or_file.cif \
    --models ./committee_models/seed_0/mace_finetuned.model \
             ./committee_models/seed_1/mace_finetuned.model \
             ./committee_models/seed_2/mace_finetuned.model \
    --output-dir ./uncertainty_results \
    --energy-threshold 10.0 \
    --force-threshold 200.0
# For MACE-MH foundation models, add:
#   --head omat_pbe
```

**Key parameters:**

| Parameter | Description | Typical value |
|:----------|:------------|:--------------|
| `--structures` | Path to structure file, directory, or `.xyz` trajectory | — |
| `--models` | Space-separated list of MACE checkpoint paths | ≥ 3 models |
| `--energy-threshold` | Flag if energy std > this value (meV/atom) | 5–20 meV/atom |
| `--force-threshold` | Flag if max force std > this value (meV/Å) | 100–300 meV/Å |
| `--output-dir` | Directory for results and plots | — |
| `--device` | `cuda` or `cpu` | `cuda` |
| `--head` | Head name for multi-head models (e.g. `omat_pbe` for MACE-MH-1) | `None` |

### 3. Interpret Results

The script produces:
- `uncertainty_summary.json` — per-structure energy/force mean ± std
- `high_uncertainty_structures/` — `.cif` files of flagged structures requiring DFT
- `uncertainty_distribution.png` — histogram of energy uncertainty across all structures

**Thresholds for DFT flagging:** There is no universal threshold. Empirically:
- Energy std > **10 meV/atom** is a conservative threshold suitable for phonon/stability work
- Energy std > **5 meV/atom** for high-accuracy MD (e.g., melting point, ionic conductivity)
- Force std > **200 meV/Å** generally indicates the configuration is poorly represented in training data

> [!TIP]
> Run this skill on your MD trajectory after a few nanoseconds to check whether the MLIP remains in-distribution throughout the simulation. High uncertainty at late simulation times suggests the trajectory has drifted into unexplored configuration space.

### 4. Send High-Uncertainty Structures to DFT

Pass the flagged structures to the DFT labelling pipeline. See the [mat-sample-pes-by-md](../mat-sample-pes-by-md/SKILL.md) skill for context on when and how to label new structures.

```bash
# High-uncertainty structures needing DFT labels are in:
ls ./uncertainty_results/high_uncertainty_structures/
# → Pass these to atomate2 DFT workflow for labelling
```

### 5. Register Threshold in the Model Registry

After determining an appropriate uncertainty threshold for your system, update the registry so future tasks can apply the same criterion automatically:

```bash
mcp_base_register_model(
    checkpoint_path="./committee_models/seed_0/mace_finetuned.model",
    chemical_system="Li-Fe-P-O",
    backend="mace",
    base_model="MACE-MH-1",
    notes="Committee of 3 models (seed 0/1/2). Use energy_std > 10 meV/atom as DFT flag threshold.",
    tags_json='["battery", "committee"]',
)
```

## Constraints

- **Minimum committee size**: Use at least 3 models. Two models can give misleading std estimates; 5+ models provide more robust uncertainty quantification.
- **Identical architecture**: All committee members must share the same base model architecture and chemical elements (same `--model` flag during fine-tuning). Different architectures cannot be meaningfully ensembled.
- **Same data, different seeds**: Committee members should be trained on the same dataset with different random seeds. Using models trained on different datasets introduces epistemic uncertainty from data mismatch, not model uncertainty.
- **Environment**: This script requires the `mace-agent` conda environment.

## References

- Batatia et al., "MACE: Higher Order Equivariant Message Passing Neural Networks for Fast and Accurate Force Fields", *NeurIPS*, 2022.
- Musil et al., "Physics-Inspired Structural Representations for Molecules and Materials", *Chem. Rev.*, 2021. (Committee model UQ)
- Schran et al., "Committee Neural Network Potentials Control Generalization Errors and Enable Active Learning", *J. Chem. Phys.*, 2020.

---

**Author:** Yu Yao  
**Contact:** [GitHub @AI4SciDisc](https://github.com/AI4SciDisc)
