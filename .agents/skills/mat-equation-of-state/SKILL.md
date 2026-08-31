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
- `--max_abs_strain`: Maximum linear strain applied (default: 0.1 = ±10%, i.e. volumes spanning (1±0.1)^3)
- `--relax_structure` / `--no-relax_structure` (default on): fully relax the input cell (ions *and* cell vectors) before the strain scan, so the scan is centred on this model's own equilibrium volume rather than whatever volume the input file happens to have. It does **not** control the per-strain relaxation -- matcalc relaxes every strained point regardless.
- `--allow_shape_change` / `--no-allow_shape_change` (default on, matcalc >= 0.5): at each strain point relax the cell *shape* at constant volume as well as the ions. This is the E(V) a Birch-Murnaghan fit assumes -- the minimum energy at fixed volume. Symmetry forbids shape relaxation in cubic cells, so it changes nothing there; for anisotropic cells, freezing the shape overestimates B0.
- `--fmax`: Force convergence tolerance for relaxation (default: 0.1 eV/Å)

## 4. Output Files

- `eos_results.json`: Summary containing bulk modulus (GPa), equilibrium volume (Å³), equilibrium energy (eV) and the R² of the fit. The equilibrium volume and energy are the Birch-Murnaghan minimum (v0, e0) -- not the volume or energy of any individual scan point.
- `energies_volumes.dat`: Energy-volume data points used for fitting. The same scan is repeated under the `energy_volume_curve` key of `eos_results.json`, so the fit can always be reproduced from the summary alone.

## 5. Examples

See `examples/` for detailed usage scenarios, including Silicon EOS calculation.

## 6. Constraints

- **Environment**: Scripts require conda environments with MLIP packages installed:
  - `mace-agent` for MACE models
  - `matgl-agent` for MatGL/CHGNet models
  - `fairchem-agent` for FairChem/UMA models
- **Structure Relaxation**: two distinct stages. The *pre-relaxation* (`--relax_structure`) centres the scan on the model's equilibrium cell; the *per-point* relaxation always runs. `--fmax` currently sets both -- the 0.1 eV/Å default is loose for a cell relaxation, and a pre-relaxation that stops early shifts the whole scan window and therefore B0. Tighten it (0.02-0.05) when B0 matters. V0 from the fit is far less sensitive than B0.
- **Strain Range**: The default ±10% strain is suitable for most materials. For very soft or very hard materials, adjust `--max_abs_strain` accordingly.
- **Fitting Model**: MatCalc fits the Birch-Murnaghan equation of state. Note that `--max_abs_strain` is applied as a *linear* strain (target volume = (1+e)^3 x V0), despite matcalc's own docstring calling it volumetric.
---

**Author:** Bowen Deng
**Contact:** [GitHub @learningmatter-mit](https://github.com/learningmatter-mit)
