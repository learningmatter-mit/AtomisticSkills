---
name: mat-surface-adsorption
description: Calculate surface adsorption energies for adsorbate-surface combinations using MLIPs.
category: [materials]
---

# Surface Adsorption Skill

This skill provides tools for calculating adsorption energies ($E_{ads}$) of molecules on crystalline surfaces using Machine Learning Interatomic Potentials (MLIPs).

## Goal

To calculate the adsorption energy for a given adsorbate-surface combination, defined as:

$$E_{ads} = E_{adsorbate+slab} - E_{slab} - E_{adsorbate}$$

where:
- $E_{adsorbate+slab}$ is the total energy of the adsorbate adsorbed on the surface
- $E_{slab}$ is the energy of the clean slab
- $E_{adsorbate}$ is the energy of the isolated adsorbate molecule

The skill uses MatCalc's `AdsorptionCalc` to automate the full workflow: bulk relaxation, slab generation, adsorbate relaxation, site identification, and energy calculations.

## Prerequisites

- The appropriate MLIP wrapper must be available (`MACEWrapper`, `MatGLWrapper`, or `FAIRCHEMWrapper`)
- `matcalc`, `pymatgen`, and `ase` must be installed in the relevant conda environment
- A bulk crystalline structure file (CIF, POSCAR, etc.)
- An adsorbate molecule structure file (XYZ, CIF) or SMILES string

## Choosing a Foundation Potential

Adsorption energy calculations require accurate prediction of both energies and forces, particularly for the adsorbate-surface interaction. **Models trained on Open Catalyst datasets are especially recommended** as they were specifically designed for catalysis and surface chemistry.

> [!IMPORTANT]
> **Recommended models (in order of preference):**
> 1. **Open Catalyst trained models** (BEST for surface adsorption):
>    - FAIRChem: `EquiformerV2-31M-S2EF-OC20-All+MD`, `EquiformerV2-153M-S2EF-OC20-All+MD`
>    - FAIRChem UMA: `uma-s-1p1`, `uma-m-1p1` (universal, includes OC20/OC25 data)
>    - MACE-OMAT: `MACE-OMAT-0-small`, `MACE-OMAT-0-medium` (trained on OC datasets)
> 2. **MatPES trained models** (Good for general surfaces):
>    - `CHGNet-MatPES-PBE-2025.2.10-2.7M-PES`
>    - `M3GNet-MatPES-PBE-v2025.1-PES`
>    - `MACE-MatPES-PBE-0`
> 3. **Avoid MPtrj-only models**: Models trained primarily on the `MPtrj` dataset may suffer from force prediction issues critical for adsorption.

**Why Open Catalyst models?** The OC20, OC22, and OC25 datasets contain millions of adsorbate-surface configurations specifically for catalysis, making these models highly accurate for adsorption energies and barriers.

Refer to the [foundation-potentials skill](../ml-foundation-potentials/SKILL.md) for detailed guidance on model selection.

## Calculation Workflow

To calculate adsorption energies, use the `calculate_adsorption.py` script:

```bash
# Env: fairchem-agent
python .agents/skills/mat-surface-adsorption/scripts/calculate_adsorption.py \
    --bulk path/to/bulk_structure.cif \
    --adsorbate path/to/adsorbate.xyz \
    --miller_index '[1,1,1]' \
    --model_type fairchem \
    --model_name EquiformerV2-31M-S2EF-OC20-All+MD \
    --fmax 0.05 \
    --output_dir research/my_folder/adsorption
```

### Key Parameters

- `--bulk`: Path to bulk structure file (CIF, POSCAR, etc.)
- `--adsorbate`: Path to adsorbate molecule file (XYZ, CIF) or SMILES string
- `--miller_index`: Miller index for the surface as JSON list (e.g., `'[1,1,1]'`, `'[1,0,0]'`)
- `--model_type`: MLIP model type (`mace`, `matgl`, or `fairchem`)
- `--model_name`: Specific model name (optional, uses defaults if not provided)

### Optional Settings

**Relaxation control:**
- `--relax_bulk` / `--no_relax_bulk`: Control bulk structure relaxation (default: True)
- `--relax_slab` / `--no_relax_slab`: Control clean slab relaxation (default: True)
- `--relax_adsorbate` / `--no_relax_adsorbate`: Control adsorbate molecule relaxation (default: True)

**Convergence:**
- `--fmax`: Force convergence criterion in eV/Å (default: 0.05)
- `--optimizer`: ASE optimizer (default: BFGS)
- `--max_steps`: Maximum optimization steps (default: 500)

