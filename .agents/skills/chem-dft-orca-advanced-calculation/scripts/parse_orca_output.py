"""
Parse ORCA output files for various properties.

Extracts structured data from ORCA .out files including energies, orbital
energies, vibrational frequencies, and thermochemistry. For properties not
covered by the built-in parsers, read the raw output file directly.

Usage:
    python parse_orca_output.py --output_file calculation.out --property energy
    python parse_orca_output.py --output_file calculation.out --property frequencies
    python parse_orca_output.py --output_file calculation.out --property all

Requirements:
    - Conda environment: orca-agent
    - No special packages required (pure Python regex parsing)
"""

import argparse
import json
import logging
import os
import re
import sys

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../"))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("ORCA-Parser")

HARTREE_TO_EV = 27.211386245988


def parse_energy(content: str) -> dict:
    """Extract final single-point energy and component energies."""
    result = {}

    matches = re.findall(r"FINAL SINGLE POINT ENERGY\s+([-\d.]+)", content)
    if matches:
        e_hartree = float(matches[-1])
        result["final_energy_hartree"] = e_hartree
        result["final_energy_eV"] = e_hartree * HARTREE_TO_EV

    nuc_match = re.search(r"Nuclear Repulsion\s+:\s+([-\d.]+)\s+Eh", content)
    if nuc_match:
        result["nuclear_repulsion_hartree"] = float(nuc_match.group(1))

    total_match = re.search(r"Total Energy\s+:\s+([-\d.]+)\s+Eh", content)
    if total_match:
        result["total_energy_hartree"] = float(total_match.group(1))

    disp_match = re.search(r"Dispersion correction\s+([-\d.]+)", content)
    if disp_match:
        result["dispersion_correction_hartree"] = float(disp_match.group(1))

    return result


def parse_orbital_energies(content: str) -> dict:
    """Extract orbital energies from the output."""
    result = {"orbitals": []}

    orbital_block = re.search(
        r"ORBITAL ENERGIES\s*\n-+\s*\n\s*NO\s+OCC\s+E\(Eh\)\s+E\(eV\)\s*\n(.*?)(?:\n\s*\n|\Z)",
        content,
        re.DOTALL,
    )
    if not orbital_block:
        return result

    for line in orbital_block.group(1).strip().split("\n"):
        parts = line.split()
        if len(parts) >= 4:
            try:
                orb = {
                    "index": int(parts[0]),
                    "occupation": float(parts[1]),
                    "energy_hartree": float(parts[2]),
                    "energy_eV": float(parts[3]),
                }
                result["orbitals"].append(orb)
            except ValueError:
                continue

    occupied = [o for o in result["orbitals"] if o["occupation"] > 0.5]
    virtual = [o for o in result["orbitals"] if o["occupation"] <= 0.5]
    if occupied and virtual:
        homo = occupied[-1]["energy_eV"]
        lumo = virtual[0]["energy_eV"]
        result["homo_eV"] = homo
        result["lumo_eV"] = lumo
        result["homo_lumo_gap_eV"] = lumo - homo

    return result


def parse_frequencies(content: str) -> dict:
    """Extract vibrational frequencies from a frequency calculation."""
    result = {"frequencies_cm1": [], "ir_intensities_km_per_mol": []}

    freq_matches = re.findall(r"^\s*\d+:\s+([-\d.]+)\s+cm\*\*-1", content, re.MULTILINE)
    if freq_matches:
        result["frequencies_cm1"] = [float(f) for f in freq_matches]

    imaginary = [f for f in result["frequencies_cm1"] if f < 0]
    real = [f for f in result["frequencies_cm1"] if f >= 0]
    result["n_imaginary"] = len(imaginary)
    result["imaginary_frequencies_cm1"] = imaginary
    result["n_real"] = len(real)

    ir_matches = re.findall(
        r"^\s*\d+:\s+[-\d.]+\s+cm\*\*-1\s+([-\d.]+)\s+km/mol",
        content,
        re.MULTILINE,
    )
    if ir_matches:
        result["ir_intensities_km_per_mol"] = [float(x) for x in ir_matches]

    return result


