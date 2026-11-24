---
name: mat-intercalation-voltage
description: Calculate the average intercalation voltage of cathode materials using MLIPs.
metadata:
  category: [materials]
  venv: [cpu, mlip]
---

# Intercalation Voltage

<!-- mcp-tools-note -->
> [!NOTE]
> Steps written `server.tool` are MCP tool calls: `mace.load_model` is the `load_model`
> tool of the `mace` server (`mcp__mace__load_model`, or
> `mcp__plugin_atomistic-skills_mace__load_model` when installed as a plugin).
> Without a connected server, run the same tools from the shell. Tools named in
> one command share a process, so a model loaded by `load_model` stays loaded:
>
> ```bash
> ${CLAUDE_SKILL_DIR}/../../venv/run mlip python -m src.mcp_server.cli mace load_model key=value relax_structure key=value
> ```

## Goal
To calculate the average open-circuit voltage (OCV) of an intercalation cathode material (e.g., Li$_x$M$_y$O$_z$) by computing the energy difference between the fully intercalated and de-intercalated states.

The average voltage $V$ is given by:
$$V = -\frac{E(\text{full}) - E(\text{empty}) - n \mu_{\text{metal}}}{n z}$$
where $E$ is the total energy in eV, $n$ is the number of intercalated ions, $z$ is the positive number of electrons transferred per ion, and $\mu_{\text{metal}}$ is the chemical potential per atom of the bulk metal. With these units, $V$ is in volts. Set $z=1$ for a monovalent reaction or $z=2$ for a divalent reaction; the script does not infer $z$ from the metal symbol.

## Instructions

1.  **Prepare Structures**:
    - Obtain the fully intercalated structure (e.g., LiFePO$_4$)
    - Create the de-intercalated structure by removing intercalating ions:

    ```bash
    ${CLAUDE_SKILL_DIR}/../../venv/run cpu python ${CLAUDE_SKILL_DIR}/scripts/remove_atoms.py \
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
    mace.load_model(model_name="MACE-MH-1", task_name="matpes_r2scan")

    # Relax full structure
    mace.relax_structure(
        structure_data="LiFePO4.cif",
        output_dir="voltage_calc/full_relax"
    )

    # Relax empty structure
    mace.relax_structure(
        structure_data="FePO4.cif",
        output_dir="voltage_calc/empty_relax"
    )

    # Relax bulk metal
    mace.relax_structure(
        structure_data="${CLAUDE_SKILL_DIR}/resources/Li_metal.cif",
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
    ${CLAUDE_SKILL_DIR}/../../venv/run cpu python ${CLAUDE_SKILL_DIR}/scripts/calculate_voltage.py \
        --e_full -123.45 \
        --e_empty -98.76 \
        --e_metal -1.23 \
        --n_metal 16 \
        --n_ions 4 \
        --electrons_per_ion 1 \
        --metal Li \
        --output voltage_calc/voltage_results.json
    ```

    **Parameters:**
    - `--e_full`: Total energy of fully intercalated structure (eV)
    - `--e_empty`: Total energy of de-intercalated structure (eV)
    - `--e_metal`: Total energy of bulk metal structure (eV)
    - `--n_metal`: Number of metal atoms in the bulk metal structure
    - `--n_ions`: Number of intercalated ions (difference between full and empty)
    - `--electrons_per_ion`: Positive finite electrons transferred per ion (default 1). Use `--electrons_per_ion 2` for a Mg²⁺/Mg, Ca²⁺/Ca or Zn²⁺/Zn reaction.
    - `--metal`: Symbol of intercalating ion (optional, for documentation)
    - `--output`: Path to save results as JSON (optional)

    The result records `electrons_per_ion` and the total transferred electron count `n_electrons`, in addition to the voltage and reaction energies. The default preserves existing monovalent calls.

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
**Contact:** [GitHub @learningmatter-mit](https://github.com/learningmatter-mit)
