# NSAID Fingerprint Similarity Example

This example computes ECFP4 Morgan fingerprints and pairwise Tanimoto similarity for three NSAIDs (aspirin, ibuprofen, and 2-phenylpropanoic acid), with Butina clustering and a similarity heatmap.

## Files

- `nsaids.smi`: SMILES file with 3 NSAID compounds
- `nsaid_similarity.json`: Full output including fingerprint metadata, pairwise similarity matrix, and Butina clusters
- `nsaid_similarity.png`: Tanimoto similarity heatmap

## How to reproduce

Using the drugdisc MCP tool:

```python
mcp_drugdisc_compute_molecular_fingerprints(
    smiles_file=".agents/skills/drug-molecular-fingerprints/examples/nsaids.smi",
    radius=2,
    fp_size=2048,
    cluster=True,
    cluster_cutoff=0.4,
    save_heatmap=".agents/skills/drug-molecular-fingerprints/examples/nsaid_similarity.png",
    output_file=".agents/skills/drug-molecular-fingerprints/examples/nsaid_similarity.json"
)
```

## Results

Pairwise Tanimoto similarity (ECFP4, 2048 bits):

| Compound | Aspirin | Ibuprofen | 2-Phenylpropanoic acid |
|----------|---------|-----------|----------------------)|
| **Aspirin** | 1.00 | 0.20 | 0.23 |
| **Ibuprofen** | 0.20 | 1.00 | 0.42 |
| **2-Phenylpropanoic acid** | 0.23 | 0.42 | 1.00 |

At cutoff 0.4, Butina clustering produces **2 clusters**:
- **Cluster 1**: Ibuprofen + 2-Phenylpropanoic acid (similarity 0.42)
- **Cluster 2**: Aspirin (distinct scaffold)

This demonstrates that ibuprofen and 2-phenylpropanoic acid share more structural similarity (both have phenylpropanoic acid core), while aspirin has a distinct salicylate scaffold.

Author: Matthew Cox
Contact: github username <mcox3406>
