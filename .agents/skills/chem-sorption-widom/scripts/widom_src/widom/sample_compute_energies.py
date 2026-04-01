# Copyright (c) 2025 CuspAI
# All rights reserved.

import numpy as np
from ase import Atoms
from ase.calculators.calculator import Calculator
from tqdm.auto import tqdm

from .structure_preparation import (
    create_combined_structure,
    prepare_structures_for_insertion,
)


def sample_compute_energies(
    calculator: Calculator,
    structure: Atoms,
    gas: Atoms,
    num_insertions: int,
    cutoff_distance: float,
    cutoff_to_com: bool,
    min_interplanar_distance: float,
    random_seed: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Run the Widom insertion algorithm to calculate interaction energies.

    This function performs Widom insertion of gas molecules into a structure to calculate
    interaction energies, which can be used for computing the Henry coefficient and heat
    of adsorption.

    Args:
        calculator: Calculator object from ASE to calculate energies.
        structure: Atoms object representing the framework structure.
        gas: Atoms object representing the gas molecule to insert.
        num_insertions: Number of random insertions to perform.
        cutoff_distance: Minimum allowed distance between framework atoms and gas molecule, in angstroms.
        cutoff_to_com: Whether to use the center of mass for distance calculations.
        min_interplanar_distance: Minimum interplanar distance before constructing a supercell, in angstroms.
        random_seed: Seed for random number generator to ensure reproducibility.

    Returns:
        A tuple containing:
            - Array of total energies (in eV) for each insertion attempt.
            - Array of booleans indicating whether the insertion was successful (non-overlapping with framework atoms).
            - Array of positions of the inserted gas molecules.
    """
    # Make copies to avoid modifying input
    structure = structure.copy()
    gas = gas.copy()

    # Use common preparation function
    structure_supercell, gas_positions, is_accessible = prepare_structures_for_insertion(
        structure=structure,
        gas=gas,
        num_insertions=num_insertions,
        cutoff_distance=cutoff_distance,
        cutoff_to_com=cutoff_to_com,
        min_interplanar_distance=min_interplanar_distance,
        random_seed=random_seed,
    )

    print(f"Number of accessible positions: {np.sum(is_accessible)} out of {num_insertions}")

    # Prepare arrays for results
    energies = np.zeros(num_insertions)  # [eV], total energy

    # Set inaccessible positions to high energy
    energies[~is_accessible] = 1e10

    # Evaluate energies for accessible positions only
    accessible_indices = np.where(is_accessible)[0]

    for i in tqdm(accessible_indices):
        # Create combined structure using common function
        combined = create_combined_structure(
            structure_supercell,
            gas,
            gas_positions[i]
        )

        # Calculate energy
        combined.calc = calculator
        energies[i] = combined.get_potential_energy()  # [eV]

    return energies, is_accessible, gas_positions  # [eV]