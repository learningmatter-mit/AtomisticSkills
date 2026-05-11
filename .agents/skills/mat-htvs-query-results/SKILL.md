---
name: mat-htvs-query-results
description: Query and extract final energies, forces, and calculation properties from completed DFT jobs in the HTVS database.
category: DB Query
---
# HTVS Query: Results

**Goal**: Extract high-fidelity labeled data from the Django HTVS database, perfect for MLIP fine-tuning workflows or thermodynamic analysis. 
This tool strictly queries `Calc` and subclass entries (e.g., `SinglePoint`, `Jacobian`).

## Configuration & Safety (CRITICAL)

Wait! HTVS operations directly interact with research databases. Before running any commands:
1.  **Expose the Context**: Explicitly state the `settings_module` and `group_name` you are about to use.
2.  **Request Confirmation**: Ask the user: *"I am about to perform this operation on the [GROUP_NAME] project within the [SETTINGS_MODULE] database. Is this correct?"*
3.  **Do NOT proceed** until the user gives explicit approval.

## Guidelines

1. You **MUST** use the **`htvs_query_results`** MCP tool to export data. 
2. Ensure you specify the correct `group_name` (and optionally `formula`).

## Example

### Query All Results in Group
```python
results = htvs_query_results(
    settings_module="orgel",
    group_name="my_project"
)
```

### Query Results by Formula
```python
results = htvs_query_results(
    settings_module="orgel",
    group_name="my_project",
    formula="LiFePO4"
)
```

### Query Results by Configuration
```python
results = htvs_query_results(
    settings_module="orgel",
    group_name="my_project",
    config_name="pbe_d3_opt_vasp"
)
```

## Options
- `group_name`: Required project group name.
- `formula`: Optional chemistry filter.
- `settings_module`: Django settings module Choice (default "orgel").
- `limit`: Max number of output entries.
- `config_name`: Filter by job config.

## Constraints
- **Environment**: All MCP tools invoked by this skill run inherently through the `htvs-agent` runtime via the gemini MCP maps.
- **Data ID Tracking**: Every tool execution will return structured data containing Database IDs for agentic tracking.
- **Dependencies**: Native MCP Server connection required; no standalone python wrappers are used.

**Author**: Hoje Chun
**Contact**: [GitHub @hojechun](https://github.com/hojechun)
