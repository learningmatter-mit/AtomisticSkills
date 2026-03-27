"""
Analytical validation of the lattice KMC engine.

Tests carriers doing random walks on a simple cubic lattice against the
exact result (dilute non-interacting limit):

    D_exact = a^2 * nu * exp(-E_b / (kB * T))

Derivation:
  - Each hop has rate k = nu * exp(-E_b / kBT)
  - z = 6 nearest neighbors on simple cubic => total rate R = 6k
  - After N hops: <r^2> = N * a^2  (uncorrelated steps)
  - D = <r^2> / (2*d*t) = R*a^2/6 = k*a^2

Uses 50 carriers on 1000 sites (5% occupancy) for ensemble averaging.
Compares against D_exact * (1 - c) to account for the blocking correction
at finite carrier density (occupied neighbors reject hops).

Usage:
    python validate_random_walk.py [--max_steps 500000] [--n_replicas 5]

Requirements:
    - numpy, matplotlib
    - run_lattice_kmc.py and analyze_kmc_msd.py from ../../scripts/
"""
from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from pathlib import Path
from typing import Tuple

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

K_B_EV_K = 8.617333262145e-5  # eV/K

SCRIPT_DIR = Path(__file__).resolve().parent.parent.parent
KMC_SCRIPT = SCRIPT_DIR / "scripts" / "run_lattice_kmc.py"


def build_simple_cubic_lattice(a: float, nx: int, ny: int, nz: int) -> dict:
    """Build a simple cubic lattice with periodic neighbors."""
    n_sites = nx * ny * nz
    cell = [[a * nx, 0.0, 0.0], [0.0, a * ny, 0.0], [0.0, 0.0, a * nz]]

    frac_coords = []
    index_map = {}
    idx = 0
    for ix in range(nx):
        for iy in range(ny):
            for iz in range(nz):
                frac_coords.append([ix / nx, iy / ny, iz / nz])
                index_map[(ix, iy, iz)] = idx
                idx += 1

    neighbors: list[list[dict]] = [[] for _ in range(n_sites)]
    directions = [(1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)]

    for ix in range(nx):
        for iy in range(ny):
            for iz in range(nz):
                i = index_map[(ix, iy, iz)]
                for dx, dy, dz in directions:
                    jx, jy, jz = ix + dx, iy + dy, iz + dz
                    sx, sy, sz = 0, 0, 0

                    if jx < 0:
                        jx += nx; sx = -1
                    elif jx >= nx:
                        jx -= nx; sx = 1
                    if jy < 0:
                        jy += ny; sy = -1
                    elif jy >= ny:
                        jy -= ny; sy = 1
                    if jz < 0:
                        jz += nz; sz = -1
                    elif jz >= nz:
                        jz -= nz; sz = 1

                    j = index_map[(jx, jy, jz)]
                    neighbors[i].append({"j": j, "shift": [sx, sy, sz]})

    return {
        "cell_A": cell,
        "site_element": "X",
        "site_frac_coords": frac_coords,
        "neighbors": neighbors,
        "cutoff_A": a * 1.01,
        "source_structure": f"simple_cubic_{nx}x{ny}x{nz}_a{a}",
    }


def d_exact(a: float, nu: float, barrier_eV: float, T: float, c: float = 0.0) -> float:
    """Exact diffusivity for random walk on simple cubic with blocking correction.

    D = a^2 * nu * exp(-Eb/kBT) * (1 - c)
    where c = carrier concentration (fraction of occupied sites).
    The (1-c) factor accounts for hop rejection when a neighbor is occupied.
    """
    return a**2 * nu * math.exp(-barrier_eV / (K_B_EV_K * T)) * (1.0 - c)


