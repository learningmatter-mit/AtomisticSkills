---
name: htvs-submission
description: Submit DFT jobs to the High-Throughput Virtual Screening (HTVS) system.
---

# HTVS Submission Skill

**Goal**: Batch submit crystal structures (xyz/cif) to the HTVS system for DFT calculations.

**Instructions**:
1.  **Verify Inputs**: Before running, ensure you have the correct:
    -   `Group Name` (HTVS Project)
    -   `Comput Platform` (Cluster)
    -   `Chem Config` (VASP settings)
    -   `Requester` (User ID)
    -   `Settings Module` (Django DB settings)

2.  **Run Script**: Use the `submit_jobs.py` script in the `scripts/` directory.
    -   **Environment**: `htvs-agent`
    -   **Command**:
        ```bash
        /path/to/htvs-agent/python scripts/submit_jobs.py \
            --structure_dir /path/to/structures \
            --group_name "MyProject" \
            --chem_config "pbe_d3_paw_opt_vasp" \
            --compute_platform "supercloud" \
            --requester "username" \
            --settings_module "djangochem.settings.orgel" \
            --inbox_path "/path/to/inbox"
        ```


3.  **Parse Jobs**: Once calculations are finished, use the `parse_jobs.py` script.
    -   **Command**:
        ```bash
        /path/to/htvs-agent/python scripts/parse_jobs.py \
            --group_name "MyProject" \
            --completed_path "/path/to/completed" \
            --settings_module "djangochem.settings.orgel" \
            --config_name "pbe_d3_paw_opt_vasp"
        ```

**Constraints**:
-   Must be run in an environment with access to the HTVS database and Django settings.
-   Structure files must be readable by `ase.io`.
-   The Project/Group must be accessible to the user.

**Files**:
-   [submit_jobs.py](scripts/submit_jobs.py): The main submission logic.
-   [parse_jobs.py](scripts/parse_jobs.py): Parsing completed jobs into the database.
-   [monitor_jobs.py](scripts/monitor_jobs.py): Monitor job status and optionally parse.
