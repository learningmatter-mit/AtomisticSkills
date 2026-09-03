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
- `--relax_deformed` / `--no-relax_deformed` (**default on**): re-minimise the ions inside each deformed cell, with the cell held fixed. See **Relaxed-ion versus clamped-ion** below — this flag selects which of two physically distinct quantities you get, and the difference is not small.
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
- **Structure Relaxation**: two distinct stages, controlled by two different flags. `--relax_structure` (default on) relaxes the input cell *before* the strain scan, so the scan is centred on a stress-free reference — elastic constants are defined about zero stress, so this matters. `--relax_deformed` (default on) controls the *per-deformation* ion relaxation, which selects between two different physical quantities; see below.
- **Linear Regime**: Strains must be small enough to remain in the linear elastic regime. The default values are appropriate for most inorganic crystalline materials.
- **Unit Conversion**: MatCalc returns moduli in eV/ų (bulk, shear) and Pa (Young's). The script converts all to GPa.
- **Symmetry**: By default, symmetry reduction is disabled (`--symmetry` flag enables it). This means all 21 independent components are fitted independently.

## Relaxed-ion versus clamped-ion

Applying a strain to a crystal leaves internal degrees of freedom that the strain does
not itself fix — the fractional coordinates of atoms on general Wyckoff positions. What
you do with them decides which elastic constant you compute:

| | `--relax_deformed` (default) | `--no-relax_deformed` |
| --- | --- | --- |
| ions in the deformed cell | re-minimised at fixed cell | carried rigidly by the affine strain |
| quantity | **relaxed-ion**, a.k.a. equilibrium | **clamped-ion**, a.k.a. frozen-ion |
| physical meaning | second derivative of the energy *minimised over* the internal coordinates — what a real crystal exhibits | second derivative at frozen internal coordinates |
| cost | one ionic relaxation per deformation | one energy/stress evaluation per deformation |

Relaxed-ion is the default here because it is the macroscopic elastic constant: it is
what experiment measures and what the Materials Project and `atomate2` elastic
workflows compute (ionic relaxation at fixed cell for every deformation). Note that
`matcalc`'s own `ElasticityCalc` defaults `relax_deformed_structures=False`, so
inheriting that default silently gives the clamped-ion answer instead.

Clamped-ion is systematically **stiffer**, because freezing the ions suppresses the
non-affine internal displacement that would otherwise relieve part of the strain. It is
a reasonable fast screening choice, and it is exact only where symmetry leaves no
internal degrees of freedom to relax (every atom on a special position, as in B1 or B2
binaries). Otherwise the gap is real: for Pnma CaMgSi it is 1.4% on the bulk modulus but
7.5% on the shear modulus, 7.3% on the Poisson ratio and 37% on the anisotropy index.
Report which one you used.

## Derived properties

Beyond the tensor and the VRH averages, the script reports the standard post-processing
of an elastic tensor. Two of these are easy to get wrong by hand:

- **Universal anisotropy index** `A^U = 5 G_V/G_R + B_V/B_R - 6` (Ranganathan &
  Ostoja-Starzewski, PRL **101**, 055504 (2008)), zero only for an isotropic crystal.
  It needs the Voigt and Reuss bounds kept separate, so it cannot be recovered from the
  VRH averages; the Voigt and Reuss bulk and shear moduli are reported alongside it.
- **Directional Young's moduli** from `E(n) = 1 / (S_ijkl n_i n_j n_k n_l)`: along
  `[100]`, `[010]`, `[001]`, plus the global minimum and maximum over *all* directions
  with the directions they occur in. Two traps here. Expanding the Voigt compliance to
  `S_ijkl` requires a factor of 1/4 on shear-shear entries (`S_1212 = S_66/4`, not
  `S_66`) and 1/2 on normal-shear — the stiffness expands with no factors, so the two
  cannot share a helper. And the extrema of an anisotropic crystal **need not lie on a
  crystal axis**: for CaMgSi the stiffest direction sits ~40° off *a* in the *a*–*c*
  plane and is 13% stiffer than the stiffest axis, so scanning only the axes is wrong.
- **Acoustic and Debye properties**: density, longitudinal and transverse sound
  velocities, the Debye mean velocity and the Debye temperature via the Anderson
  relation `Theta_D = (hbar/k_B)(6 pi^2 N/V)^(1/3) v_m`. The mean is the harmonic-cube
  mean over one longitudinal and two transverse branches, not the arithmetic mean of the
  two branches (which runs ~20% high).
- **Shear-modulus extrema** over all shear systems, from
  `G(n,m) = 1/(4 S_ijkl n_i m_j n_k m_l)` with `m` in the plane normal to `n`. This is a
  genuinely *two-dimensional* search — over the sphere and over the angle within each
  plane — where Young's modulus needs only the sphere. `min(C44, C55, C66)` is not a
  substitute: on an orthorhombic intermetallic it sits ~26% high.
- **Acoustic branch velocities** along `--acoustic_direction`, from the eigenvalues of
  the Christoffel matrix `Gamma_ik(n) = C_ijkl n_j n_l`. One quasi-longitudinal and two
  quasi-transverse branches, and in an anisotropic crystal the transverse pair is *not*
  degenerate — the slow branch can run >10% below the isotropic transverse velocity, so
  the isotropic moduli cannot reproduce these.
- **Born stability** from the eigenvalues of the tensor, and the Pugh ratio `G/B`.

## Moduli under load

`--pressure <GPa>` relaxes cell and ions against a hydrostatic load first, so the whole
analysis is reported about a pressure-loaded reference. Two things to know:

- ASE's `FrechetCellFilter` takes `scalar_pressure` in **eV/Å³**; the flag is in GPa and
  converts internally. Passing GPa straight into ASE applies ~160× the intended load.
- What comes back are the **stress-strain coefficients** about the loaded reference, not
  the Birch coefficients that carry explicit pressure corrections. Those are a different
  quantity, and the one you want for elastic *stability* under load.

matcalc's own pre-relaxation is at zero pressure, so `--pressure` performs the loaded
relaxation itself and then disables `relax_structure` — otherwise the scan would be
re-centred back on the zero-pressure cell.
---

**Author:** Bowen Deng
**Contact:** [GitHub @learningmatter-mit](https://github.com/learningmatter-mit)
