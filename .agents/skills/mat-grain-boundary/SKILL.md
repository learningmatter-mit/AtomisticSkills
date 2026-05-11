---
name: mat-grain-boundary
description: Calculate grain boundary energies for tilt/twist grain boundaries (Σ-CSL boundaries) using MLIPs; output γ_GB vs. misorientation angle curves and identify low-energy special boundaries.
category: [materials]
---

# Grain Boundary Energy Calculation

## Goal
To compute the specific grain boundary energy ($\gamma_{GB}$, J/m²) for a series of coincidence site lattice (CSL) grain boundaries using Machine Learning Interatomic Potentials. This enables:
- Identification of low-energy special grain boundaries (Σ3, Σ5, Σ7, ...)
- Anisotropy analysis of GB energy as a function of misorientation angle
- Input data for polycrystalline simulations (phase-field, kinetic Monte Carlo)

The grain boundary energy is defined as:

$$\gamma_{GB} = \frac{E_{GB} - N \cdot E_{bulk}}{2 A}$$

where $E_{GB}$ is the total energy of the GB supercell, $N$ is the number of atoms, $E_{bulk}$ is the DFT/MLIP energy per atom of the relaxed bulk, and $A$ is the interfacial area (one GB, periodic cell contains two identical GBs hence the factor of 2).

## Instructions

### 1. Select Foundation Potential

GB calculations benefit from accurate interatomic forces. Prefer r2SCAN-level models for energy accuracy:
- `MACE-MH-1` with `matpes_r2scan` head (recommended)
- `CHGNet-MatPES-r2SCAN-2025.2.10-2.7M-PES` (MatGL)
- `TensorNet-MatPES-r2SCAN-v2025.1-PES` (MatGL, faster)

Refer to [ml-foundation-potentials](../ml-foundation-potentials/SKILL.md).

### 2. Relax Bulk Reference

Perform a high-accuracy bulk relaxation to obtain $E_{bulk}$.

```bash
# Env: matgl-agent
mcp_matgl_load_model(model_name="CHGNet-MatPES-r2SCAN-2025.2.10-2.7M-PES")
mcp_matgl_relax_structure(
    structure_data="bulk.cif",
    relax_cell=True,
    fmax=0.005,
    output_dir="bulk_relaxation/"
)
```

Record the final energy per atom ($E_{bulk}$) from the relaxation output JSON.

### 3. Generate Grain Boundary Structures

Use pymatgen's `GrainBoundaryGenerator` to create CSL grain boundary supercells for a range of Σ values and rotation angles.

```bash
# Env: base-agent
python .agents/skills/mat-grain-boundary/scripts/create_grain_boundary.py \
    --bulk bulk_relaxation/relaxed_structure.cif \
    --rotation-axis 0 0 1 \
    --max-sigma 29 \
    --min-slab-size 10.0 \
    --vacuum 0.0 \
    --output-dir gb_structures/
```

**Key parameters:**

| Parameter | Description | Example |
|:----------|:------------|:--------|
| `--rotation-axis` | Rotation axis as 3 integers | `0 0 1` (tilt) or `1 1 0` |
| `--max-sigma` | Maximum Σ value to enumerate | 29 (generates Σ3, Σ5, Σ7...) |
| `--min-slab-size` | Minimum thickness of each grain (Å) | 10.0 |
| `--output-dir` | Directory for generated GB CIF files | `gb_structures/` |

The script writes one CIF per unique GB, with filename format `sigma{Σ}_{angle:.1f}deg_{hkl}.cif`.

> [!TIP]
> For a first survey use `--max-sigma 13` (gives Σ1, Σ3, Σ5, Σ7, Σ9, Σ11, Σ13). Increase to 29 for more complete misorientation curves.

### 4. Relax Grain Boundary Structures

Relax all generated GB structures. **Do NOT relax the cell in directions parallel to the GB plane** — use `relax_cell=False` to fix the in-plane lattice vectors and only relax atomic positions.

```bash
# Env: matgl-agent
mcp_matgl_load_model(model_name="CHGNet-MatPES-r2SCAN-2025.2.10-2.7M-PES")
mcp_matgl_relax_structure(
    structure_data="gb_structures/",
    relax_cell=False,
    fmax=0.02,
    output_dir="gb_relaxations/"
)
```

> [!IMPORTANT]
> `relax_cell=False` is required. The in-plane lattice vectors of the GB supercell are fixed by the CSL geometry and must remain constant to preserve the grain boundary orientation.

