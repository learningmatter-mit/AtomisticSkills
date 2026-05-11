"""
Generate point-defect supercells (vacancies, substitutions, interstitials)
from a bulk crystal structure using pymatgen-analysis-defects.

Usage:
    python generate_defects.py --bulk bulk.cif --supercell_size 2 2 2 --defect_type vacancy --output defects/
    python generate_defects.py --bulk bulk.cif --supercell_size 3 3 3 --defect_type substitution --substitute_element Na --output defects/
    python generate_defects.py --bulk bulk.cif --supercell_size 2 2 2 --defect_type interstitial --interstitial_element Li --output defects/

Requirements:
    - Conda environment: base-agent
    - Required packages: pymatgen, pymatgen-analysis-defects, ase
"""

import argparse
import json
import os
from pathlib import Path
from typing import List, Optional

import numpy as np
from pymatgen.core import Structure
from pymatgen.analysis.defects.generators import (
    VacancyGenerator,
    SubstitutionGenerator,
    InterstitialGenerator,
)
from pymatgen.transformations.standard_transformations import SupercellTransformation


def generate_vacancies(structure: Structure, supercell_matrix: List[List[int]]) -> list:
    """
    Generate all symmetry-unique vacancy defect supercells.

    Args:
        structure: Bulk primitive/conventional cell.
        supercell_matrix: 3x3 supercell transformation matrix.

    Returns:
        List of dicts with 'name', 'structure', 'defect_info'.
    """
    vac_gen = VacancyGenerator()
    defects = vac_gen.generate(structure, rm_species=None)
    results = []
    for i, defect in enumerate(defects):
        sc = defect.get_supercell_structure(
            sc_mat=np.array(supercell_matrix),
            dummy_species="X",
        )
        # Remove the dummy species marking the vacancy site
        sc.remove_species(["X"])
        site_element = defect.site.specie.symbol
        site_idx = int(defect.defect_site_index)
        name = f"vac_{site_element}_{i}"
        results.append({
            "name": name,
            "structure": sc,
            "defect_info": {
                "type": "vacancy",
                "removed_element": site_element,
                "site_index": site_idx,
                "multiplicity": int(defect.multiplicity),
            },
        })
    return results


def generate_substitutions(
    structure: Structure,
    supercell_matrix: List[List[int]],
    substitute_element: str,
) -> list:
    """
    Generate all symmetry-unique substitution defect supercells.

    Args:
        structure: Bulk primitive/conventional cell.
        supercell_matrix: 3x3 supercell transformation matrix.
        substitute_element: Element symbol to substitute in (e.g., 'Na').

    Returns:
        List of dicts with 'name', 'structure', 'defect_info'.
    """
    sub_gen = SubstitutionGenerator()
    defects = sub_gen.generate(structure, substitution={substitute_element: structure.symbol_set})
    results = []
    for i, defect in enumerate(defects):
        sc = defect.get_supercell_structure(sc_mat=np.array(supercell_matrix))
        original_element = defect.site.specie.symbol
        name = f"sub_{substitute_element}_on_{original_element}_{i}"
        results.append({
            "name": name,
            "structure": sc,
            "defect_info": {
                "type": "substitution",
                "original_element": original_element,
                "substitute_element": substitute_element,
                "site_index": int(defect.defect_site_index),
                "multiplicity": int(defect.multiplicity),
            },
        })
    return results


def generate_interstitials(
    structure: Structure,
    supercell_matrix: List[List[int]],
    interstitial_element: str,
) -> list:
    """
    Generate interstitial defect supercells at Voronoi sites.

    Args:
        structure: Bulk primitive/conventional cell.
        supercell_matrix: 3x3 supercell transformation matrix.
        interstitial_element: Element symbol to insert (e.g., 'Li').

    Returns:
        List of dicts with 'name', 'structure', 'defect_info'.
    """
    int_gen = InterstitialGenerator()
    defects = int_gen.generate(structure, insertions={interstitial_element: structure.symbol_set})
    results = []
    for i, defect in enumerate(defects):
        sc = defect.get_supercell_structure(sc_mat=np.array(supercell_matrix))
        name = f"int_{interstitial_element}_{i}"
        results.append({
            "name": name,
            "structure": sc,
            "defect_info": {
                "type": "interstitial",
                "inserted_element": interstitial_element,
                "frac_coords": defect.site.frac_coords.tolist(),
                "multiplicity": int(defect.multiplicity),
            },
        })
    return results


