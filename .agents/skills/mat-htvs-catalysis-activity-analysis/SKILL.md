---
name: mat-htvs-catalysis-activity-analysis
description: Calculate thermodynamic catalytic activity (OER, ORR, etc.) from HTVS binding energies, plot Free Energy steps, and acquire scaling Volcano plots.
category: materials
---
# Analyze Catalysis Activity Thermodynamics (HTVS)

## Goal
Extract raw DFT binding energies from HTVS, apply standard zero-point energy (ZPE) and entropy (-TS) corrections, and compute the theoretical mechanism steps for varied catalytic reactions (OER, ORR). The script empirically acquires optimal scaling lines from database sets by executing multivariate linear regression on step energies against the primary descriptor and outputs `[rxn]_free_energy_steps.png` and `[rxn]_volcano.png` to aid ranking.

## Configuration & Safety (CRITICAL)

Wait! HTVS operations directly interact with research databases. Before running any commands:
1.  **Expose the Context**: Explicitly state the `settings_module` and `group_name` you are about to use.
2.  **Request Confirmation**: Ask the user: *"I am about to perform this operation on the [GROUP_NAME] project within the [SETTINGS_MODULE] database. Is this correct?"*
3.  **Do NOT proceed** until the user gives explicit approval.

## Instructions

### 1. Prerequisites
- A standardized `binding_energies.json` payload file containing theoretical free energy step mapping. 
- To automatically generate this JSON payload file using raw DFT calculations from your active Django database, you must first execute the auxiliary data-extraction skill `.agents/skills/mat-htvs-genbindingenergy`.

### 2. Run the Analysis Script
Once you have your generated JSON payload, execute the core analysis script using the base environment:

```bash
# Env: htvs-agent
python .agents/skills/mat-htvs-catalysis-activity-analysis/scripts/catalysis_analysis.py \
    --reaction OER \
    --data_file ./research/current_research_dir/binding_energies.json \
    --output_dir ./research/current_research_dir
```

> **Note**: For validating algorithmic outputs without importing complex external datasets, refer to `.agents/skills/mat-htvs-catalysis-activity-analysis/examples/README.md` for instructions on evaluating dummy reference metrics using the isolated `test_hypothetical.py` script.

#### Parameters
| Flag | Required | Default | Description |
|---|---|---|---|
| `--reaction` | ❌ | `OER` | Target catalytic mechanism (Options: `OER`, `ORR`, `CO2RR-CO`, `HER`, `NRR`). |
| `--data_file` | ✅ | — | Generic JSON payload of evaluated binding energies. |
| `--output_dir` | ❌ | `.` | Where to save the `.png` plots and results JSON. |

### 3. Review Outputs
The script produces:
- `[rxn]_results.json`: Dict mapping surface ID to its $\Delta G_n$ steps, overpotential, descriptor, and PDS.
- `[rxn]_free_energy_steps.png`: A step-diagram plotting the relative Free Energy landscape.
- `[rxn]_volcano.png`: An empirically fit activity volcano mapping $-\eta$ versus the critical descriptor.

<<<<<<< HEAD
### 4. Comparative Benchmarking (Optional)
To benchmark a pre-screening dataset (e.g., MLIP) against a high-fidelity verification dataset (e.g., DFT), use the generalized comparative analysis script. This will output Binding Energy Parity (`parity_binding.png`) and Activity Overpotential Parity (`parity_activity.png`) with Spearman Rank Correlation metrics.

```bash
# Env: base-agent
python .agents/skills/mat-htvs-catalysis-activity-analysis/scripts/compare_methods.py \
    --base_data ./research/current_research_dir/dft_oer_full_data.csv \
    --target_data ./research/current_research_dir/mlip_oer_full_data.csv \
    --base_label "DFT" \
    --target_label "MLIP" \
    --output_dir ./research/current_research_dir
```

=======
>>>>>>> origin/htvs
## Developer Notes
- `src.utils.htvs.catalysis_utils` contains the ReactionMechanism subclasses defining unique thermodynamic logic, equilibrium voltages, and plotting aesthetics for each catalysis route.

## Constraints
- **Environment**: Requires `htvs-agent` conda environment for database decoupling and surface manipulation via `src.utils.htvs`.
- **Dependencies**: Relies directly on `catkit` and `ase` for algorithmic geometric analysis, both bundled exclusively in `htvs-agent`.
- **Data ID Tracking**: Every script execution MUST output its processed ID mappings in the final results JSON for agentic tracking.
- **Decoupling Protocol**: This script purely operates on static JSON pipelines and holds absolutely no active database connections.

**Author**: Hoje Chun
**Contact**: [GitHub @hojechun](https://github.com/hojechun)