**Slab generation:**
- `--min_slab_size`: Minimum slab thickness in Å (default: 10.0)
- `--min_vacuum_size`: Minimum vacuum layer in Å (default: 20.0)
- `--adsorption_sites`: Sites to consider: 'all', 'ontop', 'bridge', 'hollow' (default: all)
- `--height`: Initial adsorbate height above surface in Å (default: 0.9)

## Output Files

The calculation generates the following files in the output directory:

- `adsorption_results.json`: Complete summary including:
  - Adsorption energies for all identified sites
  - Most stable adsorption site and energy
  - Calculation settings and metadata
  - Individual site energies (adslab, slab, adsorbate)

## Examples

### Example 1: CO on Cu(111)

Calculate the adsorption energy of CO on the (111) surface of Cu using an Open Catalyst trained model:

```bash
# Env: fairchem-agent
python .agents/skills/mat-surface-adsorption/scripts/calculate_adsorption.py \
    --bulk examples/CO_on_Cu111/Cu_bulk.cif \
    --adsorbate examples/CO_on_Cu111/CO.xyz \
    --miller_index '[1,1,1]' \
    --model_type fairchem \
    --model_name EquiformerV2-31M-S2EF-OC20-All+MD \
    --fmax 0.05 \
    --output_dir research/Cu_CO_adsorption
```

**Example structures:**
- [`CO_Cu111_initial.cif`](examples/CO_on_Cu111/CO_Cu111_initial.cif): Initial CO adsorbed on Cu(111) slab
- [`CO_Cu111_relaxed.cif`](examples/CO_on_Cu111/CO_Cu111_relaxed.cif): Relaxed structure after optimization

### Example 2: Using SMILES for Adsorbate

Use a SMILES string to define the adsorbate:

```bash
# Env: matgl-agent
python .agents/skills/mat-surface-adsorption/scripts/calculate_adsorption.py \
    --bulk Pt_bulk.cif \
    --adsorbate "O=C=O" \
    --miller_index '[1,1,1]' \
    --model_type matgl \
    --model_name CHGNet-MatPES-PBE-2025.2.10-2.7M-PES \
    --output_dir research/Pt_CO2_adsorption
```

### Example 3: Different Surface Facet

Calculate adsorption on a (100) surface:

```bash
# Env: fairchem-agent
python .agents/skills/mat-surface-adsorption/scripts/calculate_adsorption.py \
    --bulk Ni_bulk.cif \
    --adsorbate H2.xyz \
    --miller_index '[1,0,0]' \
    --model_type fairchem \
    --model_name uma-s-1p1 \
    --output_dir research/Ni_H2_100
```

## Interpreting Results

The `adsorption_results.json` file contains:

- **`most_stable_site`**: The adsorption site with the lowest (most negative) energy
  - **Negative $E_{ads}$**: Exothermic adsorption (stable)
  - **Positive $E_{ads}$**: Endothermic adsorption (unstable)
  - Typical range: -0.5 to -5.0 eV for strong chemisorption

- **`adsorption_sites`**: List of all calculated sites with individual energies
  - Compare energies to identify preferred binding geometries
  - Multiple sites may have similar energies

- **`num_sites`**: Total number of adsorption sites found
  - Depends on `--adsorption_sites` parameter and surface symmetry

## Constraints

- **Structure Requirements**: 
  - The bulk structure should be a well-relaxed crystalline structure
  - Adsorbate should be a gas-phase molecule (not periodic)
  
- **Miller Indices**:
  - Must be provided as a JSON list: `'[h,k,l]'`
  - Use conventional cell Miller indices for accurate slab generation
  
- **Slab Size**:
  - Default `min_slab_size=10.0 Å` is usually sufficient
  - For layered materials or weak interlayer bonding, may need to increase
  
- **Vacuum Size**:
  - Default `min_vacuum_size=20.0 Å` prevents periodic image interactions
  - Critical for accurate energy calculations
  
- **Environments**:
  - Scripts require specific Conda environments (mace-agent, matgl-agent, or fairchem-agent)
  - **Each code block MUST specify the environment** using `# Env:` annotation
  
- **Computational Cost**:
  - Multiple adsorption sites are calculated automatically
  - Cost scales with number of sites and slab size
  - Use `--adsorption_sites ontop` or `bridge` to limit sites for faster calculations

## See Also

- [mat-surface-energy](../mat-surface-energy/SKILL.md): Calculate surface energies and Wulff shapes
- [general-molecular-dynamics](../general-molecular-dynamics/SKILL.md): MD simulations with MLIPs
- [ml-foundation-potentials](../ml-foundation-potentials/SKILL.md): Guide for MLIP selection
---

**Author:** Bowen Deng  
**Contact:** [GitHub @bowen-bd](https://github.com/bowen-bd)
