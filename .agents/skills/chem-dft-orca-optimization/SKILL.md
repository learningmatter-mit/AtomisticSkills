---
name: chem-dft-orca-optimization
description: Run DFT geometry optimization (minimization or TS search) on a molecular structure using ORCA via SCINE/ReaDuct wrapper.
category: [chemistry]
---

# DFT Geometry Optimization with ORCA

## Goal

Optimize the geometry of a molecular structure at the DFT level using the ORCA quantum chemistry program. Supports two modes: **minimization** (finding the nearest local minimum) and **transition state (TS) optimization** (single-ended saddle point search). The calculation uses the SCINE/ReaDuct wrapper for robust optimizer management.

> [!IMPORTANT]
> This skill provides **single-ended TS optimization** only. For reaction pathway methods (NEB, IRC), consider using the MLIP-based [NEB skill](../chem-neb-barrier/SKILL.md) or [IRC skill](../chem-irc-verification/SKILL.md) with MLIP pre-screening, then refine with DFT. For advanced ORCA features, use the [advanced ORCA skill](../chem-dft-orca-advanced-calculation/SKILL.md).

## Background

Geometry optimization iteratively adjusts nuclear positions to minimize (or, for TS search, to find a first-order saddle point of) the potential energy surface $E(\mathbf{R})$. The SCINE/ReaDuct optimizer handles step control, coordinate transformations, and convergence criteria internally.

- **Minimization** seeks a stationary point where $\nabla E = 0$ and the Hessian has all positive eigenvalues.
- **TS optimization** seeks a first-order saddle point where $\nabla E = 0$ and the Hessian has exactly one negative eigenvalue.

## 1. Prerequisites

- **Conda environment:** `orca-agent` with `scine_utilities`, `scine_readuct`, and `ase` installed
- **ORCA binary:** The environment variable `ORCA_BINARY_PATH` must point to the ORCA executable
  ```bash
  export ORCA_BINARY_PATH=/path/to/orca
  ```
- **Input structure:** A molecular structure file readable by ASE (`.xyz`, `.cif`, `.mol`, etc.)
- For **TS optimization:** Provide a reasonable TS guess geometry. Poor initial guesses will likely fail to converge to the correct saddle point.

## 2. Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--structure` | (required) | Path to input structure file |
| `--opt_type` | `min` | `min` for minimization, `ts` for transition state search |
| `--charge` | `0` | Molecular charge |
| `--spin_multiplicity` | `1` | Spin multiplicity (2S+1) |
| `--functional` | `PBE` | DFT functional (e.g. `PBE`, `B3LYP`, `wB97X-V`) |
| `--basis_set` | `def2-SVP` | Basis set (e.g. `def2-SVP`, `def2-TZVP`) |
| `--dispersion` | None | Dispersion correction (e.g. `D3BJ`, `D4`) |
| `--solvation` | None | Implicit solvation model: `CPCM` or `SMD` |
| `--solvent` | None | Solvent name; required if `--solvation` is set |
| `--special_option` | `NOSOSCF` | ORCA special option passed to SCINE calculator. Set to empty string to disable. |
| `--nprocs` | `1` | Number of CPU cores for ORCA |
| `--convergence_max_iterations` | `200` | Maximum optimization steps |
| `--calculate_final_hessian` | off | Compute Hessian at optimized geometry (for TS verification) |
| `--calculator_settings` | None | Extra SCINE calculator settings as a JSON string (see below) |
| `--optimizer_settings` | None | Extra ReaDuct optimizer kwargs as a JSON string (see below) |
| `--output_dir` | auto | Output directory |

## 3. Running an Optimization

### Geometry minimization

```bash
# Env: orca-agent
python .agent/skills/chem-dft-orca-optimization/scripts/run_optimization.py \
    --structure molecule.xyz \
    --functional B3LYP \
    --basis_set def2-TZVP \
    --dispersion D3BJ \
    --nprocs 4 \
    --output_dir research/my_project/optimization
```

### Transition state optimization

