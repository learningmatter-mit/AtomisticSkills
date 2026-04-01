---
name: chem-irc-verification
description: Verify non-periodic molecular TS connectivity with forward/reverse IRC using endpoint connectivity and RMSD checks.
category: [chemistry]
---

# IRC Verification with Sella

Verify that a saddle-point-optimized TS connects the intended reactant and product.

## Scope

- Domain: molecular chemistry only (non-periodic systems).
- Trigger: user has optimized reactant/product + optimized TS and needs IRC endpoint verification.
- Exclusions: periodic systems and barrier-only workflows.

## Tool

### `verify_irc_sella.py`

Runs forward/reverse IRC from the TS, optionally relaxes endpoints, then checks mapping quality.

### Use with MACE

```bash
# Env: mace-agent
python .agents/skills/chem-irc-verification/scripts/verify_irc_sella.py \
  --reactant reactant_optimized.xyz \
  --product product_optimized.xyz \
  --ts ts_optimized.xyz \
  --model_type mace \
  --model_name MACE-OFF23-small \
  --fmax 0.02 \
  --steps 1000 \
  --rmsd_threshold 0.20 \
  --relax_endpoints true \
  --endpoint_relax_fmax 0.02 \
  --output_dir results/irc
```

### Use with FAIRChem (UMA)

```bash
# Env: fairchem-agent
python .agents/skills/chem-irc-verification/scripts/verify_irc_sella.py \
  --reactant reactant_optimized.xyz \
  --product product_optimized.xyz \
  --ts ts_optimized.xyz \
  --model_type fairchem \
  --model_name uma-s-1p1 \
  --task_name omol \
  --fmax 0.02 \
  --steps 1000 \
  --rmsd_threshold 0.20 \
  --relax_endpoints true \
  --endpoint_relax_fmax 0.02 \
  --output_dir results/irc
```

## Arguments

- `--reactant`: required optimized reactant geometry.
- `--product`: required optimized product geometry.
- `--ts`: required saddle-point-optimized TS geometry.
- `--model_type`: required backend (`mace` or `fairchem`).
- `--model_name`: optional model identifier/checkpoint.
- `--task_name`: optional model head/task (for UMA molecular runs use `omol`).
- `--device`: `auto|cpu|cuda` (default `auto`).
- `--fmax`: IRC convergence threshold in eV/A (default `0.02`).
- `--steps`: maximum IRC steps per direction (default `1000`).
- `--rmsd_threshold`: endpoint RMSD threshold in A (default `0.20`).
- `--relax_endpoints`: `true|false`, relax IRC endpoints before matching (default `true`).
- `--endpoint_relax_fmax`: force threshold for optional endpoint relaxation (default `0.02`).
- `--output_dir`: required output directory.

## Outputs

- `irc_forward.traj`, `irc_reverse.traj`: IRC trajectories.
- `irc_forward.log`, `irc_reverse.log`: IRC logs.
- `irc_forward_endpoint.xyz`, `irc_reverse_endpoint.xyz`: terminal endpoint geometries.
- `irc_verification_results.json`: endpoint assignment and pass/fail summary.

`irc_verification_results.json` fields include:
- selected endpoint assignment (`endpoint_mapping`)
- per-pair metrics (`connectivity_match`, `rmsd_angstrom`, thresholds)
- all candidate assignments with total RMSD
- final decision (`verification_passed`)

## Verification Criterion

Verification passes only if both mapped endpoint-target pairs satisfy:
- same formula and atom order
- connectivity graph match
- Kabsch-aligned RMSD <= `rmsd_threshold`

Default criterion: both pairs must pass with `rmsd_threshold = 0.20 A`.

## Model Guidance

- Recommended for molecules:
  - `MACE-OFF23-small` / `MACE-OFF23-medium`
  - `uma-s-1p1` with `--task_name omol`
- Use the same backend/model/head as TS optimization to avoid model inconsistency.

## Prerequisites And Constraints

- Activate `mace-agent` or `fairchem-agent` depending on backend.
- Script enforces `pbc=False` for all inputs.
- Reactant/product/TS must have identical composition and consistent atom ordering.

## Examples

See `examples/` directory for sample inputs and outputs.
---

**Author:** Juno Nam
**Contact:** [GitHub @recisic](https://github.com/recisic)
