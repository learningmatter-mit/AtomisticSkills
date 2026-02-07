# Remote Job Submission with Atomate2 and Jobflow-Remote

This guide details how to set up and use remote job submission for high-throughput VASP calculations using `atomate2` and `jobflow-remote`.

## 1. Local Machine Setup

### 1.1 Install `jobflow-remote`

Configure your Conda environment (e.g., `base-agent`) and install `jobflow-remote`:

```bash
pip install jobflow-remote
```

### 1.2 Configure `jobflow-remote`

Create or edit `~/.config/jobflow-remote/jobflow_remote.yaml`. This file defines the remote workers and database connections.

Example `jobflow_remote.yaml` for NERSC Perlmutter:

```yaml
# ... (standard queues/jobstore config) ...

workers:
  perlmutter_worker:
    type: remote
    host: perlmutter-p1.nersc.gov
    user: <your_nersc_username>
    key_filename: ~/.ssh/nersc  # Path to SSH key
    scheduler_type: slurm
    resources:
      account: <your_repository> # e.g., m5068
      qos: regular
      time: "02:00:00"
      nodes: 1
      job_name: jf_remote
      scheduler_kwargs:
        constraint: cpu
      
    work_dir: /global/cfs/cdirs/<your_repository>/<user>/jobflow_runs
    
    # Pre-run commands to set up HPC environment
    pre_run: |
      module load vasp/6.4.2-cpu
      source /global/homes/b/<user>/anaconda3/bin/activate atomate2
      export ATOMATE2_CONFIG_FILE=~/.config/atomate2/config.yaml
```

**Note on Resources**:
- Use `time` instead of `walltime`.
- Use `qos` instead of `queue`.
- Ensure constraints (like `cpu`) are specified correctly for the partition.

### 1.3 SSH Configuration (`sshproxy`)

For NERSC, you must use `sshproxy` to generate short-lived SSH keys to bypass MFA for automated jobs.

1.  **Install `sshproxy`**: Download the binary appropriate for your architecture (e.g., `sshproxy-*-linux-aarch64.tar.gz`) and place it in your PATH.
2.  **Generate Keys**:
    ```bash
    sshproxy -u <your_username>
    ```
    This generates `~/.ssh/nersc` and `~/.ssh/nersc-cert.pub`.
3.  **Verify Setup**:
    ```bash
    ssh -i ~/.ssh/nersc <user>@perlmutter-p1.nersc.gov echo "Success"
    ```

### 1.4 Project Configuration

Define your project in `~/.jfremote/projects/<project_name>.yaml` or manage via `jf project` commands. The project configuration links your `jobflow-remote` setup to a specific database project.

## 2. HPC Side Setup (Perlmutter)

### 2.1 Dependencies

On the remote cluster (Perlmutter), you need:
1.  **Python Environment**: An environment with `atomate2` installed.
    ```bash
    module load python
    conda create -n atomate2 -c conda-forge atomate2
    conda activate atomate2
    ```
2.  **VASP**: Ensure VASP modules are available (`module load vasp/...`).

### 2.2 Configuration

1.  **Check `atomate2` Config**: Ensure `~/.config/atomate2/config.yaml` exists on the remote machine if you need custom settings (e.g., DB connection).
2.  **Database Access**: The remote jobs need access to the MongoDB.
    - If calculating at NERSC, you can typically use the internal NERSC MongoDB Service directly (if provisioned).
    - Alternatively, use SSH tunneling (handled by `jobflow-remote` automatically for the Runner, but the *jobs* running on compute nodes might need direct access or a forwarded port if they write to the DB during execution). *Note: `jobflow-remote` typically handles object transfer back to the DB via the Runner, but direct DB access from the compute job is preferred for large data or `atomate2`'s `JobStore` mode.*

## 3. Usage with MCP

The `materials_tools` MCP server provides `run_atomate2_vasp_calculation`.

### Arguments for Remote Execution

-   `execution_mode`: Defaults to `"remote"`. Set to `"local"` for local execution.
-   `remote_settings`: Optional dictionary. Defaults to:
    ```python
    {"project": "remote_perlmutter", "worker": "perlmutter_worker"}
    ```
    Override this to specify a different project or worker.

### Example Call

```python
# Uses default remote settings (Perlmutter)
result = run_atomate2_vasp_calculation(
    structures_path="/path/to/structures",
    output_dir="./research/remote_test"
)

# Custom remote settings
result = run_atomate2_vasp_calculation(
    structures_path="/path/to/structures",
    output_dir="./research/remote_custom",
    remote_settings={
        "project": "my_project",
        "worker": "my_worker"
    }
)
```

### SSHProxy Check

The MCP tool automatically checks if `sshproxy` keys (`~/.ssh/nersc`) exist when the worker name contains "perlmutter". If keys are missing, it will raise an error instructing you to run `sshproxy`.
