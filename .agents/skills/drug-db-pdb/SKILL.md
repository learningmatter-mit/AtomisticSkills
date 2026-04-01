---
name: drug-db-pdb
description: Search, filter, and retrieve macromolecular structures from the RCSB Protein Data Bank (PDB), including metadata, bound ligands, and optional coordinate/validation downloads.
category: [drug-discovery]
---

# db-pdb

## Goal
To programmatically discover and retrieve protein (and protein-ligand complex) structures from the RCSB Protein Data Bank (PDB) by combining the RCSB Search API (to find matching PDB IDs) with the RCSB Data API (to retrieve rich metadata and ligand information), and optionally downloading coordinate files (PDB/mmCIF) and wwPDB validation reports for downstream modeling.

## Instructions

### 1. (Recommended) Create a dedicated output directory
Keep downloaded coordinates/JSON in a reproducible folder.

```bash
# Env: base-agent
mkdir -p research/db-pdb/ace2_example
```

### 2. Search by keyword (full-text)
Uses the RCSB Search API to return the top scoring PDB IDs for a query.

```bash
# Env: base-agent
python .agents/skills/drug-db-pdb/scripts/query_pdb.py \
  --search "kinase inhibitor" \
  --max_results 10 \
  --output research/db-pdb/kinase_results.json
```

### 3. Search with structure-quality filters (recommended for drug discovery)
For ligand modeling, you often want:
- An experimental method like **X-RAY DIFFRACTION** (or high-resolution cryo-EM).
- A resolution cutoff (e.g., <= 2.5 A for X-ray, context dependent).

```bash
# Env: base-agent
python .agents/skills/drug-db-pdb/scripts/query_pdb.py \
  --search "ACE2" \
  --organism "Homo sapiens" \
  --method "X-RAY DIFFRACTION" \
  --resolution 2.5 \
  --max_results 25 \
  --output research/db-pdb/ace2_xray_le2p5.json
```

### 4. Retrieve a specific PDB entry by ID
This pulls metadata via the Data API and (by default) also collects bound ligands by enumerating non-polymer entities.

```bash
# Env: base-agent
python .agents/skills/drug-db-pdb/scripts/query_pdb.py \
  --pdb_id 1HSG \
  --output research/db-pdb/1hsg_info.json
```

### 5. Download coordinate files (mmCIF recommended)
The PDB ecosystem's canonical archival format is PDBx/mmCIF (legacy PDB format can be unavailable or insufficient for very large structures).

```bash
# Env: base-agent
python .agents/skills/drug-db-pdb/scripts/query_pdb.py \
  --pdb_id 1HSG \
  --download mmcif \
  --download_dir research/db-pdb/structures \
  --output research/db-pdb/1hsg_with_file.json
```

### 6. (Recommended) Download wwPDB validation report PDF
Quality assessment for experimental structures is standardized via wwPDB validation reports; these are especially important for ligand-bound structures in drug discovery workflows.

```bash
# Env: base-agent
python .agents/skills/drug-db-pdb/scripts/query_pdb.py \
  --pdb_id 1HSG \
  --download_validation \
  --download_dir research/db-pdb/validation \
  --output research/db-pdb/1hsg_with_validation.json
```

## Examples

Search HIV-1 protease entries, then fetch + download the best candidate:

```bash
# Env: base-agent
python .agents/skills/drug-db-pdb/scripts/query_pdb.py \
  --search "HIV-1 protease" \
  --method "X-RAY DIFFRACTION" \
  --resolution 2.0 \
  --max_results 10 \
  --output research/db-pdb/hiv1_protease_candidates.json
```

```bash
# Env: base-agent
python .agents/skills/drug-db-pdb/scripts/query_pdb.py \
  --pdb_id 1HSG \
  --download mmcif \
  --download_validation \
  --download_dir research/db-pdb/hiv1_protease_files \
  --output research/db-pdb/1hsg_full.json
```

## Constraints
- **API Rate Limits**: RCSB PDB APIs are rate-limited; the script implements a minimum inter-request interval and exponential backoff on HTTP 429.
- **Ligand metadata**: "Ligands" here refer to non-polymer entities in the PDB hierarchy. The script enumerates non-polymer entity IDs from the entry container identifiers and queries each nonpolymer entity object.
- **File formats**: Prefer mmCIF for robustness; legacy PDB may be incomplete or unavailable for some entries.
- **Quality selection**: For drug discovery, do not select structures using resolution alone -- use wwPDB validation reports and ligand-quality metrics when available.
- **Environment**: Requires the `base-agent` conda environment.
---

**Author:** Matthew Cox  
**Contact:** [GitHub @mcox3406](https://github.com/mcox3406)
