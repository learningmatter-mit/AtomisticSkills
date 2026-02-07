---
name: melting-point
description: Calculate the melting temperature of a material using the solid-liquid interface (coexistence) method.
---

# Melting Point

## Goal
To determine the thermodynamic melting temperature ($T_m$) of a bulk material by equilibrating a solid-liquid interface in an NVE ensemble.

## Instructions

1.  **Background Research**: 
    - Search for the approximate melting point ($T_m$) and boiling/evaporation point ($T_{vap}$) of the material.
    - Choose a melting temperature $T_{melt}$ where $T_m < T_{melt} \ll T_{vap}$.
    - **MD Parameters**: Refer to the [molecular-dynamics](../molecular-dynamics/SKILL.md) skill for best practices on timesteps and monitors. In general, use a 2.0 fs timestep for systems without Hydrogen.

2.  **Phase Preparation**: 
    - **Solid**: Create a supercell using `create_supercell.py`.
    ```bash
    # Env: base-agent
    python .agent/skills/melting-point/scripts/create_supercell.py [input_structure.cif] [solid_supercell.cif] --min_length 20.0
    ```
    - **Liquid**: Melt a block using 1D-NPT (with mask) to ensure matching dimensions.
    ```bash
    mcp_mace_run_md(
        structure_data="solid_supercell.cif",
        temperature=2000,  # REPLACE with T_melt from Step 1
        ensemble="npt",
        steps=5000,
        timestep=2.0,      # Use 2.0 fs for most inorganic systems
        pressure=1.0,      # Apply positive pressure (1-2 bar) to prevent evaporation
        pressure_mask=[1, 0, 0], # REQUIRED: Must match the stacking axis (e.g., x-axis)
        output_dir="melt_stage"
    )
    ```
3.  **Interface Creation**: Use `create_interface.py` to concatenate the two phases.
    ```bash
    # Env: base-agent
    python .agent/skills/melting-point/scripts/create_interface.py solid.cif liquid.cif --axis 0 --output interface.cif
    ```
4.  **Relaxation**: Perform an ionic relaxation using the `relax_structure` MCP tool with `relax_cell=True`. This allows the unit cell to adjust (shrink/expand) to match the density, and remove the interface energy created by stacking the two cells.
    ```bash
    mcp_mace_relax_structure(structure_data="interface.cif", relax_cell=True)
    ```
5.  **Phase Verification**: Before running production MD, verify solid-liquid coexistence in all structures.
    
    First, extract reference atomic features:
    ```bash
    # Env: mace-agent (or matgl-agent)
    # Extract from pure solid - use explicit output path
    mcp_mace_predict_atomic_features(
        structure_data="solid_supercell.cif",
        output_path="<research_dir>/solid_features.json"
    )
    
    # Extract from pure liquid - use explicit output path
    mcp_mace_predict_atomic_features(
        structure_data="liquid_supercell.cif",
        output_path="<research_dir>/liquid_features.json"
    )
    ```
    
    Then verify phases:
    ```bash
    # Env: base-agent
    # Solid should be ~100% solid
    python .agent/skills/melting-point/scripts/check_phase.py solid_supercell.cif \
        --solid_features <research_dir>/solid_features.json \
        --liquid_features <research_dir>/liquid_features.json
    
    # Liquid should be ~100% liquid
    python .agent/skills/melting-point/scripts/check_phase.py liquid_supercell.cif \
        --solid_features <research_dir>/solid_features.json \
        --liquid_features <research_dir>/liquid_features.json
    
    # Interface should show ~50% solid/liquid coexistence
    python .agent/skills/melting-point/scripts/check_phase.py interface_relax/relaxed_structure.cif \
        --solid_features <research_dir>/solid_features.json \
        --liquid_features <research_dir>/liquid_features.json
    ```
    
    **Expected:**
    - Solid: ≥95% solid
    - Liquid: ≥95% liquid  
    - Interface: 40-60% solid (coexistence maintained)
    
    **If interface lost coexistence:** Adjust melting temperature or relaxation parameters.

6.  **Production**: Run an NVE MD simulation starting near the expected $T_m$ (e.g., 933K for Al) with the `monitor=True` parameter. This automatically launches the stability monitor in the background.
    ```bash
    mcp_mace_run_md(
        structure_data="relaxed_structure.cif", 
        temperature=933, 
        ensemble="nve", 
        steps=100000, 
        timestep=2.0,
        monitor=True, 
        monitor_type="melting",
        output_dir="production_md"
    )
    ```
7.  **Auto-Termination**: The integrated monitor will:
    - Check for temperature and potential energy stability.
    - Automatically stop the MD simulation when the melting point is reached.
    - Log termination status in the research log.
    - `mcp_mace_run_md` will return once the simulation stops (either by finishing all steps or by monitor termination).

8.  **Phase Validation**: Verify that the solid and liquid phases still coexist at the end of the simulation.
    ```bash
    # Note: If MD was killed, use the last frame from trajectory or the restart file if available.
    # Env: base-agent
    python .agent/skills/melting-point/scripts/check_phase.py production_md/final_structure.cif
    ```
    - **Fully Solidified**: The NVE starting temperature was too low.
    - **Fully Melted**: The NVE starting temperature was too high.
9.  **Analysis**: If coexistence is verified, calculate $T_m$ by averaging the temperature over the last 5 ps of the simulation.



## Examples

Creating a solid-liquid interface for Aluminum:
```bash
# Env: base-agent
python .agent/skills/melting-point/scripts/create_interface.py Al_solid.cif Al_liquid.cif --axis 0 --output Al_interface.cif
```

## Constraints
- **Box Dimensions**: The lattice parameters perpendicular to the stacking axis must be identical for both solid and liquid blocks.
- **Ensemble**: The final production run must be in the **NVE** ensemble to allow the temperature to evolve to $T_m$.
- **Environments**: Different MLIPs require specific Conda environments (e.g., `mace-agent`, `matgl-agent`). Ensure the scripts are run within the correct environment for the chosen model.
