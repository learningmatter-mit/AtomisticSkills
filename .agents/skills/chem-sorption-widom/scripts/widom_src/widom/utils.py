# Copyright (c) 2025 CuspAI
# All rights reserved.

from typing import Optional

import numpy as np
from ase import Atoms, units
from ase.calculators.calculator import Calculator
from ase.filters import FrechetCellFilter
from ase.io import Trajectory
from ase.optimize import FIRE
from pymatgen.optimization.neighbors import find_points_in_spheres


def sample_gas_positions(
    structure: Atoms,
    gas: Atoms,
    num_insertions: int,
    rng: np.random.Generator,
) -> np.ndarray:
    """Sample random positions and orientations for gas molecules.

    Args:
        structure: Atoms object representing the framework structure.
        gas: Atoms object representing the gas molecule to insert.
        num_insertions: Number of random insertions to perform.
        rng: NumPy random number generator.

    Returns:
        Array of gas positions with shape (num_insertions, num_gas_atoms, 3).
    """
    # Uniformly sample positions in the unit cell
    random_positions = rng.random((num_insertions, 3))
    random_angles = rng.random(num_insertions) * 360  # Random angles for rotation
    random_axes = rng.random((num_insertions, 3))  # Random axes for rotation
    random_axes /= np.linalg.norm(random_axes, axis=1, keepdims=True)

    # Convert fractional coordinates to Cartesian using ASE method
    cartesian_positions = structure.cell.cartesian_positions(random_positions)

    # Generate all gas molecules
    gas_positions = np.zeros((num_insertions, len(gas), 3))
    for i in range(num_insertions):
        added_gas = gas.copy()
        added_gas.cell = structure.cell  # Use the same cell as the framework
        added_gas.pbc = structure.pbc  # Use the same periodic boundary conditions
        added_gas.rotate(v=random_axes[i], a=random_angles[i])
        added_gas.translate(cartesian_positions[i])
        added_gas.wrap()
        gas_positions[i] = added_gas.get_positions()

    return gas_positions


