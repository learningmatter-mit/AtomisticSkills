---
name: mp2020-compatibility
description: Energy corrections needed when using certain MLIPs for phase diagram construction / formation energy calculations.
---

# MP2020 Compatibility

## Goal
To apply [Materials Project 2020 Compatibility](https://pymatgen.org/pymatgen.entries.compatibility.html) schemes to MLIP-predicted energies. This is required for models trained on GGA/GGA+U mixed data (e.g., MPtrj data) when constructing convex hulls or phase diagrams to ensure compatibility with the Materials Project database.

> [!IMPORTANT]
> **Do NOT apply this to r2SCAN models.** 
> Only use this for models trained on GGA/GGA+U mixed data.

## Scientific Context

### Why is this needed?
The Materials Project (MP) database mixes calculations from two levels of theory: **GGA (PBE)** and **GGA+U**. Transition metals (e.g., Mn, Fe, Co, Ni) are calculated with a Hubbard U correction *only* when present in oxides or fluorides; otherwise, they use standard PBE. To construct a unified convex hull, MP applies the **MP2020 Compatibility** scheme (energy shifts) to align these distinct potential energy surfaces.

MLIPs trained on MP data (e.g., MACE-MP-0) typically learn these mixed energies. To accurately predict stability against the MP hull, one must apply the same MP2020 corrections to the MLIP outputs.

### Potential Issues
Selective application of U introduces discontinuities in the Potential Energy Surface (PES) that are difficult for MLIPs to model physically.
*   **Artifacts**: Models may exhibit spurious repulsion or underbinding between U-corrected metals and ligands, as they interpolate between incompatible GGA and GGA+U regimes.

### References
1.  **MP2020 Framework**: Wang, A., Kingsbury, R., McDermott, M. et al. *A framework for quantifying uncertainty in DFT energy corrections.* Sci Rep 11, 15496 (2021). [DOI](https://doi.org/10.1038/s41598-021-94550-5)
2.  **Impact on MLIPs**: *Better without U: Impact of Selective Hubbard U Correction on Foundational MLIPs.* arXiv:2601.21056 (2026). [link](https://arxiv.org/abs/2601.21056)

## Compatible Models
This correction is **REQUIRED** for:
- **MACE-MH-1** `omat_pbe` head (default)
- **MACE-MH-0** `omat_pbe` head
- **MACE-OMAT-0-small**, **MACE-OMAT-0-medium**
- **MACE-MP-small**, **MACE-MP-medium**, **MACE-MP-large**
- **M3GNet-MP-2021.2.8-PES**
- **M3GNet-MP-2021.2.8-DIRECT-PES**
- **uma-s-1**, **uma-s-1p1**, **uma-m-1p1** (with `omat` head)

This correction is **NOT** for:
- **CHGNet** (e.g. `CHGNet-MatPES-r2SCAN-2025.2.10-2.7M-PES`)
- **MACE-MATPES-r2SCAN-0**
- **TensorNet-MatPES-r2SCAN-v2025.1-PES**

> [!NOTE]
> The full list of compatible models can be found in `resources/gga-ggau-mixed-mlips.yaml`.

## Instructions

### 1. Check Compatibility
Use the `check_compatibility.py` script to programmatically determine if a model/head requires correction.

```bash
python .agent/skills/mp2020-compatibility/scripts/check_compatibility.py --name "MACE-MH-1" --head "omat_pbe"
# Exit code 0 if required, 1 if not.
```

### 2. Apply Correction to a Structure
Use the `apply_correction.py` script to calculate the corrected energy for a single structure.

To run on a directory of structure files (batch mode):
```bash
# Energy defaults to 0.0 if not specified (useful for just checking corrections)
python .agent/skills/mp2020-compatibility/scripts/apply_correction.py /path/to/structure_dir/
```

To run on a specific file with known energy:
```bash
# Env: base-agent
python .agent/skills/mp2020-compatibility/scripts/apply_correction.py structure.cif --energy -123.45
```

### 2. Batch Processing
For referencing or phase diagram generation, apply this correction to every entry before computing E_hull.

## Constraints
- **Environment**: `base-agent` (requires `pymatgen`).
- **Input Energy**: Must be the *total energy* in eV (not per atom).


Author: Bowen Deng
Contact: github username <bowen-bd>
