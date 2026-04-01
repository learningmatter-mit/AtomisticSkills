---
name: mat-magnetic-density
description: Calculate magnetic moments and spin density from spin-polarized DFT calculations using VASP.
category: [materials]
---

# Magnetic Density

## Goal

To calculate the magnetic moments and optionally extract the spin density ($\rho_{\text{spin}}$) of magnetic materials using spin-polarized DFT calculations. This skill enables the characterization of magnetic ordering, local magnetic moments on individual atoms, and spatial distribution of spin density.

## Instructions

### 1. Structure Preparation

Obtain or prepare the structure of the magnetic material you want to study. You can:
- Query from Materials Project using the base MCP tools (recommended - already DFT-optimized)
- Load from a local CIF/POSCAR file
- Use a previously relaxed structure

**Note on relaxation**: For magnetic moment calculations, **relaxation is optional** if using high-quality experimental or Materials Project structures. Magnetic moments are relatively insensitive to small structural variations. However, **relaxation is recommended** for:
- New/hypothetical structures
- Surfaces, interfaces, or defects
- Systems where you need accurate total energies (not just magnetic moments)
- Strongly correlated oxides with significant magnetic-structural coupling

### 2. Run Spin-Polarized DFT Calculation

Use the atomate2 MCP tool to run a spin-polarized static calculation. The `mp` preset (MPStaticSet) automatically enables spin polarization and applies appropriate settings for magnetic systems.

```python
mcp_atomate2_run_atomate2_vasp_calculation(
    structures_path="structure.cif",  # Path to your structure file
    output_dir="magnetic_calc",       # Directory to save results
    preset_type="mp",  # MPStaticSet with PBE (includes spin polarization)
    calculation_type="static",         # Static calculation
)
```

**Important - Functional Selection**:
- **For metallic ferromagnets** (Fe, Co, Ni): Use `mp` preset (MPStaticSet with PBE). PBE provides excellent accuracy for magnetic moments (typically within ~2% of experimental values)[1].
- **For strongly correlated oxides** (NiO, CoO, FeO): Use `mp` preset (see Example 2 below). MPStaticSet automatically applies appropriate GGA+U corrections for transition metal oxides. Standard PBE fails to predict the correct insulating antiferromagnetic ground state and severely underestimates band gaps[3]. **Note**: +U corrections improve electronic structure but do not guarantee better magnetic moments (e.g., GGA+U may overestimate for NiO or underestimate for CoO due to missing orbital contributions)[4].
- **Avoid r2SCAN for metallic ferromagnets**: r2SCAN significantly overestimates magnetic moments in itinerant ferromagnets like Fe (by ~24% compared to experimental values)[2].

