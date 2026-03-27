---
name: mat-pourbaix-diagram
description: Calculate Pourbaix (pH-voltage) diagrams for aqueous electrochemical stability using water-corrected MLIP energies and pymatgen.
category: [materials]
---

# Pourbaix Diagram

## Goal

To calculate thermodynamically consistent Pourbaix (pH-voltage) diagrams for assessing the aqueous electrochemical stability of materials. This skill uses Machine Learning Interatomic Potentials (MLIPs) for solid phase energies combined with Materials Project data for aqueous species, following the rigorous methodology of Persson et al. (2012)¹.

**Applications**:
- Alkaline-stable solid-state electrolytes (Li-air batteries)
- Corrosion-resistant materials
- Aqueous battery electrodes
- Electrochemical stability screening

## Features

- **Automated Referenced**: Fetches elemental energies from `elemental-energies` skill to fill missing terminal entries (e.g., if you relaxed `LiCoO2` but forgot `Li` metal, it will be auto-loaded).
- **H2O Reference**: Checks `resources/h2o_energies.json` values matching the MLIP checkpoint. If found, uses this pre-calculated energy. If not found, falls back to look for `H2O` relaxation in the `--relaxed_solids` directory.
- **MP2020 Compatibility**: Automatically detects if compatibility corrections are needed via `gga-ggau-mixed-mlips.yaml`.

## Background

### Pourbaix Diagrams

A Pourbaix diagram shows the thermodynamically stable phases as a function of pH and electrochemical potential (voltage vs. SHE). The diagram maps stability domains for solids and dissolved ions in aqueous environments.

### Critical: Thermodynamic Consistency

**The Challenge**: Mixing computational (MLIP/DFT) solid energies with experimental aqueous ion data creates energy scale mismatch.

**The Solution** (Persson et al. 2012)¹: **Water correction** that aligns MLIP water formation energy with experimental Gibbs free energy.
We use a robust cycle that fixes the hydrogen reference to the Standard Hydrogen Electrode (SHE) scale.

### 3. Automated Referencing

The script `calculate_pourbaix.py` automatically:
1. Fetches per-atom elemental energies from the `elemental-energies` skill.
2. Applies thermodynamic corrections for H₂ gas ($S^\circ$, $\Delta H$) to deriving $\mu_H$.
3. Uses a locally relaxed H₂O structure to derive $\mu_O$, ensuring correct water formation energy.
   *   **H2O Reference**: Checks `resources/h2o_energies.json` values matching the MLIP checkpoint. If found, uses this pre-calculated energy. If not found, falls back to look for `H2O` relaxation in the `--relaxed_solids` directory.

**Is `calculate_water_correction.py` still needed?**
**No**. The correction logic is now internal to `calculate_pourbaix.py` to simplify the workflow.

## Resources

- `resources/h2o_energies.json`: A dictionary mapping MLIP checkpoint names (e.g., `MACE-MP-medium`, `uma-s-1_omat`) to the relaxed energy of H2O per atom. This avoids the need for manual H2O relaxation when using supported MLIPs.


## Methods: MLIP vs. Pure Materials Project

There are two ways to generate Pourbaix diagrams using this skill. **Prioritize Method 1 (Pure MP)** if the target chemical system's energies are likely present and accurate in the Materials Project database. Use Method 2 (MLIP) when investigating novel materials, specific polymorphs not in MP, or when high-fidelity MLIP energies are preferred.

### Method 1: Pure Materials Project (Recommended for existing materials)

Use `calculate_pourbaix_mp.py` to fetch entries directly from Materials Project. This requires no local relaxation and uses MP's internal DFT energies.

```bash
# Env: base-agent
python .agents/skills/mat-pourbaix-diagram/scripts/calculate_pourbaix_mp.py \
    --comp_dict "Li=1,Fe=1" \
    --output ./output_dir
```

### Method 2: MLIP-Calculated Workflow (For novel/specific structures)

Use this workflow to calculate stability using specific MLIP models. This involves fetching structures, relaxing them, and then generating the diagram.

#### 1. Get Structures from Materials Project

Query all relevant solid phases and reference molecules:

```bash
# Env: base-agent
python .agents/skills/mat-pourbaix-diagram/scripts/get_pourbaix_structures.py \
    --chemsys "Zn" \
    --output_dir ./structures/
```

This retrieves:
- All solid phases in the chemical system (e.g., Zn, ZnO, ZnO2, etc.)
- Reference molecule: H₂O (Required for water correction)

#### 2. Select Foundation Potential

Choose an appropriate MLIP based on your system (see `.agents/skills/ml-foundation-potentials/SKILL.md`).

> [!IMPORTANT]
> **Recommended for Pourbaix diagrams: MatPES-r2SCAN**
> To ensure energy scale compatibility with Materials Project aqueous ions (which are often based on r2SCAN or compatible corrections), prioritize using **r2SCAN-trained MLIPs**.
> - **MatGL**: `CHGNet-MatPES-r2SCAN-2025.2.10-2.7M-PES`
> - **MACE**: `MACE-MH-1` with `matpes_r2scan` head.


#### 3. Relax Reference H₂O

