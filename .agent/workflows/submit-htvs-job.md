---
description: How to submit a DFT job via HTVS with mandatory manual inputs and parse the outputs to the DB
---

# HTVS Job Submission Workflow

This workflow guides you through submitting a DFT job using the HTVS tools, ensuring all critical metadata (Database, Group, Cluster, Requester) is explicitly handled.

## 1. Gather Mandatory Inputs
**Before** running any tools, you must identify and confirm the following parameters with the user or from the context:

1.  **Database Name** (`database_name` or `settings_module`):
    -   Example: `djangochem.settings.orgel` (Default), `djangochem.settings.toy`
    -   *Action*: Confirm which Django settings module to use.

2.  **Import Config Name** (`import_config_name`):
    -   Example: `parsed`
    -   *Action*: The name of the Job Config for imported structures.

3.  **Project Name** (`project_name` or `group_name`):
    -   Example: `agent`, `HighEntropyAlloys`
    -   *Action*: The group name for the project. Use `list_htvs_configs` or `query_htvs_structures` to verify it exists.

4.  **Chemical Config** (`chem_config`):
    -   Example: `pbe_d3_paw_opt_vasp`
    -   *Action*: The specific HTVS configuration for the calculation.

5.  **Compute Platform** (`compute_platform`):
    -   Example: `supercloud`, `perlmutter`
    -   *Action*: The cluster name where jobs will run. Ensure the chosen `chem_config` supports this cluster.

6.  **Requester** (`requester`):
    -   Example: `hojechun`
    -   *Action*: User ID of the person requesting the job.

7.  **Inbox Path** (`inbox_path`):
    -   Example: `inbox`, `/path/to/inbox`
    -   *Action*: The directory where job folders will be created. **Must be explicitly provided.**

8.  **Completed Path** (`completed_path`):
    -   Example: `completed`, `/path/to/completed`
    -   *Action*: The directory where finished job results are moved.

## 2. Verify Prerequisites
1.  **Check Group**:
    -   If the group might not exist, run `create_htvs_group(group_name=PROJECT_NAME, ...)` to ensure it does.

2.  **Check Config & Cluster**:
    -   If using a new chem_config, run `inspect_chem_config(config_name=CHEM_CONFIG)` to verify it supports the chosen `compute_platform`.

## 3. Prepare Job Details
1.  Construct the `details` dictionary.
2.  **MANDATORY**: Include `compute_platform` in the details.
    ```json
    {
      "priority": 50,
      "compute_platform": "COMPUTE_PLATFORM",
      "kppa": 4000
    }
    ```

## 4. Execute Job Request
Run `request_htvs_job`:
```python
request_htvs_job(
    group_name=PROJECT_NAME,
    chem_config=CHEM_CONFIG,
    details={...},
    requester=REQUESTER,
    settings_module=DATABASE_NAME
)
```

## 5. Build Job
Run `build_htvs_job`:
```python
build_htvs_job(
    group_name=PROJECT_NAME,
    inbox_path=INBOX_PATH,
    settings_module=DATABASE_NAME,
    compute_platform=COMPUTE_PLATFORM
)
```

## 6. Monitor Job Status
Before parsing, you must ensure the jobs are complete.

- **Option A: MCP Tool**
  ```python
  get_htvs_job_status(
      settings_module=DATABASE_NAME,
      group_name=PROJECT_NAME,
      limit=50
  )
  ```

- **Option B: Skill Script** (if tracking manually)
  ```bash
  /path/to/htvs-agent/python scripts/monitor_jobs.py \
      --tracking_file "path/to/job_tracking.json" \
      --completed_path COMPLETED_PATH
  ```

## 7. Parse Jobs
Once calculations are complete and results are in `completed_path`, parse them into the database.

- **Option A: MCP Tool**
  ```python
  parse_htvs_job(
      group_name=PROJECT_NAME,
      completed_path=COMPLETED_PATH,
      settings_module=DATABASE_NAME,
      config_name=CHEM_CONFIG
  )
  ```

- **Option B: Skill Script** (Batch Parsing)
  ```bash
  /path/to/htvs-agent/python scripts/parse_jobs.py \
      --group_name PROJECT_NAME \
      --completed_path COMPLETED_PATH \
      --settings_module DATABASE_NAME \
      --config_name CHEM_CONFIG
  ```