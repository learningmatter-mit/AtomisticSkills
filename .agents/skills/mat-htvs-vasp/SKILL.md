---
name: htvs-vasp-jobs
description: Submit DFT jobs using VASP to the High-Throughput Virtual Screening (HTVS) system.
---

# HTVS VASP Jobs Skill

**Goal**: Submit crystal structures (e.g., xyz/cif) to the HTVS system for DFT calculations using VASP.

## When to use HTVS

Use the HTVS tools (`htvs_server` MCP tools, the included scripts, or the utility functions in `src/utils/htvs`) when:
1.  **DFT Labeling**: You need to calculate energy, forces, or stress for a structure using DFT (VASP).
2.  **Save to Database**: Save DFT results to the database.
3.  **Monitor Jobs**: Monitor running jobs in the cluster.

## Configuration & Safety (CRITICAL)

<<<<<<< HEAD
Wait! HTVS operations directly interact with research databases and computing clusters. Before running any commands:
1.  **Expose the Context**: Explicitly state the `settings_module`, `group_name`, `inbox_path`, `completed_path`, `compute_platform`, and `requester` you are about to use.
2.  **Expose Job Details**: Explicitly show the user the final, generated `job_details` (including VASP INCAR parameters like `preset_type`, `ISIF`, `NSW`, `LDAUU`, etc.) that will be applied.
3.  **Request Confirmation**: Ask the user: *"I am about to perform this operation with the above DB settings and INCAR parameters. Is this correct?"*
4.  **Do NOT proceed** with execution (like `submit_jobs.py` or `autopilot`) until the user gives explicit approval.
=======
Wait! HTVS operations directly interact with research databases. Before running any commands:
1.  **Expose the Context**: Explicitly state the `settings_module` and `group_name` you are about to use.
2.  **Request Confirmation**: Ask the user: *"I am about to perform this operation on the [GROUP_NAME] project within the [SETTINGS_MODULE] database. Is this correct?"*
3.  **Do NOT proceed** until the user gives explicit approval.
>>>>>>> origin/htvs

## Workflow

> **Note**: The HTVS MCP tools use a modular utility structure (`src/utils/htvs/`) with class-based handlers:
> - `HTVSJobHandler`: Job lifecycle (request, build, parse)
> - `HTVSVaspHandler`: VASP input generation
> - `HTVSDbHandler`: Database operations (save structures, create groups)
> 
> **CRITICAL AGENT INSTRUCTION**: Do not write temporary `python` scripts to perform these steps. Use the native `mcp_htvs_*` tool APIs provided to you directly in-memory, parse the JSON outputs, and chain them to the next MCP tools.
> **ID Tracking Requirement**: Tools that create database records (e.g., `mcp_htvs_request_job` or `mcp_save_htvs_structure`) automatically log their results and IDs to tracking JSON files (e.g., `htvs_request_job_tracking.json`) in the active research directory. You no longer need to write manual scripts for this purpose. Use the **`mat-htvs-monitor-db`** skill to track progress and parse results.

### 1. Gather Mandatory Inputs
The HTVS operations are driven by global project parameters. These are loaded directly from `~/.atomistic_skills.yaml` to ensure reproducibility across agent sessions. 

Before proceeding, **STOP** and ensure these variables are defined in the user's `~/.atomistic_skills.yaml` file. If they are missing, ask the user to configure them and verify:

- **Settings Module** (`settings_module`): Django Settings Module (e.g., `djangochem.settings.orgel`). 
- **Group Name** (`group_name`): HTVS Group/Project Name (e.g., `agent`). 
- **Chemical Config** (`chem_config`): VASP calculation protocol (e.g., `pbe_d3_paw_opt_vasp`). *(Passed via Tool argument)*
- **Compute Platform** (`compute_platform`): Cluster Name (e.g., `supercloud`, `perlmutter`). 
- **Requester** (`requester`): User ID (e.g., `hojechun`).
- **Inbox Path** (`inbox_path`): Directory where job folders are created.
- **Potcar Path** (`potcar_path`): Absolute path to the POTCAR files in the cluster.
- **Project Name** (`project_name`): Compute project account (e.g., `m5068`).
- **Completed Path** (`completed_path`): Directory where finished results are stored.

