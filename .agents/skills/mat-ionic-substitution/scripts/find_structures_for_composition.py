"""
Find all structures that can produce a target composition via ionic substitution.

Given a target composition (e.g., LiCl), this script:
1. Queries Materials Project for direct matches
2. Uses pymatgen's SubstitutionPredictor to find compositions whose ions
   can be substituted to yield the target
3. Fetches those precursor structures from Materials Project
4. Applies the substitutions to generate candidate structures

Based on Hautier et al. 2011, "Data Mined Ionic Substitutions for the
Discovery of New Compounds", Inorganic Chemistry 50(2), 656-663.

Usage:
    python find_structures_for_composition.py --composition LiCl --output_dir results/
    python find_structures_for_composition.py --composition Li2ZrCl6 --threshold 0.01

Requirements:
    - Conda environment: base-agent
    - Required packages: pymatgen, mp-api
    - Environment variable: MP_API_KEY
"""

import argparse
import json
import os
import sys
from pathlib import Path

from pymatgen.core import Composition, Structure
from pymatgen.core.periodic_table import Species
from pymatgen.analysis.structure_prediction.substitution_probability import (
    SubstitutionPredictor,
)
from pymatgen.transformations.standard_transformations import (
    SubstitutionTransformation,
)


def get_oxidation_states_for_composition(
    composition: Composition,
) -> list[dict[str, list[Species]]]:
    """
    Determine likely oxidation state assignments for a composition.

    Args:
        composition: Target pymatgen Composition.

    Returns:
        List of possible oxidation state assignments, each as a dict
        mapping element symbol to list of Species with oxidation states.
    """
    oxi_states = composition.oxi_state_guesses(max_sites=-1)
    return oxi_states


def find_substitution_precursors(
    target_species: list[Species],
    threshold: float = 0.001,
) -> list[dict]:
    """
    Find all compositions that can be substituted to yield the target species.

    Uses SubstitutionPredictor in reverse mode: find all species lists
    that map TO the target species with high probability.

    Args:
        target_species: List of Species with oxidation states for the target.
        threshold: Probability threshold for substitutions.

    Returns:
        List of dicts with 'substitutions' (precursor→target map) and 'probability'.
    """
    predictor = SubstitutionPredictor(threshold=threshold)

    # list_prediction with to_this_composition=True finds what can map TO this list
    predictions = predictor.list_prediction(
        target_species, to_this_composition=True
    )

    # Filter out identity substitutions
    filtered = []
    for pred in predictions:
        sub_map = pred["substitutions"]
        actual_changes = {
            k: v for k, v in sub_map.items() if str(k) != str(v)
        }
        if actual_changes:
            filtered.append({
                "substitutions": {str(k): str(v) for k, v in sub_map.items()},
                "actual_changes": {str(k): str(v) for k, v in actual_changes.items()},
                "probability": pred["probability"],
                "precursor_species": [str(k) for k in sub_map.keys()],
            })

    filtered.sort(key=lambda x: x["probability"], reverse=True)
    return filtered


def query_mp_structures(
    formula: str,
    api_key: str | None = None,
) -> list[dict]:
    """
    Query Materials Project for structures matching a formula.

    Args:
        formula: Chemical formula to search for (e.g., "NaCl").
        api_key: Optional MP API key (defaults to MP_API_KEY env var).

    Returns:
        List of dicts with 'structure', 'material_id', 'formula', 'energy_above_hull'.
    """
    from mp_api.client import MPRester

    api_key = api_key or os.environ.get("MP_API_KEY")
    if not api_key:
        print("WARNING: MP_API_KEY not set. Cannot query Materials Project.")
        return []

    results = []
    with MPRester(api_key) as mpr:
        docs = mpr.materials.summary.search(
            formula=formula,
            fields=[
                "material_id",
                "structure",
                "formula_pretty",
                "energy_above_hull",
                "is_stable",
            ],
        )
        for doc in docs:
            results.append({
                "structure": doc.structure,
                "material_id": str(doc.material_id),
                "formula": doc.formula_pretty,
                "energy_above_hull": doc.energy_above_hull,
                "is_stable": doc.is_stable,
            })

    return results


