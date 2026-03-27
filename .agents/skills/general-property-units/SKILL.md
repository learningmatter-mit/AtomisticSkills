---
name: general-property-units
description: Reference guide for energy, force, and stress units across MLIPs, DFT codes, and ASE, including conversion factors.
category: [machine-learning]
---

# Units Reference for Atomistic Simulations

## Goal

Provide a single authoritative reference for units of **energy**, **forces**, and **stress** across all MLIPs, DFT codes, and simulation tools used in this project, including the conversions applied internally.

## Project Standard

All internal representations follow the **ASE (Atomic Simulation Environment)** convention:

| Quantity | Standard Unit | Notes |
|:---------|:-------------|:------|
| **Energy** | eV | Total energy of the system |
| **Energy per atom** | eV/atom | Used for MAE reporting and training labels |
| **Forces** | eV/Å | Negative gradient of energy w.r.t. position |
| **Stress** | eV/Å³ | Voigt notation, 6-component (xx, yy, zz, yz, xz, xy) |

## MLIP Model Units

### Prediction (Inference)

All MLIP wrappers return predictions in ASE standard units through their ASE calculator interface:

| Model | Energy | Forces | Stress | Notes |
|:------|:-------|:-------|:-------|:------|
| **MACE** | eV | eV/Å | eV/Å³ | Native ASE units |
| **CHGNet** | eV | eV/Å | eV/Å³ | Native ASE units |
| **UMA (FairChem)** | eV | eV/Å | eV/Å³ | Native ASE units |
| **M3GNet / TensorNet (MatGL)** | eV | eV/Å | eV/Å³ | Native ASE units |

### Training Input Labels

Training labels in `training_data.json` are stored in ASE standard units (eV, eV/Å, eV/Å³). Conversions to trainer-specific units are handled **automatically** inside each wrapper:

| Trainer | Energy Input | Force Input | Stress Input | Internal Conversion |
|:--------|:-------------|:------------|:-------------|:-------------------|
| **MACE** | eV | eV/Å | eV/Å³ | None — trains in eV/Å³ |
| **FairChem (UMA)** | eV | eV/Å | eV/Å³ | None — trains in eV/Å³ |
| **MatGL (CHGNet/M3GNet)** | eV | eV/Å | **GPa** (converted) | `eV/Å³ → GPa` in `_prepare_training_data` |

> [!IMPORTANT]
> **MatGL is the only trainer that requires stress conversion.** The conversion from eV/Å³ → GPa is performed automatically inside `MATGLWrapper._prepare_training_data()`. Users should always provide stress labels in eV/Å³.

### Training Output (Saved Metrics)

Each MLIP trainer natively reports MAE in **eV**. All wrappers apply a **×1000 conversion** to save MAE values in **meV** to `training_history.json` and plot axes in `training_history.png`, for human readability and consistent cross-model comparison:

| Trainer | Native Energy MAE | Native Force MAE | Native Stress MAE | Saved Unit |
|:--------|:------------------|:-----------------|:-------------------|:-----------|
| **MACE** | eV/atom | eV/Å | eV/Å³ | **meV** (×1000) |
| **FairChem (UMA)** | eV/atom | eV/Å | eV/Å³ | **meV** (×1000) |
| **MatGL (CHGNet/M3GNet)** | eV/atom | eV/Å | GPa → eV/Å³ | **meV** (×1000) |

The `training_history.json` keys and their units:

| Key | Unit |
|:----|:-----|
| `energy_mae_train` / `energy_mae_val` | meV/atom |
| `force_mae_train` / `force_mae_val` | meV/Å |
| `stress_mae_train` / `stress_mae_val` | meV/Å³ |
| `loss_train` / `loss_val` | Dimensionless (weighted combination) |

> [!NOTE]
> For MatGL stress: the trainer computes MAE in GPa internally. The wrapper converts back to eV/Å³ first, then multiplies by 1000 to get meV/Å³, matching the other wrappers.

## DFT Code Units

### VASP

| Quantity | VASP Internal | VASP OUTCAR | Conversion to ASE Standard |
|:---------|:-------------|:------------|:--------------------------|
| **Energy** | eV | eV | None needed |
| **Forces** | eV/Å | eV/Å | None needed |
| **Stress** | kB (kilo-Bar) | kB (and GPa) | `kB × 0.1 = GPa`, then `GPa × 0.0062415 = eV/Å³` |

> [!NOTE]
> VASP stores stress internally in **kB** (kilo-Bar). The `vasprun.xml` parser in pymatgen returns stress in kB. The Atomate2 MCP tool applies the conversion `kB → eV/Å³` automatically when `convert_units=True` (default).

### Sign Convention

VASP reports stress with the **opposite sign** to the physics and ASE convention:
- VASP: positive = **compressive** (pressure-like)
- ASE/Physics/MLIPs: positive = **tensile**

The sign flip is handled during VASP output parsing (e.g. in the `atomate2` MCP tool, VASP stress is multiplied by `-1` in addition to the unit conversion).

## Common Conversion Factors

| From | To | Factor | ASE Code |
|:-----|:---|:-------|:---------|
| GPa | eV/Å³ | 0.00624150913 | `ase.units.GPa` |
| eV/Å³ | GPa | 160.21766208 | `1.0 / ase.units.GPa` |
| kB | GPa | 0.1 | — |
| kB | eV/Å³ | 0.000624150913 | `0.1 * ase.units.GPa` |
| eV | kJ/mol | 96.4853 | `ase.units.kJ / ase.units.mol` |
| eV | kcal/mol | 23.0605 | `ase.units.kcal / ase.units.mol` |
| Å | Bohr | 1.8897259886 | `1.0 / ase.units.Bohr` |

## Quick Reference: Python Conversions

```python
# Env: base-agent
from ase import units

# Stress conversions
stress_GPa = stress_eV_per_A3 / units.GPa        # eV/Å³ → GPa
stress_eV_per_A3 = stress_GPa * units.GPa         # GPa → eV/Å³
stress_eV_per_A3 = stress_kB * 0.1 * units.GPa    # kB → eV/Å³

# Energy conversions
energy_kJ_per_mol = energy_eV * units.kJ / units.mol
energy_kcal_per_mol = energy_eV * units.kcal / units.mol
```

## Constraints

- **Never** mix unit systems within a single workflow.
- **Always** verify stress units when comparing MLIP predictions to DFT references.
- Training data JSON files must use eV/Å³ for stress — wrapper-internal conversion handles the rest.
- When reporting MAE in papers/docs, specify the unit explicitly (e.g., "Force MAE: 50 meV/Å").
---

**Author:** Bowen Deng  
**Contact:** [GitHub @bowen-bd](https://github.com/bowen-bd)
