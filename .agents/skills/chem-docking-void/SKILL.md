---
name: chem-docking-void
description: Dock small-molecule guests into a porous host material using the VOID library (Voronoi Clustering), generating multiple 3D conformers with RDKit and ranking generated complexes.
category: [materials, chemistry]
---

# chem-docking-void

## Goal
To perform molecular docking of a small-molecule ligand into a porous material structure (CIF format) using the **VOID** library. This skill aims to automatically generate a robust sampling of guest conformers using RDKit, optimize them, and then distribute them throughout the host framework using Voronoi-based cluster sampling and physics-informed collision filtering.

This will output:
- Ranked docked complexes saved individually as standard CIF files.
- A metadata summary (`docking_results.json`) capturing the generation parameters, associated RDKit conformer energies, and matched pose IDs.

## Instructions

### 1. Identify Inputs
You will need:
- The **SMILES** string of your guest molecule.
- The **CIF** file path to your porous material (e.g. Zeolites, MOFs).

### 2. Basic Docking Run

A standard run accepts the chemical inputs and saves outputs to a designated folder.

```bash
# Env: atomistic-agent
python .agents/skills/chem-docking-void/scripts/run_docking.py \
  --smiles "CC12C3C4C5C6C1C7C2C3C4C5C67" \
  --host_cif /path/to/host/material.cif \
  --output_dir output/docked_poses \
  --num_conformers 5
```
*(The SMILES here represents Adamantane or similar structures for testing.)*

### 3. Tuning Hyperparameters

The clustering map and acceptance rates are highly sensitive to VOID's search parameters. Use the advanced arguments for dense loading or strict spatial tolerances:

```bash
python .agents/skills/chem-docking-void/scripts/run_docking.py \
  --smiles "CC(=O)Oc1ccccc1C(=O)O" \
  --host_cif /path/to/host/MOF.cif \
  --output_dir output/docked_poses \
  --num_conformers 10 \
  --threshold 1.8 \
  --attempts 2000 \
  --structs_per_loading 5 \
  --num_clusters 150 \
  --max_loading 1 \
  --max_subdock 200 \
  --remove_species "H2O" "Na"
```

#### Meaning of Key Hyperparameters:
- `--num_conformers`: (RDKit) How many of the lowest-energy 3D geometries to test.
- `--threshold`: The acceptable minimum distance (Å) between the host atoms and guest atoms. A lower value allows tighter squeezes but risks atomic clashes.
- `--attempts`: How many random translation/rotation insertion guesses the `Subdocker` makes per `BatchDocker` queue limit.
- `--structs_per_loading`: Maximum number of successful geometries to export out of all validated matches, per conformer tested.
- `--num_clusters` & `--min_radius`: Settings for the `VoronoiClustering` sampler that determine the density and minimum pore volume of chosen docking nodes within the material.
- `--remove_species`: Pre-cleans the CIF file of specified elements (like free solvent) before docking.

## Constraints

* **Environment**: Requires `atomistic-agent` conda environment where `VOID`, `rdkit`, and `pymatgen` are accessible.
* **Loading Size**: By default, this script handles single-guest loadings per unit cell. Heavy multiple guest loading (`--max_loading > 1`) may scale exponentially in computational time depending on pore size.
* **Outputs**: Everything is standardized to CIF files for compatibility with subsequent DFT or MLIP workflows.

## References

1. VOID Library
2. Pymatgen `pymatgen.core.Structure` and `pymatgen.core.Molecule`
3. RDKit cheminformatics (MMFF94 structural optimization)

---
**Author:** Mingrou Xie 
**Contact:** [GitHub @mingrouxie](https://github.com/mingrouxie)
