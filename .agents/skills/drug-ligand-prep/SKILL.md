---
name: drug-ligand-prep
description: Prepare small-molecule ligands for docking/analysis: optional state enumeration, 3D conformer generation, MMFF/UFF minimization, and export to SDF + AutoDock PDBQT.
category: [drug-discovery]
---

# Ligand Preparation

## Goal
To prepare small-molecule ligands for molecular docking and downstream analysis by:
1) optionally enumerating relevant ligand ionization states and tautomers,
2) generating 3D conformers with RDKit ETKDG (via MCP),
3) minimizing with MMFF94/UFF (via MCP),
4) exporting a docking-ready **PDBQT** (AutoDock-Vina) and an optimized **SDF** (via MCP).

This skill combines script-based state enumeration with MCP-based 3D generation to ensure reproducibility.

## Instructions

### 1. Enumerate States (Optional Batch Processing)

Use the script to process SMILES/SDF files and enumerate protonation/tautomer states. This outputs 2D SDFs.

```bash
# Env: drugdisc-agent
python .agents/skills/drug-ligand-prep/scripts/prepare_ligand.py \
  --smiles_file ligands.smi \
  --enumerate_protomers \
  --output_dir ligand_states/
```

### 2. Generate 3D Conformer and PDBQT (using MCP)

Use the `mcp_drugdisc_convert_to_pdbqt` tool to generate the final 3D docking input.

**From a single SMILES:**
```bash
mcp_drugdisc_convert_to_pdbqt(
    input_data="CC(=O)Oc1ccccc1C(=O)O",
    input_type="smiles",
    output_path="aspirin.pdbqt",
    num_confs=50
)
```

**From an SDF (e.g. output of Step 1):**
```bash
mcp_drugdisc_convert_to_pdbqt(
    input_data="ligand_states/ligand_001.sdf",
    input_type="sdf",
    output_path="ligand_001.pdbqt",
    num_confs=20
)
```

## Examples

### Prepare Ibuprofen

1. Enumerate inputs (if needed):
   ```bash
   python .agents/skills/drug-ligand-prep/scripts/prepare_ligand.py \
     --smiles "CC(C)Cc1ccc(cc1)[C@@H](C)C(=O)O" \
     --name ibuprofen \
     --output_dir prep_stages/
   ```

2. Generate PDBQT:
   ```bash
   mcp_drugdisc_convert_to_pdbqt(
       input_data="prep_stages/ibuprofen.sdf",
       input_type="sdf",
       output_path="prep_stages/ibuprofen.pdbqt",
       num_confs=50
   )
   ```

## Constraints

* **Environment**: Requires `drugdisc-agent`.
* **3D/PDBQT**: Delegated to `mcp_drugdisc_convert_to_pdbqt` (Meeko/RDKit).
* **State Enumeration**: The script handles batch enumeration of protonation/tautomer states, but 3D generation is done by the MCP tool.
---

**Author:** Matthew Cox  
**Contact:** [GitHub @mcox3406](https://github.com/mcox3406)
