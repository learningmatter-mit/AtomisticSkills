# MACE Agent Environment

Minimal setup for MACE simulations.

## 1) New Machine Setup

```bash
bash conda-envs/mace-agent/install.sh
```

Creates `mace-agent` from `core_env.yaml`.

## 2) Run MACE Example (One Command)

```bash
conda activate mace-agent
bash .agents/skills/mat-lammps-md/examples/mace/run_mace_na2si3o7_quench.sh
```

The script auto-generates:
- seed Na2Si3O7 structure
- LAMMPS-ready MACE model (`*-lammps.pt`)

## 3) Compile LAMMPS (Optional)

Build dedicated MACE LAMMPS binary:

```bash
bash conda-envs/mace-agent/install_lammps.sh
```

Optional overrides:

```bash
LAMMPS_REF="mace" \
LAMMPS_BUILD_JOBS=32 \
bash conda-envs/mace-agent/install_lammps.sh
```

Binary path:
- `lammps/mace-agent/lmp`
