"""
Build a lattice site network from a crystal structure for lattice KMC.

Extracts all atoms of a specified element as lattice sites and connects
neighbors within a cutoff distance, storing periodic image shifts.

Usage:
    python build_lattice_from_structure.py \
        --structure relaxed.cif \
        --site_element Li \
        --cutoff 3.2 \
        --out lattice.json

Requirements:
    - ase
    - numpy
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from ase.io import read
from ase.neighborlist import neighbor_list


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Build a lattice site network from a structure for lattice KMC."
    )
    ap.add_argument("--structure", required=True, help="Path to input structure (CIF/POSCAR)")
    ap.add_argument(
        "--site_element", required=True,
        help="Element that defines lattice sites (e.g., Li for Li sublattice)"
    )
    ap.add_argument("--cutoff", required=True, type=float, help="Neighbor cutoff in angstrom")
    ap.add_argument("--out", required=True, help="Output JSON path")
    args = ap.parse_args()

    atoms = read(args.structure)
    cell = np.array(atoms.cell.array, dtype=float)
    if np.linalg.det(cell) == 0:
        raise RuntimeError("Cell matrix is singular; need periodic cell for lattice KMC.")

    symbols = np.array(atoms.get_chemical_symbols())
    site_indices = np.where(symbols == args.site_element)[0]
    if len(site_indices) < 2:
        raise ValueError(
            f"Found {len(site_indices)} sites for element={args.site_element}. Need >= 2."
        )

    site_atoms = atoms[site_indices]
    site_atoms.set_cell(atoms.cell)
    site_atoms.set_pbc(atoms.pbc)

    frac = site_atoms.get_scaled_positions(wrap=True)
    i_list, j_list, S_list = neighbor_list("ijS", site_atoms, args.cutoff)

    n_sites = len(site_atoms)
    neighbors: list[list[dict]] = [[] for _ in range(n_sites)]

    for i, j, S in zip(i_list, j_list, S_list):
        if i == j and np.all(S == 0):
            continue
        neighbors[int(i)].append({
            "j": int(j),
            "shift": [int(S[0]), int(S[1]), int(S[2])]
        })

    deg = [len(nb) for nb in neighbors]
    if min(deg) == 0:
        raise RuntimeError(
            "Some sites have zero neighbors at this cutoff. "
            "Increase cutoff or verify sublattice."
        )

    out = {
        "cell_A": cell.tolist(),
        "site_element": args.site_element,
        "site_frac_coords": frac.tolist(),
        "neighbors": neighbors,
        "cutoff_A": float(args.cutoff),
        "source_structure": str(args.structure),
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=4))
    print(f"Wrote lattice with {n_sites} sites to: {out_path}")

    # Save input configs for reproducibility
    from src.utils.config_utils import save_skill_inputs
    save_skill_inputs(args, args.out)


if __name__ == "__main__":
    main()
