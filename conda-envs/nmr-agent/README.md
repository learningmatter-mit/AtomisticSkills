# NMR Agent Environment

This environment supports NMR spectrum simulation, mixture analysis, and blind source separation.

## Quick Installation
Most users should use the simplified installation script, which installs only the necessary core packages:

```bash
bash install.sh
```

This installs:
- python 3.11
- rdkit
- numpy, scipy, matplotlib
- requests
- nmrsim (NMR spectrum simulation)
- scikit-learn (PCA/NMF for blind source separation)

## Full Reproduction
If you need to reproduce the exact environment state (including all pinned dependency versions), use the full example configuration:

```bash
conda env create -f example_full_env.yaml
```
