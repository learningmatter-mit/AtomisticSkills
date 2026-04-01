# NERSC Perlmutter: Atomate2 & JobFlow Remote Setup

This document summarizes the configuration and operational steps for running Atomate2 workflows remotely on NERSC Perlmutter using `jobflow-remote`.

## 1. Project Configuration
The primary configuration for this setup is located in:
`~/.jfremote/remote_perlmutter.yaml`

### Key Settings:
- **Worker Type**: `local` (Switched from `remote` to avoid SSH loopback issues on the login nodes).
- **Scheduler**: `slurm`
- **Working Directory**: `/global/cfs/cdirs/m5068/bdeng/jobflow_runs`
- **Environment Setup**: Handled via the `pre_run` script in the YAML, which:
  - Loads `vasp/6.4.2-cpu`.
  - Activates the `atomate2` conda environment.
  - Sets `export ATOMATE2_CONFIG_FILE=~/.config/atomate2/config.yaml`.

### Project Name Auto-detection
To avoid specifying `project_name` in every command, you can set the `ATOMATE2_REMOTE_PROJECT` environment variable:
```bash
export ATOMATE2_REMOTE_PROJECT=remote_perlmutter
```
When this variable is set, Atomate2 MCP tools will automatically use this project if no valid default is found in the `jobflow-remote` configuration.

## 2. Slurm Submission Policies
To comply with NERSC Perlmutter CPU node policies, the following Slurm resources are configured:
- **QoS**: `regular` (Automatically mapped to `regular_1` or `regular_0`).
- **Constraint**: `cpu` (Mandatory for Milan CPU jobs).
- **Time**: "24:00:00" (Default).
- **Note**: Explicit `partition` naming is omitted to allow the system to map based on QoS.

## 3. Database & Stores
The setup connects to an external MongoDB instance (`mongodb05.nersc.gov:27017`).

- **Queue Store**: Stores job states and metadata (`agent_db.queue`).
- **Job Store (Outputs)**: Stores calculation results (`agent_db.outputs`).
- **Additional Stores**:
  - `data`: Required for large datasets/specific Atomate2 outputs (`agent_db.data`).

### Full-split Configuration: SSH Tunnel for Local Access

If you are querying Atomate2 data from your **local laptop/workstation** (not from Perlmutter), you need an SSH tunnel to access the NERSC MongoDB.

**Configuration Overview:**
- **`jobstore`**: Uses `localhost:27017` (for local queries via SSH tunnel)
- **`remote_jobstore`**: Uses `mongodb05.nersc.gov:27017` (for Perlmutter - direct access, no tunnel needed)

#### Automatic SSH Tunnel Setup

Add this to your `~/.bashrc` on your **local machine**:

```bash
# NERSC MongoDB Auto-tunnel with Key Expiration Check
nersc_tunnel_start() {
    local NERSC_KEY="$HOME/.ssh/nersc"
    
    # Check if key exists
    if [[ ! -f "$NERSC_KEY" ]]; then
        echo "⚠️  NERSC SSH key not found. Run: sshproxy -u <username>" >&2
        return 1
    fi
    
    # Check key age (< 24 hours)
    local key_age_seconds=$(($(date +%s) - $(stat -c %Y "$NERSC_KEY" 2>/dev/null || stat -f %m "$NERSC_KEY")))
    local key_age_hours=$((key_age_seconds / 3600))
    
    if [[ $key_age_hours -ge 24 ]]; then
        echo "⚠️  NERSC SSH key expired ($key_age_hours hours old). Run: sshproxy -u <username>" >&2
        return 1
    fi
    
    # Check if tunnel already running
    if pgrep -f "ssh.*mongodb05.*27017" > /dev/null 2>&1; then
        return 0
    fi
    
    # Create tunnel
    ssh -f -N -L 27017:mongodb05.nersc.gov:27017 -i "$NERSC_KEY" <username>@perlmutter-p1.nersc.gov 2>/dev/null
}

# Auto-start tunnel on login
nersc_tunnel_start

# Helpful aliases
alias nersc-refresh='sshproxy -u <username> && pkill -f "ssh.*mongodb05.*27017"; nersc_tunnel_start'
alias nersc-status='pgrep -f "ssh.*mongodb05.*27017" > /dev/null && echo "✅ Tunnel running" || echo "❌ Tunnel not running"'
```

Replace `<username>` with your NERSC username.

**What this does:**
- ✅ Auto-creates SSH tunnel on login if NERSC key is fresh (< 24 hours)
- ⚠️ Warns if key is expired (won't create broken tunnel)
- ✅ Prevents duplicate tunnels
- ✅ Provides easy refresh: `nersc-refresh`

**Daily workflow:**
1. Login to your laptop - tunnel auto-starts if key is valid
2. When key expires (~24h), you'll see a warning
3. Run `sshproxy -u <username>` to refresh (requires password + OTP)
4. Tunnel auto-restarts on next login or manual `nersc-refresh`

**Check tunnel status:**
```bash
ps aux | grep "mongodb05.*27017"
```

## 4. Runner Operations
The JobFlow Remote Runner operates as a background daemon managed by `supervisord`.

### Common Commands:
- **Start Runner**:
  ```bash
  export PATH=/global/homes/b/bdeng/anaconda3/envs/atomate2/bin:$PATH
  jf -p remote_perlmutter runner start --log-level info
  ```
- **Stop Runner**:
  ```bash
  jf -p remote_perlmutter runner stop
  ```
- **Check Status**:
  ```bash
  jf -p remote_perlmutter runner status
  ```
- **Reset Daemon**: (Use if the daemon is stuck or reports running on another machine)
  ```bash
  jf -p remote_perlmutter runner reset
  ```

## 5. Remote Workflow: How to use it
Once this setup is complete, you can submit jobs from your **local machine** and they will be executed on **Perlmutter** without you needing to be logged in.

### Step-by-Step Execution:
1. **Submit locally**: Run your Atomate2 flow on your local machine using the `remote_perlmutter` project target. This uploads the jobs to the MongoDB queue.
2. **Daemon takes over**: The `jobflow-remote` runner daemon on Perlmutter periodically checks the MongoDB queue for `READY` jobs.
3. **Execution**: The daemon submits the jobs to Slurm, monitors them, and downloads results back to the `outputs` and `data` collections in MongoDB upon completion.

### Common Questions:
- **Do I need to start the runner every time?** No. Once started with `runner start`, it runs as a background process using `supervisord`. It will survive your logout.
- **Will jobs be submitted if I log out?** Yes. As long as the Perlmutter login node is up and the daemon hasn't been stopped, it will continue to process any new jobs you submit from your local machine.
- **How do I know if it's still alive?** Log in to Perlmutter and run `jf -p remote_perlmutter runner status`. If it says `Daemon status: running`, you are good to go.
- **What if Perlmutter reboots?** If the login node is rebooted, the daemon will stop. You will need to log in and run the `runner start` command again.

## 6. Job Management
- **List Jobs**: `jf -p remote_perlmutter job list`
- **Check Slurm Queue**: `squeue -u bdeng`
- **Runner Logs**: `~/.jfremote/remote_perlmutter/log/runner.log`

---
*Setup completed/verified on 2026-01-15.*  
*SSH tunnel auto-configuration added on 2026-01-22.*