The script `get_pourbaix_structures.py` automatically copies H₂O into the `references/` subdirectory.
Relax it using the same MLIP model to allow internal calibration:

```python
# Example with FairChem UMA-small (recommended)
mcp_fairchem_load_model(model_name="uma-s-1p1")

# Relax H2O reference
mcp_fairchem_relax_structure(
    structure_data="./structures/references/H2O.cif",
    fmax=0.02,        
    steps=500,
    relax_cell=True,
    output_dir="./relaxed_solids/" # SAVE TO SAME DIR AS SOLIDS
)
```

**Critical**: Use `fmax ≤ 0.02 eV/Å` for reliable energies.
**Note**: H₂ and O₂ references are NOT required to be relaxed locally because the script uses pre-computed elemental energies for gas phase corrections. Only H₂O is needed for determining the specific water formation energy offset.

#### 4. Relax Solid Phases

Relax all solid phases (and included H2O) using the **same MLIP**:

```python
# Batch relax all solids with same MLIP
# (Model already loaded from step 3)
mcp_fairchem_relax_structure(
    structure_data="./structures/structures/",  # Directory with all CIF files
    relax_cell=True,
    fmax=0.02,
    steps=500,
    output_dir="./relaxed_solids/"
)
```

**Critical**: Use the **same MLIP model** for molecules and solids!

#### 5. Calculate Pourbaix Diagram

Construct the diagram using automated referencing (fetching elemental energies and deriving corrections internally):

```bash
# Env: base-agent
python .agents/skills/mat-pourbaix-diagram/scripts/calculate_pourbaix.py \
    --relaxed_solids ./relaxed_solids/ \
    --target "Zn" \
    --mlip_name "uma-s-1p1" \
    --output ./pourbaix_results/ \
    --apply_solid_compat
```

**Parameters**:
- `--relaxed_solids`: Directory with MLIP-relaxed solid structures (MUST include the relaxed H2O)
- `--target`: Target metal element (or use `--comp_dict` for multi-element)
- `--comp_dict`: (Optional) Composition dictionary for K-nary systems (e.g. "Li=1,Fe=1")
- `--mlip_name`: Name for the plot title (and for looking up elemental energies)
- `--output`: Output directory
- `--apply_solid_compat`: (Optional) Apply Materials Project 2020 compatibility corrections. **Use only if your MLIP is trained on MP data (e.g. MACE-MP, CHGNet)**. Do NOT use for UMA or generic potentials unless verified.
- `--ion_concentration`: Ion concentration in M (default: 1e-6)


**Critical**: Use the **same MLIP** for all structures in a single workflow!

### 6. Interpret Results

The scripts generate:
- `pourbaix_diagram.png`: Visual representation
- `stable_entries.json`: List of all stable phases in the diagram
- Stability domains for each phase across pH/V space

**Interpretation**:
- **Solid domain**: Material is thermodynamically stable as a solid
- **Ion domain**: Material dissolves into aqueous ions
- **Passivation**: Material covered by protective oxide layer

## Constraints

- **Energy Consistency**: All structures (molecules + solids) MUST be relaxed with the **same MLIP model**.
- **Water Correction**: REQUIRED for thermodynamic consistency. Skipping water correction will produce incorrect diagrams.
- **Convergence**: Use `fmax ≤ 0.02 eV/Å` for both molecules and solids.
- **Chemical System**: Automatically determined from target material and MP ion data.
- **Temperature**: Calculations assume 298 K (25°C).
- **Reference Electrode**: Results are vs. Standard Hydrogen Electrode (SHE).
- **Materials Project Access**: Requires `MP_API_KEY` environment variable.
- **DFT Validation**: For publication-quality results, validate critical stability boundaries with DFT.

## Theoretical Background

Following Persson et al. (2012)¹, the grand Pourbaix potential is:

```
ϕ_pbx = G - μ_H·N_H - μ_O·N_O - eV·Q
```

The water correction aligns MLIP solid energies (computational scale) with MP aqueous ion free energies (experimental scale) by enforcing:

```
ΔGf(H₂O)_corrected = -2.4583 eV (experimental)
```

This allows thermodynamically consistent mixing of:
- MLIP total energies for solids
- MP Gibbs free energies for aqueous ions

## References

1. **K. A. Persson, B. Waldwick, P. Lazic, G. Ceder.** "Prediction of solid-aqueous equilibria: Scheme to combine first-principles calculations of solids with experimental aqueous states." *Physical Review B* **85**, 235438 (2012). [DOI:10.1103/PhysRevB.85.235438](https://doi.org/10.1103/PhysRevB.85.235438)

2. **Hierarchical screening methodology**: [arXiv:2511.20964](https://arxiv.org/abs/2511.20964)

3. **Pymatgen Pourbaix module**: https://pymatgen.org/pymatgen.analysis.pourbaix_diagram.html

4. **Related skills**: 
   - [mat-stability](../mat-stability/SKILL.md) for convex hull calculations
   - [mat-elemental-energies](../mat-elemental-energies/SKILL.md) for retrieving pre-calculated elemental reference energies required for formation energy calculations.
---

**Author:** Bowen Deng  
**Contact:** [GitHub @bowen-bd](https://github.com/bowen-bd)
