# Base Agent Environment

This environment provides the core tools for materials analysis and automation.

## Quick Installation
Most users should use the simplified installation script, which installs only the necessary core packages:

```bash
bash install.sh
```

This installs:
- python 3.10
- atomate2
- pymatgen
- ase

## Full Reproduction
If you need to reproduce the exact environment state (including all pinned dependency versions), use the full example configuration:

```bash
conda env create -f example_full_env.yaml
```
