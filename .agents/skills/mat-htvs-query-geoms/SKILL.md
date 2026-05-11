---
name: mat-htvs-query-geoms
description: Query and extract crystal bulk structures or sliced surfaces from the HTVS database.
category: DB Query
---
# HTVS Query: Geometries

**Goal**: Retrieve model geometries (crystals and surfaces) associated with an HTVS project for visualization, analysis, or further processing.

## Configuration & Safety (CRITICAL)

Wait! HTVS operations directly interact with research databases. Before running any commands:
1.  **Expose the Context**: Explicitly state the `settings_module` and `group_name` you are about to use.
2.  **Request Confirmation**: Ask the user: *"I am about to perform this operation on the [GROUP_NAME] project within the [SETTINGS_MODULE] database. Is this correct?"*
3.  **Do NOT proceed** until the user gives explicit approval.

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

## Constraints
- **Environment**: All MCP tools invoked by this skill run inherently through the `htvs-agent` runtime via the gemini MCP maps.
- **Data ID Tracking**: Every tool execution will return structured data containing Database IDs for agentic tracking.
- **Dependencies**: Native MCP Server connection required; no standalone python wrappers are used.

**Author**: Hoje Chun
**Contact**: [GitHub @hojechun](https://github.com/hojechun)
