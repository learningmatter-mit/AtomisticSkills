# MACE Example: Thermal Quench of Na2Si3O7 Glass

This example runs a melt-quench protocol for sodium silicate (`Na2Si3O7`) with
a MACE-bound LAMMPS binary:

1. auto-generates a Na2Si3O7 seed structure (or uses `INPUT_STRUCTURE`);
2. auto-prepares a LAMMPS MACE model (`mace_auto-lammps.pt`) unless `MODEL_FILE` is given;
3. runs melt/quench/hold.

```bash
# Env: mace-agent
bash .agents/skills/mat-lammps-md/examples/mace/run_mace_na2si3o7_quench.sh
```

Optional overrides:
```bash
# Env: mace-agent
INPUT_STRUCTURE=./na2si3o7_initial.cif \
MACE_MODEL_NAME=MACE-MP-medium \
MACE_HEAD=omat_pbe \
bash .agents/skills/mat-lammps-md/examples/mace/run_mace_na2si3o7_quench.sh
```

## Output
- `./out-mace-na2si3o7-quench/na2si3o7_initial.data`
- `./out-mace-na2si3o7-quench/in.na2si3o7_quench_mace`
- `./out-mace-na2si3o7-quench/log.lammps`
- `./out-mace-na2si3o7-quench/na2si3o7_quench.lammpstrj`
- `./out-mace-na2si3o7-quench/na2si3o7_glass_final.data`

## Notes
- The MACE quench input follows the same pattern; if needed, edit only the
  "MACE model hookup" block in `in.na2si3o7_quench_mace`.
- For model choice and recommended checkpoints, see
  [ml-foundation-potentials](../../../ml-foundation-potentials/SKILL.md).
