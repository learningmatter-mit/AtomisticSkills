---
name: mat-dielectric-response
description: Calculate frequency-dependent dielectric response using atomate2 OpticsMaker and VASP.
category: [materials]
---

# Dielectric Response

## Goal

To calculate the frequency-dependent dielectric response of a crystalline material using atomate2's `OpticsMaker` and VASP. This includes:

- The independent-particle real and imaginary dielectric functions
- Optical spectra written by the VASP optics workflow
- Post-processing and visualization of the dielectric response

This skill is based on atomate2's optics workflow, which is a flow maker analogous to the band structure workflow.

## Instructions

### 1. Obtain or Prepare the Input Structure

Start with a well-relaxed crystalline structure in CIF or POSCAR format. You can:

- Search Materials Project using the [`mcp_base_search_materials_project_by_formula`](../../../src/mcp_server/base_server.py) tool
- Use a structure from previous calculations
- Create a structure manually using pymatgen or ASE

> [!IMPORTANT]
> The optics workflow assumes a good relaxed bulk structure. Relax the structure first if needed; poor structures will give unreliable optical spectra.

### 2. Run the Optics Workflow

Use the `atomate2` MCP tool with `calculation_type="optics"`:

```python
mcp_atomate2_run_atomate2_vasp_calculation(
    structures_path="structure.cif",        # Input structure file
    output_dir="./optics_results",          # Output directory
    calculation_type="optics",              # Atomate2 optics workflow
    preset_type="omat",                     # VASP preset (omat, mp, matpes-pbe, matpes-r2scan)
    execution_mode="remote",                # "local" or "remote"
    remote_settings={                       # Required for remote execution
        "project": "remote_perlmutter",
        "worker": "perlmutter_worker"
    }
)
```

The workflow automatically:
1. Runs a static calculation to obtain the charge density
2. Runs the optics calculation to compute the dielectric spectrum

If you need to tune optics settings such as `NBANDS`, `NEDOS`, or `CSHIFT`, pass them through `config`:

```python
mcp_atomate2_run_atomate2_vasp_calculation(
    structures_path="structure.cif",
    output_dir="./optics_results",
    calculation_type="optics",
    preset_type="omat",
    config={
        "NBANDS": 64,
        "NEDOS": 2000,
        "CSHIFT": 0.1,
    },
    execution_mode="local"
)
```

### 3. Post-Process and Visualize Results

After the calculation completes, parse the results and generate a dielectric-response plot:

```bash
# Env: base-agent
python .agent/skills/mat-dielectric-response/scripts/plot_dielectric.py \
    optics_results \
    --output dielectric_function.png \
    --mode average
```

The script will:

- Parse `vasprun.xml(.gz)` from the atomate2 optics job
- Extract the dielectric spectrum
- Plot the real and imaginary dielectric response

For anisotropic systems, plot the diagonal tensor components separately:

```bash
# Env: base-agent
python .agent/skills/mat-dielectric-response/scripts/plot_dielectric.py \
    optics_results \
    --output dielectric_components.png \
    --mode diagonal
```

### 4. Manual Inspection of Outputs

If you want to inspect the raw VASP outputs directly, check:

- `vasprun.xml` or `vasprun.xml.gz`
- `OUTCAR`

Search `OUTCAR` for:

- `frequency dependent IMAGINARY DIELECTRIC FUNCTION`
- `frequency dependent REAL DIELECTRIC FUNCTION`
- `MACROSCOPIC STATIC DIELECTRIC TENSOR`

If you need the static dielectric tensor rather than the frequency-dependent spectrum, search `OUTCAR` for `MACROSCOPIC STATIC DIELECTRIC TENSOR`.

## Examples

### Silicon Carbide Optical Dielectric Response

```python
# 1. Prepare a relaxed SiC structure

# 2. Run optics workflow
mcp_atomate2_run_atomate2_vasp_calculation(
    structures_path="SiC.cif",
    output_dir="./SiC_optics",
    calculation_type="optics",
    preset_type="omat",
    config={
        "NBANDS": 64,
        "NEDOS": 2000,
        "CSHIFT": 0.1,
    },
    execution_mode="local"
)

# 3. Plot results
# Env: base-agent
python .agent/skills/mat-dielectric-response/scripts/plot_dielectric.py \
    SiC_optics \
    --output SiC_dielectric.png \
    --mode average
```

See [examples/](examples/) for a SiC dielectric-response tutorial and example plot.

## Constraints

- **Structure Requirements**: Input must be a well-relaxed crystalline structure.
- **Workflow Scope**: This skill covers atomate2's `OpticsMaker` workflow for the frequency-dependent dielectric function.
- **Local-Field Effects**: Advanced manual `ALGO=CHI` local-field corrections are not part of the atomate2 optics workflow documented here.
- **VASP Setup**: Requires properly configured VASP and pseudopotentials.
- **Atomate2 Setup**: Requires atomate2, jobflow, and either local or remote execution configuration.
- **Environments**:
  - Optics calculation: `atomate2-agent`
  - Post-processing scripts: `base-agent`
- **Convergence**:
  - Increase `NBANDS` until the optical spectrum is converged over the energy range of interest
  - Check sensitivity to `NEDOS`, `CSHIFT`, and k-point density
- **Band-Gap Limitation**: Semi-local DFT typically underestimates the absorption onset; use hybrid functionals or beyond-DFT methods for quantitative spectra.

