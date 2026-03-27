---
name: mat-synthesis-recommendation
description: Query and rank synthesis recipes from Materials Project's text-mined literature database with precursors, procedures, and journal references.
category: [materials]
---

# Synthesis Recommendation

## Goal

To provide experimentally validated synthesis routes for target inorganic materials by querying Materials Project's text-mined database of synthesis recipes extracted from scientific literature. This skill returns precursor materials, synthesis procedures, reaction equations, and DOI references to published papers.

## Instructions

### 1. Query Synthesis Recipes

Search for synthesis recipes for a target material using the Materials Project API:

```bash
# Env: base-agent
python .agents/skills/mat-synthesis-recommendation/scripts/recommend_synthesis.py "LiFePO4" --limit 10 --output synthesis_recipes.json
```

**Parameters:**
- `formula`: Target material formula (e.g., `"LiFePO4"`, `"Li2CO3"`, `"NMC811"`)
- `--limit`: Maximum number of recipes to display (default: 10)
- `--output`: Optional JSON file to save results
- `--type`: Filter by synthesis type (e.g., `"solid-state"`, `"hydrothermal"`, `"sol-gel"`)
- `--min-temp`: Minimum synthesis temperature in °C
- `--max-temp`: Maximum synthesis temperature in °C

**Output:** Recipes are automatically ranked by:
1. **Simplicity**: Fewer precursors preferred
2. **Temperature**: Lower synthesis temperatures preferred
3. **Synthesis type**: Common methods (solid-state, hydrothermal) ranked higher

### 2. Interpret Results

Each recipe contains:
- **Target material**: Normalized chemical formula
- **Precursors**: Starting materials/reagents
- **Synthesis type**: Method category (solid-state, hydrothermal, sol-gel, etc.)
- **Procedure**: Step-by-step synthesis description from the paper
- **Reaction equation**: Balanced chemical equation (when available)
- **DOI**: Link to the source publication for full experimental details

### 3. Validate Synthesis Feasibility (Optional)

Cross-check the recommended precursors with other skills:

```bash
# Check if target material is thermodynamically stable
# See: ../mat-stability/SKILL.md
python .agents/skills/mat-stability/scripts/calculate_stability.py target.cif --output stability_analysis.json

# Calculate formation energy to verify synthesizability
# Energy above hull (E_hull) < 0.1 eV/atom indicates likely synthesizability
```

## Examples

### Example 1: Basic Query for LiFePO4

```bash
# Env: base-agent
python .agents/skills/mat-synthesis-recommendation/scripts/recommend_synthesis.py "LiFePO4" --limit 5
```

**Expected output:**
- 5 synthesis recipes ranked by simplicity
- Common precursors: Li₂CO₃, FeC₂O₄, NH₄H₂PO₄
- Typical methods: solid-state reaction, hydrothermal synthesis
- DOI links to papers in *J. Electrochem. Soc.*, *Chem. Mater.*, etc.

### Example 2: Filter by Synthesis Type

```bash
# Env: base-agent
# Query only hydrothermal synthesis routes for LiCoO2
python .agents/skills/mat-synthesis-recommendation/scripts/recommend_synthesis.py "LiCoO2" --type hydrothermal --limit 10 --output LiCoO2_hydrothermal.json
```

### Example 3: Temperature-Constrained Search

```bash
# Env: base-agent
# Find low-temperature synthesis routes (< 600°C) for Li2CO3
python .agents/skills/mat-synthesis-recommendation/scripts/recommend_synthesis.py "Li2CO3" --max-temp 600 --limit 10
```

## Constraints

- **API Key Required**: Requires Materials Project API key via `MP_API_KEY` environment variable or `~/.atomistic_skills.yaml` configuration
- **Conda Environment**: This skill requires the `base-agent` environment (includes `mp-api`, `pymatgen`)
- **Coverage Limitations**: Not all materials have synthesis recipes in the database
  - Database contains ~55,000 recipes for common inorganic materials
  - Coverage is best for battery materials, ceramics, and metal oxides
  - Organic materials and MOFs have limited coverage
- **Text-Mining Accuracy**: Recipes are automatically extracted from literature using NLP
  - Precursors and procedures are generally accurate but should be verified against the source DOI
  - Temperature values may be missing or incomplete in some entries
- **Data Freshness**: The text-mined database is periodically updated but may not include the most recent publications

## Data Source

The synthesis recipes are extracted from scientific literature using natural language processing by the Materials Project team. The underlying datasets include:

- **Solid-state synthesis**: 19,488+ recipes from the CederGroup text-mined database
- **Solution-based synthesis**: 35,675+ recipes for solution, hydrothermal, and sol-gel methods
- **NLP pipeline**: Transformer-based models for paragraph classification, named entity recognition, and synthesis action extraction

**References:**
- Materials Project Synthesis Explorer: https://materialsproject.org/synthesis
- Text-mined synthesis datasets: [CederGroup GitHub](https://github.com/CederGroupHub/text-mined-synthesis_public)
- Kim et al., "A Database of Synthesis Recipes for Inorganic Materials," *Sci. Data* (2017)

## Related Skills

- [mat-stability](../mat-stability/SKILL.md): Verify thermodynamic stability before attempting synthesis
- [mat-intercalation-voltage](../mat-intercalation-voltage/SKILL.md): Calculate electrochemical properties of synthesized cathode materials
---

**Author:** Bowen Deng  
**Contact:** [GitHub @bowen-bd](https://github.com/bowen-bd)
