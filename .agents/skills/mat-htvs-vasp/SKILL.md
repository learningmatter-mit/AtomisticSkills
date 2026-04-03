---
name: htvs-submission
description: Submit DFT jobs using VASP to the High-Throughput Virtual Screening (HTVS) system.
---

# HTVS Submission Skill

**Goal**: Submit crystal structures (e.g., xyz/cif) to the HTVS system for DFT calculations using VASP.

## When to use HTVS

Use the HTVS tools (`htvs_server` MCP tools, the included scripts, or the utility functions in `src/utils/htvs`) when:
1.  **DFT Labeling**: You need to calculate energy, forces, or stress for a structure using DFT (VASP).
2.  **Save to Database**: Save DFT results to the database.
3.  **Monitor Jobs**: Monitor running jobs in the cluster.

## Research Planning

For every HTVS-based research task, you **MUST** create a Research Plan and get user approval via `notify_user` before proceeding. 

The research plan should include:
- **Objective**: Detailed goal (e.g., ground truth labeling for Pt bulk).
- **HTVS Parameters**: `group_name`, `chem_config`, `compute_platform`, `inbox_path`, `requester`, `settings_module`, `potcar_path`, `completed_path`.

## Workflow

> **Note**: The HTVS MCP tools use a modular utility structure (`src/utils/htvs/`) with class-based handlers:
> - `HTVSJobHandler`: Job lifecycle (request, build, parse)
> - `HTVSVaspHandler`: VASP input generation
> - `HTVSDbHandler`: Database operations (save structures, create groups)

### 1. Gather Mandatory Inputs
**STOP** and ask the user to confirm the following variables. **DO NOT** assume defaults.

- **Settings Module** (`settings_module`): Django Settings Module (e.g., `djangochem.settings.orgel`). **MANDATORY**.
- **Group Name** (`group_name`): HTVS Group/Project Name (e.g., `agent`). **MANDATORY**.
- **Chemical Config** (`chem_config`): VASP calculation protocol (e.g., `pbe_d3_paw_opt_vasp`).
- **Compute Platform** (`compute_platform`): Cluster Name (e.g., `supercloud`, `perlmutter`). **MANDATORY**.
- **Requester** (`requester`): User ID (e.g., `hojechun`). **MANDATORY**.
- **Inbox Path** (`inbox_path`): Directory where job folders are created. **MANDATORY**.
- **Potcar Path** (`potcar_path`): Path to the POTCAR files. This should be the absolute path to the directory containing the POTCAR files in the cluster. **MANDATORY**.
- **Project Name** (`project_name`): Compute project account (e.g., `m5068`). **MANDATORY for Perlmutter**.
- **Completed Path** (`completed_path`): Directory where finished results are stored.

### 2. Verify Prerequisites
- **Check Group**: Ensure the `group_name` exists. Use `HTVSDbHandler` to create if needed:
  ```python
  from src.utils.htvs import HTVSDbHandler
  handler = HTVSDbHandler("djangochem.settings.orgel")
  handler.create_group("my_group")
  ```
- **Check Config**: Verify the `chem_config` supports the chosen `compute_platform` (e.g. via `HTVSConfigHandler.inspect_chemconfig`).
- **Check Potcar Path**: Verify the `potcar_path` is valid and accessible.
- **Check Inbox Path**: Verify the `inbox_path` is valid and accessible.

### 3. Save Structures to Database

Use the **`save_htvs_structure`** MCP tool:

```python
save_htvs_structure(
    structure_file="/path/to/structure.cif",
    config_name="agent_generated",
    group_name="agent",
    settings_module="orgel",
    structure_type="auto"  # Auto-detects Crystal vs Surface
)
```

### 4. Prepare Job Details

Use the **`prepare_vasp_job_details`** MCP tool to generate standard VASP parameters:

