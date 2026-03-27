# LiZnPO4 Synthesis Pathway Prediction

This example compares the synthesis pathways for $\text{LiZnPO}_4$ using traditional solid-state precursors versus computationally predicted optimal precursors, as discussed in the *Nature Synthesis* paper ("Predicting solid-state synthesis pathways from precursor principles").

## Running the Example

Activate the appropriate Conda environment (`base-agent`) and run the included bash script:

```bash
conda activate base-agent
./run.sh
```

This will run the pathway solver for both sets of precursors and generate two JSON files: `traditional_output.json` and `predicted_output.json`.

## Interpreting the JSON Outputs

The generated JSON files contain the resolved pathway networks for the specified target.

### Structure of the Output
- **`target`**: The desired final material (e.g., `"LiZnPO4"`).
- **`precursors`**: The starting materials provided to the solver.
- **`temperature`**: The thermodynamic temperature (in K) used for the Gibbs free energy calculations.
- **`net_reaction`**: The overall balanced chemical equation from precursors to the target (+ byproducts).
- **`pathways`**: A sorted list of the most optimal balanced pathway combinations discovered by the solver.
  - If the list is **empty** (`[]`), it means either no balanced pathway could be found, or the reaction proceeds optimally in a **single direct step** without any competitive intermediate phases (as is often the case for carefully chosen, computationally predicted precursors).
  - If the list is populated, each entry represents a distinct pathway:
    - **`total_cost`**: A heuristic value scoring the thermodynamic difficulty of the path. Lower costs mean a more favorable, lower-barrier synthesis route.
    - **`steps`**: The sequence of elementary reactions that make up the full macroscopic pathway.
      - **`reaction_string`**: The balanced intermediate step (e.g., forming a binary oxide or a mixed intermediate).
      - **`dG_eV_per_atom`**: The change in Gibbs free energy for this specific step. Negative values are exergonic (favorable downhill steps), while positive values indicate endergonic bottlenecks or barriers.

### Analyzing Pairwise Pathways (Figure 2 Replication)
The `run.sh` script tests three specific pairwise precursor combinations highlighted in Figure 2 of the *Nature Synthesis* paper. The results are saved to separate JSON files:

1. **Pair A (`Zn2P2O7` + `Li2O`)**: See `pair_a_output.json`.
   - The algorithmic 1-step pathway (`Li2O + Zn2P2O7 -> 2 LiZnPO4`) has a `total_cost` of ~0.203.
   - **Context**: The key problem with this pair is *phase competition*. If you look at alternative pathways in `pair_a_output.json`, there are competing steps with much larger (more negative) driving forces — such as forming `Li3PO4` or other intermediates with a $\Delta G$ up to -0.42 eV/atom or -0.22 eV/atom. Because the largest driving force in the system does not lead directly to the target `LiZnPO4` (-0.19 eV/atom), the reaction tends to get trapped in these intermediate thermodynamic sinks, leading to impure products or requiring excessive heating times.

2. **Pair B (`Zn3(PO4)2` + `Li3PO4`)**: See `pair_b_output.json`.
   - The 1-step pathway (`Zn3(PO4)2 + Li3PO4 -> 3 LiZnPO4`) has a higher `total_cost` of ~0.236.
   - **Context**: This indicates a slightly less thermodynamically driving, potentially higher-barrier route compared to other options.

3. **Pair C (`LiPO3` + `ZnO`)**: See `pair_c_output.json`.
   - The 1-step pathway (`ZnO + LiPO3 -> LiZnPO4`) has a `total_cost` of ~0.218 and is correctly ranked as the optimal reaction.
   - **Context**: Selecting `LiPO3` provides a stable, easy-to-handle solid precursor. Its optimal 1-step route is cleanly recovered by the script, bypassing complex intermediates. This demonstrates how computational synthesis planning balances theoretical thermodynamics with viable precursor selection.
