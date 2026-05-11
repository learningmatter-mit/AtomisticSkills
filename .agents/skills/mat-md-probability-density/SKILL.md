---
name: mat-md-probability-density
description: Calculate and visualize the probability density of diffusing ions from a Molecular Dynamics (MD) trajectory.
category: [materials]
---

# MD Probability Density Visualization

## Goal
To visualize the spatial probability density of mobile ions (e.g., Li, Na) from an MD simulation trajectory. This helps in understanding conduction pathways and identifying preferred occupation sites within the crystal structure. The output is a volumetric data object in CHGCAR format, which can be easily visualized using VESTA.

## Instructions

1.  **MD Simulation**: Run an MD simulation at an appropriate temperature to observe sufficient diffusion events. 
    > Note: Short MD trajectories (e.g., ≤10 ps) often have too few discrete ion hops to naturally form continuous probability density tubes. The resulting density will look like isolated blobs exactly at the crystal lattice sites. To visualize continuous macroscopic diffusion pathways for short trajectories, use the `--log` compression flag to mathematically connect the sparse pathways.
    - The trajectory is typically saved to `trajectory.traj`.
    - Ensure `supercell_min_length` is reasonably large (>10 Å) to avoid finite-size artifacts in the density mapping.
    - Allow the simulation to run long enough so that the ions sample the entire available volume (e.g., 50-100 ps or more).

2.  **Calculate Probability Density**: Use the provided script to extract the fractional coordinates of the targeted species over time and convert them into a spatial density grid.
    ```bash
    # Env: base-agent
    python .agents/skills/mat-md-probability-density/scripts/calculate_probability_density.py \
        results/md_600K/trajectory.traj \
        --species Li \
        --interval 0.2 \
        --ignore_ps 5.0 \
        --output_chgcar results/md_600K/CHGCAR_proba
    ```
    - `--species`: The specific diffusing ion to visualize.
    - `--interval`: Grid spacing in Angstroms (0.1 to 0.5 is recommended). Smaller values give smoother isosurfaces but take longer to process and generate larger files. Defaults to `0.2` Å.
    - `--ignore_ps`: The equilibration time to discard from the beginning of the trajectory.
    - The script will automatically detect the frame time step if a `.log` file is available alongside the `.traj` file.

3.  **Visualize in VESTA**:
    *   Open the output `CHGCAR` (or `CHGCAR_proba`) file in VESTA.
    *   **Crucial VESTA Settings**:
        *   Because we apply Gaussian smoothing and optional logarithmic compression, simply open **Objects** panel > **Properties** > **Isosurfaces** to adjust colors (e.g. set the surface to yellow).
        *   If you did not use `--log` compression on a sparse timeline, the peak values may be spread out. If you don't see any 3D clouds, your **Isosurface level** is too high. Try lowering it (e.g., to `0.001` or lower) until you see continuous 3D ion diffusion channels connecting the lattice sites. If you used `--log`, the **default Isosurface level** will usually connect the pathway out of the box.

## Examples
- A fast workflow description based on a $Li_{12}Er_{12}Br_{48}$ Solid-State Electrolyte can be found in the [LiErBr Example](examples/LiErBr/README.md).

## Constraints
- **Environments**: The script requires the **base-agent** conda environment.
- **File formats**: The trajectory should be provided in `ASE .traj` format.
- **Memory Limits**: Avoid setting `--interval` too small ($< 0.1$) on large supercells, as this may result in extremely large 3D grid sizes and out-of-memory errors.

---
**Author**: Bowen Deng  
**Contact**: [GitHub @bowen-bd](https://github.com/bowen-bd)
