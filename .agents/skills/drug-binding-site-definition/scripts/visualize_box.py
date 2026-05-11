"""
Render a docking box wireframe over a protein structure using PyMOL.

Loads the protein, highlights the ligand (if present), and draws the
bounding box from a binding_site.json file as a red wireframe overlay.
Saves a ray-traced PNG screenshot.

Usage:
    python visualize_box.py --protein protein.pdb --box binding_site.json --output box_vis.png
    python visualize_box.py --protein protein.pdb --box binding_site.json --ligand_resname MK1 --output box_vis.png

Requirements:
    - Conda environment: drugdisc-agent
    - Required packages: pymol-open-source
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pymol
from pymol import cmd
from pymol.cgo import BEGIN, END, COLOR, LINES, LINEWIDTH, VERTEX


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Visualize a docking box over a protein structure."
    )
    parser.add_argument(
        "--protein",
        required=True,
        help="Protein structure file (PDB, mmCIF).",
    )
    parser.add_argument(
        "--box",
        required=True,
        help="Binding site JSON file (from define_binding_site.py).",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Output PNG file path.",
    )
    parser.add_argument(
        "--ligand_resname",
        default=None,
        help="Residue name of the ligand to highlight (e.g., MK1). Optional.",
    )
    parser.add_argument(
        "--width",
        type=int,
        default=1200,
        help="Image width in pixels (default: 1200).",
    )
    parser.add_argument(
        "--height",
        type=int,
        default=900,
        help="Image height in pixels (default: 900).",
    )
    args = parser.parse_args()

    pymol.finish_launching(["pymol", "-cq"])

    cmd.load(args.protein, "protein")
    cmd.remove("resname HOH")
    cmd.hide("everything", "protein")
    cmd.show("surface", "protein")
    cmd.color("gray80", "protein")
    cmd.set("transparency", 0.3, "protein")

    if args.ligand_resname:
        sel = f"resname {args.ligand_resname}"
        cmd.show("sticks", sel)
        cmd.color("yellow", sel)

    with open(args.box) as f:
        box = json.load(f)

    cx, cy, cz = box["center_x"], box["center_y"], box["center_z"]
    sx, sy, sz = box["size_x"] / 2, box["size_y"] / 2, box["size_z"] / 2

    cmd.pseudoatom("box_center", pos=[cx, cy, cz])
    cmd.show("spheres", "box_center")
    cmd.set("sphere_scale", 0.5, "box_center")
    cmd.color("red", "box_center")

    corners = [
        (cx + dx, cy + dy, cz + dz)
        for dx in (-sx, sx) for dy in (-sy, sy) for dz in (-sz, sz)
    ]
    edges = [
        (0, 1), (2, 3), (4, 5), (6, 7),
        (0, 2), (1, 3), (4, 6), (5, 7),
        (0, 4), (1, 5), (2, 6), (3, 7),
    ]
    obj = [LINEWIDTH, 2.0, COLOR, 1.0, 0.3, 0.3, BEGIN, LINES]
    for i, j in edges:
        obj.extend([VERTEX] + list(corners[i]) + [VERTEX] + list(corners[j]))
    obj.append(END)
    cmd.load_cgo(obj, "docking_box")

    cmd.set("ray_opaque_background", 1)
    cmd.bg_color("white")

    if args.ligand_resname:
        cmd.orient(f"resname {args.ligand_resname}")
        cmd.zoom(f"resname {args.ligand_resname}", 10)
    else:
        cmd.orient("docking_box")
        cmd.zoom("docking_box", 5)

    cmd.ray(args.width, args.height)
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cmd.png(str(out_path), dpi=150)
    print(f"Saved: {out_path}")

    # Save input configs for reproducibility
    from src.utils.config_utils import save_skill_inputs
    save_skill_inputs(args, args.output_dir)
    _params_path.parent.mkdir(parents=True, exist_ok=True)
    _params_path.write_text(json.dumps(_config, indent=2, default=str))
    cmd.quit()


if __name__ == "__main__":
    main()
