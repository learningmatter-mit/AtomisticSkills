"""
Compare predict_nmr.py outputs against tabulated experimental 1H NMR signals.

For every compound listed in the literature table, the script
  1. matches each experimental signal to a predicted signal (Hungarian
     assignment on |delta_pred - delta_exp|, with a penalty for unequal nH),
  2. reads the simulated spectrum (<name>.xy) around each predicted signal and
     measures the number of resolved lines, the mean line spacing (Hz) and the
     integrated intensity (converted to a proton count),
  3. writes comparison.csv and plots the predicted spectra with the
     experimental shift positions marked (nmr_vs_literature.png / .svg).

Usage:
    venv/run cpu python skills/chem-nmr-predict/examples/ethyl_acetate_ethanol_cdcl3/compare_to_literature.py \
        --pred_dir skills/chem-nmr-predict/examples/ethyl_acetate_ethanol_cdcl3 \
        --literature skills/chem-nmr-predict/examples/ethyl_acetate_ethanol_cdcl3/literature_cdcl3.csv

Requirements:
    - Environment: cpu
    - Required packages: numpy, pandas, scipy, matplotlib
"""

import argparse
import json
import pathlib

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment
from scipy.signal import find_peaks

plt.rcParams.update({"font.size": 14})

PRED_COLOR = "#2a78d6"
EXP_COLOR = "#eb6834"
TEXT_COLOR = "#52514e"


def load_xy(path: pathlib.Path) -> tuple[np.ndarray, np.ndarray]:
    """
    Load a two-column (ppm, intensity) spectrum and sort it by ascending ppm.

    Args:
        path: Path to the tab-separated .xy file written by predict_nmr.py.

    Returns:
        Tuple (ppm, intensity) of 1-D arrays sorted by ascending ppm.
    """
    arr = np.loadtxt(path)
    order = np.argsort(arr[:, 0])
    return arr[order, 0], arr[order, 1]


def match_signals(lit: pd.DataFrame, pred: pd.DataFrame) -> dict[int, int]:
    """
    Assign experimental signals to predicted signals.

    Args:
        lit: Experimental signals with columns shift_ppm and nH.
        pred: Predicted signals with columns shift_ppm and nH.

    Returns:
        Mapping {literature row index: predicted row index}. Experimental
        signals left without a predicted partner are absent from the mapping.
    """
    cost = np.abs(lit["shift_ppm"].values[:, None] - pred["shift_ppm"].values[None, :])
    cost = cost + 10.0 * (lit["nH"].values[:, None] != pred["nH"].values[None, :])
    rows, cols = linear_sum_assignment(cost)
    return {int(lit.index[r]): int(pred.index[c]) for r, c in zip(rows, cols)}


def measure_multiplet(
    ppm: np.ndarray,
    intensity: np.ndarray,
    center_ppm: float,
    window_ppm: float,
    field_mhz: float,
) -> dict:
    """
    Measure the simulated multiplet around a predicted shift.

    Args:
        ppm: Spectrum ppm axis (ascending).
        intensity: Spectrum intensities.
        center_ppm: Predicted chemical shift of the signal.
        window_ppm: Half-width of the integration / peak-picking window.
        field_mhz: Spectrometer frequency used to convert ppm to Hz.

    Returns:
        Dict with keys n_lines, spacing_Hz (mean spacing of adjacent lines,
        NaN for a singlet) and integral (trapezoidal area in the window).
    """
    mask = np.abs(ppm - center_ppm) <= window_ppm
    x, y = ppm[mask], intensity[mask]
    peaks, _ = find_peaks(y, height=0.05 * y.max())
    step = x[1] - x[0]
    refined = []
    for i in peaks:
        y0, y1, y2 = y[i - 1], y[i], y[i + 1]
        refined.append(x[i] + 0.5 * step * (y0 - y2) / (y0 - 2.0 * y1 + y2))
    refined = np.array(refined)
    spacing = (
        (refined.max() - refined.min()) * field_mhz / (len(refined) - 1)
        if len(refined) > 1
        else float("nan")
    )
    return {
        "n_lines": int(len(refined)),
        "spacing_Hz": float(spacing),
        "integral": float(np.trapezoid(y, x)),
    }


