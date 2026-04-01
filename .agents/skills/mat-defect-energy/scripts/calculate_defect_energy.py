"""
Calculate point-defect formation energies from MLIP relaxation results.

Formation energy:
    E_f = E_defect - (n_defect / n_bulk) * E_bulk + sum_i(Delta_n_i * mu_i)

where mu_i defaults to the elemental ground-state energy (metal-rich limit).

Usage:
    python calculate_defect_energy.py --bulk_dir bulk_relaxation/ --defect_dir defect_relaxations/ \
        --supercell_size 2 2 2 --output defect_energies.json

Requirements:
    - Conda environment: base-agent
    - Required packages: pymatgen, ase
"""

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Dict, Optional, Tuple

from pymatgen.core import Structure, Composition


def parse_relaxation_dir(relax_dir: Path) -> Tuple[float, Structure]:
    """
    Parse a relaxation output directory (from MCP relax_structure).

    Looks for energy in relaxation_results.json, result.json, or relaxed_energy.txt,
    and structure in relaxed_structure.cif or final_structure.cif.

    Args:
        relax_dir: Path to relaxation output directory.

    Returns:
        Tuple of (energy_eV, Structure).
    """
    energy = None
    # Try relaxation_results.json first (MCP standard)
    for fname in ["relaxation_results.json", "result.json"]:
        fpath = relax_dir / fname
        if fpath.exists():
            with open(fpath) as f:
                data = json.load(f)
            energy = data.get("relaxed_energy") or data.get("energy") or data.get("final_energy")
            if energy is not None:
                break

    # Fallback to relaxed_energy.txt
    if energy is None:
        txt_path = relax_dir / "relaxed_energy.txt"
        if txt_path.exists():
            with open(txt_path) as f:
                energy = float(f.read().strip())

    if energy is None:
        raise FileNotFoundError(f"No energy found in {relax_dir}")

    # Find structure
    structure = None
    for sname in ["relaxed_structure.cif", "final_structure.cif"]:
        spath = relax_dir / sname
        if spath.exists():
            structure = Structure.from_file(str(spath))
            break

    if structure is None:
        cifs = list(relax_dir.glob("*.cif"))
        if cifs:
            structure = Structure.from_file(str(cifs[0]))

    if structure is None:
        raise FileNotFoundError(f"No structure found in {relax_dir}")

    return energy, structure


def get_species_count(structure: Structure) -> Dict[str, int]:
    """
    Get element counts from a structure.

    Args:
        structure: Pymatgen Structure.

    Returns:
        Dict mapping element symbol to count.
    """
    comp = structure.composition.element_composition
    return {str(el): int(amt) for el, amt in comp.items()}


def load_elemental_energies(energies_file: Optional[str] = None) -> Dict[str, float]:
    """
    Load elemental reference energies.

    First tries the provided file, then falls back to the mat-elemental-energies
    skill's cached results.

    Args:
        energies_file: Optional path to JSON file with element->energy mapping.

    Returns:
        Dict mapping element symbol to energy per atom (eV/atom).
    """
    if energies_file and Path(energies_file).exists():
        with open(energies_file) as f:
            return json.load(f)

    # Try standard skill location
    skill_path = Path(__file__).parent.parent.parent / "mat-elemental-energies" / "resources"
    if skill_path.exists():
        for fname in skill_path.glob("*.json"):
            with open(fname) as f:
                data = json.load(f)
            # Expect format: {element: {energy_per_atom: float, ...}} or {element: float}
            result = {}
            for k, v in data.items():
                if isinstance(v, dict):
                    result[k] = v.get("energy_per_atom", v.get("energy", 0.0))
                else:
                    result[k] = float(v)
            if result:
                return result

    print("⚠️  No elemental energies found. Chemical potential corrections will be zero.")
    return {}


