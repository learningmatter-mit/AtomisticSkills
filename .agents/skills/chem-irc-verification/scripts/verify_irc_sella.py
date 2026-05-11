#!/usr/bin/env python3
"""
Verify whether an optimized TS connects to target reactant and product via IRC.

This script is limited to non-periodic molecular systems and supports MACE and
FAIRChem backends via the project's load_wrapper utility.
"""

import argparse
import inspect
import json
import logging
import os
import sys
from typing import Any, Dict, List, Tuple

import numpy as np

# Add project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../"))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.utils.mlips.loader import load_wrapper


logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("IRC-Sella")


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


def _kabsch_rmsd(reference_positions: np.ndarray, candidate_positions: np.ndarray) -> float:
    """Compute Kabsch-aligned RMSD between two coordinate sets."""
    ref = reference_positions - reference_positions.mean(axis=0)
    cand = candidate_positions - candidate_positions.mean(axis=0)

    covariance = cand.T @ ref
    v_mat, _, w_mat = np.linalg.svd(covariance)
    det = np.linalg.det(v_mat @ w_mat)
    if det < 0:
        v_mat[:, -1] *= -1

    rotation = v_mat @ w_mat
    cand_rot = cand @ rotation
    diff = ref - cand_rot
    return float(np.sqrt(np.mean(np.sum(diff * diff, axis=1))))


def _connectivity_edges(atoms: Any, cutoff_scale: float = 1.2) -> List[Tuple[int, int]]:
    """Build undirected connectivity edges using ASE natural cutoffs."""
    from ase.neighborlist import natural_cutoffs, neighbor_list

    cutoffs = natural_cutoffs(atoms, mult=cutoff_scale)
    i_idx, j_idx = neighbor_list("ij", atoms, cutoffs)

    edges = set()
    for i_val, j_val in zip(i_idx, j_idx):
        if i_val == j_val:
            continue
        edge = (int(min(i_val, j_val)), int(max(i_val, j_val)))
        edges.add(edge)

    return sorted(edges)


def _connectivity_match(candidate: Any, target: Any) -> bool:
    """Check formula and connectivity equality."""
    if candidate.get_chemical_formula() != target.get_chemical_formula():
        return False
    if list(candidate.get_chemical_symbols()) != list(target.get_chemical_symbols()):
        return False
    return _connectivity_edges(candidate) == _connectivity_edges(target)


def _endpoint_metrics(endpoint: Any, target: Any, rmsd_threshold: float) -> Dict[str, Any]:
    """Compute endpoint-to-target metrics used for assignment."""
    if len(endpoint) != len(target):
        return {
            "rmsd_angstrom": float("inf"),
            "connectivity_match": False,
            "rmsd_within_threshold": False,
            "pair_pass": False,
        }

    rmsd_value = _kabsch_rmsd(target.get_positions(), endpoint.get_positions())
    conn_ok = _connectivity_match(endpoint, target)
    rmsd_ok = rmsd_value <= rmsd_threshold

    return {
        "rmsd_angstrom": float(rmsd_value),
        "connectivity_match": bool(conn_ok),
        "rmsd_within_threshold": bool(rmsd_ok),
        "pair_pass": bool(conn_ok and rmsd_ok),
    }


def _to_relpath(path_str: str) -> str:
    """Return path relative to current working directory when possible."""
    try:
        return os.path.relpath(os.path.abspath(path_str), os.getcwd())
    except Exception:
        return path_str


def _relax_endpoint(atoms: Any, wrapper: Any, fmax: float, max_steps: int = 500) -> Dict[str, Any]:
    """Optionally relax IRC endpoint before comparison."""
    from ase.optimize import FIRE

    atoms = atoms.copy()
    atoms.pbc = False
    atoms.calc = wrapper.create_calculator()

    optimizer = FIRE(atoms, logfile=None)
    optimizer.run(fmax=fmax, steps=max_steps)
    max_force = float(np.linalg.norm(atoms.get_forces(), axis=1).max())

    return {
        "atoms": atoms,
        "steps": int(getattr(optimizer, "nsteps", -1)),
        "max_force_eV_per_A": max_force,
        "converged": bool(max_force <= fmax),
    }


