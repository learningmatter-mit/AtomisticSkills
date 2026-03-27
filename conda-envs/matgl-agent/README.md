# MatGL Agent Environment

Minimal setup for MatGL/CHGNet simulations.

## 1) New Machine Setup

```bash
bash conda-envs/matgl-agent/install.sh
```

This creates `matgl-agent` from `core_env.yaml`.

## 2) Run Simulations (Recommended)

For the current Cu phase-transition example, no LAMMPS compile is needed:

```bash
conda activate matgl-agent
bash .agents/skills/mat-lammps-md/examples/matgl/run_matgl_cu_phase_transition.sh
```

## 3) Compile LAMMPS (Optional)

If you need a dedicated MatGL-linked LAMMPS binary:

```bash
KOKKOS_ARCH_FLAG=Kokkos_ARCH_AMPERE86 \
bash conda-envs/matgl-agent/install_lammps.sh
```

Optional reproducible ref:

```bash
KOKKOS_ARCH_FLAG=Kokkos_ARCH_AMPERE86 \
LAMMPS_REF="stable_2Aug2023_update2" \
bash conda-envs/matgl-agent/install_lammps.sh
```

Binary path:
- `lammps/matgl-agent/lmp`
