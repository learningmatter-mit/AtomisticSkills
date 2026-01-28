---
trigger: model_decision
description: Rules for standardizing and selecting HTVS chemical configurations (chemconfigs).
---

# HTVS Chemical Configuration Standards

This document defines the naming conventions and standard configurations for High-Throughput Virtual Screening (HTVS) jobs, specifically for VASP.

## Naming Convention

HTVS `chemconfig` names follow a specific "underscore-separated" taxonomy:

`[FUNCTIONAL]_[DISPERSION]_[BASIS]_[TASK]_[CODE]`

### 1. Functional
- `pbe`: Perdew-Burke-Ernzerhof (GGA). Standard for most materials.
- `r2scan`: r2SCAN (Meta-GGA). Higher accuracy, more expensive.
- `pbe_u`: PBE + U (Hubbard U). For transition metal oxides/correlated systems.

### 2. Dispersion Correction
- `d3`: DFT-D3 with Becke-Johnson damping (`IVDW=12` in VASP). **Recommended** for most systems to capture van der Waals interactions.
- `(empty)`: No dispersion correction.

### 3. Basis/Potential Set
- `paw`: Projector Augmented Wave method. Standard VASP potentials.
- `def2svp`, `def2tzvp`: Gaussian basis sets (for ORCA/QChem).

### 4. Task Type
- `opt`: Geometry Optimization (Relaxation).
    - typically `IBRION=2` (CG) or `1` (RMM-DIIS).
    - `ISIF=3` (Volume + Ions) for Bulk.
    - `ISIF=2` (Ions only) for Surfaces/Defects.
- `engrad`: Static calculation of Energy and Forces (no relaxation).
    - `NSW=0`.
- `bomd`: Born-Oppenheimer Molecular Dynamics.
    - `IBRION=0`, `MDALGO=2` (Nose-Hoover) or `1` (Andersen).
- `neb`: Nudged Elastic Band transition state search.

### 5. DFT Code
- `vasp`: Vienna Ab initio Simulation Package.
- `orca`: ORCA quantum chemistry package.
- `qchem`: Q-Chem.

## Standard VASP Configurations

| Task | Configuration Name | Description | Key INCAR Tags |
| :--- | :--- | :--- | :--- |
| **Standard Relaxation** | `pbe_d3_paw_opt_vasp` | Robust default for relaxing structures. | `IBRION=2`, `ISIF=3` (Bulk) / `2` (Surf), `IVDW=12` |
| **Accurate Relaxation** | `r2scan_paw_opt_vasp` | detailed geometry optimization. | `METAGGA=R2SCAN`, `LASPH=.TRUE.` |
| **Static Calculation** | `pbe_d3_paw_engrad_vasp` | Energy & Forces matching training data. | `NSW=0`, `IBRION=-1` |
| **Molecular Dynamics** | `pbe_d3_paw_bomd_vasp` | Sampling PES for training data. | `IBRION=0`, `POTIM=2.0` |
| **Spin Polarized** | `*_spinpol_*` | For magnetic systems (Fe, Ni, Co). | `ISPIN=2`, `MAGMOM` initialized |

## Configuration Rules

1.  **Always prefer D3**: Unless you have a specific reason (e.g. reproducing old PBE data), always use the `_d3_` variant.
2.  **Match Training Data**: If fine-tuning a model trained on Materials Project (MP) data, use MP-compatible settings (often just PBE or PBE+U without D3 for older data, but `r2scan` or `pbe_d3` for newer datasets).
3.  **Surfaces MUST use ISIF=2**: When relaxing surfaces, ensure the `chemconfig` DOES NOT relax the cell vectors (`ISIF=3`), or manual `details` override is applied.
