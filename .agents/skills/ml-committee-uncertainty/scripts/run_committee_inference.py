"""
Run MACE committee model inference to quantify prediction uncertainty.

Loads N independently trained MACE checkpoints as a committee.  For each
input structure, computes the mean and standard deviation of energies and
forces across committee members.  Structures whose uncertainty exceeds the
specified thresholds are flagged and written to a dedicated sub-directory.

Usage:
    python run_committee_inference.py \
        --structures /path/to/structures.cif \
        --models model1.model model2.model model3.model \
        --output-dir ./uncertainty_results \
        --energy-threshold 10.0 \
        --force-threshold 200.0

Requirements:
    - Conda environment: mace-agent
    - Required packages: mace-torch, ase, numpy, matplotlib
"""

import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import List

import numpy as np

# Add project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../"))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from ase import Atoms
from ase.io import read, write

from src.utils.research_utils import get_current_research_dir

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("CommitteeUQ")


def load_structures(path: str) -> List[Atoms]:
    """Load structures from a file or all structure files in a directory."""
    p = Path(path)
    struct_exts = {".cif", ".xyz", ".extxyz", ".poscar", ".vasp", ".json"}

    if p.is_dir():
        files = sorted(
            f for f in p.iterdir()
            if f.suffix.lower() in struct_exts or f.name == "POSCAR"
        )
        if not files:
            raise FileNotFoundError(f"No structure files found in {path}")
        structures = []
        for f in files:
            loaded = read(str(f), index=":")
            if isinstance(loaded, list):
                for s in loaded:
                    s.info["source_file"] = f.name
                structures.extend(loaded)
            else:
                loaded.info["source_file"] = f.name
                structures.append(loaded)
        return structures
    else:
        loaded = read(str(p), index=":")
        if not isinstance(loaded, list):
            loaded = [loaded]
        for s in loaded:
            s.info["source_file"] = p.name
        return loaded


def build_committee_calculator(model_paths: List[str], device: str, head: str = None):
    """Build a MACE committee calculator from a list of checkpoint paths.

    When MACECalculator receives multiple model_paths it automatically runs
    each model independently and exposes variance outputs via
    calculator.results['energy_var'] and calculator.results['forces_var'].

    Args:
        model_paths: List of MACE checkpoint file paths.
        device: Compute device ("cuda" or "cpu").
        head: Optional model head name for multi-head models (e.g. "omat_pbe" for MACE-MH).
    """
    from mace.calculators import MACECalculator

    for p in model_paths:
        if not Path(p).exists():
            raise FileNotFoundError(f"Model checkpoint not found: {p}")

    kwargs = dict(
        model_paths=model_paths,
        device=device,
        default_dtype="float32",
    )
    if head is not None:
        kwargs["head"] = head

    calc = MACECalculator(**kwargs)
    return calc


def compute_uncertainty(atoms: Atoms, calc) -> dict:
    """Run committee inference on a single structure and return uncertainty metrics."""
    atoms.calc = calc
    energy = atoms.get_potential_energy()
    forces = atoms.get_forces()

    n_atoms = len(atoms)
    energy_per_atom = energy / n_atoms

    # Committee variance is stored in calc.results after get_potential_energy()
    energy_var = calc.results.get("energy_var", 0.0)
    forces_var = calc.results.get("forces_var", np.zeros_like(forces))

    # Convert variance → std, work in meV units
    energy_std_mev = float(np.sqrt(energy_var) * 1000.0 / n_atoms)  # meV/atom
    forces_std_mev = np.sqrt(forces_var) * 1000.0                    # meV/Å, shape (N, 3)
    max_force_std_mev = float(forces_std_mev.max())
    mean_force_std_mev = float(forces_std_mev.mean())

    return {
        "energy_per_atom_eV": round(energy_per_atom, 6),
        "energy_std_meV_per_atom": round(energy_std_mev, 4),
        "max_force_std_meV_A": round(max_force_std_mev, 4),
        "mean_force_std_meV_A": round(mean_force_std_mev, 4),
    }


