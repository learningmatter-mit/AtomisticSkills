"""
Compare a benchmark_mlips.py results file with the stored reference results.

Writes a CSV of ms/atom and MB/atom (ours vs reference) for every model and system
size present in both files, and a two-panel plot of the per-atom time.

Usage:
    python compare_with_reference.py speed_benchmark.yaml \
        ../../resources/speed_benchmark_dgx_spark.yaml --output-dir .

Requirements:
    - Environment: cpu
    - Required packages: pyyaml, matplotlib
"""

import argparse
import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import yaml  # noqa: E402

from src.utils.config_utils import save_skill_inputs  # noqa: E402

plt.rcParams.update({"font.size": 14})


def per_atom(entry: dict) -> dict[int, tuple[float, float]]:
    """
    Convert one model's results to per-atom metrics.

    Args:
        entry: Results of one model ('n_atoms', 'times' in s/step, 'memories' in GB).

    Returns:
        Mapping n_atoms -> (ms per atom per step, MB per atom).
    """
    return {
        n: (1000.0 * t / n, 1024.0 * m / n)
        for n, t, m in zip(entry["n_atoms"], entry["times"], entry["memories"])
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare MLIP speed results with a reference results file."
    )
    parser.add_argument("results", help="Results YAML written by benchmark_mlips.py")
    parser.add_argument("reference", help="Reference results YAML")
    parser.add_argument(
        "--output-dir", default=".", help="Where to write CSV and plots"
    )
    args = parser.parse_args()

    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    ours = yaml.safe_load(open(args.results))
    ref = yaml.safe_load(open(args.reference))
    models = [m for m in ours if m in ref and ours[m].get("n_atoms")]

    rows = []
    for m in models:
        o, r = per_atom(ours[m]), per_atom(ref[m])
        for n in sorted(set(o) & set(r)):
            rows.append(
                {
                    "model": m,
                    "n_atoms": n,
                    "ms_per_atom": round(o[n][0], 4),
                    "ref_ms_per_atom": round(r[n][0], 4),
                    "MB_per_atom": round(o[n][1], 3),
                    "ref_MB_per_atom": round(r[n][1], 3),
                }
            )
    with open(out / "comparison_vs_reference.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    colors = plt.get_cmap("tab10").colors
    fig, (ax_t, ax_m) = plt.subplots(2, 1, figsize=(6, 5), sharex=True)
    for i, m in enumerate(models):
        sel = [r for r in rows if r["model"] == m]
        n = [r["n_atoms"] for r in sel]
        c = colors[i % len(colors)]
        ax_t.plot(
            n, [r["ms_per_atom"] for r in sel], "o-", color=c, linewidth=2.5, label=m
        )
        ax_t.plot(n, [r["ref_ms_per_atom"] for r in sel], "s--", color=c, linewidth=1.5)
        ax_m.plot(n, [r["MB_per_atom"] for r in sel], "o-", color=c, linewidth=2.5)
        ax_m.plot(n, [r["ref_MB_per_atom"] for r in sel], "s--", color=c, linewidth=1.5)
    ax_t.set_yscale("log")
    ax_t.set_ylabel("ms / atom", fontweight="bold")
    ax_m.set_ylabel("MB / atom", fontweight="bold")
    ax_m.set_xlabel("Number of atoms", fontweight="bold")
    handles, labels = ax_t.get_legend_handles_labels()
    handles += [
        plt.Line2D([], [], color="k", marker="o", linewidth=2.5),
        plt.Line2D([], [], color="k", marker="s", linestyle="--", linewidth=1.5),
    ]
    labels += ["this run", "reference"]
    ax_m.legend(handles, labels, frameon=False, fontsize=8, loc="upper right")
    for ax in (ax_t, ax_m):
        ax.grid(False)
    plt.tight_layout()
    for suffix in (".png", ".svg"):
        plt.savefig(out / f"speed_vs_reference{suffix}", dpi=200, bbox_inches="tight")
    plt.close(fig)
    save_skill_inputs(args, str(out))
    for r in rows:
        print(r)


if __name__ == "__main__":
    main()
