# Cu-Ag Monte Carlo Simulation Example

This example demonstrates how to use a trained Cluster Expansion (CE) model to run finite-temperature Monte Carlo (MC) simulations for a disordered material.

## Files
- `cluster_expansion.json`: The trained Cluster Expansion model (serialized).
- [primordial.cif](primordial.cif): The disordered primordial structure used to define the configuration space.
- `mc_300K_energy.png`: Plot of the total energy evolution during a canonical MC simulation at 300 K.
- [mc_300K_initial.cif](mc_300K_initial.cif): The initial random structure used for the MC simulation.
- [mc_300K_final.cif](mc_300K_final.cif): The final equilibrated structure after 10,000 MC steps.

## Workflow Description

### 1. Prerequisite: Trained CE Model
This example assumes you have already trained a Cluster Expansion model using the `cluster-expansion` skill. The `cluster_expansion.json` file provided here is the output of that training process on the Cu-Ag system.

### 2. Monte Carlo Simulation
- **Ensemble**: Canonical (fixed composition 50% Cu, 50% Ag).
- **Temperature**: 300 K.
- **Supercell**: 4x4x4 (64 atoms).
- **Duration**: 10,000 steps.
- **Outcome**: The system was initialized in a random configuration and allowed to equilibrate. The energy trajectory shows the relaxation of the system towards an equilibrium state.

## How to Run
You can run a similar simulation using the MCP tool:

```python
mcp_smol_run_monte_carlo(
    ce_file="cluster_expansion.json",
    supercell_matrix=[[4,0,0],[0,4,0],[0,0,4]],
    temperature=300,
    steps=10000,
    trajectory_file="mc_trajectory.h5"
)
```
