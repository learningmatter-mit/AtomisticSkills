---
name: chem-bond-dissociation
description: Calculate homolytic bond dissociation energies (BDEs) for all single bonds in a molecule using MLIPs with RDKit fragmentation.
category: [chemistry]
---

# Bond Dissociation Energy Skill

## Goal

Calculate the homolytic bond dissociation energy (BDE) for each single bond in a molecule using Machine Learning Interatomic Potentials (MLIPs). The BDE is defined as:

$$\text{BDE}(A{-}B) = E(A\bullet) + E(B\bullet) - E(A{-}B)$$

where $A\bullet$ and $B\bullet$ are the radical fragments produced by homolytic cleavage. This enables rapid identification of the **weakest bond** (most reactive site) in a molecule.

> [!IMPORTANT]
> This skill computes BDEs by relaxing both the intact molecule and radical fragments with an MLIP. For purpose-trained GNN models that predict BDE directly from SMILES (MAE ~0.6 kcal/mol), consider [ALFABET](https://bde.ml.nrel.gov) or BonDNet instead.

## Background

BDE is a fundamental thermodynamic quantity that determines:
- **Drug metabolism**: CYP450 enzymes abstract H from the weakest C–H bond
- **Electrolyte stability**: Which bonds break first under electrochemical voltage
- **Combustion chemistry**: Rate-determining bond-breaking steps in fuel oxidation
- **Polymer degradation**: Weakest links in polymer backbone chains

A 2024 study (Zubatyuk et al., *JCTC*) demonstrated that MACE potentials achieve BDE RMSE of 1.37 kcal/mol for aliphatic C–H bonds in drug-like molecules, outperforming semi-empirical methods and ALFABET for BDE **ranking**.

## 1. Prerequisites

- **Conda Environment**: `mace-agent` (includes RDKit, ASE, and MACE)
- **Input**: SMILES string or structure file (`.xyz`, `.sdf`, `.mol2`)
- **RDKit**: Required for bond identification and molecular fragmentation

## 2. Choosing a Foundation Potential

Refer to the [foundation-potentials skill](../ml-foundation-potentials/SKILL.md) for model selection.

> [!IMPORTANT]
> For organic molecules, use `MACE-OFF23` models (trained on organic chemistry data including radical species). For inorganic or mixed systems, use `MACE-OMAT` or `MACE-MH-1`.

## 3. Calculation Workflow

### Step 1: Provide a molecule

Specify a SMILES string or structure file:
```bash
# SMILES input (most common)
--smiles "CCO"

# Or from a structure file
--structure molecule.xyz
```

### Step 2: Run BDE calculation

```bash
# Env: mace-agent
python .agents/skills/chem-bond-dissociation/scripts/calculate_bde.py \
    --smiles CCO \
    --all_bonds \
    --model_type mace \
    --model_name MACE-OFF23-small \
    --output_dir research/my_folder/bde_results
```

To compute BDE for a specific bond only:
```bash
# Env: mace-agent
python .agents/skills/chem-bond-dissociation/scripts/calculate_bde.py \
    --smiles CCO \
    --bond 0-1 \
    --model_type mace \
    --model_name MACE-OFF23-small \
    --output_dir research/my_folder/bde_cc_bond
```

### Key Parameters

| Argument | Default | Description |
|:---|:---|:---|
| `--smiles` | — | SMILES string of the molecule |
| `--structure` | — | Path to structure file (alternative to SMILES) |
| `--bond` | — | Specific bond as atom indices `"i-j"` (0-indexed, heavy atoms) |
| `--all_bonds` | `True` | Compute BDE for all single bonds |
| `--include_h_bonds` | `False` | Include X–H bonds (by default only heavy-atom bonds) |
| `--model_type` | `mace` | MLIP backend (`mace`, `matgl`, `fairchem`) |
| `--model_name` | `MACE-OFF23-small` | Specific model checkpoint |
| `--fmax` | `0.01` | Force convergence for relaxation (eV/Å) |
| `--output_dir` | required | Output directory |

## 4. Output Files

- `bde_results.json`: Summary including:
  - `intact_energy_eV`: Energy of the relaxed intact molecule
  - `bonds`: List of bond results, each containing:
    - `bond_index`: RDKit bond index
    - `atom_indices`: `[i, j]` (0-indexed including H)
    - `atom_symbols`: `["C", "O"]`
    - `bond_type`: `"SINGLE"`, etc.
    - `in_ring`: Whether the bond is in a ring
    - `bde_eV`, `bde_kJ_mol`, `bde_kcal_mol`: BDE in various units
    - `frag1_formula`, `frag2_formula`: Fragment compositions
    - `frag1_energy_eV`, `frag2_energy_eV`: Fragment energies
  - `weakest_bond`: The bond with the lowest BDE
  - Metadata: model, SMILES, parameters

- `intact_relaxed.xyz`: Relaxed intact molecule
- `frag_*.xyz`: Relaxed fragment structures

## 5. Examples

### Ethanol BDE Analysis

See `examples/ethanol/` for a complete example:

```bash
# Env: mace-agent
python .agents/skills/chem-bond-dissociation/scripts/calculate_bde.py \
    --smiles CCO \
    --all_bonds \
    --include_h_bonds \
    --model_type mace \
    --model_name MACE-OFF23-small \
    --output_dir .agents/skills/chem-bond-dissociation/examples/ethanol
```

Experimental BDEs for ethanol (Blanksby & Ellison, 2003):
| Bond | Experimental BDE (kcal/mol) |
|:---|:---|
| O–H | ~104 |
| C–H (methyl) | ~101 |
| C–H (methylene) | ~95 |
| C–C | ~85 |
| C–O | ~92 |

## 6. Constraints

- **Radical spin states**: MLIPs are generally "electron-agnostic" and may not correctly capture spin-state effects. BDE **ranking** (which bond is weakest) is typically more reliable than absolute BDE values.
- **Ring bonds**: Breaking bonds in rings produces a single open-chain diradical, not two separate fragments. The script will warn about ring bonds and skip them by default.
- **Accuracy**: Expect ~2–5 kcal/mol error vs. experiment for well-behaved organic molecules with MACE-OFF23. Absolute accuracy is worse than purpose-trained GNNs (ALFABET: ~0.6 kcal/mol).
- **Environments**: Scripts require conda environments with MLIP packages:
  - `mace-agent` for MACE models
  - `matgl-agent` for MatGL/CHGNet models
  - `fairchem-agent` for FairChem/UMA models

## References

- Blanksby & Ellison, "Bond Dissociation Energies of Organic Molecules", *Acc. Chem. Res.* **2003**, 36, 255.
- St. John et al., "Prediction of organic homolytic bond dissociation enthalpies at near chemical accuracy with sub-second computational cost", *Nat. Commun.* **2020**, 11, 2328. (ALFABET)
- Zubatyuk et al., "A Transferable MACE Potential for Open- and Closed-Shell Drug-Like Molecules", *J. Chem. Theory Comput.* **2024**.

---

**Author:** Bowen Deng  
**Contact:** [GitHub @bowen-bd](https://github.com/bowen-bd)