*Note: All HTVS MCP Tools will automatically pull these values directly from the YAML config. You do not need to use `htvs_set_project_context` if these are defined globally.*

### Configuration & Logging

Whenever you use this skill, you **MUST**:
1. Explicitly **tell the user** the above HTVS configuration parameters in your response.
2. **Ask the user** if they want to change any of these settings before proceeding.
3. Once confirmed, **log the configuration** for the run into the research plan or task artifact.

### 2. Verify Prerequisites
- **Check Group**: Ensure the `group_name` exists. Use the `htvs_create_group` MCP tool to create if needed:
  ```python
  mcp_htvs_create_group(
      settings_module="orgel",
      group_name="my_group"
  )
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

<<<<<<< HEAD
### 4. Step-Specific Configuration (vasp_steps)

For workflow transparency, VASP INCAR settings and cluster parameters must be centrally managed in `~/.atomistic_skills.yaml`. This ensures that there are no "hidden defaults" during generation and provides a single source of truth for the entire workflow.

1. **Configure** `~/.atomistic_skills.yaml` to include your VASP workflow parameters under the `vasp_steps` block:
```yaml
# Global settings
compute_platform: perlmutter_cpu
project_name: m5068
requester: hojechun

# Step-specific VASP settings
vasp_steps:
  pbe_u_paw_spinpol_opt_surf_vasp:
    preset_type: omat
    calculation_type: relaxation
    custom_settings:
      ENCUT: 520
      ISIF: 2
      NSW: 200
      LDAUU: 
        Fe: 4.3
        O: 0
        H: 0
```
*Note: Available presets include `mp`, `omat`, `matpes-pbe`, and `matpes-r2scan`. The presets inject specific Pymatgen `DictSet` defaults before your `custom_settings` are applied.*

2. **Preview**: If you are using the `submit_jobs.py` script instead of MCP tools, you must preview the fully resolved INCAR parameters (including presets) before actual submission using the `--preview_incar` flag. Since the settings are globally accessible, you do not need to pass a separate config file argument:
```bash
conda run -n htvs-agent python .agents/skills/mat-htvs-vasp/scripts/submit_jobs.py --chem_config pbe_u_paw_spinpol_opt_surf_vasp --preview_incar
```

3. **Confirm**: Show the previewed INCAR defaults and the YAML configuration to the user and request explicit confirmation.

### 5. Submit Jobs

Use the **`htvs_request_job`** or **`htvs_request_followup_job`** MCP tools (passing the settings parsed from the confirmed JSON file), OR use the `submit_jobs.py` script:

```python
# 1. Parse your JSON configuration and pass custom_settings to generate details
details_json = prepare_vasp_job_details(
    structure_file="structure.cif",
    preset_type=parsed_config["preset_type"],
    calculation_type=parsed_config["calculation_type"],
    custom_settings=parsed_config["custom_settings"],
    magnetism=True
)

# 2. Update with global settings
details = json.loads(details_json)
details.update(global_settings)

# 3. Request job via MCP tool
=======
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
>>>>>>> origin/htvs
htvs_request_job(
    settings_module="orgel",
    group_name="agent",
    chem_config="pbe_d3_paw_opt_vasp",
    details=details
)

<<<<<<< HEAD
# 4. Request follow-up (e.g. Static after Relaxation)
=======
# 3. Request follow-up (e.g. Static after Relaxation)
>>>>>>> origin/htvs
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
- **Data ID Tracking**: Every tool or script execution that creates database records MUST output a JSON block with the related Database IDs for agentic tracking.
- **Structure files** must be readable by `ase.io`.

## Files
- [SKILL.md](SKILL.md): This documentation.
- [chemconfig-standards.md](chemconfig-standards.md): Detailed HTVS configuration standards and naming conventions.
- [src/mcp_server/htvs_server.py](file:///home/hojechun/ssd_mnt/repos/AtomisticSkills/src/mcp_server/htvs_server.py): The primary interface for all HTVS operations.

**Author**: Hoje Chun
**Contact**: [GitHub @hojechun](https://github.com/hojechun)
