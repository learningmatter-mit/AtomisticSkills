---
name: mat-lattice-thermal-conductivity
description: Calculate lattice thermal conductivity of materials with MLIPs.
category: [materials]
---

# Lattice Thermal Conductivity Calculation Skill

This skill provides tools for calculating lattice thermal conductivity of materials using anharmonic lattice dynamics with Machine Learning Interatomic Potentials (MLIPs).

> [!WARNING]
> Lattice thermal conductivity only considers phonon-phonon interactions. It can be considered that lattice thermal conductivity accurately models the thermal conductivity of non-metallic materials. For metallic materials, electron-phonon interactions also need to be considered to accurately calculate thermal conductivity, which is beyond the scope of this skill.

## 1. Prerequisites

- The appropriate MLIP wrapper must be available (`MACEWrapper`, `MatGLWrapper`, or `FAIRCHEMWrapper`).
- `matcalc`, `phonopy`, and `phono3py` must be installed in the relevant conda environment.

### Required Patch for phono3py ≥ 3.x

phono3py 3.x renamed `ConductivityRTA.kappa_TOT_RTA` to `.kappa`. Apply the following one-line fix in `matcalc/src/matcalc/_phonon3.py`:

```diff
-kappa = np.asarray(phonon3.thermal_conductivity.kappa_TOT_RTA)
+kappa = np.asarray(phonon3.thermal_conductivity.kappa)
```

## 2. Choosing a Foundation Potential

Phonon and thermal conductivity calculations are highly sensitive to the quality of the potential energy surface (PES). 

> [!IMPORTANT]
> - **Use OMAT or MatPES trained models**: These models (e.g., `MACE-OMAT-0-small`, `TensorNet-MatPES-r2SCAN`) are specifically optimized for forces and vibrational stability.
> - **Avoid MPtrj-trained models**: Models trained primarily on the `MPtrj` dataset (e.g., `CHGNet-MPtrj`) suffer from the "softening" problem, where the calculated phonon frequencies are significantly lower than DFT values.

Refer to the [foundation-potentials skill](../ml-foundation-potentials/SKILL.md) for more details.

## 3. Calculation Workflow

### Step One: Verify given material is an insulator / semiconductor

First of all, using the [`mat-electronic-structure` skill](../mat-electronic-structure/SKILL.md) to calculate the band gap of the given material or retrieve the band gap from Materials Project. If the band gap does not exist, the material is a metal, and this skill cannot give a meaningful prediction on thermal conductivity. Otherwise, the material is an insulator, and we can proceed to next step.

### Step Two: Calculate phonon properties

Before calculating thermal conductivity (which is related to higher order force constants), we need to calculate phonon properties which is related to second order force constants. Use the [`mat-phonon` skill](../mat-phonon/SKILL.md) to calculate phonon properties. 

Check the `phonon_results.json` file and phonon band structure to see if the phonon properties are reasonable, especially for imaginary frequencies in phonon band. If there are imaginary frequencies, the structure is not stable. In this case, redo the structure optimization first, and if it does not work, try different models/methods. Only after validating the phonon properties, proceed to calculate thermal conductivity.

### Step Three: Calculate lattice thermal conductivity

```sh
# Env: mace-agent
python .agents/skills/mat-lattice-thermal-conductivity/scripts/calculate_thermal_conductivity.py \
    --structure Si.cif \
    --model_type mace \
    --model_name MACE-OMAT-0-small \
    --output_dir si_mace_thermal_conductivity
```

See `examples/README.md` for detailed usage scenarios.

## 4. Output Files

- `lattice_thermal_conductivity_results.json`: Summary.
- `phonon3.yaml`: Third order force constants and supercell data.

## 5. Examples

See `examples/` for detailed usage scenarios.

---

**Author:** Bohan Li
**Contact:** [GitHub @bkhli](https://github.com/bkhli)
