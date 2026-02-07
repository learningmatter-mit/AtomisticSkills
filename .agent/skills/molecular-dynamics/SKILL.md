---
name: molecular-dynamics
description: Best practices and tools for running stable Machine Learning Interatomic Potential (MLIP) molecular dynamics.
---

# Molecular Dynamics

## Goal
To perform stable and accurate molecular dynamics simulations using MLIPs, ensuring physical correctness and avoiding common "explosions" associated with neural network potentials.

## Instructions

### 1. Monitoring Stability
MD stability monitoring is integrated directly into the `run_md` tool via ASE callbacks. This ensures zero-latency response to instabilities and simplifies the simulation workflow.

- **Enable Monitoring**: Set `monitor=True` and specify `monitor_type` (single string or list).
    - `explosion`: Safety check. Stops if T > 10,000K or NaN. Recommended for all unstable simulations.
    - `equilibration`: Convergence check. Stops once temperature and potential energy stabilize (e.g., for production runs).
    - `overshoot`: Thermostat check. Stops if T deviates significantly from target (T-target > 200K).
    - `volume`: NPT stability check. Stops if volume expands by 2x or contracts to 0.2x of initial.
    - `diffusion`: Convergence check for transport properties. Stops once the relative error of diffusivity for a specific `specie` (default Li) falls below a `threshold` (default 0.1).
        - **Parameters**: `specie`, `threshold`, `check_interval_ps` (default 5.0), `ignore_ps` (initial equilibration to skip, default 5.0).
    - `quenching`: Linear temperature ramp. Updates the thermostat target every step to move from `temperature` to `temperature_end` over a specified number of `steps`.
        - **Best Practice**: Use `dyn.set_temperature(temperature_K=T)` inside the ramping callback. This is critical for thermostats like `Langevin` to update internal noise/coupling coefficients.
        - **Advanced Thermostats**: For `NoseHooverChainNVT` and `MTKNPT`, where `set_temperature` might be missing, manual updates to internal attributes (`_kT`, `_Q`, `_W`) are required to keep the damping frequency consistent.

- **Example Usage**:
    ```python
    # MACE example with multiple monitors
    mace.run_md(structure, monitor=True, monitor_type=["explosion", "equilibration"])
    ```

- **Quenching Template (MCP Tool Call)**:
    ```json
    {
      "tool": "mcp_mace_run_md",
      "arguments": {
        "structure_data": "initial_structure.cif",
        "temperature": 3000.0,
        "steps": 5000,
        "timestep": 2.0,
        "ensemble": "nvt_langevin",
        "monitor": true,
        "monitor_type": "quenching",
        "monitor_params": {
          "temperature_end": 300.0,
          "steps": 5000
        },
        "output_dir": "research/quenching_output"
      }
    }
    ```

- **Action**: When a monitor triggers, the simulation stops immediately with a `status: "stopped"` and a clear `stop_reason` in the result dictionary.

### 2. Parameter Initialization
- **Time Step**: 
    - **2.0 fs**: Recommended for most systems without light elements (Hydrogen).
    - **0.5 - 1.0 fs**: Use for systems containing Hydrogen, or at very high temperatures (> 2000K) to maintain stability.
- **Thermostat**: Use a coupling constant (`taut`) around $100 \times \text{timestep}$.
- **Temperature Ramp**: Start at a low temperature (50K) and ramp to the target to avoid "shock" waves from initial overlaps.

### 3. Handling Instability
If a simulation explodes:
1.  **Reduce Timestep**: Try 0.5 fs.
2.  **Ramp Temperature**: Use a slower heating rate.
3.  **Check Potential**: Consider if the chemistry is within the training range of the foundation potential. If not, use the [mlip-training](../mlip-training/SKILL.md) skill.

## Examples

Monitoring stability is handled automatically by the ASE callbacks. When a monitor is triggered, the stop reason is logged to `stdout` and saved in the result dictionary.

## Constraints
- **Termination**: If a monitor triggers an explosion, terminate the task and adjust parameters. Do not proceed with unstable trajectories.
- **Reporting**: Always report simulation parameters (ensemble, T, timestep, duration) in the research report.
