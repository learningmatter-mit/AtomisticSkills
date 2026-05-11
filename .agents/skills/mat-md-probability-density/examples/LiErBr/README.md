# Example: Visualizing Li-Ion Probability Density in Li-Er-Br Halide SSE

This example provides the workflow to visualize the lithium-ion conduction pathways in the solid-state electrolyte $Li_{12}Er_{12}Br_{48}$ via time-averaged probability density. Given its superionic nature, calculating the ion spatial density after a Molecular Dynamics simulation serves to highlight the interconnected 3D lithium pathways within the crystal lattice.

## Workflow

### 1. Identify the MD Trajectory
Typically, you run an MD simulation at elevate temperature (e.g., 500K-1000K) to ensure sufficient site hopping events sample the available spatial density. In this example, we have provided a 500K NVT trajectory for reference:
- `Br48Er12Li12_500.0K_nvt.traj`

### 2. Calculate Probability Density
Execute the probability density extraction script. This maps the fractional coordinates of Li ions over the trajectory into a unified crystal grid and aggregates occupation probabilities. 

Because this is a relatively short trajectory, it contains "sparse" hopping events. We utilize the `--log` compression flag to mathematically enhance the visibility of intermediate saddle points in the diffusion pathway without diluting the background noise.

```bash
# Env: base-agent
python .agents/skills/mat-md-probability-density/scripts/calculate_probability_density.py \
    .agents/skills/mat-md-probability-density/examples/LiErBr/Br48Er12Li12_500.0K_nvt.traj \
    --species Li \
    --interval 0.2 \
    --ignore_ps 5.0 \
    --log \
    --output_chgcar .agents/skills/mat-md-probability-density/examples/LiErBr/CHGCAR_proba
```
In this command:
- `--interval 0.2` provides a smooth volumetric isosurface mapping of 0.2 Å resolution.
- `--ignore_ps 5.0` ensures the initial pre-equilibration positions do not bias the average probability map.
- `--log` scales the grid logarithmically to beautifully connect discrete trajectory hops into continuous 1D/3D tubes.

### 3. Visualizing in VESTA
Once the script successfully outputs `CHGCAR_proba` (which we have included in this directory), open it within VESTA:
1. Load `CHGCAR_proba` inside VESTA (this loads both the spatial grid and crystal structure).
2. Because we used `--log` compression, the **default Isosurface level** should perfectly highlight the continuous 3D Li diffusion pathways right out of the box!
3. Go to **Objects** panel > **Properties** > **Isosurfaces** to adjust colors (e.g., set the surface to yellow).
