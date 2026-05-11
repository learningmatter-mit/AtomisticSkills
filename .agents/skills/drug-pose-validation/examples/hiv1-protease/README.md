# HIV-1 Protease Pose Validation Example

## Goal
Demonstrate PoseBusters pose validation with both passing and failing poses, using a simple drug-like molecule (phenylacetic acid).

## Input Files
- `test_poses.sdf`: 3 identical valid poses of phenylacetic acid (all should pass)
- `mixed_poses.sdf`: 4 poses (3 valid + 1 with crushed geometry where all atoms are collapsed onto a line at 0.1 A spacing)

## Steps

### Ligand-only validation (all pass)

```bash
# Env: drugdisc-agent
python .agents/skills/drug-pose-validation/scripts/validate_poses.py \
  --poses .agents/skills/drug-pose-validation/examples/hiv1-protease/test_poses.sdf \
  --output_dir validation/
```

Expected: 3/3 pass.

### Mixed validation (one bad pose)

```bash
# Env: drugdisc-agent
python .agents/skills/drug-pose-validation/scripts/validate_poses.py \
  --poses .agents/skills/drug-pose-validation/examples/hiv1-protease/mixed_poses.sdf \
  --output_dir mixed_validation/
```

Expected: 3/4 pass. Pose 2 (`bad_pose_crushed`) fails on `bond_lengths`, `bond_angles`, `internal_steric_clash`, and `internal_energy`. The `valid_poses.sdf` output contains only the 3 good poses.

## Key Observations
- The script identifies pass/fail test columns from the PoseBusters config (`chosen_binary_test_output` per module), so only config-relevant plausibility checks determine validity.
- Full diagnostic info (including loading-status columns) is included in the JSON report under `diagnostics` for debugging.
- When `--receptor` is omitted, protein-ligand clash checks are skipped.
