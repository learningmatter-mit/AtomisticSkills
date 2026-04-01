"""
Generate defect supercells with charge states for DFT calculations
using pymatgen-analysis-defects.

Usage:
    python generate_defect_structures.py --bulk MgO.cif --supercell_size 3 3 3 \
        --defect_type vacancy --charge_range -2 2 --output dft_defects/

Requirements:
    - Conda environment: base-agent
    - Required packages: pymatgen, pymatgen-analysis-defects
"""

import argparse
import json
from pathlib import Path
from typing import List, Optional

import numpy as np
from pymatgen.core import Structure
from pymatgen.analysis.defects.generators import (
    VacancyGenerator,
    SubstitutionGenerator,
    InterstitialGenerator,
)


def generate_defect_supercells(
    bulk: Structure,
    sc_mat: List[List[int]],
    defect_type: str = "vacancy",
    charge_range: tuple = (-2, 2),
    substitute_element: Optional[str] = None,
    interstitial_element: Optional[str] = None,
) -> list:
    """
    Generate defect supercells for each unique defect site and charge state.

    Args:
        bulk: Primitive/conventional bulk structure.
        sc_mat: 3x3 supercell matrix.
        defect_type: 'vacancy', 'substitution', or 'interstitial'.
        charge_range: (min_charge, max_charge) inclusive range.
        substitute_element: Element for substitution.
        interstitial_element: Element for interstitial.

    Returns:
        List of dicts with 'name', 'structure', 'charge', 'defect_info'.
    """
    if defect_type == "vacancy":
        gen = VacancyGenerator()
        defects = list(gen.generate(bulk, rm_species=None))
    elif defect_type == "substitution":
        gen = SubstitutionGenerator()
        defects = list(gen.generate(bulk, substitution={substitute_element: bulk.symbol_set}))
    elif defect_type == "interstitial":
        gen = InterstitialGenerator()
        defects = list(gen.generate(bulk, insertions={interstitial_element: bulk.symbol_set}))
    else:
        raise ValueError(f"Unknown defect_type: {defect_type}")

    results = []
    for i, defect in enumerate(defects):
        site_element = defect.site.specie.symbol

        # Generate supercell for neutral defect as base structure
        if defect_type == "vacancy":
            sc = defect.get_supercell_structure(
                sc_mat=np.array(sc_mat), dummy_species="X"
            )
            sc.remove_species(["X"])
            base_name = f"vac_{site_element}_{i}"
        elif defect_type == "substitution":
            sc = defect.get_supercell_structure(sc_mat=np.array(sc_mat))
            base_name = f"sub_{substitute_element}_on_{site_element}_{i}"
        else:
            sc = defect.get_supercell_structure(sc_mat=np.array(sc_mat))
            base_name = f"int_{interstitial_element}_{i}"

        # For each charge state, the atomic structure is the same
        # (charge is handled via INCAR NELECT setting in DFT)
        for q in range(charge_range[0], charge_range[1] + 1):
            charge_label = f"q{q:+d}" if q != 0 else "q0"
            name = f"{base_name}_{charge_label}"
            results.append({
                "name": name,
                "structure": sc.copy(),
                "charge": q,
                "defect_info": {
                    "type": defect_type,
                    "site_element": site_element,
                    "defect_index": i,
                    "multiplicity": int(defect.multiplicity),
                    "base_name": base_name,
                },
            })

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Generate defect supercells with charge states for DFT."
    )
    parser.add_argument("--bulk", required=True, help="Path to bulk structure file")
    parser.add_argument(
        "--supercell_size", nargs=3, type=int, default=[3, 3, 3],
        help="Supercell dimensions"
    )
    parser.add_argument(
        "--defect_type", choices=["vacancy", "substitution", "interstitial", "all"],
        default="vacancy", help="Type of defects to generate"
    )
    parser.add_argument(
        "--charge_range", nargs=2, type=int, default=[-2, 2],
        help="Min and max charge states (inclusive)"
    )
    parser.add_argument("--substitute_element", default=None, help="Element for substitution")
    parser.add_argument("--interstitial_element", default=None, help="Element for interstitial")
    parser.add_argument("--output", default="dft_defects", help="Output directory")
    args = parser.parse_args()

    bulk = Structure.from_file(args.bulk)
    print(f"✓ Loaded bulk: {bulk.formula} ({len(bulk)} atoms)")

    sc_mat = [
        [args.supercell_size[0], 0, 0],
        [0, args.supercell_size[1], 0],
        [0, 0, args.supercell_size[2]],
    ]

    # Create pristine supercell
    pristine = bulk.copy()
    pristine.make_supercell(sc_mat)
    print(f"✓ Supercell: {pristine.formula} ({len(pristine)} atoms)")

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save pristine
    pristine.to(filename=str(output_dir / "pristine_supercell.cif"))

    # Determine which defect types to generate
    defect_types = []
    if args.defect_type in ("vacancy", "all"):
        defect_types.append("vacancy")
    if args.defect_type in ("substitution", "all") and args.substitute_element:
        defect_types.append("substitution")
    if args.defect_type in ("interstitial", "all") and args.interstitial_element:
        defect_types.append("interstitial")

    all_defects = []
    for dt in defect_types:
        defects = generate_defect_supercells(
            bulk, sc_mat, dt,
            charge_range=tuple(args.charge_range),
            substitute_element=args.substitute_element,
            interstitial_element=args.interstitial_element,
        )
        all_defects.extend(defects)
        print(f"✓ Generated {len(defects)} {dt} structure(s) "
              f"(including charge states {args.charge_range[0]} to {args.charge_range[1]})")

    # Write structure files and build index
    defect_index = {
        "bulk_formula": bulk.formula,
        "supercell_size": args.supercell_size,
        "pristine_num_atoms": len(pristine),
        "charge_range": args.charge_range,
        "defects": [],
    }

    for defect in all_defects:
        cif_path = output_dir / f"{defect['name']}.cif"
        defect["structure"].to(filename=str(cif_path))

        entry = {
            "name": defect["name"],
            "file": str(cif_path),
            "charge": defect["charge"],
            "num_atoms": len(defect["structure"]),
        }
        entry.update(defect["defect_info"])
        defect_index["defects"].append(entry)
        print(f"  → {defect['name']} ({len(defect['structure'])} atoms, q={defect['charge']:+d})")

    # Save index
    index_path = output_dir / "defect_index.json"
    with open(index_path, "w") as f:
        json.dump(defect_index, f, indent=2)

    print(f"\n✓ Saved {len(all_defects)} structures and index to {output_dir}")


if __name__ == "__main__":
    main()
