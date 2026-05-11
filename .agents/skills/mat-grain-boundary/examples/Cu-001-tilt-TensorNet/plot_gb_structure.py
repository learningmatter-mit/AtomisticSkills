import argparse
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
from pymatgen.core import Structure

matplotlib.use("Agg")


def plot_gb_structure(cif_path: str, output_path: str):
    """
    Plots the XZ projection of a grain boundary bicrystal slab.
    Colors atoms based on their vertical (Z) position to highlight the two grains.
    """
    struct = Structure.from_file(cif_path)
    coords = np.array([s.coords for s in struct])

    # Project along Y axis: show X vs Z (the stacking direction)
    x = coords[:, 0]
    z = coords[:, 2]

    # Use a taller figure to match the slab dimensions
    fig, ax = plt.subplots(figsize=(5, 7))

    # Color atoms by z-height to visually separate the two grains
    # Z goes from 0 to 'c' lattice vector.
    z_norm = (z - z.min()) / (z.max() - z.min())
    sc = ax.scatter(
        x,
        z,
        c=z_norm,
        cmap="RdBu",
        s=180,
        edgecolors="#333",
        linewidths=0.6,
        zorder=3,
    )

    # GB planes are typically located at the periodic boundaries (z=0, z=c)
    # and exactly in the middle of the slab (z=c/2)
    lc = struct.lattice.c
    for gb_z in [lc / 2]:
        ax.axhline(gb_z, color="#E74C3C", lw=2.0, ls="--", label="GB plane")
    ax.axhline(0, color="#E74C3C", lw=2.0, ls="--")
    ax.axhline(lc, color="#E74C3C", lw=2.0, ls="--")

    ax.set_xlabel("x (Å)", fontsize=13, fontweight="bold")
    ax.set_ylabel("z (Å)", fontsize=13, fontweight="bold")
    ax.set_title(
        r"Cu Σ5 [001] Tilt GB — 36.87°" + "\n(Relaxed Structure)",
        fontsize=12,
        fontweight="bold",
    )
    
    # Position the legend outside the core structure visual
    ax.legend(fontsize=11, frameon=False, loc="upper right")
    
    # Adjust ranges to show a bit of padding around the unit cell
    ax.set_xlim(-0.5, x.max() + 0.5)
    ax.set_ylim(-1, lc + 1)
    ax.grid(True, linestyle="--", alpha=0.4)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    print(f"Saved structure visualization to {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Plot grain boundary structure projection.")
    parser.add_argument("--cif-path", type=str, required=True, help="Path to the relaxed grain boundary CIF file.")
    parser.add_argument("--output-path", type=str, default="gb_structure.png", help="Path to save the output PNG.")
    args = parser.parse_args()
    
    plot_gb_structure(args.cif_path, args.output_path)
