"""
Compute gas-phase thermodynamic quantities (H, S, G) for molecules and
reaction thermochemistry (ΔH, ΔS, ΔG) using MLIPs.

Uses ASE's IdealGasThermo with the ideal-gas / rigid-rotor / harmonic-oscillator
(IGRRHO) approximation. Vibrational frequencies are obtained from finite-difference
Hessian calculations powered by MLIPs.

Usage:
    # Single molecule
    python calculate_thermochemistry.py --molecule H2O --model_type mace --output_dir results

    # Reaction
    python calculate_thermochemistry.py --reaction "2H2 + O2 -> 2H2O" --model_type mace --output_dir results

Requirements:
    - Conda environment: mace-agent, matgl-agent, or fairchem-agent
    - Required packages: ase, numpy
"""

import argparse
import os
import sys
import json
import logging
import re
from typing import Optional, Any

# Add project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../"))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.utils.serialization_utils import recursive_tolist
from src.utils.research_utils import get_current_research_dir
from ase.io import read
from ase.build import molecule as ase_molecule
from ase.vibrations import Vibrations
from ase.thermochemistry import IdealGasThermo
from ase.optimize import LBFGS
from ase.units import kJ, mol
import numpy as np

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("Thermochemistry-Skill")

# Threshold below which a frequency is translational/rotational (cm^-1)
TRANSLATION_ROTATION_THRESHOLD = 50.0

# eV to kJ/mol conversion factor
EV_TO_KJMOL = 96.4853

# Lookup table for spin (S, not 2S+1) and symmetry number of common molecules
# spin = number of unpaired electrons / 2 (e.g., O2 triplet -> spin=1)
MOLECULE_PROPERTIES: dict[str, dict[str, Any]] = {
    "H2":  {"spin": 0, "symmetrynumber": 2},
    "O2":  {"spin": 1, "symmetrynumber": 2},
    "N2":  {"spin": 0, "symmetrynumber": 2},
    "H2O": {"spin": 0, "symmetrynumber": 2},
    "CO2": {"spin": 0, "symmetrynumber": 2},
    "CO":  {"spin": 0, "symmetrynumber": 1},
    "NO":  {"spin": 0.5, "symmetrynumber": 1},
    "NO2": {"spin": 0.5, "symmetrynumber": 2},
    "NH3": {"spin": 0, "symmetrynumber": 3},
    "CH4": {"spin": 0, "symmetrynumber": 12},
    "C2H2": {"spin": 0, "symmetrynumber": 2},
    "C2H4": {"spin": 0, "symmetrynumber": 4},
    "C2H6": {"spin": 0, "symmetrynumber": 6},
    "HCl": {"spin": 0, "symmetrynumber": 1},
    "HF":  {"spin": 0, "symmetrynumber": 1},
    "F2":  {"spin": 0, "symmetrynumber": 2},
    "Cl2": {"spin": 0, "symmetrynumber": 2},
    "SO2": {"spin": 0, "symmetrynumber": 2},
    "H2S": {"spin": 0, "symmetrynumber": 2},
    "CH3OH": {"spin": 0, "symmetrynumber": 1},
}


from src.utils.mlips.loader import load_wrapper

def check_linearity(atoms, tol: float = 0.01) -> bool:
    """
    Check if a molecule is linear.

    Args:
        atoms: ASE Atoms object
        tol: Tolerance for SVD ratio (default: 0.01)

    Returns:
        True if the molecule is linear
    """
    if len(atoms) <= 2:
        return True
    positions = atoms.get_positions()
    centered = positions - positions.mean(axis=0)
    _, s, _ = np.linalg.svd(centered)
    if s[0] > 1e-10:
        return s[1] / s[0] < tol
    return True


def get_geometry_string(atoms) -> str:
    """
    Determine the geometry string for IdealGasThermo.

    Args:
        atoms: ASE Atoms object

    Returns:
        'monatomic', 'linear', or 'nonlinear'
    """
    if len(atoms) == 1:
        return "monatomic"
    if check_linearity(atoms):
        return "linear"
    return "nonlinear"


