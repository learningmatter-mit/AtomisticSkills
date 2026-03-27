---
name: mat-elasticity
description: Calculate the full elastic tensor and mechanical properties (bulk modulus, shear modulus, Young's modulus, Poisson's ratio) using MLIPs.
category: [materials]
---

# Elastic Tensor Skill

This skill calculates the full elastic tensor ($C_{ij}$) and derived mechanical properties of crystalline materials using Machine Learning Interatomic Potentials (MLIPs). It applies a set of normal and shear strains, computes the resulting stresses, and fits the elastic constants via least-squares regression using MatCalc's `ElasticityCalc`.

## Goal

Calculate the elastic tensor ($C_{ij}$) of a material by applying systematic deformations (normal and shear strains), computing the stress response with an MLIP, and extracting the full Voigt elastic tensor along with:
- Bulk modulus $B$ (Voigt-Reuss-Hill average)
- Shear modulus $G$ (Voigt-Reuss-Hill average)
- Young's modulus $E$
- Poisson's ratio $\nu$

## 1. Prerequisites

- The appropriate MLIP wrapper must be available (`MACEWrapper`, `MatGLWrapper`, or `FAIRCHEMWrapper`).
- `matcalc` must be installed in the relevant conda environment.
- A structure file (CIF, POSCAR, or other ASE-readable format). The structure will be relaxed before deformation by default.

## 2. Choosing a Foundation Potential

Elastic tensor calculations require accurate stress predictions across multiple deformed structures.

> [!IMPORTANT]
> - **Use OMAT or MatPES trained models**: These models (e.g., `MACE-OMAT-0-small`, `CHGNet-MatPES-PBE`, `TensorNet-MatPES-r2SCAN`) are trained with stress labels and provide reliable stress predictions.
> - **Stress accuracy is critical**: Unlike EOS (which only uses energies), elasticity calculations directly depend on stress tensors. Models trained without stress labels may give poor results.

Refer to the [foundation-potentials skill](../ml-foundation-potentials/SKILL.md) for more details.

## 3. Calculation Workflow

To calculate the elastic tensor, use the `calculate_elasticity.py` script:

```bash
# Env: mace-agent
python .agents/skills/mat-elasticity/scripts/calculate_elasticity.py \
    --structure path/to/structure.cif \
    --model_type mace \
    --model_name MACE-OMAT-0-small \
    --norm_strains -0.01 -0.005 0.005 0.01 \
    --shear_strains -0.06 -0.03 0.03 0.06 \
    --relax_structure \
    --output_dir research/my_folder/elasticity
```

**Key Parameters:**
- `--norm_strains`: Normal strain magnitudes applied (default: ±0.5%, ±1.0%)
- `--shear_strains`: Shear strain magnitudes applied (default: ±3%, ±6%)
- `--relax_structure`: Relax the structure before applying strains (recommended)
- `--relax_deformed`: Additionally relax atomic positions in each deformed structure (usually not needed)
- `--fmax`: Force convergence tolerance for relaxation (default: 0.1 eV/Å)

> [!TIP]
> - For **metals**, the default strain magnitudes work well.
> - For **soft materials** (polymers, molecular crystals), reduce strains to stay in the linear regime.
> - For **very hard materials** (diamond, SiC), the default strains are fine since deformations remain small.

## 4. Output Files

- `elasticity_results.json`: Full results including:
  - `elastic_tensor_GPa`: 6×6 Voigt elastic tensor in GPa
  - `bulk_modulus_vrh_GPa`: Bulk modulus (VRH) in GPa
  - `shear_modulus_vrh_GPa`: Shear modulus (VRH) in GPa
  - `youngs_modulus_GPa`: Young's modulus in GPa
  - `poissons_ratio`: Poisson's ratio (dimensionless)
  - `residuals_sum`: Residual from the least-squares fit (lower is better)

## 5. Examples

See `examples/Cu/` for a copper elastic tensor calculation using MACE-OMAT-0-small.

```bash
# Env: mace-agent
python .agents/skills/mat-elasticity/scripts/calculate_elasticity.py \
    --structure .agents/skills/mat-elasticity/examples/Cu/Cu.cif \
    --model_type mace \
    --model_name MACE-OMAT-0-small \
    --output_dir research/elasticity/Cu
```

## 6. Constraints

- **Environment**: Scripts require conda environments with MLIP packages installed:
  - `mace-agent` for MACE models
  - `matgl-agent` for MatGL/CHGNet models
  - `fairchem-agent` for FairChem/UMA models
- **Structure Relaxation**: It is highly recommended to relax the structure before computing elastic properties. Use `--relax_structure` (enabled by default).
- **Linear Regime**: Strains must be small enough to remain in the linear elastic regime. The default values are appropriate for most inorganic crystalline materials.
- **Unit Conversion**: MatCalc returns moduli in eV/ų (bulk, shear) and Pa (Young's). The script converts all to GPa.
- **Symmetry**: By default, symmetry reduction is disabled (`--symmetry` flag enables it). This means all 21 independent components are fitted independently.
---

**Author:** Bowen Deng  
**Contact:** [GitHub @bowen-bd](https://github.com/bowen-bd)