```python
details_json = prepare_vasp_job_details(
    structure_file="structure.cif",
    preset_type="mp",          # or "omat", "matpes-pbe", "matpes-r2scan"
    calculation_type="static",  # or "relaxation"
    magnetism=True,
    magnetism_scheme="fm"       # or "afm", "nm"
)
```

### 5. Submit Jobs

Use the **`htvs_request_job`** or **`htvs_request_followup_job`** MCP tools:

```python
# 1. Generate details
details = json.loads(details_json)
details.update({
    "compute_platform": "perlmutter",
    "pseudo_dir": "/path/to/potcar",
    "requester": "hojechun",
    "project_name": "m5068"
})

# 2. Request job via MCP tool
htvs_request_job(
    settings_module="orgel",
    group_name="agent",
    chem_config="pbe_d3_paw_opt_vasp",
    details=details
)

# 3. Request follow-up (e.g. Static after Relaxation)
htvs_request_followup_job(
    settings_module="orgel",
    group_name="agent",
    chem_config="pbe_d3_paw_static_vasp",
    parent_job_pks=[123], # PK of finalized relaxation job
    details=static_details
)
```

### 6. Build and Parse Jobs

Use the **`htvs_build_jobs`** and **`htvs_parse_jobs`** MCP tools:

```python
# Build jobs into inbox
htvs_build_jobs(
    settings_module="orgel",
    group_name="agent",
    inbox_path="/path/to/inbox",
    compute_platform="perlmutter"
)

# Parse completed jobs into database
htvs_parse_jobs(
    settings_module="orgel",
    group_name="agent",
    completed_path="/path/to/completed"
)
```

### 7. Fetching Results from DB

Use the **`htvs_query_results`**, **`htvs_query_structures`**, or **`htvs_get_structure`** MCP tools:

```python
# Query results for a group
results = htvs_query_results(
    settings_module="orgel",
    group_name="agent",
    formula="LiFePO4"
)

# Find structures by formula
structures = htvs_query_structures(
    settings_module="orgel",
    group_name="agent",
    formula="LiFePO4",
    structure_type="crystal"
)

# Get ASE-compatible atoms data for a specific record
atoms_json = htvs_get_structure(
    settings_module="orgel",
    structure_id=456,
    structure_type="crystal"
)
```

## Chemical Configuration Selection

Select the `chem_config` based on the material type and desired accuracy. For detailed naming conventions and standards, see [chemconfig-standards.md](chemconfig-standards.md).

### Inorganic Materials (Bulk)
- **Standard Relaxation**: `pbe_d3_paw_opt_vasp` (PBE+D3).
- **Static/Energy**: `pbe_d3_paw_engrad_vasp` (Single point energy/forces).
- **Accurate**: `r2scan_paw_opt_vasp` (r2SCAN relaxation).
- **MD**: `pbe_d3_paw_bomd_vasp`.

### Surfaces
- **Standard Relaxation**: `pbe_u_paw_spinpol_opt_surf_vasp` (PBE+U).
- **Static/Energy**: `pbe_u_paw_spinpol_opt_surf_vasp` (Single point energy/forces). Ensure NSW = 0.
- **MD**: `pbe_d3_paw_bomd_vasp`.

### Organic / Molecules
- **Relaxation**: `pbe_d3_paw_opt_vasp`.
- **MD**: `pbe_d3_paw_bomd_vasp`.

*Note: For MLIP training labels, `pbe_d3_paw_engrad_vasp` is often the standard choice.*

## Constraints
- **Environments**: All MCP tools and scripts require the **htvs-agent** conda environment.
- **Structure files** must be readable by `ase.io`.

## Files
- [SKILL.md](SKILL.md): This documentation.
- [chemconfig-standards.md](chemconfig-standards.md): Detailed HTVS configuration standards and naming conventions.
- [src/mcp_server/htvs_server.py](file:///home/hojechun/ssd_mnt/repos/AtomisticSkills/src/mcp_server/htvs_server.py): The primary interface for all HTVS operations.


