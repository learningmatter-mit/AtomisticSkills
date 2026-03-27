# Mat-DB-MP Examples

This directory contains example scripts and outputs demonstrating all mat-db-mp functionality.

## Directory Structure

```
examples/
├── README.md
├── query_mp/          # Basic MP queries with filtering
├── elasticity/        # Elastic properties queries
├── magnetism/         # Magnetic properties queries
├── similarity/        # Structure similarity search
└── get_structure/     # Structure retrieval by material ID
```

## Examples by Category

### 1. Query MP (`query_mp/`)
**Script**: `li_s_stability.sh`  
**Function**: Basic Materials Project querying with stability filtering

**Query**: Li-S chemical system, energy_above_hull < 0.05 eV/atom  
**Output**: `li_s_stable.json` (2 materials)  
**Properties**: energy_above_hull, formation_energy_per_atom, band_gap

```bash
cd .agents/skills/mat-db-mp
bash examples/query_mp/li_s_stability.sh
```

---

### 2. Elasticity (`elasticity/`)
**Script**: `elasticity_query.sh`  
**Function**: Elastic modulus and tensor queries

**Queries**:
- Si (mp-149) elastic properties
- Materials with bulk modulus 200-400 GPa

**Outputs**:
- `si_elasticity.json` (1 material, ~18KB)
- `high_bulk_modulus.json` (1387 materials, ~38MB)

**Properties**: bulk_modulus (VRH), shear_modulus (VRH), elastic_tensor

```bash
cd .agents/skills/mat-db-mp
bash examples/elasticity/elasticity_query.sh
```

---

### 3. Magnetism (`magnetism/`)
**Script**: `magnetism_query.sh`  
**Function**: Magnetic ordering and magnetization queries

**Queries**:
- Fe2O3 (mp-19770) magnetic properties
- Ferromagnetic materials with magnetization > 10 μB

**Outputs**:
- `fe2o3_magnetism.json` (1 material, ~2KB)
- `ferromagnetic_materials.json` (23,121 materials, ~62MB)

**Properties**: ordering (FM/AFM/FiM/NM), total_magnetization, magnetic_moments

```bash
cd .agents/skills/mat-db-mp
bash examples/magnetism/magnetism_query.sh
```

---

### 4. Similarity Search (`similarity/`)
**Script**: `similarity_search.sh`  
**Function**: Crystal structure similarity search

**Queries**:
- Top 15 structures similar to Si (mp-149)
- Carbon structures similar to Si (with chemical filter)

**Outputs**:
- `similar_to_si.json` (15 structures, ~2KB)
- `similar_si_carbon_only.json` (0 structures - no C-only matches)

**Properties**: task_id, formula, dissimilarity score

```bash
cd .agents/skills/mat-db-mp
bash examples/similarity/similarity_search.sh
```

---

### 5. Structure Retrieval (`get_structure/`)
**Script**: `structure_retrieval.sh`  
**Function**: Retrieve crystal structures by Materials Project ID

**Queries**:
- Single structure retrieval (Si, mp-149)
- Batch retrieval of multiple structures (Si, LiFePO4, Fe2O3)

**Outputs**:
- `mp-149_Si.cif` (~1KB, custom filename)
- `mp-149.cif` (~1KB, Silicon diamond structure)
- `mp-19017.cif` (~2KB, LiFePO4 olivine structure)
- `mp-1143.cif` (~1KB, Fe2O3 hematite structure)

```bash
cd .agents/skills/mat-db-mp
bash examples/get_structure/structure_retrieval.sh
```

---

## Quick Reference

| Category | Output Files | Total Size | Materials Count |
|----------|--------------|------------|-----------------|
| Query MP | 1 | ~2KB | 2 |
| Elasticity | 2 | ~38MB | 1,388 |
| Magnetism | 2 | ~62MB | 23,122 |
| Similarity | 2 | ~2KB | 15 |
| Get Structure | 4 | ~4KB | 4 (CIF files) |

## Requirements

- Materials Project API key set in `MP_API_KEY` environment variable
- `base-agent` conda environment activated
- mp-api >= 0.46.0 (for similarity search)

## Notes

- All JSON outputs use MontyEncoder for pymatgen objects
- Large result sets (>1000 materials) may take longer to retrieve
- Similarity search requires mp-api 0.46.0+ with `find_similar` method
- Run all scripts from the `.agents/skills/mat-db-mp/` directory
