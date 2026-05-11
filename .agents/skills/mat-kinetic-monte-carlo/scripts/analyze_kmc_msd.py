"""
Analyze KMC trace to estimate tracer and collective diffusivity.

Computes D using the single-point Einstein relation (standard for KMC):

  D_tracer = <|r_i(t)|^2> / (2*d*t)   (mean over carriers)
  D_J      = |sum_i r_i(t)|^2 / (2*d*t*N)  (collective/charge)
  H_R      = D_tracer / D_J            (Haven ratio)

where d = dimensionality, t = simulated time, N = number of carriers.

D_J is the physically relevant quantity for ionic conductivity via
the Nernst-Einstein relation: sigma = n*q^2*D_J / (kB*T).

Usage:
    python analyze_kmc_msd.py \
        --trace kmc_run_T800K/kmc_trace.npz \
        --dim 3 \
        --out kmc_run_T800K/D_fit.json

Requirements:
    - numpy
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Compute diffusivity from KMC trace (single-point Einstein relation)."
    )
    ap.add_argument("--trace", required=True, help="Path to kmc_trace.npz")
    ap.add_argument("--dim", type=int, default=3, help="Diffusion dimensionality (1, 2, or 3)")
    ap.add_argument("--out", default="", help="Optional output JSON path")
    args = ap.parse_args()

    data = np.load(args.trace)
    t_final = float(data["time_s"][-1])
    if t_final <= 0:
        raise RuntimeError("Simulated time is zero; cannot compute D.")

    r = data["carrier_r_A"].astype(float)    # (n_carriers, 3) final positions
    r0 = data["carrier_r0_A"].astype(float)  # (n_carriers, 3) initial positions
    disp = r - r0                            # (n_carriers, 3)
    n_carriers = disp.shape[0]

    d = int(args.dim)

    # D_tracer: mean of per-carrier squared displacements
    disp_sq = np.sum(disp ** 2, axis=1)  # per-carrier |dr|^2
    msd_tracer = float(np.mean(disp_sq))
    D_tracer_A2_s = msd_tracer / (2.0 * d * t_final)

    # D_J: squared displacement of center-of-mass (collective)
    total_disp = np.sum(disp, axis=0)  # sum of all carrier displacements
    msd_collective = float(np.sum(total_disp ** 2))
    D_J_A2_s = msd_collective / (2.0 * d * t_final * n_carriers)

    # Haven ratio
    H_R = D_tracer_A2_s / D_J_A2_s if D_J_A2_s > 0 else float("nan")

    # unit conversions
    D_tracer_m2_s = D_tracer_A2_s * 1e-20
    D_tracer_cm2_s = D_tracer_A2_s * 1e-16
    D_J_m2_s = D_J_A2_s * 1e-20
    D_J_cm2_s = D_J_A2_s * 1e-16

    result = {
        "dim": d,
        "time_s": t_final,
        "n_carriers": n_carriers,
        "D_tracer_A2_s": float(D_tracer_A2_s),
        "D_tracer_m2_s": float(D_tracer_m2_s),
        "D_tracer_cm2_s": float(D_tracer_cm2_s),
        "D_J_A2_s": float(D_J_A2_s),
        "D_J_m2_s": float(D_J_m2_s),
        "D_J_cm2_s": float(D_J_cm2_s),
        "haven_ratio": float(H_R),
        "msd_tracer_A2": float(msd_tracer),
        "msd_collective_A2": float(msd_collective),
        "trace": str(args.trace),
    }

    print(json.dumps(result, indent=4))

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(result, indent=4))
        print(f"Wrote: {out_path}")

    # Save input configs for reproducibility
    from src.utils.config_utils import save_skill_inputs
    save_skill_inputs(args, args.out)


if __name__ == "__main__":
    main()
