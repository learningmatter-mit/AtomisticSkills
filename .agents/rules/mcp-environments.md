---
trigger: always_on
---

# MCP Server Environment Rules

When running scripts or debugging code related to specific MCP servers, you MUST use the corresponding Conda environment defined in `mcp_config.json`.

For general development logic that cuts across tools, usually `base-agent` is sufficient, but when importing specific libraries that are isolated (like `atomate2`, `jobflow_remote`, `mace`, `fairchem`), you must use the correct environment.

## Installation Instructions

For detailed installation instructions, please refer to the `README.md` and `install.sh` located in each environment's directory under `conda-envs/<env_name>/`.

- **base-agent**: `conda-envs/base-agent/` (Core: pymatgen, ase, rdkit, packmol)
- **mace-agent**: `conda-envs/mace-agent/` (Core: mace-torch, pymatgen, ase)
- **matgl-agent**: `conda-envs/matgl-agent/` (Core: matgl, pymatgen, dgl)
- **fairchem-agent**: `conda-envs/fairchem-agent/` (Core: fairchem-core≥2.18, pymatgen, Python 3.12)
- **atomate2-agent**: `conda-envs/atomate2-agent/` (Core: atomate2, pymatgen)
- **smol-agent**: `conda-envs/smol-agent/` (Core: smol, pymatgen)
- **htvs-agent**: `conda-envs/htvs-agent.yml` (Core: django, psycopg2, vasp-parsers)
- **adit-agent**: `conda-envs/adit-agent/` (Core: ADiT, lightning, hydra, PyG)
- **diffcsp-agent**: `conda-envs/diffcsp-agent/` (Core: DiffCSP++, hydra, PyG, pyxtal)
- **mattergen-agent**: `conda-envs/mattergen-agent/` (Core: MatterGen, PyG, lightning)
- **smol-agent**: `conda-envs/smol-agent/` (Core: smol, pymatgen)
- **drugdisc-agent**: `conda-envs/drugdisc-agent/` (Core: rdkit, autodock-vina, pdbfixer, meeko)
- **xrd-agent**: `conda-envs/xrd-agent/` (Core: DARA, pymatgen)
- **orca-agent**: `conda-envs/orca-agent/` (Core: scine_utilities, scine_readuct, ase). Requires `ORCA_BINARY_PATH` environment variable pointing to the ORCA binary. No MCP server, scripts only.
- **phasefield-agent**: `conda-envs/phasefield-agent/` (Core: fipy, scipy, numpy, imageio). No MCP server, scripts only.
- **calphad-agent**: `conda-envs/calphad-agent/` (Core: pycalphad, pymatgen). No MCP server, scripts only.
- **nmr-agent**: `conda-envs/nmr-agent/` (Core: nmrsim, nmrglue, pot). No MCP server, scripts only.
- **react-ot-agent**: `conda-envs/react-ot-agent/` (Core: PyTorch). No MCP server, scripts only.

| MCP Server | Conda Environment | Python Path |
| :--- | :--- | :--- |
| matgl | `matgl-agent` | `<conda_base>/envs/matgl-agent/bin/python` |
| mace | `mace-agent` | `<conda_base>/envs/mace-agent/bin/python` |
| fairchem | `fairchem-agent` | `<conda_base>/envs/fairchem-agent/bin/python` |
| materials_tools | `base-agent` | `<conda_base>/envs/base-agent/bin/python` |
| atomate2 | `atomate2-agent` | `<conda_base>/envs/atomate2-agent/bin/python` |
| smol | `smol-agent` | `<conda_base>/envs/smol-agent/bin/python` |
| htvs | `htvs-agent` | `<conda_base>/envs/htvs-agent/bin/python` |
| adit | `adit-agent` | `<conda_base>/envs/adit-agent/bin/python` |
| diffcsp | `diffcsp-agent` | `<conda_base>/envs/diffcsp-agent/bin/python` |
| mattergen | `mattergen-agent` | `<conda_base>/envs/mattergen-agent/bin/python` |
| drugdisc | `drugdisc-agent` | `<conda_base>/envs/drugdisc-agent/bin/python` |
