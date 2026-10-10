#!/usr/bin/env python3
"""
Validate kinetics.py output on a two-component NMR time series against
reference-free and independent estimates of the same series.

Three checks are made:

1. Rank test. The time-centred spectrum matrix of a two-component mixture
   series with white noise is rank one: the first singular value carries the
   composition change and the others sit at the noise level sigma*sqrt(N).
2. Reference-free rate constant. The first principal-component scores are an
   affine function of the true mixing fraction, so fitting them with
   s(t) = A + C*exp(-k*t) recovers the time constant of the generating
   trajectory without using any reference spectrum or baseline treatment.
3. Independent composition. Each spectrum is fitted by ordinary linear least
   squares to the two reference spectra plus a constant baseline, giving
   amplitudes a(t), b(t) and offset c(t). For a mixture of two fixed
   end-member spectra with weights w and 1 - w these obey the closure
   a/s_1 + b/s_2 = 1; s_1 and s_2 are fitted over the whole series and the
   end-member mixing weight is w(t) = (a/s_1 + 1 - b/s_2)/2. Because w(t) is
   linear in the data it keeps the time constant of the true trajectory. The
   closure residual and the offsets, which must obey
   c = w*o_1 + (1 - w)*o_2, are reported as consistency checks.

Every trajectory is fitted with x(t) = x_inf + (x0 - x_inf)*exp(-k*t).

Usage:
    venv/run cpu python validate_kinetics.py \
        --timepoints t000min.csv t005min.csv ... --times 0 5 ... \
        --refs borneol.csv isoborneol.csv --names borneol isoborneol \
        --kinetics_csv output/legacy_min/kinetics.csv \
                       output/window_baseline/kinetics.csv \
        --labels legacy_min window_baseline \
        --output_dir validation

Requirements:
    - Environment: cpu (run with: venv/run cpu python ...)
    - Required packages: numpy, scipy, matplotlib
"""

import argparse
import csv
import json
import pathlib

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.optimize import curve_fit

plt.rcParams.update({"font.size": 14})


def first_order(t: np.ndarray, x_inf: float, amplitude: float, k: float) -> np.ndarray:
    """First-order relaxation x(t) = x_inf + amplitude * exp(-k t)."""
    return x_inf + amplitude * np.exp(-k * t)


def fit_first_order(times: np.ndarray, values: np.ndarray) -> dict:
    """
    Fit a first-order relaxation to a trajectory.

    Args:
        times: Time points.
        values: Trajectory values at each time point.

    Returns:
        Dictionary with keys 'k', 'k_err', 'x0', 'x_inf', 'rms'.
    """
    p0 = [values[-1], values[0] - values[-1], 1.0 / max(times.max(), 1e-12)]
    popt, pcov = curve_fit(first_order, times, values, p0=p0, maxfev=20000)
    resid = values - first_order(times, *popt)
    return {
        "k": float(popt[2]),
        "k_err": float(np.sqrt(pcov[2, 2])),
        "x0": float(popt[0] + popt[1]),
        "x_inf": float(popt[0]),
        "rms": float(np.sqrt(np.mean(resid**2))),
    }


def load_two_column(path: str) -> np.ndarray:
    """Load a two-column comma-separated (ppm, intensity) spectrum sorted by ppm."""
    arr = np.loadtxt(path, delimiter=",", usecols=[0, 1])
    return arr[np.argsort(arr[:, 0])]