**References**:
[1] PBE underestimates Fe magnetization by only 1.8%: Zhang et al., *Phys. Rev. Materials* **6**, 013801 (2022). DOI: [10.1103/PhysRevMaterials.6.013801](https://doi.org/10.1103/PhysRevMaterials.6.013801)  
[2] r2SCAN and SCAN overestimate Fe magnetization by 24% and 17% respectively: ibid.  
[3] PBE+U opens band gaps and corrects ground state in transition metal oxides: Kulik, *J. Chem. Phys.* **142**, 240901 (2015). DOI: [10.1063/1.4922693](https://doi.org/10.1063/1.4922693)  
[4] CoO magnetic moments: PBE+U underestimates due to missing orbital contributions: Radi et al., *Z. Naturforsch. A* **70**, 789 (2015). DOI: [10.1515/zna-2015-0216](https://doi.org/10.1515/zna-2015-0216)

See the "Functional Selection Guide" section below for detailed recommendations.

### 3. Monitor Job Status

After submitting the calculation, monitor its progress:

```python
mcp_atomate2_get_atomate2_job_status(
    job_id="<job_id_from_step_2>"  # Job ID returned from step 2
)
```

### 4. Extract Magnetic Moments

Once the calculation is complete, retrieve the results to extract magnetic moments:

```python
mcp_atomate2_get_atomate2_results_by_id(
    job_ids=["<job_id>"],  # List of job IDs
    save_to_file="magnetic_results.json"  # Save results to file
)
```

The results will include:
- **Total magnetization**: Net magnetic moment of the unit cell
- **Site magnetic moments**: Magnetic moment on each atom
- **Energy**: Total energy of the magnetic configuration

### 5. Parse and Analyze Results

Use the provided script to parse the magnetic moments from the results:

```bash
# Env: base-agent
python .agents/skills/mat-magnetic-density/scripts/parse_magnetic_moments.py magnetic_results.json --output magnetic_analysis.json
```

This script will:
- Extract site-resolved magnetic moments
- Calculate the total magnetization
- Identify the magnetic ordering pattern
- Generate a summary report

### 6. Extract Spin Density (Optional)

For detailed analysis of spin density distribution, use the spin density extraction script:

```bash
# Env: base-agent
python .agents/skills/mat-magnetic-density/scripts/extract_spin_density.py <output_dir> --output spin_density.json
```

This requires access to the CHGCAR file from the VASP calculation and will:
- Read the spin density from CHGCAR
- Calculate integrated spin moments
- Optionally generate 3D visualization data

### 7. Visualize Magnetic Ordering (Optional)

Visualize the magnetic ordering by creating a structure with magnetic moment vectors:

```bash
# Env: base-agent
python .agents/skills/mat-magnetic-density/scripts/visualize_magnetic_structure.py structure.cif magnetic_analysis.json --output magnetic_structure.png
```

## Examples

### Example 1: Calculate magnetic moments for bulk Fe

```python
# Step 1: Get Fe structure from Materials Project
mcp_base_search_materials_project_by_formula(
    formula="Fe",
    save_to_file="Fe_mp.cif"
)

# Step 2: Run spin-polarized static calculation
mcp_atomate2_run_atomate2_vasp_calculation(
    structures_path="Fe_mp.cif",
    output_dir="Fe_magnetic",
    preset_type="mp",  # MPStaticSet with PBE
    calculation_type="static",
    execution_mode="remote"
)

# Step 3: After completion, retrieve results
mcp_atomate2_get_atomate2_results_by_id(
    job_ids=["<job_id>"],
    save_to_file="Fe_magnetic_results.json"
)
```

```bash
# Step 4: Parse magnetic moments
# Env: base-agent
python .agents/skills/mat-magnetic-density/scripts/parse_magnetic_moments.py Fe_magnetic_results.json --output Fe_moments.json
```

### Example 2: NiO with automatic GGA+U

```python
# For transition metal oxides like NiO, use 'mp' preset
# MPStaticSet automatically applies appropriate U parameters (e.g., U=6.2 eV for Ni in oxides)
# This ensures correct insulating antiferromagnetic ground state

mcp_atomate2_run_atomate2_vasp_calculation(
    structures_path="NiO.cif",
    output_dir="NiO_magnetic",
    preset_type="mp",  # MPStaticSet automatically handles +U for transition metal oxides
    calculation_type="static",
    execution_mode="remote"
)
```

## Functional Selection Guide

Choosing the right exchange-correlation functional is critical for accurate magnetic property calculations:

### For Metallic Ferromagnets (Fe, Co, Ni, etc.)

**Recommended**: PBE (use `preset_type="mp"` for MPStaticSet)
- PBE underestimates magnetic moments by only ~1.8% for Fe
- Provides excellent agreement with experimental spin magnetization
- Computational efficiency superior to meta-GGA functionals
- **Do NOT use**: r2SCAN overestimates by ~24% for Fe

**Example**: Bulk Fe experimental value = 2.2 μB/atom
- PBE prediction: ~2.15 μB/atom (2% error) ✓
- r2SCAN prediction: ~2.73 μB/atom (24% error) ✗

### For Transition Metal Oxides and Strongly Correlated Systems

**Recommended**: PBE with automatic +U (use `preset_type="mp"` - MPStaticSet handles this automatically)

**When to use PBE+U**:
1. **Localized d-electrons**: Systems where d-electrons exhibit strong correlation (NiO, CoO, Fe₂O₃)
2. **Band gap issues**: Standard PBE underestimates band gaps significantly
3. **Magnetic ground states**: PBE gives incorrect magnetic ordering or underestimates moments
4. **Redox chemistry**: Systems involving oxidation state changes

**U parameter selection**:
- U values are material-dependent and typically calibrated against experimental band gaps or magnetic moments
- Common values: U = 3-5 eV for 3d transition metals in oxides
- For NiO: U = 5-6 eV is typical
- Consult literature for your specific system

**Why standard GGA fails for oxides**:
- Self-interaction error artificially delocalizes d-electrons
- Underestimates band gaps and magnetic exchange interactions
- May predict incorrect magnetic ground states

## Constraints

- **Spin Polarization**: The `mp` preset (MPStaticSet) automatically enables spin polarization (ISPIN=2) for magnetic systems. MAGMOM values are also automatically initialized (default 0.6 per magnetic atom).
- **Initial Magnetic Moments**: For complex magnetic ordering (e.g., antiferromagnetic), you should provide initial MAGMOM values through the config parameter to help convergence.
- **Environment**: The parsing scripts require the `base-agent` conda environment with pymatgen installed.
- **Remote Execution**: DFT calculations are computationally expensive and should typically be run on remote clusters using `execution_mode="remote"`.
- **CHGCAR Access**: Extracting spin density requires access to the CHGCAR file, which may not be automatically retrieved. You may need to manually download it from the remote execution directory.
- **Convergence**: Magnetic systems can be challenging to converge. If calculations fail to converge, try:
  - Adjusting MAGMOM initial values
  - Increasing NELM (max electronic steps)
  - Using a denser k-point mesh
  - Enabling LDAU for strongly correlated systems

## References

- VASP Manual: [Spin-polarized calculations](https://www.vasp.at/wiki/index.php/Spin-polarized_calculations)
- Pymatgen Documentation: [Magnetic Structure Analysis](https://pymatgen.org/pymatgen.analysis.magnetism.html)

---
---

**Author:** Bowen Deng  
**Contact:** [GitHub @bowen-bd](https://github.com/bowen-bd)
