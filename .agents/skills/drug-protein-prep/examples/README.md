# c-Abl Kinase Receptor Preparation Example (1IEP)

This example demonstrates preparing the c-Abl kinase domain (PDB: 1IEP, chain A) for docking with AutoDock Vina.

## Files

- `1iep_receptor/1IEP_prepared.pdb`: Cleaned receptor with hydrogens added at pH 7.0
- `1iep_receptor/1IEP_prepared.pdbqt`: Vina/AutoDock-ready receptor (PDBQT format via Meeko)
- `1iep_receptor/1IEP_summary.json`: Full preparation report (settings, missing residues, chain selection, atom counts)

## How to reproduce

From the project root:

```bash
# Env: drugdisc-agent
python .agents/skills/drug-protein-prep/scripts/prepare_protein.py \
  --pdb_id 1iep \
  --chains A \
  --heterogens none \
  --missing_residues ignore \
  --ph 7.0 \
  --output_dir .agents/skills/drug-protein-prep/examples/1iep_receptor/
```

## Results

| Property | Value |
|---|---|
| PDB ID | 1IEP |
| Chain | A |
| Residues | 274 |
| Atoms (with H) | 4411 |
| Missing residue regions | 2 (N-terminal GA + C-terminal 17-residue loop, both ignored) |
| Nonstandard residues | None |
| Heterogens | Removed (mode: none) |
| PDBQT | Generated via Meeko 0.7.1 |
