---
name: mat-electronic-structure
description: Calculate electronic band structure and density of states using atomate2 and VASP.
category: [materials]
---

# Electronic Structure

## Goal

To calculate the electronic band structure of a crystalline material, revealing the energy-momentum relationship for electrons and determining whether the material is metallic, semiconducting, or insulating. This includes computing the band gap ($E_g$), identifying direct vs. indirect transitions, and visualizing the dispersion along high-symmetry k-paths.

## Instructions

### 1. Obtain or Prepare the Input Structure

Start with a relaxed crystalline structure in CIF or POSCAR format. You can:

- Search Materials Project using the [`mcp_base_search_materials_project_by_formula`](../../../src/mcp_server/base_server.py) tool
- Use a structure from previous calculations
- Create a structure manually using pymatgen or ASE

### 2. Run Band Structure Calculation

Use the `atomate2` MCP tool with `calculation_type="band_structure"`:

```python
mcp_atomate2_run_atomate2_vasp_calculation(
    structures_path="structure.cif",           # Input structure file
    output_dir="./band_structure_results",     # Output directory
    calculation_type="band_structure",         # Band structure calculation
    bandstructure_mode="line",                 # Options: "line", "uniform", "both"
    preset_type="omat",                        # VASP preset (omat, mp, matpes-pbe, matpes-r2scan)
    execution_mode="remote",                   # "local" or "remote"
    remote_settings={                          # Required for remote execution
        "project": "remote_perlmutter",
        "worker": "perlmutter_worker"
    }
)
```

**Band structure modes:**
- `"line"`: Calculate along high-symmetry k-paths (for band structure plots)
- `"uniform"`: Calculate on a uniform k-mesh (for density of states)
- `"both"`: Perform both line and uniform calculations

The workflow automatically:
1. Runs a static SCF calculation to obtain the charge density
2. Runs a non-SCF calculation to compute band structure eigenvalues

### Alternative: Retrieve Pre-Computed Data from Materials Project

Instead of running DFT calculations, you can retrieve existing electronic structure data from Materials Project:

```bash
# Env: base-agent
python .agents/skills/mat-electronic-structure/scripts/get_mp_electronic_structure.py \
    --material_id mp-149 \
    --output si_mp_bands.json \
    --plot
```

**This retrieves**:
- Pre-computed band structure along high-symmetry paths
- Density of states (DOS)
- Band gap (energy, direct/indirect)
- Fermi energy

**When to use MP retrieval vs. calculations**:
- **Retrieve from MP**: Quick screening, validation, known materials
- **Run calculations**: New materials, custom structures, specific DFT settings

### 3. Post-Process and Visualize Results

After the calculation completes, parse the results and generate a band structure plot:

```bash
# Env: base-agent
python .agents/skills/mat-electronic-structure/scripts/plot_band_structure.py \
    band_structure_results \
    --output band_structure.png
```

The script will:
- Parse the `vasprun.xml.gz` from the non-SCF job
- Extract band gap information (energy, directness, transition)
- Generate a publication-quality band structure plot

**For DOS (uniform mode)**:

```bash
# Env: base-agent
python .agents/skills/mat-electronic-structure/scripts/plot_dos.py \
    dos_results \
    --output dos.png
```

The script will:
- Parse the `vasprun.xml.gz` from the uniform k-mesh job
- Extract band gap and Fermi level
- Generate a DOS plot

**Alternative: Manual post-processing with pymatgen**

```python
from pymatgen.io.vasp import BSVasprun
from pymatgen.electronic_structure.plotter import BSPlotter

# Load band structure from atomate2 results
vasprun_path = "band_structure_results/results/structure_0/job_*/vasprun.xml.gz"
vasprun = BSVasprun(vasprun_path, parse_projected_eigen=False)
bs = vasprun.get_band_structure(line_mode=True)

# Get band gap
if not bs.is_metal():
    bg = bs.get_band_gap()
    print(f"Band gap: {bg['energy']:.3f} eV")
    print(f"Direct: {bg['direct']}")
    print(f"Transition: {bg['transition']}")

# Plot
plotter = BSPlotter(bs)
ax = plotter.get_plot(ylim=(-10, 10))
ax.get_figure().savefig("band_structure.png", dpi=300, bbox_inches='tight')
```

## Examples

### Silicon Band Structure Calculation

```python
# 1. Search for Si structure
mcp_base_search_materials_project_by_formula(
    formula="Si",
    save_to_file="Si.cif"
)

# 2. Run band structure calculation
mcp_atomate2_run_atomate2_vasp_calculation(
    structures_path="Si.cif",
    output_dir="./Si_bands",
    calculation_type="band_structure",
    bandstructure_mode="line",
    preset_type="omat",
    execution_mode="local"
)

# 3. Plot results
# Env: base-agent
python .agents/skills/mat-electronic-structure/scripts/plot_band_structure.py Si_bands --output Si_bands.png
```

See [examples/](examples/) for a complete Si band structure calculation showing an indirect band gap of 0.581 eV.

### Silicon Density of States (DOS)

```python
# 1. Use existing Si structure (or search Materials Project)

# 2. Run DOS calculation with uniform k-mesh
mcp_atomate2_run_atomate2_vasp_calculation(
    structures_path="Si.cif",
    output_dir="./Si_dos",
    calculation_type="band_structure",
    bandstructure_mode="uniform",  # Uniform k-mesh for DOS
    preset_type="omat",
    execution_mode="local"
)

# 3. Plot DOS
# Env: base-agent
python .agents/skills/mat-electronic-structure/scripts/plot_dos.py Si_dos --output Si_dos.png
```

See [examples/](examples/) for the complete DOS calculation showing the distribution of electronic states.

## Constraints

- **Structure Requirements**: Input must be a crystalline structure with well-defined symmetry. Band structure calculations are not meaningful for amorphous or highly disordered materials.
- **VASP Setup**: Requires properly configured VASP environment:
  - `PMG_VASP_PSP_DIR` must point to POTCAR directory (or set in `~/.pmgrc.yaml`)
  - For remote execution: Atomate2/jobflow-remote must be configured
- **Environments**: 
  - Band structure calculation: `atomate2-agent` (via MCP tool)
  - Post-processing scripts: `base-agent` (pymatgen, matplotlib)
- **Functional Choice**: 
  - PBE (omat, mp presets) typically **underestimates** band gaps
  - For accurate gaps: Use hybrid functionals (HSE06) or GW methods (not yet supported)
  - MatPES presets (matpes-pbe, matpes-r2scan) use r2SCAN which improves gap predictions
- **k-point Density**: The automatic k-path generation uses pymatgen's `HighSymmKpath`. For very accurate results, you may need to manually specify denser k-paths.
- **Spin-Polarization**: Current implementation assumes non-spin-polarized calculations. For magnetic materials, additional configuration may be needed.

## Foundation Potential Recommendations

For exploratory band structure analysis using MLIPs (not DFT):

- **CHGNet**: Can predict band gaps, but accuracy varies
- **Note**: MACE, M3GNet, and other MLIPs trained on PES data do not predict electronic properties

For production calculations, **always use DFT** (this skill) and choose the appropriate functional:
- **Standard screening**: PBE (omat/mp presets)
- **Improved gaps**: r2SCAN (matpes-r2scan preset)
- **Accurate gaps**: HSE06 or GW (requires custom INCAR settings)
---

**Author:** Bowen Deng  
**Contact:** [GitHub @bowen-bd](https://github.com/bowen-bd)