```bash
# Env: orca-agent
python .agent/skills/chem-dft-orca-optimization/scripts/run_optimization.py \
    --structure ts_guess.xyz \
    --opt_type ts \
    --functional B3LYP \
    --basis_set def2-TZVP \
    --dispersion D3BJ \
    --calculate_final_hessian \
    --nprocs 4 \
    --output_dir research/my_project/ts_optimization
```

### With extra settings (calculator + optimizer)

For settings not exposed as dedicated flags, pass JSON strings. `--calculator_settings` applies to the SCINE/ORCA calculator, `--optimizer_settings` applies to the ReaDuct optimization task. SCINE is strict about types, so JSON ensures values are passed with the correct type (int, float, string).

```bash
# Env: orca-agent
python .agent/skills/chem-dft-orca-optimization/scripts/run_optimization.py \
    --structure molecule.xyz \
    --functional B3LYP \
    --basis_set def2-TZVP \
    --calculator_settings '{"max_scf_iterations": 128}' \
    --optimizer_settings '{"convergence_delta_value": 1e-6}' \
    --output_dir research/my_project/opt_custom
```

### With implicit solvation

```bash
# Env: orca-agent
python .agent/skills/chem-dft-orca-optimization/scripts/run_optimization.py \
    --structure molecule.xyz \
    --functional PBE0 \
    --basis_set def2-TZVP \
    --solvation SMD \
    --solvent water \
    --nprocs 4 \
    --output_dir research/my_project/opt_solvated
```

## 4. Output Files

- `optimization_results.json`: Structured results containing:
  - `converged`: Boolean indicating whether the optimization converged
  - `final_energy_hartree`, `final_energy_eV`: Final electronic energy
  - `final_max_force_eV_per_Ang`, `final_rms_force_eV_per_Ang`: Residual force information
  - `opt_type`: Whether this was a minimization or TS search
  - If `--calculate_final_hessian` was used: `hessian_eV_per_Ang2`, `hessian_wave_numbers_cm-1`, and `n_imaginary_modes`
  - All input parameters for reproducibility
- `initial_structure.xyz`: Copy of the input structure
- `optimized_structure.xyz`: The optimized geometry

## 5. Interpreting Results

### Minimization
- Check `converged: true` in the results JSON.
- Residual forces should be small (max force < 0.01 eV/A for typical convergence).
- If convergence fails, try increasing `--convergence_max_iterations` or improving the initial geometry.

### TS Optimization
- Convergence alone does not guarantee a valid TS. After convergence, verify the Hessian has exactly one imaginary frequency:
  - **Recommended:** Use `--calculate_final_hessian` to compute the Hessian directly after optimization. The output will include `n_imaginary_modes` — expect exactly 1 for a valid TS.
  - Alternatively, run a separate single-point Hessian with the [singlepoint skill](../chem-dft-orca-singlepoint/SKILL.md) using `--compute_hessian`.
- Inspect the imaginary mode to confirm it corresponds to the expected reaction coordinate.
- If the optimizer converges to a minimum instead of a saddle point, the initial guess was likely too far from the true TS.

## 6. Constraints

- **Non-periodic systems only:** ORCA does not handle periodic boundary conditions.
- **Single-ended TS:** Only single-ended TS optimization is available. For double-ended methods (NEB), pre-screen with MLIPs.
- **TS guess quality:** The TS optimizer requires a reasonable initial guess. Generate one using constrained scans, interpolation, or MLIP-based TS search methods.
- **ORCA binary:** `ORCA_BINARY_PATH` must be set and point to a working ORCA installation.
- **Environment:** All commands require the `orca-agent` conda environment.
- **Solvation:** When using `--solvation`, you must also provide `--solvent`.

## References

- Neese, F., "Software update: The ORCA program system—Version 5.0", *WIREs Comput. Mol. Sci.*, 2022. [DOI](https://doi.org/10.1002/wcms.1606)
- Unsleber, J.P. et al., "SCINE—Software for Chemical Interaction Networks", *J. Chem. Phys.*, 2024. [DOI](https://doi.org/10.1063/5.0206974)

---

**Author:** Miguel Steiner
**Contact:** [GitHub @steinmig](https://github.com/steinmig)
