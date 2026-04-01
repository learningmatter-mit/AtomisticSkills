---
name: mat-db-mp
description: Query Materials Project database for crystal structures, computed properties, elastic/magnetic data, and structurally similar materials using the MP API.
category: [materials]
---

# Materials Project Database Query

## Goal

To retrieve crystal structures and computed properties from the Materials Project database, enabling efficient materials discovery and property analysis. This skill provides access to:
- Basic material properties (energy above hull, formation energy, band gap)
- Elastic properties (bulk modulus, shear modulus, elastic tensors)
- Magnetic properties (magnetic ordering, magnetization, site moments)
- Structure similarity search (CrystalNN-based fingerprinting)

**Note**: For quick structure retrieval by formula or chemical system, MCP tools are also available (see [MCP Tools](#mcp-tools-for-quick-retrieval) section).

## Instructions

### 1. Query Materials by Chemical System or Formula

Use `query_mp.py` to search for materials by chemical system, formula, or elements with property filtering.

**Basic Query (Summary Endpoint)**:
```bash
# Env: base-agent
python .agents/skills/mat-db-mp/scripts/query_mp.py \
    --chemsys "Li-S" \
    --properties energy_above_hull formation_energy_per_atom band_gap \
    --e_above_hull_max 0.05 \
    --limit 10 \
    --endpoint summary \
    --output stable_li_s_materials.json
```

**Detailed Thermodynamic Data (Thermo Endpoint)**:
```bash
# Env: base-agent
python .agents/skills/mat-db-mp/scripts/query_mp.py \
    --chemsys "Li-O" \
    --endpoint thermo \
    --limit 20 \
    --output li_o_thermo.json
```

**Key Parameters**:
- `--chemsys`: Chemical system (e.g., "Li-S", "Si-O")
- `--formula`: Specific chemical formula (e.g., "LiFePO4")
- `--elements`: List of elements that must be present
- `--properties`: Properties to retrieve (default: energy_above_hull, formation_energy_per_atom)
- `--e_above_hull_max`: Maximum energy above hull for stability filtering (eV/atom)
- `--endpoint`: Choose `summary` (includes structures) or `thermo` (detailed thermodynamics, no structures)
- `--limit`: Maximum number of results to retrieve

**Output**: JSON file containing material IDs, formulas, CIF strings (summary endpoint), and requested properties.

### 2. Query Elastic Properties

Use `get_elasticity.py` to retrieve bulk modulus, shear modulus, and elastic tensor data.

**Query Specific Material**:
```bash
# Env: base-agent
python .agents/skills/mat-db-mp/scripts/get_elasticity.py \
    --material_id mp-149 \
    --output si_elasticity.json
```

**Filter by Bulk Modulus Range**:
```bash
# Env: base-agent
python .agents/skills/mat-db-mp/scripts/get_elasticity.py \
    --bulk_modulus_min 200 \
    --bulk_modulus_max 400 \
    --output high_bulk_modulus.json
```

**Key Parameters**:
- `--material_id`: Specific MP ID(s) to query
- `--bulk_modulus_min/max`: Bulk modulus (VRH) range in GPa
- `--shear_modulus_min/max`: Shear modulus (VRH) range in GPa

**Output**: JSON file with bulk modulus, shear modulus (Voigt, Reuss, VRH averages), and full elastic tensor.

### 3. Query Magnetic Properties

Use `get_magnetism.py` to retrieve magnetic ordering, magnetization, and site-specific magnetic moments.

**Query Specific Material**:
```bash
# Env: base-agent
python .agents/skills/mat-db-mp/scripts/get_magnetism.py \
    --material_id mp-19770 \
    --output fe2o3_magnetism.json
```

**Filter by Magnetic Ordering and Magnetization**:
```bash
# Env: base-agent
python .agents/skills/mat-db-mp/scripts/get_magnetism.py \
    --ordering FM \
    --total_magnetization_min 10.0 \
    --output ferromagnetic_materials.json
```

**Key Parameters**:
- `--material_id`: Specific MP ID(s) to query
- `--ordering`: Magnetic ordering type (FM, AFM, FiM, NM)
- `--total_magnetization_min/max`: Total magnetization range in μB

**Output**: JSON file with magnetic ordering, total magnetization, and per-site magnetic moments.

### 4. Retrieve Structures by Material ID

Use `get_structure_by_id.py` to retrieve crystal structures directly by their Materials Project ID.

**Single Structure Retrieval**:
```bash
# Env: base-agent
python .agents/skills/mat-db-mp/scripts/get_structure_by_id.py mp-149 \
    --output Si_diamond.cif
```

**Batch Retrieval**:
```bash
# Env: base-agent
python .agents/skills/mat-db-mp/scripts/get_structure_by_id.py \
    mp-149 mp-19017 mp-1143 \
    --output_dir structures/
```

**Key Parameters**:
- `material_ids`: One or more MP IDs to retrieve
- `--output`: Output path for single material ID (CIF format)
- `--output_dir`: Output directory for batch retrieval
- `--api_key`: Optional API key (uses `MP_API_KEY` env var by default)

**Output**: CIF file(s) containing the crystal structure(s).

### 5. Find Structurally Similar Materials

Use `find_similar_structures.py` to find materials with similar crystal structures based on CrystalNN fingerprinting.

**Find Similar to MP Material**:
```bash
# Env: base-agent
python .agents/skills/mat-db-mp/scripts/find_similar_structures.py \
    --material_id mp-149 \
    --top 15 \
    --output similar_to_si.json
```

**Find Similar to Custom Structure**:
```bash
# Env: base-agent
python .agents/skills/mat-db-mp/scripts/find_similar_structures.py \
    --structure my_structure.cif \
    --top 20 \
    --output similar_structures.json
```

**Filter by Chemical System**:
```bash
# Env: base-agent
python .agents/skills/mat-db-mp/scripts/find_similar_structures.py \
    --material_id mp-149 \
    --top 20 \
    --chemsys "C" \
    --output carbon_structures_like_si.json
```

**Key Parameters**:
- `--material_id`: MP ID to use as query structure
- `--structure`: Path to custom structure file (CIF, POSCAR, etc.)
- `--top`: Number of most similar structures to return (default: 50)
- `--chemsys`: Optional post-filter by exact chemical system match

**Similarity Algorithm**: Uses CrystalNN to compute local coordination fingerprints, aggregates them into structure fingerprints, and ranks by Euclidean distance in fingerprint space. Dissimilarity score: `100 * (1 - exp(-distance))`, where 0% = identical and 100% = maximally different.

**Output**: JSON file with similar material IDs, formulas, and dissimilarity scores (0-100%).

## Examples

See the `examples/` directory for complete working examples:

**Basic Queries** (`examples/query_mp/`):
```bash
cd .agents/skills/mat-db-mp
bash examples/query_mp/li_s_stability.sh
# Output: Retrieves 2 stable Li-S materials (E_hull < 0.05 eV/atom)
```

**Elastic Properties** (`examples/elasticity/`):
```bash
cd .agents/skills/mat-db-mp
bash examples/elasticity/elasticity_query.sh
# Output: Si elastic data + 1387 materials with K=200-400 GPa
```

**Magnetic Properties** (`examples/magnetism/`):
```bash
cd .agents/skills/mat-db-mp
bash examples/magnetism/magnetism_query.sh
# Output: Fe2O3 magnetic data + 23,121 ferromagnetic materials
```

**Structure Similarity** (`examples/similarity/`):
```bash
cd .agents/skills/mat-db-mp
bash examples/similarity/similarity_search.sh
# Output: 15 structures similar to Si (mp-149)
```

**Structure Retrieval** (`examples/get_structure/`):
```bash
cd .agents/skills/mat-db-mp
bash examples/get_structure/structure_retrieval.sh
# Output: CIF files for Si, LiFePO4, and Fe2O3
```

## MCP Tools for Quick Retrieval

For simple structure retrieval tasks, MCP tools provide a convenient alternative to running scripts:

### Retrieve Most Stable Structure by Formula

```python
mcp_base_search_materials_project_by_formula(
    formula="LiFePO4",          # Chemical formula
    save_to_file="lifepo4.cif"  # Optional: save path (default: auto-generated)
)
```

Returns **only the single most stable structure** (lowest energy above hull) matching the formula. If multiple polymorphs exist, only ONE is returned.

### Retrieve All Stable Structures by Chemical System

```python
mcp_base_search_materials_project_by_chemsys(
    chemsys="Li-O",                    # Chemical system
    save_to_file="LiO_structures"      # Optional: directory path (default: {chemsys}_structures)
)
```

Returns **all stable structures on the convex hull** (E_hull = 0) in the specified chemical system. Structures are saved to individual CIF files in a directory.

**Output**: Directory containing CIF files for each hull structure, named `{mp-id}_{formula}.cif`. Each structure includes metadata (material_id, formula, energy_above_hull) in the atoms.info dict.

**Example Output**:
```
Found 3 structures on convex hull for Li-O
Saved to directory: /path/to/LiO_structures

Structures:
  - mp-1960: Li2O (E_hull=0.000000 eV/atom)
  - mp-12958: Li2O2 (E_hull=0.000000 eV/atom)
  - mp-841: LiO2 (E_hull=0.000000 eV/atom)
```

### When to Use MCP Tools vs Scripts

**Use MCP Tools** when:
- **Formula search**: Need the single most stable polymorph quickly
- **Chemical system search**: Need all stable phases on the convex hull
- Working from Python/Jupyter notebooks
- Simple queries without complex property filtering
- Exploring phase diagrams (chemsys tool returns all hull phases)

**Use Scripts** when:
- Querying structures with specific property filters (e.g., bandgap > 2 eV)
- Need detailed properties (elasticity, magnetism, formation energy)
- Batch processing with custom criteria
- Generating datasets for ML training
- Advanced queries (similarity search, property ranges, metastable structures)

## Constraints

- **API Key**: Requires Materials Project API key set in `MP_API_KEY` environment variable
- **Environment**: All scripts require the `base-agent` conda environment
- **MP-API Version**: Similarity search requires mp-api >= 0.46.0 with `find_similar` method
- **Python Version**: Base-agent uses Python 3.11
- **Rate Limits**: Materials Project API has rate limits; large queries may be throttled
- **Endpoint Differences**: 
  - `summary` endpoint includes crystal structures (CIF format)
  - `thermo` endpoint provides detailed thermodynamic data but no structures
- **Similarity Chemical Filter**: The `--chemsys` parameter in similarity search performs post-filtering for exact element matches, not compositional similarity
- **Large Result Sets**: Queries returning >1000 materials may take several minutes to complete

### API Endpoints

- **Summary** (`mpr.materials.summary`): General material data with structures
- **Thermo** (`mpr.materials.thermo`): Detailed thermodynamic properties
- **Elasticity** (`mpr.materials.elasticity`): Elastic modulus and tensor data  
- **Magnetism** (`mpr.materials.magnetism`): Magnetic ordering and moments
- **Similarity** (`mpr.materials.similarity`): CrystalNN-based structure matching
---

**Author:** Bowen Deng  
**Contact:** [GitHub @bowen-bd](https://github.com/bowen-bd)
