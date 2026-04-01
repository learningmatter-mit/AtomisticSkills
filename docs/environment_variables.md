# Environment Variables Guide

This document lists the environment variables required for the MLIP agent to function correctly with various MCP tools.

## Core Variables

| Variable | Description | Required By | Example |
| :--- | :--- | :--- | :--- |
| `CURRENT_RESEARCH_DIR` | Tracks the active research directory for the current session. Automatically set by tools. | All MCP Tools | `/path/to/project/research/2024-01-20_LiFePO4` |

## Atomate2 & VASP

| Variable | Description | Required By | Example |
| :--- | :--- | :--- | :--- |
| `ATOMATE2_CONFIG_FILE` | Path to the Atomate2 configuration file. | `atomate2` | `~/.config/atomate2/config.yaml` |
| `atomate2_remote_project` (or `ATOMATE2_REMOTE_PROJECT`) | Default project name for remote job submission (auto-detected). | `atomate2` | `remote_perlmutter` |
| `VASP_CMD` or `ATOMATE2_VASP_CMD` | Command to run VASP (for local execution). | `atomate2` | `mpirun -np 1 vasp_std` |
| `PMG_VASP_PSP_DIR` | Path to VASP POTCAR directory. | `pymatgen`, `atomate2` | `/path/to/vasp/potcar` |
| `MP_API_KEY` | API Key for Materials Project access. | `base_tools`, `pymatgen` | `abc123def456` |

## Configuration Files

Instead of setting variables manually, it is recommended to use standard configuration files where possible:

- **MLIP Agent**: `~/.mlip_agent.yaml` or `~/.config/mlip_agent.yaml`
    - This is the main configuration for the agent. Any key defined here will be injected into the environment.
    - Example:
      ```yaml
      ATOMATE2_REMOTE_PROJECT: remote_perlmutter
      MP_API_KEY: abc123def456
      ```
- **Pymatgen**: `~/.pmgrc.yaml` (Manages `PMG_VASP_PSP_DIR`, `MP_API_KEY`)
- **JobFlow Remote**: `~/.jfremote/` (Manages remote clusters and projects like `remote_perlmutter`)
- **Atomate2**: `~/.config/atomate2/config.yaml`

The `.env` file in the project root can be used for project-specific overrides or for variables not covered by the above (like `CURRENT_RESEARCH_DIR`).