def compute_D_from_trace(trace_path: Path, dim: int = 3) -> Tuple[float, float]:
    """Compute D from final carrier displacements (Einstein relation).

    Returns (D_mean, D_sem) in A^2/s.
    Uses D_i = |r_i(T) - r_i(0)|^2 / (2*d*t) for each carrier,
    then averages. This avoids the noisy MSD linear fit problem.
    """
    data = np.load(trace_path)
    t_final = float(data["time_s"][-1])
    if t_final <= 0:
        raise RuntimeError("Simulated time is zero.")

    r = data["carrier_r_A"].astype(float)    # (n_carriers, 3)
    r0 = data["carrier_r0_A"].astype(float)  # (n_carriers, 3)
    disp_sq = np.sum((r - r0) ** 2, axis=1)  # per-carrier |dr|^2

    D_per_carrier = disp_sq / (2.0 * dim * t_final)
    D_mean = float(np.mean(D_per_carrier))
    D_sem = float(np.std(D_per_carrier, ddof=1) / math.sqrt(len(D_per_carrier)))
    return D_mean, D_sem


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Validate KMC engine against exact random walk diffusivity."
    )
    ap.add_argument("--max_steps", type=int, default=500000)
    ap.add_argument("--n_replicas", type=int, default=5,
                    help="Independent replicas per temperature for error bars")
    ap.add_argument("--out_dir", default=".")
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    a = 3.0
    nx, ny, nz = 10, 10, 10
    n_sites = nx * ny * nz
    nu = 1e13
    barrier_eV = 0.3
    n_carriers = 50
    temperatures = [500, 600, 800, 1000, 1200, 1500]
    max_steps = args.max_steps
    n_replicas = args.n_replicas
    save_every = max(1, max_steps // 500)

    # spread carriers evenly across the lattice
    carrier_spacing = n_sites // n_carriers
    occupied_sites = [i * carrier_spacing for i in range(n_carriers)]

    lattice = build_simple_cubic_lattice(a, nx, ny, nz)
    lattice_path = out_dir / "sc_lattice.json"
    lattice_path.write_text(json.dumps(lattice, indent=4))
    conc = n_carriers / n_sites
    print(f"Built simple cubic lattice: {n_sites} sites, a={a} A")
    print(f"Carriers: {n_carriers} ({conc*100:.1f}% occupancy)")
    print(f"Replicas per temperature: {n_replicas}")

    results = []

    for T in temperatures:
        print(f"\n--- T = {T} K ---")
        D_replicas = []

        t_dir = out_dir / "runs" / f"T{T}K"
        t_dir.mkdir(parents=True, exist_ok=True)

        for rep in range(n_replicas):
            run_dir = t_dir / f"rep{rep}"
            seed = 1000 * T + rep * 137

            config = {
                "lattice": str(lattice_path),
                "model": {
                    "temperature_K": T,
                    "prefactor_Hz": nu,
                    "rate_model": "constant",
                    "barrier_eV": barrier_eV,
                    "site_energies_eV": None,
                },
                "initial_state": {"occupied_sites": occupied_sites},
                "simulation": {
                    "max_steps": max_steps,
                    "max_time_s": None,
                    "save_every": save_every,
                    "seed": seed,
                },
                "output": {"out_dir": str(run_dir)},
            }
            cfg_path = t_dir / f"config_rep{rep}.json"
            cfg_path.write_text(json.dumps(config, indent=4))

            res = subprocess.run(
                [sys.executable, str(KMC_SCRIPT), "--config", str(cfg_path)],
                capture_output=True, text=True,
            )
            if res.returncode != 0:
                print(f"  rep {rep} FAILED:\n{res.stderr[:200]}")
                continue

            trace_path = run_dir / "kmc_trace.npz"
            try:
                D_val, _ = compute_D_from_trace(trace_path, dim=3)
                D_replicas.append(D_val)
            except Exception as e:
                print(f"  rep {rep} analysis failed: {e}")
                continue

        if not D_replicas:
            print(f"  No successful replicas at T={T}K")
            continue

        D_mean = float(np.mean(D_replicas))
        D_std = float(np.std(D_replicas, ddof=1)) if len(D_replicas) > 1 else 0.0
        D_sem = D_std / math.sqrt(len(D_replicas)) if len(D_replicas) > 1 else 0.0
        D_ana = d_exact(a, nu, barrier_eV, T, c=conc)

        ratio = D_mean / D_ana
        pct_err = (ratio - 1.0) * 100

        results.append({
            "T_K": T,
            "D_kmc_A2_s": D_mean,
            "D_kmc_std_A2_s": D_std,
            "D_kmc_sem_A2_s": D_sem,
            "D_exact_A2_s": D_ana,
            "ratio": ratio,
            "pct_error": pct_err,
            "n_replicas": len(D_replicas),
        })

        print(f"  D_kmc   = {D_mean:.6e} +/- {D_sem:.2e} A^2/s  ({len(D_replicas)} reps)")
        print(f"  D_exact = {D_ana:.6e} A^2/s")
        print(f"  ratio   = {ratio:.4f}  ({pct_err:+.2f}%)")

    if not results:
        print("No successful runs. Exiting.")
        return

    print("\n" + "=" * 80)
    print(f"{'T (K)':>8} {'D_kmc (A^2/s)':>16} {'D_exact (A^2/s)':>16} {'ratio':>8} {'err%':>8} {'reps':>5}")
    print("-" * 80)
    for r in results:
        print(
            f"{r['T_K']:>8d} {r['D_kmc_A2_s']:>16.6e} {r['D_exact_A2_s']:>16.6e} "
            f"{r['ratio']:>8.4f} {r['pct_error']:>+8.2f}% {r['n_replicas']:>5d}"
        )
    print("=" * 80)

    max_err = max(abs(r["pct_error"]) for r in results)
    print(f"\nMax |error|: {max_err:.2f}%")
    print(f"(Analytical reference includes (1-c) blocking correction, c={conc:.2f})")
    if max_err < 5.0:
        print("PASS: all temperatures within 5% of analytical result.")
    elif max_err < 10.0:
        print("MARGINAL: errors within 10%, may need more steps or replicas.")
    else:
        print("FAIL: errors exceed 10%, investigate engine or analysis.")

    summary = {
        "lattice": "simple_cubic",
        "supercell": f"{nx}x{ny}x{nz}",
        "a_A": a,
        "nu_Hz": nu,
        "barrier_eV": barrier_eV,
        "max_steps": max_steps,
        "n_carriers": n_carriers,
        "n_replicas_per_T": n_replicas,
        "carrier_concentration": conc,
        "analytical_formula": "D = a^2 * nu * exp(-Eb / kBT) * (1 - c)",
        "results": results,
    }
    summary_path = out_dir / "validation_summary.json"
    summary_path.write_text(json.dumps(summary, indent=4))
    print(f"\nWrote: {summary_path}")

    temps = np.array([r["T_K"] for r in results], dtype=float)
    D_kmc_arr = np.array([r["D_kmc_A2_s"] for r in results], dtype=float)
    D_sem_arr = np.array([r["D_kmc_sem_A2_s"] for r in results], dtype=float)
    D_ana_arr = np.array([r["D_exact_A2_s"] for r in results], dtype=float)
    ratios = np.array([r["ratio"] for r in results], dtype=float)

    inv_T = 1000.0 / temps

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

    # left: Arrhenius plot
    ax1.errorbar(inv_T, D_kmc_arr, yerr=D_sem_arr * 1.96, fmt="o", color="C0",
                 markersize=8, capsize=4, label="KMC (this engine)")
    T_fine = np.linspace(min(temps) * 0.9, max(temps) * 1.1, 200)
    D_fine = np.array([d_exact(a, nu, barrier_eV, t, c=conc) for t in T_fine])
    ax1.semilogy(1000.0 / T_fine, D_fine, "-", color="C1", linewidth=1.5,
                 label=r"Exact: $D = a^2 \nu \exp(-E_b/k_BT)$")
    ax1.set_xlabel("1000/T (1/K)")
    ax1.set_ylabel(r"D ($\AA^2$/s)")
    ax1.set_title("Arrhenius: KMC vs Analytical")
    ax1.legend()
    ax1.set_yscale("log")

    # right: ratio plot
    ratio_sem = D_sem_arr / D_ana_arr
    ax2.axhline(1.0, color="gray", linestyle="--", linewidth=1)
    ax2.axhspan(0.95, 1.05, color="green", alpha=0.15, label=r"$\pm$5%")
    ax2.errorbar(temps, ratios, yerr=ratio_sem * 1.96, fmt="o-", color="C0",
                 markersize=8, capsize=4)
    ax2.set_xlabel("T (K)")
    ax2.set_ylabel(r"$D_{\mathrm{KMC}} / D_{\mathrm{exact}}$")
    ax2.set_title("Accuracy: KMC / Exact")
    ax2.legend()
    ax2.set_ylim(0.8, 1.2)

    fig.tight_layout()
    plot_path = out_dir / "validation_plot.png"
    fig.savefig(plot_path, dpi=150)
    plt.close(fig)
    print(f"Wrote: {plot_path}")


if __name__ == "__main__":
    main()
