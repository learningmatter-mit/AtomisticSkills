---
name: mat-htvs-cutcleansurface
description: Cut clean surface slabs from crystal bulk structures in the HTVS database by specifying a Miller index.
category: materials
---
# Cut Clean Surfaces (HTVS)

## Goal
Generate surface slab structures from bulk crystals stored in the HTVS database for a specified Miller index and bind them to the database under the `clean_surface_cut` config.

## Instructions

### 1. Prepare a Bulk ID Pickle
Save a list of Crystal IDs you want to slice into a `.pkl` file:
```python
# Env: htvs-agent
import pickle
bulk_ids = [1, 2, 3, ...]
pickle.dump(bulk_ids, open("bulk_ids.pkl", "wb"))
```

### 2. Run the Script
```bash
# Env: htvs-agent
python .agents/skills/mat-htvs-cutcleansurface/scripts/run.py \
    --group my_project \
    --bulk_pkl /path/to/bulk_ids.pkl \
    --MI 1 1 0 \
    --settings djangochem.settings.orgel
```

#### Parameters
| Flag | Required | Description |
|---|---|---|
| `--group` | ✅ | HTVS project group name |
| `--bulk_pkl` | ✅ | Pickle file of crystal IDs |
| `--MI` | ✅ | Miller index, space-separated (e.g. `1 1 0`) |
| `--settings` | ✅ | Django settings module |
| `--limit` | ❌ | Max number of crystals to process (default: 10000) |
| `--dry_run` | ❌ | Simulate without writing to DB |
| `--djangochem` | ❌ | Path to the djangochem project root if needed |

### 3. Verify Results
After the run, query the new surfaces using:
```python
mcp_htvs_query_structures(
    settings_module="orgel",
    group_name="my_project",
    structure_type="surface",
    config_name="clean_surface_cut",
)
```

## Constraints
- The config used for created surfaces is hardcoded to `clean_surface_cut`.
- The Crystal's `details["B"]` field must contain the list of active-site element symbols to be exposed at the surface.
- **Environment**: `htvs-agent`

## References
- Nørskov et al., *J. Electrochem. Soc.*, 2004. [DOI](https://doi.org/10.1149/1.1612015)

---

**Author:** Hoje Chun  
**Contact:** [GitHub @hojechun](https://github.com/hojechun)
