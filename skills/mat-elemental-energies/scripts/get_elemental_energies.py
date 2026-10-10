"""
Retrieve elemental energies from the library for a given list of elements and a checkpoint.

Usage:
    python get_elemental_energies.py --elements H Li Fe --checkpoint MACE-MP-medium
    python get_elemental_energies.py --elements Li O --checkpoint MACE-MP-medium --output refs/energies.json

Requirements:
    - Environment: cpu (run with: venv/run cpu python ...)
    - Required packages: none beyond the standard library (PyYAML for input_configs.yaml)
"""

import argparse
import json
import os
import sys

# The library ships next to this script, so resolve it independently of the working directory.
DEFAULT_RESOURCES_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "resources"
)


def resolve_library_path(checkpoint: str, resources_dir: str) -> str:
    """
    Locate the library file for a checkpoint, matching the name case-insensitively.

    Args:
        checkpoint: MLIP checkpoint name (e.g. "MACE-MP-medium").
        resources_dir: Directory containing ``<checkpoint>_energies.json`` files.

    Returns:
        Path to the library file, or the exact-case path if no file matches.
    """
    exact = os.path.join(resources_dir, f"{checkpoint}_energies.json")
    if os.path.exists(exact) or not os.path.isdir(resources_dir):
        return exact
    target = f"{checkpoint}_energies.json".lower()
    for fname in sorted(os.listdir(resources_dir)):
        if fname.lower() == target:
            return os.path.join(resources_dir, fname)
    return exact


def get_elemental_energies(
    elements: list[str], checkpoint: str, resources_dir: str = DEFAULT_RESOURCES_DIR
) -> dict[str, float] | None:
    """
    Retrieve energies (eV/atom) for a list of elements from the library.

    Args:
        elements: Element symbols (e.g. ["Li", "Fe", "O"]).
        checkpoint: MLIP checkpoint name; matched case-insensitively.
        resources_dir: Directory containing the library files.

    Returns:
        Mapping of element symbol to energy per atom in eV, or None if the
        checkpoint has no library file.
    """
    library_path = resolve_library_path(checkpoint, resources_dir)

    if not os.path.exists(library_path):
        available = []
        if os.path.isdir(resources_dir):
            available = sorted(
                f[: -len("_energies.json")]
                for f in os.listdir(resources_dir)
                if f.endswith("_energies.json")
            )
        print(
            f"Error: Library file not found for checkpoint '{checkpoint}' at {library_path}"
        )
        if available:
            print(f"Available checkpoints: {', '.join(available)}")
        return None

    with open(library_path, "r") as f:
        library = json.load(f)

    results = {}
    missing = []

    for element in elements:
        if element in library:
            results[element] = library[element]
        else:
            missing.append(element)

    if missing:
        print(f"Warning: Energies not found for elements: {', '.join(missing)}")

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Get elemental energies from the library."
    )
    parser.add_argument("--elements", nargs="+", required=True, help="List of elements")
    parser.add_argument(
        "--checkpoint",
        required=True,
        help="MLIP checkpoint name (case-insensitive), e.g. MACE-MP-medium",
    )
    parser.add_argument(
        "--resources_dir",
        default=None,
        help="Directory containing library files (default: the skill's resources/)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Optional JSON file to write the energies to; input_configs.yaml is saved next to it",
    )
    args = parser.parse_args()

    resources_dir = args.resources_dir or DEFAULT_RESOURCES_DIR
    results = get_elemental_energies(args.elements, args.checkpoint, resources_dir)
    if results is None:
        sys.exit(1)

    print(json.dumps(results, indent=2))

    if args.output:
        out_dir = os.path.dirname(os.path.abspath(args.output))
        os.makedirs(out_dir, exist_ok=True)
        with open(args.output, "w") as f:
            json.dump(results, f, indent=2)

        # Save input configs for reproducibility next to the results, never into the library.
        from src.utils.config_utils import save_skill_inputs

        save_skill_inputs(args, out_dir)


if __name__ == "__main__":
    main()
