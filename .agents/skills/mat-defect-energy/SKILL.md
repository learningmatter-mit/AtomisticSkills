---
name: mat-defect-energy
description: Calculate point-defect formation energies (vacancies, substitutions, interstitials) using MLIPs.
category: [materials]
---

# Point-Defect Formation Energy (MLIP)

## Goal
To calculate the formation energy ($E_f$) of neutral point defects (vacancies, substitutions, and interstitials) using Machine Learning Interatomic Potentials (MLIPs). Formation energy is defined as:

$$E_f = E_\mathrm{defect} - \frac{n_\mathrm{defect}}{n_\mathrm{bulk}} E_\mathrm{bulk} + \sum_i \Delta n_i \mu_i$$

where $E_\mathrm{defect}$ and $E_\mathrm{bulk}$ are the total energies of the defective and pristine supercells, $n$ is the number of atoms, $\Delta n_i$ is the change in number of species $i$, and $\mu_i$ is the chemical potential of species $i$.

## Instructions

### 1. Select Level of Theory
Choose an MLIP model. See [ml-foundation-potentials](../ml-foundation-potentials/SKILL.md) for guidance.
- **Recommended**: r2SCAN-level potentials for inorganic defects (e.g., `MACE-MH-1` with `matpes_r2scan` head).
- Use the **same model** for bulk and defect calculations.

### 2. Obtain Bulk Structure
Start with a relaxed bulk primitive cell. You can retrieve one from Materials Project:
```bash
mcp_base_search_materials_project_by_formula(formula="MgO", save_to_file="MgO.cif")
```

### 3. Relax Bulk Structure
Relax the bulk unit cell to get the reference energy:
```bash
mcp_mace_load_model(model_name="MACE-MH-1", task_name="matpes_r2scan")
mcp_mace_relax_structure(
    structure_data="MgO.cif",
    relax_cell=True,
    fmax=0.01,
    output_dir="bulk_relaxation/"
)
```
Record the final **energy per atom** from the output.

### 4. Generate Defect Supercells
Use the defect generation script with `pymatgen-analysis-defects`:
```bash
# Env: base-agent
python .agents/skills/mat-defect-energy/scripts/generate_defects.py \
    --bulk bulk_relaxation/relaxed_structure.cif \
    --supercell_size 2 2 2 \
    --defect_type vacancy \
    --output defect_structures/
```

**Options for `--defect_type`:**
- `vacancy` — removes each symmetry-unique atom
- `substitution` — replaces atoms with `--substitute_element` at each unique site
- `interstitial` — inserts `--interstitial_element` at Voronoi interstitial sites
- `all` — generates all vacancy types

### 5. Relax Defect Supercells
Relax **without cell relaxation** (fixed supercell volume):
```bash
mcp_mace_relax_structure(
    structure_data="defect_structures/",
    relax_cell=False,  # Fixed cell for defect calculations
    fmax=0.02,
    output_dir="defect_relaxations/"
)
```

### 6. Calculate Formation Energies
Compute defect formation energies:
```bash
# Env: base-agent
python .agents/skills/mat-defect-energy/scripts/calculate_defect_energy.py \
    --bulk_dir bulk_relaxation/ \
    --defect_dir defect_relaxations/ \
    --supercell_size 2 2 2 \
    --output defect_energies.json
```
The script automatically:
- Parses bulk and defect relaxation results
- Determines removed/added species and computes $\Delta n_i$
- Uses elemental energies from [mat-elemental-energies](../mat-elemental-energies/SKILL.md) as default chemical potentials (metal-rich limit)
- Reports formation energies in eV

## Examples

### Oxygen Vacancy in MgO
```bash
# 1. Get MgO structure
mcp_base_search_materials_project_by_formula(formula="MgO")

# 2. Relax bulk
mcp_mace_load_model(model_name="MACE-MH-1", task_name="matpes_r2scan")
mcp_mace_relax_structure(structure_data="MgO.cif", relax_cell=True, fmax=0.01, output_dir="bulk/")

# 3. Generate O vacancy supercells
python .agents/skills/mat-defect-energy/scripts/generate_defects.py \
    --bulk bulk/relaxed_structure.cif --supercell_size 3 3 3 --defect_type vacancy --output vacancies/

# 4. Relax defect structures
mcp_mace_relax_structure(structure_data="vacancies/", relax_cell=False, fmax=0.02, output_dir="vac_relax/")

# 5. Compute formation energies
python .agents/skills/mat-defect-energy/scripts/calculate_defect_energy.py \
    --bulk_dir bulk/ --defect_dir vac_relax/ --supercell_size 3 3 3 --output vac_energies.json
```
Expected: O vacancy formation energy ~6–8 eV (DFT reference: ~7.2 eV for neutral O vacancy in MgO).

## Constraints
- **Neutral defects only**: This skill does NOT handle charged defects. For charged defects with finite-size corrections, use [mat-defect-energy-dft](../mat-defect-energy-dft/SKILL.md).
- **Fixed cell**: Do NOT relax the unit cell during defect relaxation — the supercell must remain fixed to be commensurate with the bulk reference.
- **Supercell size**: Use at least 3×3×3 for cubic systems to minimize periodic image interactions. Formation energies converge with supercell size.
- **Chemical potential**: Default uses metal-rich limit (elemental energies). For environment-specific stability, manually provide chemical potentials.
- **Environments**: Defect generation and energy calculation scripts require `base-agent`.

---

**Author:** Bowen Deng  
**Contact:** [GitHub @bowen-bd](https://github.com/bowen-bd)
