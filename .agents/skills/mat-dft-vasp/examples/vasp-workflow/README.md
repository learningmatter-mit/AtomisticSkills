# VASP Workflow Example

This directory contains a standalone example demonstrating how to leverage the `mat-dft-vasp` skill to process structural inputs into ready-to-calculate VASP files, and subsequently parse the results into standardized JSON format.

## Example Scenario

We start with a basic crystalline unit cell of Silicon ([Si.cif](Si.cif)) and want to prepare the necessary input files (`INCAR`, `POSCAR`, `KPOINTS`, and `POTCAR`) for a local VASP relaxation calculation, using standard presets.

### 1. Preparing the Calculation

Using the `base-agent` environment, we convert the `Si` structure into a working VASP directory utilizing the `matpes-pbe` preset (a robust preset built for Machine Learning Interatomic Potential training data curation).

```bash
# Env: base-agent
conda activate base-agent

# Run the preparation script
python ../../../scripts/prepare_vasp_inputs.py \
    Si.cif \
    vasp_inputs/ \
    --preset_type matpes-pbe \
    --calculation_type relaxation
```

Output files stored in `vasp_inputs/` include:
- **POSCAR**: Auto-scaled cartesian coordinates of the structure.
- **INCAR**: Standardized calculation settings (e.g. `ALGO = Fast`, `ISIF = 3`).
- **KPOINTS**: Gamma-centered Monkhorst-Pack mesh generated via density heuristics.
- **POTCAR**: Automatically assembled pseudopotentials from the local `PMG_VASP_PSP_DIR`.

### 2. Executing VASP

(This step must be performed using the local VASP binary, e.g.:)
```bash
cd vasp_inputs/
mpirun -np 16 vasp_std
cd ..
```

### 3. Parsing the Geometry Output

After the calculation completes, the simulation directory will contain standard output files such as `vasprun.xml` and `OUTCAR`. The parsing script will traverse the directory and extract all critical physics metrics (Energy, Forces, Stress) into a serialized JSON representation.

```bash
# Env: base-agent
conda activate base-agent

# Parse the directory locally
python ../../../scripts/parse_vasp_results.py \
    vasp_inputs/ \
    --save_to_file parsed_results.json
```

Output:
A unified `parsed_results.json` containing the extracted structure array alongside its correlated total internal energy (eV), per-atom forces ($eV/\AA$), and lattice stresses ($eV/\AA^3$).
