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

<<<<<<< HEAD
### 0. Initialize Project References (New Projects)

For first-time setup or new screening groups, initialize the gas-phase references (`H2`, `H2O`, `CO2`, `N2`) in your target database. This skill provides a centralized resource and a utility to ensure consistent thermodynamics.

**Verify Reference Energies**:
Check `.agents/skills/mat-htvs-genbindingenergy/resources/reference_molecules.json` to ensure the total energies match your intended level of theory (default: PBE/Hartree).

**Run Initialization**:
```bash
# Env: htvs-agent
python .agents/skills/mat-htvs-genbindingenergy/scripts/migrate_references.py \
    --settings djangochem.settings.toy \
    --group_name my_project \
    --research_dir ./research/current_research_dir
```
=======
### 1. Execute the Pipeline
Run the generator using the specific group configuration parameters:
>>>>>>> origin/htvs

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

<<<<<<< HEAD
### 2. Molecule Energy Scale Correction (Parallel Campaigns)

When running parallel MLIP/DFT campaigns, the MLIP calculated energies must be shifted to the DFT molecule energy scale to ensure thermodynamic consistency in Volcano plots.

**Procedure**:
1. Update `resources/reference_molecules.json` with your high-fidelity DFT molecule energies (e.g., VASP-PBE).
2. Run `generate_binding_energy.py` for the MLIP group, but set `--level` to your DFT level (e.g., `--level PBE`).
3. This forces the script to use DFT molecule baselines even when the surface energies are in MLIP scale, effectively shifting the binding energy results.

### 3. Connect into Analytics
=======
### 2. Connect into Analytics
>>>>>>> origin/htvs
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
