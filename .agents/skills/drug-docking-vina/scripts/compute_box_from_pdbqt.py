"""
Compute a docking box (center + size) from a reference PDBQT file.

This is intended for cases where you have a reference ligand in the desired binding site
(e.g., a co-crystallized ligand converted to PDBQT in the receptor coordinate frame).

Usage:
    python compute_box_from_pdbqt.py reference_ligand.pdbqt --padding 6.0 --min_size 20.0 --output_json box.json

Requirements:
    - Conda environment: drugdisc-agent
    - No external dependencies
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List, Tuple


def _extract_coords(pdbqt_path: Path) -> List[Tuple[float, float, float]]:
    coords: List[Tuple[float, float, float]] = []
    with open(pdbqt_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("ATOM") or line.startswith("HETATM"):
                try:
                    x = float(line[30:38])
                    y = float(line[38:46])
                    z = float(line[46:54])
                    coords.append((x, y, z))
                except Exception:
                    continue
    if not coords:
        raise ValueError(f"No ATOM/HETATM coordinates parsed from {pdbqt_path}")
    return coords


def compute_box(coords: List[Tuple[float, float, float]], padding: float, min_size: float) -> Dict[str, float]:
    xs = [c[0] for c in coords]
    ys = [c[1] for c in coords]
    zs = [c[2] for c in coords]

    xmin, xmax = min(xs), max(xs)
    ymin, ymax = min(ys), max(ys)
    zmin, zmax = min(zs), max(zs)

    cx = 0.5 * (xmin + xmax)
    cy = 0.5 * (ymin + ymax)
    cz = 0.5 * (zmin + zmax)

    sx = max((xmax - xmin) + 2.0 * padding, min_size)
    sy = max((ymax - ymin) + 2.0 * padding, min_size)
    sz = max((zmax - zmin) + 2.0 * padding, min_size)

    return {
        "center_x": round(cx, 4),
        "center_y": round(cy, 4),
        "center_z": round(cz, 4),
        "size_x": round(sx, 4),
        "size_y": round(sy, 4),
        "size_z": round(sz, 4),
        "padding": padding,
        "min_size": min_size,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute docking box from a reference PDBQT.")
    parser.add_argument("pdbqt", help="Reference PDBQT file (e.g., co-crystal ligand) in receptor coordinates.")
    parser.add_argument("--padding", type=float, default=6.0, help="Padding added to ligand bounds (Angstrom).")
    parser.add_argument("--min_size", type=float, default=20.0, help="Minimum box edge length per axis (Angstrom).")
    parser.add_argument("--output_json", default=None, help="Optional output JSON path. If omitted, prints to stdout.")
    args = parser.parse_args()

    pdbqt_path = Path(args.pdbqt)
    coords = _extract_coords(pdbqt_path)
    box = compute_box(coords, padding=args.padding, min_size=args.min_size)

    if args.output_json:
        out_path = Path(args.output_json)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(box, f, indent=2)
        print(f"Wrote: {out_path}")
    else:
        print(json.dumps(box, indent=2))


if __name__ == "__main__":
    main()
