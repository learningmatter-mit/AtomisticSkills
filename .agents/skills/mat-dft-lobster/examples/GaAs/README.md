# GaAs LOBSTER Workflow Example

This directory contains the example configuration and outputs for the `mat-dft-lobster` skill, demonstrating how to generate a computational Directed Acyclic Graph (DAG) for projecting VASP plane waves onto local basis sets using LOBSTER for standard zincblende GaAs.

## Validation

LOBSTER provides explicit metrics on the stability and accuracy of the projection via the charge spilling metrics. For a standard III-V semiconductor like GaAs using PAW pseudopotentials with a suitably high energy cutoff (`ENCUT`), LOBSTER typically recovers bonding characteristics showing the strong covalent interaction between Ga `$4s$/$4p$` and As `$4s$/$4p$`.

In typical reliable LOBSTER runs for semiconductors:
1. **Absolute charge spilling** should ideally be below 1-2%.
2. **COHP Analysis**: The integrated COHP (ICOHP) for the nearest-neighbor Ga-As bond indicates the total covalent bond strength.

While physical execution relies on HPC allocation, generating the DAG with the strict VASP requirements ($k$-points and `ISYM=-1` symmetry restrictions) ensures that manual errors in interfacing these two major codes are minimized.
