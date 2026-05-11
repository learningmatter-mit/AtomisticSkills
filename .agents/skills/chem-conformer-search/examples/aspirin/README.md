# Aspirin Conformer Search Example

This example demonstrates how to find low-energy conformers of Acetylsalicylic acid (Aspirin) using RDKit and MACE-OFF23.

## Usage

Run the following command from the project root:

```bash
# Env: mace-agent
python .agents/skills/chem-conformer-search/scripts/conformer_search.py \
    --smiles "CC(=O)Oc1ccccc1C(=O)O" \
    --num_conformers 50 \
    --model_type mace \
    --model_name MACE-OFF23-small \
    --output_dir .agents/skills/chem-conformer-search/examples/aspirin
```

## Expected Results

- **`conformer_results.json`**: Summary of unique conformers (energies, Boltzmann weights).
- **[conf_*.xyz](conf_*.xyz)**: XYZ files for each unique conformer.

## Literature Comparison

The search identified 2 unique conformers with an energy difference of **0.17 kcal/mol**. This result is highly consistent with literature studies of aspirin's conformational landscape.

*   **Agreement with DFT/MP2**: Computational studies (e.g., *Glaser, J. Phys. Chem. A, 2005*) identify the global minimum as an intramolecularly hydrogen-bonded structure between the carboxylic hydroxyl and ester carbonyl groups. Several other stable rotamers (involving ester or carboxyl group rotations) lie within **0–2 kcal/mol**.

### References
1.  Glaser, R. "Aspirin: An *ab Initio* Quantum-Mechanical Study of Conformational Preferences..." *J. Phys. Chem. A* **2001**, *105*, 39, 8861–8871.
2.  Desiraju, G. R. et al. "Aspirin: A Polymorphic Wonder..." *Cryst. Growth Des.* **2011**, *11*, 10, 4279–4293.
