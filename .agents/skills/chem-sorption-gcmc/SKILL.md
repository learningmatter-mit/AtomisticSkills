---
name: chem-sorption-gcmc
description: Calculates gas adsorption isotherms via BVT/GCMC Monte Carlo simulations in a porous framework using MLIP.
category: [materials, chemistry]
---

# chem-sorption-gcmc

## Goal

To predict the macroscopic adsorption uptake of a gas (or gas mixture) in a porous material at a specific temperature and pressure. The skill relies on Grand Canonical Monte Carlo (GCMC) simulations where the host-guest and guest-guest interactions are calculated using a Machine Learning Interatomic Potential (MLIP: MACE, FairChem, MatGL).

## Prerequisites

- **Input**: A relaxed framework structure in CIF (or XYZ) format. The structure should ideally be processed by [chem-sorption-relax](../chem-sorption-relax/SKILL.md) to ensure proper supercell dimensions.
- **Conda environment**: Depends on the MLIP used (e.g., `fairchem-agent`, `mace-agent`, `matgl-agent`).

## Instructions

1. **Perform Single-Component GCMC (Optional)**: If you are investigating a single gas species, use `run_gcmc.py`.

```bash
# Env: fairchem-agent (or other MLIP-specific env)
python .agents/skills/chem-sorption-gcmc/scripts/run_gcmc.py \
    --cif path/to/relaxed_supercell.cif \
    --calculator fairchem \
    --model-name uma-s-1p1 \
    --task-name omol \
    --steps 50000 \
    --temperature-K 298 \
    --pressure-bar 1.0 \
    --adsorbate CO2 \
    --output-dir ./results/single_gcmc
```

2. **Perform Multi-Component GCMC (Optional)**: If you are simulating a gas mixture (e.g. flue gas separation 15% CO2 / 85% N2), use `run_gcmc_multi.py`.

```bash
# Env: fairchem-agent
python .agents/skills/chem-sorption-gcmc/scripts/run_gcmc_multi.py \
    --cif path/to/relaxed_supercell.cif \
    --calculator fairchem \
    --model-name uma-s-1p1 \
    --task-name omol \
    --steps 50000 \
    --temperature-K 298 \
    --gases CO2 N2 \
    --y 0.15 0.85 \
    --p-total-bar 1.0 \
    --output-dir ./results/multi_gcmc
```

### Key Parameters
- `--cif`: Path to the relaxed host framework.
- `--calculator`: The backend MLIP (`fairchem`, `mace`, `matgl`).
- `--model-name`: Name or path to the MLIP weights (e.g., `uma-s-1p1.pt`, `MACE-MH-1`).
- `--task-name`: Optional, required by some models (`omol` for UMA and MACE-MH).
- `--steps`: Number of Monte Carlo steps (minimum 50,000 recommended for equilibration).
- `--temperature-K`: Sim temperature.
- `--pressure-bar` (Single): Gas pressure in bar.
- `--p-total-bar` (Multi): Total mixture pressure in bar.
- `--gases` / `--y` (Multi): Species list and corresponding mole fractions in the vapor phase.

## Examples

**Example 1: Generating an Isotherm Point (CO2, 0.1 bar, 298K) with UMA:**
```bash
# Env: fairchem-agent
python .agents/skills/chem-sorption-gcmc/scripts/run_gcmc.py \
    --cif ./data/MOF-5_supercell.cif \
    --calculator fairchem \
    --model-name uma-s-1p1 \
    --task-name omol \
    --steps 50000 \
    --temperature-K 298 \
    --pressure-bar 0.1 \
    --adsorbate CO2 \
    --output-dir ./out/0.1_bar
```

## Constraints
- **Simulation Time**: GCMC with MLIPs can be computationally intensive. Use GPUs when available (`--device cuda`). 
- **Equilibration**: You MUST check the generated `nmols.png` and `energy.png` inside the `output-dir` to visually confirm that the number of molecules and energy have plateaued (equilibrated). If the trend is still rising/falling at the end of the simulation, you must re-run with more `--steps` (or restart the trajectory).
- **Restarting**: You can pass `--restart-traj ./out/mc.traj` to continue a previous run.

---

**Author:** Artur Lyssenko  
**Contact:** [GitHub @arturlyssenko12](https://github.com/arturlyssenko12)
