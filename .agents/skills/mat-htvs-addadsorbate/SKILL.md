---
name: mat-htvs-addadsorbate
description: Add adsorbate species (O, OH, OOH) to clean surface slabs stored in the HTVS database at catalytically active B-top sites.
category: materials
---
# Add Adsorbates to Surfaces (HTVS)

## Goal
Place adsorbate species at B-top sites on clean surface slabs already stored in the HTVS database and save the resulting adsorbate-decorated surfaces as new records.

## Configuration & Safety (CRITICAL)

Wait! HTVS operations directly interact with research databases. Before running any commands:
1.  **Expose the Context**: Explicitly state the `settings_module` and `group_name` you are about to use.
2.  **Request Confirmation**: Ask the user: *"I am about to perform this operation on the [GROUP_NAME] project within the [SETTINGS_MODULE] database. Is this correct?"*
3.  **Do NOT proceed** until the user gives explicit approval.
4.  **Track DB IDs**: Use the `--output_log` parameter to dump generated IDs. (Note: This is partially automated in newer MCP tools).

## Instructions

### 1. Ensure Clean Surfaces and Group Exist
Run the [mat-htvs-cutcleansurface](../mat-htvs-cutcleansurface/SKILL.md) skill first to generate the parent clean surfaces.
Also ensure the HTVS project group exists:
```python
mcp_htvs_create_group(
    settings_module="orgel",
    group_name="my_project"
)
```

### 2. Prepare a Bulk ID Pickle
The bulk IDs are used to filter the set of clean surfaces:
```python
# Env: htvs-agent
import pickle
bulk_ids = [1, 2, 3, ...]
pickle.dump(bulk_ids, open("bulk_ids.pkl", "wb"))
```

### 3. Run the Script
```bash
# Env: htvs-agent
python .agents/skills/mat-htvs-addadsorbate/scripts/add_adsorbate.py \
    --group my_project \
    --config_name clean_surface_cut \
    --species OH \
    --bulk_pkl /path/to/bulk_ids.pkl \
    --settings djangochem.settings.orgel
```

#### Parameters
| Flag | Required | Description |
|---|---|---|
| `--group` | ✅ | HTVS project group name |
| `--config_name` | ✅ | Config name of the parent clean surfaces |
| `--species` | ✅ | Adsorbate species: `O`, `OH`, or `OOH` |
| `--bulk_pkl` | ✅ | Pickle file of bulk IDs to filter surfaces |
| `--settings` | ✅ | Django settings module |
| `--output_log` | ❌ | JSON file path to save created surface IDs |
| `--limit` | ❌ | Max number of surfaces to process (default: 10000) |
| `--dry_run` | ❌ | Simulate without writing to DB |
| `--djangochem` | ❌ | Path to the djangochem project root if needed |

### 4. Verify Results
```python
mcp_htvs_query_structures(
    settings_module="orgel",
    group_name="my_project",
    structure_type="surface",
    config_name="add_adsorbate",
)
```

## Constraints
- Only `O`, `OH`, and `OOH` are natively supported. Adding further adsorbates requires extending `get_adsorbate()` in `scripts/run.py`.
- The script locates B-top adsorption sites by walking up the job chain to the `clean_surface_cut` parent.
- **Environment**: `htvs-agent`

## References
- J. Lunger et al., *npj Comput. Mater.*, 2024. [DOI](https://doi.org/10.1038/s41524-024-01273-y)
- H. Chun et al., *npj Comput. Mater.*, 2024. [DOI](https://doi.org/10.1038/s41524-024-01432-1)

---

**Author:** Hoje Chun  
**Contact:** [GitHub @hojechun](https://github.com/hojechun)
