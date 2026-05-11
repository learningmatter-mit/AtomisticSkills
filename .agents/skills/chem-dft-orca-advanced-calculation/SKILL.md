---
name: chem-dft-orca-advanced-calculation
description: Write and run custom ORCA input files for advanced electronic structure methods or settings not available through the SCINE wrapper, including multi-reference methods, excited states, relativistic effects, advanced SCF, NMR/EPR, and more.
category: [chemistry]
---

# Advanced ORCA Calculation

## Goal

Enable advanced ORCA quantum chemistry calculations by constructing a custom ORCA input file from scratch. This skill covers methods and features not available through the SCINE wrapper, including multi-reference methods, excited states, relativistic effects, advanced SCF settings, NMR/EPR properties, and more.

> [!IMPORTANT]
> For **standard DFT single-point** calculations (energy, gradients, Hessian), use the [singlepoint skill](../chem-dft-orca-singlepoint/SKILL.md) instead. For **geometry optimization**, use the [optimization skill](../chem-dft-orca-optimization/SKILL.md). This skill is for cases where those wrappers do not expose the needed method or settings.

## 1. Prerequisites

- **Conda environment:** `orca-agent` with `ase` installed (SCINE not required for this skill)
- **ORCA binary:** The environment variable `ORCA_BINARY_PATH` must point to the ORCA executable
  ```bash
  export ORCA_BINARY_PATH=/path/to/orca
  ```
