---
name: mat-htvs-mlip-relax
description: Export structures from HTVS database, relax them using MLIPs (FAIRChem/MACE), and ingest the relaxed energies back into the database.
category: [materials, htvs, mlip]
---

# HTVS MLIP Relaxation Skill

This skill provides a standardized, decoupled workflow to calculate Machine Learning Interatomic Potential (MLIP) relaxation energies for structures tracked in the HTVS database. 

Because the HTVS database management requires the `htvs-agent` environment while MLIP models require isolated environments (like `fairchem-agent` or `mace-agent`), this workflow decouples the extraction, relaxation, and ingestion steps to avoid `ModuleNotFoundError` issues and dependency conflicts.

## Workflow Execution

### 1. Export Surfaces (`htvs-agent`)

Extract target surfaces into CIF files and generate a `metadata.json` mapping file.

```bash
# Env: htvs-agent
python .agents/skills/mat-htvs-mlip-relax/scripts/export_surfaces.py \
    --group fe-binary-screen \
    --config_name clean_surface_cut \
    --output_dir research/my_mlip_relax_folder \
    --settings djangochem.settings.toy
```

*Optional args:*
- `--bulk_ids_json <path>`: Filter export to only surfaces originating from specific bulk IDs.
- `--surface_ids_json <path>`: Filter export to only specific surface IDs.

### 2. Relax with MLIP (`fairchem-agent` or `mace-agent`)

Read the exported directory, perform relaxation, and write energies to `results.json`.

```bash
# Env: fairchem-agent
python .agents/skills/mat-htvs-mlip-relax/scripts/relax_mlip.py \
    --input_dir research/my_mlip_relax_folder \
    --model_type fairchem \
    --model_name uma-s-1p1 \
    --fmax 0.03
```

*Args:*
- `--model_type`: Choose between `fairchem`, `mace`, or `matgl`.
- `--model_name`: The specific pre-trained model name.

### 3. Ingest Results (`htvs-agent`)

Read `results.json`, update the surface coordinates, and attach the MLIP calculated energies as `Calc` models.

```bash
# Env: htvs-agent
python .agents/skills/mat-htvs-mlip-relax/scripts/import_relaxations.py \
    --input_dir research/my_mlip_relax_folder \
    --model_name uma-s-1p1 \
    --group fe-binary-screen \
    --config_name uma_small_relaxed_surf \
    --settings djangochem.settings.toy
```
