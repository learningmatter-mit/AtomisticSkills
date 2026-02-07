---
name: material-stability
description: Calculate the thermodynamic stability and energy above the convex hull (E_hull) of a material at 0K.
---

# Stability Calculation

## Goal
To determine the thermodynamic stability of a material at 0K by computing the energy above the convex hull ($E_{hull}$) using pymatgen phase diagram analysis with structures from Materials Project.

> [!TIP]
> **Finite Temperature Stability**: While this skill focuses on 0K stability (potential energy), you can construct a finite-temperature phase diagram by replacing potential energies with **Free Energies** ($G = U + F_{\text{vib}}$) calculated from the [qha-thermal-expansion](../../skills/qha-thermal-expansion/SKILL.md) skill.

## Instructions

1.  **Select Level of Theory**: Choose the target accuracy level for stability calculations.
    - **Recommended**: r2SCAN-level foundation potentials for high accuracy
    - **Options**: `TensorNet-MatPES-r2SCAN-v2025.1-PES` (MatGL) or `MACE-MH-1` with `matpes_r2scan` head
    - See [foundation-potentials](../../skills/foundation-potentials/SKILL.md) for detailed guidance
    
    **Note**: r2SCAN shows high accuracy for predicting thermodynamic stability (MAE 80 meV/atom for formation energies vs PBE's 175 meV/atom)[^1]. Using r2SCAN-trained potentials ensures consistency with Materials Project's r2SCAN entries.
    
    [^1]: Kingsbury, R. et al. "Performance comparison of r2SCAN and SCAN metaGGA density functionals for solid materials via an automated, high-throughput computational workflow" *Physical Review Materials* **6**, 013801 (2022). [DOI: 10.1103/PhysRevMaterials.6.013801](https://doi.org/10.1103/PhysRevMaterials.6.013801)

2.  **Query Materials Project Hull**: Retrieve all structures on the convex hull in the target material's chemical space.
    ```bash
    # Env: base-agent
    python .agent/skills/material-stability/scripts/query_mp_hull.py \
        --formula "Li-Fe-P-O" \
        --target "LiFePO4" \
        --thermo_type "R2SCAN" \
        --output hull_structures/
    ```
    
    This script will:
    - Query Materials Project for all stable phases in the chemical space (including all subsystems)
    - Download structures on the convex hull (ground state phases)
    - Filter by level of theory (e.g., GGA/GGA+U or R2SCAN) to ensure consistency
    - Save the target material and all competing phases
    - Output a `hull_entries.json` manifest

3.  **Relax All Structures**: Perform structural relaxation on all hull structures using the same MLIP.
    ```bash
    # Env: matgl-agent (if using MatGL)
    mcp_matgl_relax_structure(
        structure_data="hull_structures/",  # Pass directory containing all CIF files
        relax_cell=True,
        model_name="TensorNet-MatPES-r2SCAN-v2025.1-PES",
        fmax=0.02,
        steps=500,
        output_dir="relaxed/"
    )
    ```
    
    The MCP tool will automatically:
    - Process all CIF files in `hull_structures/`
    - Create individual subdirectories in `relaxed/` for each structure
    - Save energies to `relaxed_energy.txt` files for compute_ehull.py
    
    **Critical**: Use the **same MLIP and settings** for all relaxations to ensure energy consistency.

4.  **Construct Convex Hull**: Build a pymatgen phase diagram using the relaxed energies.
    ```bash
    # Env: base-agent
    python .agent/skills/material-stability/scripts/compute_ehull.py \
        --hull_manifest hull_entries.json \
        --relaxed_dir relaxed/ \
        --target_material LiFePO4 \
        --output stability_analysis.json
    ```
    
    The script will:
    - Read relaxed structures and energies from each subdirectory
    - Create `ComputedEntry` objects for pymatgen
    - Construct the convex hull using `PhaseDiagram`
    - Calculate $E_{hull}$ for the target material
    - Generate a phase diagram plot (optional)

5.  **Interpret Stability**: Assess the thermodynamic stability based on $E_{hull}$ (energy above hull in meV/atom):
    - **$E_{hull} = 0$ meV/atom**: **STABLE** - On the convex hull, thermodynamically stable
    - **$0 < E_{hull} \leq 50$ meV/atom**: **METASTABLE** - May be synthesizable under kinetic control
    - **$E_{hull} > 50$ meV/atom**: **UNSTABLE** - Likely to decompose into competing phases
    
    The decomposition reaction and products are also reported by pymatgen.

## Examples

### Example 1: Stability Analysis for LiFePO4
```bash
# Step 1: Query Materials Project hull in Li-Fe-P-O space
# Env: base-agent
python .agent/skills/material-stability/scripts/query_mp_hull.py \
    --formula "Li-Fe-P-O" \
    --target "LiFePO4" \
    --output hull_structures/

# Step 2: Batch relax all structures (target + hull phases)
mcp_matgl_relax_structure(
    structure_data="hull_structures/",  # Directory with all CIF files
    relax_cell=True,
    model_name="TensorNet-MatPES-r2SCAN-v2025.1-PES",
    fmax=0.02,
    output_dir="relaxed/"
)

# Step 3: Compute E_hull
# Env: mlip-agent
python .agent/skills/material-stability/scripts/compute_ehull.py \
    --hull_manifest hull_entries.json \
    --relaxed_dir relaxed/ \
    --target_material LiFePO4 \
    --output LiFePO4_stability.json
```

### Example 2: Quick Stability Check for LiCoO2
```bash
# Query Li-Co-O chemical space
# Env: mlip-agent
python .agent/skills/material-stability/scripts/query_mp_hull.py \
    --formula "Li-Co-O" \
    --target "LiCoO2" \
    --thermo_type "R2SCAN" \
    --output hull_structures_LiCoO2/
```

## Constraints

- **Energy Consistency**: All structures (target + hull phases) MUST be relaxed with the **same MLIP model and settings**. Mixing different MLIPs will produce incorrect E_hull values.
- **Level of Theory**: Use r2SCAN-trained foundation potentials (e.g., `MACE-MH-1 matpes_r2scan`) for better accuracy and consistency with Materials Project.
- **Convergence Criterion**: Use `fmax ≤ 0.02 eV/Å` for all relaxations. Inconsistent convergence criteria will introduce systematic errors.
- **Chemical Space**: The query must include ALL elements in the target material. For example, for LiFePO4, query "Li-Fe-P-O" not just "Li-Fe-P".
- **Hull Completeness**: Ensure all competing phases are included. Missing hull phases will lead to underestimated E_hull (false negatives for instability).
- **Stability Thresholds**: 
  - $E_{hull} = 0$ meV/atom: **Stable**
  - $0 < E_{hull} \leq 50$ meV/atom: **Metastable**
  - $E_{hull} > 50$ meV/atom: **Unstable**
- **Phase Diagram Construction**: For full phase diagram visualization and competing phase analysis, see the separate phase-diagram skill (to be developed).
- **Energy Input**: Use **TOTAL POTENTIAL ENERGY** for all entries in `pymatgen.analysis.phase_diagram.PhaseDiagram` automatically calculates formation energies by identifying elemental ground states from the provided entries. Do not pass formation energies directly.
- **DFT Validation**: For publication-quality results, validate E_hull with DFT calculations, especially for materials close to the stability threshold.