### 5. Calculate Grain Boundary Energies

```bash
# Env: base-agent
python .agents/skills/mat-grain-boundary/scripts/calculate_gb_energy.py \
    --bulk-energy-per-atom -4.567 \
    --gb-relaxation-dir gb_relaxations/ \
    --output-dir gb_results/
```

The script reads the JSON output from each relaxation, applies the GB energy formula, and generates:
- `gb_energy_results.json` — Σ, angle, area, $\gamma_{GB}$, and provenance per boundary
- `gb_energy_vs_angle.png/svg` — plot of $\gamma_{GB}$ (J/m²) vs. misorientation angle (°)
- `gb_summary_table.csv` — CSV for further analysis

### 6. Identify Low-Energy Boundaries

Inspect the output table and plot to identify:
- **Cusps**: sharp dips in $\gamma_{GB}$ vs. angle correspond to special low-energy GBs (Σ3 ≈ twin boundary, Σ5, etc.)
- **Asymmetric tilt boundaries**: generated alongside symmetric ones; compare energies
- **Coincidence index correlation**: low-Σ GBs typically have the lowest energies

## Examples

### Example: Copper [001] Tilt Grain Boundaries

Copper is a well-benchmarked system. MLIP values should be compared to DFT/MD literature.

```bash
# 1. Query and relax bulk Cu
mcp_base_search_materials_project_by_formula(formula="Cu", save_to_file="Cu_bulk.cif")
mcp_matgl_load_model(model_name="TensorNet-MatPES-r2SCAN-v2025.1-PES")
mcp_matgl_relax_structure(structure_data="Cu_bulk.cif", relax_cell=True, fmax=0.005, output_dir="Cu_bulk_relax/")

# 2. Generate [001] tilt GBs up to Σ13
python .agents/skills/mat-grain-boundary/scripts/create_grain_boundary.py \
    --bulk Cu_bulk_relax/relaxed_structure.cif \
    --rotation-axis 0 0 1 --max-sigma 13 --output-dir Cu_gb_structures/

# 3. Relax GB structures
mcp_matgl_relax_structure(structure_data="Cu_gb_structures/", relax_cell=False, fmax=0.02, output_dir="Cu_gb_relax/")

# 4. Calculate GB energies (E_bulk ≈ -3.73 eV/atom for Cu with TensorNet)
python .agents/skills/mat-grain-boundary/scripts/calculate_gb_energy.py \
    --bulk-energy-per-atom -3.73 \
    --gb-relaxation-dir Cu_gb_relax/ \
    --output-dir Cu_gb_results/
```

**Literature comparison:** For Cu [001] tilt boundaries, the Σ5 (36.9°) boundary has $\gamma_{GB}$ ≈ 0.8–1.0 J/m² from MD simulations. The Σ3 (twin) boundary has $\gamma_{GB}$ < 0.05 J/m².

## Constraints

- **Cell relaxation**: Always use `relax_cell=False` for GB structures. The in-plane dimensions define the CSL geometry and must not change.
- **Slab thickness**: Use `--min-slab-size ≥ 10 Å` to ensure bulk-like behaviour at the centre of each grain. Thin grains cause artificial interaction between the two GBs in the periodic cell.
- **Same MLIP for bulk and GB**: Use the **identical model** and settings for both bulk relaxation (Step 2) and GB relaxation (Step 4) to ensure energy cancellation in the GB energy formula.
- **Vacuum**: Set `--vacuum 0.0`. Unlike surface calculations, grain boundary supercells should have no vacuum — both grains are connected periodically.
- **Environment**: All scripts run in `base-agent`. MLIP relaxations use the respective MLIP environment.

## References

- Zhao et al., "Automated generation and analysis of grain boundary structures using machine learning potentials", *npj Comput. Mater.*, 2021.
- Holm & Foiles, "How Grain Boundary Properties Are Influenced by the Character of the Boundary", *Science*, 2010.
- Tschopp & McDowell, "Asymmetric Tilt Grain Boundary Structure and Energy in Copper and Aluminium", *Phil. Mag.*, 2007.
- Pymatgen `GrainBoundaryGenerator` documentation: [link](https://pymatgen.org/pymatgen.analysis.grain_boundary.html)

---

**Author:** Yu Yao, Bowen Deng  
**Contact:** [GitHub @AI4SciDisc](https://github.com/AI4SciDisc)