def get_molecule_properties(name: str, spin_overrides: dict, sym_overrides: dict) -> tuple[float, int]:
    """
    Get spin and symmetry number for a molecule.

    Checks override dicts first, then the built-in lookup table, then defaults.

    Args:
        name: Molecule formula/name
        spin_overrides: User-provided spin overrides {name: spin_value}
        sym_overrides: User-provided symmetry number overrides {name: sym_value}

    Returns:
        Tuple of (spin, symmetrynumber)
    """
    # Defaults
    spin = 0.0
    symmetrynumber = 1

    # Lookup table
    if name in MOLECULE_PROPERTIES:
        spin = MOLECULE_PROPERTIES[name]["spin"]
        symmetrynumber = MOLECULE_PROPERTIES[name]["symmetrynumber"]

    # User overrides
    if name in spin_overrides:
        spin = spin_overrides[name]
    if name in sym_overrides:
        symmetrynumber = sym_overrides[name]

    return float(spin), int(symmetrynumber)


def parse_reaction(reaction_str: str) -> tuple[list[tuple[int, str]], list[tuple[int, str]]]:
    """
    Parse a reaction string into reactants and products.

    Format: "2H2 + O2 -> 2H2O"
    Returns lists of (coefficient, species_name) tuples.

    Args:
        reaction_str: Balanced reaction string with '->' separator

    Returns:
        Tuple of (reactants, products) where each is a list of (coeff, name) tuples
    """
    if "->" not in reaction_str:
        raise ValueError(f"Reaction string must contain '->': {reaction_str}")

    sides = reaction_str.split("->")
    if len(sides) != 2:
        raise ValueError(f"Reaction string must have exactly one '->': {reaction_str}")

    def parse_side(side_str: str) -> list[tuple[int, str]]:
        """Parse one side of the reaction."""
        species_list = []
        terms = [t.strip() for t in side_str.strip().split("+")]
        for term in terms:
            term = term.strip()
            # Match optional coefficient followed by molecule name
            match = re.match(r"^(\d+)?\s*(.+)$", term)
            if match:
                coeff = int(match.group(1)) if match.group(1) else 1
                name = match.group(2).strip()
                species_list.append((coeff, name))
            else:
                raise ValueError(f"Cannot parse reaction term: {term}")
        return species_list

    reactants = parse_side(sides[0])
    products = parse_side(sides[1])

    logger.info(f"Parsed reaction: {reactants} -> {products}")
    return reactants, products


