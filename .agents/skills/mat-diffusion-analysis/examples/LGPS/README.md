## Li Diffusion in LGPS: Methodology and Analysis

This example demonstrates a complete workflow for calculating the lithium-ion activation energy in the superionic conductor Li10GeP2S12 (LGPS).

### Workflow Steps

1.  **Structure Preparation**:
    - Query the LGPS structure (`mp-696128`) and expand to a $2 \times 2 \times 1$ supercell (~200 atoms) to ensure valid diffusion statistics and avoid self-interaction.
    - [LGPS_221.cif](file:///home/bdeng/projects/AtomisticSkills/.agents/skills/mat-diffusion-analysis/examples/LGPS/LGPS_221.cif)

2.  **Molecular Dynamics**:
    - Run 20 ps NVT simulations at 600, 700, 800, 900, and 1000 K using the `MatPES-r2SCAN` foundation potential.
    - MD parameters: 2 fs timestep, logging every 100 steps (0.2 ps).

3.  **Diffusivity Analysis**:
    - Analyze the Li-ion Mean Square Displacement (MSD) using the `analyze_diffusion.py` script.
    - **Equilibration Skip**: The first **5.0 ps** are ignored to ensure the system is at thermal equilibrium.
    - **Uncertainty**: The statistical error in diffusivity is calculated from the structural variance of the MSD.

#### Temperature-Dependent MSD Plots
````carousel
![Li MSD at 600K](file:///home/bdeng/projects/AtomisticSkills/.agents/skills/mat-diffusion-analysis/examples/LGPS/msd_Li_600K.png)
<!-- slide -->
![Li MSD at 700K](file:///home/bdeng/projects/AtomisticSkills/.agents/skills/mat-diffusion-analysis/examples/LGPS/msd_Li_700K.png)
<!-- slide -->
![Li MSD at 800K](file:///home/bdeng/projects/AtomisticSkills/.agents/skills/mat-diffusion-analysis/examples/LGPS/msd_Li_800K.png)
<!-- slide -->
![Li MSD at 900K](file:///home/bdeng/projects/AtomisticSkills/.agents/skills/mat-diffusion-analysis/examples/LGPS/msd_Li_900K.png)
<!-- slide -->
![Li MSD at 1000K](file:///home/bdeng/projects/AtomisticSkills/.agents/skills/mat-diffusion-analysis/examples/LGPS/msd_Li_1000K.png)
````

4.  **Activation Energy Fitting**:
    - Use `calculate_activation_energy.py` to perform a weighted linear regression on the Arrhenius data.
    - **Weighted Fit**: Accounts for the standard deviation of diffusivity at each temperature.
    - **Covariance Analysis**: Propagates errors to derive the uncertainty in both $E_a$ and the extrapolated room-temperature conductivity ($\sigma_{RT}$).

### Results

- **Activation Energy ($E_a$)**: **0.152 $\pm$ 0.035 eV**
- **RT Conductivity (300 K)**: **91.44 $\pm$ 79.18 mS/cm**

![Final Arrhenius Plot](file:///home/bdeng/projects/AtomisticSkills/.agents/skills/mat-diffusion-analysis/examples/LGPS/arrhenius_plot.png)

### Files
- `LGPS_221.cif`: Initial supercell structure.
- `arrhenius_plot.png`: Final publication-quality Arrhenius plot.
- `msd_Li_600K.png`: Example MSD plot showing ps units and diffusive fit.
