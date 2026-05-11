# Ibuprofen K-Means Clustering Example

This example demonstrates the new **K-Means clustering** mode for deduplication, introduced to solve [Issue #13](https://github.com/bowen-bd/AtomisticSkills/issues/13). Unlike the legacy RMSD threshold approach, clustering guarantees a maximally **diverse** yet **low-energy** conformer ensemble.

## Molecule

**Ibuprofen** (`CC(C)CC1=CC=C(C=C1)C(C)C(=O)O`) — a flexible NSAID drug with multiple rotatable bonds, making it a good benchmark for conformer diversity.

## Usage

Run from the project root:

```bash
# Env: mace-agent
python .agents/skills/chem-conformer-search/scripts/conformer_search.py \
    --smiles "CC(C)CC1=CC=C(C=C1)C(C)C(=O)O" \
    --num_conformers 50 \
    --clustering kmeans \
    --num_clusters 5 \
    --model_type mace \
    --model_name MACE-OFF23-small \
    --output_dir .agents/skills/chem-conformer-search/examples/ibuprofen_kmeans
```

## Results

| Conformer | File | Rel. Energy (kcal/mol) | Boltzmann Weight |
|:---:|:---|:---:|:---:|
| 0 (Global Min) | [conf_000.xyz](conf_000.xyz) | 0.000 | 26.7% |
| 1 | [conf_001.xyz](conf_001.xyz) | 0.052 | 24.5% |
| 2 | [conf_002.xyz](conf_002.xyz) | 0.176 | 19.9% |
| 3 | [conf_003.xyz](conf_003.xyz) | 0.356 | 14.7% |
| 4 | [conf_004.xyz](conf_004.xyz) | 0.373 | 14.3% |

- **Initial conformers generated:** 25 (from 50 RDKit requests, after initial RMS pruning)
- **Final unique conformers (1 per KMeans cluster):** 5
- **Model:** MACE-OFF23-small

## Key Advantage Over RMSD Threshold

The strict 0.1 Å default threshold can return an excessive number of conformers that are slightly different, but represent the same conformational state. The simple RMSD deduplication can be sufficient for small, conformationally restricted drug-like molecules, but can struggle with larger molecules. K-Means always returns exactly `--num_clusters` representatives by construction, ensuring broad exploration of the conformational landscape regardless of molecule size or RMSD scale.
