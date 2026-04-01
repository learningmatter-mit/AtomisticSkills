---
name: drug-admet-prediction
description: Compute RDKit physicochemical descriptors and rule-based drug-likeness heuristics (Ro5, Veber, QED) from SMILES.
category: [drug-discovery]
---

# admet-prediction

## Goal
Compute ADMET-relevant **physicochemical descriptors** and **rule-based drug-likeness heuristics** from SMILES strings using RDKit.

This skill reports:
- Core descriptors: molecular weight (average and exact), Wildman-Crippen cLogP, TPSA, HBD/HBA, rotatable bonds, ring counts, aromatic rings, heavy atoms, fractionCSP3, molar refractivity.
- Heuristics:
  - **Lipinski Rule of Five (Ro5)** compliance (≤ 1 violation) as a permeability/absorption triage heuristic.
  - **Veber** oral bioavailability heuristic (RB ≤ 10 and TPSA ≤ 140 Å²; plus reporting the alternative HBD+HBA ≤ 12 condition).
  - **QED** (Quantitative Estimate of Drug-likeness) score.

> Note: This does **not** predict experimental ADMET endpoints (e.g., clearance, CYP inhibition, hERG, Ames, etc.). It is an early-stage physchem/heuristics screen.

## Instructions

The drugdisc MCP server provides a `compute_molecular_descriptors` tool that can be called directly:

**Single molecule analysis:**
```bash
mcp_drugdisc_compute_molecular_descriptors(
    smiles="CC(=O)Oc1ccccc1C(=O)O",
    output_file="aspirin_admet.json"
)
```

**Batch analysis from a SMILES file:**
```bash
mcp_drugdisc_compute_molecular_descriptors(
    smiles_file=".agents/skills/drug-admet-prediction/examples/compounds.smi",
    output_file="batch_admet.json"
)
```

**With S/P-inclusive TPSA:**
```bash
mcp_drugdisc_compute_molecular_descriptors(
    smiles="OC(=O)P(=O)(O)O",
    include_sandp_tpsa=True,
    output_file="foscarnet_admet.json"
)
```

## Examples

Example `compounds.smi`:
```text
CN1C=NC2=C1C(=O)N(C(=O)N2C)C	caffeine
CC(=O)Oc1ccccc1C(=O)O	aspirin
CC(C)Cc1ccc(cc1)C(C)C(=O)O	ibuprofen
```

Run:
```bash
mcp_drugdisc_compute_molecular_descriptors(
    smiles_file=".agents/skills/drug-admet-prediction/examples/compounds.smi",
    output_file="drug_admet.json"
)
```

## Constraints
- **MCP Server**: Requires `drugdisc` MCP server
- **Dependencies**: RDKit (Chem, Descriptors, Lipinski, Crippen, QED)
- **Scope**: Outputs physchem descriptors + rule-based heuristics only; not ML/experimental ADMET prediction
- **Ro5 interpretation**: A "pass" is defined here as **≤ 1 violation** (common industry convention)
- **Veber interpretation**: Primary check uses **TPSA ≤ 140 Å² and rotatable bonds ≤ 10**, and additionally reports the alternative **(HBD + HBA ≤ 12)** criterion
- **Standardization**: If SMILES contains multiple fragments (e.g., salts, "."), results are reported but flagged with a warning; consider desalting/neutralization upstream for library triage
- **TPSA option**: By default, TPSA uses RDKit's default behavior (no S/P); `include_sandp_tpsa=True` includes S/P contributions
---

**Author:** Matthew Cox  
**Contact:** [GitHub @mcox3406](https://github.com/mcox3406)
