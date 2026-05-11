"""
Convert a chosen pocket from detect_pockets.py output into a docking-box JSON
compatible with drug-binding-site-definition / drug-docking-vina /
drug-complex-system-builder.

Sizing strategy (most-faithful to least):
    1. If the pocket has a `bounding_box` (fpocket), build the box from
       per-axis min/max plus padding, then enforce per-axis `min_size`.
       Anisotropic pockets keep their shape.
    2. Else if the pocket has a `volume_a3`, compute an equivalent-sphere
       radius and produce a cubic box of edge `2 * (radius + padding)`,
       clamped to `min_size`.
    3. Else fall back to a cubic box of edge `default_size` centered on
       the reported center. Used for P2Rank pockets that report neither
       a bounding box nor a volume.

Usage:
    python pocket_to_box.py \
        --pockets pockets.json \
        --rank 1 \
        --padding 6.0 \
        --min_size 20.0 \
        --output_json binding_site.json

Requirements:
    - Conda environment: drugdisc-agent (stdlib only)
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export a binding-site-definition box JSON from a detected pocket."
    )
    parser.add_argument("--pockets", required=True, help="JSON from detect_pockets.py.")
    parser.add_argument("--rank", type=int, default=1, help="Pocket rank to export (default: 1).")
    parser.add_argument("--padding", type=float, default=6.0,
                        help="Padding (A) added on each side beyond the pocket extent (default: 6.0).")
    parser.add_argument("--min_size", type=float, default=20.0,
                        help="Minimum box edge length (A) per axis (default: 20.0).")
    parser.add_argument(
        "--default_size", type=float, default=22.0,
        help="Cubic box edge (A) used when neither bounding_box nor volume is "
             "available (e.g., P2Rank pockets) (default: 22.0).",
    )
    parser.add_argument("--output_json", required=True, help="Output box JSON.")
    args = parser.parse_args()

    if args.rank <= 0:
        sys.exit("--rank must be positive.")
    if args.padding < 0:
        sys.exit("--padding must be non-negative.")
    if args.min_size <= 0:
        sys.exit("--min_size must be positive.")
    if args.default_size <= 0:
        sys.exit("--default_size must be positive.")

    with open(args.pockets) as fh:
        data = json.load(fh)
    pockets = data.get("pockets", [])
    chosen = next((p for p in pockets if p.get("rank") == args.rank), None)
    if chosen is None:
        sys.exit(f"No pocket with rank={args.rank} in {args.pockets}.")

    bbox = chosen.get("bounding_box")
    volume = chosen.get("volume_a3")

    if bbox and "min" in bbox and "max" in bbox:
        mn = bbox["min"]
        mx = bbox["max"]
        cx = 0.5 * (mn[0] + mx[0])
        cy = 0.5 * (mn[1] + mx[1])
        cz = 0.5 * (mn[2] + mx[2])
        sx = max((mx[0] - mn[0]) + 2.0 * args.padding, args.min_size)
        sy = max((mx[1] - mn[1]) + 2.0 * args.padding, args.min_size)
        sz = max((mx[2] - mn[2]) + 2.0 * args.padding, args.min_size)
        sizing = "bounding_box"
    elif volume and volume > 0:
        center = chosen["center"]
        cx, cy, cz = center["x"], center["y"], center["z"]
        radius = (3.0 * volume / (4.0 * math.pi)) ** (1.0 / 3.0)
        edge = max(2.0 * (radius + args.padding), args.min_size)
        sx = sy = sz = edge
        sizing = "volume_sphere"
    else:
        center = chosen["center"]
        cx, cy, cz = center["x"], center["y"], center["z"]
        sx = sy = sz = max(args.default_size, args.min_size)
        sizing = "default_size"

    box = {
        "center_x": round(cx, 3),
        "center_y": round(cy, 3),
        "center_z": round(cz, 3),
        "size_x": round(sx, 3),
        "size_y": round(sy, 3),
        "size_z": round(sz, 3),
        "padding": args.padding,
        "min_size": args.min_size,
        "default_size": args.default_size,
        "sizing_strategy": sizing,
        "mode": "pocket",
        "source": f"{Path(args.pockets).name}#rank={args.rank}",
        "pocket_id": chosen.get("id"),
        "druggability_score": chosen.get("druggability_score"),
        "backend": data.get("backend"),
    }
    out = Path(args.output_json)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w") as fh:
        json.dump(box, fh, indent=4)
    print(
        f"Wrote {out} (sizing={sizing}, "
        f"size=({sx:.1f}, {sy:.1f}, {sz:.1f}) A)"
    )


if __name__ == "__main__":
    main()
