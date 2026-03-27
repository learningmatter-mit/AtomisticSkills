# LAMMPS MLIP Backend Matrix Check

## Goal
Verify that each MLIP stack has its own working LAMMPS binary and matching runtime environment.

## Steps

1. Build MACE-linked binary:
```bash
# Env: base-agent
KOKKOS_ARCH_FLAG=Kokkos_ARCH_AMPERE86 \
bash conda-envs/mace-agent/install_lammps.sh
```

2. Build MatGL-linked binary:
```bash
# Env: base-agent
KOKKOS_ARCH_FLAG=Kokkos_ARCH_AMPERE86 \
bash conda-envs/matgl-agent/install_lammps.sh
```

3. Build FairChem-linked binary:
```bash
# Env: base-agent
KOKKOS_ARCH_FLAG=Kokkos_ARCH_AMPERE86 \
bash conda-envs/fairchem-agent/install_lammps.sh
```

4. Verify each binary with its matching environment:
```bash
# Env: mace-agent
conda activate mace-agent
./lammps/mace-agent/lmp -h

# Env: matgl-agent
conda activate matgl-agent
./lammps/matgl-agent/lmp -h

# Env: fairchem-agent
conda activate fairchem-agent
./lammps/fairchem-agent/lmp -h
```

## Expected Output
- All three binaries exist and start without Python embedding errors.
- Package summaries include Python and Kokkos support.
- No backend is run with a non-matching conda environment.