def compare_compound(
    name: str,
    lit: pd.DataFrame,
    pred_dir: pathlib.Path,
    window_ppm: float,
    field_mhz: float,
) -> tuple[pd.DataFrame, tuple[np.ndarray, np.ndarray]]:
    """
    Build the per-signal comparison table for one compound.

    Args:
        name: Compound name used as file stem by predict_nmr.py.
        lit: Experimental signals for this compound.
        pred_dir: Directory holding <name>_signals.csv and <name>.xy.
        window_ppm: Half-width of the multiplet window in ppm.
        field_mhz: Spectrometer frequency in MHz.

    Returns:
        Tuple (comparison DataFrame, (ppm, intensity) of the simulated spectrum).
    """
    pred = pd.read_csv(pred_dir / f"{name}_signals.csv", dtype={"J_Hz": str})
    ppm, intensity = load_xy(pred_dir / f"{name}.xy")
    mapping = match_signals(lit, pred)

    measured = {
        j: measure_multiplet(
            ppm, intensity, pred.loc[j, "shift_ppm"], window_ppm, field_mhz
        )
        for j in pred.index
    }
    total_area = sum(m["integral"] for m in measured.values())
    total_h = pred["nH"].sum()

    rows = []
    for i, lrow in lit.iterrows():
        row = {
            "compound": name,
            "group": lrow["group"],
            "nH_exp": int(lrow["nH"]),
            "shift_exp_ppm": lrow["shift_ppm"],
            "mult_exp": lrow["multiplicity"],
            "J_exp_Hz": lrow["J_Hz"],
        }
        if i in mapping:
            j = mapping[i]
            m = measured[j]
            row.update(
                {
                    "shift_pred_ppm": pred.loc[j, "shift_ppm"],
                    "mult_pred": pred.loc[j, "multiplicity"],
                    "J_pred_Hz": pred.loc[j, "J_Hz"],
                    "nH_pred": int(pred.loc[j, "nH"]),
                    "abs_err_ppm": round(
                        abs(pred.loc[j, "shift_ppm"] - lrow["shift_ppm"]), 3
                    ),
                    "sim_lines": m["n_lines"],
                    "sim_spacing_Hz": round(m["spacing_Hz"], 2),
                    "sim_integral_H": round(m["integral"] / total_area * total_h, 2),
                }
            )
        rows.append(row)
    return pd.DataFrame(rows), (ppm, intensity)


