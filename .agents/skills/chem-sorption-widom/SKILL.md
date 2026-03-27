---
name: chem-sorption-widom
description: Calculates Henry coefficient and heat of adsorption for a gas in a porous framework using Widom insertion with any supported MLIP.
category: [materials, chemistry]
---

# chem-sorption-widom

## Goal

To determine the initial affinity of a porous material (e.g., MOFs, COFs) for a specific gas molecule at infinite dilution. This is done by computing the Henry coefficient ($K_H$) and the isosteric heat of adsorption ($\Delta H_{ads}$) using Widom insertion, calculating interaction energies with a generic Machine Learning Interatomic Potential (MLIP) such as MACE, FairChem, or MatGL.

## Prerequisites

- **Input**: A relaxed framework structure in CIF (or XYZ) format. The structure should ideally be processed by [chem-sorption-relax](../chem-sorption-relax/SKILL.md) to ensure proper supercell dimensions.
- **Conda environment**: Depends on the MLIP used (e.g., `fairchem-agent`, `mace-agent`, `matgl-agent`).

## Instructions

1. **Perform Widom Insertion**: Use the `run_widom.py` script, specifying the structure, gas, temperature, and your MLIP of choice.

```bash
# Env: fairchem-agent (if using fairchem), mace-agent (if using mace), etc.
python .agents/skills/chem-sorption-widom/scripts/run_widom.py \
    --structure path/to/relaxed_supercell.cif \
    --name MY_FRAMEWORK \
    --calculator fairchem \
    --model-name uma-s-1p1 \
    --task-name omol \
    --gas CO2 \
    --temperature 298 \
    --output-dir ./results
```

### Parameters

- `--structure`: Path to the relaxed host framework (must be large enough, see [Constraints](#constraints)).
- `--name`: Identifier for the output files.
- `--calculator`: The backend MLIP (`fairchem`, `mace`, `matgl`).
- `--model-name`: Name or path to the MLIP weights (e.g., `uma-s-1p1.pt`, `MACE-MH-1`).
- `--task-name`: Optional, but highly recommended for multi-task models (e.g., `omol` for FairChem UMA and MACE-MH).
- `--gas`: The adsorbate gas (e.g., `CO2`, `N2`, `CH4`).
- `--temperature`: Temperature in Kelvin.
- `--num-insertions`: Number of Monte Carlo insertion attempts (default: 50,000).
- `--output-dir`: Directory to save the `widom_results.json`.

## Examples

**Example 1: Using FairChem UMA for CO2 adsorption at 298K**
```bash
# Env: fairchem-agent
python .agents/skills/chem-sorption-widom/scripts/run_widom.py \
    --structure ./results/COF-1_supercell.cif \
    --name COF-1 \
    --calculator fairchem \
    --model-name uma-s-1p1 \
    --task-name omol \
    --gas CO2 \
    --temperature 298 \
    --output-dir ./results
```



## Constraints

- **Cell Size**: The periodic boundary conditions of the framework must be large enough ($> 12$ Å minimum interplanar distance) to prevent artificial self-interactions of the inserted gas molecules across boundaries. It is highly recommended to use [chem-sorption-relax](../chem-sorption-relax/SKILL.md) first.
- **Statistical Noise**: Increasing `--num-insertions` (e.g., to 100,000) improves the convergence of $K_H$ and $\Delta H_{ads}$, at the cost of increased computation time.
- **Model Compatibility**: Ensure the selected MLIP and its corresponding `task-name` are suitable for non-covalent interactions (e.g., `omol` for UMA, or dispersion-corrected MACE/MatGL models).

---

**Author:** Artur Lyssenko  
**Contact:** [GitHub @arturlyssenko12](https://github.com/arturlyssenko12)