def check_accessibility(
    gas_positions: np.ndarray,
    framework_coords: np.ndarray,
    lattice_matrix: np.ndarray,
    cutoff_distance: float,
    cutoff_to_com: bool,
) -> np.ndarray:
    """Check which gas insertions are accessible (non-overlapping with framework atoms).

    Args:
        gas_positions: Array of gas positions with shape (num_insertions, num_gas_atoms, 3).
        framework_coords: Array of framework atom positions.
        lattice_matrix: 3x3 lattice matrix for periodic boundary conditions.
        cutoff_distance: Minimum allowed distance between framework and gas atoms.
        cutoff_to_com: Whether to use the center of mass for distance calculations.

    Returns:
        Boolean array indicating which insertions are accessible.
    """
    num_insertions, num_gas_atoms = gas_positions.shape[:2]

    # Handle empty inputs
    if num_insertions == 0:
        return np.array([], dtype=bool)

    # Convert ASE cell to format expected by find_points_in_spheres
    pbc_array = np.array([1, 1, 1], dtype=np.int64)  # Assume periodic in all directions

    if cutoff_to_com:
        # If cutoff is to center of mass, calculate the center of mass for each gas insertion
        gas_coords = np.mean(gas_positions, axis=1)
    else:
        # Flatten gas positions to check all gas atoms at once
        # Shape: (num_insertions * num_gas_atoms, 3)
        gas_coords = gas_positions.reshape(-1, 3)

    # Use find_points_in_spheres to check overlaps in batch
    center_indices, all_coords_indices, offset_vectors, distances = find_points_in_spheres(
        all_coords=gas_coords,
        center_coords=framework_coords.astype(np.float64),
        r=float(cutoff_distance),
        pbc=pbc_array,
        lattice=lattice_matrix.astype(np.float64),
        tol=1e-8,
    )

    # Determine which insertions have overlaps
    if cutoff_to_com:
        overlapping_insertions = set(all_coords_indices)
    else:
        # all_coords_indices corresponds to gas atoms, divide by num_gas_atoms to get insertion index
        overlapping_insertions = set(all_coords_indices // num_gas_atoms)

    is_accessible = np.array([i not in overlapping_insertions for i in range(num_insertions)])

    return is_accessible


def optimize_atoms(
    calculator: Calculator,
    atoms: Atoms,
    num_total_optimization: int = 30,
    num_internal_steps: int = 50,
    num_cell_steps: int = 50,
    fmax: float = 0.05,
    cell_relax: bool = True,
    trajectory_file: Optional[str] = None,
) -> Optional[Atoms]:
    """Perform geometry optimization using the FIRE algorithm.

    The code in this function is derived from
    https://github.com/hspark1212/DAC-SIM
    MIT-licensed

    Args:
        calculator: ASE calculator for the optimization.
        atoms: Atoms object to optimize.
        num_total_optimization: The number of optimization steps including internal and cell relaxation.
        num_internal_steps: The number of internal steps (freezing the cell).
        num_cell_steps: The number of optimization steps (relaxing the cell).
        fmax: The threshold for the maximum force to stop the optimization.
        cell_relax: If True, relax the cell.
        trajectory_file: Path to the trajectory file. If provided, the trajectory will be saved.

    Returns:
        The optimized atoms object, or None if optimization failed.
    """
    if trajectory_file is not None:
        trajectory = Trajectory(trajectory_file, "w", atoms)

    opt_atoms = atoms.copy()
    convergence = False

    for _ in range(int(num_total_optimization)):
        opt_atoms = opt_atoms.copy()
        opt_atoms.calc = calculator

        # cell relaxation
        if cell_relax:
            filter = FrechetCellFilter(opt_atoms)  # pylint: disable=redefined-builtin
            optimizer = FIRE(filter)  # type: ignore
            convergence = optimizer.run(fmax=fmax, steps=num_cell_steps)
            opt_atoms.wrap()
            if trajectory_file is not None:
                optimizer.attach(trajectory.write, interval=1)  # type: ignore
            convergence = optimizer.run(fmax=fmax, steps=num_internal_steps)
            if convergence:
                break

        # internal relaxation
        optimizer = FIRE(opt_atoms)
        convergence = optimizer.run(fmax=fmax, steps=num_internal_steps)
        if trajectory_file is not None:
            optimizer.attach(trajectory.write, interval=1)  # type: ignore
        if convergence and not cell_relax:
            break

        # fail if the forces are too large
        forces = filter.get_forces()  # type: ignore
        _fmax = np.sqrt((forces**2).sum(axis=1).max())
        if _fmax > 1000:
            return None

    if not convergence:
        return None
    return opt_atoms


def create_supercell_if_needed(structure: Atoms, min_interplanar_distance: float = 6.0) -> Atoms:
    """Create a supercell if the interplanar distance is too small.

    The code in this function is derived from
    https://github.com/hspark1212/DAC-SIM
    MIT-licensed

    Args:
        structure: The structure to potentially expand into a supercell.
        min_interplanar_distance: Minimum interplanar distance before constructing a supercell, in angstroms.

    Returns:
        The original structure or supercell if expansion was needed.
    """
    structure = structure.copy()

    # Calculate interplanar distances
    cell_volume = structure.get_volume()
    cell_vectors = np.array(structure.cell)
    dist_a = cell_volume / np.linalg.norm(np.cross(cell_vectors[1], cell_vectors[2]))
    dist_b = cell_volume / np.linalg.norm(np.cross(cell_vectors[2], cell_vectors[0]))
    dist_c = cell_volume / np.linalg.norm(np.cross(cell_vectors[0], cell_vectors[1]))
    plane_distances = np.array([dist_a, dist_b, dist_c])

    # Determine supercell dimensions
    supercell = np.ceil(min_interplanar_distance / plane_distances).astype(int)

    if np.any(supercell > 1):
        print(
            f"Making supercell: {supercell} to prevent interplanar distance < {min_interplanar_distance}"
        )
        structure = structure.repeat(supercell)

    return structure


def bootstrap_ratio_std(
    numerator: np.ndarray,
    denominator: np.ndarray,
    n_bootstrap: int,
    random_seed: int,
) -> float:
    """Calculate standard deviation of ratio estimator using bootstrap.

    Args:
        numerator: Array of numerator values.
        denominator: Array of denominator values.
        n_bootstrap: Number of bootstrap samples.
        random_seed: Seed for the random number generator.

    Returns:
        Standard deviation of the ratio estimator.
    """
    n = len(numerator)
    ratios = np.zeros(n_bootstrap)

    rng = np.random.default_rng(random_seed)

    for i in range(n_bootstrap):
        # Generate bootstrap sample indices (with replacement)
        indices = rng.choice(n, size=n, replace=True)

        # Calculate ratio for this bootstrap sample
        num_sample = numerator[indices]
        denom_sample = denominator[indices]
        ratios[i] = num_sample.mean() / denom_sample.mean()

    # Return standard deviation of bootstrap ratios
    return float(np.std(ratios))


def calculate_atomic_density(atoms: Atoms) -> float:
    """Calculate atomic density of the atoms.

    The code in this function is derived from
    https://github.com/hspark1212/DAC-SIM
    MIT-licensed

    Args:
        atoms: The Atoms object to operate on.

    Returns:
        Atomic density of the atoms in kg/m³.
    """
    volume = atoms.get_volume() * 1e-30  # Convert Å³ to m³
    total_mass = np.sum(atoms.get_masses()) * units._amu  # Convert amu to kg # type: ignore
    return total_mass / volume
