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

## Workflow

The standard workflow for running a DFT job via HTVS is:

1.  **Prepare Details**: Convert VASP settings to HTVS `details` format.
    -   Use `vasp_to_htvs_details(vasp_input, ...)` tool.
    -   Map standard tags (`ENCUT`, `ISPIN`, etc.) to the `details` dictionary.


2.  **Request Job**: Create a job entry in the database.
    -   Use `request_htvs_job` tool.
    -   **Critical Arguments**:
        -   `settings_module`: Specifies the Database Name (e.g., `djangochem.settings.orgel`). Check with user if unsure.
        -   `project_name`: Specifies the Group Name (e.g., `HighEntropyAlloys`). Must exist in DB.
        -   `requester`: Specifies the Requester Name (e.g., `hojechun`).
        -   `details['compute_platform']`: Specifies the Cluster Name (e.g., `supercloud`, `perlmutter`). MANDATORY.
    -   **Chem Config**: Select the appropriate configuration (see selection guide below).

3.  **Build Job**: Create the job files.
    -   Use `build_htvs_job(project_name, inbox_path, ...)` tool.
    -   **Inbox Path**: Defaults to `HTVS_JOB_ROOT/inbox`.

4.  **Parse Job**: (After completion) Retrieve results.
    -   Use `parse_htvs_job(project_name, completed_path, ...)` tool.

## Chemical Configuration Selection

Select the `chem_config` based on the material type and desired accuracy:

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

*Note: If unsure, `pbe_d3_paw_bomd_vasp` is a safe default for most MLIP training data generation tasks.*

## Configuration Details

When invoking `request_htvs_job`, ensure the `details` dictionary includes:
-   `priority`: Integer (default 50). Higher is better.
-   `compute_platform`: Target cluster (e.g., `supercloud`, `engaging`, `perlmutter`). **Ask user if unknown.**
-   `kppa` or `kpoints`: K-point density.
-   `encut`: Plane wave cutoff.