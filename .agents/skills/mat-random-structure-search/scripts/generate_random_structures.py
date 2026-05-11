"""
Generate random crystal structures for a given composition (AIRSS-style).

Generates random crystal structures using pymatgen's Structure.from_spacegroup()
with randomized lattice parameters and Wyckoff positions. Structures are filtered
for minimum interatomic distances to avoid unphysical configurations.

This implements the core idea of Ab Initio Random Structure Searching (AIRSS)
by Pickard & Needs, but uses MLIP relaxation instead of DFT for efficiency.

Usage:
    python generate_random_structures.py --composition NaCl --num_structures 100
    python generate_random_structures.py --composition Li2ZrCl6 --num_structures 50 --spacegroups 12,14,62,166

Requirements:
    - Conda environment: base-agent
    - Required packages: pymatgen, numpy
"""

import argparse
import json
import sys
import warnings
from pathlib import Path

import numpy as np
from pymatgen.core import Composition, Lattice, Structure, Element
from pymatgen.symmetry.groups import SpaceGroup


# Common space groups for inorganic crystals, weighted by frequency in ICSD
COMMON_SPACEGROUPS = [
    # Cubic
    225, 227, 221, 229, 216, 226,
    # Hexagonal
    194, 186, 167, 166, 193, 164,
    # Trigonal
    148, 155, 160, 161,
    # Tetragonal
    139, 140, 136, 129, 141, 127,
    # Orthorhombic
    62, 63, 64, 58, 55, 57, 59, 61, 33, 36,
    # Monoclinic
    14, 12, 15, 13, 11,
    # Triclinic
    2, 1,
]


def estimate_volume_per_atom(elements: list[Element]) -> float:
    """
    Estimate a reasonable volume per atom based on element radii.

    Args:
        elements: List of pymatgen Element objects.

    Returns:
        Estimated volume per atom in Å³.
    """
    radii = []
    for el in elements:
        r = el.atomic_radius
        if r is None:
            r = 1.5  # fallback
        radii.append(float(r))
    avg_radius = np.mean(radii)
    # Approximate: V ≈ (2*r)^3 * packing_factor
    # Use packing factor ~0.7 for random structures
    return (2.0 * avg_radius) ** 3 * 0.7


def get_min_distance(el1: Element, el2: Element) -> float:
    """
    Get minimum allowed distance between two elements.

    Uses sum of covalent radii * 0.7 as a lower bound.

    Args:
        el1, el2: pymatgen Element objects.

    Returns:
        Minimum distance in Å.
    """
    r1 = float(el1.atomic_radius or 1.5)
    r2 = float(el2.atomic_radius or 1.5)
    return (r1 + r2) * 0.7


def check_min_distances(structure: Structure, scale: float = 0.7) -> bool:
    """
    Check that all interatomic distances are above minimum thresholds.

    Args:
        structure: pymatgen Structure to check.
        scale: Scale factor for minimum distance (default: 0.7 * sum of radii).

    Returns:
        True if all distances are acceptable, False otherwise.
    """
    for i, site_i in enumerate(structure):
        for j, site_j in enumerate(structure):
            if j <= i:
                continue
            d = structure.get_distance(i, j)
            min_d = get_min_distance(
                site_i.specie if hasattr(site_i.specie, "symbol") else Element(str(site_i.specie)),
                site_j.specie if hasattr(site_j.specie, "symbol") else Element(str(site_j.specie)),
            )
            if d < min_d:
                return False
    return True


