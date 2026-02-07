---
name: qha-thermal-expansion
description: Calculate Quasi-Harmonic Approximation (QHA) thermal properties using MLIPs.
---

# QHA Thermal Expansion Skill

This skill provides tools for calculating thermal expansion and temperature-dependent Gibbs energy using Machine Learning Interatomic Potentials (MLIPs).

## 1. Prerequisites

- The appropriate MLIP wrapper must be available (`MACEWrapper`, `MatGLWrapper`, or `FAIRCHEMWrapper`).
- `matcalc` must be installed in the relevant conda environment.

## 2. Choosing a Foundation Potential

QHA calculations require accurate lattice expansion and vibrational properties.

> [!IMPORTANT]
> - **Use OMAT or MatPES trained models**: These models (e.g., `MACE-OMAT-0-small`, `TensorNet-MatPES-r2SCAN`) are specifically optimized for forces and vibrational stability.
> - **Avoid MPtrj-trained models**: Models trained primarily on the `MPtrj` dataset (e.g., `CHGNet-MPtrj`) suffer from the "softening" problem, where the calculated phonon frequencies are significantly lower than DFT values.

Refer to the [foundation-potentials skill](../foundation-potentials/SKILL.md) for more details.

## 3. Calculation Workflow

To calculate thermal expansion and temperature-dependent Gibbs energy, use `calculate_qha.py`.

```bash
conda activate matgl-agent
python .agent/skills/qha/scripts/calculate_qha.py \
    --structure path/to/relaxed_structure.cif \
    --model_type matgl \
    --eos vinet \
    --output_dir research/my_folder/qha
```

## 4. Output Files

- `qha_results.json`: Summary.
- `gibbs_temperature.dat`: Gibbs energy vs T.
- `thermal_expansion.dat`: Thermal expansion vs T.

## 5. Examples

See `examples/` for detailed usage scenarios.
