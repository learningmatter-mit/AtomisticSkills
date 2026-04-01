#!/usr/bin/env python3
"""
Deconvolve an NMR mixture against component spectra using Wasserstein (optimal
transport) distance, solved via scipy.optimize.linprog.

Algorithm adapted from Magnetstein/Masserstein (Domzal et al., Anal. Chem. 2024;
Ciach et al., Rapid Commun. Mass Spectrom. 2020).  The dual LP formulation is:

    maximize   v^T z
    subject to T_j^T z <= 0   for each component j
               |z_i - z_{i+1}| <= l_i   (Lipschitz / 1-Wasserstein)
               z_i <= kappa              (denoising penalty)

Component proportions are the dual variables (shadow prices) of the T_j
constraints.  No PuLP, CBC, or external solver required -- uses SciPy's
built-in HiGHS backend.

Usage:
  # Env: nmr-agent
  python deconvolve.py crude.csv ref_a.csv ref_b.csv \
      --protons 18 18 --names borneol isoborneol --baseline-correct --json

Requirements: numpy, scipy (>= 1.7), matplotlib (optional, for --plot)
"""

import argparse
import json
import pathlib
import sys
from typing import Optional

import numpy as np
from scipy.optimize import linprog


# ---------------------------------------------------------------------------
# Spectrum I/O helpers
# ---------------------------------------------------------------------------

def detect_delim(path: str, default: str = ",") -> str:
    p = pathlib.Path(path)
    if p.suffix.lower() in (".tsv", ".xy"):
        return "\t"
    try:
        with open(path, "r", errors="ignore") as f:
            line = f.readline()
        return "\t" if "\t" in line else default
    except Exception:
        return default


def load_xy(path: str, delimiter: Optional[str] = None, mnova: bool = False) -> np.ndarray:
    if delimiter is None:
        delimiter = "\t" if mnova else detect_delim(path)
    try:
        arr = np.loadtxt(path, delimiter=delimiter, usecols=[0, 1])
    except ValueError:
        arr = np.loadtxt(path, delimiter=delimiter, usecols=[0, 1], skiprows=1)
    if arr.ndim != 2 or arr.shape[1] < 2:
        raise ValueError(f"{path}: expected two numeric columns (ppm, intensity)")
    return arr


def baseline_correct(arr: np.ndarray) -> np.ndarray:
    corrected = arr.copy()
    corrected[:, 1] -= arr[:, 1].min()
    return corrected


# ---------------------------------------------------------------------------
# Wasserstein LP deconvolution (scipy port of dualdeconv2)
# ---------------------------------------------------------------------------

def _merge_axes(*spectra_confs: list[tuple[float, float]]) -> np.ndarray:
    """Build a sorted, deduplicated common ppm axis from multiple spectra."""
    all_ppm = set()
    for confs in spectra_confs:
        for ppm, _ in confs:
            all_ppm.add(round(ppm, 6))
    return np.array(sorted(all_ppm))


def _intensities_on_axis(confs: list[tuple[float, float]], axis: np.ndarray) -> np.ndarray:
    """Project a (ppm, intensity) list onto a common axis (zero where absent)."""
    lookup = {}
    for ppm, inten in confs:
        key = round(ppm, 6)
        lookup[key] = lookup.get(key, 0.0) + inten
    return np.array([lookup.get(round(a, 6), 0.0) for a in axis])


