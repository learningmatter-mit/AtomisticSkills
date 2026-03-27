# MgO Vacancy Formation Energy Example

Neutral vacancy formation energies in MgO using MACE-MH-1 (`omat_pbe`) with a 3×3×3 supercell (54 atoms).

## Run

```bash
# Step 1: Fetch MgO from Materials Project
mcp_base_search_materials_project_by_formula(formula="MgO")

# Step 2: Load MACE model
mcp_mace_load_model(model_name="MACE-MH-1", task_name="omat_pbe")

# Step 3: Relax bulk primitive cell
mcp_mace_relax_structure(structure_data="MgO.cif", fmax=0.01, output_dir="bulk_relaxation")

# Step 4: Generate vacancy supercells
# Env: base-agent
python .agents/skills/mat-defect-energy/scripts/generate_defects.py \
    --bulk bulk_relaxation/relaxed_structure.cif \
    --supercell_size 3 3 3 \
    --defect_type vacancy \
    --output vacancy_structures/

# Step 5: Relax pristine supercell and each defect structure
mcp_mace_relax_structure(structure_data="vacancy_structures/pristine_supercell.cif", fmax=0.01, output_dir="pristine_relaxation")
mcp_mace_relax_structure(structure_data="vacancy_structures/vac_Mg_0.cif", fmax=0.01, output_dir="defect_relaxations/vac_Mg_0")
mcp_mace_relax_structure(structure_data="vacancy_structures/vac_O_1.cif", fmax=0.01, output_dir="defect_relaxations/vac_O_1")

# Step 6: Calculate formation energies
# Env: base-agent
python .agents/skills/mat-defect-energy/scripts/calculate_defect_energy.py \
    --bulk_dir pristine_relaxation/ \
    --defect_dir defect_relaxations/ \
    --elemental_energies .agents/skills/mat-elemental-energies/resources/MACE-MH-1_omat_pbe_energies.json \
    --output defect_energies.json
```

## Expected Results

| Defect | Formation Energy (eV) | DFT PBE Literature (eV) |
|--------|:---------------------:|:-----------------------:|
| V_O (F-center) | ~7.1 | 7–10 |
| V_Mg | ~7.4 | 7–10 |

## Output Files

- `pristine_supercell.cif` — 3×3×3 MgO supercell (Mg₂₇O₂₇, 54 atoms)
- `vac_Mg_0.cif` — Mg vacancy supercell (53 atoms)
- `vac_O_1.cif` — O vacancy supercell (53 atoms)
- `defect_energies.json` — Computed formation energies with elemental references

## References

1. P. Rinke, A. Schleife, E. Kioupakis, A. Janotti, C. Rödl, F. Bechstedt, M. Scheffler, C. G. Van de Walle, "First-Principles Optical Spectra for F Centers in MgO," *Phys. Rev. Lett.* **108**, 126404 (2012). [DOI: 10.1103/PhysRevLett.108.126404](https://doi.org/10.1103/PhysRevLett.108.126404)
2. C. Freysoldt, B. Grabowski, T. Hickel, J. Neugebauer, G. Kresse, A. Janotti, C. G. Van de Walle, "First-principles calculations for point defects in solids," *Rev. Mod. Phys.* **86**, 253 (2014). [DOI: 10.1103/RevModPhys.86.253](https://doi.org/10.1103/RevModPhys.86.253)
