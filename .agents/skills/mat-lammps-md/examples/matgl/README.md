# MatGL Example: Cu Phase-Transition Scan

This example runs a simple heat-and-hold workflow for fcc Copper (Cu) with
ASE + CHGNet. The script:

1. creates an fcc Cu supercell data file;
2. loads a MatGL potential in ASE;
3. runs heat-and-hold MD;
4. stores logs/trajectory for post-analysis of a transition signature
   (e.g., abrupt energy/volume slope change).

```bash
# Env: matgl-agent
bash .agents/skills/mat-lammps-md/examples/matgl/run_matgl_cu_phase_transition.sh
```

## Output
- `./out-matgl-cu-phase-transition/cu_fcc.data`
- `./out-matgl-cu-phase-transition/log.matgl`
- `./out-matgl-cu-phase-transition/cu_heat.lammpstrj`
- `./out-matgl-cu-phase-transition/run_summary.json`

Optional model override:
```bash
CHGNET_MODEL=0.3.0 bash .agents/skills/mat-lammps-md/examples/matgl/run_matgl_cu_phase_transition.sh
```
