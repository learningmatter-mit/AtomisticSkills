---
name: mat-equation-of-state
description: Calculate equation of state (bulk modulus, equilibrium volume) using MLIPs.
category: [materials]
---

# Equation of State Skill

This skill provides tools for calculating the equation of state (EOS) of crystalline materials using Machine Learning Interatomic Potentials (MLIPs). The EOS describes the relationship between volume, energy, and pressure, allowing extraction of bulk modulus and equilibrium volume.

## Goal

Calculate the equation of state for a material by applying volumetric strains, computing the energy-volume relationship, and fitting to the Birch-Murnaghan equation to determine the bulk modulus ($B_0$) and equilibrium volume ($V_0$).

## 1. Prerequisites

- The appropriate MLIP wrapper must be available (`MACEWrapper`, `MatGLWrapper`, or `FAIRCHEMWrapper`).
- `matcalc` must be installed in the relevant conda environment.
- A relaxed structure file (CIF, POSCAR, or other ASE-readable format).

## 2. Choosing a Foundation Potential

EOS calculations require accurate total energies across different volumes.

> [!IMPORTANT]
> - **Use OMAT or MatPES trained models**: These models (e.g., `MACE-OMAT-0-small`, `CHGNet-MatPES-PBE`, `TensorNet-MatPES-r2SCAN`) provide more reliable energy predictions.
> - **MPtrj models can be used**: Unlike phonon calculations, EOS is less sensitive to force accuracy, but OMAT/MatPES models are still recommended for best results.

Refer to the [foundation-potentials skill](../ml-foundation-potentials/SKILL.md) for more details.

## 3. Calculation Workflow

To calculate the equation of state, use the `calculate_eos.py` script:

```bash
# Env: mace-agent
python .agents/skills/mat-equation-of-state/scripts/calculate_eos.py \
    --structure path/to/relaxed_structure.cif \
    --model_type mace \
    --model_name MACE-OMAT-0-small \
    --n_points 11 \
    --max_abs_strain 0.1 \
    --relax_structure \
    --output_dir research/my_folder/eos
```

**Key Parameters:**
- `--n_points`: Number of strain points (default: 11)
- `--max_abs_strain`: Maximum volumetric strain applied (default: 0.1 = ±10%)
- `--relax_structure`: Relax atomic positions at each strain point (recommended)
- `--fmax`: Force convergence tolerance for relaxation (default: 0.1 eV/Å)

## 4. Output Files

- `eos_results.json`: Summary containing bulk modulus (GPa), equilibrium volume (Ų), equilibrium energy (eV)
- `energies_volumes.dat`: Energy-volume data points used for fitting

## 5. Examples

See `examples/` for detailed usage scenarios, including Silicon EOS calculation.

## 6. Constraints

- **Environment**: Scripts require conda environments with MLIP packages installed:
  - `mace-agent` for MACE models
  - `matgl-agent` for MatGL/CHGNet models
  - `fairchem-agent` for FairChem/UMA models
- **Structure Relaxation**: It is highly recommended to start with a pre-relaxed structure and use `--relax_structure` to relax atomic positions at each strain point.
- **Strain Range**: The default ±10% strain is suitable for most materials. For very soft or very hard materials, adjust `--max_abs_strain` accordingly.
- **Fitting Model**: MatCalc uses the Birch-Murnaghan equation of state by default.
---

**Author:** Bowen Deng  
**Contact:** [GitHub @bowen-bd](https://github.com/bowen-bd)
