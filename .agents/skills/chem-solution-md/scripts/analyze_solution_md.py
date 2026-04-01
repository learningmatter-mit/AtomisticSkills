"""
Analyze solution-phase MD trajectories.

Computes radial distribution functions (RDFs), coordination numbers,
density convergence, and mean-square displacement (MSD) from an ASE
trajectory of a solvated system.

Usage:
    python analyze_solution_md.py --trajectory md/trajectory.traj \\
        --box_metadata solvation_box/box_metadata.json \\
        --rdf_pairs "Na-O,Cl-O" --output_dir analysis

Requirements:
    - Conda environment: base-agent
    - Required packages: ase, numpy, matplotlib, pymatgen
"""

import argparse
import json
import os
from pathlib import Path
from typing import Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from ase.io import read as ase_read
from ase.io.trajectory import Trajectory


def compute_rdf(
    trajectory_path: str,
    element_pair: tuple[str, str],
    rmax: float = 8.0,
    nbins: int = 200,
    start_frame: int = 0,
    stride: int = 1,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Compute the radial distribution function g(r) for a pair of elements.

    Uses a direct histogram approach over trajectory frames.

    Args:
        trajectory_path: Path to ASE .traj file.
        element_pair: Tuple of (element1, element2) for the pair correlation.
        rmax: Maximum distance in Å.
        nbins: Number of bins.
        start_frame: First frame to include.
        stride: Frame stride.

    Returns:
        Tuple of (r_values, g_of_r) arrays.
    """
    traj = Trajectory(trajectory_path, "r")
    frames = list(range(start_frame, len(traj), stride))

    dr = rmax / nbins
    r_edges = np.linspace(0, rmax, nbins + 1)
    r_centers = 0.5 * (r_edges[:-1] + r_edges[1:])
    hist = np.zeros(nbins)

    el1, el2 = element_pair
    n_frames_used = 0

    for frame_idx in frames:
        atoms = traj[frame_idx]
        cell = atoms.get_cell()
        volume = atoms.get_volume()
        positions = atoms.get_positions()
        symbols = atoms.get_chemical_symbols()

        indices_1 = [i for i, s in enumerate(symbols) if s == el1]
        indices_2 = [i for i, s in enumerate(symbols) if s == el2]

        if len(indices_1) == 0 or len(indices_2) == 0:
            continue

        n_frames_used += 1

        # Compute pair distances with minimum image convention
        for i in indices_1:
            for j in indices_2:
                if i == j:
                    continue
                delta = positions[j] - positions[i]
                # Apply minimum image convention for orthorhombic cells
                for dim in range(3):
                    cell_length = cell[dim, dim]
                    if cell_length > 0:
                        delta[dim] -= cell_length * round(delta[dim] / cell_length)
                dist = np.linalg.norm(delta)
                if dist < rmax:
                    bin_idx = int(dist / dr)
                    if bin_idx < nbins:
                        hist[bin_idx] += 1

    traj.close()

    if n_frames_used == 0:
        return r_centers, np.zeros(nbins)

    # Normalize: g(r) = hist / (N_frames * N_1 * rho_2 * 4*pi*r^2*dr)
    # where rho_2 = N_2 / V
    # Get counts from last frame
    atoms_last = ase_read(trajectory_path, index=-1)
    symbols_last = atoms_last.get_chemical_symbols()
    n1 = sum(1 for s in symbols_last if s == el1)
    n2 = sum(1 for s in symbols_last if s == el2)
    volume = atoms_last.get_volume()

    # If el1 == el2, we count ordered pairs (i != j)
    if el1 == el2:
        rho = (n2 - 1) / volume
    else:
        rho = n2 / volume

    shell_volumes = 4.0 * np.pi * r_centers ** 2 * dr
    ideal_count = n1 * rho * shell_volumes * n_frames_used
    g_r = np.divide(hist, ideal_count, out=np.zeros_like(hist), where=ideal_count > 0)

    return r_centers, g_r


def compute_coordination_number(
    r_values: np.ndarray,
    g_r: np.ndarray,
    rho: float,
    r_cutoff: Optional[float] = None,
) -> tuple[float, float]:
    """
    Compute the coordination number from the RDF by integration.

    CN = 4*pi*rho * integral_0^r_cutoff r^2 * g(r) dr

    If r_cutoff is not given, uses the first minimum after the first peak.

    Args:
        r_values: Radial distance array.
        g_r: RDF g(r) array.
        rho: Number density of the second element (atoms/ų).
        r_cutoff: Integration cutoff in Å. Auto-detected if None.

    Returns:
        Tuple of (coordination_number, r_cutoff_used).
    """
    if r_cutoff is None:
        # Find first peak
        peak_idx = None
        for i in range(1, len(g_r) - 1):
            if g_r[i] > g_r[i - 1] and g_r[i] > g_r[i + 1] and g_r[i] > 1.0:
                peak_idx = i
                break

        if peak_idx is None:
            # No clear peak found, use 3.5 Å as default
            r_cutoff = 3.5
        else:
            # Find first minimum after peak
            for i in range(peak_idx + 1, len(g_r) - 1):
                if g_r[i] < g_r[i - 1] and g_r[i] < g_r[i + 1]:
                    r_cutoff = r_values[i]
                    break
            else:
                r_cutoff = r_values[min(peak_idx + 20, len(r_values) - 1)]

    # Integrate
    dr = r_values[1] - r_values[0]
    mask = r_values <= r_cutoff
    cn = 4.0 * np.pi * rho * np.sum(r_values[mask] ** 2 * g_r[mask] * dr)

    return float(cn), float(r_cutoff)


def compute_density_vs_time(
    trajectory_path: str,
    total_mass_amu: float,
    log_interval_fs: float = 10.0,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Compute the system density as a function of time from the trajectory.

    Args:
        trajectory_path: Path to ASE .traj file.
        total_mass_amu: Total mass in atomic mass units.
        log_interval_fs: Time interval between frames in femtoseconds.

    Returns:
        Tuple of (time_ps, density_g_cm3) arrays.
    """
    traj = Trajectory(trajectory_path, "r")
    n_frames = len(traj)

    densities = []
    times = []

    amu_to_gram = 1.66053906660e-24  # 1 amu in grams
    angstrom_to_cm = 1e-8

    for i in range(n_frames):
        atoms = traj[i]
        volume_ang3 = atoms.get_volume()
        volume_cm3 = volume_ang3 * (angstrom_to_cm ** 3)
        mass_g = total_mass_amu * amu_to_gram
        density = mass_g / volume_cm3
        densities.append(density)
        times.append(i * log_interval_fs / 1000.0)  # Convert to ps

    traj.close()
    return np.array(times), np.array(densities)


def compute_msd(
    trajectory_path: str,
    target_element: str,
    start_frame: int = 0,
    stride: int = 1,
    log_interval_fs: float = 10.0,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Compute the mean-square displacement for a target element.

    MSD(t) = <|r(t) - r(0)|^2> averaged over all atoms of the target element.

    Args:
        trajectory_path: Path to ASE .traj file.
        target_element: Element symbol to track.
        start_frame: Starting frame index.
        stride: Frame stride.
        log_interval_fs: Time between frames in fs.

    Returns:
        Tuple of (time_ps, msd_ang2) arrays.
    """
    traj = Trajectory(trajectory_path, "r")
    frames = list(range(start_frame, len(traj), stride))

    if len(frames) == 0:
        traj.close()
        return np.array([]), np.array([])

    # Get reference positions
    atoms_ref = traj[frames[0]]
    symbols = atoms_ref.get_chemical_symbols()
    target_indices = [i for i, s in enumerate(symbols) if s == target_element]

    if len(target_indices) == 0:
        traj.close()
        return np.array([]), np.array([])

    ref_positions = atoms_ref.get_positions()[target_indices]

    times = []
    msd_values = []
    prev_positions = ref_positions.copy()

    # Unwrap positions across PBC
    unwrapped = ref_positions.copy()

    for fidx, frame_idx in enumerate(frames):
        atoms = traj[frame_idx]
        cell = atoms.get_cell()
        curr_positions = atoms.get_positions()[target_indices]

        if fidx > 0:
            # Unwrap: correct for periodic boundary jumps
            delta = curr_positions - prev_positions
            for dim in range(3):
                cell_length = cell[dim, dim]
                if cell_length > 0:
                    delta[:, dim] -= cell_length * np.round(delta[:, dim] / cell_length)
            unwrapped += delta

        displacement = unwrapped - ref_positions
        msd = np.mean(np.sum(displacement ** 2, axis=1))
        msd_values.append(msd)
        times.append(fidx * stride * log_interval_fs / 1000.0)

        prev_positions = curr_positions.copy()

    traj.close()
    return np.array(times), np.array(msd_values)


def parse_rdf_pairs(pairs_str: str) -> list[tuple[str, str]]:
    """
    Parse RDF pair specification string.

    Args:
        pairs_str: Comma-separated element pairs, e.g. "Na-O,Cl-O,O-H"

    Returns:
        List of (element1, element2) tuples.
    """
    pairs = []
    for pair in pairs_str.split(","):
        pair = pair.strip()
        elements = pair.split("-")
        if len(elements) != 2:
            raise ValueError(f"Invalid pair format: {pair}. Expected 'El1-El2'")
        pairs.append((elements[0].strip(), elements[1].strip()))
    return pairs


def analyze_solution_md(
    trajectory_path: str,
    rdf_pairs: list[tuple[str, str]],
    output_dir: str,
    rmax: float = 8.0,
    nbins: int = 200,
    start_frame: int = 0,
    stride: int = 1,
    log_interval_fs: float = 10.0,
    msd_elements: Optional[list[str]] = None,
) -> dict:
    """
    Run full solution MD analysis.

    Args:
        trajectory_path: Path to ASE .traj file.
        rdf_pairs: List of element pairs for RDF computation.
        output_dir: Output directory.
        rmax: Max distance for RDF in Å.
        nbins: Number of RDF bins.
        start_frame: Starting frame for analysis.
        stride: Frame stride.
        log_interval_fs: Time between frames in fs.
        msd_elements: Elements for MSD calculation.

    Returns:
        Dictionary with all analysis results.
    """
    os.makedirs(output_dir, exist_ok=True)
    results = {"rdf": {}, "coordination": {}, "msd": {}}

    # --- RDFs ---
    print("Computing RDFs...")
    fig_rdf, axes = plt.subplots(len(rdf_pairs), 1, figsize=(8, 4 * len(rdf_pairs)),
                                  squeeze=False)

    atoms_last = ase_read(trajectory_path, index=-1)
    symbols = atoms_last.get_chemical_symbols()
    volume = atoms_last.get_volume()

    for idx, (el1, el2) in enumerate(rdf_pairs):
        print(f"  Computing g({el1}-{el2})...")
        r, g_r = compute_rdf(
            trajectory_path, (el1, el2), rmax=rmax, nbins=nbins,
            start_frame=start_frame, stride=stride,
        )

        # Find first peak
        peak_r = None
        peak_g = None
        for i in range(1, len(g_r) - 1):
            if g_r[i] > g_r[i - 1] and g_r[i] > g_r[i + 1] and g_r[i] > 1.0:
                peak_r = float(r[i])
                peak_g = float(g_r[i])
                break

        # Coordination number
        n2 = sum(1 for s in symbols if s == el2)
        rho2 = n2 / volume
        cn, cn_cutoff = compute_coordination_number(r, g_r, rho2)

        results["rdf"][f"{el1}-{el2}"] = {
            "r": r.tolist(),
            "g_r": g_r.tolist(),
            "first_peak_r_angstrom": peak_r,
            "first_peak_g": peak_g,
        }
        results["coordination"][f"{el1}-{el2}"] = {
            "coordination_number": round(cn, 2),
            "cutoff_angstrom": round(cn_cutoff, 2),
        }

        print(f"    First peak: r={peak_r} Å, g(r)={peak_g}")
        print(f"    Coordination number: {cn:.2f} (cutoff: {cn_cutoff:.2f} Å)")

        # Plot
        ax = axes[idx, 0]
        ax.plot(r, g_r, "b-", linewidth=1.5)
        ax.axhline(y=1.0, color="gray", linestyle="--", alpha=0.5)
        if peak_r is not None:
            ax.axvline(x=peak_r, color="red", linestyle=":", alpha=0.5,
                       label=f"Peak: {peak_r:.2f} Å")
        ax.set_xlabel("r (Å)", fontsize=12)
        ax.set_ylabel(f"g({el1}-{el2})(r)", fontsize=12)
        ax.set_title(f"{el1}-{el2} RDF (CN={cn:.1f})", fontsize=13)
        ax.legend()
        ax.set_xlim(0, rmax)

    plt.tight_layout()
    rdf_plot_path = Path(output_dir) / "rdf_plots.png"
    fig_rdf.savefig(rdf_plot_path, dpi=150, bbox_inches="tight")
    plt.close(fig_rdf)
    print(f"  Saved RDF plot: {rdf_plot_path}")

    # --- Density convergence ---
    print("Computing density convergence...")
    total_mass_amu = sum(atoms_last.get_masses())
    time_ps, density = compute_density_vs_time(
        trajectory_path, total_mass_amu, log_interval_fs
    )

    if len(density) > 0:
        avg_density = float(np.mean(density[-len(density) // 4:]))  # Last 25%
        results["density"] = {
            "average_g_cm3": round(avg_density, 4),
            "std_g_cm3": round(float(np.std(density[-len(density) // 4:])), 4),
        }
        print(f"  Average density (last 25%): {avg_density:.4f} g/cm³")

        fig_dens, ax_dens = plt.subplots(figsize=(8, 4))
        ax_dens.plot(time_ps, density, "b-", linewidth=0.8)
        ax_dens.axhline(y=avg_density, color="red", linestyle="--",
                        label=f"Avg: {avg_density:.4f} g/cm³")
        ax_dens.set_xlabel("Time (ps)", fontsize=12)
        ax_dens.set_ylabel("Density (g/cm³)", fontsize=12)
        ax_dens.set_title("Density Convergence", fontsize=13)
        ax_dens.legend()
        plt.tight_layout()
        density_plot_path = Path(output_dir) / "density_convergence.png"
        fig_dens.savefig(density_plot_path, dpi=150, bbox_inches="tight")
        plt.close(fig_dens)
        print(f"  Saved density plot: {density_plot_path}")

    # --- MSD ---
    if msd_elements:
        print("Computing MSD...")
        fig_msd, ax_msd = plt.subplots(figsize=(8, 4))

        for el in msd_elements:
            print(f"  Computing MSD for {el}...")
            time_msd, msd_vals = compute_msd(
                trajectory_path, el, start_frame=start_frame,
                stride=stride, log_interval_fs=log_interval_fs,
            )
            if len(msd_vals) > 0:
                results["msd"][el] = {
                    "time_ps": time_msd.tolist(),
                    "msd_ang2": msd_vals.tolist(),
                }
                ax_msd.plot(time_msd, msd_vals, label=el, linewidth=1.5)

        ax_msd.set_xlabel("Time (ps)", fontsize=12)
        ax_msd.set_ylabel("MSD (Å²)", fontsize=12)
        ax_msd.set_title("Mean Square Displacement", fontsize=13)
        ax_msd.legend()
        plt.tight_layout()
        msd_plot_path = Path(output_dir) / "msd_plot.png"
        fig_msd.savefig(msd_plot_path, dpi=150, bbox_inches="tight")
        plt.close(fig_msd)
        print(f"  Saved MSD plot: {msd_plot_path}")

    # --- Save results ---
    results_path = Path(output_dir) / "solution_analysis.json"
    # Convert numpy arrays for JSON serialization
    with open(results_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"  Saved analysis results: {results_path}")

    return results


def main() -> None:
    """Main entry point for solution MD analysis."""
    parser = argparse.ArgumentParser(
        description="Analyze solution-phase MD trajectories (RDFs, coordination, density, MSD)."
    )
    parser.add_argument(
        "--trajectory", type=str, required=True,
        help="Path to ASE .traj trajectory file"
    )
    parser.add_argument(
        "--rdf_pairs", type=str, required=True,
        help="Comma-separated element pairs for RDF, e.g. 'Na-O,Cl-O'"
    )
    parser.add_argument(
        "--output_dir", type=str, required=True,
        help="Output directory for analysis results"
    )
    parser.add_argument(
        "--rmax", type=float, default=8.0,
        help="Maximum distance for RDF in Å (default: 8.0)"
    )
    parser.add_argument(
        "--nbins", type=int, default=200,
        help="Number of RDF bins (default: 200)"
    )
    parser.add_argument(
        "--start_frame", type=int, default=0,
        help="First trajectory frame to analyze (default: 0)"
    )
    parser.add_argument(
        "--stride", type=int, default=1,
        help="Frame stride for analysis (default: 1)"
    )
    parser.add_argument(
        "--log_interval_fs", type=float, default=10.0,
        help="Time interval between trajectory frames in fs (default: 10.0)"
    )
    parser.add_argument(
        "--msd_elements", type=str, default=None,
        help="Comma-separated elements for MSD calculation (e.g. 'Na,Cl')"
    )

    args = parser.parse_args()

    rdf_pairs = parse_rdf_pairs(args.rdf_pairs)
    msd_elements = args.msd_elements.split(",") if args.msd_elements else None

    print("=" * 60)
    print("Solution MD Analysis")
    print("=" * 60)

    analyze_solution_md(
        trajectory_path=args.trajectory,
        rdf_pairs=rdf_pairs,
        output_dir=args.output_dir,
        rmax=args.rmax,
        nbins=args.nbins,
        start_frame=args.start_frame,
        stride=args.stride,
        log_interval_fs=args.log_interval_fs,
        msd_elements=msd_elements,
    )

    print("=" * 60)
    print("Analysis complete.")
    print("=" * 60)


if __name__ == "__main__":
    main()
