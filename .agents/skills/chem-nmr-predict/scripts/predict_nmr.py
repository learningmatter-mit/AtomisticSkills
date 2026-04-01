#!/usr/bin/env python3
"""
Predict 1H NMR spectra from SMILES via NMRdb.org SPINUS + nmrsim QM simulation.

For each compound, produces:
  - <name>.xy         : simulated 1H spectrum (ppm, intensity)
  - <name>_signals.csv : signal table (shift_ppm, multiplicity, J_Hz, nH)

Usage:
    # Env: nmr-agent
    python predict_nmr.py \
        --smiles "OC1CC2CCC1C2" "OC1CC2CCC1C2" \
        --names "borneol" "isoborneol" \
        --output_dir references/

Requirements: rdkit, numpy, requests, nmrsim
"""

import argparse
import csv
import json
import pathlib
import re
import sys

import numpy as np
import requests


# ---------------------------------------------------------------------------
# SMILES -> Molfile conversion (RDKit)
# ---------------------------------------------------------------------------

def smiles_to_molblock(smiles: str) -> str:
    """Convert SMILES to a V2000 molfile block via RDKit."""
    from rdkit import Chem
    from rdkit.Chem import AllChem
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        raise ValueError(f"Invalid SMILES: {smiles}")
    mol = Chem.AddHs(mol)
    AllChem.EmbedMolecule(mol, AllChem.ETKDGv3())
    return Chem.MolToMolBlock(mol)


# ---------------------------------------------------------------------------
# NMRdb.org SPINUS endpoint
# ---------------------------------------------------------------------------

_SPINUS_URL = "https://www.nmrdb.org/service/predictor"


def fetch_spinus(smiles: str) -> list[dict]:
    """
    Fetch 1H NMR prediction from NMRdb.org SPINUS endpoint.

    Returns list of dicts, one per hydrogen atom:
        {
            "atom_idx": int,
            "parent_heavy_atom": int,
            "shift_ppm": float,
            "couplings": [{"atom_idx": int, "distance": int, "J_Hz": float}, ...]
        }
    """
    molblock = smiles_to_molblock(smiles)

    r = requests.post(
        _SPINUS_URL,
        files={"molfile": ("mol.mol", molblock, "chemical/x-mdl-molfile")},
        timeout=30,
    )
    r.raise_for_status()

    atoms = []
    for line in r.text.strip().splitlines():
        tokens = line.split("\t")
        if len(tokens) < 4:
            continue
        atom_idx = int(tokens[0])
        parent = int(tokens[1])
        shift = float(tokens[2])
        n_couplings = int(tokens[3])
        couplings = []
        for i in range(n_couplings):
            base = 4 + i * 3
            if base + 2 < len(tokens):
                couplings.append({
                    "atom_idx": int(tokens[base]),
                    "distance": int(tokens[base + 1]),
                    "J_Hz": float(tokens[base + 2]),
                })
        atoms.append({
            "atom_idx": atom_idx,
            "parent_heavy_atom": parent,
            "shift_ppm": shift,
            "couplings": couplings,
        })

    return atoms


# ---------------------------------------------------------------------------
# Group equivalent hydrogens and build signal table
# ---------------------------------------------------------------------------

def group_signals(atoms: list[dict]) -> list[dict]:
    """
    Group hydrogen atoms by parent heavy atom to produce a signal list.

    Returns list of dicts sorted by descending shift:
        {
            "shift_ppm": float,
            "nH": int,
            "multiplicity": str (e.g., "s", "d", "t", "q", "m"),
            "J_Hz": str (comma-separated unique J values),
            "atom_indices": list[int],
        }
    """
    from collections import defaultdict

    groups = defaultdict(list)
    for atom in atoms:
        groups[atom["parent_heavy_atom"]].append(atom)

    signals = []
    for parent, group_atoms in sorted(groups.items()):
        n_h = len(group_atoms)
        shift = np.mean([a["shift_ppm"] for a in group_atoms])

        group_indices = {a["atom_idx"] for a in group_atoms}
        j_values = []
        for a in group_atoms:
            for c in a["couplings"]:
                if c["atom_idx"] not in group_indices:
                    j_values.append(round(c["J_Hz"], 1))

        j_unique = sorted(set(j_values), reverse=True)

        partner_atoms = set()
        for a in group_atoms:
            for c in a["couplings"]:
                if c["atom_idx"] not in group_indices:
                    partner_atoms.add(c["atom_idx"])
        n_partners = len(partner_atoms)

        mult_map = {0: "s", 1: "d", 2: "t", 3: "q", 4: "quint", 5: "sext", 6: "sept"}
        multiplicity = mult_map.get(n_partners, "m")

        signals.append({
            "shift_ppm": round(float(shift), 3),
            "nH": n_h,
            "multiplicity": multiplicity,
            "J_Hz": ",".join(str(j) for j in j_unique) if j_unique else "",
            "atom_indices": [a["atom_idx"] for a in group_atoms],
        })

    signals.sort(key=lambda s: -s["shift_ppm"])
    return signals


# ---------------------------------------------------------------------------
# nmrsim spectrum simulation
# ---------------------------------------------------------------------------

