---
name: mat-ionic-substitution
description: Discover new crystal structures by data-mined ionic substitution — propose candidates from existing structures (forward) or find potential structures for a target composition (reverse).
category: [materials]
---

# Ionic Substitution

## Goal

To discover new crystal structures using data-mined ionic substitution (Hautier et al. 2011). Two modes:

1. **Forward (propose)**: Given an existing structure, propose all high-probability ion-substituted variants. E.g., input NaCoO₂ → get LiCoO₂, KCoO₂, NaNiO₂, etc.
2. **Reverse (find)**: Given a target composition, find all known crystal structures that can be ion-substituted to create it, plus direct matches from Materials Project.

The substitution probability model is trained on the ICSD (Inorganic Crystal Structure Database) and captures empirical chemical rules about which ions commonly substitute for each other.

> [!TIP]
> After generating candidate structures, relax them with an MLIP and compute their [stability (E_hull)](../mat-stability/SKILL.md) to prioritize the most thermodynamically viable candidates.

## Instructions

### Mode 1: Forward — Propose substitutions from a structure

1. **Prepare a source structure** (CIF or POSCAR). Ensure it is an ordered structure.

2. **Run the forward proposal script**:
   ```bash
   # Env: base-agent
   python .agents/skills/mat-ionic-substitution/scripts/propose_substitutions.py \
       --structure source.cif \
       --threshold 0.001 \
       --output_dir proposed_substitutions/
   ```

   The script will:
   - Auto-decorate the structure with oxidation states (if not already present)
   - Enumerate all charge-balanced ionic substitutions above the threshold
   - Handle single-ion, double-ion, and multi-ion swaps
   - Save each substituted structure as a CIF file
   - Generate a `substitution_manifest.json` with substitution maps and probabilities

3. **Review and filter results**: Higher probability → more likely to be stable. Relax top candidates with an MLIP.

### Mode 2: Reverse — Find structures for a target composition

1. **Run the reverse search script**:
   ```bash
   # Env: base-agent
   python .agents/skills/mat-ionic-substitution/scripts/find_structures_for_composition.py \
       --composition LiCl \
       --threshold 0.001 \
       --output_dir structures_for_LiCl/
   ```

   The script will:
   - **Step A**: Query Materials Project for existing structures with the target formula
   - **Step B**: Use `SubstitutionPredictor` to find precursor compositions whose ions map to the target
   - **Step C**: Fetch precursor structures from MP and apply the substitutions
   - Save all candidate CIF files and a `structure_manifest.json` with full provenance

2. **Interpret results**: Each candidate includes:
   - Source: `"materials_project"` (direct match) or `"substitution"` (derived)
   - Substitution map: e.g., `{Na+→Li+}` and probability
   - Precursor MP material ID for traceability

### Mode 3: Manual Targeted Substitution via MCP

If you already know the exact substitution you want to make on a specific structure, you can immediately generate the new structure using the base MCP server's `modify_structure` tool:

- **`modify_structure` tool**: Maps an existing element to a new element or fraction.
  - Example 1 (Full replacement): `substitution_dict_json='{"Na": "Li"}'` (Replaces all Na with Li)
  - Example 2 (Partial/Alloying): `substitution_dict_json='{"Na": {"Li": 0.5, "Na": 0.5}}'` (Creates a 50/50 random mixture)

## Examples

### Example 1: Discover new Li-ion cathode from NaCoO₂
```bash
# Env: base-agent
python .agents/skills/mat-ionic-substitution/scripts/propose_substitutions.py \
    --structure NaCoO2.cif \
    --threshold 0.001 \
    --output_dir NaCoO2_substitutions/
```
Expected output includes: LiCoO₂, KCoO₂, NaNiO₂, NaMnO₂, LiNiO₂, etc.

### Example 2: Find all crystal structures for LiCl
```bash
# Env: base-agent
python .agents/skills/mat-ionic-substitution/scripts/find_structures_for_composition.py \
    --composition LiCl \
    --output_dir LiCl_structures/
```
Expected output includes: LiCl from MP + NaCl(Na→Li), KCl(K→Li), NaBr(Na→Li, Br→Cl), etc.

## Constraints

- **Oxidation States**: The probability model requires oxidation-state-decorated structures. The scripts auto-decorate using pymatgen's `AutoOxiStateDecorationTransformation`, but exotic compositions may fail.
- **Charge Balance**: Only charge-balanced substitutions are returned. This is enforced automatically.
- **Threshold**: Default 0.001. Lower values (e.g., 0.0001) find more candidates but include less probable substitutions. Higher values (e.g., 0.01) give fewer, more confident results.
- **MP API Key**: The reverse script requires `MP_API_KEY` environment variable to query Materials Project.
- **Structure Count**: The number of species in the structure determines the combinatorial space. Structures with 2–3 unique species work best; structures with 5+ species may produce very large result sets.
- **Relaxation**: Generated structures are **not relaxed**. Always relax with an MLIP before drawing conclusions about stability.

## References

- Hautier, G., Fischer, C., Ehrlacher, V., Jain, A., & Ceder, G. (2011). Data Mined Ionic Substitutions for the Discovery of New Compounds. *Inorganic Chemistry*, 50(2), 656–663. [DOI: 10.1021/ic102031h](https://doi.org/10.1021/ic102031h)

---

**Author:** Bowen Deng  
**Contact:** [GitHub @bowen-bd](https://github.com/bowen-bd)
