# Oxadiazole Isomerization (C₂H₂N₂O)

**Reaction:** 1,2,4-oxadiazole ring rearrangement  
**Source:** Transition1x validation dataset (reaction index 0)

This example is extracted from the official React-OT validation dataset ([Zenodo](https://zenodo.org/records/13131875)). The reference TS is computed at the ωB97x/6-31G(d) level of theory.

## Files

- **`reactant.xyz`**: Reactant geometry (7 atoms: O, 2C, 2N, 2H)
- **`product.xyz`**: Product geometry
- **`reference_ts.xyz`**: DFT reference transition state (ωB97x/6-31G(d))
- **`output/ts_generated.xyz`**: React-OT generated transition state

## Usage

```bash
conda activate react-ot-agent
python .agents/skills/chem-react-ot/scripts/generate_ts.py \
    --reactants .agents/skills/chem-react-ot/examples/oxadiazole_isomerization/reactant.xyz \
    --products .agents/skills/chem-react-ot/examples/oxadiazole_isomerization/product.xyz \
    --output_dir .agents/skills/chem-react-ot/examples/oxadiazole_isomerization/output
```

## Results

Comparison of React-OT generated TS vs DFT reference (ωB97x/6-31G(d)):

| Atom | Deviation (Å) |
|------|---------------|
| O    | 0.051         |
| C    | 0.062         |
| N    | 0.055         |
| N    | 0.027         |
| C    | 0.020         |
| H    | 0.055         |
| H    | 0.043         |

| Metric | Value |
|--------|-------|
| **RMSD** | **0.047 Å** |
| Max deviation | 0.062 Å |

The generated TS is in excellent agreement with the DFT reference, demonstrating sub-0.1 Å accuracy on a reaction from the Transition1x dataset.

### References
1. Schreiner, M. et al. "Transition1x — A dataset for building generalizable reactive machine-learning interatomic potentials." *Sci. Data* **2022**, *9*, 779.
2. Duan, C. et al. "React-OT: Optimal Transport for Generating Transition State in Chemical Reactions." *JACS* **2025**.
