---
name: drug-molecular-fingerprints
description: Compute Morgan/ECFP fingerprints, Tanimoto similarity, and optional Butina clusters/heatmaps for small-molecule comparison.
category: [drug-discovery]
---

# Molecular Fingerprints

## Goal
To compute circular Morgan fingerprints (ECFP-style; default ECFP4 with radius=2) for a set of compounds, then calculate pairwise Tanimoto similarity for library comparison. Optionally perform Butina clustering for diversity analysis and generate a similarity heatmap for small sets.

This skill is commonly used for hit expansion, SAR triage, compound library diversity assessment, and applicability-domain style analysis.

## Instructions

The drugdisc MCP server provides a `compute_molecular_fingerprints` tool that can be called directly:

**Basic usage with SMILES file:**
```bash
mcp_drugdisc_compute_molecular_fingerprints(
    smiles_file="compounds.smi",
    radius=2,
    fp_size=2048,
    compute_similarity=True,
    output_file="similarity.json"
)
```

**With Butina clustering:**
```bash
mcp_drugdisc_compute_molecular_fingerprints(
    smiles_file="library.smi",
    cluster=True,
    cluster_cutoff=0.7,
    output_file="clustered.json"
)
```

**With similarity heatmap (small molecule sets, ≤250 compounds):**
```bash
mcp_drugdisc_compute_molecular_fingerprints(
    smiles_file="hits.smi",
    save_heatmap="heatmap.png",
    output_file="similarity.json"
)
```

**Feature Morgan (FCFP-like) fingerprints:**
```bash
mcp_drugdisc_compute_molecular_fingerprints(
    smiles_file="compounds.smi",
    use_features=True,
    output_file="fcfp_similarity.json"
)
```

**Chirality-aware fingerprints:**
```bash
mcp_drugdisc_compute_molecular_fingerprints(
    smiles_file="enantiomers.smi",
    use_chirality=True,
    output_file="chiral_sim.json"
)
```

## Examples

### SMILES file format

```text
CCO	ethanol
CCCO	propanol
c1ccccc1	benzene
c1ccc(cc1)O	phenol
```

### Basic similarity analysis

```bash
mcp_drugdisc_compute_molecular_fingerprints(
    smiles_file=".agents/skills/drug-molecular-fingerprints/examples/compounds.smi",
    output_file="similarity.json"
)
```

### Diversity-based clustering for library selection

```bash
mcp_drugdisc_compute_molecular_fingerprints(
    smiles_file="screening_library.smi",
    cluster=True,
    cluster_cutoff=0.5,
    output_file="diverse_clusters.json"
)
```

## Output Format

The tool returns a JSON with:
- `n_compounds`: Total number of input compounds
- `n_valid`: Number of successfully processed compounds
- `compounds`: List of compound info (SMILES, name, validity, fingerprint bits)
- `similarity_matrix`: Pairwise Tanimoto similarity (if `compute_similarity=True`)
- `clusters`: Butina clustering results (if `cluster=True`)

## Constraints

- **MCP Server**: Requires `drugdisc` MCP server
- **Dependencies**: RDKit (Chem, rdFingerprintGenerator, DataStructs, ML.Cluster.Butina)
- **SMILES file format**: One molecule per line, `SMILES[whitespace]NAME` (NAME optional), `#` for comments
- **Fingerprint defaults**: Morgan radius=2 (ECFP4-like), 2048 bits
- **Heatmap rendering**: Limited to ≤250 compounds due to memory constraints
- **Similarity metric**: Tanimoto coefficient (Jaccard index for bit vectors)
- **Clustering algorithm**: Butina (leader-picker style); cutoff = similarity threshold (not distance)
---

**Author:** Matthew Cox  
**Contact:** [GitHub @mcox3406](https://github.com/mcox3406)