def plot_comparison(
    spectra: dict,
    table: pd.DataFrame,
    out_stem: pathlib.Path,
    ppm_range: tuple[float, float],
    label_threshold_ppm: float = 0.1,
) -> None:
    """
    Plot predicted spectra (one panel per compound) with experimental shifts marked.

    Args:
        spectra: {compound: (ppm, intensity)}.
        table: Comparison table produced by compare_compound.
        out_stem: Output path without suffix; .png and .svg are written.
        ppm_range: (ppm_min, ppm_max) shown on the inverted x-axis.
        label_threshold_ppm: Shift errors at or above this value are labelled.
    """
    names = list(spectra)
    fig, axes = plt.subplots(len(names), 1, figsize=(6, 5), sharex=True)
    axes = np.atleast_1d(axes)
    for ax, name in zip(axes, names):
        ppm, intensity = spectra[name]
        ax.plot(ppm, intensity, color=PRED_COLOR, linewidth=2.5)
        for _, row in table[table["compound"] == name].iterrows():
            predicted = not pd.isna(row["shift_pred_ppm"])
            ax.axvline(
                row["shift_exp_ppm"],
                color=EXP_COLOR,
                linestyle="--",
                linewidth=1.5,
                ymax=0.88,
            )
            ax.plot(
                row["shift_exp_ppm"],
                1.12,
                marker="v",
                markersize=9,
                color=EXP_COLOR,
                markerfacecolor=EXP_COLOR if predicted else "white",
                linestyle="none",
            )
            if not predicted:
                ax.annotate(
                    row["group"],
                    (row["shift_exp_ppm"], 0.55),
                    xytext=(-6, 0),
                    textcoords="offset points",
                    ha="right",
                    fontsize=10,
                    color=TEXT_COLOR,
                )
            elif row["abs_err_ppm"] >= label_threshold_ppm:
                delta = row["shift_pred_ppm"] - row["shift_exp_ppm"]
                # The x-axis is inverted: an upfield prediction lies to the right on screen.
                side = 1 if delta < 0 else -1
                ax.annotate(
                    f"$\\Delta\\delta$ = {delta:+.2f}",
                    (row["shift_exp_ppm"], 0.85),
                    xytext=(6 * side, 0),
                    textcoords="offset points",
                    ha="left" if side > 0 else "right",
                    fontsize=10,
                    color=TEXT_COLOR,
                )
        ax.set_title(name.replace("_", " "), loc="left", fontsize=12)
        ax.set_ylim(0, 1.25)
        ax.set_yticks([0, 0.5, 1.0])
        ax.set_ylabel("Intensity", fontweight="bold")
        ax.grid(False)
    axes[-1].set_xlim(ppm_range[1], ppm_range[0])
    axes[-1].set_xlabel("Chemical shift (ppm)", fontweight="bold")
    handles = [
        Line2D(
            [], [], color=PRED_COLOR, linewidth=2.5, label="Predicted (SPINUS + nmrsim)"
        ),
        Line2D(
            [],
            [],
            color=EXP_COLOR,
            marker="v",
            markersize=9,
            linestyle="--",
            linewidth=1.5,
            label="Experimental, CDCl$_3$",
        ),
        Line2D(
            [],
            [],
            color=EXP_COLOR,
            marker="v",
            markersize=9,
            markerfacecolor="white",
            linestyle="none",
            label="Experimental, not predicted",
        ),
    ]
    plt.tight_layout()
    fig.legend(
        handles=handles,
        frameon=False,
        fontsize=9,
        loc="upper center",
        bbox_to_anchor=(0.5, 0.0),
        ncol=2,
    )
    plt.savefig(out_stem.with_suffix(".png"), dpi=200, bbox_inches="tight")
    plt.savefig(out_stem.with_suffix(".svg"), bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Compare predicted 1H NMR signals and spectra with tabulated experimental values."
    )
    ap.add_argument(
        "--pred_dir", required=True, help="Output directory of predict_nmr.py"
    )
    ap.add_argument(
        "--literature",
        required=True,
        help="CSV with columns compound, group, shift_ppm, multiplicity, J_Hz, nH",
    )
    ap.add_argument(
        "--window_ppm",
        type=float,
        default=0.1,
        help="Half-width (ppm) of the window used to pick and integrate each multiplet (default: 0.1)",
    )
    ap.add_argument(
        "--ppm_min",
        type=float,
        default=0.6,
        help="Lower ppm limit of the plot (default: 0.6)",
    )
    ap.add_argument(
        "--ppm_max",
        type=float,
        default=4.4,
        help="Upper ppm limit of the plot (default: 4.4)",
    )
    args = ap.parse_args()

    pred_dir = pathlib.Path(args.pred_dir)
    manifest = json.loads((pred_dir / "predictions.json").read_text())
    field_mhz = manifest["parameters"]["field_mhz"]
    lit_all = pd.read_csv(args.literature)

    tables, spectra = [], {}
    for name, lit in lit_all.groupby("compound", sort=False):
        table, spectrum = compare_compound(
            name, lit, pred_dir, args.window_ppm, field_mhz
        )
        tables.append(table)
        spectra[name] = spectrum
    table = pd.concat(tables, ignore_index=True)
    table = table.astype({"nH_pred": "Int64", "sim_lines": "Int64"})
    table.to_csv(pred_dir / "comparison.csv", index=False)

    print(table.to_string(index=False))
    matched = table.dropna(subset=["abs_err_ppm"])
    for name, sub in matched.groupby("compound", sort=False):
        print(
            f"MAE {name}: {sub['abs_err_ppm'].mean():.3f} ppm over {len(sub)} signals"
        )
    print(
        f"MAE all matched signals: {matched['abs_err_ppm'].mean():.3f} ppm over {len(matched)} signals"
    )
    unmatched = table[table["abs_err_ppm"].isna()]
    for _, row in unmatched.iterrows():
        print(
            f"Not predicted: {row['compound']} {row['group']} ({row['shift_exp_ppm']} ppm)"
        )

    plot_comparison(
        spectra, table, pred_dir / "nmr_vs_literature", (args.ppm_min, args.ppm_max)
    )
    print(
        f"Wrote {pred_dir / 'comparison.csv'} and {pred_dir / 'nmr_vs_literature'}.png/.svg"
    )


if __name__ == "__main__":
    main()
