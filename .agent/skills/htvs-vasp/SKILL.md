---
name: htvs-submission
description: Submit DFT jobs using VASP to the High-Throughput Virtual Screening (HTVS) system.
---

# HTVS Submission Skill

**Goal**: Submit crystal structures (e.g., xyz/cif) to the HTVS system for DFT calculations using VASP.

## When to use HTVS

Use the HTVS tools (`htvs_server` MCP tools or the included scripts) when:
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

Use the `save_htvs_structure` MCP tool or `HTVSDbHandler`:

**Using MCP tool:**
```python
save_htvs_structure(
    structure_file="/path/to/structure.cif",
    config_name="agent_generated",
    group_name="agent",
    settings_module="djangochem.settings.orgel",
    structure_type="auto"  # Auto-detects Crystal vs Surface
)
```

**Using HTVSDbHandler:**
```python
from src.utils.htvs import HTVSDbHandler

handler = HTVSDbHandler("djangochem.settings.orgel")

# Batch save from directory
result = handler.save_structures(
    structure_path="./structures",
    config_name="agent_generated",
    group_name="agent"
)
```

### 4. Prepare Job Details

Use the **`prepare_vasp_job_details`** MCP tool to generate standard VASP parameters:

```python
details_json = prepare_vasp_job_details(
    structure_file="structure.cif",
    preset_type="omat",  # or "mp", "matpes-pbe", "matpes-r2scan"
    calculation_type="static",  # or "relaxation"
    custom_settings=None,
    magnetism=True
)
```

Then add mandatory platform-specific fields:
```json
{
  "priority": 50,
  "compute_platform": "supercloud",
  "pseudo_dir": "/path/to/potcar",
  "requester": "hojechun"
}
```

### 5. Submit Jobs & Build

Use `HTVSJobHandler` directly for job operations:

```python
from src.utils.htvs import HTVSJobHandler, HTVSVaspHandler

#Initialize handlers
job_handler = HTVSJobHandler("djangochem.settings.orgel")
vasp_handler = HTVSVaspHandler()

# Generate VASP details
details_json = vasp_handler.generate_details(
    structure_file="structure.cif",
    preset_type="omat",
    calculation_type="static",
    magnetism=True
)
details = json.loads(details_json)

# Add platform-specific settings
details.update({
    "compute_platform": "perlmutter",
    "pseudo_dir": "/path/to/potcar",
    "requester": "hojechun",
    "project_name": "m5068"
})

# Request jobs
result = job_handler.request_job(
    group_name="agent",
    chem_config="pbe_d3_paw_opt_vasp",
    details=details,
    requester="hojechun"
)

# Build jobs
result = job_handler.build_jobs(
    group_name="agent",
    inbox_path="/path/to/inbox",
    config_name="pbe_d3_paw_opt_vasp",
    compute_platform="perlmutter"
)
```

**Or use submit_jobs.py script** for convenience:
```bash
python scripts/submit_jobs.py \
    --group_name "agent" \
    --chem_config "pbe_d3_paw_opt_vasp" \
    --parent_config "agent_generated" \
    --compute_platform "perlmutter" \
    --requester "hojechun" \
    --settings_module "djangochem.settings.orgel" \
    --inbox_path "/path/to/inbox" \
    --project_name "m5068" \
    --potcar_path "/path/to/potcar" \
    --preset_type "omat" \
    --calculation_type "static"
```

### 6. Monitor Job Status
Before parsing, ensure jobs are complete. Use the `monitor_jobs.py` script:

```bash
python scripts/monitor_jobs.py \
    --tracking_file job_tracking.json \
    --completed_path "/path/to/completed"
```

### 7. Parse Jobs

Use `HTVSJobHandler` directly:

```python
from src.utils.htvs import HTVSJobHandler

handler = HTVSJobHandler("djangochem.settings.orgel")
result = handler.parse_jobs(
    group_name="agent",
    completed_path="/path/to/completed",
    config_name="pbe_d3_paw_opt_vasp"
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


### 8. Fetching Results from DB

After parsing, retrieve results (energies, structures) directly from the database using a custom script via `run_htvs_script` or `HTVSDbHandler`.

See the example script for a complete query template.

## Example Workflow

A complete, runnable example of the pipeline (Save -> Submit -> Build -> Parse -> Query) is available in:
- [examples/run_workflow.py](examples/run_workflow.py)

To run the example:
```bash
python .agent/skills/htvs-vasp/examples/run_workflow.py
```

## Constraints
- **Environments**: All scripts require the **htvs-agent** conda environment.
- **Structure files** must be readable by `ase.io`.

## Files
- [SKILL.md](SKILL.md): This documentation.
- [chemconfig-standards.md](chemconfig-standards.md): Detailed HTVS configuration standards and naming conventions.
- [submit_jobs.py](scripts/submit_jobs.py): Submit jobs using HTVSJobHandler and HTVSVaspHandler.
- [monitor_jobs.py](scripts/monitor_jobs.py): Status tracking.
- [examples/run_workflow.py](examples/run_workflow.py): Full Python workflow example.


