"""
Build and relax NEB endpoint structures for H migration in BCC W (T-site → T-site).

Creates a 3x3x3 BCC W supercell (54 W atoms) with a single H interstitial
at a tetrahedral site, then builds the neighboring T-site endpoint.  Both
structures are relaxed with a fixed cell using the specified MACE model so
that the same PES is used for NEB and phonon calculations downstream.

T-site positions in the BCC conventional cell (fractional):
    12 sites per cell, e.g. (0, 1/4, 1/2) and its symmetry equivalents.
Hop: (0, 1/4, 1/2) → (0, 1/2, 1/4), distance = a*sqrt(2)/4 ≈ 1.12 Å.

Usage:
    python prepare_h_migration.py \
        --model_type mace --model_name MACE-OMAT-0-small \
        --output_dir . --fmax 0.01

Requirements:
    pymatgen, ase, numpy (base-agent or mace-agent env)
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from pathlib import Path

import numpy as np
from ase import Atoms
from ase.io import write as ase_write
from ase.optimize import FIRE
from pymatgen.core import Lattice, Structure
from pymatgen.io.ase import AseAtomsAdaptor

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../../"))
if project_root not in sys.path:
    sys.path.insert(0, project_root)


def build_bcc_w_supercell(a: float, nx: int, ny: int, nz: int) -> Structure:
    """Build a BCC W supercell (conventional cell tiled nx x ny x nz)."""
    lattice = Lattice.cubic(a)
    # BCC conventional cell: 2 atoms at (0,0,0) and (0.5,0.5,0.5)
    bcc_cell = Structure(
        lattice,
        ["W", "W"],
        [[0.0, 0.0, 0.0], [0.5, 0.5, 0.5]],
    )
    supercell = bcc_cell.copy()
    supercell.make_supercell([nx, ny, nz])
    return supercell


def add_h_at_tsite(structure: Structure, frac_in_conv: list[float],
                   nx: int, ny: int, nz: int) -> Structure:
    """Insert H at a tetrahedral site given in fractional coords of the conventional cell.

    Converts to supercell fractional coords and appends H.
    """
    s = structure.copy()
    # Convert conventional-cell fractional to supercell fractional
    sup_frac = [frac_in_conv[i] / [nx, ny, nz][i] for i in range(3)]
    s.append("H", sup_frac)
    return s


def relax_structure(atoms: Atoms, calc, fmax: float = 0.01,
                    max_steps: int = 500) -> Atoms:
    """Relax atomic positions with fixed cell."""
    atoms.calc = calc
    opt = FIRE(atoms, logfile="-")
    opt.run(fmax=fmax, steps=max_steps)
    return atoms


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Prepare NEB endpoints for H migration in BCC W (T-site hop)."
    )
    ap.add_argument("--model_type", default="mace", choices=["mace", "fairchem", "matgl"])
    ap.add_argument("--model_name", default="MACE-OMAT-0-small")
    ap.add_argument("--device", default="auto")
    ap.add_argument("--a", type=float, default=3.165, help="W lattice constant (A)")
    ap.add_argument("--supercell", type=int, nargs=3, default=[3, 3, 3],
                    help="Supercell dimensions (nx ny nz)")
    ap.add_argument("--fmax", type=float, default=0.01,
                    help="Force convergence for relaxation (eV/A)")
    ap.add_argument("--output_dir", default=".", help="Output directory")
    args = ap.parse_args()

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    nx, ny, nz = args.supercell
    a = args.a

    # T-site pair: nearest-neighbor hop in the conventional cell
    # Site A: (0, 1/4, 1/2)  Site B: (0, 1/2, 1/4)
    # hop distance = a*sqrt(2)/4
    tsite_A = [0.0, 0.25, 0.5]
    tsite_B = [0.0, 0.5, 0.25]
    hop_dist = a * math.sqrt(2) / 4.0
    print(f"T-site hop: {tsite_A} -> {tsite_B}")
    print(f"Expected hop distance: {hop_dist:.4f} A")

    print(f"\nBuilding {nx}x{ny}x{nz} BCC W supercell (a={a} A)...")
    supercell = build_bcc_w_supercell(a, nx, ny, nz)
    n_w = len(supercell)
    print(f"  {n_w} W atoms")

    struct_A = add_h_at_tsite(supercell, tsite_A, nx, ny, nz)
    struct_B = add_h_at_tsite(supercell, tsite_B, nx, ny, nz)
    print(f"  Structure A: {len(struct_A)} atoms (H at T-site A)")
    print(f"  Structure B: {len(struct_B)} atoms (H at T-site B)")

    # load MLIP
    print(f"\nLoading {args.model_type} model: {args.model_name}...")
    if args.model_type == "mace":
        from src.utils.mlips.mace.mace_wrapper import MACEWrapper
        wrapper = MACEWrapper(model_name=args.model_name, device=args.device)
    elif args.model_type == "fairchem":
        from src.utils.mlips.fairchem.fairchem_wrapper import FAIRCHEMWrapper
        wrapper = FAIRCHEMWrapper(model_name=args.model_name, device=args.device)
    elif args.model_type == "matgl":
        from src.utils.mlips.matgl.matgl_wrapper import MatGLWrapper
        wrapper = MatGLWrapper(model_name=args.model_name, device=args.device)
    wrapper.load()
    calc = wrapper.create_calculator()

    adaptor = AseAtomsAdaptor()

    # relax structure A
    print("\nRelaxing structure A (H at T-site A)...")
    atoms_A = adaptor.get_atoms(struct_A)
    atoms_A = relax_structure(atoms_A, calc, fmax=args.fmax)
    start_path = out_dir / "start_relaxed.cif"
    struct_A_relaxed = adaptor.get_structure(atoms_A)
    struct_A_relaxed.to(str(start_path), "cif")
    print(f"  Wrote: {start_path}")

    # relax structure B (fresh calculator to avoid shared state)
    print("\nRelaxing structure B (H at T-site B)...")
    calc_B = wrapper.create_calculator()
    atoms_B = adaptor.get_atoms(struct_B)
    atoms_B = relax_structure(atoms_B, calc_B, fmax=args.fmax)
    end_path = out_dir / "end_relaxed.cif"
    struct_B_relaxed = adaptor.get_structure(atoms_B)
    struct_B_relaxed.to(str(end_path), "cif")
    print(f"  Wrote: {end_path}")

    # verify H positions after relaxation
    h_pos_A = atoms_A.positions[-1]
    h_pos_B = atoms_B.positions[-1]
    final_dist = np.linalg.norm(h_pos_A - h_pos_B)
    print(f"\nPost-relaxation H-H distance: {final_dist:.4f} A")
    print(f"Expected (ideal): {hop_dist:.4f} A")

    e_A = atoms_A.get_potential_energy()
    e_B = atoms_B.get_potential_energy()
    print(f"Energy A: {e_A:.6f} eV")
    print(f"Energy B: {e_B:.6f} eV")
    print(f"Delta E:  {abs(e_A - e_B):.6f} eV (should be ~0 by symmetry)")

    summary = {
        "system": "H in BCC W (T-site migration)",
        "model_type": args.model_type,
        "model_name": args.model_name,
        "lattice_constant_A": a,
        "supercell": [nx, ny, nz],
        "n_W_atoms": n_w,
        "tsite_A_frac_conv": tsite_A,
        "tsite_B_frac_conv": tsite_B,
        "ideal_hop_distance_A": hop_dist,
        "relaxed_hop_distance_A": float(final_dist),
        "energy_A_eV": float(e_A),
        "energy_B_eV": float(e_B),
        "delta_E_eV": float(abs(e_A - e_B)),
        "fmax_eV_A": args.fmax,
        "start_structure": str(start_path),
        "end_structure": str(end_path),
    }
    summary_path = out_dir / "structure_prep_summary.json"
    summary_path.write_text(json.dumps(summary, indent=4))
    print(f"\nWrote: {summary_path}")


if __name__ == "__main__":
    main()
