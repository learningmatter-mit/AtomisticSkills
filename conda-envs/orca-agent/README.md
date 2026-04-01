# ORCA Agent Environment

This environment provides the tools for carrying out molecular DFT calculations given that ORCA is already installed on the system and specified with `ORCA_BINARY_PATH`.

> **Platform**: Requires **x86_64** (linux-64 or osx-64). SCINE packages are not available as pre-built binaries for aarch64/ARM. On ARM systems, build SCINE from source: https://github.com/qcscine/utilities

## Quick Installation
Most users should use the simplified installation script, which installs only the necessary core packages:

```bash
bash install.sh
```

This installs:
- python 3.11
- ase
- numpy<2
- scipy
- pyyaml
- scine-utilities==10.1.0
- scine-readuct

## Full Reproduction
If you need to reproduce the exact environment state (including all pinned dependency versions), use the full example configuration:

```bash
conda env create -f example_full_env.yaml
```