def main():
    parser = argparse.ArgumentParser(
        description="Calculate point-defect formation energies from relaxation results."
    )
    parser.add_argument("--bulk_dir", required=True, help="Directory with bulk relaxation results")
    parser.add_argument(
        "--defect_dir", required=True, help="Directory with defect relaxation results"
    )
    parser.add_argument(
        "--supercell_size",
        nargs=3,
        type=int,
        default=[2, 2, 2],
        help="Supercell dimensions used for defect generation",
    )
    parser.add_argument(
        "--elemental_energies",
        default=None,
        help="JSON file mapping element -> energy_per_atom (eV/atom)",
    )
    parser.add_argument("--output", default="defect_energies.json", help="Output JSON file")
    args = parser.parse_args()

    bulk_dir = Path(args.bulk_dir)
    defect_dir = Path(args.defect_dir)

    # Parse bulk (this should be the pristine SUPERCELL, same size as defect cells)
    bulk_energy, bulk_structure = parse_relaxation_dir(bulk_dir)
    n_bulk = len(bulk_structure)
    e_bulk_per_atom = bulk_energy / n_bulk
    bulk_species = get_species_count(bulk_structure)
    print(f"✓ Bulk: {bulk_structure.formula}, E = {bulk_energy:.4f} eV, "
          f"E/atom = {e_bulk_per_atom:.4f} eV/atom ({n_bulk} atoms)")

    # The pristine supercell is the bulk_dir itself (already the supercell)
    pristine_species = bulk_species.copy()
    n_pristine = n_bulk
    e_pristine = bulk_energy

    # Load elemental energies for chemical potential
    elem_energies = load_elemental_energies(args.elemental_energies)
    if elem_energies:
        print(f"✓ Loaded elemental energies for: {', '.join(elem_energies.keys())}")

    # Process each defect
    results = []
    for subdir in sorted(defect_dir.iterdir()):
        if not subdir.is_dir():
            continue

        # Skip pristine_supercell if present
        if "pristine" in subdir.name:
            continue

        defect_energy, defect_structure = parse_relaxation_dir(subdir)
        n_defect = len(defect_structure)
        defect_species = get_species_count(defect_structure)

        # Compute Delta_n for each species (pristine - defect = removed count)
        delta_n = {}
        all_elements = set(list(pristine_species.keys()) + list(defect_species.keys()))
        for el in all_elements:
            dn = pristine_species.get(el, 0) - defect_species.get(el, 0)
            if dn != 0:
                delta_n[el] = dn

        # Chemical potential correction
        mu_correction = 0.0
        for el, dn in delta_n.items():
            mu = elem_energies.get(el, 0.0)
            mu_correction += dn * mu

        # Formation energy — direct subtraction, no atom-ratio scaling
        # E_f = E_defect - E_pristine + sum(delta_n_i * mu_i)
        e_f = defect_energy - e_pristine + mu_correction

        result = {
            "name": subdir.name,
            "defect_energy_eV": defect_energy,
            "num_atoms_defect": n_defect,
            "delta_n": delta_n,
            "mu_correction_eV": mu_correction,
            "formation_energy_eV": e_f,
        }
        results.append(result)

        # Determine defect description
        desc_parts = []
        for el, dn in delta_n.items():
            if dn > 0:
                desc_parts.append(f"-{dn}{el}")  # removed
            elif dn < 0:
                desc_parts.append(f"+{-dn}{el}")  # added
        desc = " ".join(desc_parts) if desc_parts else "unknown"

        print(f"  {subdir.name}: E_f = {e_f:.3f} eV ({desc})")

    # Sort by formation energy
    results.sort(key=lambda x: x["formation_energy_eV"])

    output_data = {
        "bulk_formula": bulk_structure.formula,
        "bulk_energy_per_atom_eV": e_bulk_per_atom,
        "supercell_size": args.supercell_size,
        "pristine_num_atoms": n_pristine,
        "elemental_energies_used": elem_energies,
        "defects": results,
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(output_data, f, indent=2)

    print(f"\n✓ Saved {len(results)} defect formation energies to {output_path}")


if __name__ == "__main__":
    main()