def compute_species_thermo(
    species_name: str,
    wrapper: Any,
    temperature: float,
    pressure: float,
    fmax: float,
    delta: float,
    nfree: int,
    spin_overrides: dict,
    sym_overrides: dict,
    output_dir: str,
    structure_path: Optional[str] = None,
) -> dict:
    """
    Compute thermodynamic quantities for a single gas-phase species.

    Args:
        species_name: ASE molecule name or identifier
        wrapper: Loaded MLIP wrapper
        temperature: Temperature in K
        pressure: Pressure in Pa
        fmax: Force convergence for relaxation (eV/Å)
        delta: Finite-difference displacement (Å)
        nfree: Number of displacements per DOF
        spin_overrides: User-provided spin values
        sym_overrides: User-provided symmetry numbers
        output_dir: Output directory for this species
        structure_path: Optional path to structure file (overrides species_name)

    Returns:
        Dictionary with thermodynamic data for this species
    """
    os.makedirs(output_dir, exist_ok=True)

    # Build or load the molecule
    if structure_path:
        atoms = read(structure_path)
        logger.info(f"Loaded structure from {structure_path}")
    else:
        atoms = ase_molecule(species_name)
        logger.info(f"Built molecule: {species_name}")

    atoms.pbc = False
    calc = wrapper.create_calculator()
    atoms.calc = calc

    # Relax
    logger.info(f"Relaxing {species_name} with fmax={fmax} eV/Å ...")
    opt = LBFGS(atoms, logfile=os.path.join(output_dir, "relax.log"))
    opt.run(fmax=fmax)
    potential_energy = atoms.get_potential_energy()
    logger.info(f"  Relaxed energy: {potential_energy:.6f} eV ({opt.nsteps} steps)")

    # Determine geometry
    geometry = get_geometry_string(atoms)
    n_atoms = len(atoms)
    logger.info(f"  Geometry: {geometry}, {n_atoms} atoms")

    # Get spin and symmetry number
    formula = atoms.get_chemical_formula()
    spin, symmetrynumber = get_molecule_properties(
        species_name, spin_overrides, sym_overrides
    )
    logger.info(f"  Spin: {spin}, Symmetry number: {symmetrynumber}")

    # Vibration analysis
    vib_name = os.path.join(output_dir, "vib")
    vib = Vibrations(atoms, delta=delta, name=vib_name, nfree=nfree)
    vib.clean()
    vib.run()

    # Get vibrational energies (in eV)
    vib_energies_complex = vib.get_energies()
    frequencies_cm1_complex = vib.get_frequencies()

    # Filter: keep only real vibrational modes (above threshold)
    real_vib_energies = []
    all_frequencies_cm1 = []
    real_mode_info = []

    for i, (e_ev, f_cm1) in enumerate(zip(vib_energies_complex, frequencies_cm1_complex)):
        freq_real = float(np.real(f_cm1))
        freq_imag = float(np.imag(f_cm1))

        if abs(freq_imag) > TRANSLATION_ROTATION_THRESHOLD:
            all_frequencies_cm1.append(f"{abs(freq_imag):.1f}i")
        elif abs(freq_real) < TRANSLATION_ROTATION_THRESHOLD:
            all_frequencies_cm1.append(round(freq_real, 1))
        else:
            all_frequencies_cm1.append(round(freq_real, 1))
            real_vib_energies.append(float(np.real(e_ev)))
            real_mode_info.append({
                "index": i,
                "frequency_cm1": freq_real,
                "energy_meV": float(np.real(e_ev)) * 1000.0,
            })

    logger.info(f"  Found {len(real_vib_energies)} real vibrational modes")

    # ZPE
    zpe_ev = float(vib.get_zero_point_energy())

    # Construct IdealGasThermo
    vib_energies_array = np.array(real_vib_energies)

    thermo = IdealGasThermo(
        vib_energies=vib_energies_array,
        potentialenergy=potential_energy,
        atoms=atoms,
        geometry=geometry,
        symmetrynumber=symmetrynumber,
        spin=spin,
    )

    # Compute thermodynamic quantities
    enthalpy = thermo.get_enthalpy(temperature=temperature, verbose=False)
    entropy = thermo.get_entropy(temperature=temperature, pressure=pressure, verbose=False)
    gibbs = thermo.get_gibbs_energy(temperature=temperature, pressure=pressure, verbose=False)

    logger.info(f"  H({temperature} K) = {enthalpy:.6f} eV = {enthalpy * EV_TO_KJMOL:.2f} kJ/mol")
    logger.info(f"  S({temperature} K) = {entropy:.6e} eV/K = {entropy * EV_TO_KJMOL * 1000:.2f} J/(mol·K)")
    logger.info(f"  G({temperature} K) = {gibbs:.6f} eV = {gibbs * EV_TO_KJMOL:.2f} kJ/mol")

    result = {
        "species": species_name,
        "formula": formula,
        "n_atoms": n_atoms,
        "geometry": geometry,
        "spin": spin,
        "symmetrynumber": symmetrynumber,
        "potential_energy_eV": potential_energy,
        "zero_point_energy_eV": zpe_ev,
        "frequencies_cm1": all_frequencies_cm1,
        "real_vibrational_modes": real_mode_info,
        "n_real_modes": len(real_vib_energies),
        "enthalpy_eV": enthalpy,
        "enthalpy_kJmol": enthalpy * EV_TO_KJMOL,
        "entropy_eV_per_K": entropy,
        "entropy_J_per_molK": entropy * EV_TO_KJMOL * 1000,
        "gibbs_energy_eV": gibbs,
        "gibbs_energy_kJmol": gibbs * EV_TO_KJMOL,
        "temperature_K": temperature,
        "pressure_Pa": pressure,
    }

    return result