def _normalize_confs(confs: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Clamp negatives to 0, then normalize intensities to sum to 1."""
    clamped = [(p, max(i, 0.0)) for p, i in confs]
    total = sum(i for _, i in clamped)
    if total <= 0:
        return clamped
    return [(p, i / total) for p, i in clamped]


def wasserstein_deconvolve(
    mixture_confs: list[tuple[float, float]],
    component_confs_list: list[list[tuple[float, float]]],
    kappa: float = 0.25,
) -> dict:
    """
    Estimate component proportions via Wasserstein-distance LP deconvolution.

    Parameters
    ----------
    mixture_confs : list of (ppm, intensity)
        Mixture spectrum, will be normalized internally.
    component_confs_list : list of list of (ppm, intensity)
        Reference spectra, each normalized internally.
    kappa : float
        Denoising penalty (max transport cost).  Default 0.25.

    Returns
    -------
    dict with keys:
        "proportions" : list[float]  -- estimated proportion per component
        "wasserstein_distance" : float  -- objective value (fit quality)
        "noise" : float  -- fraction of signal attributed to noise
    """
    # Normalize
    mix_n = _normalize_confs(mixture_confs)
    comp_n = [_normalize_confs(c) for c in component_confs_list]

    # Build common axis
    axis = _merge_axes(mix_n, *comp_n)
    n = len(axis)
    if n < 2:
        return {"proportions": [0.0] * len(comp_n), "wasserstein_distance": float("nan"), "noise": 1.0}

    # Intensity vectors on common axis
    v = _intensities_on_axis(mix_n, axis)        # mixture
    T = [_intensities_on_axis(c, axis) for c in comp_n]  # components
    k = len(T)

    # Interval lengths between consecutive axis points
    intervals = np.diff(axis)

    # -----------------------------------------------------------------------
    # LP formulation  (scipy minimizes, so we minimize -v^T z)
    #
    # Variables: z_0 .. z_{n-1}
    #
    # Inequality constraints (A_ub @ z <= b_ub):
    #   1. Component constraints:  T_j^T z <= 0    (k constraints)
    #   2. Lipschitz forward:   z_i - z_{i+1} <= l_i   (n-1 constraints)
    #   3. Lipschitz backward:  z_{i+1} - z_i <= l_i   (n-1 constraints)
    #
    # Variable bounds:  z_i <= kappa  (no lower bound)
    # -----------------------------------------------------------------------

    c_obj = -v  # minimize -v^T z  <=>  maximize v^T z

    n_ineq = k + 2 * (n - 1)
    A_ub = np.zeros((n_ineq, n))
    b_ub = np.zeros(n_ineq)

    row = 0
    # Component constraints: T_j^T z <= 0
    for j in range(k):
        A_ub[row, :] = T[j]
        b_ub[row] = 0.0
        row += 1

    # Lipschitz forward: z_i - z_{i+1} <= l_i
    for i in range(n - 1):
        A_ub[row, i] = 1.0
        A_ub[row, i + 1] = -1.0
        b_ub[row] = intervals[i]
        row += 1

    # Lipschitz backward: z_{i+1} - z_i <= l_i
    for i in range(n - 1):
        A_ub[row, i] = -1.0
        A_ub[row, i + 1] = 1.0
        b_ub[row] = intervals[i]
        row += 1

    bounds = [(None, kappa)] * n

    result = linprog(
        c_obj,
        A_ub=A_ub,
        b_ub=b_ub,
        bounds=bounds,
        method="highs",
        options={"presolve": True, "disp": False},
    )

    if not result.success:
        return {
            "proportions": [0.0] * k,
            "wasserstein_distance": float("nan"),
            "noise": 1.0,
        }

    # Extract proportions from dual variables of component constraints
    # result.ineqlin.marginals[j] for the first k constraints
    duals = result.ineqlin.marginals
    proportions = [-float(duals[j]) for j in range(k)]  # negated because dual of <= constraint

    # Noise: from reduced costs (dual of upper bound constraints)
    noise = 1.0 - sum(proportions)

    # Wasserstein distance = optimal objective value (negated back)
    wd = -float(result.fun)

    return {
        "proportions": proportions,
        "wasserstein_distance": wd,
        "noise": max(noise, 0.0),
    }


def deconvolve_spectra(
    mix_arr: np.ndarray,
    comp_arrays: list[np.ndarray],
    protons: list[int],
    kappa: float = 0.25,
) -> dict:
    """
    High-level deconvolution: load arrays, run LP, apply proton correction.

    Parameters
    ----------
    mix_arr : ndarray of shape (M, 2)
        Mixture spectrum (ppm, intensity).
    comp_arrays : list of ndarray of shape (N_i, 2)
        Component reference spectra.
    protons : list of int
        Number of 1H protons per component molecule.
    kappa : float
        Denoising penalty.

    Returns
    -------
    dict with "proportions", "wasserstein_distance", "noise"
    """
    mix_confs = list(zip(mix_arr[:, 0].tolist(), mix_arr[:, 1].tolist()))
    comp_confs = [
        list(zip(a[:, 0].tolist(), a[:, 1].tolist())) for a in comp_arrays
    ]

    raw = wasserstein_deconvolve(mix_confs, comp_confs, kappa=kappa)
    raw_props = raw["proportions"]

    # Proton correction: convert area-proportional to concentration-proportional
    if protons and all(p > 0 for p in protons):
        corrected = [prop / p for prop, p in zip(raw_props, protons)]
        total = sum(corrected)
        if total > 0:
            corrected = [c / total for c in corrected]
        raw["proportions"] = corrected

    return raw


# ---------------------------------------------------------------------------
# Plotting (delegated to plot.py)
# ---------------------------------------------------------------------------

def _save_plot(out_path: str, mix_arr: np.ndarray, comp_arrays: list,
               names: list, props: list, wd: float) -> None:
    from plot import plot_deconvolution
    plot_deconvolution(mix_arr, comp_arrays, names, props, wd, out_path)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="Estimate component proportions in an NMR mixture.")
    ap.add_argument("mixture", help="CSV/TSV file with mixture: columns [ppm, intensity]")
    ap.add_argument("components", nargs="+", help="CSV/TSV files for components: columns [ppm, intensity]")
    ap.add_argument("--protons", type=int, nargs="+", help="Proton counts for each component (e.g. 18 18)")
    ap.add_argument("--names", nargs="+", help='Names for components (e.g. borneol isoborneol)')
    ap.add_argument("--kappa", type=float, default=0.25, help="Denoising penalty (default: 0.25)")
    ap.add_argument("--mnova", action="store_true", help="Treat inputs as Mnova TSV (delimiter='\\t')")
    ap.add_argument("--baseline-correct", action="store_true",
                    help="Shift each spectrum so its minimum intensity becomes 0.")
    ap.add_argument("--plot", metavar="FILE", default=None,
                    help="Save a deconvolution plot to FILE (e.g. result.png).")
    ap.add_argument("--json", action="store_true", help="Print JSON result line as well")
    ap.add_argument("--quiet", action="store_true", help="Suppress verbose output")
    args = ap.parse_args()

    # Load data
    mix_arr = load_xy(args.mixture, mnova=args.mnova)
    comp_arrays = [load_xy(p, mnova=args.mnova) for p in args.components]

    if args.baseline_correct:
        if not args.quiet:
            print("Baseline correction: shifting each spectrum so its minimum intensity = 0.")
        mix_arr = baseline_correct(mix_arr)
        comp_arrays = [baseline_correct(a) for a in comp_arrays]

    n = len(comp_arrays)
    names = args.names if args.names and len(args.names) == n else [f"comp{i}" for i in range(n)]
    if args.names and len(args.names) != n:
        print("WARNING: --names length does not match number of components; using default names.", file=sys.stderr)

    if args.protons and len(args.protons) != n:
        print("ERROR: --protons length must equal number of components.", file=sys.stderr)
        sys.exit(2)
    protons = args.protons if args.protons else [1] * n
    if not args.protons:
        print("NOTE: No --protons provided; assuming 1 for each component.", file=sys.stderr)

    # Deconvolve
    result = deconvolve_spectra(mix_arr, comp_arrays, protons, kappa=args.kappa)
    props = result["proportions"]
    wd = result["wasserstein_distance"]

    # Output
    print("\nEstimated proportions:")
    width = max(len(s) for s in names) + 2
    for name, val in zip(names, props):
        print(f"  {name.ljust(width)} {val:.6f}")
    print(f"\nWasserstein distance: {wd:.12f}")

    if args.json:
        out = {"proportions": dict(zip(names, props)), "Wasserstein distance": wd}
        print("\nJSON:", json.dumps(out))

    if args.plot:
        _save_plot(args.plot, mix_arr, comp_arrays, names, props, wd)
        if not args.quiet:
            print(f"\nPlot saved -> {args.plot}")


if __name__ == "__main__":
    main()
