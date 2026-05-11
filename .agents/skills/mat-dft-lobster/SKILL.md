---
name: mat-dft-lobster
description: Construct computational flows for VASP electronic structure projection via LOBSTER to calculate chemical bonding insights (COHP, atomic charges, DOS).
category: materials
---

# mat-dft-lobster

## Goal
To calculate advanced chemical bonding properties—like Crystal Orbital Hamilton Populations (COHP), atomic charges, projected DOS, and bonding integrands (ICOHP)—by projecting converged plane-wave Density Functional Theory (DFT) wavefunctions onto a localized, atomic-like basis set using the LOBSTER code.

## Background
Standard plane-wave DFT (e.g., VASP) distributes electron density uniformly across reciprocal space, which is computationally robust but lacks explicit chemical intuition regarding localized bonds. LOBSTER (Local Orbital Basis Suite Towards Electronic-Structure Reconstruction) takes the massive `WAVECAR` from VASP and projects it back to an atomic orbital basis to recover classical chemical bonding insights.

Because `WAVECAR` files are extremely large (often tens or hundreds of gigabytes), LOBSTER analysis must be performed on the *same remote node* directly after the VASP static loop. The `atomate2` `VaspLobsterMaker` automates this sequentially (Relax -> Static -> Lobster) and ensures the massive `WAVECAR` is deleted once the projection completes.

## Installation

LOBSTER is free to download for non-commercial use from [http://www.cohp.de/](http://www.cohp.de/). 

To use this skill, deploy the compiled `lobster` binary to your remote HPC worker or local testing environment and ensure its path is exported in your environment `PATH`. All required Python packages (`lobsterpy`, `ijson`) are already provided by the `atomate2-agent` environment.

## Instructions

### 1. Generate and Execute the Workflow
To submit a LOBSTER workflow, utilize the built-in MCP tool. This natively maps the `VaspLobsterMaker` directed acyclic graph (DAG) to your HPC resources:

**Tool:** `mcp_atomate2_run_atomate2_vasp_calculation`
**Arguments:**
- `structures_path`: Path to your POSCAR or CIF.
- `calculation_type`: `"lobster"`
- `execution_mode`: `"remote"` (to execute on the HPC worker)

**CRITICAL**: Do not run this locally unless you are purely generating testing DAGs (`check_only=True`). The generated flow contains heavy VASP iterations and high-memory LOBSTER matrix projections.

### 2. Parse and Analyze Output
Once completed, the termination node returns a `LobsterTaskDocument`. The most critical file generated is `COHPCAR.lobster`, which contains the Crystal Orbital Hamilton Populations (COHP).

To analyze COHP outputs, the standard package is **LobsterPy**. It offers both CLI and Python API tools:

**Via CLI:**
```bash
# Env: atomate2-agent
lobsterpy automatic-plot
```

**Via Python API:**
Use the provided `analyze_lobster.py` script as a baseline to parse and visualize the COHPCAR out of the compute node limits.

You can test the DAG generation by running the MCP tool with `check_only=True` on a structure, or if testing scripts manually:

```bash
# Env: atomate2-agent
cd .agents/skills/mat-dft-lobster/examples/GaAs
python ../../scripts/generate_inputs.py --output gaas_flow.json
```

To plot a sample COHPCAR:
```bash
# Env: atomate2-agent
python .agents/skills/mat-dft-lobster/scripts/analyze_lobster.py --cohpcar COHPCAR.lobster --poscar POSCAR --save cohp_plot.png
```

## Constraints
- **Environments**: Scripts require the `atomate2-agent` environment.
- **HPC Execution**: You must map this flow to run on an HPC environment natively since `WAVECAR` sizes exceed optimal transfer limits. Ensure both `vasp_std` and `lobster` binaries are available to the workers.
- **Basis Sets**: The `VaspLobsterMaker` optimally restricts VASP settings (e.g., setting `ISYM=-1`, generating all $k$-points explicitly) to comply with LOBSTER's mathematical constraints. Do not manually override these strict geometry settings unless required by standard pseudopotential edge cases.

## References
- Maintz, S., Deringer, V. L., Tchougréeff, A. L., & Dronskowski, R. "LOBSTER: A tool to extract chemical bonding from plane-wave based DFT", *J. Comput. Chem.*, 37, 1030-1035 (2016). [DOI](https://doi.org/10.1002/jcc.24300)

---

**Author:** Bowen Deng  
**Contact:** [GitHub](https://github.com/bowen-bd)
