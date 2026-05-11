"""
Relax a porous framework (CIF/XYZ) using any supported MLIP backend via AtomisticSkills.

Usage:
    python relax_structure.py --structure path/to/supercell.cif --name MOF-1 \\
        --calculator fairchem --model-name uma-s-1p2 --task-name omol \\
        --fmax 0.05 --steps 500 --output-dir ./relaxed/MOF-1

Requirements:
    - Env: depends on --calculator
        fairchem              -> use 'fairchem-agent' conda env
        mace                  -> use 'mace-agent' conda env
        matgl                 -> use 'matgl-agent' conda env
    - PYTHONPATH must include AtomisticSkills project root so src.utils is importable.
"""

from pathlib import Path
import argparse
import json
import sys

# Add project root so src.utils is importable
_project_root = Path(__file__).resolve().parents[4]
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from ase.io import read, write
from ase.optimize import LBFGS, FIRE
from ase.filters import FrechetCellFilter

from src.utils.mlips.loader import load_wrapper


def select_device(device: str) -> str:
    if device == "auto":
        import torch
        return "cuda" if torch.cuda.is_available() else "cpu"
    return device


def normalize_charge_spin(atoms) -> None:
    info = atoms.info if isinstance(atoms.info, dict) else {}
    if atoms.info is not info:
        atoms.info = info
    try:
        charge = int(info.get("charge", info.get("chg", 0)))
    except Exception:
        charge = 0
    try:
        spin_mult = int(
            info.get("spin_multiplicity", info.get("multiplicity", info.get("spin", 1)))
        )
    except Exception:
        spin_mult = 1
    atoms.info["charge"] = charge
    atoms.info["spin_multiplicity"] = spin_mult
    atoms.info["spin"] = spin_mult


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Relax a framework structure using a generic MLIP calculator.")
    p.add_argument("--structure", type=Path, required=True, help="Input structure (.cif or .xyz)")
    p.add_argument("--name", type=str, required=True, help="Identifier for output files")
    p.add_argument(
        "--calculator",
        type=str,
        required=True,
        choices=["mace", "fairchem", "matgl"],
        help="Backend MLIP calculator to use.",
    )
    p.add_argument("--model-name", type=str, required=True, help="Model name or path to checkpoint")
    p.add_argument(
        "--task-name",
        type=str,
        default=None,
        help="Optional task name for multi-task models (e.g. omol, omat, odac for fairchem UMA)",
    )
    p.add_argument(
        "--optimizer",
        type=str,
        default="LBFGS",
        choices=["LBFGS", "FIRE"],
        help="ASE optimizer to use",
    )
    p.add_argument("--fmax", type=float, default=0.05, help="Force convergence threshold (eV/Å)")
    p.add_argument("--steps", type=int, default=500, help="Maximum optimization steps")
    p.add_argument(
        "--relax-cell",
        action="store_true",
        default=True,
        help="Relax the unit cell (default: True)",
    )
    p.add_argument(
        "--fixed-cell",
        action="store_true",
        default=False,
        help="Fix the unit cell during relaxation (overrides --relax-cell)",
    )
    p.add_argument(
        "--device",
        type=str,
        default="auto",
        choices=["auto", "cuda", "cpu"],
        help="Device to use ('auto' picks CUDA if available)",
    )
    p.add_argument("--output-dir", type=Path, default=None, help="Directory to save relaxed structure and results")
    return p.parse_args()


def main() -> int:
    args = parse_args()

    device = select_device(args.device)
    relax_cell = args.relax_cell and not args.fixed_cell

    # Read structure
    atoms = read(str(args.structure))
    normalize_charge_spin(atoms)
    print(f"Loaded structure: {args.name} ({len(atoms)} atoms) from {args.structure}")

    # Load MLIP
    print(f"Loading {args.calculator} model: {args.model_name} (task={args.task_name}, device={device})")
    wrapper = load_wrapper(
        args.calculator,
        model_name=args.model_name,
        device=device,
        task_name=args.task_name,
    )
    calc = wrapper.create_calculator()
    atoms.calc = calc

    # Initial energy
    e_init = atoms.get_potential_energy()
    print(f"Initial energy: {e_init:.4f} eV")

    # Set up optimizer — optionally relax cell
    if relax_cell:
        opt_atoms = FrechetCellFilter(atoms)
    else:
        opt_atoms = atoms

    if args.optimizer == "LBFGS":
        opt = LBFGS(opt_atoms, logfile="-")
    else:
        opt = FIRE(opt_atoms, logfile="-")

    converged = opt.run(fmax=args.fmax, steps=args.steps)
    e_final = atoms.get_potential_energy()
    print(f"Final energy: {e_final:.4f} eV | Converged: {converged}")

    # Save outputs
    output_dir = args.output_dir or Path(f"./relaxed/{args.name}")
    output_dir.mkdir(parents=True, exist_ok=True)

    cif_path = output_dir / f"{args.name}.relaxed.cif"
    write(str(cif_path), atoms)
    print(f"Relaxed structure saved to: {cif_path}")

    results = {
        "name": args.name,
        "calculator": args.calculator,
        "model_name": args.model_name,
        "task_name": args.task_name,
        "device": device,
        "n_atoms": len(atoms),
        "energy_initial_eV": e_init,
        "energy_final_eV": e_final,
        "converged": bool(converged),
        "optimizer": args.optimizer,
        "fmax": args.fmax,
        "steps": args.steps,
        "relax_cell": relax_cell,
        "relaxed_cif": str(cif_path),
    }
    json_path = output_dir / "relax_results.json"
    with open(json_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"Results saved to: {json_path}")

    # Save input configs for reproducibility
    from src.utils.config_utils import save_skill_inputs
    save_skill_inputs(args, args.output_dir)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