def main():
    parser = argparse.ArgumentParser(
        description="Generate point-defect supercells from a bulk crystal structure."
    )
    parser.add_argument("--bulk", required=True, help="Path to bulk structure file (CIF/POSCAR)")
    parser.add_argument(
        "--supercell_size",
        nargs=3,
        type=int,
        default=[2, 2, 2],
        help="Supercell dimensions (e.g., 2 2 2)",
    )
    parser.add_argument(
        "--defect_type",
        choices=["vacancy", "substitution", "interstitial", "all"],
        default="vacancy",
        help="Type of defects to generate",
    )
    parser.add_argument(
        "--substitute_element",
        default=None,
        help="Element to substitute (required for substitution type)",
    )
    parser.add_argument(
        "--interstitial_element",
        default=None,
        help="Element to insert (required for interstitial type)",
    )
    parser.add_argument("--output", default="defect_structures", help="Output directory")
    args = parser.parse_args()

    # Read bulk structure
    bulk = Structure.from_file(args.bulk)
    print(f"✓ Loaded bulk structure: {bulk.formula} ({len(bulk)} atoms)")

    # Build diagonal supercell matrix
    sc_mat = [
        [args.supercell_size[0], 0, 0],
        [0, args.supercell_size[1], 0],
        [0, 0, args.supercell_size[2]],
    ]

    # Also save the pristine supercell for reference
    pristine_sc = bulk.copy()
    pristine_sc.make_supercell(sc_mat)
    print(f"✓ Supercell: {pristine_sc.formula} ({len(pristine_sc)} atoms)")

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save pristine supercell
    pristine_sc.to(filename=str(output_dir / "pristine_supercell.cif"))

    all_defects = []

    # Generate defects
    if args.defect_type in ("vacancy", "all"):
        vacancies = generate_vacancies(bulk, sc_mat)
        all_defects.extend(vacancies)
        print(f"✓ Generated {len(vacancies)} vacancy defect(s)")

    if args.defect_type in ("substitution", "all"):
        if args.substitute_element is None and args.defect_type == "substitution":
            parser.error("--substitute_element is required for substitution defects")
        if args.substitute_element:
            subs = generate_substitutions(bulk, sc_mat, args.substitute_element)
            all_defects.extend(subs)
            print(f"✓ Generated {len(subs)} substitution defect(s)")

    if args.defect_type in ("interstitial", "all"):
        if args.interstitial_element is None and args.defect_type == "interstitial":
            parser.error("--interstitial_element is required for interstitial defects")
        if args.interstitial_element:
            ints = generate_interstitials(bulk, sc_mat, args.interstitial_element)
            all_defects.extend(ints)
            print(f"✓ Generated {len(ints)} interstitial defect(s)")

    # Write CIF files and metadata
    metadata_list = []
    for defect in all_defects:
        cif_path = output_dir / f"{defect['name']}.cif"
        defect["structure"].to(filename=str(cif_path))
        info = defect["defect_info"].copy()
        info["name"] = defect["name"]
        info["file"] = str(cif_path)
        info["num_atoms"] = len(defect["structure"])
        metadata_list.append(info)
        print(f"  → Saved {cif_path.name} ({len(defect['structure'])} atoms)")

    # Save metadata
    meta_path = output_dir / "defect_metadata.json"
    with open(meta_path, "w") as f:
        json.dump(
            {
                "bulk_formula": bulk.formula,
                "supercell_size": args.supercell_size,
                "pristine_num_atoms": len(pristine_sc),
                "defects": metadata_list,
            },
            f,
            indent=2,
        )
    print(f"\n✓ Saved metadata to {meta_path}")
    print(f"✓ Total defect structures generated: {len(all_defects)}")

    # Save input configs for reproducibility
    from src.utils.config_utils import save_skill_inputs
    save_skill_inputs(args, args.output_dir)


if __name__ == "__main__":
    main()
