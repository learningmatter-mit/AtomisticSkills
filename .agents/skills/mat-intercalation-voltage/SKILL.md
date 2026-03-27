---
name: mat-intercalation-voltage
description: Calculate the average intercalation voltage of cathode materials using MLIPs.
category: [materials]
---

# Intercalation Voltage

## Goal
To calculate the average open-circuit voltage (OCV) of an intercalation cathode material (e.g., Li$_x$M$_y$O$_z$) by computing the energy difference between the fully intercalated (charged) and de-intercalated (discharged) states.

The average voltage $V$ is given by:
$$V = -\frac{E(\text{full}) - E(\text{empty}) - n \mu_{\text{metal}}}{n}$$
where $E$ is the total energy, $n$ is the number of intercalated ions, and $\mu_{\text{metal}}$ is the chemical potential per atom of the bulk metal.

## Instructions

1.  **Prepare Structures**:
    - Obtain the fully intercalated structure (e.g., LiFePO$_4$)
    - Create the de-intercalated structure by removing intercalating ions:
    
    ```bash
    # Env: base-agent
    python .agents/skills/mat-intercalation-voltage/scripts/remove_atoms.py \
        LiFePO4.cif \
        --remove Li \
        --output FePO4.cif
    ```
    
    - Get the bulk metal structure from `resources/` (e.g., `Li_metal.cif`)

2.  **Select Foundation Potential**:
    Choose an appropriate MLIP based on the system (see [foundation-potentials.md](../../skills/ml-foundation-potentials/SKILL.md)). For cathode materials, `MACE-MH-1` with `matpes_r2scan` head or `CHGNet-MatPES-r2SCAN` are recommended.

3.  **Relax Structures Using MCP Tools**:
    
    Load the model and relax all three structures:

    ```bash
    # Load the model (example with MACE)
    mcp_mace_load_model(model_name="MACE-MH-1", task_name="matpes_r2scan")
    
    # Relax full structure
    mcp_mace_relax_structure(
        structure_data="LiFePO4.cif",
        output_dir="voltage_calc/full_relax"
    )
    
    # Relax empty structure
    mcp_mace_relax_structure(
        structure_data="FePO4.cif",
        output_dir="voltage_calc/empty_relax"
    )
    
    # Relax bulk metal
    mcp_mace_relax_structure(
        structure_data=".agents/skills/mat-intercalation-voltage/resources/Li_metal.cif",
        output_dir="voltage_calc/metal_relax"
    )
    ```

4.  **Extract Energies**:
    From each relaxation output directory, extract:
    - `E_full`: Energy from `full_relax/result.json`
    - `E_empty`: Energy from `empty_relax/result.json`
    - `E_metal`: Energy from `metal_relax/result.json`
    - `n_metal`: Number of atoms in the relaxed metal structure
    - `n_ions`: Count difference of intercalating ions between full and empty structures

5.  **Calculate Voltage**:
    
    ```bash
    # Env: base-agent
    python .agents/skills/mat-intercalation-voltage/scripts/calculate_voltage.py \
        --e_full -123.45 \
        --e_empty -98.76 \
        --e_metal -1.23 \
        --n_metal 16 \
        --n_ions 4 \
        --metal Li \
        --output voltage_calc/voltage_results.json
    ```

    **Parameters:**
    - `--e_full`: Total energy of fully intercalated structure (eV)
    - `--e_empty`: Total energy of de-intercalated structure (eV)
    - `--e_metal`: Total energy of bulk metal structure (eV)
    - `--n_metal`: Number of metal atoms in the bulk metal structure
    - `--n_ions`: Number of intercalated ions (difference between full and empty)
    - `--metal`: Symbol of intercalating ion (optional, for documentation)
    - `--output`: Path to save results as JSON (optional)

## Available Metal Structures

The following bulk metal structures are available in `resources/`:
- `Li_metal.cif` - Lithium (BCC)
- `Na_metal.cif` - Sodium (BCC)
- `Mg_metal.cif` - Magnesium (HCP)
- `Ca_metal.cif` - Calcium (FCC)
- `K_metal.cif` - Potassium (BCC)
- `Zn_metal.cif` - Zinc (HCP)

All structures are queried from Materials Project and represent the most stable phases.

## Example

See [examples/LiFePO4/](examples/LiFePO4/) for a complete worked example (MACE-MH-1 r2SCAN, 3.26 V vs 3.4 V experimental).

## Constraints
- **Host Consistency**: The number of host atoms must be identical in both full and empty structures
- **MLIP Consistency**: Use the same MLIP model for all three relaxations
- **Metal Phase**: Use the provided metal structures from `resources/` which are the most stable phases from Materials Project
- **Temperature**: This calculation provides the 0K OCV; entropy effects are neglected
---

**Author:** Bowen Deng  
**Contact:** [GitHub @bowen-bd](https://github.com/bowen-bd)