def read_kinetics_csv(path: str, name: str) -> tuple:
    """
    Read the time column and one component column from a kinetics.csv file.

    Args:
        path: Path to kinetics.csv written by kinetics.py.
        name: Component column to read.

    Returns:
        Tuple of (times, fractions) as numpy arrays.
    """
    with open(path, newline="") as handle:
        rows = list(csv.DictReader(handle))
    time_key = [key for key in rows[0] if key.startswith("time_")][0]
    times = np.array([float(row[time_key]) for row in rows])
    fractions = np.array([float(row[name]) for row in rows])
    return times, fractions


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Validate NMR kinetics deconvolution against reference-free "
        "and least-squares estimates."
    )
    ap.add_argument(
        "--timepoints", nargs="+", required=True, help="Time-ordered spectra"
    )
    ap.add_argument("--times", type=float, nargs="+", required=True, help="Time values")
    ap.add_argument("--refs", nargs=2, required=True, help="Two reference spectra")
    ap.add_argument(
        "--names", nargs=2, required=True, help="Names of the two references"
    )
    ap.add_argument(
        "--kinetics_csv", nargs="+", default=[], help="kinetics.csv files to validate"
    )
    ap.add_argument("--labels", nargs="+", default=[], help="Labels for --kinetics_csv")
    ap.add_argument(
        "--signal_free",
        type=float,
        nargs=2,
        default=[2.40, 3.40],
        help="ppm window without signals, used for the noise estimate (default: 2.40 3.40)",
    )
    ap.add_argument("--output_dir", default="validation", help="Output directory")
    args = ap.parse_args()

    times = np.array(args.times)
    out_dir = pathlib.Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    labels = (
        args.labels
        if len(args.labels) == len(args.kinetics_csv)
        else [pathlib.Path(p).parent.name for p in args.kinetics_csv]
    )

    spectra = [load_two_column(p) for p in args.timepoints]
    grid = spectra[0][:, 0]
    matrix = np.stack([np.interp(grid, s[:, 0], s[:, 1]) for s in spectra])

    # 1. Rank test and noise level
    quiet = (grid > args.signal_free[0]) & (grid < args.signal_free[1])
    sigma = matrix[:, quiet].std(axis=1)
    # Pedestal left by minimum subtraction (kinetics.py --baseline_correct)
    pedestal = matrix[:, quiet].mean(axis=1) - matrix.min(axis=1)
    pedestal_fraction = (
        pedestal * grid.size / (matrix - matrix.min(axis=1)[:, None]).sum(axis=1)
    )
    centred = matrix - matrix.mean(axis=0)
    u, s, _ = np.linalg.svd(centred, full_matrices=False)
    explained = s**2 / np.sum(s**2)

    # 2. Reference-free rate constant from PC1 scores
    scores = u[:, 0] * s[0]
    pc1_fit = fit_first_order(times, scores)
    pc1_fit.pop("x0")
    pc1_fit.pop("x_inf")
    pc1_fit["rms_over_span"] = pc1_fit.pop("rms") / float(np.ptp(scores))
    keep = [np.arange(len(times)) != i for i in range(len(times))]
    loo_k = [fit_first_order(times[m], scores[m])["k"] for m in keep]
    pc1_fit["leave_one_out_k_range"] = [float(min(loo_k)), float(max(loo_k))]

    # 3. Linear least squares on the references + constant baseline, then the
    #    two-end-member closure a/s_1 + b/s_2 = 1 to obtain the mixing weight
    refs = [load_two_column(p) for p in args.refs]
    ref_on_grid = [np.interp(grid, r[:, 0], r[:, 1], left=0.0, right=0.0) for r in refs]
    design = np.column_stack(ref_on_grid + [np.ones_like(grid)])
    amp = np.linalg.lstsq(design, matrix.T, rcond=None)[0].T  # (n_times, 3)
    inv_scale = np.linalg.lstsq(amp[:, :2], np.ones(len(times)), rcond=None)[0]
    scale = 1.0 / inv_scale
    lsq_fraction = 0.5 * (amp[:, 0] / scale[0] + 1.0 - amp[:, 1] / scale[1])
    closure_resid = amp[:, 0] / scale[0] + amp[:, 1] / scale[1] - 1.0
    offsets = np.linalg.lstsq(
        np.column_stack([lsq_fraction, 1.0 - lsq_fraction]), amp[:, 2], rcond=None
    )[0]
    offset_resid = amp[:, 2] - (
        lsq_fraction * offsets[0] + (1.0 - lsq_fraction) * offsets[1]
    )
    lsq_fit = fit_first_order(times, lsq_fraction)

    # End members implied by w(t): compare peak positions/shapes with the references
    endmembers = np.linalg.lstsq(
        np.column_stack([lsq_fraction, 1.0 - lsq_fraction]), matrix, rcond=None
    )[0]
    shifts = np.arange(-0.02, 0.02001, 0.0005)
    endmember_corr, endmember_shift = [], []
    for member, ref in zip(endmembers, ref_on_grid):
        corr = [
            np.corrcoef(member, np.interp(grid - d, grid, ref))[0, 1] for d in shifts
        ]
        endmember_corr.append(float(np.corrcoef(member, ref)[0, 1]))
        endmember_shift.append(float(shifts[int(np.argmax(corr))]))

    # 4. Compare each kinetics.csv with the least-squares composition
    comparisons = {}
    for path, label in zip(args.kinetics_csv, labels):
        t_csv, x_csv = read_kinetics_csv(path, args.names[0])
        diff = x_csv - lsq_fraction
        fit = fit_first_order(t_csv, x_csv)
        comparisons[label] = {
            "kinetics_csv": path,
            f"{args.names[0]}_fraction": x_csv.tolist(),
            "first_order_fit": fit,
            "k_relative_error_vs_reference_free": (fit["k"] - pc1_fit["k"])
            / pc1_fit["k"],
            "max_abs_diff_vs_lsq": float(np.abs(diff).max()),
            "mean_abs_diff_vs_lsq": float(np.abs(diff).mean()),
            "monotonic": bool(np.all(np.diff(x_csv) < 0) or np.all(np.diff(x_csv) > 0)),
        }

    summary = {
        "component": args.names[0],
        "times": times.tolist(),
        "noise_sigma_per_spectrum": sigma.tolist(),
        "min_subtraction_pedestal": pedestal.tolist(),
        "min_subtraction_pedestal_fraction": pedestal_fraction.tolist(),
        "singular_values_centred": s.tolist(),
        "expected_noise_singular_value": float(sigma.mean() * np.sqrt(grid.size)),
        "pc1_explained_variance": float(explained[0]),
        "reference_free_pc1_fit": pc1_fit,
        "lsq_fraction": lsq_fraction.tolist(),
        "lsq_amplitudes": amp.tolist(),
        "lsq_endmember_scales": scale.tolist(),
        "lsq_closure_residual": closure_resid.tolist(),
        "lsq_endmember_offsets": offsets.tolist(),
        "lsq_offset_residual": offset_resid.tolist(),
        "lsq_first_order_fit": lsq_fit,
        "endmember_correlation_with_refs": endmember_corr,
        "endmember_best_shift_ppm": endmember_shift,
        "kinetics_csv_comparison": comparisons,
    }
    with open(out_dir / "validation.json", "w") as handle:
        json.dump(summary, handle, indent=2)

    # Plot: component fraction vs time with first-order fits
    fig, ax = plt.subplots(figsize=(6, 5))
    t_dense = np.linspace(0.0, times.max(), 200)
    ax.plot(
        times,
        lsq_fraction * 100,
        "ko",
        markersize=7,
        label="Least squares (independent)",
    )
    ax.plot(
        t_dense,
        first_order(
            t_dense, lsq_fit["x_inf"], lsq_fit["x0"] - lsq_fit["x_inf"], lsq_fit["k"]
        )
        * 100,
        "k-",
        linewidth=2.5,
    )
    for i, (label, comp) in enumerate(comparisons.items()):
        fit = comp["first_order_fit"]
        ax.plot(
            times,
            np.array(comp[f"{args.names[0]}_fraction"]) * 100,
            "s",
            color=f"C{i}",
            markersize=6,
            label=f"kinetics.py: {label} (k = {fit['k']:.4f})",
        )
        ax.plot(
            t_dense,
            first_order(t_dense, fit["x_inf"], fit["x0"] - fit["x_inf"], fit["k"])
            * 100,
            "--",
            color=f"C{i}",
            linewidth=2.5,
        )
    ax.set_xlabel("Time (min)", fontweight="bold")
    ax.set_ylabel(f"{args.names[0]} fraction (%)", fontweight="bold")
    ax.set_title(f"Reference-free k = {pc1_fit['k']:.4f} min$^{{-1}}$", fontsize=13)
    ax.set_ylim(0, 110)
    ax.grid(False)
    ax.legend(frameon=False, fontsize=10)
    plt.tight_layout()
    fig.savefig(out_dir / "validation.png", dpi=150, bbox_inches="tight")
    fig.savefig(out_dir / "validation.svg", bbox_inches="tight")
    plt.close(fig)

    print(f"Noise sigma (signal-free window): {sigma.mean():.4f}")
    print(
        "Singular values (centred): "
        + " ".join(f"{v:.3f}" for v in s)
        + f"  | expected noise level ~ {summary['expected_noise_singular_value']:.3f}"
    )
    print(f"PC1 explained variance: {explained[0]:.4f}")
    print(
        "Min-subtraction pedestal: "
        + " ".join(f"{v:.3f}" for v in pedestal)
        + " | fraction of summed intensity: "
        + " ".join(f"{v:.2f}" for v in pedestal_fraction)
    )
    print(
        f"Reference-free k (PC1): {pc1_fit['k']:.4f} +/- {pc1_fit['k_err']:.4f} "
        f"(leave-one-out {pc1_fit['leave_one_out_k_range'][0]:.4f}-"
        f"{pc1_fit['leave_one_out_k_range'][1]:.4f})"
    )
    print(
        "Least-squares mixing weight: "
        + " ".join(f"{v:.3f}" for v in lsq_fraction)
        + f"  | max |closure resid| = {np.abs(closure_resid).max():.3f}"
        + f", max |offset resid| = {np.abs(offset_resid).max():.4f}"
    )
    print(
        "End members vs references: correlation "
        + " ".join(f"{v:.3f}" for v in endmember_corr)
        + ", best shift (ppm) "
        + " ".join(f"{v:+.4f}" for v in endmember_shift)
        + f"; scales {scale[0]:.3f} {scale[1]:.3f}, offsets {offsets[0]:.3f} {offsets[1]:.3f}"
    )
    print(
        f"Least squares: k = {lsq_fit['k']:.4f} +/- {lsq_fit['k_err']:.4f}, "
        f"x0 = {lsq_fit['x0']:.3f}, x_inf = {lsq_fit['x_inf']:.3f}"
    )
    for label, comp in comparisons.items():
        fit = comp["first_order_fit"]
        print(
            f"{label}: k = {fit['k']:.4f} +/- {fit['k_err']:.4f} "
            f"({comp['k_relative_error_vs_reference_free'] * 100:+.1f}% vs ref-free), "
            f"x0 = {fit['x0']:.3f}, x_inf = {fit['x_inf']:.3f}, "
            f"max |dx| vs LSQ = {comp['max_abs_diff_vs_lsq']:.3f}, "
            f"monotonic = {comp['monotonic']}"
        )
    print(f"Validation -> {out_dir / 'validation.json'}, {out_dir / 'validation.png'}")

    from src.utils.config_utils import save_skill_inputs

    save_skill_inputs(args, str(out_dir))


if __name__ == "__main__":
    main()