def plot_uncertainty_distribution(records: list, output_path: str) -> None:
    """Plot histograms of energy and force uncertainty across all structures."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update({"font.size": 14})

    energy_stds = [r["energy_std_meV_per_atom"] for r in records]
    force_stds = [r["max_force_std_meV_A"] for r in records]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4))

    ax1.hist(energy_stds, bins=30, color="#4C72B0", edgecolor="white", linewidth=0.5)
    ax1.set_xlabel("Energy Uncertainty (meV/atom)", fontweight="bold")
    ax1.set_ylabel("Count", fontweight="bold")
    ax1.set_title("Energy Uncertainty Distribution")
    ax1.grid(True, linestyle="--", alpha=0.6)
    ax1.legend(frameon=False)

    ax2.hist(force_stds, bins=30, color="#DD8452", edgecolor="white", linewidth=0.5)
    ax2.set_xlabel("Max Force Uncertainty (meV/Å)", fontweight="bold")
    ax2.set_ylabel("Count", fontweight="bold")
    ax2.set_title("Force Uncertainty Distribution")
    ax2.grid(True, linestyle="--", alpha=0.6)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.savefig(output_path.replace(".png", ".svg"), bbox_inches="tight")
    plt.close()
    logger.info(f"Saved uncertainty distribution plot to {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="MACE committee uncertainty quantification."
    )
    parser.add_argument(
        "--structures",
        required=True,
        help="Path to structure file, directory of structures, or .xyz trajectory.",
    )
    parser.add_argument(
        "--models",
        nargs="+",
        required=True,
        help="Paths to MACE checkpoint files (≥ 3 recommended).",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Output directory. Defaults to <research_dir>/uncertainty.",
    )
    parser.add_argument(
        "--energy-threshold",
        type=float,
        default=10.0,
        help="Flag structures with energy std > this value in meV/atom (default: 10.0).",
    )
    parser.add_argument(
        "--force-threshold",
        type=float,
        default=200.0,
        help="Flag structures with max force std > this value in meV/Å (default: 200.0).",
    )
    parser.add_argument(
        "--device",
        default="cuda",
        choices=["cuda", "cpu"],
        help="Device for inference (default: cuda).",
    )
    parser.add_argument(
        "--head",
        default=None,
        help="Model head name for multi-head MACE models (e.g. 'omat_pbe' for MACE-MH-1). "
             "Required when using MACE-MH foundation models.",
    )
    args = parser.parse_args()

    if len(args.models) < 2:
        parser.error("At least 2 model checkpoints are required for a committee.")

    # Resolve output directory
    if args.output_dir is None:
        research_dir = get_current_research_dir()
        args.output_dir = str(research_dir / "uncertainty")
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    high_unc_dir = output_dir / "high_uncertainty_structures"
    high_unc_dir.mkdir(exist_ok=True)

    logger.info(f"Loading structures from: {args.structures}")
    structures = load_structures(args.structures)
    logger.info(f"Loaded {len(structures)} structures")

    logger.info(f"Building committee calculator from {len(args.models)} models")
    calc = build_committee_calculator(args.models, device=args.device, head=args.head)

    records = []
    n_flagged = 0

    for i, atoms in enumerate(structures):
        source = atoms.info.get("source_file", f"structure_{i}")
        logger.info(f"[{i+1}/{len(structures)}] Processing {source} ({len(atoms)} atoms)")

        metrics = compute_uncertainty(atoms, calc)
        metrics["structure_index"] = i
        metrics["source_file"] = source
        records.append(metrics)

        energy_flagged = metrics["energy_std_meV_per_atom"] > args.energy_threshold
        force_flagged = metrics["max_force_std_meV_A"] > args.force_threshold
        is_flagged = energy_flagged or force_flagged
        metrics["flagged_for_dft"] = is_flagged
        metrics["flag_reason"] = []

        if energy_flagged:
            metrics["flag_reason"].append(
                f"energy_std={metrics['energy_std_meV_per_atom']:.2f} > {args.energy_threshold} meV/atom"
            )
        if force_flagged:
            metrics["flag_reason"].append(
                f"force_std={metrics['max_force_std_meV_A']:.2f} > {args.force_threshold} meV/Å"
            )

        if is_flagged:
            n_flagged += 1
            flag_path = high_unc_dir / f"flagged_{i:04d}_{source}"
            write(str(flag_path), atoms)

        status = "FLAGGED" if is_flagged else "ok"
        logger.info(
            f"  E_std={metrics['energy_std_meV_per_atom']:.2f} meV/atom, "
            f"F_std_max={metrics['max_force_std_meV_A']:.2f} meV/Å  [{status}]"
        )

    # Save summary JSON
    summary_path = output_dir / "uncertainty_summary.json"
    with open(summary_path, "w") as f:
        json.dump(
            {
                "committee_models": args.models,
                "energy_threshold_meV_per_atom": args.energy_threshold,
                "force_threshold_meV_A": args.force_threshold,
                "n_total": len(structures),
                "n_flagged": n_flagged,
                "flagged_fraction": round(n_flagged / len(structures), 4),
                "per_structure": records,
            },
            f,
            indent=2,
        )
    logger.info(f"Saved uncertainty summary to {summary_path}")

    # Plot distributions
    plot_path = str(output_dir / "uncertainty_distribution.png")
    plot_uncertainty_distribution(records, plot_path)

    # Print final summary
    energy_stds = [r["energy_std_meV_per_atom"] for r in records]
    force_stds = [r["max_force_std_meV_A"] for r in records]
    print("\n" + "=" * 60)
    print("COMMITTEE UNCERTAINTY SUMMARY")
    print("=" * 60)
    print(f"  Structures analysed : {len(structures)}")
    print(f"  Committee members   : {len(args.models)}")
    print(f"  Energy std (mean)   : {np.mean(energy_stds):.2f} meV/atom")
    print(f"  Energy std (max)    : {np.max(energy_stds):.2f} meV/atom")
    print(f"  Force  std (mean)   : {np.mean(force_stds):.2f} meV/Å")
    print(f"  Force  std (max)    : {np.max(force_stds):.2f} meV/Å")
    print(f"  Flagged for DFT     : {n_flagged}/{len(structures)} ({100*n_flagged/len(structures):.1f}%)")
    print(f"  Results saved to    : {output_dir}")
    print("=" * 60)

    # Save input configs for reproducibility
    from src.utils.config_utils import save_skill_inputs
    save_skill_inputs(args, args.output_dir)


if __name__ == "__main__":
    main()
