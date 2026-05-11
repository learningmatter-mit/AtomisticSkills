"""
Run Widom insertion with any supported MLIP (MACE, FairChem, MatGL) to compute 
Henry coefficient and heat of adsorption.

Usage:
    python run_widom.py --structure path/to/relaxed.cif --name MYCOF \\
        --calculator fairchem --model-name uma-s-1p1.pt --task-name omol \\
        --gas CO2 --temperature 298 --output-dir ./out

Requirements:
    - Conda environment: Varies based on `--calculator` (e.g. fairchem-agent, mace-agent, matgl-agent)
    - Required packages: ase, torch, pydantic, pymatgen, tqdm, plus the MLIP package
"""

from pathlib import Path
import argparse
import sys

# Add project root so src.utils and same-dir helpers are importable
_project_root = Path(__file__).resolve().parents[4]
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from src.utils.mlips.loader import load_wrapper
from src.utils.structure_utils import normalize_charge_spin
from widom_common import (
    add_common_widom_args,
    read_structure,
    run_widom_job,
    select_device,
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run Widom insertion with a generic MLIP calculator.")
    add_common_widom_args(p)
    p.add_argument(
        "--calculator",
        type=str,
        required=True,
        choices=["mace", "fairchem", "matgl"],
        help="Backend MLIP calculator to use."
    )
    p.add_argument("--model-name", type=str, required=True, help="Name or path of the model checkpoint")
    p.add_argument(
        "--task-name",
        type=str,
        default=None,
        help="Optional task name required by some calculators (e.g. omol for fairchem, omat_pbe for mace)",
    )
    p.add_argument(
        "--device",
        type=str,
        default="auto",
        choices=["auto", "cuda", "cpu"],
        help="'auto' picks CUDA if available",
    )
    p.add_argument("--model-tag", type=str, default=None, help="Model tag for output metadata")
    p.add_argument("--output", "-o", type=Path, default=None, help="Output JSON path (default: output_dir/widom_results.json)")
    return p.parse_args()


def main() -> int:
    args = parse_args()

    device = select_device(args.device)
    atoms = read_structure(args.structure)
    normalize_charge_spin(atoms, args.task_name)

    model_tag = args.model_tag or f"{args.calculator}_{args.model_name}"
    
    # Load the MLIP calculator
    wrapper = load_wrapper(
        args.calculator,
        model_name=args.model_name,
        device=device,
        task_name=args.task_name,
    )
    calc = wrapper.create_calculator()

    output_path = args.output
    if output_path is None:
        output_path = args.output_dir / "widom_results.json"

    run_widom_job(
        calculator=calc,
        structure=atoms,
        gas=args.gas,
        temperature=args.temperature,
        model_outputs_interaction_energy=False,
        num_insertions=args.num_insertions,
        optimize_structures=args.optimize_structures,
        cutoff_distance=args.cutoff_distance,
        cutoff_to_com=args.cutoff_to_com,
        min_interplanar_distance=args.min_interplanar_distance,
        random_seed=getattr(args, "random_seed", 42),
        min_interaction_energy=args.min_interaction_energy,
        output_path=output_path,
        name=args.name,
        model_tag=model_tag,
        extra_config={
            "calculator": args.calculator,
            "model_name": args.model_name,
            "device": device,
            "task_name": args.task_name,
        },
    )

    # Save input configs for reproducibility
    from src.utils.config_utils import save_skill_inputs
    save_skill_inputs(args, args.output_dir)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
