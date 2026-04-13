---
name: mat-htvs-query-jobs
description: Check the status, timing, and errors of submitted VASP jobs in the HTVS queue.
category: DB Query
---
# HTVS Query: Jobs

**Goal**: Monitor the progress of submitted DFT calculations, find job IDs, and check for specific pipeline states (e.g., "done", "error", "claimed").

## Configuration & Safety (CRITICAL)

Wait! HTVS operations directly interact with research databases. Before running any commands:
1.  **Expose the Context**: Explicitly state the `settings_module` and `group_name` you are about to use.
2.  **Request Confirmation**: Ask the user: *"I am about to perform this operation on the [GROUP_NAME] project within the [SETTINGS_MODULE] database. Is this correct?"*
3.  **Do NOT proceed** until the user gives explicit approval.

## Guidelines

1. You **MUST** use the **`htvs_query_jobs`** MCP tool to check job status.
2. The standard statuses are "claimed", "done", "error", "requested".

## Example

### Query All Jobs in Group
```python
jobs = htvs_query_jobs(
    settings_module="orgel",
    group_name="my_project"
)
```

### Query Failed Jobs
```python
failed_jobs = htvs_query_jobs(
    settings_module="orgel",
    group_name="my_project",
    status="error"
)
```

### Query Jobs by Configuration
```python
specific_jobs = htvs_query_jobs(
    settings_module="orgel",
    group_name="my_project",
    config_name="pbe_d3_opt_vasp"
)
```

## Options
- `group_name`: Required project group name.
- `status`: Filter exactly by string status ("error", "done", "claimed").
- `config_name`: Filter by applied job config (e.g. `pbe_d3_opt_vasp`).
- `settings_module`: Django settings module Choice (default "orgel").

## Constraints
- **Environment**: All MCP tools invoked by this skill run inherently through the `htvs-agent` runtime via the gemini MCP maps.
- **Data ID Tracking**: Every tool execution will return structured data containing Database IDs for agentic tracking.
- **Dependencies**: Native MCP Server connection required; no standalone python wrappers are used.

**Author**: Hoje Chun
**Contact**: [GitHub @hojechun](https://github.com/hojechun)