- **ORCA documentation:** Consult the [ORCA 6.1 tutorials](https://www.faccts.de/docs/orca/6.1/tutorials/index.html) for method-specific input syntax, keyword blocks, and recommended settings

## 2. Workflow

### Step 1: Understand the user's request

Identify the target method, property, and system. Determine which ORCA keywords and blocks are needed. If unsure, consult the tutorials linked above for the specific method.

### Step 2: Write the ORCA input file

Create a `.inp` file following ORCA input syntax. Every input file should include:

**Mandatory elements:**
- A keyword line starting with `!` specifying the method, basis set, and job type
- A `*xyzfile` entry referencesing an external .xyz file

**Strongly recommended elements:**
- `%pal nprocs N end`: parallelization (always set this to avoid single-core runs)
- `%maxcore M`: memory per core in MB (e.g. 4000 for 4 GB per core)

**Example — TD-DFT excited states:**
```
! B3LYP def2-TZVP TightSCF
%pal nprocs 4 end
%maxcore 4000

%tddft
  NRoots 10
  MaxDim 5
end

* xyzfile 0 1 molecule.xyz
```

**Example: DLPNO-CCSD(T) single point:**
```
! DLPNO-CCSD(T) def2-TZVPP def2-TZVPP/C TightSCF
%pal nprocs 8 end
%maxcore 4000

* xyzfile 0 1 molecule.xyz
```

**Example: Geometry optimization with frequency calculation:**
```
! B3LYP def2-TZVP D3BJ Opt Freq TightSCF
%pal nprocs 4 end
%maxcore 4000

* xyzfile 0 1 molecule.xyz
```

**Example: CASSCF multi-reference:**
```
! CASSCF def2-TZVP
%pal nprocs 4 end
%maxcore 8000

%casscf
  nel 6
  norb 6
  nroots 3
end

* xyzfile 0 1 molecule.xyz
```

> [!TIP]
> When using an external `.xyz` file with `* xyzfile charge mult filename.xyz`, the `.xyz` file must be placed in the same directory where ORCA runs (the `--output_dir`).

### Step 3: Run the calculation

```bash
# Env: orca-agent
python .agent/skills/chem-dft-orca-advanced-calculation/scripts/run_orca_input.py \
    --input_file calculation.inp \
    --output_dir research/my_project/advanced_calc
```

The script will:
1. Validate basic input structure and warn about missing `%pal`/`%maxcore`
2. Copy the input file to the output directory
3. Execute ORCA and capture all output
4. Parse the final electronic energy from the output
5. Save a `calculation_results.json` summary

### Step 4: Parse results

For standard energies, the runner script already extracts the final energy. For other properties, use the dedicated parser:

```bash
# Env: orca-agent
python .agent/skills/chem-dft-orca-advanced-calculation/scripts/parse_orca_output.py \
    --output_file research/my_project/advanced_calc/calculation.out \
    --property energy orbitals
```

Available `--property` options in the parser:
- `energy`: Final energy, nuclear repulsion, dispersion correction
- `orbitals`: Orbital energies, HOMO/LUMO, gap
- `frequencies`: Vibrational frequencies, imaginary modes, IR intensities
- `thermochemistry`: ZPE, enthalpy, Gibbs energy, entropy
- `all`: Parse everything available

### Step 5: Manual output inspection

For properties not covered by the built-in parser (excited-state energies, NMR shifts, spin populations, natural orbitals, etc.), read the ORCA `calculation.property.txt` file directly.

## 3. Common Use Cases

| Method                     | Key ORCA Keywords                           | Notes                                                                                                                                                                                                        |
|----------------------------|---------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Multi-step SCF convergence | `! GuessMode=CMatrix` | Some SCFs are difficult to converge, solving it multiple steps, converging first on a small basis set and loose criterion and launching it again with the desired parameters |
| TD-DFT excited states      | `! B3LYP def2-TZVP`, `%tddft NRoots N end`  | Use TDA for faster approximation                                                                                                                                                                             |
| CASSCF/NEVPT2              | `! CASSCF def2-TZVP`, `%casscf nel N norb M end` | Active space selection is critical                                                                                                                                                                           |
| DFT + NMR                  | `! B3LYP def2-TZVP NMR`                     | Shielding tensors in output                                                                                                                                                                                  |
| DFT + EPR                  | `! B3LYP def2-TZVP EPR/ORP`                 | g-tensor and hyperfine couplings                                                                                                                                                                             |
| Relativistic (ZORA)        | `! B3LYP ZORA def2-TZVP SARC/J`             | For heavy elements; use SARC basis sets                                                                                                                                                                      |
| Scan/Relaxed scan          | `! B3LYP def2-SVP Opt`, `%geom Scan ... end` | Potential energy surface scans                                                                                                                                                                               |

## 4. Output Files

- `calculation_results.json`: Summary with energy, SCF convergence, return code, and any input warnings
- `<input_stem>.property.txt`: Structured ORCA output file of all properties
- `<input_stem>.out`: Full ORCA output file, only suitable for debugging errors
- Various ORCA-generated files (`.gbw`, `.densities`, `.engrad`, etc.) in the output directory
- `parsed_results.json` (if parser was run): Structured extraction of requested properties

## 5. Constraints

- **Input correctness:** The agent is responsible for writing a valid ORCA input file. The runner performs basic validation but cannot catch all syntax errors, ORCA itself will report those in the output.
- **SCF convergence:** Always check that the SCF converged. If it did not, try `SlowConv`, `VerySlowConv`, or adjust `%scf MaxIter` and damping settings.
- **Memory:** ORCA can be memory-intensive for correlated methods. Set `%maxcore` appropriately (rule of thumb: total available RAM / nprocs, leaving some for the OS).
- **Disk:** Post-HF methods (CCSD(T), CASSCF) can generate large temporary files. Ensure sufficient disk space.
- **ORCA binary:** `ORCA_BINARY_PATH` must be set and point to a working ORCA installation.
- **Environment:** All commands require the `orca-agent` conda environment.
- **Parallelization:** ORCA uses OpenMPI internally. Do not run multiple ORCA instances on overlapping core sets.
- **Output parsing:** The built-in parser covers common output patterns. For uncommon methods or output formats, the raw `.out` file must be inspected directly.

## References

- Neese, F., "Software update: The ORCA program system—Version 5.0", *WIREs Comput. Mol. Sci.*, 2022. [DOI](https://doi.org/10.1002/wcms.1606)
- ORCA 6.1 Tutorials: [https://www.faccts.de/docs/orca/6.1/tutorials/](https://www.faccts.de/docs/orca/6.1/tutorials/index.html)

---

**Author:** Miguel Steiner
**Contact:** [GitHub @steinmig](https://github.com/steinmig)
