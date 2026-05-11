"""
Render top-N detected pockets over a protein structure using PyMOL.

Loads the protein, draws each pocket center as a labeled sphere, colors the
lining residues, and ray-traces a PNG. Reads the JSON written by
detect_pockets.py.

Usage:
    python visualize_pockets.py \
        --protein protein.pdb \
        --pockets pockets.json \
        --top_n 3 \
        --output pockets_vis.png

Requirements:
    - Conda environment: drugdisc-agent (or any env with pymol-open-source)
    - Required packages: pymol-open-source
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pymol
from pymol import cmd


PALETTE = [
    "red", "tv_orange", "yellow", "green", "cyan",
    "blue", "magenta", "deepteal", "wheat", "salmon",
]


def _residue_selection(residues: list[dict], object_name: str = "receptor") -> str:
    """Build a PyMOL selection string for a list of pocket residues.

    Scopes selections to the named object so we never pick up residues from
    other loaded objects (e.g., the pseudoatom center spheres). Includes the
    insertion code in `resi` when present, since PyMOL accepts the standard
    PDB `<resnum><icode>` form.
    """
    parts: list[str] = []
    for res in residues:
        chain = (res.get("chain") or "").strip()
        icode = (res.get("icode") or "").strip()
        resi = f"{res['resnum']}{icode}"
        if chain:
            parts.append(f"({object_name} and chain {chain} and resi {resi})")
        else:
            parts.append(f"({object_name} and resi {resi})")
    return " or ".join(parts) if parts else "none"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Visualize ranked pockets over a protein structure."
    )
    parser.add_argument("--protein", required=True, help="Protein structure file.")
    parser.add_argument("--pockets", required=True, help="JSON from detect_pockets.py.")
    parser.add_argument("--output", required=True, help="Output PNG path.")
    parser.add_argument("--top_n", type=int, default=3, help="Number of pockets to render (default: 3).")
    parser.add_argument("--width", type=int, default=1200, help="Image width (px).")
    parser.add_argument("--height", type=int, default=900, help="Image height (px).")
    args = parser.parse_args()

    with open(args.pockets) as fh:
        data = json.load(fh)
    pockets = data.get("pockets", [])[: args.top_n]
    if not pockets:
        raise SystemExit("No pockets to visualize.")

    pymol.finish_launching(["pymol", "-cq"])
    cmd.load(args.protein, "receptor")
    cmd.remove("resname HOH")
    cmd.hide("everything", "receptor")
    cmd.show("cartoon", "receptor")
    cmd.color("gray70", "receptor")
    cmd.set("cartoon_transparency", 0.3, "receptor")

    union_sel_parts: list[str] = []
    for i, pocket in enumerate(pockets):
        color = PALETTE[i % len(PALETTE)]
        rank = pocket.get("rank", i + 1)
        center = pocket["center"]
        cx, cy, cz = center["x"], center["y"], center["z"]

        # Center sphere
        ps_name = f"p{rank}_center"
        cmd.pseudoatom(ps_name, pos=[cx, cy, cz], label=f" P{rank}")
        cmd.show("spheres", ps_name)
        cmd.set("sphere_scale", 1.2, ps_name)
        cmd.color(color, ps_name)
        cmd.set("label_size", 18, ps_name)
        cmd.set("label_color", "black", ps_name)

        # Lining residues
        residues = pocket.get("residues", [])
        if residues:
            sel = _residue_selection(residues)
            res_obj = f"p{rank}_residues"
            cmd.select(res_obj, sel)
            cmd.show("sticks", f"{res_obj} and not name C+N+O+H")
            cmd.color(color, res_obj)
            union_sel_parts.append(f"({sel})")

    cmd.bg_color("white")
    cmd.set("ray_opaque_background", 1)

    if union_sel_parts:
        cmd.orient(" or ".join(union_sel_parts))
        cmd.zoom(" or ".join(union_sel_parts), 5)
    else:
        cmd.orient("receptor")

    cmd.ray(args.width, args.height)
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cmd.png(str(out_path), dpi=150)
    print(f"Saved: {out_path}")
    cmd.quit()


if __name__ == "__main__":
    main()
