---
name: amorphorization
description: Generate amorphorized structures from crystalline starting points using a melt-quench MD protocol.
---

# Amorphorization

## Goal
To generate disordered, amorphous structures from crystalline inputs using molecular dynamics (MD). This is achieved through a "melt-quench" protocol, where the material is heated above its melting point and then rapidly cooled to "freeze" the liquid-like disorder.

## Protocol: Melt-Quench
The standard Computational amorphization protocol involves:

1.  **Supercell Setup**: The system must be large enough to avoid spurious periodicity effects in the amorphous state. Generally, $>100$ atoms is recommended.
2.  **Melting (Stage A)**: Heat the system to $T_{melt}$. $T_{melt}$ should be significantly higher than the experimental melting point (often 1000K higher) to ensure rapid loss of crystalline memory within MD timescales.
3.  **Equilibration (Stage A/B)**: Maintain the liquid at $T_{melt}$ for several picoseconds to ensure structural randomized.
4.  **Quenching (Stage B)**: Cool the system linearly to the target temperature (e.g., 300K).
    - **Cooling Rate**: A critical parameter. Typical MD cooling rates are $1-10$ K/ps ($10^{12}-10^{13}$ K/s). Slower rates yield more stable, realistic amorphous structures but are computationally expensive.
5.  **Annealing/Equilibration (Stage C)**: Relax the density and local structure at the target temperature.
6.  **Quenched/Static Relaxation (Stage D)**: Perform a final geometry optimization (0K) to find the local energy minimum of the amorphous state.

## Instructions

### 1. Preparation
- **Supercell**: Use the `prep_supercell.py` helper script. By default, it generates an orthorhombic conventional supercell with approximately 100 atoms, ensuring a robust starting point for amorphization.
```bash
python .agent/skills/amorphorization/scripts/prep_supercell.py --input crystalline.cif --output supercell.cif
```
- **Foundation Potential**: Select a robust model like `MACE-MP-large` or `CHGNet` using the `mcp_mace_load_model` (or similar) tool.

### 2. Execution (The Melt-Quench Cycle)
Amorphization is performed by calling the `run_md` tool in a sequence:

#### Stage 1: Melting
Heat the system to a high temperature (e.g., 3000K) to eliminate crystalline order.
- **Tool**: `mcp_mace_run_md`
- **Thermostat**: `nvt_langevin` (Robust for high-T dynamics).
- **Parameters**: `temperature=3000`, `steps=5000` (10 ps), `ensemble="nvt_langevin"`, `timestep=2.0`.

#### Stage 2: Quenching
Cool the system rapidly to the target temperature (e.g., 300K).
- **Tool**: `mcp_mace_run_md`
- **Thermostat**: `nvt_langevin` (Supports specific `set_temperature` ramping).
- **Monitor**: Use `monitor_type="quenching"` and `monitor_params={"temperature_end": 300, "steps": 5000}`.
- **Parameters**: `temperature=3000` (start), `steps=5000` (10 ps), `ensemble="nvt_langevin"`.
- **Note**: Ensure the input structure is the output of Stage 1.

#### Stage 3: Equilibration
Relax the structure at the target temperature to reach equilibrium distribution.
- **Tool**: `mcp_mace_run_md`
- **Thermostat**: `nvt_bussi` (Bussi-Donadio-Parrinello) - Provides correct canonical sampling.
- **Parameters**: `temperature=300`, `steps=2500` (5 ps), `ensemble="nvt_bussi"`.

### 3. Analysis & Verification
Use the `analyze_amorphous.py` script to verify the results:
- **RDF (Radial Distribution Function)**: Confirm the absence of long-range order.
- **Coordination Number**: Check local bonding environments.

## Helper Scripts
- `prep_supercell.py`: Expands a unit cell to a supercell.
- `analyze_amorphous.py`: Calculates RDF and coordination numbers from the final structure.
- **RDF (Radial Distribution Function)**: Crystalline structures show discrete, sharp peaks at long distances. Amorphous structures show a sharp first peak, a broader second peak, and then decay to 1.0 (no long-range order).
- **Coordination Number**: Check if the local coordination (e.g., 4 for Si) is maintained despite the global disorder.

## Foundation Potential Selection
- [foundation-potentials](../foundation-potentials/SKILL.md)
- **MACE-MP-large** or **CHGNet** are recommended for high-temperature MD as they are trained on diverse configurations.

## Examples
See `.agent/skills/amorphorization/examples/` for validated amorphous structures.
