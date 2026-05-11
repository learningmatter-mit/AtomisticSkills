"""
Generate crystal structures from a JSON file of symmetry specifications using DiffCSP++.

Each entry in the JSON file specifies a space group, Wyckoff positions, and atom types.
This corresponds to `sample.py --json_file` in the official DiffCSP++ repository.

Usage:
    python .agents/skills/ml-generative-diffcsp/scripts/batch_generate.py \\
        --json_file example.json \\
        --model mp_csp \\
        --output_dir outputs

JSON format:
    [
        {
            "spacegroup_number": 58,
            "wyckoff_letters": ["2a", "2d", "4g"],
            "atom_types": ["Mn", "Li", "O"]
        },
        {
            "spacegroup_number": 194,
            "wyckoff_letters": "abff",
            "atom_types": ["Tm", "Tm", "Ni", "As"]
        }
    ]

Requirements:
    - Conda environment: diffcsp-agent
    - Required packages: torch, pyxtal, pymatgen, hydra-core
"""

import argparse
import json
import os
import sys
from pathlib import Path

# Add project root to path
project_root = str(Path(__file__).resolve().parents[4])
if project_root not in sys.path:
    sys.path.insert(0, project_root)
os.environ.setdefault("PROJECT_ROOT", "/home/bdeng/projects/DiffCSP-PP")


def main(args: argparse.Namespace) -> None:
    """Run batch structure generation from JSON file.

    Args:
        args: Parsed CLI arguments.
    """
    from src.utils.mlips.diffcsp.diffcsp_wrapper import DiffCSPWrapper

    # Validate JSON file
    with open(args.json_file, "r") as f:
        json_specs = json.load(f)
    print(f"Loaded {len(json_specs)} specifications from {args.json_file}")

    # Load model
    wrapper = DiffCSPWrapper(model_name=args.model, device=args.device)

    # Generate
    result = wrapper.generate_from_json(
        json_specs=json_specs,
        step_lr=args.step_lr,
        batch_size=args.batch_size,
        output_dir=args.output_dir,
    )

    print(f"\nGenerated {result['num_generated']} structures")
    print(f"Output directory: {result['output_dir']}")
    print(f"Metadata: {result['metadata_path']}")
    for p in result["structures"]:
        print(f"  {p}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Batch generate crystal structures from JSON symmetry specs using DiffCSP++"
    )
    parser.add_argument(
        "--json_file", required=True,
        help="Path to JSON file with symmetry specifications"
    )
    parser.add_argument(
        "--model", default="mp_csp",
        help="Model name: mp_csp, perov_csp, mpts_csp (default: mp_csp)"
    )
    parser.add_argument(
        "--output_dir", default="diffcsp_batch_output",
        help="Output directory for CIF files"
    )
    parser.add_argument(
        "--step_lr", default=1e-5, type=float,
        help="Langevin dynamics step size (default: 1e-5)"
    )
    parser.add_argument(
        "--batch_size", default=128, type=int,
        help="Batch size for parallel generation (default: 128)"
    )
    parser.add_argument(
        "--device", default="auto",
        help="Device: auto, cpu, cuda (default: auto)"
    )
    args = parser.parse_args()
    main(args)

    # Save input configs for reproducibility
    from src.utils.config_utils import save_skill_inputs
    save_skill_inputs(args, args.output_dir)
