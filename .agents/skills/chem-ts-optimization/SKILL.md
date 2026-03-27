---
name: chem-ts-optimization
description: Optimize non-periodic molecular TS guesses and verify first-order saddle point from vibrational modes.
category: [chemistry]
---

# TS Optimization with Sella

Optimize a transition-state guess and check whether it is a first-order saddle point.

## Scope

- Domain: molecular chemistry only (non-periodic systems).
- Trigger: user has a TS guess and needs TS optimization plus frequency validation.
- Exclusions: periodic diffusion/path workflows (use `chem-neb-barrier` instead).

## Tool

### `optimize_ts_sella.py`

Runs Sella TS optimization followed by finite-difference vibrations.

### Use with MACE

```bash
# Env: mace-agent
python .agents/skills/chem-ts-optimization/scripts/optimize_ts_sella.py \
  --ts_guess ts_guess.xyz \
  --model_type mace \
  --model_name MACE-OFF23-small \
  --fmax 0.02 \
  --steps 500 \
  --imag_cutoff_cm1 -50.0 \
  --output_dir results/ts_opt
```

### Use with FAIRChem (UMA)

```bash
# Env: fairchem-agent
python .agents/skills/chem-ts-optimization/scripts/optimize_ts_sella.py \
  --ts_guess ts_guess.xyz \
  --model_type fairchem \
  --model_name uma-s-1p1 \
  --task_name omol \
  --fmax 0.02 \
  --steps 500 \
  --imag_cutoff_cm1 -50.0 \
  --output_dir results/ts_opt
```

## Arguments

- `--ts_guess`: required TS guess geometry (XYZ supported by ASE I/O).
- `--model_type`: required backend (`mace` or `fairchem`).
- `--model_name`: optional model identifier/checkpoint.
- `--task_name`: optional model head/task (for UMA molecular runs use `omol`).
- `--device`: `auto|cpu|cuda` (default `auto`).
- `--fmax`: Sella convergence threshold in eV/A (default `0.02`).
- `--steps`: maximum TS optimization steps (default `500`).
- `--vib_delta`: finite-difference displacement in A (default `0.01`).
- `--vib_nfree`: finite-difference stencil size (`2` or `4`, default `2`).
- `--imag_cutoff_cm1`: imaginary mode cutoff in cm^-1 (default `-50.0`).
- `--keep_vib_cache`: optional flag to keep vibration cache files in `output_dir/vib`.
- `--output_dir`: required output directory.

## Outputs

- `ts_optimized.xyz`: optimized TS geometry.
- `ts_opt.traj`: TS optimization trajectory.
- `ts_opt.log`: optimizer log.
- `ts_optimization_results.json`: run summary and pass/fail decision.
- `vib/` cache files only when `--keep_vib_cache` is set.

`ts_optimization_results.json` fields include:
- run/model metadata
- convergence (`sella_converged`, `optimization_steps`, `max_force_eV_per_A`)
- vibrational data (`all_frequencies_cm1`, `imaginary_modes`)
- classification (`n_imag_below_cutoff`, `is_first_order_saddle`)

## TS Pass Criterion

A structure is accepted as first-order saddle only if:
- exactly one frequency satisfies `frequency < imag_cutoff_cm1`

Default criterion: exactly one mode below `-50 cm^-1`.

## Model Guidance

- Recommended for molecules:
  - `MACE-OFF23-small` / `MACE-OFF23-medium`
  - `uma-s-1p1` with `--task_name omol`
- Use the same backend/model/head across reactant/product/TS optimization and TS validation.

## Prerequisites And Constraints

- Activate `mace-agent` or `fairchem-agent` depending on backend.
- Script enforces `pbc=False` (non-periodic only).
- TS guess quality matters; poor guesses can converge to minima or higher-order saddles.

## Examples

See `examples/` directory for sample inputs and outputs.
---

**Author:** Juno Nam
**Contact:** [GitHub @recisic](https://github.com/recisic)