def apply_substitution(
    structure: Structure,
    sub_map: dict[str, str],
) -> Structure | None:
    """
    Apply an ionic substitution to a structure.

    Args:
        structure: Source pymatgen Structure.
        sub_map: Dict mapping source species (str) to target species (str).

    Returns:
        Substituted Structure, or None if transformation fails.
    """
    # Convert string keys to Species
    species_map = {}
    for old_str, new_str in sub_map.items():
        old_sp = Species.from_str(old_str)
        new_sp = Species.from_str(new_str)
        species_map[old_sp] = new_sp

    # Check that source species exist in structure (by element match)
    source_elements = {sp.element.symbol for sp in species_map.keys()}
    structure_elements = {el.symbol for el in structure.composition.elements}
    if not source_elements.issubset(structure_elements):
        return None

    # Apply substitution at element level (ignoring oxidation states
    # since MP structures may not have them)
    element_map = {}
    for old_sp, new_sp in species_map.items():
        element_map[str(old_sp.element)] = str(new_sp.element)

    new_structure = structure.copy()
    new_structure.replace_species(element_map)
    return new_structure


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Find all structures that can produce a target composition"
    )
    parser.add_argument(
        "--composition",
        required=True,
        help="Target composition (e.g., LiCl, Li2ZrCl6)",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.001,
        help="Probability threshold for substitutions (default: 0.001)",
    )
    parser.add_argument(
        "--max_precursors",
        type=int,
        default=50,
        help="Max number of precursor compositions to search (default: 50)",
    )
    parser.add_argument(
        "--output_dir",
        required=True,
        help="Directory to save results",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    target_comp = Composition(args.composition)
    print(f"Target composition: {target_comp.reduced_formula}")
    print(f"Elements: {[str(el) for el in target_comp.elements]}")

    all_results = []
    structure_index = 0

    # ── Part 1: Direct MP search ──
    print(f"\n{'='*60}")
    print("Part 1: Querying Materials Project for direct matches...")
    print(f"{'='*60}")

    direct_matches = query_mp_structures(target_comp.reduced_formula)
    print(f"Found {len(direct_matches)} direct matches in MP")

    for match in direct_matches:
        cif_name = f"{structure_index:03d}_{match['formula']}_MP_{match['material_id']}.cif"
        cif_path = output_dir / cif_name
        match["structure"].to(filename=str(cif_path))

        all_results.append({
            "index": structure_index,
            "source": "materials_project",
            "material_id": match["material_id"],
            "formula": match["formula"],
            "energy_above_hull": match["energy_above_hull"],
            "is_stable": match["is_stable"],
            "substitution_map": None,
            "precursor_formula": None,
            "probability": None,
            "cif_file": cif_name,
        })
        structure_index += 1

    # ── Part 2: Substitution-derived structures ──
    print(f"\n{'='*60}")
    print("Part 2: Finding substitution precursors...")
    print(f"{'='*60}")

    # Guess oxidation states for target composition
    oxi_guesses = get_oxidation_states_for_composition(target_comp)
    if not oxi_guesses:
        print("WARNING: Could not determine oxidation states for target composition.")
        print("Trying common oxidation states...")
        # Fallback: try to use the composition directly
        oxi_guesses = [{}]

    # Use the first (most likely) oxidation state guess
    if oxi_guesses:
        oxi_assignment = oxi_guesses[0]
        print(f"Using oxidation state assignment: {oxi_assignment}")

        # Build Species list from the oxidation state assignment
        target_species = []
        for el, oxi in oxi_assignment.items():
            target_species.append(Species(str(el), oxi))

        if target_species:
            print(f"Target species: {[str(sp) for sp in target_species]}")

            # Find precursor compositions
            precursors = find_substitution_precursors(
                target_species, threshold=args.threshold
            )
            print(f"Found {len(precursors)} substitution precursors")

            # Limit precursors to search
            precursors_to_search = precursors[: args.max_precursors]

            for precursor in precursors_to_search:
                # Determine the precursor formula by substituting target→precursor
                precursor_elements = set()
                reverse_map = {}
                for prec_sp, tgt_sp in zip(
                    precursor["precursor_species"],
                    [str(sp) for sp in target_species],
                ):
                    prec_el = Species.from_str(prec_sp).element.symbol
                    precursor_elements.add(prec_el)
                    tgt_el = Species.from_str(tgt_sp).element.symbol
                    if prec_el != tgt_el:
                        reverse_map[prec_el] = tgt_el

                # Build precursor formula by element substitution on target
                precursor_comp_dict = {}
                for el, amt in target_comp.as_dict().items():
                    mapped_el = el
                    # Reverse: which precursor element maps to this target element?
                    for prec_el, tgt_el in reverse_map.items():
                        if tgt_el == el:
                            mapped_el = prec_el
                            break
                    precursor_comp_dict[mapped_el] = amt

                precursor_formula = Composition(precursor_comp_dict).reduced_formula

                # Query MP for precursor structures
                print(f"  Searching MP for {precursor_formula} "
                      f"(sub: {precursor['actual_changes']}, "
                      f"p={precursor['probability']:.4f})...")

                mp_structures = query_mp_structures(precursor_formula)
                if not mp_structures:
                    continue

                print(f"    Found {len(mp_structures)} MP structures for {precursor_formula}")

                for mp_struct in mp_structures:
                    # Apply substitution (precursor→target)
                    new_structure = apply_substitution(
                        mp_struct["structure"], 
                        precursor["actual_changes"]
                    )
                    if new_structure is None:
                        continue

                    cif_name = (
                        f"{structure_index:03d}_{target_comp.reduced_formula}"
                        f"_from_{precursor_formula}"
                        f"_{mp_struct['material_id']}.cif"
                    )
                    cif_path = output_dir / cif_name
                    new_structure.to(filename=str(cif_path))

                    sub_str = ", ".join(
                        f"{k}→{v}" for k, v in precursor["actual_changes"].items()
                    )
                    all_results.append({
                        "index": structure_index,
                        "source": "substitution",
                        "material_id": mp_struct["material_id"],
                        "precursor_formula": precursor_formula,
                        "formula": target_comp.reduced_formula,
                        "substitution_map": precursor["actual_changes"],
                        "substitution_str": sub_str,
                        "probability": precursor["probability"],
                        "precursor_energy_above_hull": mp_struct["energy_above_hull"],
                        "precursor_is_stable": mp_struct["is_stable"],
                        "cif_file": cif_name,
                    })
                    structure_index += 1

    # ── Save manifest ──
    manifest_path = output_dir / "structure_manifest.json"
    manifest = {
        "target_composition": target_comp.reduced_formula,
        "threshold": args.threshold,
        "num_direct_matches": len(direct_matches),
        "num_substitution_derived": structure_index - len(direct_matches),
        "total_structures": structure_index,
        "structures": all_results,
    }
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    # ── Print summary ──
    print(f"\n{'='*60}")
    print(f"SUMMARY: Structures for {target_comp.reduced_formula}")
    print(f"{'='*60}")
    print(f"  Direct MP matches:        {len(direct_matches)}")
    print(f"  Substitution-derived:     {structure_index - len(direct_matches)}")
    print(f"  Total structures:         {structure_index}")
    print(f"  Output directory:         {output_dir}")
    print(f"  Manifest:                 {manifest_path}")

    # Print top substitution results
    sub_results = [r for r in all_results if r["source"] == "substitution"]
    if sub_results:
        print(f"\nTop substitution-derived structures:")
        for r in sub_results[:15]:
            print(
                f"  [{r['index']:3d}] {r['precursor_formula']:15s} → {r['formula']:15s} "
                f"({r['substitution_str']}) "
                f"p={r['probability']:.4f} "
                f"[{r['material_id']}]"
            )
        if len(sub_results) > 15:
            print(f"  ... and {len(sub_results) - 15} more")


if __name__ == "__main__":
    main()
