---
name: surface-energy
description: Calculate surface energy of various (hkl) planes and generate the equilibrium crystal shape (Wulff shape).
---

# Surface Energy Calculation

## Goal
To determine the surface energy ($\gamma$) of different crystallographic planes (hkl) and construct the equilibrium crystal shape (Wulff shape) using structural relaxation with Machine Learning Interatomic Potentials (MLIPs).

## Instructions

1.  **Select Level of Theory**: Choose the target accuracy level for surface energy calculations.
    - **Recommended**: r2SCAN-level foundation potentials for high accuracy in inorganic systems.
    - **Examples**: `CHGNet-MatPES-r2SCAN-2025.2.10-2.7M-PES` (MatGL), `TensorNet-MatPES-r2SCAN-v2025.1-PES` (MatGL), or `MACE-MH-1` with `matpes_r2scan` head.
    - See [foundation-potentials](../../skills/foundation-potentials/SKILL.md) for detailed guidance.

2.  **Relax Bulk Reference**: Perform a high-accuracy relaxation of the bulk material to serve as the reference energy.
    ```bash
    # Env: matgl-agent
    mcp_matgl_load_model(model_name="CHGNet-MatPES-r2SCAN-2025.2.10-2.7M-PES")
    mcp_matgl_relax_structure(
        structure_data="bulk.cif",
        relax_cell=True,
        fmax=0.01,
        output_dir="bulk_relaxation/"
    )
    ```
    **Note**: Record the final energy per atom ($E_{bulk}$).

3.  **Generate Slabs**: Create oriented slabs for the target (hkl) planes.
    ```bash
    # Env: base-agent
    python .agent/skills/surface-energy/scripts/create_slabs.py \
        --bulk bulk_relaxation/relaxed_structure.cif \
        --max_index 1 \
        --min_thickness 10.0 \
        --vacuum 15.0 \
        --output slabs/
    ```
    This script generates slabs for all unique planes up to the specified `max_index`.

4.  **Relax Slabs**: Perform structural relaxation on all generated slabs.
    ```bash
    # Env: matgl-agent
    mcp_matgl_load_model(model_name="CHGNet-MatPES-r2SCAN-2025.2.10-2.7M-PES")
    mcp_matgl_relax_structure(
        structure_data="slabs/", 
        relax_cell=False,  # DO NOT relax cell for slabs (fixed area)
        fmax=0.02,
        output_dir="slab_relaxations/"
    )
    ```
    **Important**: Keep the unit cell fixed (`relax_cell=False`) to maintain the target surface area.

5.  **Calculate Surface Energy**: Compute the surface energy for each plane.
    ```bash
    # Env: base-agent
    python .agent/skills/surface-energy/scripts/calculate_surface_energy.py \
        --bulk_energy_per_atom -4.567 \
        --slab_dir slab_relaxations/ \
        --output surface_energies.json
    ```
    Surface energy is calculated as:
    $$\gamma = \frac{E_{slab} - N \cdot E_{bulk}}{2A}$$
    where $E_{slab}$ is the total energy of the slab, $N$ is the number of atoms in the slab, $E_{bulk}$ is the energy per atom of the bulk, and $A$ is the surface area.

6.  **Generate Wulff Shape**: Construct the Wulff shape from the calculated surface energies.
    ```bash
    # Env: base-agent
    python .agent/skills/surface-energy/scripts/generate_wulff.py \
        --energies_json surface_energies.json \
        --bulk bulk_relaxation/relaxed_structure.cif \
        --output wulff_shape.png
    ```

## Examples

### Example 1: Aluminum (fcc) Surface Energy
```bash
# Generate slabs up to index 1 (100, 110, 111)
python .agent/skills/surface-energy/scripts/create_slabs.py --bulk Al.cif --max_index 1

# Load and run relaxations using CHGNet
mcp_matgl_load_model(model_name="CHGNet-MatPES-r2SCAN-2025.2.10-2.7M-PES")
mcp_matgl_relax_structure(structure_data="Al.cif", relax_cell=True, output_dir="bulk_relax")
mcp_matgl_relax_structure(structure_data="slabs/", relax_cell=False, output_dir="slab_relax")

# Calculate and generate Wulff shape
python .agent/skills/surface-energy/scripts/calculate_surface_energy.py --bulk_energy_per_atom -3.36 --slab_dir slab_relax/
python .agent/skills/surface-energy/scripts/generate_wulff.py --energies_json surface_energies.json --bulk Al.cif
```

## Constraints
- **Cell Relaxation**: Do NOT relax the unit cell during slab relaxation. The surface area must remain constant to match the bulk reference.
- **Vacuum**: Ensure sufficient vacuum (typically >15 Å) to avoid interactions between periodic images.
- **Slab Thickness**: Ensure sufficient slab thickness (typically >10 Å) to recover bulk-like behavior in the center of the slab.
- **Consistency**: Use the SAME MLIP and convergence settings for both bulk and slab relaxations.


Author: Bowen Deng
Contact: github username <bowen-bd>
