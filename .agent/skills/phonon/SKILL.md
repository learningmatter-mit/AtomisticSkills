---
name: phonon
description: Calculate vibrational properties (phonon dispersions, density of states, thermal properties) using MLIPs.
---

# Phonon Calculation Skill

This skill provides tools for calculating vibrational properties of materials using Machine Learning Interatomic Potentials (MLIPs).

## 1. Prerequisites

- The appropriate MLIP wrapper must be available (`MACEWrapper`, `MatGLWrapper`, or `FAIRCHEMWrapper`).
- `matcalc`, `phonopy`, and `phono3py` must be installed in the relevant conda environment.

## 2. Choosing a Foundation Potential

Phonon calculations are highly sensitive to the quality of the potential energy surface (PES). 

> [!IMPORTANT]
> - **Use OMAT or MatPES trained models**: These models (e.g., `MACE-OMAT-0-small`, `TensorNet-MatPES-r2SCAN`) are specifically optimized for forces and vibrational stability.
> - **Avoid MPtrj-trained models**: Models trained primarily on the `MPtrj` dataset (e.g., `CHGNet-MPtrj`) suffer from the "softening" problem, where the calculated phonon frequencies are significantly lower than DFT values.

Refer to the [foundation-potentials skill](../foundation-potentials/SKILL.md) for more details.

## 3. Calculation Workflow

To calculate phonon properties, use the `calculate_phonon.py` script.

```bash
conda activate mace-agent
python .agent/skills/phonon/scripts/calculate_phonon.py \
    --structure path/to/relaxed_structure.cif \
    --model_type mace \
    --model_name MACE-MP-small \
    --supercell_matrix '[[2,0,0],[0,2,0],[0,0,2]]' \
    --output_dir research/my_folder/phonon
```

## 4. Output Files

- `phonon_results.json`: Summary.
- `phonon.yaml`: Phonon data.
- `band_structure.yaml`: Band structure.
- `total_dos.dat`: Density of states.

## 5. Examples

See `examples/` for detailed usage scenarios.


Author: Bowen Deng
Contact: github username <bowen-bd>
