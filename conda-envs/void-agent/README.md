# `void-agent`
This conda environment is specifically built to support the `VOID` library (Voronoi Organic-Inorganic Docker) and the `chem-docking-void` capability.

## Overview
- **Python**: 3.10
- **Purpose**: Molecular docking and sampling within porous materials (e.g. Zeolites, MOFs).
- **Core Dependencies**: `pymatgen`, `zeopp-lsmo` (via Conda-forge), `pyzeo`, `numpy`, `networkx`, and `rdkit` (required for 3D conformer initialization).

## Installation

This installer leverages `uv` and `conda` to accelerate the installation timeline.
It automatically replaces the cumbersome manual compile procedure for Zeo++ and Voro++ by installing a pre-packaged build (`zeopp-lsmo`) from `conda-forge`. 
It will clone the core VOID repository directly from `https://github.com/learningmatter-mit/VOID.git` into `~/projects/atomistic_skills/VOID` to install it.

Run the auto-installer:
```bash
./install.sh
```

## Usage
Once installed, remember to activate it before initiating docking tasks:
```bash
conda activate void-agent
```