def _run_irc_direction(
    ts_atoms: Any,
    wrapper: Any,
    direction: str,
    fmax: float,
    steps: int,
    traj_path: str,
    log_path: str,
) -> Dict[str, Any]:
    """Run one IRC direction and return endpoint + metadata."""
    from ase.io import read
    from sella import IRC

    atoms = ts_atoms.copy()
    atoms.pbc = False
    atoms.calc = wrapper.create_calculator()

    irc_ctor_kwargs = _select_supported_kwargs(
        IRC.__init__,
        {
            "trajectory": traj_path,
            "logfile": log_path,
        },
    )
    irc_opt = IRC(atoms, **irc_ctor_kwargs)

    irc_run_kwargs = _select_supported_kwargs(
        irc_opt.run,
        {
            "fmax": fmax,
            "steps": steps,
            "direction": direction if "direction" not in irc_ctor_kwargs else None,
        },
    )
    irc_opt.run(**irc_run_kwargs)

    if os.path.exists(traj_path):
        try:
            endpoint = read(traj_path, index="-1")
        except Exception:
            endpoint = atoms.copy()
    else:
        endpoint = atoms.copy()

    endpoint.pbc = False

    max_force = float(np.linalg.norm(endpoint.get_forces(), axis=1).max())
    return {
        "endpoint": endpoint,
        "converged": bool(max_force <= fmax),
        "optimization_steps": int(getattr(irc_opt, "nsteps", -1)),
        "max_force_eV_per_A": max_force,
        "trajectory_file": os.path.basename(traj_path),
    }


