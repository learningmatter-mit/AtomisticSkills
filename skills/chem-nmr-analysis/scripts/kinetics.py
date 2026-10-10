#!/usr/bin/env python3
"""
NMR reaction kinetics: supervised deconvolution at each time point -> composition vs time.

Runs Wasserstein deconvolution on a series of crude spectra recorded at known times,
collects the estimated mole fractions and Wasserstein distances, saves a CSV table
and a kinetics plot.

Usage:
    venv/run cpu python kinetics.py \
        --refs ref_a.csv ref_b.csv \
        --timepoints t000min.csv t005min.csv t010min.csv \
        --times 0 5 10 \
        --time_unit min \
        --protons 18 18 \
        --names "borneol" "isoborneol" \
        --baseline_window 2.40 3.40 \
        --output_dir results/kinetics

Requirements: numpy, scipy (>= 1.7), matplotlib
"""

import argparse
import csv
import os
import pathlib
import sys

sys.path.insert(0, os.path.dirname(__file__))
from deconvolve import load_xy, deconvolve_spectra  # noqa: E402
from spectra import BASELINE_STATS, preprocess_spectrum  # noqa: E402


def save_kinetics_plot(
    times: list,
    time_unit: str,
    names: list,
    proportions_over_time: list[dict],
    wd_over_time: list[float],
    out_path: pathlib.Path,
) -> None:
    """
    Save a two-panel kinetics plot:
      - Top:    mole fraction vs time for each component.
      - Bottom: Wasserstein distance vs time (fit quality indicator).
    """
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update({"font.size": 14})

    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(8, 7), sharex=True, gridspec_kw={"height_ratios": [2, 1]}
    )

    for i, name in enumerate(names):
        fracs = [p.get(name, float("nan")) for p in proportions_over_time]
        ax1.plot(
            times,
            [f * 100 for f in fracs],
            "o-",
            color=f"C{i}",
            lw=2.5,
            markersize=5,
            label=name,
        )

    ax1.set_ylabel("Mole fraction (%)", fontweight="bold")
    ax1.set_ylim(-5, 105)
    ax1.axhline(0, color="gray", lw=0.4)
    ax1.legend(frameon=False)
    ax1.grid(True, linestyle="--", alpha=0.6)
    ax1.set_title("NMR Reaction Kinetics")

    ax2.semilogy(times, wd_over_time, "s--", color="gray", lw=2.5, markersize=4)
    ax2.set_ylabel("Wasserstein\ndistance", fontweight="bold")
    ax2.set_xlabel(f"Time ({time_unit})", fontweight="bold")
    ax2.set_title("Fit quality (lower = better)")
    ax2.grid(True, linestyle="--", alpha=0.6)

    fig.tight_layout()
    out_path = pathlib.Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path.with_suffix(".png"), dpi=150, bbox_inches="tight")
    fig.savefig(out_path.with_suffix(".svg"), bbox_inches="tight")
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser(
        description="Run NMR deconvolution at each time point and plot kinetics."
    )
    ap.add_argument(
        "--refs",
        nargs="+",
        required=True,
        help="Reference spectrum files for each component",
    )
    ap.add_argument(
        "--timepoints",
        nargs="+",
        required=True,
        help="Crude spectrum files ordered by time",
    )
    ap.add_argument(
        "--times",
        type=float,
        nargs="+",
        required=True,
        help="Time values matching --timepoints (e.g. 0 5 10 20)",
    )
    ap.add_argument("--time_unit", default="min", help="Time axis label (default: min)")
    ap.add_argument(
        "--protons", type=int, nargs="+", help="Proton counts per reference component"
    )
    ap.add_argument(
        "--names", nargs="+", help="Component names (must match number of --refs)"
    )
    baseline = ap.add_mutually_exclusive_group()
    baseline.add_argument(
        "--baseline_correct",
        action="store_true",
        help="Legacy: shift each spectrum so its minimum intensity = 0. "
        "Biased for noisy or offset spectra; prefer --baseline_window.",
    )
    baseline.add_argument(
        "--baseline_window",
        type=float,
        nargs=2,
        metavar=("LO", "HI"),
        default=None,
        help="Signal-free ppm window; its --baseline_stat is subtracted from every "
        "time point and reference, and negatives are clipped to 0.",
    )
    ap.add_argument(
        "--baseline_stat",
        choices=BASELINE_STATS,
        default="median",
        help="Baseline estimate in --baseline_window: median (noisy/offset "
        "spectra, default) or max (one-sided floors such as digitization residue).",
    )
    ap.add_argument(
        "--ppm_range",
        type=float,
        nargs=2,
        metavar=("LO", "HI"),
        default=None,
        help="Deconvolve only this ppm range (applied after baseline correction).",
    )
    ap.add_argument(
        "--kappa", type=float, default=0.25, help="Denoising penalty (default: 0.25)"
    )
    ap.add_argument("--mnova", action="store_true", help="Treat inputs as Mnova TSV")
    ap.add_argument(
        "--output_dir",
        default="kinetics_results",
        help="Directory for kinetics CSV and plot",
    )
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    if len(args.times) != len(args.timepoints):
        print(
            "ERROR: --times and --timepoints must have the same length.",
            file=sys.stderr,
        )
        sys.exit(1)

    out_dir = pathlib.Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    n_refs = len(args.refs)
    names = (
        args.names
        if args.names and len(args.names) == n_refs
        else [f"comp{i}" for i in range(n_refs)]
    )
    protons = args.protons if args.protons else [1] * n_refs
    if args.protons and len(args.protons) != n_refs:
        print("ERROR: --protons length must equal number of --refs.", file=sys.stderr)
        sys.exit(1)

    # Load reference spectra once
    prep = dict(
        baseline_correct=args.baseline_correct,
        baseline_window=args.baseline_window,
        baseline_stat=args.baseline_stat,
        ppm_range=args.ppm_range,
    )
    ref_arrays = [
        preprocess_spectrum(load_xy(p, mnova=args.mnova), **prep)[0] for p in args.refs
    ]

    proportions_over_time = []
    wd_over_time = []
    noise_over_time = []
    baseline_over_time = []

    for t, tp_path in zip(args.times, args.timepoints):
        if not args.quiet:
            print(f"  t={t} {args.time_unit}  <- {os.path.basename(tp_path)}", end="  ")
        try:
            mix_arr, mix_base = preprocess_spectrum(
                load_xy(tp_path, mnova=args.mnova), **prep
            )

            res = deconvolve_spectra(mix_arr, ref_arrays, protons, kappa=args.kappa)
            props_dict = dict(zip(names, res["proportions"]))
            wd = res["wasserstein_distance"]

            proportions_over_time.append(props_dict)
            wd_over_time.append(wd)
            noise_over_time.append(res["noise"])
            baseline_over_time.append(mix_base)

            if not args.quiet:
                frac_str = "  ".join(
                    f"{n}={props_dict.get(n, 0)*100:.1f}%" for n in names
                )
                print(f"{frac_str}  WD={wd:.5f}  noise={res['noise']:.3f}")
        except Exception as e:
            print(f"FAILED: {e}", file=sys.stderr)
            proportions_over_time.append({n: float("nan") for n in names})
            wd_over_time.append(float("nan"))
            noise_over_time.append(float("nan"))
            baseline_over_time.append(float("nan"))

    # Save CSV table
    csv_path = out_dir / "kinetics.csv"
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [f"time_{args.time_unit}"]
            + names
            + ["wasserstein_distance", "noise_fraction", "mixture_baseline"]
        )
        for t, props, wd, noise, base in zip(
            args.times,
            proportions_over_time,
            wd_over_time,
            noise_over_time,
            baseline_over_time,
        ):
            writer.writerow(
                [t] + [props.get(n, float("nan")) for n in names] + [wd, noise, base]
            )
    if not args.quiet:
        print(f"\nKinetics table -> {csv_path}")

    # Save plot
    plot_path = out_dir / "kinetics_plot"
    save_kinetics_plot(
        args.times,
        args.time_unit,
        names,
        proportions_over_time,
        wd_over_time,
        plot_path,
    )
    if not args.quiet:
        print(f"Kinetics plot  -> {plot_path}.png, {plot_path}.svg")

    # Save input configs for reproducibility
    from src.utils.config_utils import save_skill_inputs

    save_skill_inputs(args, args.output_dir)


if __name__ == "__main__":
    main()
