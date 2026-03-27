---
name: chem-react-ot
description: Generate transition state structures for chemical reactions using React-OT.
category: [chemistry]
---

# `chem-react-ot` — React-OT Transition State Generation

## Goal

Generate transition state (TS) structures given reactant and product structures using the React-OT model (Optimal Transport). React-OT is a generative model that predicts TS geometries directly without requiring an initial guess path (like NEB).

**Category:** `chemistry`
**Environment:** `react-ot-agent`

## Key Features

- **Generative TS Prediction:** Predicts 3D transition state structures from 3D reactants and products.
- **Fast Inference:** Uses an ODE solver for generation, typically much faster than DFT-based NEB.
- **No Path Guess Required:** Directly generates the TS structure.

## Usage

### 1. Environment Setup

This skill requires the `react-ot-agent` conda environment. Ensure it is installed:

```bash
# Env: react-ot-agent
cd conda-envs/react-ot-agent
bash install.sh
```

### 2. Download Models

Before running the skill for the first time, download the pre-trained model weights:

```bash
# activate react-ot-agent first
conda activate react-ot-agent
python conda-envs/react-ot-agent/download_models.py
```

The checkpoint is saved to `~/.cache/react-ot/checkpoints/sb-pretrained.ckpt`.

### 3. Generate Transition State

Run the generation script with reactant and product files (xyz, cif, pdb, etc. - anything ASE reads).

```bash
# Env: react-ot-agent
python .agents/skills/chem-react-ot/scripts/generate_ts.py \
    --reactants reactant.xyz \
    --products product.xyz \
    --output_dir results/ts_search
```

**Arguments:**

- `--reactants`: Path to reactant structure file(s). Can be a single file with multiple molecules or a list of files.
- `--products`: Path to product structure file(s).
- `--output_dir`: Directory to save the generated TS structure (`ts_generated.xyz`) and trajectory (`generation_traj.xyz`).
- `--nfe`: Number of function evaluations for the ODE solver (default: 10). Higher values might be more accurate but slower.
- `--checkpoint`: Path to custom model checkpoint (optional, defaults to downloaded one).

## Example

```bash
# Env: react-ot-agent
python .agents/skills/chem-react-ot/scripts/generate_ts.py \
    --reactants .agents/skills/chem-react-ot/examples/oxadiazole_isomerization/reactant.xyz \
    --products .agents/skills/chem-react-ot/examples/oxadiazole_isomerization/product.xyz \
    --output_dir .agents/skills/chem-react-ot/examples/oxadiazole_isomerization/output
```

## Constraints

- **Environment**: All scripts require the `react-ot-agent` conda environment.
- **Input Format**: Reactant and product structures must be in any format readable by ASE (XYZ, CIF, PDB, etc.).
- **Atom Ordering**: Reactant and product structures must have the same number of atoms with consistent atom ordering.
- **Model Checkpoint**: The pre-trained checkpoint must be downloaded before first use (see step 2).

## References

- [React-OT GitHub](https://github.com/deepprinciple/react-ot)
- Duan, C., Liu, G.-H., Du, Y. et al., "Optimal transport for generating transition states in chemical reactions", *Nature Machine Intelligence*, 2025. [DOI](https://doi.org/10.1038/s42256-025-01010-0)

---

**Author:** Bowen Deng  
**Contact:** [GitHub @bowen-bd](https://github.com/bowen-bd)
