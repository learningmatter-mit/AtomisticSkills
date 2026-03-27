---
name: drug-protein-prep
description: Prepare macromolecular receptor structures (PDB/mmCIF or RCSB PDB ID) for docking or simulation by fixing common structure issues and adding hydrogens.
category: [drug-discovery]
---

# protein-prep

## Goal
To prepare protein (and optionally nucleic acid) receptor structures for molecular docking (e.g., AutoDock Vina) by:
1) retrieving coordinates from RCSB PDB (optional),
2) fixing common structural issues (missing atoms, nonstandard residues),
3) adding hydrogens at a target pH.

> **Note**: This skill handles structure cleanup and protonation. To convert the result to **PDBQT** for docking, use the `mcp_drugdisc_convert_to_pdbqt` tool.

## Instructions

### 1. Prepare a receptor to PDB (Cleanup + Hydrogens)

This script manages missing atoms, nonstandard residues, and protonation.

```bash
# Env: drugdisc-agent
python .agents/skills/drug-protein-prep/scripts/prepare_protein.py \
  --pdb_id 1iep \
  --chains A \
  --ph 7.0 \
  --heterogens none \
  --missing_residues ignore \
  --output_dir protein_prep/
```

### 2. Convert to PDBQT (for AutoDock Vina)

Use the MCP tool to convert the prepared PDB to PDBQT format.

```bash
mcp_drugdisc_convert_to_pdbqt(
    input_data="protein_prep/1IEP_prepared.pdb",
    output_path="protein_prep/1IEP.pdbqt",
    input_type="pdb"
)
```

### 3. Keep cofactors/metal ions

```bash
# Env: drugdisc-agent
python .agents/skills/drug-protein-prep/scripts/prepare_protein.py \
  --pdb_id 1iep \
  --chains A \
  --heterogens non-water \
  --delete_resname SO4 GOL \
  --output_dir protein_prep_keep_cofactors/
```

### 4. Use a biological assembly (recommended when oligomerization matters)

```bash
# Env: drugdisc-agent
python .agents/skills/drug-protein-prep/scripts/prepare_protein.py \
  --pdb_id 1iep \
  --assembly 1 \
  --chains A \
  --output_dir protein_prep_assembly1/
```

### 5. Prepare from a local structure file

```bash
# Env: drugdisc-agent
python .agents/skills/drug-protein-prep/scripts/prepare_protein.py \
  --pdb_file receptor.pdb \
  --heterogens none \
  --output_dir protein_prep_local/
```

### 6. Validate the output (strongly recommended)

After preparation:

* Inspect the JSON summary for **missing residues**, **nonstandard residue replacements**, and **atoms added**.
* Visually inspect the binding site and check for:
  * correct oligomeric state,
  * retained/removed cofactors and metal ions,
  * sensible protonation (especially histidines),
  * alternate locations resolved appropriately.

If protonation is critical, consider a hydrogen optimization / pKa-aware tool (e.g., Reduce/Reduce2, PROPKA/PDB2PQR/H++), then regenerate PDBQT from the protonated receptor.

## Examples

### Full Workflow: HIV-1 Protease

1. Prepare the structure:

```bash
# Env: drugdisc-agent
python .agents/skills/drug-protein-prep/scripts/prepare_protein.py \
  --pdb_id 1hsg \
  --chains A B \
  --heterogens none \
  --ph 7.0 \
  --output_dir hiv_prep/
```

2. Convert to PDBQT:

```bash
mcp_drugdisc_convert_to_pdbqt(
    input_data="hiv_prep/1HSG_prepared.pdb",
    output_path="hiv_prep/1HSG.pdbqt",
    input_type="pdb"
)
```

## Constraints

* **Environment**: Requires `drugdisc-agent`.
* **Core dependencies**: `pdbfixer`, `openmm`.
* **Protonation**: Default pH-based hydrogen addition is a baseline.
* **Missing residues**: By default, missing residues are ignored to avoid introducing uncertain loop models.
* **PDBQT**: PDBQT conversion is delegated to the `mcp_drugdisc_convert_to_pdbqt` tool (which uses Meeko).
---

**Author:** Matthew Cox  
**Contact:** [GitHub @mcox3406](https://github.com/mcox3406)
