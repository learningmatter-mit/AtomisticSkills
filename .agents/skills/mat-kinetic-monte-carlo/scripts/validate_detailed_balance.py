"""
Validate detailed balance / microreversibility for a lattice KMC model.

Checks that:
  1) The neighbor graph is bidirectional (i<->j) with opposite shifts.
  2) For enabled edges under the chosen rate model, detailed balance holds:
     ln(k_ij / k_ji) + (E_j - E_i)/(kB*T) = 0

Usage:
    python validate_detailed_balance.py --config kmc_config.json [--tol 1e-6]

Requirements:
    - numpy
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Dict, Tuple

import numpy as np

K_B_EV_K = 8.617333262145e-5  # eV/K


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Validate detailed balance for a lattice KMC model."
    )
    ap.add_argument("--config", required=True, help="Path to KMC config JSON")
    ap.add_argument(
        "--tol", type=float, default=1e-6,
        help="Tolerance on detailed balance residual"
    )
    args = ap.parse_args()

    cfg = json.loads(Path(args.config).read_text())
    lattice = json.loads(Path(cfg["lattice"]).read_text())

    neighbors = lattice["neighbors"]
    n_sites = len(neighbors)

    model = cfg["model"]
    T = float(model["temperature_K"])
    nu = float(model["prefactor_Hz"])
    rate_model = str(model.get("rate_model", "constant"))
    barrier_eV = float(model["barrier_eV"])

    site_E = model.get("site_energies_eV", None)
    if site_E is None:
        site_E_arr = np.zeros(n_sites, dtype=float)
    else:
        site_E_arr = np.array(site_E, dtype=float)

    # build map of directed edges: (i,j) -> shift
    edge_shift: Dict[Tuple[int, int], Tuple[int, int, int]] = {}
    for i in range(n_sites):
        for nb in neighbors[i]:
            j = int(nb["j"])
            s = tuple(int(x) for x in nb["shift"])
            edge_shift[(i, j)] = s

    # check bidirectionality
    bad_edges = []
    for (i, j), s in edge_shift.items():
        if (j, i) not in edge_shift:
            bad_edges.append((i, j, s, None))
        else:
            s2 = edge_shift[(j, i)]
            if tuple([-x for x in s]) != s2:
                bad_edges.append((i, j, s, s2))

    if bad_edges:
        print("WARNING: Neighbor graph is not strictly bidirectional with opposite shifts.")
        print("First few problematic edges:")
        for item in bad_edges[:10]:
            print(f"  edge {item}")
    else:
        print("OK: neighbor graph is bidirectional with opposite shifts.")

    def k_ij(i: int, j: int) -> float:
        beta = 1.0 / (K_B_EV_K * T)
        Ei, Ej = float(site_E_arr[i]), float(site_E_arr[j])
        if rate_model == "constant":
            return nu * math.exp(-barrier_eV * beta)
        if rate_model == "symmetric_site_energy":
            b = barrier_eV + max(0.0, Ej - Ei)
            return nu * math.exp(-b * beta)
        raise ValueError(f"Unsupported rate_model: {rate_model}")

    # detailed balance residuals
    residuals = []
    for (i, j) in edge_shift:
        if (j, i) not in edge_shift:
            continue
        kij = k_ij(i, j)
        kji = k_ij(j, i)
        if kij <= 0 or kji <= 0:
            continue
        Ei, Ej = float(site_E_arr[i]), float(site_E_arr[j])
        res = math.log(kij / kji) + (Ej - Ei) / (K_B_EV_K * T)
        residuals.append(res)

    if not residuals:
        print("No residuals computed (missing reverse edges or zero rates).")
        return

    residuals_arr = np.array(residuals, dtype=float)
    max_res = float(np.max(np.abs(residuals_arr)))
    rms_res = float(np.sqrt(np.mean(residuals_arr**2)))
    print(f"Detailed balance residual stats: max|res|={max_res:.3e}, rms={rms_res:.3e}")

    if max_res > args.tol:
        print(
            "WARNING: detailed balance residual exceeds tolerance. "
            "Model may violate microreversibility."
        )
    else:
        print("OK: detailed balance satisfied within tolerance.")


if __name__ == "__main__":
    main()
