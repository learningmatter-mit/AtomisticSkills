---
name: Generating Binding Energies in HTVS
description: Retrieves completed DFT surface calculations, generates dynamic Binding Energies, and dumps JSON generic data payloads for downsteam analysis.
category: htvs, analysis
---

# Generating Binding Energies in HTVS

This skill extracts targeted adsorbate-containing surface slabs from the database, computes `BindingEnergy` metrics linking them dynamically back to gas-phase thermodynamic points, and produces a decoupled `<group>_binding_energies.json` mapping.

## Configuration & Safety (CRITICAL)

Wait! HTVS operations directly interact with research databases. Before running any commands:
1.  **Expose the Context**: Explicitly state the `settings_module` and `group_name` you are about to use.
2.  **Request Confirmation**: Ask the user: *"I am about to perform this operation on the [GROUP_NAME] project within the [SETTINGS_MODULE] database. Is this correct?"*
3.  **Do NOT proceed** until the user gives explicit approval.

This file serves as the generic property bridge feeding directly into `.agents/skills/mat-htvs-catalysis-activity-analysis` to evaluate OER/ORR/CO2RR/NRR scaling laws.

### 1. Execute the Pipeline
Run the generator using the specific group configuration parameters:

```bash
# Env: htvs-agent
python .agents/skills/mat-htvs-genbindingenergy/scripts/generate_binding_energy.py \
    --group my_project \
    --config_name pbe_paw_opt_vasp \
    --ref_group surface_binding_energy_references \
    --ref_config pbe_u_paw_spinpol_opt_vasp \
    --settings djangochem.settings.orgel \
    --output_data ./research/current_research_dir/binding_energies.json
```

### 2. Connect into Analytics
Navigate back into the standard analysis module (`mat-htvs-catalysis-activity-analysis`) and parse your newly created JSON:
```bash
python .agents/skills/mat-htvs-catalysis-activity-analysis/scripts/run.py \
    --reaction OER \
    --data_file ./research/current_research_dir/binding_energies.json
```

## Constraints
- **Environment**: Requires `htvs-agent` conda environment to map and interact with the Django Models and HTVS database schemas.
- **Dependencies**: Django backend configurations MUST be supplied dynamically during runtime to correctly initialize PostgreSQL connections.
- **Data Integrity**: Ensure the JSON export is structurally intact before dropping it into decoupled analysis endpoints.
- **Data ID Tracking**: Every script execution will output a JSON block with the related Database IDs (Job IDs, Result IDs) for agentic tracking.

**Author**: Hoje Chun
**Contact**: [GitHub @hojechun](https://github.com/hojechun)
