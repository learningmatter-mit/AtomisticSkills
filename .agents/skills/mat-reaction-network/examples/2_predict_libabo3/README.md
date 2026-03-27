# BaLiBO3 Synthesis Pathway Prediction

This example compares the theoretical synthesis pathways for the phosphor material $\text{BaLiBO}_3$ using traditional solid-state precursors versus computationally predicted optimal precursors.

## Running the Example

Activate the appropriate Conda environment (`base-agent`) and run the included bash script:

```bash
conda activate base-agent
./run.sh
```

This invokes the `find_pathways.py` tool on both cursor sets and generates two JSON files: `traditional_output.json` and `predicted_output.json`.

## Interpreting the JSON Outputs

The JSON outputs provide a clean, structured schema of the graph network solver's results.

### Comparison of Precursors for BaLiBO3

1. **Traditional Precursors (`B2O3` + `BaO` + `Li2O`)**
   - See: `traditional_output.json`
   - **Result**: The lowest-cost pathway (`total_cost` ≈ 0.194) requires **3 distinct steps**. 
   - **Why this is problematic**: The reaction network must navigate through multiple intermediate phases (e.g., `Li3B11O18`, `Ba2B2O5`) before forming the final target phase. This reduces synthesis efficiency due to competing thermodynamic driving forces of intermediates.

2. **Predicted Precursors (`LiBO2` + `BaO`)**
   - See: `predicted_output.json`
   - **Result**: The very first, lowest-cost pathway (`total_cost` ≈ 0.190) is computationally shown to be a **single step** (`BaO + LiBO2 -> BaLiBO3` with dG = -0.266 eV/atom).
   - **Why this is optimal**: The predicted precursors can react linearly in a single consolidated step with an extremely favorable driving force. This perfectly matches the objective of directed computational materials design—finding precursors that bypass intermediate decomposition cascades entirely.

By strictly comparing the step counts and total costs within the JSON schema, the mathematically validated advantage of non-intuitive computational precursor suggestions becomes explicitly clear.
