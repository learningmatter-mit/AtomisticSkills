# HIV-1 Protease PDB Query Example

This example demonstrates searching the RCSB PDB for HIV-1 protease X-ray structures and retrieving metadata for a specific entry (1HSG), a protease-inhibitor complex.

## Files

- `hiv1_protease_search.json`: Keyword search for "HIV-1 protease" filtered to X-ray diffraction structures with resolution <= 2.0 A (top 5 hits)
- `1hsg_entry.json`: Detailed metadata for PDB entry 1HSG, including title, resolution, unit cell, and bound ligand (MK1 / indinavir)

## How to reproduce

From the project root:

```bash
# Env: base-agent
# Step 1: Search for HIV-1 protease structures
python .agents/skills/drug-db-pdb/scripts/query_pdb.py \
  --search "HIV-1 protease" \
  --method "X-RAY DIFFRACTION" \
  --resolution 2.0 \
  --max_results 5 \
  --output .agents/skills/drug-db-pdb/examples/hiv1_protease_search.json

# Step 2: Fetch metadata for a specific entry
python .agents/skills/drug-db-pdb/scripts/query_pdb.py \
  --pdb_id 1HSG \
  --output .agents/skills/drug-db-pdb/examples/1hsg_entry.json
```

## Results

Step 1 returns 5 high-resolution X-ray structures:

| PDB ID | Resolution (A) | Ligand | Title (abbrev.) |
|---|---|---|---|
| 1TW7 | 1.30 | NA (sodium) | Wide open multi-drug resistant HIV-1 protease |
| 4RVI | 1.99 | GRL0519 | MDR clinical isolate + non-peptidic inhibitor |
| 4NJV | 1.80 | Ritonavir | MDR clinical isolate + ritonavir |
| 4RVX | 1.96 | GRL079 | MDR clinical isolate + non-peptidic inhibitor |
| 5T84 | 1.65 | (none) | Unbound subtype B L63P construct |

Step 2 returns metadata for 1HSG: HIV-II protease complexed with L-735,524 (indinavir precursor) at 2.0 A resolution, with one bound ligand (MK1).
