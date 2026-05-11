"""
Molecular Docking with AutoDock Vina (Python API)

Dock small-molecule ligands into a protein receptor using AutoDock Vina's Python bindings.

Usage (single ligand):
    python run_docking.py \
        --receptor receptor.pdbqt \
        --ligand ligand.pdbqt \
        --center_x 16.0 --center_y 25.0 --center_z 2.0 \
        --size_x 20 --size_y 20 --size_z 20 \
        --output_dir results/

Usage (batch):
    python run_docking.py \
        --receptor receptor.pdbqt \
        --ligand_dir ligands/ \
        --center_x 16.0 --center_y 25.0 --center_z 2.0 \
        --size_x 20 --size_y 20 --size_z 20 \
        --output_dir results/

Requirements:
    - Conda environment: drugdisc-agent
    - Required packages: vina (AutoDock Vina Python bindings), numpy
"""

from __future__ import annotations

import argparse
import json
import platform
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from vina import Vina

try:
    from importlib.metadata import version as pkg_version
except Exception:
    pkg_version = None  # type: ignore


@dataclass
class DockingConfig:
    receptor: str
    flex_receptor: Optional[str]
    scoring: str
    center: List[float]
    box_size: List[float]
    spacing: float
    exhaustiveness: int
    n_poses: int
    energy_range: float
    min_rmsd: float
    max_evals: int
    seed: int
    cpu: int
    verbosity: int
    no_refine: bool


def _vina_version() -> str:
    if pkg_version is None:
        return "unknown"
    try:
        return pkg_version("vina")
    except Exception:
        return "unknown"


def _energy_columns(scoring: str) -> List[str]:
    """
    Column meanings per Vina docs for Vina.energies().

    Vina/Vinardo: [total, inter, intra, torsions, intra best pose]
    AD4: [total, inter, intra, torsions, -intra]
    """
    if scoring.lower() == "ad4":
        return ["total", "inter", "intra", "torsions", "neg_intra"]
    return ["total", "inter", "intra", "torsions", "intra_best_pose"]


def _collect_ligands(single: Optional[str], ligand_dir: Optional[str]) -> List[Path]:
    if single:
        return [Path(single)]
    assert ligand_dir is not None
    files: List[Path] = []
    for pat in ["*.pdbqt", "*.PDBQT"]:
        files.extend(Path(ligand_dir).glob(pat))
    return sorted(set(files))


def _init_vina(cfg: DockingConfig) -> Vina:
    v = Vina(
        sf_name=cfg.scoring,
        cpu=cfg.cpu,
        seed=cfg.seed,
        no_refine=cfg.no_refine,
        verbosity=cfg.verbosity,
    )
    if cfg.flex_receptor:
        v.set_receptor(cfg.receptor, cfg.flex_receptor)
    else:
        v.set_receptor(cfg.receptor)
    return v


def dock_one(
    v: Vina,
    cfg: DockingConfig,
    ligand_path: Path,
    maps_ready: bool,
) -> Tuple[Dict[str, Any], bool]:
    """Dock a single ligand using an initialized Vina object."""
    ligand_name = ligand_path.stem
    result: Dict[str, Any] = {
        "ligand": ligand_name,
        "ligand_file": str(ligand_path),
        "success": False,
    }

    try:
        v.set_ligand_from_file(str(ligand_path))

        if not maps_ready:
            v.compute_vina_maps(center=cfg.center, box_size=cfg.box_size, spacing=cfg.spacing)

        t0 = time.time()
        v.dock(
            exhaustiveness=cfg.exhaustiveness,
            n_poses=cfg.n_poses,
            min_rmsd=cfg.min_rmsd,
            max_evals=cfg.max_evals,
        )
        dt = time.time() - t0

        energies = v.energies(n_poses=cfg.n_poses, energy_range=cfg.energy_range)
        energies = np.asarray(energies, dtype=float)

        cols = _energy_columns(cfg.scoring)
        poses: List[Dict[str, Any]] = []
        for i in range(energies.shape[0]):
            row = energies[i].tolist()
            pose: Dict[str, Any] = {"pose": i + 1}
            for c, val in zip(cols, row):
                pose[c] = round(float(val), 4)
            pose["affinity_kcal_mol"] = pose["total"]
            poses.append(pose)

        best_aff = poses[0]["affinity_kcal_mol"] if poses else None

        result.update(
            {
                "poses": poses,
                "best_affinity_kcal_mol": best_aff,
                "n_poses_returned": len(poses),
                "runtime_s": round(dt, 3),
                "success": True,
            }
        )

        return result, True

    except Exception as exc:
        result["error"] = str(exc)
        return result, False