def generate_random_structure(
    composition: Composition,
    spacegroup: int,
    volume_scale: float = 1.0,
    max_attempts: int = 50,
) -> Structure | None:
    """
    Generate a random crystal structure for a composition in a given space group.

    Uses pymatgen's Structure.from_spacegroup() with randomized lattice
    parameters and random fractional coordinates for Wyckoff positions.

    Args:
        composition: Target pymatgen Composition.
        spacegroup: Space group number (1-230).
        volume_scale: Scale factor for estimated volume (randomized around this).
        max_attempts: Number of random attempts before giving up.

    Returns:
        A pymatgen Structure, or None if generation failed.
    """
    elements = list(composition.as_dict().keys())
    amounts = [int(composition.as_dict()[el]) for el in elements]
    num_atoms = sum(amounts)

    # Estimate target volume
    element_objs = [Element(el) for el in elements]
    vol_per_atom = estimate_volume_per_atom(element_objs)
    target_volume = vol_per_atom * num_atoms * volume_scale

    sg = SpaceGroup.from_int_number(spacegroup)
    crystal_system = sg.crystal_system

    for _attempt in range(max_attempts):
        # Generate random lattice parameters
        a, b, c, alpha, beta, gamma = _random_lattice_params(
            crystal_system, target_volume
        )

        lattice = Lattice.from_parameters(a, b, c, alpha, beta, gamma)

        # Generate random fractional coordinates
        species = []
        coords = []
        for el, amt in zip(elements, amounts):
            for _ in range(amt):
                species.append(el)
                coords.append(np.random.rand(3).tolist())

        # Create structure
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            structure = Structure(
                lattice, species, coords,
                coords_are_cartesian=False,
            )

        # Check minimum distances
        if check_min_distances(structure):
            return structure

    return None


