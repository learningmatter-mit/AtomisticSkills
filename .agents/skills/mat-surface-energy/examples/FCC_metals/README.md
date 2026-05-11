# Surface Energy and Wulff Shape Example

This conceptual example demonstrates how to predict the equilibrium crystal shape (Wulff shape) of a pure elemental system using surface energy calculations.

### Workflow

1. **Cleave Slabs**
   Use `scripts/create_slabs.py` on a primitive bulk unit cell to extract common low-index continuous surface terminations (e.g., (111), (100), (110) for FCC metals). Ensure sufficient vacuum space (e.g.,>15 Å) and slab thickness.

2. **Relax and Calculate Structure Energies**
   Compute the potential energy of the bulk bulk unit cell.
   Next, pass the generated surface slabs to your preferred MLIP (e.g. MACE or MatGL) via the `mcp_*_relax_structure` tools to obtain the relaxed surface slab energies. The difference between slab energy and bulk energy normalized by the cross-sectional area yields the intrinsic surface energy $\gamma$.
   Alternatively, you can automate this via `scripts/calculate_surface_energy.py`.

3. **Generate Wulff Shape**
   Use the mapped energies $\gamma_{(hkl)}$ along with their respective Miller indices  in `scripts/generate_wulff.py`. This script applies Wulff's theorem to construct a minimum-energy morphological polyhedron representing the macroscopic nanoparticle shape.

### Literature Comparison
The dummy energies provided in this example (1.30, 1.45, 1.55 J/m²) for Cu obey the general stability trend observed in experimental and theoretical literature: $\gamma_{(111)} < \gamma_{(100)} < \gamma_{(110)}$. Experimental values for Cu typically lie in the range of ~1.5 - 1.8 J/m² near 0K, and standard DFT-PBE calculations often yield values around ~1.3 - 1.4 J/m². Obtaining quantitative agreement with experimental values requires advanced density functionals (e.g. SCAN) and carefully constructed surface models.
