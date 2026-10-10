---
name: mat-elemental-energies
description: A library of ground-state element structures and their energies calculated from MLIPs. Used to calculate formation energies of compounds.
metadata:
  category: [materials]
  venv: [cpu]
---

# Elemental Energies

## Goal
To provide a centralized library of the most stable phases (ground states) for each element and their corresponding reference energies calculated using different Machine Learning Interatomic Potentials (MLIPs). This avoids redundant relaxations and ensure consistency in thermodynamics calculations (e.g., formation energy, stability).

## Instructions

### 1. Retrieve Elemental Energies
To get the energies for a list of elements from a specific checkpoint:
```bash
${CLAUDE_SKILL_DIR}/../../venv/run cpu python ${CLAUDE_SKILL_DIR}/scripts/get_elemental_energies.py --elements Li Fe O --checkpoint mace-mp-medium
```
Checkpoint names are matched case-insensitively against `resources/<checkpoint>_energies.json`. Add `--output refs/energies.json` to save the energies, with `input_configs.yaml` next to them.


## Library Status
As of **2026-01-30**, the library is fully expanded and contains **89 elements** (Ground states from H to Lr) across **36 MLIP variants**, including:
- **MACE**: MACE-MP (S/M/L), MACE-MH-0/1 (all heads), MACE-OMAT (S/M), MACE-MATPES (PBE/R2SCAN).
- **MatGL**: CHGNet (MPtrj, MatPES), M3GNet (MP, MatPES), TensorNet (MatPES).
- **FairChem**: UMA (S/M) with all heads (omat, omol, oc20).

**Corrections (2026-10):** `TensorNet-MatPES-r2SCAN-v2025.1-PES` and
`TensorNet-MatPES-PBE-v2025.1-PES` were regenerated for all 89 elements with the 2025.2 weights
that those names now load (the PBE O entry is the MP single point, see Constraints). Four O entries whose relaxation collapses the O2
crystal now hold the single point on the MP structure: MACE-MP-medium, and MACE-MH-0 omat_pbe,
matpes_r2scan and oc20_usemppbe (see Constraints). Two entries that the library protocol did not
reproduce were replaced by its converged, physical results: MACE-MATPES-PBE-0 O
(-5.575 → -4.905 eV/atom) and MACE-MP-small Cl (-2.146 → -1.838 eV/atom).

## Examples
- [Li, Fe, Cu, O, Si references vs Materials Project](examples/li_fe_cu_o_si_vs_mp/README.md): MPtrj and MatPES-r2SCAN library energies compared with MP's GGA and r2SCAN energies, with a CPU reproducibility check and Li2O / Fe2O3 formation energies. It documents the corrected MACE-MP-medium O and regenerated TensorNet-MatPES-r2SCAN entries.

## Constraints
- **Materials Project**: Structures must be queried from Materials Project to ensure they represent the true ground-state phases.
- **Naming**: Library files must follow the `<checkpoint_name>_energies.json` format.
- **Units**: Energies are stored as **eV/atom** (total potential energy of the relaxed structure divided by the number of atoms).
- **Relaxation (library protocol)**: No generation script ships with the library. Each
  value is `relax_structure` on `resources/structures/<El>.cif` with `relax_cell=True`,
  `fmax=0.02` eV/Å, at most 500 `FIRE` steps (the MCP tool defaults), and the stored
  value is the final energy divided by the number of atoms. A positions-only relaxation
  leaves the reference above the potential's own minimum and biases every formation
  energy that uses it.
- **Molecular-crystal elements are sensitive**: for O, N, F, Cl, H the MP ground state
  is a van der Waals-bound molecular crystal, so the relaxed cell can differ a lot from
  the DFT cell. Some potentials have no molecular minimum for O2 (mp-12957): the
  relaxation contracts the O=O bond and pulls molecules to an intermolecular O–O
  contact below 2.0 Å (MP: 2.145 Å), 0.15–0.86 eV/atom below the single point. When
  this happens the stored O value is the **single point on the MP structure** instead.
  This applies to MACE-MP-medium and MACE-MH-0 (omat_pbe, matpes_r2scan, oc20_usemppbe).
  The same rule gives the O entry of `TensorNet-MatPES-PBE-v2025.1-PES` (-5.117 eV/atom fully
  relaxed vs -4.964 single point). More than one MP entry can also tie at `energy_above_hull = 0` for these
  elements (O2: mp-12957 and mp-1524462), so pin the `material_id` rather than relying
  on a formula lookup returning a stable order.
- **Checkpoint names vs weights**: matgl 4.x loads the `TensorNet-MatPES-*-v2025.1-PES`
  and `M3GNet-MatPES-*-v2025.1-PES` names as the 2025.2 weights. Both TensorNet files were
  regenerated with those weights (2026-10). The M3GNet-MatPES files
  still hold the old weights' energies (e.g. Si -0.46 and -0.63 eV/atom off), and
  `M3GNet-MP-2021.2.8-PES` now loads M3GNet-PES-MatPES-PBE-2025.2 weights, so check
  that a library file matches the loaded model before use.
---

**Author:** Bowen Deng
**Contact:** [GitHub @learningmatter-mit](https://github.com/learningmatter-mit)
