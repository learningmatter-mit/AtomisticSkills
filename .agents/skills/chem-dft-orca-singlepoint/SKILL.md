---
name: chem-dft-orca-singlepoint
description: Run a DFT or Coupled Cluster single-point energy calculation (with optional gradients/Hessian) on a molecular structure with ORCA through SCINE wrapper.
category: [chemistry]
---

# DFT Single-Point Calculation with ORCA

## Goal

Compute the DFT electronic energy and optionally forces (gradients) and/or the Hessian for a given molecular structure with the ORCA quantum chemistry program.
The calculation relies on the SCINE wrapper for automated input generation, output parsing, and error handling, with curated defaults suitable for standard cases.

> [!IMPORTANT]
> This skill is for **standard DFT single-point calculations** on molecular (non-periodic) systems. For advanced methods, multi-reference calculations, or properties not exposed here, use the [advanced ORCA skill](../chem-dft-orca-advanced-calculation/SKILL.md). For geometry optimization, use the [ORCA optimization skill](../chem-dft-orca-optimization/SKILL.md).

## 1. Prerequisites

- **Conda environment:** `orca-agent` with `scine_utilities` and `ase` installed
- **ORCA binary:** The environment variable `ORCA_BINARY_PATH` must point to the ORCA executable
  ```bash
  export ORCA_BINARY_PATH=/path/to/orca
  ```
- **Input structure:** A molecular structure file readable by ASE (`.xyz`, `.cif`, `.mol`, etc.)

## 2. Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--structure` | (required) | Path to input structure file |
| `--charge` | `0` | Molecular charge |
| `--spin_multiplicity` | `1` | Spin multiplicity (2S+1) |
| `--functional` | `PBE` | DFT functional (e.g. `PBE`, `B3LYP`, `wB97X-V`, `PBE0`) |
| `--basis_set` | `def2-SVP` | Basis set (e.g. `def2-SVP`, `def2-TZVP`, `def2-TZVPP`) |
| `--dispersion` | None | Dispersion correction (e.g. `D3BJ`, `D4`) |
| `--solvation` | None | Implicit solvation model: `CPCM` or `SMD` |
| `--solvent` | None | Solvent name (e.g. `water`, `ethanol`, `dmso`); required if `--solvation` is set |
| `--special_option` | `NOSOSCF` | ORCA special option passed to SCINE calculator. Set to empty string to disable. |
| `--nprocs` | `1` | Number of CPU cores for ORCA |
| `--compute_gradients` | off | Flag to also compute forces |
| `--compute_hessian` | off | Flag to also compute the Hessian matrix |
| `--calculator_settings` | None | Extra SCINE calculator settings as a JSON string (see below) |
| `--output_dir` | auto | Output directory |

## 3. Running a Calculation

### Basic energy calculation

```bash
# Env: orca-agent
python .agent/skills/chem-dft-orca-singlepoint/scripts/run_singlepoint.py \
    --structure molecule.xyz \
    --output_dir research/my_project/singlepoint
```

### Energy + forces with a hybrid functional and dispersion

```bash
# Env: orca-agent
python .agent/skills/chem-dft-orca-singlepoint/scripts/run_singlepoint.py \
    --structure molecule.xyz \
    --functional B3LYP \
    --basis_set def2-TZVP \
    --dispersion D3BJ \
    --compute_gradients \
    --nprocs 4 \
    --output_dir research/my_project/singlepoint
```

### With implicit solvation

```bash
# Env: orca-agent
python .agent/skills/chem-dft-orca-singlepoint/scripts/run_singlepoint.py \
    --structure molecule.xyz \
    --functional PBE0 \
    --basis_set def2-TZVP \
    --solvation CPCM \
    --solvent water \
    --compute_gradients \
    --output_dir research/my_project/singlepoint_solvated
```

### With extra SCINE calculator settings

For settings not exposed as dedicated flags, pass a JSON string via `--calculator_settings`. SCINE is strict about types, so JSON ensures values are passed with the correct type (int, float, string).

