
# HTVS Workflow Example

This directory contains an example script demonstrating how to programmatically use the HTVS tools to submit VASP calculations.

## Files

- `run_workflow.py`: A complete Python script that:
    1.  Initializes HTVS handlers (`HTVSJobHandler`, `HTVSVaspHandler`, `HTVSDbHandler`).
    2.  Saves a structure to the HTVS database.
    3.  Generates VASP input details using Pymatgen sets (compatible with `omat`, `mp`, etc.).
    4.  Submits the job to the database.
    5.  Builds the job directory for the cluster.
    6.  (Simulated) Parses the results and queries the database.

## Prerequisites

- **Conda Environment**: You must run this in the `htvs-agent` environment.
  ```bash
  conda activate htvs-agent
  ```
- **Analysis/Database Node**: This script should be run on a node with access to the HTVS database (e.g., a login node or a workstation with DB tunnel).

## Configuration

The script uses default values for the `toy` database, but you can override them with environment variables or by modifying the script variables.

### Key Variables (in script)
- `SETTINGS_MODULE`: Django settings (default: `djangochem.settings.toy`).
- `GROUP_NAME`: The HTVS group/project name.
- `CONFIG_NAME`: The chemical configuration (e.g., `pbe_d3_paw_engrad_vasp`).
- `COMPUTE_PLATFORM`: The target cluster (e.g., `perlmutter`).

## Usage

Run the script directly from the root of the repository or from this directory:

```bash
# From repo root
python .agent/skills/htvs-vasp/examples/run_workflow.py
```

## How It Works

1.  **Structure Saving**: Uses `HTVSDbHandler.save_structures` (or `save_crystals`/`save_surfaces`) to ingest atoms into the `pgmols` app.
2.  **VASP Details**: Uses `HTVSVaspHandler` to map standard Pymatgen sets (`MPStaticSet`, `MatPESStaticSet`, etc.) to the HTVS `details` JSON format. This ensures that `INCAR` tags are correctly translated.
3.  **Job Request**: Uses `HTVSJobHandler.request_job` to create a `Job` entry in the `jobs` app, linking the config, group, and parent structure.
4.  **Job Build**: Uses `HTVSJobHandler.build_jobs` (wrapping the `buildjobs` management command) to write the actual inputs (`POSCAR`, `INCAR`, `KPOINTS`, `POTCAR`, `job.sh`) to the `HTVS_INBOX`.
