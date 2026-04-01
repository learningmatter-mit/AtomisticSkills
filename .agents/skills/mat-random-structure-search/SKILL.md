---
name: mat-random-structure-search
description: Generate random crystal structures for a given composition (AIRSS-style) and relax with MLIPs to find low-energy candidates.
category: [materials]
---

# Random Structure Search (AIRSS-Style)

## Goal

To perform random structure searching (RSS) for a given chemical composition — the approach pioneered by AIRSS (Ab Initio Random Structure Searching, Pickard & Needs 2011). Random crystal structures are generated with sensible geometric constraints, then relaxed with an MLIP to identify low-energy candidates.

> [!TIP]
> This method is complementary to [ionic substitution](../mat-ionic-substitution/SKILL.md) and generative models like [MatterGen](../ml-generative-mattergen/SKILL.md) and [DiffCSP++](../ml-generative-diffcsp/SKILL.md). RSS explores the full potential energy surface without structural bias.

## Instructions

1. **Generate random structures** for the target composition:
   ```bash
   # Env: base-agent
   python .agents/skills/mat-random-structure-search/scripts/generate_random_structures.py \
       --composition NaCl \
       --num_structures 100 \
       --output_dir random_NaCl/
   ```

   The script will:
   - Sample random space groups from a list of common inorganic crystal space groups
   - Generate random lattice parameters consistent with each crystal system
   - Place atoms at random fractional coordinates
   - Filter structures for minimum interatomic distances
   - Save CIF files and a `generation_manifest.json`

   **Optional parameters:**
   - `--spacegroups 225,166,62,14` — restrict to specific space groups
   - `--volume_min 0.6 --volume_max 1.8` — control volume randomization range
   - `--seed 42` — set random seed for reproducibility

2. **Relax all structures** with an MLIP:
   ```bash
   mcp_mace_relax_structure(
       structure_data="random_NaCl/",
       relax_cell=True,
       fmax=0.02,
       steps=500,
       output_dir="relaxed_NaCl/"
   )
   ```
   
   Or with MatGL/FairChem — use the same MLIP consistently.

3. **Rank by energy**: The lowest-energy relaxed structures are the most promising candidates. Check for duplicate structures using pymatgen's `StructureMatcher`.

4. **Validate top candidates**: Compute [stability (E_hull)](../mat-stability/SKILL.md) for the best candidates to assess thermodynamic viability.

## Examples

### Example 1: Search for NaCl ground state
```bash
# Env: base-agent
python .agents/skills/mat-random-structure-search/scripts/generate_random_structures.py \
    --composition NaCl \
    --num_structures 100 \
    --seed 42 \
    --output_dir random_NaCl/
```
Expected: Rocksalt (SG 225) should emerge as the lowest-energy structure after MLIP relaxation.

### Example 2: Search for Li₂ZrCl₆ polymorphs
```bash
# Env: base-agent
python .agents/skills/mat-random-structure-search/scripts/generate_random_structures.py \
    --composition Li2ZrCl6 \
    --num_structures 200 \
    --spacegroups 12,14,62,148,166,167 \
    --output_dir random_Li2ZrCl6/
```

## Constraints

- **Not a DFT method**: Unlike true AIRSS, this skill uses MLIPs for relaxation. The accuracy depends on the MLIP's quality for the target chemistry.
- **No symmetry enforcement**: Generated structures have atoms at random positions (P1). Symmetry emerges only after relaxation.
- **Volume range**: The default volume range (0.6–1.8× estimated) covers most reasonable crystal packings. Extreme chemistries (e.g., heavy elements, molecular crystals) may need adjusted ranges.
- **Scalability**: Generation is fast (~100 structures/second), but MLIP relaxation is the bottleneck. For large-scale searches, use batch relaxation via MCP tools.
- **Duplicate removal**: After relaxation, use `StructureMatcher` to remove duplicate structures that converge to the same minimum.

## References

- Pickard, C. J., & Needs, R. J. (2011). Ab initio random structure searching. *Journal of Physics: Condensed Matter*, 23(5), 053201. [DOI: 10.1088/0953-8984/23/5/053201](https://doi.org/10.1088/0953-8984/23/5/053201)

---

**Author:** Bowen Deng  
**Contact:** [GitHub @bowen-bd](https://github.com/bowen-bd)
