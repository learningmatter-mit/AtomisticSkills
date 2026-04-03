---
name: mat-htvs-query-jobs
description: Check the status, timing, and errors of submitted VASP jobs in the HTVS queue.
category: DB Query
---
# HTVS Query: Jobs

**Goal**: Monitor the progress of submitted DFT calculations, find job IDs, and check for specific pipeline states (e.g., "done", "error", "claimed").

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

**Author**: Hoje Chun
**Contact**: [GitHub @hojechun](https://github.com/hojechun)