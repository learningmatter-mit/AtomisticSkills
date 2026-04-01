"""
Propose ionic substitutions for a given crystal structure.

Given an input structure, uses pymatgen's data-mined ionic substitution model
(Hautier et al. 2011) to propose all high-probability ion substitutions.
Handles single, double, and multi-ion swaps automatically.

Usage:
    python propose_substitutions.py structure.cif --output_dir substitutions/
    python propose_substitutions.py structure.cif --threshold 0.01

Requirements:
    - Conda environment: base-agent
    - Required packages: pymatgen
"""

import argparse
import json
import sys
from pathlib import Path

from pymatgen.core import Structure
from pymatgen.analysis.structure_prediction.substitutor import Substitutor
from pymatgen.transformations.standard_transformations import (
    AutoOxiStateDecorationTransformation,
)


def propose_substitutions(
    structure: Structure,
    threshold: float = 0.001,
    max_results: int = 100,
) -> list[dict]:
    """
    Propose all high-probability ionic substitutions for a structure.

    Uses pymatgen's Substitutor (Hautier et al. 2011) to enumerate
    charge-balanced substitutions above the probability threshold.

    Args:
        structure: Input pymatgen Structure (will be auto-decorated with
                   oxidation states if not already).
        threshold: Probability cutoff for substitutions (default: 0.001).
        max_results: Maximum number of substituted structures to return.

    Returns:
        List of dicts with keys:
            - 'structure': substituted pymatgen Structure
            - 'substitution_map': dict mapping original → new species
            - 'probability': substitution probability
            - 'formula': reduced formula of substituted structure
    """
    # Auto-decorate with oxidation states if needed
    has_oxi = all(
        hasattr(site.specie, "oxi_state") and site.specie.oxi_state != 0
        for site in structure
    )
    if not has_oxi:
        print("Auto-decorating structure with oxidation states...")
        oxi_transform = AutoOxiStateDecorationTransformation()
        structure = oxi_transform.apply_transformation(structure)
        print(f"  Decorated species: {[str(sp) for sp in structure.species]}")

    # Get the species list
    species_list = list(set(structure.species))
    print(f"Species in structure: {[str(sp) for sp in species_list]}")

    # Initialize Substitutor with threshold
    substitutor = Substitutor(threshold=threshold)

    # Use pred_from_list to get all possible substitution maps
    print(f"Finding substitutions above threshold={threshold}...")
    substitution_maps = substitutor.pred_from_list(species_list)
    print(f"Found {len(substitution_maps)} substitution maps")

    # Apply each substitution to produce new structures
    results = []
    for sub_info in substitution_maps:
        sub_map = sub_info["substitutions"]
        probability = sub_info["probability"]

        # Skip identity substitution (no change)
        actual_changes = {
            k: v for k, v in sub_map.items() if str(k) != str(v)
        }
        if not actual_changes:
            continue

        # Apply substitution
        new_structure = structure.copy()
        for old_sp, new_sp in actual_changes.items():
            new_structure.replace_species({old_sp: new_sp})

        # Check charge balance
        total_charge = sum(
            site.specie.oxi_state * 1 for site in new_structure
        )
        if abs(total_charge) > 0.01:
            continue

        results.append({
            "structure": new_structure,
            "substitution_map": {str(k): str(v) for k, v in actual_changes.items()},
            "probability": probability,
            "formula": new_structure.composition.reduced_formula,
        })

    # Sort by probability descending
    results.sort(key=lambda x: x["probability"], reverse=True)

    # Limit results
    if len(results) > max_results:
        results = results[:max_results]

    return results


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Propose ionic substitutions for a crystal structure"
    )
    parser.add_argument(
        "--structure",
        required=True,
        help="Path to input structure file (CIF, POSCAR, etc.)",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.001,
        help="Probability threshold for substitutions (default: 0.001)",
    )
    parser.add_argument(
        "--max_results",
        type=int,
        default=100,
        help="Maximum number of results to return (default: 100)",
    )
    parser.add_argument(
        "--output_dir",
        required=True,
        help="Directory to save substituted structures and manifest",
    )
    args = parser.parse_args()

    # Load structure
    structure_path = Path(args.structure)
    if not structure_path.exists():
        print(f"ERROR: Structure file not found: {structure_path}")
        sys.exit(1)

    structure = Structure.from_file(str(structure_path))
    print(f"Loaded structure: {structure.composition.reduced_formula}")
    print(f"  Num atoms: {len(structure)}")

    # Run substitution prediction
    results = propose_substitutions(
        structure,
        threshold=args.threshold,
        max_results=args.max_results,
    )

    if not results:
        print("No substitutions found above threshold.")
        sys.exit(0)

    # Save results
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    manifest_entries = []
    for i, result in enumerate(results):
        # Save CIF
        formula = result["formula"]
        cif_name = f"{i:03d}_{formula}.cif"
        cif_path = output_dir / cif_name
        result["structure"].to(filename=str(cif_path))

        manifest_entries.append({
            "index": i,
            "formula": formula,
            "substitution_map": result["substitution_map"],
            "probability": result["probability"],
            "cif_file": cif_name,
        })

    # Save manifest
    manifest_path = output_dir / "substitution_manifest.json"
    manifest = {
        "source_structure": str(structure_path),
        "source_formula": structure.composition.reduced_formula,
        "threshold": args.threshold,
        "num_substitutions": len(manifest_entries),
        "substitutions": manifest_entries,
    }
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    # Print summary
    print(f"\n{'='*60}")
    print(f"Source: {structure.composition.reduced_formula}")
    print(f"Substitutions found: {len(results)}")
    print(f"Output directory: {output_dir}")
    print(f"{'='*60}")
    for entry in manifest_entries[:20]:
        sub_str = ", ".join(
            f"{k}→{v}" for k, v in entry["substitution_map"].items()
        )
        print(f"  [{entry['index']:3d}] {entry['formula']:20s} ({sub_str}) p={entry['probability']:.4f}")
    if len(manifest_entries) > 20:
        print(f"  ... and {len(manifest_entries) - 20} more (see manifest)")


if __name__ == "__main__":
    main()
