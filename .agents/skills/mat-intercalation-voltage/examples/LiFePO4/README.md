# LiFePO₄ Intercalation Voltage Example

Average intercalation voltage of olivine LiFePO₄ cathode using MACE-MH-1 (matpes_r2scan).

## Run

```bash
# 1. Get LiFePO4 from Materials Project
mcp_base_search_materials_project_by_formula(formula="LiFePO4")

# 2. Create de-intercalated structure
# Env: base-agent
python .agents/skills/mat-intercalation-voltage/scripts/remove_atoms.py \
    LiFePO4_structure.cif --remove Li --output FePO4.cif

# 3. Load model & relax all three structures
mcp_mace_load_model(model_name="MACE-MH-1", task_name="matpes_r2scan")
mcp_mace_relax_structure(structure_data="LiFePO4_structure.cif", output_dir="voltage/full_relax")
mcp_mace_relax_structure(structure_data="FePO4.cif", output_dir="voltage/empty_relax")
mcp_mace_relax_structure(
    structure_data=".agents/skills/mat-intercalation-voltage/resources/Li_metal.cif",
    output_dir="voltage/metal_relax"
)

# 4. Calculate voltage (substitute actual energies from relaxation)
# Env: base-agent
python .agents/skills/mat-intercalation-voltage/scripts/calculate_voltage.py \
    --e_full <E_full> --e_empty <E_empty> --e_metal <E_metal> \
    --n_metal <n_metal_atoms> --n_ions <n_Li_removed> --metal Li \
    --output voltage/voltage_results.json
```

## Expected Results

| Property | MLIP | Experimental |
|----------|:----:|:------------:|
| Average voltage (V) | 3.26 | 3.4 |

Error: ~0.14 V (4%) — good agreement for a foundation MLIP without fine-tuning.
