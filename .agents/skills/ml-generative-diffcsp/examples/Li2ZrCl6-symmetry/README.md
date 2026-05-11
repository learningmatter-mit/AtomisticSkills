# Li₂ZrCl₆ Symmetry-Constrained Generation

Example of generating Li₂ZrCl₆ structures with exact composition control using the MCP tool.

## Run

```python
# Via MCP tool
mcp_diffcsp_generate_structures_with_symmetry(
    spacegroup=12,                        # C2/m
    wyckoff_letters="2a,4g,4h,4i,4i",     # Zr: 2a, Li: 4g, Cl: 4h+4i+4i
    atom_types="Zr,Li,Cl,Cl,Cl",
    model_name="mp_csp",
    num_samples=3
)
```

## Expected Results

- **Space group**: 12 (C2/m)
- **Formula**: Li₂ZrCl₆ (18 atoms/cell: 2 Zr + 4 Li + 4+4+4 Cl)
- **Generation time**: ~5 seconds on GPU
- Lattice parameters vary across samples (~1-3% spread), confirming structural diversity

## Files

- [structure_0000.cif](structure_0000.cif) — Example generated structure
- `generation_metadata.json` — Generation parameters
