#!/usr/bin/env python3
"""Generate Si supercell defects without pymatgen-analysis-defects (base-agent only)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from pymatgen.core import Structure


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--bulk", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--supercell_size", nargs=3, type=int, default=[3, 3, 3])
    args = p.parse_args()

    bulk = Structure.from_file(args.bulk)
    sc = [[args.supercell_size[0], 0, 0], [0, args.supercell_size[1], 0], [0, 0, args.supercell_size[2]]]
    pristine = bulk.copy()
    pristine.make_supercell(sc)
    args.output.mkdir(parents=True, exist_ok=True)
    pristine.to(filename=str(args.output / "pristine_supercell.cif"))

    # Central Si site for subst / vac (conventional diamond cell)
    si_sites = [i for i, site in enumerate(pristine) if site.specie.symbol == "Si"]
    center_idx = si_sites[len(si_sites) // 2]

    defects = []

    # P@Si
    sub_p = pristine.copy()
    sub_p[center_idx] = "P"
    sub_p.to(filename=str(args.output / "sub_P_0.cif"))
    defects.append({"name": "sub_P_0", "type": "substitution", "dopant": "P"})

    # B@Si
    sub_b = pristine.copy()
    sub_b[center_idx] = "B"
    sub_b.to(filename=str(args.output / "sub_B_0.cif"))
    defects.append({"name": "sub_B_0", "type": "substitution", "dopant": "B"})

    # Vacancy
    vac = pristine.copy()
    del vac[center_idx]
    vac.to(filename=str(args.output / "vac_Si_0.cif"))
    defects.append({"name": "vac_Si_0", "type": "vacancy"})

    # Self-interstitial: offset ~1 Å along a bond direction (Cartesian)
    intst = pristine.copy()
    site = pristine[center_idx]
    new_cart = site.coords + [1.0, 0.0, 0.0]
    intst.append("Si", new_cart, coords_are_cartesian=True)
    intst.to(filename=str(args.output / "int_Si_0.cif"))
    defects.append({"name": "int_Si_0", "type": "interstitial"})

    meta = {
        "bulk_formula": str(bulk.formula),
        "supercell_size": args.supercell_size,
        "pristine_num_atoms": len(pristine),
        "defects": defects,
    }
    with open(args.output / "defect_metadata.json", "w") as f:
        json.dump(meta, f, indent=2)
    print(f"Wrote {len(defects) + 1} structures to {args.output}")


if __name__ == "__main__":
    main()
