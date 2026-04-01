# Copyright (c) 2025 CuspAI
# All rights reserved.

"""
The code in this file is derived from
https://github.com/hspark1212/DAC-SIM
MIT-licensed
"""

from io import BytesIO

import numpy as np
from ase import Atoms, units
from pydantic import BaseModel

from .utils import (
    bootstrap_ratio_std,
    calculate_atomic_density,
)


class WidomInsertionResults(BaseModel):
    henry_coefficient: float  # [mol/kg/Pa]
    henry_coefficient_std: float  # [mol/kg/Pa]
    averaged_interaction_energy: float  # [eV]
    averaged_interaction_energy_std: float  # [eV]
    heat_of_adsorption: float  # [kJ/mol]
    heat_of_adsorption_std: float  # [kJ/mol]
    atomic_density: float  # [kg/m³]
    total_energies: list[float]  # [eV]
    energy_gas: float  # [eV]
    energy_structure: float  # [eV]
    interaction_energies: list[float]  # [eV]
    is_accessible: list[bool]  # Guests non-overlapping with framework atoms
    is_valid: list[bool]  # Guests with valid interaction energy (> -1.25 eV)
    gas_positions: list[list[list[float]]]  # Positions of the inserted gas molecules
    optimized_structure_cif: str  # CIF string of the optimized structure


def analyze_widom_insertions(
    energies: np.ndarray,
    is_accessible: np.ndarray,
    gas_positions: np.ndarray,
    energy_structure: float,
    energy_gas: float,
    temperature: float,
    structure: Atoms,
    energies_are_interaction: bool,
    min_interaction_energy: float,
    random_seed: int,
) -> WidomInsertionResults:
    """Analyze Widom insertion results to calculate thermodynamic properties.

    Args:
        energies: Array of total energies for each insertion attempt.
        is_accessible: Array indicating which insertions were successful.
        gas_positions: Array of positions of the inserted gas molecules.
        energy_structure: Total energy of the bare structure.
        energy_gas: Total energy of the isolated gas molecule.
        temperature: Temperature in Kelvin.
        structure: The framework structure.
        energies_are_interaction: Whether the energies are already interaction energies.
        min_interaction_energy: Minimum valid interaction energy for the gas molecule. [eV]
        random_seed: Seed for bootstrap calculations.

    Returns:
        Results containing Henry coefficient, heat of adsorption, and other properties.
    """
    if energies_are_interaction:
        interaction_energies = energies  # [eV]
    else:
        interaction_energies = energies - energy_structure - energy_gas  # [eV]

    num_samples = len(interaction_energies)

    # If the model gives too low interaction energy, we treat it as invalid.
    is_valid = interaction_energies > min_interaction_energy  # [eV]
    # Set invalid energies to a large value
    interaction_energies_valid = np.where(is_valid, interaction_energies, 1e10)  # [eV]

    # Calculate ensemble averages properties
    # units._e [J/eV], units._k [J/K], units._k / units._e # [eV/K]
    boltzmann_factor = np.exp(-interaction_energies_valid / (temperature * units._k / units._e))

    # KH = <exp(-E/RT)> / (R * T)
    atomic_density = calculate_atomic_density(structure)  # [kg / m^3]
    kh = (
        boltzmann_factor.mean()
        / (units._k * units._Nav)  # R = [J / mol K] = [Pa m^3 / mol K]
        / temperature  # T = [K] -> [mol/ m^3 Pa]
        / atomic_density  #  = [kg / m^3] -> [mol / kg Pa]
    )  # [mol/kg Pa]

    # Estimate std dev of estimator. Is a mean, so we take the std dev of terms/sqrt(N)
    kh_std = (
        boltzmann_factor.std()
        / (units._k * units._Nav)
        / temperature
        / atomic_density
        / np.sqrt(num_samples)
    )  # [mol/kg Pa]

    # U = < E * exp(-E/RT) > / <exp(-E/RT)> # [eV]
    # If we only hit large interaction energies, we don't get a good estimator due to numerics.
    # Correct for this by shifting the interaction energies.
    interaction_energies_shift = interaction_energies_valid - interaction_energies_valid.min()
    boltzmann_factor_shift = np.exp(
        -interaction_energies_shift / (temperature * units._k / units._e)
    )
    u = (interaction_energies_valid * boltzmann_factor_shift).sum() / boltzmann_factor_shift.sum()

    u_std = bootstrap_ratio_std(
        interaction_energies_valid * boltzmann_factor_shift,
        boltzmann_factor_shift,
        n_bootstrap=100,
        random_seed=random_seed,
    )  # [eV]

    # Qst = U - RT # [kJ/mol]
    qst = (u * units._e - units._k * temperature) * units._Nav * 1e-3

    # Std dev simple linear transformation of u_std
    qst_std = u_std * units._e * units._Nav * 1e-3

    cif_writer = BytesIO()
    structure.write(cif_writer, format="cif")
    cif_writer.seek(0)

    results = WidomInsertionResults(
        henry_coefficient=float(kh),
        henry_coefficient_std=float(kh_std),
        averaged_interaction_energy=float(u),
        averaged_interaction_energy_std=float(u_std),
        heat_of_adsorption=float(qst),
        heat_of_adsorption_std=float(qst_std),
        atomic_density=float(atomic_density),
        total_energies=energies.tolist(),
        energy_gas=float(energy_gas),
        energy_structure=float(energy_structure),
        interaction_energies=interaction_energies.tolist(),
        is_accessible=is_accessible.tolist(),
        is_valid=is_valid.tolist(),
        gas_positions=gas_positions.tolist(),
        optimized_structure_cif=cif_writer.read().decode("ascii"),
    )
    return results