def parse_thermochemistry(content: str) -> dict:
    """Extract thermochemistry data from a frequency/thermo calculation."""
    result = {}

    zpe_match = re.search(r"Zero point energy\s+\.\.\.\s+([-\d.]+)\s+Eh", content)
    if zpe_match:
        zpe = float(zpe_match.group(1))
        result["zero_point_energy_hartree"] = zpe
        result["zero_point_energy_eV"] = zpe * HARTREE_TO_EV

    h_match = re.search(r"Total enthalpy\s+\.\.\.\s+([-\d.]+)\s+Eh", content)
    if h_match:
        h = float(h_match.group(1))
        result["enthalpy_hartree"] = h
        result["enthalpy_eV"] = h * HARTREE_TO_EV

    g_match = re.search(r"Final Gibbs free energy\s+\.\.\.\s+([-\d.]+)\s+Eh", content)
    if g_match:
        g = float(g_match.group(1))
        result["gibbs_energy_hartree"] = g
        result["gibbs_energy_eV"] = g * HARTREE_TO_EV

    s_match = re.search(r"Total entropy correction\s+\.\.\.\s+([-\d.]+)\s+Eh", content)
    if s_match:
        result["entropy_correction_hartree"] = float(s_match.group(1))

    temp_match = re.search(r"Temperature\s+\.\.\.\s+([-\d.]+)\s+K", content)
    if temp_match:
        result["temperature_K"] = float(temp_match.group(1))

    return result


def parse_output(output_path: str, properties: list[str]) -> dict:
    """
    Parse an ORCA output file for the requested properties.

    Args:
        output_path: Path to the .out file
        properties: List of property names to parse

    Returns:
        Dictionary with parsed results
    """
    with open(output_path, "r") as f:
        content = f.read()

    result = {"output_file": os.path.basename(output_path)}
    parse_all = "all" in properties

    if parse_all or "energy" in properties:
        result["energy"] = parse_energy(content)
        if result["energy"]:
            logger.info(f"Energy: {result['energy'].get('final_energy_hartree', 'N/A')} Hartree")

    if parse_all or "orbitals" in properties:
        result["orbitals"] = parse_orbital_energies(content)
        if result["orbitals"].get("homo_lumo_gap_eV"):
            logger.info(f"HOMO-LUMO gap: {result['orbitals']['homo_lumo_gap_eV']:.4f} eV")

    if parse_all or "frequencies" in properties:
        result["frequencies"] = parse_frequencies(content)
        if result["frequencies"]["frequencies_cm1"]:
            logger.info(f"Found {len(result['frequencies']['frequencies_cm1'])} vibrational modes")
            if result["frequencies"]["n_imaginary"] > 0:
                logger.warning(f"  {result['frequencies']['n_imaginary']} imaginary frequencies found")

    if parse_all or "thermochemistry" in properties:
        result["thermochemistry"] = parse_thermochemistry(content)
        if result["thermochemistry"].get("gibbs_energy_hartree"):
            logger.info(f"Gibbs energy: {result['thermochemistry']['gibbs_energy_hartree']:.10f} Hartree")

    return result


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Parse ORCA output files for various properties",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument("--output_file", required=True, help="Path to ORCA .out file")
    parser.add_argument(
        "--property",
        nargs="+",
        default=["energy"],
        choices=["energy", "orbitals", "frequencies", "thermochemistry", "all"],
        help="Properties to parse",
    )
    parser.add_argument("--output_dir", default=None, help="Directory to save parsed JSON")

    args = parser.parse_args()

    if not args.output_dir:
        args.output_dir = os.path.dirname(os.path.abspath(args.output_file))

    result = parse_output(args.output_file, args.property)

    os.makedirs(args.output_dir, exist_ok=True)
    results_file = os.path.join(args.output_dir, "parsed_results.json")
    with open(results_file, "w") as f:
        json.dump(result, f, indent=4)
    logger.info(f"Parsed results saved to {results_file}")


if __name__ == "__main__":
    main()
