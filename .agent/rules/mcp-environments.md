---
trigger: always_on
---

# MCP Server Environment Rules

When running scripts or debugging code related to specific MCP servers, you MUST use the corresponding Conda environment defined in `mcp_config.json`.

For general development logic that cuts across tools, usually `base-agent` is sufficient, but when importing specific libraries that are isolated (like `atomate2`, `jobflow_remote`, `mace`, `fairchem`), you must use the correct environment.

## Installation Instructions

For detailed installation instructions, please refer to the `README.md` and `install.sh` located in each environment's directory under `conda-envs/<env_name>/`.

- **base-agent**: `conda-envs/base-agent/` (Core: atomate2, pymatgen, ase)
- **mace-agent**: `conda-envs/mace-agent/` (Core: mace-torch, pymatgen, ase)
- **matgl-agent**: `conda-envs/matgl-agent/` (Core: matgl, pymatgen, dgl)
- **fairchem-agent**: `conda-envs/fairchem-agent/` (Core: fairchem-core, pymatgen)
- **atomate2-agent**: `conda-envs/atomate2-agent/` (Core: atomate2, pymatgen)
- **smol-agent**: `conda-envs/smol-agent/` (Core: smol, pymatgen)

| MCP Server | Conda Environment | Python Path |
| :--- | :--- | :--- |
| matgl | `matgl-agent` | `<conda_base>/envs/matgl-agent/bin/python` |
| mace | `mace-agent` | `<conda_base>/envs/mace-agent/bin/python` |
| fairchem | `fairchem-agent` | `<conda_base>/envs/fairchem-agent/bin/python` |
| materials_tools | `base-agent` | `<conda_base>/envs/base-agent/bin/python` |
| atomate2 | `atomate2-agent` | `<conda_base>/envs/atomate2-agent/bin/python` |
| smol | `smol-agent` | `<conda_base>/envs/smol-agent/bin/python` |