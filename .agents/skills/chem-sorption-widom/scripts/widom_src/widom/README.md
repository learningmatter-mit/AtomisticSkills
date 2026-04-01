# Widom

A Python package developed by CuspAI for performing Widom insertion simulations to calculate gas adsorption properties in porous materials like metal-organic frameworks (MOFs).

## Overview

Widom insertion is a Monte Carlo method used to calculate thermodynamic properties of gas adsorption in porous materials. This package implements the Widom insertion technique to compute:

- **Henry coefficient** (mol/kg/Pa) - measure of gas affinity to a material at low pressure
- **Heat of adsorption** (kJ/mol) - enthalpy change associated with the adsorption of a single gas molecule
- **Interaction energies** (eV) - energy of gas-framework interactions

The implementation is derived from [DAC-SIM](https://github.com/hspark1212/DAC-SIM) [1] and is designed to work with any ASE-compatible calculator for energy evaluations.

## Features

- **Multiple gas molecules**: Support for various gas species (H2, CO2, CH4, etc.)
- **Flexible energy calculators**: Works with any ASE calculator (DFT, force fields, ML potentials)
- **Structure optimization**: Optional optimization of framework and gas molecules
- **Statistical analysis**: Bootstrap error estimation for computed properties
- **Accessibility checking**: Automatic detection of overlapping positions
- **Reproducible results**: Configurable random seeds for consistent simulations

## Installation

```bash
pip install -e .
```

## Quick Start
To demonstrate the usage of this library, we are using a Si crystal and Lennard-Jones calculator. The resulting numbers should not taken to be chemically meaningful.

```python
from widom import run_widom_insertion
from ase.build import bulk
from ase.calculators.lj import LennardJones

calculator = LennardJones(epsilon=1, sigma=0.6)  # Example calculator
structure = bulk("Si")  # Example structure

# Run Widom insertion simulation
results = run_widom_insertion(
    calculator=calculator,
    structure=structure,
    gas="CO2",
    temperature=298.15,  # K
    model_outputs_interaction_energy=False,
    num_insertions=1000,
    random_seed=42,
)

# Access results
print(f"Henry coefficient: {results.henry_coefficient:.2e} mol/kg/Pa")
print(f"Heat of adsorption: {results.heat_of_adsorption:.2f} kJ/mol")
```

## API Reference

### `run_widom_insertion`

Main function to perform Widom insertion simulation.

**Parameters:**
- `calculator` (Calculator): ASE calculator for energy calculations
- `structure` (Atoms): ASE Atoms object representing the framework structure
- `gas` (str): Gas molecule name (e.g., 'H2', 'CO2', 'CH4')
- `temperature` (float): Temperature in Kelvin
- `model_outputs_interaction_energy` (bool): Whether calculator outputs interaction energies directly
- `num_insertions` (int): Number of random insertion attempts (default: 10000)
- `optimize_structures` (bool): Whether to optimize structures before insertion (default: False)
- `cutoff_distance` (float): Minimum distance between framework and gas atoms in Å (default: 1.0)
- `cutoff_to_com` (bool): Use center of mass for distance calculations (default: False)
- `min_interplanar_distance` (float): Minimum interplanar distance for supercell construction in Å (default: 6.0)
- `random_seed` (int): Seed for reproducibility (default: 0)
- `min_interaction_energy` (float): Minimum valid interaction energy for the gas molecule in eV (default: -1.25)

**Returns:**
- `WidomInsertionResults`: Object containing computed properties and metadata

### `WidomInsertionResults`

Results container with the following attributes:
- `henry_coefficient`: Henry coefficient in mol/kg/Pa
- `henry_coefficient_std`: Standard deviation of Henry coefficient
- `heat_of_adsorption`: Heat of adsorption in kJ/mol
- `heat_of_adsorption_std`: Standard deviation of heat of adsorption
- `averaged_interaction_energy`: Mean interaction energy in eV
- `total_energies`: List of total energies for each insertion
- `interaction_energies`: List of interaction energies
- `is_accessible`: Boolean array indicating accessible positions
- `gas_positions`: Positions of inserted gas molecules

## Theory

The Widom insertion method calculates the chemical potential of a gas in a porous material by inserting test particles at random positions and computing the Boltzmann-weighted average:

```
μ = -kT ln⟨exp(-ΔE/kT)⟩
```

Where ΔE is the interaction energy between the inserted gas and the framework. The Henry coefficient is then calculated as:

```
KH = ⟨exp(-ΔE/kT)⟩ / (ρ_framework × kT)
```

## Requirements

- Python ≥ 3.12
- ASE ≥ 3.25.0
- NumPy ≥ 2.2.6
- Pymatgen ≥ 2025.5.28
- Pydantic ≥ 2.11.5
- tqdm-loggable ≥ 0.2

## Development

Run tests:
```bash
pytest tests/
```

## References

[1] Park, H. S., et al. "DAC-SIM: A Machine Learning Approach to Predicting Gas Adsorption in Metal-Organic Frameworks." *ChemRxiv* (2024). DOI: [10.26434/chemrxiv-2024-7w6g6](https://chemrxiv.org/engage/chemrxiv/article-details/6759b06df9980725cfbc8cef)

## License

Apache 2.0 licensed.
Some parts are derived from [DAC-SIM](https://github.com/hspark1212/DAC-SIM) [1], which is MIT licensed.
