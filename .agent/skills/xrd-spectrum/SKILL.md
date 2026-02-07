---
name: xrd-spectrum
description: Calculate the X-ray Diffraction (XRD) spectrum of a material using pymatgen.
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
python .agent/skills/xrd-spectrum/scripts/calculate_xrd.py <structure_file> --output_dir <output_dir> --wavelength <wavelength>
```

### Arguments

- `structure`: Path to the input structure file (e.g., `POSCAR`, `CIF`).
- `--output_dir`: (Optional) Directory to save the results. Defaults to the current directory.
- `--wavelength`: (Optional) Radiation wavelength or source name (e.g., `CuKa`, `MoKa`, `CrKa`). Defaults to `CuKa` ($1.54184$ Å).
- `--symprec`: (Optional) Symmetry precision for identifying equivalent peaks. Defaults to `0.1`.

## Output Files

1.  `<filename>_xrd.json`: Contains $2\theta$ positions, intensities, d-spacings, and (hkl) indices.
2.  `<filename>_xrd.png`: A plot of the XRD spectrum.

## Example

To calculate the XRD pattern for LiFePO4:

```bash
conda activate base-agent
python .agent/skills/xrd-spectrum/scripts/calculate_xrd.py examples/LiFePO4/LiFePO4.cif --output_dir .agent/test/xrd_test
```

## Foundation Potential Recommendations

Since XRD is a purely geometric property of the crystal structure, it does not require a machine learning interatomic potential (MLIP) for the calculation itself. However, it is **highly recommended** to perform a structure relaxation using a high-quality MLIP (e.g., MACE, CHGNet) before calculating the XRD pattern to ensure the structure is at its energy minimum.

For recommendations on relaxation models, see the [foundation-potentials](file:///home/bdeng/projects/AtomisticSkills/.agent/skills/foundation-potentials/SKILL.md) skill.
