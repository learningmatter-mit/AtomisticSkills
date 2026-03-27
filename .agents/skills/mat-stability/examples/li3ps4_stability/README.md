# Li3PS4 Stability and ECW Calculation Example

This example demonstrates the complete end-to-end pipeline for evaluating the 0K thermodynamic stability ($E_{hull}$) and the intrinsic Electrochemical Stability Window (ECW) of $\text{Li}_3\text{PS}_4$. 

It seamlessly combines functionality from both the `mat-stability` and `mat-electrochemical-window` skills.

## Overview
The pipeline consists of three automated steps:
1.  **Query MP Hull**: Retrieves all unique ground-state solid phases within the `Li-P-S` chemical subsystem computed at the r2SCAN level of theory.
2.  **MLIP Relaxation**: Relaxes all retrieved structures uniformly using the MatGL `TensorNet-MatPES-r2SCAN-v2025.1-PES` foundation model.
3.  **Phase Diagram Construction**: Constructs a strict convex hull using PhaseDiagram, assesses the $E_{hull}$ for $\text{Li}_3\text{PS}_4$, and evaluates the upper/lower thermodynamic bounds ($V_{red}$, $V_{ox}$) against $\text{Li/Li}^+$.

## Usage

Due to cross-environment isolation (base vs. mlip agent), this pipeline is executed via discrete steps. The AI agent orchestrates these steps natively.

### Step 1: Query Hull
```bash
conda run -n base-agent python ../../scripts/query_mp_hull.py \
    --formula "Li-P-S" \
    --target "Li3PS4" \
    --thermo_type "R2SCAN" \
    --output hull_structures/
```

### Step 2: MLIP Relaxation (via MCP Server)
The agent executes the MatGL MCP tool directly on the `hull_structures/` directory:
```python
mcp_matgl_relax_structure(
    structure_data="hull_structures/",
    relax_cell=True,
    model_name="TensorNet-MatPES-r2SCAN-v2025.1-PES",
    fmax=0.05,
    steps=20,
    output_dir="relaxed_structures/"
)
```

### Step 3: Compute E_hull and ECW
```bash
conda run -n base-agent python ../../scripts/compute_ehull.py \
    --hull_manifest hull_entries.json \
    --relaxed_dir relaxed_structures/ \
    --target_material Li3PS4 \
    --calculate_ecw \
    --mobile_ion Li \
    --output stability_analysis.json
```

## Expected Output
The script automatically generates a `stability_analysis.json` containing the findings.

```json
{
  "target_formula": "Li3PS4",
  "energy_above_hull_meV": 0.0,
  "stability": "STABLE",
  "assessment": "On the convex hull - thermodynamically stable",
  "decomposition_products": [
    {
      "phase": "Li3PS4",
      "fraction": 1.0
    }
  ],
  "num_phases_on_hull": 11,
  "v_red": 0.6300951111002517,
  "v_ox": 2.2291589139268674,
  "ecw": "[0.63 V, 2.23 V]"
}
```
