"""
Generate crystal structures unconditionally using DiffCSP++ ab initio generation.

Samples structures from the training distribution without composition constraints.
This corresponds to `generation.py` in the official DiffCSP++ repository.

Usage:
    python .agents/skills/ml-generative-diffcsp/scripts/unconditional_generate.py \\
        --model mp_gen \\
        --num_structures 100 \\
        --output_dir outputs

Requirements:
    - Conda environment: diffcsp-agent
    - Required packages: torch, pyxtal, pymatgen, hydra-core
    - A generation model (mp_gen, perov_gen, or carbon_gen)
"""

import argparse
import os
import sys
from pathlib import Path

# Add project root to path
project_root = str(Path(__file__).resolve().parents[4])
if project_root not in sys.path:
    sys.path.insert(0, project_root)
os.environ.setdefault("PROJECT_ROOT", "/home/bdeng/projects/DiffCSP-PP")


def main(args: argparse.Namespace) -> None:
    """Run unconditional structure generation.

    Args:
        args: Parsed CLI arguments.
    """
    from src.utils.mlips.diffcsp.diffcsp_wrapper import DiffCSPWrapper

    # Load model
    wrapper = DiffCSPWrapper(model_name=args.model, device=args.device)

    # Generate
    result = wrapper.generate_unconditional(
        num_structures=args.num_structures,
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
        description="Unconditional crystal structure generation using DiffCSP++"
    )
    parser.add_argument(
        "--model", default="mp_gen",
        help="Generation model: mp_gen, perov_gen, carbon_gen (default: mp_gen)"
    )
    parser.add_argument(
        "--num_structures", default=10, type=int,
        help="Number of structures to generate (default: 10)"
    )
    parser.add_argument(
        "--output_dir", default="diffcsp_gen_output",
        help="Output directory for CIF files"
    )
    parser.add_argument(
        "--step_lr", default=5e-6, type=float,
        help="Langevin dynamics step size (default: 5e-6)"
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
