"""
Literature validation: H diffusion in BCC tungsten T-site sublattice.

Two validation routes are supported:

  Route 0 (default): Yang-calibrated coarse-grained KMC.  Adopt effective
      Arrhenius parameters from Yang et al. (2016) and verify the engine
      reproduces the published diffusivity line.

  Route 1 (--from_mlip): First-principles NEB + phonon -> hTST -> KMC.
      Load barrier and Vineyard prefactor computed from MLIP phonon data
      (see compute_htst_prefactor.py) and run the same KMC pipeline.
      Compare MLIP-KMC against Yang and Frauenfelder literature lines.

Validates the lattice KMC engine against:
  1) Analytical random walk -- D = (f*z*l^2/6) * nu * exp(-Eb / kBT)
  2) Yang et al. (2016) KMC -- should coincide (same effective Arrhenius params)
  3) Frauenfelder (1969) experimental -- independent comparison

References:
  - Yang et al. (2016): D = 8.45e-7 * exp(-0.440 / kBT) m^2/s  (hTST KMC)
  - Frauenfelder (1969): D = 4.1e-7 * exp(-0.39 / kBT) m^2/s   (experimental)

Usage:
    # Route 0 (Yang-calibrated):
    python validate_h_in_bcc_w.py [--max_steps 500000] [--n_replicas 20] [--out_dir .]

    # Route 1 (MLIP first-principles):
    python validate_h_in_bcc_w.py --from_mlip htst_results.json [--max_steps 500000] [--out_dir mlip_validation]

Requirements:
    - numpy, matplotlib
    - run_lattice_kmc.py from ../../scripts/
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


def build_bcc_tsite_lattice(a: float, nx: int, ny: int, nz: int) -> dict:
    """Build a BCC T-site sublattice with periodic neighbors.

    Each conventional BCC cell has 12 tetrahedral interstitial sites
    (4 on each pair of opposite faces). Each T-site has exactly z=4
    nearest T-site neighbors at distance d_hop = a*sqrt(2)/4.
    """
    # 12 T-site basis positions in fractional coords of the conventional cell
    basis = [
        # {100} faces (x = 0 face, wraps to x = 1)
        [0.0, 0.25, 0.5],
        [0.0, 0.75, 0.5],
        [0.0, 0.5, 0.25],
        [0.0, 0.5, 0.75],
        # {010} faces (y = 0 face)
        [0.25, 0.0, 0.5],
        [0.75, 0.0, 0.5],
        [0.5, 0.0, 0.25],
        [0.5, 0.0, 0.75],
        # {001} faces (z = 0 face)
        [0.25, 0.5, 0.0],
        [0.75, 0.5, 0.0],
        [0.5, 0.25, 0.0],
        [0.5, 0.75, 0.0],
    ]
    n_basis = len(basis)
    basis_arr = np.array(basis, dtype=float)

    d_hop = a * math.sqrt(2) / 4.0
    tol = 0.1  # angstrom tolerance for neighbor detection

    # build neighbor template: for each basis site, find its 4 neighbors
    # by searching all 12 basis sites in the 27 cell images
    neighbor_template: list[list[dict]] = [[] for _ in range(n_basis)]
    images = [-1, 0, 1]

    for b in range(n_basis):
        fb = basis_arr[b]
        cart_b = fb * a  # Cartesian position within one cell
        for b2 in range(n_basis):
            for dx in images:
                for dy in images:
                    for dz in images:
                        fb2_img = basis_arr[b2] + np.array([dx, dy, dz], dtype=float)
                        cart_b2 = fb2_img * a
                        dist = np.linalg.norm(cart_b2 - cart_b)
                        if abs(dist - d_hop) < tol:
                            neighbor_template[b].append({
                                "basis": b2,
                                "cell_offset": [dx, dy, dz],
                            })

    for b in range(n_basis):
        assert len(neighbor_template[b]) == 4, (
            f"Basis site {b} has {len(neighbor_template[b])} neighbors, expected 4"
        )

    # tile the supercell
    n_sites = n_basis * nx * ny * nz
    supercell = [[a * nx, 0.0, 0.0], [0.0, a * ny, 0.0], [0.0, 0.0, a * nz]]

    frac_coords = []
    index_map = {}
    idx = 0
    for cx in range(nx):
        for cy in range(ny):
            for cz in range(nz):
                for b in range(n_basis):
                    frac_coords.append([
                        (cx + basis_arr[b, 0]) / nx,
                        (cy + basis_arr[b, 1]) / ny,
                        (cz + basis_arr[b, 2]) / nz,
                    ])
                    index_map[(cx, cy, cz, b)] = idx
                    idx += 1

    neighbors: list[list[dict]] = [[] for _ in range(n_sites)]
    for cx in range(nx):
        for cy in range(ny):
            for cz in range(nz):
                for b in range(n_basis):
                    i = index_map[(cx, cy, cz, b)]
                    for nb_tmpl in neighbor_template[b]:
                        b2 = nb_tmpl["basis"]
                        dx, dy, dz = nb_tmpl["cell_offset"]
                        raw_x = cx + dx
                        raw_y = cy + dy
                        raw_z = cz + dz

                        jx = raw_x % nx
                        jy = raw_y % ny
                        jz = raw_z % nz

                        # supercell shift: how many supercell lengths we crossed
                        sx = (raw_x - jx) // nx
                        sy = (raw_y - jy) // ny
                        sz = (raw_z - jz) // nz

                        j = index_map[(jx, jy, jz, b2)]
                        neighbors[i].append({"j": j, "shift": [sx, sy, sz]})

    # validate: z=4 for all sites, bidirectionality
    for i in range(n_sites):
        assert len(neighbors[i]) == 4, (
            f"site {i} has {len(neighbors[i])} neighbors, expected 4"
        )

    # check bidirectionality: for each edge i->j with shift s,
    # there must be an edge j->i with shift -s
    for i in range(n_sites):
        for nb in neighbors[i]:
            j = nb["j"]
            s = nb["shift"]
            reverse_found = False
            for nb2 in neighbors[j]:
                if nb2["j"] == i and nb2["shift"] == [-s[0], -s[1], -s[2]]:
                    reverse_found = True
                    break
            assert reverse_found, (
                f"No reverse edge for {i}->{j} shift={s}"
            )

    return {
        "cell_A": supercell,
        "site_element": "H",
        "site_frac_coords": frac_coords,
        "neighbors": neighbors,
        "cutoff_A": d_hop * 1.05,
        "source_structure": f"bcc_W_Tsite_{nx}x{ny}x{nz}_a{a}",
    }


def d_analytical(a: float, nu: float, barrier_eV: float, T: float) -> float:
    """Analytical diffusivity for random walk on BCC T-site sublattice.

    D = a^2/12 * nu * exp(-Eb / kBT)

    In the dilute limit, blocking correction is negligible.
    Returns D in A^2/s.
    """
    return (a**2 / 12.0) * nu * math.exp(-barrier_eV / (K_B_EV_K * T))


def d_yang(T: float) -> float:
    """Yang et al. (2016) KMC result: D = 8.45e-7 * exp(-0.440/kBT) m^2/s."""
    return 8.45e-7 * math.exp(-0.440 / (K_B_EV_K * T))


def d_frauenfelder(T: float) -> float:
    """Frauenfelder (1969) experimental: D = 4.1e-7 * exp(-0.39/kBT) m^2/s."""
    return 4.1e-7 * math.exp(-0.39 / (K_B_EV_K * T))


def compute_D_from_trace(trace_path: Path, dim: int = 3) -> Tuple[float, float]:
    """Compute D from final carrier displacements (Einstein relation).

    Returns (D_mean, D_sem) in A^2/s.
    """
    data = np.load(trace_path)
    t_final = float(data["time_s"][-1])
    if t_final <= 0:
        raise RuntimeError("Simulated time is zero.")

    r = data["carrier_r_A"].astype(float)
    r0 = data["carrier_r0_A"].astype(float)
    disp_sq = np.sum((r - r0) ** 2, axis=1)

    D_per_carrier = disp_sq / (2.0 * dim * t_final)
    D_mean = float(np.mean(D_per_carrier))
    D_sem = float(np.std(D_per_carrier, ddof=1) / math.sqrt(len(D_per_carrier)))
    return D_mean, D_sem


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Validate KMC engine: H diffusion on BCC W T-site sublattice."
    )
    ap.add_argument("--max_steps", type=int, default=500000)
    ap.add_argument("--n_replicas", type=int, default=20,
                    help="Independent replicas per temperature for error bars")
    ap.add_argument("--out_dir", default=".")
    ap.add_argument("--from_mlip", default=None, metavar="HTST_JSON",
                    help="Path to htst_results.json from compute_htst_prefactor.py. "
                         "Uses MLIP-derived barrier and prefactor instead of Yang et al. parameters.")
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # BCC tungsten parameters
    a = 3.165  # lattice constant in angstrom
    nx, ny, nz = 8, 8, 8
    n_basis = 12
    n_sites = n_basis * nx * ny * nz  # 6144

    # Yang et al. reference parameters (always needed for comparison)
    nu_yang = 8.45e-7 / (a**2 * 1e-20 / 12.0)  # 1.012e14 Hz
    barrier_yang = 0.440  # effective barrier

    mlip_mode = args.from_mlip is not None
    if mlip_mode:
        htst_data = json.loads(Path(args.from_mlip).read_text())
        nu = htst_data["prefactor_Hz"]
        barrier_eV = htst_data["barrier_eV"]
        mlip_label = "MLIP hTST"
        print(f"MLIP mode: barrier={barrier_eV:.4f} eV, prefactor={nu:.4e} Hz")
        print(f"  (from {args.from_mlip})")
    else:
        # effective Arrhenius parameters from Yang et al. (2016) hTST KMC:
        # D = 8.45e-7 * exp(-0.440/kBT) m^2/s => nu = D0 / (a^2/12)
        nu = nu_yang
        barrier_eV = barrier_yang

    n_carriers = 50
    temperatures = [500, 700, 900, 1100, 1400, 1800, 2300]
    max_steps = args.max_steps
    n_replicas = args.n_replicas
    save_every = max(1, max_steps // 500)

    # spread carriers evenly across the lattice
    carrier_spacing = n_sites // n_carriers
    occupied_sites = [i * carrier_spacing for i in range(n_carriers)]

    print(f"Building BCC W T-site lattice: {nx}x{ny}x{nz} supercell...")
    lattice = build_bcc_tsite_lattice(a, nx, ny, nz)
    lattice_path = out_dir / "bcc_w_tsite_lattice.json"
    lattice_path.write_text(json.dumps(lattice, indent=4))
    conc = n_carriers / n_sites
    print(f"  {n_sites} sites, a={a} A, z=4")
    print(f"  Carriers: {n_carriers} ({conc*100:.4f}% occupancy)")
    print(f"  Barrier: {barrier_eV} eV, prefactor: {nu:.0e} Hz")
    print(f"  Replicas per temperature: {n_replicas}")

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
        D_ana = d_analytical(a, nu, barrier_eV, T)

        ratio = D_mean / D_ana
        pct_err = (ratio - 1.0) * 100

        results.append({
            "T_K": T,
            "D_kmc_A2_s": D_mean,
            "D_kmc_std_A2_s": D_std,
            "D_kmc_sem_A2_s": D_sem,
            "D_analytical_A2_s": D_ana,
            "ratio": ratio,
            "pct_error": pct_err,
            "n_replicas": len(D_replicas),
        })

        print(f"  D_kmc        = {D_mean:.6e} +/- {D_sem:.2e} A^2/s  ({len(D_replicas)} reps)")
        print(f"  D_analytical = {D_ana:.6e} A^2/s")
        print(f"  ratio        = {ratio:.4f}  ({pct_err:+.2f}%)")

    if not results:
        print("No successful runs. Exiting.")
        return

    print("\n" + "=" * 88)
    print(f"{'T (K)':>8} {'D_kmc (A^2/s)':>16} {'D_anal (A^2/s)':>16} {'ratio':>8} {'err%':>8} {'reps':>5}")
    print("-" * 88)
    for r in results:
        print(
            f"{r['T_K']:>8d} {r['D_kmc_A2_s']:>16.6e} {r['D_analytical_A2_s']:>16.6e} "
            f"{r['ratio']:>8.4f} {r['pct_error']:>+8.2f}% {r['n_replicas']:>5d}"
        )
    print("=" * 88)

    max_err = max(abs(r["pct_error"]) for r in results)
    print(f"\nMax |error|: {max_err:.2f}%")
    if max_err < 5.0:
        print("PASS: all temperatures within 5% of analytical result.")
    elif max_err < 10.0:
        print("MARGINAL: errors within 10%, may need more steps or replicas.")
    else:
        print("FAIL: errors exceed 10%, investigate engine or analysis.")

    summary = {
        "system": "H in BCC W (T-site sublattice)",
        "mode": "mlip_htst" if mlip_mode else "yang_calibrated",
        "lattice": "bcc_tsite",
        "supercell": f"{nx}x{ny}x{nz}",
        "a_A": a,
        "nu_Hz": nu,
        "barrier_eV": barrier_eV,
        "max_steps": max_steps,
        "n_carriers": n_carriers,
        "n_sites": n_sites,
        "n_replicas_per_T": n_replicas,
        "carrier_concentration": conc,
        "analytical_formula": "D = a^2/12 * nu * exp(-Eb / kBT)",
        "results": results,
    }
    if mlip_mode:
        summary["htst_source"] = str(args.from_mlip)
        summary["yang_reference"] = {
            "nu_Hz": nu_yang,
            "barrier_eV": barrier_yang,
        }
    summary_path = out_dir / "validation_summary.json"
    summary_path.write_text(json.dumps(summary, indent=4))
    print(f"\nWrote: {summary_path}")

    temps = np.array([r["T_K"] for r in results], dtype=float)
    D_kmc_arr = np.array([r["D_kmc_A2_s"] for r in results], dtype=float)
    D_sem_arr = np.array([r["D_kmc_sem_A2_s"] for r in results], dtype=float)
    D_ana_arr = np.array([r["D_analytical_A2_s"] for r in results], dtype=float)
    ratios = np.array([r["ratio"] for r in results], dtype=float)

    # convert KMC and analytical D from A^2/s to m^2/s for Arrhenius plot
    D_kmc_m2 = D_kmc_arr * 1e-20
    D_sem_m2 = D_sem_arr * 1e-20
    D_ana_m2 = D_ana_arr * 1e-20

    inv_T = 1000.0 / temps

    T_fine = np.linspace(min(temps) * 0.85, max(temps) * 1.1, 300)
    inv_T_fine = 1000.0 / T_fine

    if mlip_mode:
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5.5))

        # left panel: Arrhenius with 3 lines
        ax1.errorbar(inv_T, D_kmc_m2, yerr=D_sem_m2 * 1.96, fmt="s", color="C3",
                     markersize=8, capsize=4, label=f"MLIP KMC (Eb={barrier_eV:.3f} eV)")

        # MLIP analytical line
        D_mlip_fine = np.array([d_analytical(a, nu, barrier_eV, t) for t in T_fine]) * 1e-20
        ax1.semilogy(inv_T_fine, D_mlip_fine, "-", color="C3", linewidth=1.5, alpha=0.5)

        # Yang et al. literature line
        D_yang_fine = np.array([d_yang(t) for t in T_fine])
        ax1.semilogy(inv_T_fine, D_yang_fine, "-", color="C1", linewidth=1.5,
                     label="Yang et al. (2016) hTST KMC")

        # Frauenfelder experimental
        D_frau_fine = np.array([d_frauenfelder(t) for t in T_fine])
        ax1.semilogy(inv_T_fine, D_frau_fine, "-.", color="C2", linewidth=1.5,
                     label="Frauenfelder (1969) expt.")

        ax1.set_xlabel("1000/T (1/K)")
        ax1.set_ylabel(r"D (m$^2$/s)")
        ax1.set_title("H diffusion in BCC W: MLIP vs Literature")
        ax1.legend(fontsize=8)
        ax1.set_yscale("log")

        # right panel: ratio MLIP-KMC / Yang analytical
        D_yang_at_T = np.array([d_yang(t) for t in temps])
        ratio_to_yang = D_kmc_m2 / D_yang_at_T
        ratio_sem_yang = D_sem_m2 / D_yang_at_T

        ax2.axhline(1.0, color="gray", linestyle="--", linewidth=1)
        ax2.axhspan(0.5, 2.0, color="yellow", alpha=0.1, label="within 2x")
        ax2.axhspan(0.8, 1.25, color="green", alpha=0.15, label=r"$\pm$25%")
        ax2.errorbar(temps, ratio_to_yang, yerr=ratio_sem_yang * 1.96,
                     fmt="s-", color="C3", markersize=8, capsize=4,
                     label="MLIP / Yang")

        # also show ratio to Frauenfelder
        D_frau_at_T = np.array([d_frauenfelder(t) for t in temps])
        ratio_to_frau = D_kmc_m2 / D_frau_at_T
        ax2.plot(temps, ratio_to_frau, "d--", color="C2", markersize=6,
                 label="MLIP / Frauenfelder")

        ax2.set_xlabel("T (K)")
        ax2.set_ylabel(r"$D_{\mathrm{MLIP\text{-}KMC}} / D_{\mathrm{lit.}}$")
        ax2.set_title("MLIP Accuracy vs Literature")
        ax2.legend(fontsize=8)
        ax2.set_yscale("log")
        # Auto-scale with padding to fit all data points
        all_ratios = np.concatenate([ratio_to_yang, ratio_to_frau])
        ymin = min(all_ratios) * 0.5
        ymax = max(all_ratios) * 2.0
        ax2.set_ylim(ymin, ymax)

    else:
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5.5))

        # left panel: Arrhenius plot (D in m^2/s)
        ax1.errorbar(inv_T, D_kmc_m2, yerr=D_sem_m2 * 1.96, fmt="o", color="C0",
                     markersize=8, capsize=4, label="KMC (this engine)")

        D_ana_fine = np.array([d_analytical(a, nu, barrier_eV, t) for t in T_fine]) * 1e-20
        ax1.semilogy(inv_T_fine, D_ana_fine, "-", color="C1", linewidth=1.5,
                     label="Analytical / Yang et al. (2016)")

        D_frau_fine = np.array([d_frauenfelder(t) for t in T_fine])
        ax1.semilogy(inv_T_fine, D_frau_fine, "-.", color="C2", linewidth=1.5,
                     label="Frauenfelder (1969) expt.")

        ax1.set_xlabel("1000/T (1/K)")
        ax1.set_ylabel(r"D (m$^2$/s)")
        ax1.set_title("H diffusion in BCC W: Arrhenius")
        ax1.legend(fontsize=8)
        ax1.set_yscale("log")

        # right panel: ratio D_KMC / D_analytical
        ratio_sem = D_sem_arr / D_ana_arr
        ax2.axhline(1.0, color="gray", linestyle="--", linewidth=1)
        ax2.axhspan(0.95, 1.05, color="green", alpha=0.15, label=r"$\pm$5%")
        ax2.errorbar(temps, ratios, yerr=ratio_sem * 1.96, fmt="o-", color="C0",
                     markersize=8, capsize=4)
        ax2.set_xlabel("T (K)")
        ax2.set_ylabel(r"$D_{\mathrm{KMC}} / D_{\mathrm{analytical}}$")
        ax2.set_title("Accuracy: KMC / Analytical")
        ax2.legend()
        ax2.set_ylim(0.8, 1.2)

    fig.tight_layout()
    plot_path = out_dir / "validation_plot.png"
    fig.savefig(plot_path, dpi=150)
    plt.close(fig)
    print(f"Wrote: {plot_path}")


if __name__ == "__main__":
    main()
