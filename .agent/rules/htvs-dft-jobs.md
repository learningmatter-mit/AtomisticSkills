---
trigger: model_decision
description: Guidelines for using HTVS tools for DFT calculations and data generation
---

# HTVS Usage Rules

You are an expert in using the High-Throughput Virtual Screening (HTVS) tools (`htvs` library) for performing DFT calculations. Use this guide when the user requests DFT calculations, ground truth labeling, or dataset generation.

## When to use HTVS

Use the HTVS tools (`htvs_server`) when:
1.  **DFT Labeling**: You need to calculate energy, forces, or stress for a structure using DFT (VASP).
2.  **Dataset Generation**: You need to generate a training dataset for an MLIP.
3.  **HPC Execution**: The calculations need to run on a cluster (Slurm, Torque) rather than locally.

## Research Planning

For every HTVS-based research task, you MUST create a **[Research Plan](file:///home/hojechun/ssd_mnt/repos/simulation_mcp/.agent/workflows/research-plan-template.md)** and get user approval via `notify_user` before proceeding. 

The research plan should include:
- **Objective**: Run DFT calculations using HTVS.
- **HTVS Parameters**: `group_name`, `chem_config`, `compute_platform`, `inbox_path`, `requester`, `parent_config`, `settings_module`, `details`, `complete_path`.

## Workflow

The standard workflow for running a DFT job via HTVS is:

1.  **Mandatory Variable Verification**: **STOP** and ask the user to confirm the following variables. **DO NOT** assume defaults.
    -   `database_name`: Django Settings Module (e.g., `djangochem.settings.orgel`).
    -   `import_config_name`: Job Config Name for imported structures (e.g., `parsed`).
    -   `project_name`: Group Name (e.g., `agent`).
    -   `chem_config`: Chemical Config (e.g., `pbe_d3_paw_opt_vasp`).
    -   `compute_platform`: Cluster Name (e.g., `supercloud`, `perlmutter`).
    -   `requester`: User ID (e.g., `hojechun`).

2.  **Script Implementation Rules**:
    -   **Configurable Scripts**: Any Python script you write MUST use `argparse` (or similar) for the variables above. **NEVER** hardcode them.
    -   **Environment Setup**: Explicitly handle Django setup with `try/except` imports or `sys.path` appending using the `htvs_repo` variable.

3.  **Prepare Details**: Convert VASP settings to HTVS `details` format.
    -   Use `vasp_to_htvs_details(vasp_input, ...)` tool.
    -   Map standard tags (`ENCUT`, `ISPIN`, etc.) to the `details` dictionary.

4.  **Request Job**: Create a job entry in the database.
    -   Use `request_htvs_job` tool or your script.
    -   Ensure `details['compute_platform']` is set.

5.  **Build Job**: Create the job files.
    -   Use `build_htvs_job(project_name, inbox_path, ...)` tool or your script.
    -   **Inbox Path**: Use the `inbox_path` argument. This is now **MANDATORY**. You must determine the correct path (e.g., from `$HTVS_JOB_ROOT/inbox` or explicit user input) and pass it. The tool will no longer auto-detect defaults.

6.  **Parse Job**: (After completion) Retrieve results.
    -   Use `parse_htvs_job(project_name, completed_path, ...)` tool.

## Chemical Configuration Selection

Select the `chem_config` based on the material type and desired accuracy.
For a complete list of naming conventions and standard configurations, see `chemconfig-standards.md`.

### Inorganic Materials (Bulk, Surfaces)
-   **Standard Relaxation**: `pbe_d3_paw_opt_vasp` or `pbe_paw_opt_vasp` (PBE + optional D3).
-   **Static/Energy**: `pbe_d3_paw_engrad_vasp` or `pbe_paw_engrad_vasp` (Single point energy/forces).
-   **Accurate**: `r2scan_paw_opt_vasp` (r2SCAN meta-GGA relaxation).
-   **MD**: `pbe_d3_paw_bomd_vasp` (Born-Oppenheimer MD).
-   **NEB**: `pbe_d3_paw_neb_vasp` (Nudged Elastic Band).
-   **Spin Polarized**: Use `*spinpol*` variants (e.g., `pbe_u_paw_spinpol_opt_vasp`) for magnetic systems.

### Organic / Molecules
-   **Relaxation**: `pbe_d3_paw_opt_vasp` (Standard).
-   **MD**: `pbe_d3_paw_bomd_vasp`.

*Note: If unsure, `pbe_d3_paw_engrad_vasp` is a safe default for most MLIP training data generation tasks.*

## Configuration Details

When invoking `request_htvs_job`, ensure the `details` dictionary includes:
-   `priority`: Integer (default 50). Higher is better.
-   `compute_platform`: Target cluster (e.g., `supercloud`, `engaging`, `perlmutter`). **Ask user if unknown.**
-   `kppa` or `kpoints`: K-point density.
-   `encut`: Plane wave cutoff.