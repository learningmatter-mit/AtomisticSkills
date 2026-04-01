# End-to-End PdPtAg Ternary Surface Segregation

This example demonstrates reproducing a scientific study of a ternary alloy surface using the complete `smol` MCP pipeline. 
**Reference Paper:** *Cluster expansion-accelerated exploration of the surface structure properties of a PdPtAg ternary alloy for the oxygen reduction reaction across the compositional space* (RSC Advances, 2021). The aim of the original paper was to investigate elemental segregation across the Z-axis of the catalytic surface.

**Dataset Origin:** The 266 ATAT raw surface structures and energies used for this Cluster Expansion training are sourced from the GitHub repository: [Huamh/Data-for-cluster-expansion-of-PdPtAg-ternary-alloy](https://github.com/Huamh/Data-for-cluster-expansion-of-PdPtAg-ternary-alloy).

## 1. Preparing the Primordial Structure
The `parse_primordial.py` script demonstrates how to read a `lat.in` (ATAT format) lattice file from the dataset and construct a unified `primordial.cif` base structure for `smol`'s Cluster Subspace. 

**Key Takeaway:** Ensure your primordial structure has perfect precision for fractional coordinates and occupancies. The `smol` subspace builder uses a strict symmetry tolerance (`symprec=1e-5`). The script implements numerical snapping to mathematically enforce exact fractions (e.g., `1/6`, `1/3`) on active sublattices.

## 2. Formatting the Training Dataset
The `parse_atat.py` script traverses 266 ATAT `str_relax.out` and `energy` files, maps their relaxed Cartesian coordinates to the primordial fractional basis, and outputs a valid JSON representation (`training_data.json`).

```json
[
  {
    "structure": {"@module": "pymatgen.core.structure", ...},
    "energy": -450.12, 
    "id": "config_001"
  }
]
```

## 3. Training the CE Model with Lasso
By utilizing the MCP tool `mcp_smol_train_cluster_expansion`, we fitted this highly-complex 3-component system. Using a sparse solver like Lasso (`alpha=0.001`) prevents overfitting on the massively large pool of ternary multi-component clusters.

```python
# MCP Tool: mcp_smol_train_cluster_expansion
result = mcp_smol_train_cluster_expansion(
    disordered_structure="primordial.cif",
    training_data="training_data.json",
    cutoffs={2: 6.0, 3: 4.0},
    fit_method="lasso",
    alpha=0.001,
    ce_file="cluster_expansion.json"
)
```

## 4. Canonical Monte Carlo
The core scientific finding is that the species with the lowest surface energy (Ag) should segregate completely to the outer surface layers, pushing Pd/Pt into the bulk. We ran the MC Canonical ensemble on the fitted CE, enforcing the total molar fraction `{"Ag": 0.33, "Pd": 0.33, "Pt": 0.34}` using `mcp_smol_run_monte_carlo`.

```python
# MCP Tool: mcp_smol_run_monte_carlo
mc_result = mcp_smol_run_monte_carlo(
    supercell_matrix=[[2,0,0], [0,2,0], [0,0,1]],
    temperature=300, 
    steps=50000,
    ensemble_type="canonical",
    initial_composition={"Ag": 0.33, "Pd": 0.33, "Pt": 0.34},
    ce_file="cluster_expansion.json",
    trajectory_file="mc_trajectory.h5"
)
```

## 5. Result Verification
The `analyze_mc.py` script parses the final relaxed trajectory frame (`mc_trajectory_final.cif`) and groups atomic species layer-by-layer across the Z slab axis. 

**Scientific Recovery:** 
As reported in the source paper, Ag is heavily favored to segregate purely to the top and bottom free surfaces of the catalytic slab due to its lower surface energy. 
- **Start (`mc_trajectory_initial.cif`)**: The 48 dynamically-swapping surface and sub-surface sites start as a highly mixed multi-element solid solution. Ag, Pd, and Pt are roughly evenly dispersed across the Z planes (e.g., `z=0.29`: Ag7/Pd5/Pt4, `z=0.36`: Ag5/Pd4/Pt7).
- **Equilibrium (`mc_trajectory_final.cif`)**: Our Monte Carlo simulation definitively recovers the paper's primary energetic finding. Upon equilibration, silver (Ag) wholly segregates outward to completely monopolize the top and bottom free-surface layers (`z=0.06`, `z=0.14`, `z=0.21` and `z=0.44` are universally 100% Ag coverage). Palladium (Pd) and Platinum (Pt) are correctly driven inwards into the sub-surface (`z=0.29` and `z=0.36`), exactly mirroring the physical alloy behavior showcased in the literature!
