---
name: diffusion-analysis
description: Calculate ionic diffusion coefficients and activation energy from MD trajectories using pymatgen.
---

# Diffusion Analysis

## Goal
To accurately calculate the ionic diffusivity ($D$) and activation energy ($E_a$) of specific atomic species in a material using Molecular Dynamics (MD) trajectories and the Arrhenius relation: $D(T) = D_0 \exp\left(-\frac{E_a}{k_B T}\right)$.

## Instructions

1.  **MD Preparation**: Run NVT MD simulations at multiple temperatures (typically 4-6 points between 600K and 1200K). 
    - Use the `run_md` tool from a relevant potential skill (e.g., [mace](../mace/SKILL.md) or [matgl](../matgl/SKILL.md)).
    - Ensure supercells are sufficiently large (> 10 Å in all dimensions).
    - **Optimization**: Use the `diffusion` monitor to automatically stop simulations once the transport properties have converged.
        ```python
        mace.run_md(
            structure, 
            monitor=True, 
            monitor_type="diffusion",
            monitor_params={"specie": "Li", "threshold": 0.05, "check_interval_ps": 5.0}
        )
        ```

2.  **Individual Diffusivity Analysis**: For each temperature directory, run the analysis script to extract the diffusivity and Mean Square Displacement (MSD).
    ```bash
    # Env: base-agent
    python .agent/skills/diffusion-analysis/scripts/analyze_diffusion.py \
        results/md_600K/trajectory.traj \
        --species Li \
        --temperature 600 \
        --ignore_ps 5.0 \
        --output_dir results/md_600K
    ```
    - `--ignore_ps`: Time to skip for equilibration. Default is 5.0 ps.
    - The script automatically detects the frame interval from the `.log` file if present.

3.  **Activation Energy Fitting**: Once all individual results are generated, use the fitting script to combine data and perform a weighted Arrhenius fit.
    ```bash
    # Env: base-agent
    python .agent/skills/diffusion-analysis/scripts/calculate_activation_energy.py results/
    ```
    - The script looks for `md_*K/diffusion_results.json` patterns.
    - It performs error propagation to calculate uncertainty in $E_a$ and extrapolated room-temperature conductivity.

## Examples

- **Superionic Conductor (LGPS)**: A complete workflow demonstration including supercell preparation, multi-temperature MD, and final Arrhenius plotting for $Li_{10}GeP_2S_{12}$ is available in the [LGPS Example](examples/LGPS/README.md).

## Constraints
- **Trajectory Format**: Trajectories MUST be in ASE `.traj` format.
- **Environments**: All analysis scripts require the **base-agent** conda environment.
- **Linearity**: The diffusivity calculation assumes a linear diffusive regime. Always inspect the generated MSD plots to ensure linearity after the `ignore_ps` period.
- **Atom Count**: To ensure statistical significance, the system should contain a sufficient number of mobile ions (> 20 recommended).
- **Paths**: Always use relative paths from the project root when executing scripts.


Author: Bowen Deng
Contact: github username <bowen-bd>