def parse_overrides(override_str: Optional[str]) -> dict:
    """
    Parse override strings like "O2:1,NO:0.5" into a dictionary.

    Args:
        override_str: Comma-separated name:value pairs, or None

    Returns:
        Dictionary mapping molecule name to numeric value
    """
    if not override_str:
        return {}
    result = {}
    for pair in override_str.split(","):
        pair = pair.strip()
        if ":" in pair:
            name, value = pair.split(":", 1)
            result[name.strip()] = float(value.strip())
    return result


def main():
    """Main entry point for thermochemistry calculations."""
    parser = argparse.ArgumentParser(
        description="Compute gas-phase thermodynamic quantities with MLIPs",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    # Input mode
    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument("--molecule", help="ASE built-in molecule name (e.g., H2O, CO2)")
    mode_group.add_argument("--structure", help="Path to structure file (.xyz, .cif, etc.)")
    mode_group.add_argument("--reaction", help="Balanced reaction string (e.g., '2H2 + O2 -> 2H2O')")

    # Thermodynamic parameters
    parser.add_argument("--temperature", type=float, default=298.15,
                        help="Temperature in Kelvin")
    parser.add_argument("--pressure", type=float, default=101325,
                        help="Pressure in Pascals (default: 1 atm)")

    # Model parameters
    parser.add_argument("--model_type", required=True, choices=["mace", "fairchem", "matgl"],
                        help="MLIP type")
    parser.add_argument("--model_name", default=None,
                        help="Specific model name (optional)")
    parser.add_argument("--task", default=None,
                        help="Task/Head name (e.g. omol, omat) for multi-task models")

    # Override parameters
    parser.add_argument("--spin", default=None,
                        help="Spin override as name:value pairs (e.g., 'O2:1,NO:0.5')")
    parser.add_argument("--symmetry_number", default=None,
                        help="Symmetry number override as name:value pairs (e.g., 'H2:2,CH4:12')")

    # Vibration parameters
    parser.add_argument("--delta", type=float, default=0.01,
                        help="Finite-difference displacement in Angstrom")
    parser.add_argument("--nfree", type=int, default=2, choices=[2, 4],
                        help="Number of displacements per DOF")
    parser.add_argument("--fmax", type=float, default=0.01,
                        help="Force convergence for relaxation (eV/Angstrom)")

    # Output
    parser.add_argument("--output_dir", help="Output directory")
    parser.add_argument("--device", default="auto", help="Device (cpu, cuda, auto)")

    args = parser.parse_args()

    # Parse overrides
    spin_overrides = parse_overrides(args.spin)
    sym_overrides = {k: int(v) for k, v in parse_overrides(args.symmetry_number).items()}

    # Determine output directory
    if not args.output_dir:
        args.output_dir = str(get_current_research_dir() / "thermochemistry")
    os.makedirs(args.output_dir, exist_ok=True)

    # Load MLIP
    wrapper = load_wrapper(args.model_type, args.model_name, device=args.device, task=args.task)

    if args.reaction:
        # ===== Reaction mode =====
        reactants, products = parse_reaction(args.reaction)

        # Collect all unique species
        all_species = {}
        for coeff, name in reactants + products:
            if name not in all_species:
                all_species[name] = name

        # Compute thermo for each species
        species_results = {}
        for name in all_species:
            logger.info(f"\n{'='*60}")
            logger.info(f"Computing thermochemistry for {name}")
            logger.info(f"{'='*60}")
            species_dir = os.path.join(args.output_dir, f"species_{name}")
            result = compute_species_thermo(
                species_name=name,
                wrapper=wrapper,
                temperature=args.temperature,
                pressure=args.pressure,
                fmax=args.fmax,
                delta=args.delta,
                nfree=args.nfree,
                spin_overrides=spin_overrides,
                sym_overrides=sym_overrides,
                output_dir=species_dir,
            )
            species_results[name] = result

        # Compute reaction thermodynamics
        delta_h_ev = 0.0
        delta_s_ev_per_k = 0.0
        delta_g_ev = 0.0

        for coeff, name in products:
            delta_h_ev += coeff * species_results[name]["enthalpy_eV"]
            delta_s_ev_per_k += coeff * species_results[name]["entropy_eV_per_K"]
            delta_g_ev += coeff * species_results[name]["gibbs_energy_eV"]

        for coeff, name in reactants:
            delta_h_ev -= coeff * species_results[name]["enthalpy_eV"]
            delta_s_ev_per_k -= coeff * species_results[name]["entropy_eV_per_K"]
            delta_g_ev -= coeff * species_results[name]["gibbs_energy_eV"]

        delta_h_kjmol = delta_h_ev * EV_TO_KJMOL
        delta_s_jmolk = delta_s_ev_per_k * EV_TO_KJMOL * 1000
        delta_g_kjmol = delta_g_ev * EV_TO_KJMOL

        logger.info(f"\n{'='*60}")
        logger.info(f"Reaction Thermochemistry: {args.reaction}")
        logger.info(f"Temperature: {args.temperature} K, Pressure: {args.pressure} Pa")
        logger.info(f"{'='*60}")
        logger.info(f"  ΔH = {delta_h_ev:.6f} eV = {delta_h_kjmol:.2f} kJ/mol")
        logger.info(f"  ΔS = {delta_s_ev_per_k:.6e} eV/K = {delta_s_jmolk:.2f} J/(mol·K)")
        logger.info(f"  ΔG = {delta_g_ev:.6f} eV = {delta_g_kjmol:.2f} kJ/mol")
        logger.info(f"{'='*60}")

        # Save results
        output = {
            "mode": "reaction",
            "reaction": args.reaction,
            "temperature_K": args.temperature,
            "pressure_Pa": args.pressure,
            "reactants": [{"coefficient": c, "species": n} for c, n in reactants],
            "products": [{"coefficient": c, "species": n} for c, n in products],
            "species": species_results,
            "reaction_thermodynamics": {
                "delta_H_eV": delta_h_ev,
                "delta_H_kJmol": delta_h_kjmol,
                "delta_S_eV_per_K": delta_s_ev_per_k,
                "delta_S_J_per_molK": delta_s_jmolk,
                "delta_G_eV": delta_g_ev,
                "delta_G_kJmol": delta_g_kjmol,
            },
            "model_type": args.model_type,
            "model_name": wrapper.model_name,
        }

    else:
        # ===== Single molecule mode =====
        species_name = args.molecule if args.molecule else os.path.basename(args.structure)
        result = compute_species_thermo(
            species_name=args.molecule or species_name,
            wrapper=wrapper,
            temperature=args.temperature,
            pressure=args.pressure,
            fmax=args.fmax,
            delta=args.delta,
            nfree=args.nfree,
            spin_overrides=spin_overrides,
            sym_overrides=sym_overrides,
            output_dir=args.output_dir,
            structure_path=args.structure,
        )
        output = {
            "mode": "single_molecule",
            "temperature_K": args.temperature,
            "pressure_Pa": args.pressure,
            "species": result,
            "model_type": args.model_type,
            "model_name": wrapper.model_name,
        }

    # Save JSON
    results_file = os.path.join(args.output_dir, "thermochemistry_results.json")
    with open(results_file, "w") as f:
        json.dump(recursive_tolist(output), f, indent=4)
    logger.info(f"\nResults saved to {results_file}")

    # Save input configs for reproducibility
    from src.utils.config_utils import save_skill_inputs
    save_skill_inputs(args, args.output_dir)


if __name__ == "__main__":
    main()
