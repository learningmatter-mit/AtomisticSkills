---
name: drug-docking-vina
description: Dock small-molecule ligands into a protein receptor using AutoDock Vina (Python API) and save ranked poses + docking metadata for reproducible virtual screening.
category: [drug-discovery]
---

# docking-vina

## Goal
To perform molecular docking of one or more small-molecule ligands into a protein receptor using **AutoDock Vina (>= 1.2.x)** via its **Python API**, producing:
- Ranked binding poses (PDBQT)
- Docking scores (kcal/mol) and pose RMSDs
- A machine-readable JSON report with full docking parameters for reproducibility

This skill is intended for **pose generation and relative ranking**, not rigorous binding free energy prediction. Please refer to the original Vina method (Trott & Olson, https://doi.org/10.1002/jcc.21334) and the AutoDock Vina repo (https://github.com/ccsb-scripps/AutoDock-Vina) for more details.

## Instructions

### 1. Prepare receptor and ligand (recommended)
Docking accuracy is strongly affected by **structure preparation** (protonation, missing residues, cofactors, waters, tautomer states, etc.). Use:
- [protein-prep](../drug-protein-prep/SKILL.md) to generate `*_prepared.pdbqt`
- [ligand-prep](../drug-ligand-prep/SKILL.md) to generate ligand `*.pdbqt` (consider multiple protomers/tautomers)

```bash
# Env: drugdisc-agent
python .agents/skills/drug-protein-prep/scripts/prepare_protein.py \
  --pdb_id 1HSG \
  --heterogens none \
  --missing_residues ignore \
  --output_dir docking/inputs/

# Env: drugdisc-agent
python .agents/skills/drug-ligand-prep/scripts/prepare_ligand.py \
  --smiles "CC(=O)Oc1ccccc1C(=O)O" \
  --name aspirin \
  --output_dir docking/inputs/
```

**Best practice:** if you have a co-crystal ligand, keep it as a positive control for redocking validation.

### 2. Define the docking search box (center + size)

You must define the docking region. The most common approaches:

* **Redocking / known pocket:** center on the co-crystallized ligand
* **Known active site residues:** center on key catalytic residues
* **Blind docking:** large box spanning the protein (slower and less reliable, so use cautiously)

If you have a reference ligand already positioned in the binding site (PDBQT), compute a reasonable box automatically:

```bash
# Env: drugdisc-agent
python .agents/skills/drug-docking-vina/scripts/compute_box_from_pdbqt.py \
  docking/inputs/reference_ligand.pdbqt \
  --padding 6.0 \
  --min_size 20.0 \
  --output_json docking/inputs/docking_box.json
```

This writes `center_x/y/z` and `size_x/y/z` you can paste into the docking command.

### 3. Run docking (single ligand)

```bash
# Env: drugdisc-agent
python .agents/skills/drug-docking-vina/scripts/run_docking.py \
  --receptor docking/inputs/1HSG_prepared.pdbqt \
  --ligand docking/inputs/aspirin.pdbqt \
  --center_x 16.0 --center_y 25.0 --center_z 2.0 \
  --size_x 20 --size_y 20 --size_z 20 \
  --scoring vina \
  --exhaustiveness 32 \
  --n_poses 10 \
  --energy_range 3.0 \
  --min_rmsd 1.0 \
  --seed 42 \
  --cpu 0 \
  --output_dir docking/results/
```

Outputs:

* `docking/results/aspirin_docked.pdbqt`
* `docking/results/docking_results.json`

### 4. Run docking (batch mode / virtual screening)

```bash
# Env: drugdisc-agent
python .agents/skills/drug-docking-vina/scripts/run_docking.py \
  --receptor docking/inputs/1HSG_prepared.pdbqt \
  --ligand_dir docking/inputs/ligands_pdbqt/ \
  --center_x 16.0 --center_y 25.0 --center_z 2.0 \
  --size_x 20 --size_y 20 --size_z 20 \
  --scoring vina \
  --exhaustiveness 16 \
  --n_poses 5 \
  --seed 42 \
  --cpu 0 \
  --output_dir docking/screening_results/
```

**Tip:** for batch docking, the script will compute Vina maps once (before loading ligands) to reduce repeated setup overhead.

### 5. Validation & interpretation (strongly recommended)

Docking is approximate; good practice is to validate your protocol for a given target:

* **Redocking test:** dock the co-crystal ligand back into the pocket and check whether the top pose reproduces the experimental pose (often RMSD < 2 Angstrom is used as a sanity check, but interpret in context).
* **Multiple runs / convergence:** Vina's search is **non-deterministic**; increasing exhaustiveness and/or running multiple seeds can improve reliability.
* **Controls:** include known actives/inactives or decoys; don't rely on a universal "score threshold".

## Examples

### Example: HIV-1 protease docking (1HSG + indinavir)

```bash
# Env: drugdisc-agent
python .agents/skills/drug-protein-prep/scripts/prepare_protein.py \
  --pdb_id 1HSG \
  --heterogens none \
  --missing_residues ignore \
  --output_dir hiv_docking/inputs/

# Env: drugdisc-agent
python .agents/skills/drug-ligand-prep/scripts/prepare_ligand.py \
  --smiles "CC(C)(C)NC(=O)C1CC2CCCCC2CN1CC(O)C(CC1=CC=CC=C1)NC(=O)C(CC(N)=O)NC(=O)C1=CC2=CC=CC=C2N1" \
  --name indinavir \
  --output_dir hiv_docking/inputs/

# Env: drugdisc-agent
python .agents/skills/drug-docking-vina/scripts/run_docking.py \
  --receptor hiv_docking/inputs/1HSG_prepared.pdbqt \
  --ligand hiv_docking/inputs/indinavir.pdbqt \
  --center_x 16.0 --center_y 25.0 --center_z 2.0 \
  --size_x 20 --size_y 20 --size_z 20 \
  --exhaustiveness 32 \
  --n_poses 10 \
  --output_dir hiv_docking/results/
```

## Constraints

* **Environment**: Requires `drugdisc-agent`.
* **AutoDock Vina**: Requires AutoDock Vina Python bindings (`vina` package; typically Vina >= 1.2.x).
* **Input format**: Receptor and ligands must be **PDBQT**.
* **Search space selection**: Box center/size strongly affects accuracy and runtime; avoid unnecessarily large "blind docking" boxes unless justified.
* **Stochastic search**: Results can vary between runs; use an explicit `--seed` for reproducibility and consider higher `--exhaustiveness` for difficult systems.
* **Scoring**: Vina scores are **not experimental delta-G**; treat as approximate scoring for ranking/pose generation.

## References (recommended reading)

1. Trott, O.; Olson, A. J. AutoDock Vina: Improving the Speed and Accuracy of Docking with a New Scoring Function, Efficient Optimization, and Multithreading. *J. Comput. Chem.* **2010**, *31*, 455–461. https://doi.org/10.1002/jcc.21334

2. Eberhardt, J.; Santos-Martins, D.; Tillack, A. F.; Forli, S. AutoDock Vina 1.2.0: New Docking Methods, Expanded Force Field, and Python Bindings. *J. Chem. Inf. Model.* **2021**, *61*, 3891–3898. https://doi.org/10.1021/acs.jcim.1c00203

3. Forli, S. Charting a Path to Success in Virtual Screening. *Molecules* **2015**, *20*, 18732–18758. https://doi.org/10.3390/molecules201018732

4. Paggi, J. M.; Pandit, A.; Dror, R. O. The Art and Science of Molecular Docking. *Annu. Rev. Biochem.* **2024**, *93*, 389–410. https://doi.org/10.1146/annurev-biochem-030222-120000

5. Feinstein, W. P.; Brylinski, M. Calculating an Optimal Box Size for Ligand Docking and Virtual Screening against Experimental and Predicted Binding Pockets. *J. Cheminform.* **2015**, *7*, 18. https://doi.org/10.1186/s13321-015-0067-5
---

**Author:** Matthew Cox  
**Contact:** [GitHub @mcox3406](https://github.com/mcox3406)
