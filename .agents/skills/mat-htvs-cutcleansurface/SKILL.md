---
name: mat-htvs-cutcleansurface
description: Cut clean surface slabs from crystal bulk structures in the HTVS database by specifying a Miller index.
category: materials
---
# Cut Clean Surfaces (HTVS)

## Goal
Generate surface slab structures from bulk crystals stored in the HTVS database for a specified Miller index and bind them to the database under the `clean_surface_cut` config.

## Configuration & Safety (CRITICAL)

Wait! HTVS operations directly interact with research databases. Before running any commands:
1.  **Expose the Context**: Explicitly state the `settings_module` and `group_name` you are about to use.
2.  **Request Confirmation**: Ask the user: *"I am about to perform this operation on the [GROUP_NAME] project within the [SETTINGS_MODULE] database. Is this correct?"*
3.  **Do NOT proceed** until the user gives explicit approval.
4.  **Review Parameters**: Explicitly state your intended `--scale` (supercell size), `--layers` (slab thickness), and `--vacuum` parameters to ensure they are physically sound.

## Instructions

### 1. Ensure Group Exists
Before running HTVS scripts, ensure the project group exists using the MCP tool:
```python
mcp_htvs_create_group(
    settings_module="orgel",  # Maps to djangochem.settings.orgel
    group_name="my_project"
)
```

### 2. Prepare a Bulk ID Pickle
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
python .agents/skills/mat-htvs-cutcleansurface/scripts/cut_clean_surface.py \
    --group my_project \
    --bulk_pkl /path/to/bulk_ids.pkl \
    --MI 1 1 1 \
    --settings djangochem.settings.orgel
```

#### Parameters
| Flag | Required | Description |
|---|---|---|
| `--group` | ✅ | HTVS project group name |
| `--bulk_pkl` | ✅ | Pickle file of crystal IDs |
| `--MI` | * | Max Miller indices to sweep (e.g. `1 1 1` iterates over all irreducible valid combinations). Output guarantees single lowest layer-shift symmetry deduping recursively! Mutually exclusive with exact_mi, one is required. |
| `--exact_mi` | * | Exact Miller indices to cut (e.g., `'1,0,0' '1,1,1'`). Overrides `--MI` if provided. |
| `--settings` | ✅ | Django settings module |
| `--output_log`| ❌ | JSON file path to save created surface IDs |
| `--limit` | ❌ | Max number of crystals to process (default: 10000) |
| `--dry_run` | ❌ | Simulate without writing to DB |
| `--target_species`| ❌ | Filter resulting slabs to those natively exposing this element on their topmost surface (e.g., `Fe`) |
<<<<<<< HEAD
| `--slab_thickness` | ❌ | Minimum slab thickness in Angstroms (default: 10.0). Specifies the bulk-like region's depth. |
| `--vacuum` | ❌ | Vacuum thickness (Angstroms) surrounding the slab (default: 15.0) |
| `--supercell_min_length` | ❌ | Minimum distance between periodic images in Angstroms for auto-scaling (default: 10.0). |
| `--scale` | ❌ | Exact supercell scaling factors for a and b (e.g., `2 2`). Overrides auto-scaling if provided. |
=======
| `--layers` | ❌ | Minimum number of atomic layers in the sliced slab (default: 4) |
| `--vacuum` | ❌ | Vacuum thickness (Angstroms) surrounding the slab (default: 15.0) |
| `--scale` | ❌ | Supercell scaling factors for a and b (e.g., `2 2` or `3 3`). If omitted, auto-scales the primitive cell to at least ~5.0 Å wide. |
>>>>>>> origin/htvs
| `--rotation` | ❌ | Rotation angle in degrees for the supercell grid (default: 0.0) |

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
- **Environment**: All MCP tools invoked by this skill run inherently through the `htvs-agent` runtime via the gemini MCP maps.
- **Data ID Tracking**: Every tool execution will return structured data containing Database IDs for agentic tracking.
- **Dependencies**: Native MCP Server connection required; no standalone python wrappers are used.

## References
- J. Lunger et al., *npj Comput. Mater.*, 2024. [DOI](https://doi.org/10.1038/s41524-024-01273-y)
---

**Author:** Hoje Chun  
**Contact:** [GitHub @hojechun](https://github.com/hojechun)