def main() -> None:
    parser = argparse.ArgumentParser(description="Molecular docking with AutoDock Vina (Python API).")

    parser.add_argument("--receptor", required=True, help="Rigid receptor PDBQT file")
    parser.add_argument("--flex_receptor", default=None, help="Flexible residues PDBQT file (optional)")

    ligand_group = parser.add_mutually_exclusive_group(required=True)
    ligand_group.add_argument("--ligand", help="Single ligand PDBQT file")
    ligand_group.add_argument("--ligand_dir", help="Directory containing ligand PDBQT files")

    parser.add_argument("--center_x", type=float, required=True, help="Box center X (Angstrom)")
    parser.add_argument("--center_y", type=float, required=True, help="Box center Y (Angstrom)")
    parser.add_argument("--center_z", type=float, required=True, help="Box center Z (Angstrom)")

    parser.add_argument("--size_x", type=float, default=20.0, help="Box size X (Angstrom)")
    parser.add_argument("--size_y", type=float, default=20.0, help="Box size Y (Angstrom)")
    parser.add_argument("--size_z", type=float, default=20.0, help="Box size Z (Angstrom)")

    parser.add_argument(
        "--scoring",
        default="vina",
        choices=["vina", "vinardo", "ad4"],
        help="Scoring function (vina, vinardo, ad4)",
    )

    parser.add_argument("--spacing", type=float, default=0.375, help="Grid spacing (Angstrom)")
    parser.add_argument("--exhaustiveness", type=int, default=8, help="Search exhaustiveness")
    parser.add_argument("--n_poses", type=int, default=5, help="Number of poses to generate")
    parser.add_argument("--energy_range", type=float, default=3.0, help="Energy range for retrieving/writing poses")
    parser.add_argument("--min_rmsd", type=float, default=1.0, help="Minimum RMSD between poses (Angstrom)")
    parser.add_argument("--max_evals", type=int, default=0, help="Max evaluations (0 = heuristic default)")

    parser.add_argument("--seed", type=int, default=42, help="Random seed (0 = random)")
    parser.add_argument("--cpu", type=int, default=0, help="CPU threads (0 = all available)")
    parser.add_argument("--verbosity", type=int, default=1, choices=[0, 1, 2], help="Vina verbosity level")
    parser.add_argument("--no_refine", action="store_true", help="Disable explicit receptor refinement steps")

    parser.add_argument("--output_dir", default=".", help="Output directory")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing pose files")

    args = parser.parse_args()

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    receptor = Path(args.receptor)
    if not receptor.exists():
        print(f"ERROR: receptor not found: {receptor}", file=sys.stderr)
        sys.exit(2)

    flex_receptor = Path(args.flex_receptor) if args.flex_receptor else None
    if flex_receptor and not flex_receptor.exists():
        print(f"ERROR: flex receptor not found: {flex_receptor}", file=sys.stderr)
        sys.exit(2)

    ligand_files = _collect_ligands(args.ligand, args.ligand_dir)
    if not ligand_files:
        print("ERROR: No ligand PDBQT files found.", file=sys.stderr)
        sys.exit(2)

    cfg = DockingConfig(
        receptor=str(receptor),
        flex_receptor=str(flex_receptor) if flex_receptor else None,
        scoring=args.scoring,
        center=[args.center_x, args.center_y, args.center_z],
        box_size=[args.size_x, args.size_y, args.size_z],
        spacing=args.spacing,
        exhaustiveness=args.exhaustiveness,
        n_poses=args.n_poses,
        energy_range=args.energy_range,
        min_rmsd=args.min_rmsd,
        max_evals=args.max_evals,
        seed=args.seed,
        cpu=args.cpu,
        verbosity=args.verbosity,
        no_refine=args.no_refine,
    )

    meta: Dict[str, Any] = {
        "vina_python_package_version": _vina_version(),
        "platform": platform.platform(),
        "python": sys.version,
        "config": asdict(cfg),
        "timestamp_unix": int(time.time()),
    }

    print("Receptor:", cfg.receptor)
    if cfg.flex_receptor:
        print("Flex receptor:", cfg.flex_receptor)
    print("Ligands:", len(ligand_files))
    print("Scoring:", cfg.scoring)
    print("Box center:", cfg.center)
    print("Box size:", cfg.box_size)
    print("Exhaustiveness:", cfg.exhaustiveness)
    print("CPU:", cfg.cpu)
    print("=" * 60)

    v = _init_vina(cfg)

    # batch: compute maps once before any ligand is loaded (covers all atom types)
    # single: compute maps after loading ligand (only needed atom types)
    maps_ready = False
    if args.ligand_dir:
        v.compute_vina_maps(center=cfg.center, box_size=cfg.box_size, spacing=cfg.spacing)
        maps_ready = True

    all_results: List[Dict[str, Any]] = []

    for lig_path in ligand_files:
        lig_name = lig_path.stem
        print(f"\nDocking: {lig_name}")

        result, ok = dock_one(v=v, cfg=cfg, ligand_path=lig_path, maps_ready=maps_ready)

        if ok:
            poses_path = out_dir / f"{lig_name}_docked.pdbqt"
            try:
                v.write_poses(
                    str(poses_path),
                    n_poses=cfg.n_poses,
                    energy_range=cfg.energy_range,
                    overwrite=args.overwrite,
                )
                result["poses_file"] = str(poses_path)
            except Exception as exc:
                result["poses_file_error"] = str(exc)

            print(f"  Best affinity: {result.get('best_affinity_kcal_mol')} kcal/mol")
            print(f"  Poses returned: {result.get('n_poses_returned')}")
        else:
            print(f"  FAILED: {result.get('error', 'Unknown error')}", file=sys.stderr)

        all_results.append(result)

    successful = [r for r in all_results if r.get("success")]
    if successful:
        best = min(successful, key=lambda r: float(r["best_affinity_kcal_mol"]))
        print("\n" + "=" * 60)
        print(f"Docking complete: {len(successful)}/{len(all_results)} successful")
        print(f"Best hit: {best['ligand']} ({best['best_affinity_kcal_mol']} kcal/mol)")

    results_path = out_dir / "docking_results.json"
    payload = {"meta": meta, "results": all_results}
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    print(f"\nSaved results to {results_path}")

    # Save input configs for reproducibility
    from src.utils.config_utils import save_skill_inputs
    save_skill_inputs(args, args.output_dir)


if __name__ == "__main__":
    main()
