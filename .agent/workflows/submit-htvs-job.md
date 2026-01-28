---
description: How to submit a DFT job via HTVS with mandatory manual inputs
---

# HTVS Job Submission Workflow

This workflow guides you through submitting a DFT job using the HTVS tools, ensuring all critical metadata (Database, Group, Cluster, Requester) is explicitly handled.

## 1. Gather Mandatory Inputs
**Before** running any tools, you must identify and confirm the following parameters with the user or from the context:

1.  **Database Name** (`settings_module`):
    -   Example: `djangochem.settings.orgel` (Default), `djangochem.settings.toy`
    -   *Action*: Confirm which database to use.

2.  **Group Name** (`project_name`):
    -   Example: `HighEntropyAlloys`, `testing`, `agent`
    -   *Action*: Use `list_htvs_configs` or `query_htvs_structures` (or just `create_htvs_group`) to verify it exists.

3.  **Cluster Name** (`compute_platform`):
    -   Example: `supercloud`, `engaging`, `perlmutter`
    -   *Action*: Ensure the chosen `chem_config` supports this cluster (use `inspect_chem_config` if unsure).

4.  **Requester Name** (`requester`):
    -   Example: `hojechun`
    -   *Action*: Must be provided to `request_htvs_job`.

## 2. Verify Prerequisites
1.  **Check Group**:
    -   If the group might not exist, run `create_htvs_group(group_name=GROUP_NAME, ...)` to ensure it does.

2.  **Check Config & Cluster**:
    -   If using a new chem_config, run `inspect_chem_config(config_name=CHEM_CONFIG)` to verify it supports the chosen `compute_platform`.

## 3. Prepare Job Details
1.  Construct the `details` dictionary.
2.  **MANDATORY**: Include `compute_platform` in the details.
    ```json
    {
      "priority": 50,
      "compute_platform": "CLUSTER_NAME",
      "kppa": 4000
    }
    ```

## 4. Execute Job Request
Run `request_htvs_job`:
```python
request_htvs_job(
    project_name=GROUP_NAME,
    chem_config=CHEM_CONFIG,
    details={...},
    requester=REQUESTER_NAME,
    settings_module=DATABASE_SETTINGS
)
```

## 5. Build Job
Run `build_htvs_job`:
```python
build_htvs_job(
    project_name=GROUP_NAME,
    inbox_path="inbox",  # Default
    settings_module=DATABASE_SETTINGS
)
```
