---
name: chem-vibration
description: Calculate vibrational frequencies, normal modes, zero-point energy, and IR spectra of molecules and clusters using MLIPs.
category: [chemistry]
---

# Molecular Vibration Analysis Skill

## Goal

Calculate the vibrational frequencies ($\nu$), normal modes, and zero-point energy (ZPE) of **non-periodic (finite) systems** — molecules, clusters, and adsorbates — within the harmonic approximation using Machine Learning Interatomic Potentials (MLIPs).

> [!IMPORTANT]
> This skill is for **molecules and finite systems only**. For periodic crystals, use the [phonon skill](../mat-phonon/SKILL.md) instead.

## Background

In the harmonic approximation, the potential energy surface near a local minimum is approximated as $V \approx V_0 + \frac{1}{2} \sum_{ij} H_{ij} \Delta r_i \Delta r_j$, where $H_{ij} = \frac{\partial^2 V}{\partial r_i \partial r_j}$ is the Hessian (force constant) matrix. Diagonalizing the mass-weighted Hessian yields $3N$ eigenvalues: for a nonlinear molecule, $3N-6$ are real vibrational modes (and $3N-5$ for linear molecules), while the remaining eigenvalues correspond to translational and rotational degrees of freedom (near zero).

## 1. Prerequisites

- An MLIP wrapper must be available (`MACEWrapper`, `MatGLWrapper`, or `FAIRCHEMWrapper`).
- ASE must be installed in the relevant conda environment.
- The input structure must be a **molecule or cluster** (non-periodic). Periodic systems should use [mat-phonon](../mat-phonon/SKILL.md).

## 2. Choosing a Foundation Potential

> [!IMPORTANT]
> - **Use OMAT or MatPES trained models** (e.g., `MACE-OMAT-0-small`). These are optimized for forces and give reliable Hessians.
> - The harmonic approximation **requires a well-converged equilibrium geometry**. Always relax with tight force tolerance (fmax ≤ 0.001 eV/Å) before computing vibrations.

Refer to the [foundation-potentials skill](../ml-foundation-potentials/SKILL.md) for details.

## 3. Calculation Workflow

### Step 1: Prepare a molecule

Use ASE's built-in molecule database or provide a structure file:
```bash
# Built-in molecules: H2O, CO2, CH4, NH3, CH3OH, C2H6, etc.
# Or provide a .xyz / .cif / POSCAR file
```

### Step 2: Run vibration analysis

```bash
# Env: mace-agent
python .agents/skills/chem-vibration/scripts/calculate_vibrations.py \
    --molecule H2O \
    --model_type mace \
    --model_name MACE-OMAT-0-small \
    --output_dir research/my_folder/vibrations
```

With a structure file instead:
```bash
# Env: mace-agent
python .agents/skills/chem-vibration/scripts/calculate_vibrations.py \
    --structure path/to/molecule.xyz \
    --model_type mace \
    --model_name MACE-OMAT-0-small \
    --no_relax \
    --output_dir research/my_folder/vibrations
```

**Key Parameters:**
- `--molecule`: ASE built-in molecule name (e.g., `H2O`, `CO2`, `CH4`)
- `--structure`: Path to structure file (alternative to `--molecule`)
- `--delta`: Finite-difference displacement in Å (default: 0.01)
- `--nfree`: Number of displacements per degree of freedom, 2 or 4 (default: 2)
- `--relax / --no_relax`: Whether to relax before vibration analysis (default: relax)
- `--fmax`: Force convergence for relaxation (default: 0.001 eV/Å)

## 4. Output Files

- `vibration_results.json`: Summary including:
  - `frequencies_cm1`: All frequencies in cm⁻¹
  - `frequencies_meV`: All frequencies in meV
  - `real_modes`: Indices and frequencies of real vibrational modes
  - `imaginary_modes`: Indices and frequencies of imaginary modes (should be near zero)
  - `zero_point_energy_eV`: Zero-point energy in eV
  - `n_atoms`, `formula`, `is_linear`
- `vib.N.traj`: Trajectory files for each vibrational mode (for visualization)

## 5. Examples

See `examples/H2O/` for a water molecule vibration analysis.

```bash
# Env: mace-agent
python .agents/skills/chem-vibration/scripts/calculate_vibrations.py \
    --molecule H2O \
    --model_type mace \
    --model_name MACE-OMAT-0-small \
    --output_dir .agents/skills/chem-vibration/examples/H2O
```

Expected H2O vibrational modes (experimental reference):
| Mode | Type | Experimental (cm⁻¹) |
|------|------|---------------------|
| Bending | ν₂ | ~1595 |
| Symmetric stretch | ν₁ | ~3657 |
| Asymmetric stretch | ν₃ | ~3756 |

## 6. Constraints

- **Molecule/cluster only**: This skill applies the harmonic approximation to finite systems. For periodic crystals, use [mat-phonon](../mat-phonon/SKILL.md).
- **Equilibrium required**: The structure MUST be at a local minimum (forces ≈ 0). Large residual forces invalidate the harmonic approximation.
- **Harmonic approximation**: Only valid near equilibrium. Accuracy degrades for large-amplitude motions and near dissociation.
- **Environments**: Scripts require conda environments with MLIP packages:
  - `mace-agent` for MACE models
  - `matgl-agent` for MatGL/CHGNet models
  - `fairchem-agent` for FairChem/UMA models
---

**Author:** Bowen Deng  
**Contact:** [GitHub @bowen-bd](https://github.com/bowen-bd)
