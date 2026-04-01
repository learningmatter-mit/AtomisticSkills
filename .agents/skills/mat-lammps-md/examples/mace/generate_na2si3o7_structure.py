#!/usr/bin/env python3
"""Generate a simple periodic Na2Si3O7 seed structure for the MACE example."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from ase import Atoms
from ase.io import write


def _build_seed_structure(seed: int = 17) -> Atoms:
    # One Na2Si3O7 formula unit repeated to create a small periodic cell.
    symbols = ["Na", "Na", "Si", "Si", "Si"] + ["O"] * 7
    cell = np.diag([9.0, 9.0, 9.0])
    rng = np.random.default_rng(seed)

    scaled_positions = []
    min_dist = 1.35
    max_attempts = 10000

    for _ in symbols:
        for _attempt in range(max_attempts):
            cand = rng.random(3)
            cart = cand @ cell
            if not scaled_positions:
                scaled_positions.append(cand)
                break

            ok = True
            for prev in scaled_positions:
                prev_cart = prev @ cell
                # Minimum-image distance in orthorhombic cell.
                delta = cart - prev_cart
                delta -= np.rint(delta / np.diag(cell)) * np.diag(cell)
                if np.linalg.norm(delta) < min_dist:
                    ok = False
                    break

            if ok:
                scaled_positions.append(cand)
                break
        else:
            raise RuntimeError("Failed to generate non-overlapping seed structure.")

    atoms = Atoms(symbols=symbols, scaled_positions=scaled_positions, cell=cell, pbc=True)
    atoms = atoms.repeat((2, 2, 2))
    return atoms


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Na2Si3O7 CIF for LAMMPS example.")
    parser.add_argument("--out", default="./na2si3o7_initial.cif", help="Output structure path.")
    parser.add_argument("--seed", type=int, default=17, help="Random seed for reproducibility.")
    args = parser.parse_args()

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    atoms = _build_seed_structure(seed=args.seed)
    write(out_path, atoms)
    print(f"Wrote {out_path} with {len(atoms)} atoms")


if __name__ == "__main__":
    main()
