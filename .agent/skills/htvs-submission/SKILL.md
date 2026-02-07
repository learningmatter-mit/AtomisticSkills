---
name: htvs-submission
description: Submit DFT jobs to the High-Throughput Virtual Screening (HTVS) system.
---

# HTVS Submission Skill

**Goal**: Batch submit crystal structures (e.g., xyz/cif) to the HTVS system for DFT calculations.

## When to use HTVS

Use the HTVS tools (`htvs_server` or the included scripts) when:
1.  **DFT Labeling**: You need to calculate energy, forces, or stress for a structure using DFT (VASP).
2.  **Dataset Generation**: You need to generate a training dataset for an MLIP.
3.  **HPC Execution**: The calculations need to run on a cluster (Slurm, Torque) rather than locally.

## Research Planning

For every HTVS-based research task, you **MUST** create a Research Plan and get user approval via `notify_user` before proceeding. 

The research plan should include:
- **Objective**: Detailed goal (e.g., ground truth labeling for Pt bulk).
- **HTVS Parameters**: `group_name`, `chem_config`, `compute_platform`, `inbox_path`, `requester`, `settings_module`, `details`, `completed_path`.

## Workflow

### 1. Gather Mandatory Inputs
**STOP** and ask the user to confirm the following variables. **DO NOT** assume defaults.

- **Settings Module** (`settings_module`): Django Settings Module (e.g., `djangochem.settings.orgel`).
- **Project Name** (`group_name`): HTVS Group/Project Name (e.g., `agent`).
- **Chemical Config** (`chem_config`): VASP calculation protocol (e.g., `pbe_d3_paw_opt_vasp`).
- **Compute Platform** (`compute_platform`): Cluster Name (e.g., `supercloud`, `perlmutter`).
- **Requester** (`requester`): User ID (e.g., `hojechun`).
- **Inbox Path** (`inbox_path`): Directory where job folders are created. **MANDATORY**.
- **Completed Path** (`completed_path`): Directory where finished results are stored.

### 2. Verify Prerequisites
- **Check Group**: Ensure the `group_name` exists using `create_htvs_group` if necessary.
- **Check Config**: Verify the `chem_config` supports the chosen `compute_platform` using `inspect_chem_config`.

### 3. Prepare Job Details
Convert VASP settings to HTVS `details` format. Use the `vasp_to_htvs_details(vasp_input, ...)` tool.
**MANDATORY**: Ensure `details['compute_platform']` is set.

Example `details`:
```json
{
  "priority": 50,
  "compute_platform": "supercloud",
  "kppa": 4000
}
```

### 4. Execute Job Request
Run `request_htvs_job` or the `submit_jobs.py` script.

**Using Script**:
```bash
/mnt/data0/hojechun/miniforge3/envs/htvs-agent/bin/python scripts/submit_jobs.py \
    --structure_dir /path/to/structures \
    --group_name "MyProject" \
    --chem_config "pbe_d3_paw_opt_vasp" \
    --compute_platform "supercloud" \
    --requester "username" \
    --settings_module "djangochem.settings.orgel" \
    --inbox_path "/path/to/inbox"
```

### 5. Build Job
Run `build_htvs_job`. This creates the actual file structure in the `inbox_path`.

### 6. Monitor Job Status
Before parsing, ensure jobs are complete. Use `get_htvs_job_status` or the `monitor_jobs.py` script.

### 7. Parse Jobs
Retrieve results into the database using `parse_htvs_job` or the `parse_jobs.py` script.

**Using Script**:
```bash
/mnt/data0/hojechun/miniforge3/envs/htvs-agent/bin/python scripts/parse_jobs.py \
    --group_name "MyProject" \
    --completed_path "/path/to/completed" \
    --settings_module "djangochem.settings.orgel" \
    --config_name "pbe_d3_paw_opt_vasp"
```

## Chemical Configuration Selection

### Inorganic Materials (Bulk, Surfaces)
- **Standard Relaxation**: `pbe_d3_paw_opt_vasp` (PBE+D3).
- **Static/Energy**: `pbe_d3_paw_engrad_vasp` (Single point energy/forces).
- **Accurate**: `r2scan_paw_opt_vasp` (r2SCAN relaxation).
- **MD**: `pbe_d3_paw_bomd_vasp`.

### Organic / Molecules
- **Relaxation**: `pbe_d3_paw_opt_vasp`.
- **MD**: `pbe_d3_paw_bomd_vasp`.

*Note: For MLIP training labels, `pbe_d3_paw_engrad_vasp` is often the standard choice.*

## Constraints
- **Environments**: All scripts require the **htvs-agent** conda environment.
- **Structure files** must be readable by `ase.io`.

## Files
- [submit_jobs.py](scripts/submit_jobs.py): Main submission logic.
- [parse_jobs.py](scripts/parse_jobs.py): Result retrieval.
- [monitor_jobs.py](scripts/monitor_jobs.py): Status tracking.
