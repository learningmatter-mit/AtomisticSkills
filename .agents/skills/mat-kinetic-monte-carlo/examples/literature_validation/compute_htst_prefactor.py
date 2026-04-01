"""
Compute the hTST (harmonic transition state theory) prefactor from phonon data.

Implements the Vineyard formula:

    nu_hTST = prod(nu_eq, i=1..3N-3) / prod(nu_ts, j=1..3N-4)

where 3N-3 excludes the 3 translational (acoustic) modes at Gamma, and 3N-4
additionally excludes the imaginary mode at the saddle point.

Inputs:
    - phonon.yaml from equilibrium (T-site) phonon calculation
    - phonon.yaml from saddle point phonon calculation
    - neb_results.json with the NEB barrier

The phonon.yaml files are produced by matcalc/phonopy and contain force
constants for the supercell.  This script loads them via phonopy's API,
computes the dynamical matrix at Gamma, and extracts all eigenfrequencies.

Usage:
    python compute_htst_prefactor.py \
        --phonon_eq phonon_eq/phonon.yaml \
        --phonon_ts phonon_ts/phonon.yaml \
        --neb_results neb_results/neb_results.json \
        --output htst_results.json

Requirements:
    phonopy, numpy (base-agent env)
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Optional

import numpy as np


def load_gamma_frequencies_thz(phonon_yaml_path: str) -> np.ndarray:
    """Load phonon.yaml via phonopy and return Gamma-point frequencies in THz.

    Uses phonopy to:
    1. Load force constants from phonon.yaml
    2. Build the dynamical matrix at q=(0,0,0)
    3. Diagonalize to get eigenfrequencies

    Returns sorted array of all 3N frequencies in THz.  Imaginary modes are
    returned as negative values (phonopy convention: sqrt of negative
    eigenvalue → negative frequency).
    """
    from phonopy import load as phonopy_load

    phonon = phonopy_load(phonon_yaml_path)
    phonon.run_mesh([1, 1, 1], with_eigenvectors=False, is_gamma_center=True)
    mesh_dict = phonon.get_mesh_dict()
    # mesh_dict['frequencies'] shape: (n_qpoints, n_bands) in THz
    # with [1,1,1] mesh + gamma center, n_qpoints=1
    freqs = mesh_dict["frequencies"][0]  # 1D array, 3N entries
    return np.sort(freqs)


def filter_real_modes(
    freqs_thz: np.ndarray,
    acoustic_threshold_thz: float = 0.1,
    is_transition_state: bool = False,
    strict: bool = True,
) -> tuple[np.ndarray, int]:
    """Filter out acoustic/translational modes and (for TS) the imaginary mode.

    For the equilibrium geometry:
        - Remove 3 near-zero acoustic modes (|freq| < threshold)
        - All remaining should be positive
        - Returns 3N-3 frequencies

    For the transition state:
        - Remove 3 near-zero acoustic modes
        - Remove 1 imaginary mode (most negative frequency)
        - Returns 3N-4 frequencies

    Returns:
        (filtered_frequencies, n_imaginary)
    """
    freqs_sorted = np.sort(freqs_thz)
    imag_mask = freqs_sorted < -acoustic_threshold_thz
    n_imaginary = int(np.sum(imag_mask))

    if is_transition_state:
        if n_imaginary == 0:
            msg = "No imaginary frequency found at transition state."
            if strict:
                raise RuntimeError(f"{msg} Structure is not a first-order saddle.")
            print(f"WARNING: {msg}")
        elif n_imaginary > 1:
            msg = f"{n_imaginary} imaginary frequencies at transition state."
            if strict:
                raise RuntimeError(f"{msg} Expected exactly 1.")
            print(f"WARNING: {msg} Expected exactly 1. Proceeding non-strict.")

        # remove the most negative (imaginary) mode if present
        if n_imaginary >= 1:
            freqs_sorted = freqs_sorted[1:]
    else:
        if n_imaginary > 0:
            msg = f"Equilibrium structure has {n_imaginary} imaginary mode(s)."
            if strict:
                raise RuntimeError(msg)
            print(f"WARNING: {msg} Proceeding non-strict.")

    # remove near-zero acoustic modes
    filtered = freqs_sorted[np.abs(freqs_sorted) > acoustic_threshold_thz]

    # In non-strict mode, drop any remaining negative frequencies
    if not strict:
        filtered = filtered[filtered > 0.0]

    return filtered, n_imaginary


def vineyard_prefactor(freqs_eq_thz: np.ndarray,
                       freqs_ts_thz: np.ndarray) -> float:
    """Compute the Vineyard hTST prefactor.

    nu_hTST = prod(nu_eq) / prod(nu_ts)

    Uses log-space arithmetic to avoid overflow:
        log(nu) = sum(log(nu_eq)) - sum(log(nu_ts))

    Returns prefactor in THz.
    """
    log_prod_eq = np.sum(np.log(np.abs(freqs_eq_thz)))
    log_prod_ts = np.sum(np.log(np.abs(freqs_ts_thz)))
    log_prefactor = log_prod_eq - log_prod_ts
    return math.exp(log_prefactor)


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Compute hTST prefactor from phonon calculations (Vineyard formula)."
    )
    ap.add_argument("--phonon_eq", required=True,
                    help="Path to equilibrium phonon.yaml")
    ap.add_argument("--phonon_ts", required=True,
                    help="Path to saddle point phonon.yaml")
    ap.add_argument("--neb_results", default=None,
                    help="Path to neb_results.json (for barrier)")
    ap.add_argument("--barrier_eV", type=float, default=None,
                    help="Override barrier (eV), used if --neb_results not given")
    ap.add_argument("--acoustic_threshold", type=float, default=0.3,
                    help="Threshold (THz) below which modes are considered acoustic/translational")
    ap.add_argument("--output", default="htst_results.json",
                    help="Output JSON path")
    ap.add_argument("--strict", dest="strict", action="store_true",
                    help="Abort if equilibrium has imaginary modes or TS is not first-order saddle")
    ap.add_argument("--no-strict", dest="strict", action="store_false",
                    help="Warn instead of aborting on unstable phonons (not recommended)")
    ap.set_defaults(strict=True)
    args = ap.parse_args()

    # load barrier
    barrier_eV: Optional[float] = args.barrier_eV
    if args.neb_results:
        neb_data = json.loads(Path(args.neb_results).read_text())
        barrier_eV = neb_data["barrier_eV"]
        print(f"NEB barrier: {barrier_eV:.4f} eV")
    if barrier_eV is None:
        print("ERROR: Must provide --neb_results or --barrier_eV")
        return

    # load Gamma-point frequencies
    print(f"\nLoading equilibrium phonon: {args.phonon_eq}")
    freqs_eq_all = load_gamma_frequencies_thz(args.phonon_eq)
    n_atoms_eq = len(freqs_eq_all) // 3
    print(f"  {len(freqs_eq_all)} modes ({n_atoms_eq} atoms)")
    print(f"  Lowest 6 freqs: {freqs_eq_all[:6]} THz")
    print(f"  Highest 3 freqs: {freqs_eq_all[-3:]} THz")

    print(f"\nLoading saddle-point phonon: {args.phonon_ts}")
    freqs_ts_all = load_gamma_frequencies_thz(args.phonon_ts)
    n_atoms_ts = len(freqs_ts_all) // 3
    print(f"  {len(freqs_ts_all)} modes ({n_atoms_ts} atoms)")
    print(f"  Lowest 6 freqs: {freqs_ts_all[:6]} THz")
    print(f"  Highest 3 freqs: {freqs_ts_all[-3:]} THz")

    if n_atoms_eq != n_atoms_ts:
        print(f"WARNING: Atom count mismatch (eq={n_atoms_eq}, ts={n_atoms_ts})")

    # filter modes
    threshold = args.acoustic_threshold
    freqs_eq, n_imag_eq = filter_real_modes(
        freqs_eq_all, threshold, is_transition_state=False, strict=args.strict
    )
    freqs_ts, n_imag_ts = filter_real_modes(
        freqs_ts_all, threshold, is_transition_state=True, strict=args.strict
    )

    n_3N = len(freqs_eq_all)
    print(f"\nFiltered modes (threshold={threshold} THz):")
    print(f"  Equilibrium: {len(freqs_eq)} of {n_3N} (expected {n_3N - 3})")
    print(f"  Saddle point: {len(freqs_ts)} of {n_3N} (expected {n_3N - 4})")

    expected_eq = n_3N - 3
    expected_ts = n_3N - 4
    if len(freqs_eq) != expected_eq:
        msg = (f"Expected {expected_eq} equilibrium modes, got {len(freqs_eq)}. "
               f"Adjust --acoustic_threshold if needed (current: {threshold} THz).")
        if args.strict:
            raise RuntimeError(msg)
        print(f"  WARNING: {msg}")
    if len(freqs_ts) != expected_ts:
        msg = f"Expected {expected_ts} saddle modes, got {len(freqs_ts)}."
        if args.strict:
            raise RuntimeError(msg)
        print(f"  WARNING: {msg}")

    # Vineyard formula
    prefactor_thz = vineyard_prefactor(freqs_eq, freqs_ts)
    prefactor_hz = prefactor_thz * 1e12

    print(f"\nVineyard hTST prefactor:")
    print(f"  nu = {prefactor_thz:.4f} THz = {prefactor_hz:.4e} Hz")
    print(f"  log10(nu/Hz) = {math.log10(prefactor_hz):.2f}")
    print(f"  Barrier: {barrier_eV:.4f} eV")

    # physical reasonableness check
    if 1e10 < prefactor_hz < 1e16:
        print("  PASS: Prefactor in physically reasonable range (10^10 - 10^16 Hz)")
    else:
        print(f"  WARNING: Prefactor {prefactor_hz:.2e} Hz outside typical range")

    # derived quantities
    a_W = 3.165  # Angstrom
    D0_m2_s = (a_W**2 * 1e-20 / 12.0) * prefactor_hz
    print(f"\n  D0 = (a^2/12) * nu = {D0_m2_s:.4e} m^2/s")
    print(f"  (Compare: Yang et al. = 8.45e-7 m^2/s, Frauenfelder = 4.1e-7 m^2/s)")

    results = {
        "system": "H in BCC W (T-site migration, hTST)",
        "barrier_eV": barrier_eV,
        "prefactor_THz": prefactor_thz,
        "prefactor_Hz": prefactor_hz,
        "log10_prefactor_Hz": math.log10(prefactor_hz),
        "D0_m2_s": D0_m2_s,
        "n_atoms": n_atoms_eq,
        "n_modes_eq": len(freqs_eq),
        "n_modes_ts": len(freqs_ts),
        "acoustic_threshold_THz": threshold,
        "strict": args.strict,
        "n_imag_eq": int(n_imag_eq),
        "n_imag_ts": int(n_imag_ts),
        "freqs_eq_min_THz": float(freqs_eq[0]),
        "freqs_eq_max_THz": float(freqs_eq[-1]),
        "freqs_ts_min_THz": float(freqs_ts[0]),
        "freqs_ts_max_THz": float(freqs_ts[-1]),
        "imaginary_freq_THz": float(freqs_ts_all[0]) if freqs_ts_all[0] < 0 else None,
        "phonon_eq_path": str(args.phonon_eq),
        "phonon_ts_path": str(args.phonon_ts),
    }

    output_path = Path(args.output)
    output_path.write_text(json.dumps(results, indent=4))
    print(f"\nWrote: {output_path}")


if __name__ == "__main__":
    main()
