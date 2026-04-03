---
name: mat-htvs-addadsorbate
description: Add adsorbate species (O, OH, OOH) to clean surface slabs stored in the HTVS database at catalytically active B-top sites.
category: materials
---
# Add Adsorbates to Surfaces (HTVS)

## Goal
Place adsorbate species at B-top sites on clean surface slabs already stored in the HTVS database and save the resulting adsorbate-decorated surfaces as new records.

## Instructions

### 1. Ensure Clean Surfaces Exist
Run the [mat-htvs-cutcleansurface](../mat-htvs-cutcleansurface/SKILL.md) skill first to generate the parent clean surfaces.

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
python .agents/skills/mat-htvs-addadsorbate/scripts/run.py \
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
- Nørskov et al., *J. Electrochem. Soc.*, 2004. [DOI](https://doi.org/10.1149/1.1612015)

---

**Author:** Hoje Chun  
**Contact:** [GitHub @hojechun](https://github.com/hojechun)