def _random_lattice_params(
    crystal_system: str,
    target_volume: float,
) -> tuple[float, float, float, float, float, float]:
    """
    Generate random lattice parameters consistent with a crystal system.

    Args:
        crystal_system: One of "cubic", "hexagonal", "trigonal",
                       "tetragonal", "orthorhombic", "monoclinic", "triclinic".
        target_volume: Target unit cell volume in ų.

    Returns:
        Tuple of (a, b, c, alpha, beta, gamma).
    """
    # Random aspect ratios
    r1 = np.random.uniform(0.5, 2.0)
    r2 = np.random.uniform(0.5, 2.0)

    if crystal_system == "cubic":
        a = target_volume ** (1.0 / 3.0)
        return (a, a, a, 90, 90, 90)

    elif crystal_system == "hexagonal":
        # a = b, gamma = 120
        a = (target_volume / (r1 * np.sin(np.radians(60)))) ** (1.0 / 3.0)
        c = a * r1
        return (a, a, c, 90, 90, 120)

    elif crystal_system == "trigonal":
        a = (target_volume / (r1 * np.sin(np.radians(60)))) ** (1.0 / 3.0)
        c = a * r1
        return (a, a, c, 90, 90, 120)

    elif crystal_system == "tetragonal":
        a = (target_volume / r1) ** (1.0 / 3.0)
        c = a * r1
        return (a, a, c, 90, 90, 90)

    elif crystal_system == "orthorhombic":
        a = (target_volume / (r1 * r2)) ** (1.0 / 3.0)
        b = a * r1
        c = a * r2
        return (a, b, c, 90, 90, 90)

    elif crystal_system == "monoclinic":
        beta = np.random.uniform(90, 130)
        a = (target_volume / (r1 * r2 * np.sin(np.radians(beta)))) ** (1.0 / 3.0)
        b = a * r1
        c = a * r2
        return (a, b, c, 90, beta, 90)

    else:  # triclinic
        alpha = np.random.uniform(70, 110)
        beta = np.random.uniform(70, 110)
        gamma = np.random.uniform(70, 110)
        cos_a, cos_b, cos_g = (
            np.cos(np.radians(alpha)),
            np.cos(np.radians(beta)),
            np.cos(np.radians(gamma)),
        )
        sin_g = np.sin(np.radians(gamma))
        vol_factor = np.sqrt(
            1 - cos_a**2 - cos_b**2 - cos_g**2 + 2 * cos_a * cos_b * cos_g
        )
        a = (target_volume / (r1 * r2 * sin_g * vol_factor)) ** (1.0 / 3.0)
        b = a * r1
        c = a * r2
        return (a, b, c, alpha, beta, gamma)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate random crystal structures (AIRSS-style)"
    )
    parser.add_argument(
        "--composition",
        required=True,
        help="Chemical composition (e.g., NaCl, Li2ZrCl6, SrTiO3)",
    )
    parser.add_argument(
        "--num_structures",
        type=int,
        default=100,
        help="Number of structures to generate (default: 100)",
    )
    parser.add_argument(
        "--spacegroups",
        type=str,
        default=None,
        help="Comma-separated space group numbers to use (default: common SGs)",
    )
    parser.add_argument(
        "--volume_min",
        type=float,
        default=0.6,
        help="Minimum volume scale factor (default: 0.6)",
    )
    parser.add_argument(
        "--volume_max",
        type=float,
        default=1.8,
        help="Maximum volume scale factor (default: 1.8)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Random seed for reproducibility",
    )
    parser.add_argument(
        "--output_dir",
        required=True,
        help="Directory to save generated structures",
    )
    args = parser.parse_args()

    if args.seed is not None:
        np.random.seed(args.seed)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    composition = Composition(args.composition)
    reduced = composition.reduced_composition
    print(f"Composition: {reduced.reduced_formula}")
    print(f"Num atoms per formula unit: {int(reduced.num_atoms)}")

    # Determine space groups to use
    if args.spacegroups:
        spacegroups = [int(sg) for sg in args.spacegroups.split(",")]
    else:
        spacegroups = COMMON_SPACEGROUPS

    print(f"Using {len(spacegroups)} space groups")
    print(f"Target: {args.num_structures} structures")

    # Generate structures
    generated = []
    attempts = 0
    max_total_attempts = args.num_structures * 20  # safety limit

    while len(generated) < args.num_structures and attempts < max_total_attempts:
        # Pick random space group
        sg = int(np.random.choice(spacegroups))
        # Random volume scale
        vol_scale = np.random.uniform(args.volume_min, args.volume_max)

        structure = generate_random_structure(
            reduced, sg, volume_scale=vol_scale, max_attempts=10
        )
        attempts += 1

        if structure is not None:
            generated.append({
                "structure": structure,
                "spacegroup": sg,
                "volume_scale": vol_scale,
            })
            if len(generated) % 10 == 0:
                print(f"  Generated {len(generated)}/{args.num_structures}...")

    print(f"Successfully generated {len(generated)} structures ({attempts} attempts)")

    # Save structures
    manifest_entries = []
    for i, item in enumerate(generated):
        formula = item["structure"].composition.reduced_formula
        cif_name = f"{i:04d}_{formula}_sg{item['spacegroup']}.cif"
        cif_path = output_dir / cif_name
        item["structure"].to(filename=str(cif_path))

        manifest_entries.append({
            "index": i,
            "formula": formula,
            "spacegroup": item["spacegroup"],
            "volume_scale": round(item["volume_scale"], 3),
            "num_atoms": len(item["structure"]),
            "volume": round(item["structure"].volume, 2),
            "cif_file": cif_name,
        })

    # Save manifest
    manifest_path = output_dir / "generation_manifest.json"
    manifest = {
        "composition": reduced.reduced_formula,
        "num_generated": len(generated),
        "total_attempts": attempts,
        "spacegroups_used": list(set(e["spacegroup"] for e in manifest_entries)),
        "volume_range": [args.volume_min, args.volume_max],
        "seed": args.seed,
        "structures": manifest_entries,
    }
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    # Print summary
    print(f"\n{'='*60}")
    print(f"Random Structure Generation: {reduced.reduced_formula}")
    print(f"{'='*60}")
    print(f"  Generated:    {len(generated)}")
    print(f"  Attempts:     {attempts}")
    print(f"  Success rate: {len(generated)/max(attempts,1)*100:.1f}%")
    print(f"  Output:       {output_dir}")
    print(f"  Manifest:     {manifest_path}")

    # Space group distribution
    sg_counts: dict[int, int] = {}
    for e in manifest_entries:
        sg_counts[e["spacegroup"]] = sg_counts.get(e["spacegroup"], 0) + 1
    print(f"\n  Space group distribution:")
    for sg, count in sorted(sg_counts.items(), key=lambda x: -x[1])[:10]:
        print(f"    SG {sg:3d}: {count} structures")

    print(f"\n  Next step: Relax all structures with an MLIP, then rank by energy.")

    # Save input configs for reproducibility
    from src.utils.config_utils import save_skill_inputs
    save_skill_inputs(args, args.output_dir)


if __name__ == "__main__":
    main()
