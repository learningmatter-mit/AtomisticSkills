# Copyright (c) 2025 CuspAI
# All rights reserved.

"""
Common structure preparation utilities for Widom insertion.
"""

import numpy as np
from ase import Atoms

from .utils import check_accessibility, create_supercell_if_needed, sample_gas_positions


def create_combined_structure(
    structure: Atoms,
    gas: Atoms,
    gas_position: np.ndarray,
) -> Atoms:
    """
    Create a combined structure with gas molecule at specified position.

    Args:
        structure: Framework structure
        gas: Gas molecule
        gas_position: Position for gas molecule (num_gas_atoms, 3)

    Returns:
        Combined ASE Atoms object
    """
    combined = structure.copy()
    gas_copy = gas.copy()
    gas_copy.positions = gas_position
    combined.extend(gas_copy)
    combined.wrap()  # Ensure atoms are within unit cell
    return combined


def prepare_structures_for_insertion(
    structure: Atoms,
    gas: Atoms,
    num_insertions: int,
    cutoff_distance: float,
    cutoff_to_com: bool,
    min_interplanar_distance: float,
    random_seed: int,
) -> tuple[Atoms, np.ndarray, np.ndarray]:
    """
    Prepare structures and sample positions for Widom insertion.

    This function combines the common preparation steps:
    1. Create supercell if needed
    2. Sample gas positions
    3. Check accessibility

    Args:
        structure: Framework structure
        gas: Gas molecule
        num_insertions: Number of insertions to attempt
        cutoff_distance: Minimum allowed distance
        cutoff_to_com: Whether to use center of mass for cutoff
        min_interplanar_distance: Minimum interplanar distance
        random_seed: Random seed for reproducibility

    Returns:
        Tuple of (supercell structure, gas positions, accessibility array)
    """
    # Create supercell if needed
    structure_supercell = create_supercell_if_needed(structure, min_interplanar_distance)

    # Set up random number generator
    rng = np.random.default_rng(random_seed)

    # Sample gas positions
    gas_positions = sample_gas_positions(structure_supercell, gas, num_insertions, rng)

    # Check accessibility
    framework_coords = structure_supercell.get_positions()
    lattice_matrix = np.array(structure_supercell.cell)
    is_accessible = check_accessibility(
        gas_positions,
        framework_coords,
        lattice_matrix,
        cutoff_distance,
        cutoff_to_com
    )

    return structure_supercell, gas_positions, is_accessible