def simulate_spectrum(
    atoms: list[dict],
    field_mhz: float = 400.0,
    ppm_min: float = -0.5,
    ppm_max: float = 12.0,
    n_points: int = 8192,
    linewidth_hz: float = 1.0,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Simulate a 1H NMR spectrum from SPINUS atom data using nmrsim (QM).

    Returns (ppm_array, intensity_array) both shape (n_points,).
    """
    from nmrsim import SpinSystem

    if not atoms:
        ppm = np.linspace(ppm_min, ppm_max, n_points)
        return ppm, np.zeros(n_points)

    idx_map = {a["atom_idx"]: i for i, a in enumerate(atoms)}
    n = len(atoms)

    v = [a["shift_ppm"] * field_mhz for a in atoms]

    J = np.zeros((n, n))
    for a in atoms:
        i = idx_map[a["atom_idx"]]
        for c in a["couplings"]:
            if c["atom_idx"] in idx_map:
                j = idx_map[c["atom_idx"]]
                J[i, j] = c["J_Hz"]
                J[j, i] = c["J_Hz"]

    J_list = J.tolist()

    try:
        spin_system = SpinSystem(v=v, J=J_list)
        peaklist = spin_system.peaklist()
    except Exception as e:
        print(f"WARNING: nmrsim simulation failed, falling back to stick spectrum: {e}",
              file=sys.stderr)
        peaklist = [(a["shift_ppm"] * field_mhz, 1.0) for a in atoms]

    if not peaklist:
        ppm = np.linspace(ppm_min, ppm_max, n_points)
        return ppm, np.zeros(n_points)

    peaks = np.array(peaklist)
    freqs_hz = peaks[:, 0]
    intensities = peaks[:, 1]

    ppm = np.linspace(ppm_min, ppm_max, n_points)
    freq_axis = ppm * field_mhz

    spectrum = np.zeros(n_points)
    hwhm = linewidth_hz / 2.0
    for f, amp in zip(freqs_hz, intensities):
        spectrum += amp * (hwhm**2) / ((freq_axis - f)**2 + hwhm**2)

    max_val = spectrum.max()
    if max_val > 0:
        spectrum /= max_val

    return ppm, spectrum


# ---------------------------------------------------------------------------
# Save outputs
# ---------------------------------------------------------------------------

def save_spectrum_xy(ppm: np.ndarray, intensity: np.ndarray, path: pathlib.Path) -> None:
    """Save spectrum as two-column .xy file (ppm, intensity), descending ppm."""
    order = np.argsort(ppm)[::-1]
    arr = np.column_stack([ppm[order], intensity[order]])
    np.savetxt(path, arr, delimiter="\t", fmt="%.6f")


def save_signals_csv(signals: list[dict], path: pathlib.Path) -> None:
    """Save signal table as CSV."""
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["shift_ppm", "multiplicity", "J_Hz", "nH"])
        for s in signals:
            writer.writerow([s["shift_ppm"], s["multiplicity"], s["J_Hz"], s["nH"]])


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(
        description="Predict 1H NMR spectra from SMILES via NMRdb.org SPINUS + nmrsim."
    )
    ap.add_argument("--smiles", nargs="+", required=True,
                    help="SMILES strings for compounds")
    ap.add_argument("--names", nargs="+",
                    help="Names for each SMILES (used in filenames). Defaults to comp0, comp1, ...")
    ap.add_argument("--field_mhz", type=float, default=400.0,
                    help="Spectrometer frequency in MHz (default: 400)")
    ap.add_argument("--linewidth", type=float, default=1.0,
                    help="Lorentzian linewidth FWHM in Hz (default: 1.0)")
    ap.add_argument("--n_points", type=int, default=8192,
                    help="Number of points in simulated spectrum (default: 8192)")
    ap.add_argument("--output_dir", default="nmr_predictions",
                    help="Directory for output files (default: nmr_predictions/)")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    names = args.names if args.names and len(args.names) == len(args.smiles) \
        else [f"comp{i}" for i in range(len(args.smiles))]

    out_dir = pathlib.Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    found = []
    failed = []

    for smiles, name in zip(args.smiles, names):
        safe_name = re.sub(r"[^\w\-]", "_", name)[:40]
        if not args.quiet:
            print(f"  {name} ({smiles})...", end="  ", flush=True)

        try:
            atoms = fetch_spinus(smiles)
            if not atoms:
                raise ValueError("SPINUS returned no atoms")

            signals = group_signals(atoms)

            ppm, intensity = simulate_spectrum(
                atoms,
                field_mhz=args.field_mhz,
                n_points=args.n_points,
                linewidth_hz=args.linewidth,
            )

            xy_path = out_dir / f"{safe_name}.xy"
            sig_path = out_dir / f"{safe_name}_signals.csv"
            save_spectrum_xy(ppm, intensity, xy_path)
            save_signals_csv(signals, sig_path)

            found.append({
                "smiles": smiles,
                "name": name,
                "n_signals": len(signals),
                "n_atoms_h": len(atoms),
                "spectrum": str(xy_path),
                "signals": str(sig_path),
            })
            if not args.quiet:
                print(f"OK ({len(signals)} signals, {len(atoms)} H atoms)")

        except Exception as e:
            failed.append({"smiles": smiles, "name": name, "error": str(e)})
            if not args.quiet:
                print(f"FAILED: {e}")

    manifest = {
        "found": found,
        "failed": failed,
        "parameters": {
            "field_mhz": args.field_mhz,
            "linewidth_hz": args.linewidth,
            "n_points": args.n_points,
        },
    }
    manifest_path = out_dir / "predictions.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))

    print(f"\nDone: {len(found)} spectra predicted, {len(failed)} failed.")
    print(f"Output -> {out_dir}/")

    if failed:
        print(f"\nFailed: {[e['name'] for e in failed]}")


if __name__ == "__main__":
    main()
