---
name: chem-sorption-relax
description: Prepares supercells for porous frameworks based on minimum interplanar distance and relaxes them using standard MLIP relaxation tools.
category: [materials, chemistry]
---

# chem-sorption-relax

## Goal

To process porous frameworks (e.g., MOFs, COFs) for downstream molecular sorption calculations. It checks if the unit cell's interplanar distances are large enough (usually ≥ 12 Å for typical gases) to avoid self-interaction of gas molecules across periodic boundaries. If not, it builds an appropriate supercell. Finally, it uses a standard Machine Learning Interatomic Potential (MLIP) workflow to relax the structure.

## Prerequisites

- **Input**: A framework structure in CIF (or XYZ) format.
- **MLIP MCP Tool**: A relaxation tool such as `mcp_fairchem_relax_structure`, `mcp_mace_relax_structure`, or `mcp_matgl_relax_structure`.
- **Conda environment**: `base-agent` for the supercell builder logic, followed by the specific environment for the chosen MLIP (e.g., `fairchem-agent`).

## Instructions

1. **Build Supercell (if necessary)**: Determine if the input framework needs to be expanded. Use the provided utility to read the input CIF, check interplanar distances, build a supercell if they are below the threshold, and save the result.

```bash
# Env: base-agent
python .agents/skills/chem-sorption-relax/scripts/build_supercell.py \
    --structure path/to/framework.cif \
    --min-plane-dist 12.0 \
    --output-cif ./out/framework_supercell.cif
```

> [!TIP]
> If the script output indicates a `1x1x1` supercell was created (i.e. no expansion needed), you can just use your original CIF or the output CIF, as they will be identical. 

2. **Relax the Framework**: Relax the output structure using the MCP server environment. Ensure that the correct MLIP is loaded first.

```python
# Env: fairchem-agent (via MCP server)
mcp_fairchem_load_model(
    model_name="uma-s-1p2",
    device="auto"
)

mcp_fairchem_relax_structure(
    structure_data="./out/framework_supercell.cif",
    fmax=0.05,
    steps=500,
    optimizer="LBFGS",
    relax_cell=True,
    output_dir="./out/relaxed_framework"
)
```

### relax_structure.py Parameters
- `--structure`: Path to input CIF or XYZ.
- `--name`: Identifier used in output filenames.
- `--calculator`: Backend MLIP (`fairchem`, `mace`, `matgl`).
- `--model-name`: Named model (e.g. `uma-s-1p2`) or full path to checkpoint.
- `--task-name`: Multi-task head (`omol`, `omat`, `odac`, `oc20`, `omc`).
- `--optimizer`: `LBFGS` (default) or `FIRE`.
- `--fmax`: Force convergence threshold in eV/Å (default: 0.05).
- `--steps`: Maximum optimizer steps (default: 500).
- `--relax-cell`: Relax unit cell (default: True). Use `--fixed-cell` to fix cell.
- `--output-dir`: Directory to save `<name>.relaxed.cif` and `relax_results.json`.

3. **Proceed to downstream tasks**:
The relaxed CIF file (e.g. `./out/relaxed_framework/<name>.relaxed.cif`) from step 2 is now ready for use in [chem-sorption-widom](../chem-sorption-widom/SKILL.md) and [chem-sorption-gcmc](../chem-sorption-gcmc/SKILL.md).

## Examples

**Full workflow:**

1. Build supercell:
```bash
# Env: base-agent
python .agents/skills/chem-sorption-relax/scripts/build_supercell.py \
    --structure my_cof.cif \
    --min-plane-dist 12.0 \
    --output-cif ./results/COF-1_supercell.cif
```

2. Relax with UMA-S-1p2 via MCP Tool:
```python
mcp_fairchem_load_model(
    model_name="uma-s-1p2",
    device="auto"
)

mcp_fairchem_relax_structure(
    structure_data="./results/COF-1_supercell.cif",
    fmax=0.05,
    steps=500,
    optimizer="LBFGS",
    output_dir="./results/relaxed"
)
```

## Constraints

- **Input Structure**: The initial framework should be somewhat reasonable; highly distorted structures might fail during relaxation.
- **Minimum Distance**: The `--min-plane-dist` should be at least 2 × (cut-off radius) of the probe gas interaction length (typically 12 Å for CO2 or N2).

---

**Authors:** Artur Lyssenko, Sauradeep Majumdar
**Contact:** [GitHub @arturlyssenko12](https://github.com/arturlyssenko12), [GitHub @sauradeep93](https://github.com/sauradeep93)
