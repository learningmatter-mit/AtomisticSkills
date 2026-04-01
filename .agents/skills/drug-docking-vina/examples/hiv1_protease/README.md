# HIV-1 Protease Docking Example (1HSG + Indinavir)

This example demonstrates docking indinavir into HIV-1 protease (PDB: 1HSG) using AutoDock Vina. 1HSG is a common benchmark for docking validation; it contains HIV-II protease complexed with L-735,524 (an indinavir precursor).

## Files

- `inputs/1HSG_prepared.pdb`: Prepared receptor (protonated, heterogens removed)
- `inputs/1HSG_prepared.pdbqt`: Receptor in PDBQT format (docking input)
- `inputs/indinavir/indinavir.pdbqt`: Prepared indinavir ligand in PDBQT format
- `output/docking_results.json`: Full docking results with scores, energy decomposition, and metadata
- `output/indinavir_docked.pdbqt`: Ranked docked poses

## How to reproduce

From the project root:

```bash
# Env: drugdisc-agent
# Step 1: Prepare receptor
python .agents/skills/drug-protein-prep/scripts/prepare_protein.py \
  --pdb_id 1HSG \
  --heterogens none \
  --missing_residues ignore \
  --output_dir .agents/skills/drug-docking-vina/examples/hiv1_protease/inputs/

# Step 2: Prepare ligand
python .agents/skills/drug-ligand-prep/scripts/prepare_ligand.py \
  --smiles "CC(C)(C)NC(=O)C1CC2CCCCC2CN1CC(O)C(CC1=CC=CC=C1)NC(=O)C(CC(N)=O)NC(=O)C1=CC2=CC=CC=C2N1" \
  --name indinavir \
  --output_dir .agents/skills/drug-docking-vina/examples/hiv1_protease/inputs/

# Step 3: Dock
python .agents/skills/drug-docking-vina/scripts/run_docking.py \
  --receptor .agents/skills/drug-docking-vina/examples/hiv1_protease/inputs/1HSG_prepared.pdbqt \
  --ligand .agents/skills/drug-docking-vina/examples/hiv1_protease/inputs/indinavir/indinavir.pdbqt \
  --center_x 16.0 --center_y 25.0 --center_z 2.0 \
  --size_x 20 --size_y 20 --size_z 20 \
  --scoring vina \
  --exhaustiveness 32 \
  --n_poses 5 \
  --seed 42 \
  --output_dir .agents/skills/drug-docking-vina/examples/hiv1_protease/output/
```

## Results

Vina returns 5 poses ranked by affinity:

| Pose | Affinity (kcal/mol) | Inter | Intra | Torsions |
|---|---|---|---|---|
| 1 | -9.75 | -17.45 | -2.07 | 7.70 |
| 2 | -9.62 | -18.44 | -0.84 | 7.59 |
| 3 | -9.51 | -17.42 | -1.67 | 7.51 |
| 4 | -9.44 | -17.76 | -1.20 | 7.45 |
| 5 | -9.26 | -17.72 | -0.92 | 7.31 |

Best affinity: **-9.75 kcal/mol** (pose 1).
