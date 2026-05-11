# Silicon Frenkel-Ladd Example

This example demonstrates a reduced-cost Frenkel-Ladd run on crystalline silicon using MACE.

## Purpose

This example is intended as a portability and smoke-test example for the skill script. It uses a simple silicon structure and reduced trajectory lengths so the command is easier to try.

It is **not** a production-quality free-energy workflow. For production calculations, start from a structure that has already been equilibrated at the target state point and use the heavier default settings from the skill.

## Structure

[Si.cif](Si.cif) contains a small diamond-cubic silicon cell.

## Run

```bash
# Env: mace-agent
python .agents/skills/mat-solid-free-energy/scripts/run_frenkel_ladd.py \
    --structure .agents/skills/mat-solid-free-energy/examples/Si_MACE/Si.cif \
    --name Si_demo \
    --calculator mace \
    --model-name MACE-OMAT-0-small \
    --temperature 300 \
    --msd-equilibration-steps 50 \
    --msd-production-steps 200 \
    --equilibration-steps 100 \
    --switching-steps 500 \
    --record-interval 5 \
    --output-dir frenkel_ladd_output
```

## Expected Outputs

The script writes:

- `frenkel_ladd_output/frenkel_ladd_results.json`
- `frenkel_ladd_output/frenkel_ladd_traces.npz`
- `frenkel_ladd_output/input_structure.cif`
- `frenkel_ladd_output/final_structure.cif`

## Notes

- The reduced step counts are only for demonstration.
- For production calculations, use the full default settings or longer trajectories.
- Treat large `abs(dissipated_energy) / num_atoms` values as a warning sign for poor reversibility.
