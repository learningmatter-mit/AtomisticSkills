#!/usr/bin/env python3
"""
Optimize a transition-state guess with Sella and validate first-order saddle character.

This script is limited to non-periodic molecular systems and supports
MACE and FAIRChem backends via the project's load_wrapper utility.
"""

import argparse
import inspect
import json
import logging
import os
import sys
import tempfile
import shutil
from typing import Any, Dict, List

import numpy as np

# Add project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../"))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.utils.mlips.loader import load_wrapper


logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("TS-Sella")


def _select_supported_kwargs(callable_obj: Any, candidates: Dict[str, Any]) -> Dict[str, Any]:
    """Filter kwargs to only those supported by callable_obj signature."""
    sig = inspect.signature(callable_obj)
    accepts_var_kwargs = any(
        param.kind == inspect.Parameter.VAR_KEYWORD for param in sig.parameters.values()
    )
    supported = {}
    for key, value in candidates.items():
        if value is None:
            continue
        if accepts_var_kwargs or key in sig.parameters:
            supported[key] = value
    return supported


def _signed_frequencies_cm1(frequencies: List[complex]) -> List[float]:
    """Convert ASE complex frequencies to signed real values in cm^-1."""
    signed = []
    for freq in frequencies:
        real_part = float(np.real(freq))
        imag_part = float(np.imag(freq))
        if abs(imag_part) > 1e-8:
            signed.append(-abs(imag_part))
        else:
            signed.append(real_part)
    return signed


def _to_relpath(path_str: str) -> str:
    """Return path relative to current working directory when possible."""
    try:
        return os.path.relpath(os.path.abspath(path_str), os.getcwd())
    except Exception:
        return path_str


def run_ts_optimization(args: argparse.Namespace) -> Dict[str, Any]:
    """Execute TS optimization + vibrational validation."""
    from ase.io import read, write
    from ase.optimize import FIRE
    from ase.vibrations import Vibrations
    from sella import Sella

    os.makedirs(args.output_dir, exist_ok=True)

    atoms = read(args.ts_guess)
    atoms.pbc = False

    wrapper = load_wrapper(
        args.model_type,
        model_name=args.model_name,
        device=args.device,
        task_name=args.task_name,
    )
    atoms.calc = wrapper.create_calculator()

    traj_path = os.path.join(args.output_dir, "ts_opt.traj")
    log_path = os.path.join(args.output_dir, "ts_opt.log")

    # Sella API differs slightly across versions; pick only supported kwargs.
    sella_ctor_kwargs = _select_supported_kwargs(
        Sella.__init__,
        {
            "order": 1,
            "trajectory": traj_path,
            "logfile": log_path,
        },
    )
    optimizer = Sella(atoms, **sella_ctor_kwargs)

    run_kwargs = _select_supported_kwargs(
        optimizer.run,
        {
            "fmax": args.fmax,
            "steps": args.steps,
        },
    )
    optimizer.run(**run_kwargs)

    # Fallback max-force check (works even if run() does not return convergence status).
    max_force = float(np.linalg.norm(atoms.get_forces(), axis=1).max())
    converged = max_force <= args.fmax
    nsteps = int(getattr(optimizer, "nsteps", -1))

    ts_xyz_path = os.path.join(args.output_dir, "ts_optimized.xyz")
    write(ts_xyz_path, atoms)

    temp_vib_dir = None
    if args.keep_vib_cache:
        vib_prefix = os.path.join(args.output_dir, "vib")
    else:
        temp_vib_dir = tempfile.mkdtemp(prefix="ts_vib_", dir="/tmp")
        vib_prefix = os.path.join(temp_vib_dir, "vib")

    vib = Vibrations(atoms, delta=args.vib_delta, nfree=args.vib_nfree, name=vib_prefix)
    vib.clean()
    vib.run()

    frequencies = vib.get_frequencies()
    signed_freqs = _signed_frequencies_cm1(frequencies)

    imag_modes = [
        {"index": i, "frequency_cm1": float(freq)}
        for i, freq in enumerate(signed_freqs)
        if freq < args.imag_cutoff_cm1
    ]

    n_imag_below_cutoff = len(imag_modes)
    is_first_order_saddle = n_imag_below_cutoff == 1

    results = {
        "ts_guess": _to_relpath(args.ts_guess),
        "output_dir": _to_relpath(args.output_dir),
        "model_type": args.model_type,
        "model_name": wrapper.model_name,
        "task_name": args.task_name,
        "device": args.device,
        "fmax": args.fmax,
        "steps": args.steps,
        "vib_delta": args.vib_delta,
        "vib_nfree": args.vib_nfree,
        "imag_cutoff_cm1": args.imag_cutoff_cm1,
        "sella_converged": bool(converged),
        "optimization_steps": nsteps,
        "max_force_eV_per_A": max_force,
        "all_frequencies_cm1": [float(f) for f in signed_freqs],
        "imaginary_modes": imag_modes,
        "n_imag_below_cutoff": n_imag_below_cutoff,
        "is_first_order_saddle": bool(is_first_order_saddle),
        "keep_vib_cache": bool(args.keep_vib_cache),
        "vib_cache_dir": _to_relpath(os.path.dirname(vib_prefix)) if args.keep_vib_cache else None,
        "optimized_ts_file": os.path.basename(ts_xyz_path),
        "trajectory_file": os.path.basename(traj_path),
    }

    json_path = os.path.join(args.output_dir, "ts_optimization_results.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    if temp_vib_dir is not None:
        shutil.rmtree(temp_vib_dir, ignore_errors=True)

    logger.info("TS optimization complete")
    logger.info("Converged: %s (max|F|=%.6f eV/A)", converged, max_force)
    logger.info("Imaginary modes below %.1f cm^-1: %d", args.imag_cutoff_cm1, n_imag_below_cutoff)
    logger.info("First-order saddle: %s", is_first_order_saddle)
    logger.info("Results written to %s", json_path)

    return results


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Optimize a TS guess with Sella and validate with vibrational analysis.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--ts_guess", required=True, help="Path to TS guess structure file")
    parser.add_argument("--model_type", required=True, choices=["mace", "fairchem"], help="MLIP backend")
    parser.add_argument("--model_name", default=None, help="Specific model name/checkpoint")
    parser.add_argument("--task_name", default=None, help="Task/head name (e.g., omol)")
    parser.add_argument("--device", default="auto", help="Device: cpu/cuda/auto")
    parser.add_argument("--fmax", type=float, default=0.02, help="Force convergence criterion (eV/A)")
    parser.add_argument("--steps", type=int, default=500, help="Maximum optimization steps")
    parser.add_argument("--vib_delta", type=float, default=0.01, help="Vibration finite displacement (A)")
    parser.add_argument("--vib_nfree", type=int, default=2, choices=[2, 4], help="Number of finite displacements")
    parser.add_argument(
        "--keep_vib_cache",
        action="store_true",
        default=False,
        help="Keep ASE vibration cache files under output_dir/vib",
    )
    parser.add_argument("--imag_cutoff_cm1", type=float, default=-50.0, help="Imaginary mode cutoff in cm^-1")
    parser.add_argument("--output_dir", required=True, help="Directory for outputs")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    run_ts_optimization(args)


if __name__ == "__main__":
    main()
