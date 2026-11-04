---
name: mat-qha-thermal-expansion
description: Calculate Quasi-Harmonic Approximation (QHA) thermal properties using MLIPs.
metadata:
  category: [materials]
  venv: [mlip]
---

# QHA Thermal Expansion Skill

This skill provides tools for calculating thermal expansion and temperature-dependent Gibbs energy using Machine Learning Interatomic Potentials (MLIPs).

## 1. Prerequisites

- The appropriate MLIP wrapper must be available (`MACEWrapper`, `MatGLWrapper`, or `FAIRCHEMWrapper`).
- `matcalc` is included in the `mlip` and `fairchem` environments.

## 2. Choosing a Foundation Potential

QHA calculations require accurate lattice expansion and vibrational properties.

> [!IMPORTANT]
> - **Use OMAT or MatPES trained models**: These models (e.g., `MACE-OMAT-0-small`, `TensorNet-MatPES-r2SCAN`) are specifically optimized for forces and vibrational stability.
> - **Avoid MPtrj-trained models**: Models trained primarily on the `MPtrj` dataset (e.g., `MACE-MP-small`, `MACE-MP-medium`) suffer from the "softening" problem, where the calculated phonon frequencies are significantly lower than DFT values.

Refer to the [foundation-potentials skill](../ml-foundation-potentials/SKILL.md) for more details.

## 3. Choosing the Volume Window

QHA fits the free energy against volume -- `phonopy-qha` fits `E(V) + F_vib(V,T)` to a
Vinet, Birch-Murnaghan or Murnaghan equation of state at each temperature and minimises
it -- so the sampled volume range is a real input, and you should report it alongside
the result.

**The convention is +/-5% in LINEAR strain, which is -14% to +16% in volume:**

| source | window | volume width |
|---|---|---|
| `matcalc` `QHACalc` default `scale_factors` | 0.95-1.05 linear | 1.35x |
| `atomate2` `QhaMaker` default `linear_strain` | (-0.05, 0.05) | 1.35x |
| `phonopy` `Si-QHA` example `e-v.dat` | 140.03-189.07 A^3 | 1.35x |

Note the cube: a window quoted as "+/-5%" in lattice parameter is three times that in
volume. Read which convention a tool means before comparing windows across codes --
`QHACalc` scales the lattice (`apply_strain`), not the volume.

Omit `--volume_window` to retain MatCalc's native scale grid; `--n_volumes` only
applies when a volume window is supplied. For example,
`--volume_window 0.10 --n_volumes 7` samples seven volumes from 0.90 to 1.10 times
the relaxed volume,
with lattice scale factors obtained by taking their cube roots.

> [!IMPORTANT]
> **The window must bracket the free-energy minimum at your highest temperature.** The
> lattice expands on heating, so a window adequate at 0 K can be too narrow at high T,
> and a minimiser that runs into the edge of the scan returns the edge rather than the
> minimum. Check that the equilibrium volume at your top temperature is interior to the
> sampled volumes, and widen `--volume_window` if it is not. `phonopy` requires at least
> 5 volume points; 11 is the usual choice.

> [!NOTE]
> **Widening the window is not automatically safer.** On BCC lithium with
> a MatGL MatPES-PBE potential, going from +/-10% to the conventional +/-14/+16% in volume
> moves the 0 K equilibrium volume by 0.09 A^3 (0.5%) and the thermal expansion
> coefficient by 9%, with every sampled volume still dynamically stable -- so this is
> fit sensitivity, not a soft-mode artefact. Neither window is wrong; quote the one you
> used. If you need a number comparable to someone else's, match their window rather
> than assuming a default agrees.

## 4. Calculation Workflow

To calculate thermal expansion and temperature-dependent Gibbs energy, use `calculate_qha.py`.

```bash
${CLAUDE_SKILL_DIR}/../../venv/run mlip python ${CLAUDE_SKILL_DIR}/scripts/calculate_qha.py \
    --structure path/to/relaxed_structure.cif \
    --model_type matgl \
    --eos vinet \
    --output_dir research/my_folder/qha
```

## 5. Output Files

- `qha_results.json`: Summary.
- `gibbs_temperature.dat`: Gibbs energy vs T.
- `thermal_expansion.dat`: Thermal expansion vs T.

## 6. Examples

See `examples/` for detailed usage scenarios.
---

**Author:** Bowen Deng
**Contact:** [GitHub @learningmatter-mit](https://github.com/learningmatter-mit)
