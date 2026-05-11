"""
Plot and compare NMR spectra: overlays, stacked time-series, and deconvolution diagnostics.

Usage:
    # Overlay multiple spectra
    python plot.py spectrum1.csv spectrum2.csv --labels "Mixture" "Ref A" \\
        --title "Comparison" --output overlay.png

    # Stacked time-series plot
    python plot.py t0.csv t1.csv t2.csv --stacked \\
        --labels 0min 30min 60min --output time_series.png

Requirements:
    # Env: nmr-agent
    - Required packages: numpy, matplotlib
"""

import argparse
import pathlib
import sys
import os

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams.update({"font.size": 14})

sys.path.insert(0, os.path.dirname(__file__))
from spectra import load_spectrum


def _save_fig(fig, out_path: pathlib.Path) -> None:
    """Save figure as both .png and .svg per plot-standards.md."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path.with_suffix(".png"), dpi=150, bbox_inches="tight")
    fig.savefig(out_path.with_suffix(".svg"), bbox_inches="tight")
    plt.close(fig)


def plot_overlay(
    spectra: list,
    labels: list,
    title: str,
    out_path: pathlib.Path,
    ppm_range: tuple = None,
) -> None:
    """
    Overlay multiple NMR spectra on a single axes.

    Args:
        spectra: List of (ppm, intensity) tuples.
        labels: Legend labels for each spectrum.
        title: Plot title.
        out_path: Output file path (.png saved alongside .svg).
        ppm_range: Optional (ppm_min, ppm_max) tuple to restrict the x-axis.
    """
    fig, ax = plt.subplots(figsize=(10, 4))
    for i, ((ppm, intensity), label) in enumerate(zip(spectra, labels)):
        ax.plot(ppm, intensity, linewidth=2.5, label=label, color=f"C{i}")
    ax.invert_xaxis()
    ax.set_xlabel("Chemical shift (ppm)", fontweight="bold")
    ax.set_ylabel("Intensity (a.u.)", fontweight="bold")
    ax.set_title(title)
    ax.legend(frameon=False)
    ax.grid(True, linestyle="--", alpha=0.6)
    if ppm_range is not None:
        ax.set_xlim(ppm_range[1], ppm_range[0])  # inverted axis
    fig.tight_layout()
    _save_fig(fig, out_path)


def plot_stacked(
    spectra: list,
    labels: list,
    title: str,
    out_path: pathlib.Path,
    ppm_range: tuple = None,
) -> None:
    """
    Stack NMR spectra vertically (offset), useful for time-series visualization.

    Args:
        spectra: List of (ppm, intensity) tuples (time-ordered).
        labels: Labels for each spectrum (shown on y-axis).
        title: Plot title.
        out_path: Output file path.
        ppm_range: Optional (ppm_min, ppm_max) to restrict the x-axis.
    """
    n = len(spectra)
    fig, ax = plt.subplots(figsize=(10, max(5, 2 * n)))
    for i, ((ppm, intensity), label) in enumerate(zip(spectra, labels)):
        offset = i * (intensity.max() - intensity.min()) * 1.2
        ax.plot(ppm, intensity + offset, linewidth=2.5, color=f"C{i % 10}", label=label)
        ax.text(ppm.max() + 0.05, offset + intensity.mean(), label, fontsize=10, va="center")
    ax.invert_xaxis()
    ax.set_xlabel("Chemical shift (ppm)", fontweight="bold")
    ax.set_title(title)
    ax.set_yticks([])
    ax.legend(frameon=False)
    ax.grid(True, linestyle="--", alpha=0.6)
    if ppm_range is not None:
        ax.set_xlim(ppm_range[1], ppm_range[0])
    fig.tight_layout()
    _save_fig(fig, out_path)


def plot_deconvolution(
    mix_arr: np.ndarray,
    comp_arrays: list,
    names: list,
    proportions: list,
    wasserstein_distance: float,
    out_path: pathlib.Path,
) -> None:
    """
    Multi-panel deconvolution diagnostic plot.

    Panels (top to bottom):
      - Mixture spectrum
      - One panel per component (scaled by proportion)
      - Fit vs mixture overlay with residual

    Args:
        mix_arr: (M, 2) array of mixture (ppm, intensity).
        comp_arrays: List of (N_i, 2) arrays for each component.
        names: Component names.
        proportions: Estimated mole fractions per component.
        wasserstein_distance: Fit quality metric.
        out_path: Output path (saves .png and .svg).
    """
    mix_ppm = mix_arr[:, 0]
    mix_int = mix_arr[:, 1]
    order = np.argsort(mix_ppm)
    mix_ppm, mix_int = mix_ppm[order], mix_int[order]

    n_comp = len(comp_arrays)
    colors = [f"C{i + 1}" for i in range(n_comp)]

    # Interpolate components onto mixture grid
    comp_on_grid = []
    for arr in comp_arrays:
        p, intens = arr[:, 0], arr[:, 1]
        o = np.argsort(p)
        comp_on_grid.append(np.interp(mix_ppm, p[o], intens[o], left=0.0, right=0.0))

    # Scale each component by its proportion
    mix_max = mix_int.max() if mix_int.max() != 0 else 1.0
    scaled = []
    for comp_int, prop in zip(comp_on_grid, proportions):
        comp_max = comp_int.max() if comp_int.max() != 0 else 1.0
        scaled.append(comp_int * (prop * mix_max / comp_max))

    fit = sum(scaled)
    residual = mix_int - fit

    out_path = pathlib.Path(out_path)

    # --- Figure 1: Deconvolution panels (crude + components) ---
    n_rows = 1 + n_comp
    fig, axes = plt.subplots(n_rows, 1, figsize=(11, 3 * n_rows), sharex=True)
    if n_rows == 1:
        axes = [axes]

    # Top panel: crude spectrum
    axes[0].plot(mix_ppm, mix_int, color="black", lw=2.5, label="Crude")
    axes[0].axhline(0, color="gray", lw=0.4)
    axes[0].set_ylabel("Intensity", fontweight="bold")
    axes[0].legend(frameon=False)
    axes[0].grid(True, linestyle="--", alpha=0.6)
    axes[0].set_title("NMR Mixture Deconvolution")

    # Component panels
    for i, (name, sc, color) in enumerate(zip(names, scaled, colors)):
        ax = axes[1 + i]
        ax.plot(mix_ppm, sc, color=color, lw=2.5,
                label=f"{name}  ({proportions[i] * 100:.1f}%)")
        ax.axhline(0, color="gray", lw=0.4)
        ax.set_ylabel("Intensity", fontweight="bold")
        ax.legend(frameon=False)
        ax.grid(True, linestyle="--", alpha=0.6)

    axes[-1].set_xlabel("Chemical shift (ppm)", fontweight="bold")
    axes[-1].invert_xaxis()
    fig.tight_layout()
    _save_fig(fig, out_path)

    # --- Figure 2: Fit vs Crude (separate, wider for detail) ---
    fig2, ax_fit = plt.subplots(figsize=(12, 5))
    ax_fit.plot(mix_ppm, mix_int, color="black", lw=2.5, alpha=0.5, label="Crude")
    ax_fit.plot(mix_ppm, fit, color="red", lw=2.5, linestyle="--", label="Fit (sum)")
    ax_fit.fill_between(mix_ppm, residual, 0, color="gray", alpha=0.3, label="Residual")
    ax_fit.axhline(0, color="gray", lw=0.4)
    ax_fit.set_ylabel("Intensity", fontweight="bold")
    ax_fit.set_xlabel("Chemical shift (ppm)", fontweight="bold")
    ax_fit.legend(frameon=False)
    ax_fit.grid(True, linestyle="--", alpha=0.6)
    ax_fit.set_title(f"Fit vs Crude  (Wasserstein distance = {wasserstein_distance:.5f})")
    ax_fit.invert_xaxis()
    fig2.tight_layout()
    fit_path = out_path.with_name(out_path.stem + "_fit")
    _save_fig(fig2, fit_path)


def main():
    ap = argparse.ArgumentParser(description="Plot and compare NMR spectra.")
    ap.add_argument("spectra", nargs="+", help="Input .csv or .xy spectrum files")
    ap.add_argument("--labels", nargs="+", help="Legend labels (defaults to file stems)")
    ap.add_argument("--title", default="NMR Spectra", help="Plot title")
    ap.add_argument("--output", default="nmr_plot.png", help="Output file path")
    ap.add_argument(
        "--stacked", action="store_true",
        help="Use stacked (offset) layout instead of overlay",
    )
    ap.add_argument("--ppm_min", type=float, default=None, help="Minimum ppm to display")
    ap.add_argument("--ppm_max", type=float, default=None, help="Maximum ppm to display")
    args = ap.parse_args()

    spectra = [load_spectrum(p) for p in args.spectra]
    labels = (
        args.labels
        if args.labels and len(args.labels) == len(args.spectra)
        else [pathlib.Path(p).stem for p in args.spectra]
    )
    ppm_range = (
        (args.ppm_min, args.ppm_max)
        if args.ppm_min is not None and args.ppm_max is not None
        else None
    )
    out_path = pathlib.Path(args.output)

    if args.stacked:
        plot_stacked(spectra, labels, args.title, out_path, ppm_range)
    else:
        plot_overlay(spectra, labels, args.title, out_path, ppm_range)
    print(f"Plot saved -> {out_path.with_suffix('.png')}, {out_path.with_suffix('.svg')}")

    # Save input configs for reproducibility
    from src.utils.config_utils import save_skill_inputs
    save_skill_inputs(args, args.output)


if __name__ == "__main__":
    main()
