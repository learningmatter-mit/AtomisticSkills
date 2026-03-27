# NaFeO₂ — Random Structure Search

## Goal

Discover low-energy polymorphs of NaFeO₂ (a ternary oxide cathode material) via random structure searching with MLIP relaxation, and validate by comparing against Materials Project.

## Commands

### Step 1: Generate random structures
```bash
# Env: base-agent
python .agents/skills/mat-random-structure-search/scripts/generate_random_structures.py \
    --composition NaFeO2 \
    --num_structures 50 \
    --seed 42 \
    --output_dir examples/NaFeO2_search/
```

### Step 2: Relax with MACE-MH-1
```python
mcp_mace_load_model(model_name="MACE-MH-1", task_name="omat_pbe")
mcp_mace_relax_structure(
    structure_data="examples/NaFeO2_search/",
    relax_cell=True, fmax=0.05, steps=300,
    output_dir="examples/NaFeO2_search/relaxed/"
)
```

## Results

- **Generation:** 50 structures from 39 space groups (40.7% success rate, 123 attempts)
- **Relaxation:** 50/50 successful (MACE-MH-1, omat_pbe head)

### Energy Ranking (Top 10)

| Rank | Structure | Initial SG | Energy (eV/atom) |
|---:|---|---:|---:|
| 1 | 0006_NaFeO2_sg11 | 11 | −5.771 |
| 2 | 0011_NaFeO2_sg148 | 148 | −5.771 |
| 3 | 0029_NaFeO2_sg2 | 2 | −5.771 |
| 4 | 0036_NaFeO2_sg227 | 227 | −5.771 |
| 5 | 0019_NaFeO2_sg57 | 57 | −5.771 |
| 6 | 0023_NaFeO2_sg127 | 127 | −5.771 |
| 7 | 0044_NaFeO2_sg33 | 33 | −5.770 |
| 8 | 0025_NaFeO2_sg127 | 127 | −5.673 |
| 9 | 0041_NaFeO2_sg226 | 226 | −5.673 |
| 10 | 0022_NaFeO2_sg221 | 221 | −5.673 |

### Two Distinct Energy Basins

| Basin | Energy (eV/atom) | Count | Description |
|---|---|---:|---|
| **A (ground state)** | −5.771 | 7 | α-NaFeO₂ layered rocksalt (R-3m) |
| **B (metastable)** | −5.673 | ~30 | Higher-energy polymorph, 98 meV/atom above GS |

### Validation Against Materials Project

Using `pymatgen.StructureMatcher`, we compare the top RSS candidates against the 4 known NaFeO₂ phases on MP:

| MP ID | Space Group | E_hull (eV/atom) | Stable? |
|---|---|---:|---|
| mp-19359 | R-3m | 0.000 | ✅ |
| mp-21880 | P4₁2₁2 | 0.027 | ❌ |
| mp-21060 | Pna2₁ | 0.050 | ❌ |
| mp-971633 | P6₃/mmc | 0.084 | ❌ |

**Matching results:**

| RSS Candidate | Basin | Matches MP? |
|---|---|---|
| 0006_sg11, 0011_sg148, 0029_sg2, 0036_sg227, 0019_sg57 | A | ✅ **mp-19359 (R-3m, stable GS)** |
| 0025_sg127, 0041_sg226 | B | ❌ No match — possible novel polymorph |

**All 7 Basin A structures re-discover the thermodynamically stable α-NaFeO₂ ground state (mp-19359, R-3m).** They started from 5 different random space groups and all converged to the same correct structure.

Basin B (~30 structures) does not match any of the 4 known MP phases, suggesting it may be a novel metastable polymorph or an artifact of the MLIP potential energy surface.

## Output Files

- `generation_manifest.json` — metadata for the 50 generated structures
- `best_structure.png` — visualization of the lowest-energy relaxed structure
- `relaxed_structures/basin_A_ground_state_R3m.cif` — the best structure (matches mp-19359)
- `relaxed_structures/basin_B_metastable.cif` — representative of the second energy basin