def run_irc_verification(args: argparse.Namespace) -> Dict[str, Any]:
    """Execute IRC in both directions and verify endpoint mapping."""
    from ase.io import read, write

    os.makedirs(args.output_dir, exist_ok=True)

    reactant = read(args.reactant)
    product = read(args.product)
    ts = read(args.ts)

    for atoms in (reactant, product, ts):
        atoms.pbc = False

    wrapper = load_wrapper(
        args.model_type,
        model_name=args.model_name,
        device=args.device,
        task_name=args.task_name,
    )

    forward_meta = _run_irc_direction(
        ts,
        wrapper,
        direction="forward",
        fmax=args.fmax,
        steps=args.steps,
        traj_path=os.path.join(args.output_dir, "irc_forward.traj"),
        log_path=os.path.join(args.output_dir, "irc_forward.log"),
    )

    reverse_meta = _run_irc_direction(
        ts,
        wrapper,
        direction="reverse",
        fmax=args.fmax,
        steps=args.steps,
        traj_path=os.path.join(args.output_dir, "irc_reverse.traj"),
        log_path=os.path.join(args.output_dir, "irc_reverse.log"),
    )

    endpoint_relaxation = {}
    forward_endpoint = forward_meta["endpoint"]
    reverse_endpoint = reverse_meta["endpoint"]

    if args.relax_endpoints:
        relaxed_forward = _relax_endpoint(forward_endpoint, wrapper, fmax=args.endpoint_relax_fmax)
        relaxed_reverse = _relax_endpoint(reverse_endpoint, wrapper, fmax=args.endpoint_relax_fmax)
        forward_endpoint = relaxed_forward["atoms"]
        reverse_endpoint = relaxed_reverse["atoms"]
        endpoint_relaxation = {
            "forward": {
                "steps": relaxed_forward["steps"],
                "max_force_eV_per_A": relaxed_forward["max_force_eV_per_A"],
                "converged": relaxed_forward["converged"],
            },
            "reverse": {
                "steps": relaxed_reverse["steps"],
                "max_force_eV_per_A": relaxed_reverse["max_force_eV_per_A"],
                "converged": relaxed_reverse["converged"],
            },
        }

    forward_ep_path = os.path.join(args.output_dir, "irc_forward_endpoint.xyz")
    reverse_ep_path = os.path.join(args.output_dir, "irc_reverse_endpoint.xyz")
    write(forward_ep_path, forward_endpoint)
    write(reverse_ep_path, reverse_endpoint)

    # Evaluate both possible endpoint assignments.
    candidate_assignments = [
        {
            "endpoint_mapping": {"forward": "reactant", "reverse": "product"},
            "metrics": {
                "forward_to_reactant": _endpoint_metrics(forward_endpoint, reactant, args.rmsd_threshold),
                "reverse_to_product": _endpoint_metrics(reverse_endpoint, product, args.rmsd_threshold),
            },
        },
        {
            "endpoint_mapping": {"forward": "product", "reverse": "reactant"},
            "metrics": {
                "forward_to_product": _endpoint_metrics(forward_endpoint, product, args.rmsd_threshold),
                "reverse_to_reactant": _endpoint_metrics(reverse_endpoint, reactant, args.rmsd_threshold),
            },
        },
    ]

    for assignment in candidate_assignments:
        total_rmsd = sum(v["rmsd_angstrom"] for v in assignment["metrics"].values())
        all_pass = all(v["pair_pass"] for v in assignment["metrics"].values())
        assignment["total_rmsd_angstrom"] = float(total_rmsd)
        assignment["assignment_pass"] = bool(all_pass)

    best_assignment = min(candidate_assignments, key=lambda x: x["total_rmsd_angstrom"])

    verification_passed = bool(best_assignment["assignment_pass"])

    selected_mapping = best_assignment["endpoint_mapping"]
    selected_metrics = best_assignment["metrics"]

    results = {
        "reactant": _to_relpath(args.reactant),
        "product": _to_relpath(args.product),
        "ts": _to_relpath(args.ts),
        "output_dir": _to_relpath(args.output_dir),
        "model_type": args.model_type,
        "model_name": wrapper.model_name,
        "task_name": args.task_name,
        "device": args.device,
        "fmax": args.fmax,
        "steps": args.steps,
        "rmsd_threshold": args.rmsd_threshold,
        "relax_endpoints": bool(args.relax_endpoints),
        "endpoint_relax_fmax": args.endpoint_relax_fmax,
        "irc_runs": {
            "forward": {
                "converged": forward_meta["converged"],
                "optimization_steps": forward_meta["optimization_steps"],
                "max_force_eV_per_A": forward_meta["max_force_eV_per_A"],
                "trajectory_file": forward_meta["trajectory_file"],
                "endpoint_file": os.path.basename(forward_ep_path),
            },
            "reverse": {
                "converged": reverse_meta["converged"],
                "optimization_steps": reverse_meta["optimization_steps"],
                "max_force_eV_per_A": reverse_meta["max_force_eV_per_A"],
                "trajectory_file": reverse_meta["trajectory_file"],
                "endpoint_file": os.path.basename(reverse_ep_path),
            },
        },
        "endpoint_mapping": selected_mapping,
        "selected_metrics": selected_metrics,
        "assignment_candidates": candidate_assignments,
        "endpoint_relaxation": endpoint_relaxation,
        "verification_passed": verification_passed,
    }

    json_path = os.path.join(args.output_dir, "irc_verification_results.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    logger.info("IRC verification complete")
    logger.info("Selected mapping: %s", selected_mapping)
    logger.info("Verification passed: %s", verification_passed)
    logger.info("Results written to %s", json_path)

    return results


def _str_to_bool(raw: str) -> bool:
    value = raw.strip().lower()
    if value in {"1", "true", "yes", "y", "on"}:
        return True
    if value in {"0", "false", "no", "n", "off"}:
        return False
    raise argparse.ArgumentTypeError(f"Invalid boolean value: {raw}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Verify IRC connectivity from TS to reactant/product using Sella.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--reactant", required=True, help="Optimized reactant structure")
    parser.add_argument("--product", required=True, help="Optimized product structure")
    parser.add_argument("--ts", required=True, help="Saddle-point optimized TS structure")
    parser.add_argument("--model_type", required=True, choices=["mace", "fairchem"], help="MLIP backend")
    parser.add_argument("--model_name", default=None, help="Specific model name/checkpoint")
    parser.add_argument("--task_name", default=None, help="Task/head name (e.g., omol)")
    parser.add_argument("--device", default="auto", help="Device: cpu/cuda/auto")
    parser.add_argument("--fmax", type=float, default=0.02, help="IRC force convergence criterion (eV/A)")
    parser.add_argument("--steps", type=int, default=1000, help="Maximum IRC optimization steps")
    parser.add_argument("--rmsd_threshold", type=float, default=0.20, help="RMSD threshold for endpoint match (A)")
    parser.add_argument(
        "--relax_endpoints",
        type=_str_to_bool,
        default=True,
        help="Relax IRC endpoints before matching (true/false)",
    )
    parser.add_argument(
        "--endpoint_relax_fmax",
        type=float,
        default=0.02,
        help="Force tolerance for optional endpoint relaxation (eV/A)",
    )
    parser.add_argument("--output_dir", required=True, help="Directory for outputs")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    run_irc_verification(args)

    # Save input configs for reproducibility
    from src.utils.config_utils import save_skill_inputs
    save_skill_inputs(args, args.output_dir)


if __name__ == "__main__":
    main()