```bash
# Env: orca-agent
python .agent/skills/chem-dft-orca-singlepoint/scripts/run_singlepoint.py \
    --structure molecule.xyz \
    --functional B3LYP \
    --basis_set def2-TZVP \
    --calculator_settings '{"max_scf_iterations": 128}' \
    --output_dir research/my_project/singlepoint_custom
```

> [!IMPORTANT]
> A popular functional choice is 'wB97M-V' which can only be used with the hack "--functional '' --dispersion '' --special_option wB97M-V"
> This hack will work for any functional choice that includes hyphens

### Hessian calculation

```bash
# Env: orca-agent
python .agent/skills/chem-dft-orca-singlepoint/scripts/run_singlepoint.py \
    --structure molecule.xyz \
    --functional B3LYP \
    --basis_set def2-TZVP \
    --dispersion D3BJ \
    --compute_gradients \
    --compute_hessian \
    --charge 0 \
    --spin_multiplicity 1 \
    --nprocs 8 \
    --output_dir research/my_project/singlepoint_full
```

### Beyond DFT calculation

ORCA also supports post-HF methods useful for reference calculations, such as local coupled cluster DLPNO-CCSD(T).
This is also available through this skill.

```bash
# Env: orca-agent
python .agent/skills/chem-dft-orca-singlepoint/scripts/run_singlepoint.py \
    --structure molecule.xyz \
    --functional DLPNO-CCSD(T) \
    --basis_set def2-TZVP \
    --charge 0 \
    --spin_multiplicity 1 \
    --nprocs 8 \
    --output_dir research/my_project/singlepoint_full
```

## 4. Useful standards to adhere to

- Transition state structures should be calculated with an unrestricted method (e.g. '--calculator_settings {"spin_mode": "unrestricted"}')
- For open-shell systems, different spin multiplicities should be calculated with separate single-point calculations

## 5. Output Files

- `singlepoint_results.json`: Structured results containing:
  - `energy_hartree`, `energy_eV`: Electronic energy in Hartree and eV
  - `forces_eV_per_Ang`: Forces array (if `--compute_gradients` was set)
  - `max_force_eV_per_Ang`, `rms_force_eV_per_Ang`: Force summary statistics
  - `hessian_eV_per_Ang2`: Hessian matrix (if `--compute_hessian` was set)
  - Input parameters (functional, basis set, charge, etc.) for reproducibility
- `input_structure.xyz`: Copy of the input structure

## 6. Constraints

- **Non-periodic systems only:** This skill is designed for molecules, clusters, and finite systems. ORCA does not handle periodic boundary conditions.
- **Standard methods:** For multi-reference methods (CASSCF, NEVPT2), excited-state calculations (TD-DFT, EOM-CCSD), or other advanced features, use the [advanced ORCA skill](../chem-dft-orca-advanced-calculation/SKILL.md).
- **ORCA binary:** `ORCA_BINARY_PATH` must be set and point to a working ORCA installation.
- **Environment:** All commands require the `orca-agent` conda environment.
- **Solvation:** When using `--solvation`, you must also provide `--solvent`. Available solvents depend on the chosen model (CPCM/SMD); common names like `water`, `ethanol`, `dmso`, `acetonitrile`, `thf` are supported.
- **Spin multiplicity:** Provide the spin multiplicity $2S+1$ (e.g. 1 for singlet, 2 for doublet, 3 for triplet), not the number of unpaired electrons.

## References

- Neese, F., "Software update: The ORCA program system—Version 5.0", *WIREs Comput. Mol. Sci.*, 2022. [DOI](https://doi.org/10.1002/wcms.1606)
- Weymuth, T. et al., "SCINE—Software for Chemical Interaction Networks", *J. Chem. Phys.*, 2024. [DOI](https://doi.org/10.1063/5.0206974)

---

**Author:** Miguel Steiner
**Contact:** [GitHub @steinmig](https://github.com/steinmig)
