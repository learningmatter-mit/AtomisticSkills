# Magnetic Density Skill Examples

This directory contains example calculations demonstrating the magnetic density skill for various magnetic materials.

## Available Examples

### 1. Bulk Iron (Fe) - Ferromagnetic Metal

**Files**:
- [`Fe_example.md`](Fe_example.md) - Detailed analysis and comparison
- `Fe_bulk.cif` - Input structure (bcc Fe)
- `Fe_moments.json` - Parsed magnetic moment analysis

**Key Results**:
- Calculated moment: 2.15 μB per Fe atom (PBE functional)
- Experimental moment: 2.2 μB per Fe atom
- Error: -2.3% (excellent agreement)
- Ordering: Ferromagnetic (all moments aligned)

**Validation**: This example validates that:
1. The parsing scripts correctly extract magnetic moments
2. PBE functional provides accurate results for metallic ferromagnets
3. The skill properly identifies ferromagnetic ordering

## Functional Selection Summary

Based on literature research and validation:

### ✓ Use PBE for:
- Metallic ferromagnets (Fe, Co, Ni)
- Systems where d-electrons are itinerant
- Error typically ~2% vs experimental values

### ✓ Use PBE+U for:
- Transition metal oxides (NiO, CoO, FeO)
- Strongly correlated d-electron systems
- Systems with underestimated band gaps in standard PBE

### ✗ Avoid r2SCAN for:
- Metallic ferromagnets (overestimates by ~24%)
- Itinerant magnetic systems

## Typical Workflow

1. Query or prepare structure
2. Run spin-polarized DFT using atomate2 with appropriate functional
3. Extract magnetic moments using `parse_magnetic_moments.py`
4. Compare to experimental/literature values
5. Optionally visualize using `visualize_magnetic_structure.py`

## References

- Furness et al., J. Phys. Chem. Lett. 2020: r2SCAN overestimation of magnetic moments
- Crangle & Goodman, Proc. R. Soc. Lond. A 321, 477 (1971): Experimental Fe magnetization
