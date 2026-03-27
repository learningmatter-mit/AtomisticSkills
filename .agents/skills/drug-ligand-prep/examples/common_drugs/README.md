# Common Drugs Ligand Preparation Example

This example demonstrates ligand preparation for three well-known drug molecules: aspirin, ibuprofen, and caffeine. It shows multi-conformer generation, MMFF94 minimization, and SDF/PDBQT export.

## Files

- `compounds.smi`: Input SMILES file (tab-separated SMILES + name)
- `output/`: Pre-computed results from running the workflow
  - `output/preparation_summary.json`: Full preparation summary
  - `output/<name>/<name>.sdf`: Optimized 3D structure (best conformer)
  - `output/<name>/<name>.pdbqt`: Docking-ready PDBQT

## How to run

To reproduce the results, run the following command from the project root:

```bash
conda activate drugdisc-agent
python .agents/skills/drug-ligand-prep/scripts/prepare_ligand.py \
  --smiles_file .agents/skills/drug-ligand-prep/examples/common_drugs/compounds.smi \
  --output_dir .agents/skills/drug-ligand-prep/examples/common_drugs/output \
  --num_confs 50 \
  --prune_rms 0.5
```

## With protonation state enumeration

Aspirin and ibuprofen both have a carboxylic acid that can be ionized at physiological pH. To enumerate protomers:

```bash
conda activate drugdisc-agent
python .agents/skills/drug-ligand-prep/scripts/prepare_ligand.py \
  --smiles_file .agents/skills/drug-ligand-prep/examples/common_drugs/compounds.smi \
  --output_dir ligand_prep/common_drugs_states \
  --num_confs 50 \
  --enumerate_protomers \
  --ph_min 6.8 \
  --ph_max 7.4
```

This will generate multiple states per molecule (e.g., neutral and deprotonated aspirin), each with its own SDF and PDBQT.

## Results

All three molecules prepared successfully with MMFF94:

| Molecule | MW | Conformers | Best Energy (kcal/mol) | SDF | PDBQT |
|---|---|---|---|---|---|
| Aspirin | 180.04 | 2 | 18.91 | yes | yes |
| Ibuprofen (S) | 206.13 | 6 | 23.79 | yes | yes |
| Caffeine | 194.08 | 1 | -122.53 | yes | yes |

Notable:
- **Ibuprofen** uses the (S)-enantiomer SMILES (`[C@@H]`), which is the pharmacologically active form. No stereocenter warnings.
- **Caffeine** generates only 1 conformer because it is a rigid planar molecule with 0 rotatable bonds.
- **Aspirin** generates 2 conformers (limited flexibility from the ester/acid torsion).
