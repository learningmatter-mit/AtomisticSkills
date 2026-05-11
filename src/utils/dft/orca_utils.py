"""
Shared utilities for ORCA calculations via SCINE wrapper.

Provides helper functions to build a configured SCINE/ORCA calculator
from common DFT parameters and to validate the ORCA binary.

Usage:
    from src.utils.dft.orca_utils import setup_orca_calculator, check_orca_binary

Requirements:
    - Conda environment: orca-agent
    - Required packages: scine_utilities, ase
    - Environment variable: ORCA_BINARY_PATH
"""

import json
import os
import logging
from pathlib import Path
from typing import Any, Optional

import ase.io
import scine_utilities as su

logger = logging.getLogger(__name__)

HARTREE_TO_EV = su.EV_PER_HARTREE
BOHR_PER_ANGSTROM = su.BOHR_PER_ANGSTROM


def check_orca_binary() -> str:
    """
    Validate that ORCA_BINARY_PATH is set and points to an executable.

    Returns:
        The resolved path to the ORCA binary.

    Raises:
        EnvironmentError: If ORCA_BINARY_PATH is not set or not executable.
    """
    orca_path = os.environ.get("ORCA_BINARY_PATH")
    if not orca_path:
        raise EnvironmentError(
            "ORCA_BINARY_PATH environment variable is not set. "
            "Set it to the path of your ORCA binary, e.g. "
            "export ORCA_BINARY_PATH=/path/to/orca"
        )
    if not os.path.isfile(orca_path):
        raise EnvironmentError(
            f"ORCA_BINARY_PATH points to a non-existent file: {orca_path}"
        )
    if not os.access(orca_path, os.X_OK):
        raise EnvironmentError(
            f"ORCA binary is not executable: {orca_path}"
        )
    logger.info(f"ORCA binary validated: {orca_path}")
    return orca_path


def load_structure(structure_path: str) -> tuple[su.AtomCollection, "ase.Atoms"]:
    """
    Load a structure file and convert to SCINE AtomCollection.

    Args:
        structure_path: Path to structure file (.xyz, .cif, etc.)

    Returns:
        Tuple of (SCINE AtomCollection, ASE Atoms object)
    """
    atoms = ase.io.read(structure_path)
    elements = [su.ElementInfo.element_from_symbol(s) for s in atoms.symbols]
    atom_collection = su.AtomCollection(elements, atoms.positions * BOHR_PER_ANGSTROM)
    return atom_collection, atoms


def parse_json_settings(json_string: Optional[str]) -> dict[str, Any]:
    """
    Parse a JSON string into a dictionary for SCINE settings.

    Using JSON preserves exact types (int vs float vs string), which is
    important because SCINE is strict about the types it receives.

    Args:
        json_string: JSON string like '{"max_scf_iterations": 128}', or None

    Returns:
        Parsed dictionary, or empty dict if input is None/empty

    Raises:
        ValueError: If the string is not valid JSON or not a flat object
    """
    if not json_string:
        return {}
    try:
        parsed = json.loads(json_string)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON for settings: {e}")
    if not isinstance(parsed, dict):
        raise ValueError(
            f"Settings JSON must be a flat object/dict, got {type(parsed).__name__}"
        )
    return parsed


def setup_orca_calculator(
    structure_path: str,
    charge: int = 0,
    spin_multiplicity: int = 1,
    functional: str = "PBE",
    basis_set: str = "def2-SVP",
    dispersion: Optional[str] = None,
    solvation: Optional[str] = None,
    solvent: Optional[str] = None,
    special_option: str = "NOSOSCF",
    nprocs: int = 1,
    extra_calculator_settings: Optional[dict[str, Any]] = None,
    output_dir: str = ".",
) -> tuple["su.core.Calculator", su.AtomCollection, "ase.Atoms"]:
    """
    Build and configure a SCINE calculator powered by ORCA.

    Args:
        structure_path: Path to input structure file
        charge: Molecular charge
        spin_multiplicity: Spin multiplicity (2S+1)
        functional: DFT functional (e.g. PBE, B3LYP, wB97X-V)
        basis_set: Basis set (e.g. def2-SVP, def2-TZVP)
        dispersion: Dispersion correction (e.g. D3BJ, D4), or None
        solvation: Solvation model (CPCM or SMD), or None
        solvent: Solvent name (e.g. water, ethanol); required if solvation is set
        special_option: ORCA special option string passed to the SCINE calculator
            (default: "NOSOSCF" — disables second-order SCF, which is more robust
            for single-point and optimization workflows)
        nprocs: Number of CPU cores for ORCA
        extra_calculator_settings: Additional SCINE calculator settings as a dict.
            Applied after all other settings, so can override defaults. Types
            must match what SCINE expects (use JSON parsing to preserve types).

    Returns:
        Tuple of (configured calculator, AtomCollection, ASE Atoms)

    Raises:
        ValueError: If solvation is set but solvent is not provided
        EnvironmentError: If ORCA binary is not available
    """
    check_orca_binary()

    if solvation and not solvent:
        raise ValueError(
            f"Solvation model '{solvation}' requires --solvent to be set "
            "(e.g. water, ethanol, dmso)"
        )

    atom_collection, atoms = load_structure(structure_path)

    calculator = su.core.get_calculator("dft", "orca")

    calculator.settings["molecular_charge"] = charge
    calculator.settings["spin_multiplicity"] = spin_multiplicity

    method = functional
    if dispersion:
        method = f"{functional}-{dispersion}"
    calculator.settings["method"] = method
    calculator.settings["basis_set"] = basis_set

    if solvation:
        calculator.settings["solvation"] = solvation
        calculator.settings["solvent"] = solvent

    if special_option:
        calculator.settings["special_option"] = special_option

    if nprocs > 1:
        calculator.settings["external_program_nprocs"] = nprocs

    if extra_calculator_settings:
        for key, value in extra_calculator_settings.items():
            calculator.settings[key] = value
            logger.info(f"  Extra setting: {key} = {value!r}")
            if key == "method":
                method = value
            elif key == "basis_set":
                basis_set = value
            elif key == "molecular_charge":
                charge = value
            elif key == "spin_multiplicity":
                spin_multiplicity = value
            elif key == "external_program_nprocs":
                nprocs = value
            elif key == "solvation":
                solvation = value
            elif key == "solvent":
                solvent = value

    logger.info(
        f"ORCA calculator configured: {method}/{basis_set}, "
        f"charge={charge}, mult={spin_multiplicity}, nprocs={nprocs}"
    )
    if solvation:
        logger.info(f"  Solvation: {solvation}, solvent: {solvent}")

    # make sure that raw ORCA files are in the output directory if no other place was specified
    if extra_calculator_settings is None or 'base_working_directory' not in extra_calculator_settings:
        calculator.settings['base_working_directory'] = str(Path(output_dir).resolve())
    # set higher default memory than specified in wrapper if not specified otherwise
    if extra_calculator_settings is None or 'external_program_memory' not in extra_calculator_settings:
        calculator.settings['external_program_memory'] = 4096 * nprocs
    logger.debug(str(calculator.settings.as_dict()))

    calculator.structure = atom_collection
    return calculator, atom_collection, atoms


def scine_positions_to_ase(positions_bohr) -> "list":
    """Convert SCINE positions (Bohr) back to ASE-compatible Angstrom."""
    return (positions_bohr / BOHR_PER_ANGSTROM).tolist()
