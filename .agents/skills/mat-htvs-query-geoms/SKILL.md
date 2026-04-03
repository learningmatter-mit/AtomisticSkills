---
name: mat-htvs-query-geoms
description: Query and extract crystal bulk structures or sliced surfaces from the HTVS database.
category: DB Query
---
# HTVS Query: Geometries

**Goal**: Retrieve model geometries (crystals and surfaces) associated with an HTVS project for visualization, analysis, or further processing.

## Guidelines

1. You **MUST** use the **`htvs_query_structures`** and **`htvs_get_structure`** MCP tools for structure retrieval.
2. Filter by `group_name`, `formula`, and `structure_type` ("crystal" or "surface").

## Examples

### Query Crystals
Retrieve crystal structures belonging to a specific project:
```python
results = htvs_query_structures(
    settings_module="orgel",
    group_name="my_project",
    structure_type="crystal",
    formula="LiFePO4"
)
```

### Query Surfaces
Retrieve slab structures with Miller indices:
```python
results = htvs_query_structures(
    settings_module="orgel",
    group_name="my_project",
    structure_type="surface"
)
```

### Get Detailed Atoms Data
Fetch full ASE-compatible Atoms metadata for a specific record ID:
```python
atoms_data = htvs_get_structure(
    settings_module="orgel",
    structure_id=123,
    structure_type="crystal"
)
```

## Options
- `group_name`: Required project group name.
- `formula`: Optional chemical formula filter.
- `structure_type`: "crystal" (default) or "surface".
- `settings_module`: Django settings module Choice (default "orgel").

**Author**: Hoje Chun
**Contact**: [GitHub @hojechun](https://github.com/hojechun)
