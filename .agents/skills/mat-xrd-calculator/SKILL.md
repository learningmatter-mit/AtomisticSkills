---
name: mat-xrd-calculator
description: Calculate the X-ray Diffraction (XRD) spectrum of a material using pymatgen.
category: [materials]
---

# XRD Spectrum Calculation

This skill calculates the X-ray Diffraction (XRD) pattern of a crystal structure using `pymatgen`. It identifies diffraction peaks, their intensities, and associated (hkl) indices.

## Requirements

- Conda environment: `base-agent`
- `pymatgen`
- `matplotlib`

## Usage

The primary script for this skill is `calculate_xrd.py`. It takes a structure file as input and generates a JSON file with the diffraction data and a plot of the intensities versus $2\theta$.

### Command Line Interface

```bash
python .agents/skills/mat-xrd-calculator/scripts/calculate_xrd.py <structure_file> --output_dir <output_dir> --wavelength <wavelength>
```

### Arguments

- `structure`: Path to the input structure file (e.g., `POSCAR`, `CIF`).
- `--output_dir`: (Optional) Directory to save the results. Defaults to the current directory.
- `--wavelength`: (Optional) Radiation wavelength or source name (e.g., `CuKa`, `MoKa`, `CrKa`). Defaults to `CuKa` ($1.54184$ Å).
- `--symprec`: (Optional) Symmetry precision for identifying equivalent peaks. Defaults to `0.1`.

## Output Files

1.  `<filename>_xrd.json`: Contains $2\theta$ positions, intensities, d-spacings, and (hkl) indices.
2.  `<filename>_PV_xrd.png`: A plot of the simulated XRD spectrum (Pseudo-Voigt model).

## Example

To calculate the XRD pattern for LiFePO4:

```bash
```bash
conda activate base-agent
python .agents/skills/mat-xrd-calculator/scripts/calculate_xrd.py .agents/skills/mat-xrd-calculator/examples/LiFePO4/LiFePO4.cif --output_dir .agents/skills/mat-xrd-calculator/examples/LiFePO4
```
```

## Foundation Potential Recommendations

Since XRD is a purely geometric property of the crystal structure, it does not require a machine learning interatomic potential (MLIP) for the calculation itself. However, it is **highly recommended** to perform a structure relaxation using a high-quality MLIP (e.g., MACE, CHGNet) before calculating the XRD pattern to ensure the structure is at its energy minimum.

For recommendations on relaxation models, see the [ml-foundation-potentials](file:///home/bdeng/projects/AtomisticSkills/.agents/skills/ml-foundation-potentials/SKILL.md) skill.
---

**Author:** Bowen Deng  
**Contact:** [GitHub @bowen-bd](https://github.com/bowen-bd)
