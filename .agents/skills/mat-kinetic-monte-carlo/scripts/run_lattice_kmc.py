"""
Rejection-free lattice KMC for carrier hops on a fixed site network.

Implements the residence-time / Gillespie direct method with local rate
updates and a Fenwick tree (Binary Indexed Tree) for O(log N) weighted
event sampling.

Supported rate models:
  1) constant:  k = nu * exp(-barrier_eV / (kB*T))
  2) symmetric_site_energy (microreversible if prefactors equal):
     k = nu * exp(-(E0 + max(0, Ej - Ei)) / (kB*T))

Usage:
    python run_lattice_kmc.py --config kmc_config.json

Requirements:
    - numpy
"""
from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np

K_B_EV_K = 8.617333262145e-5  # eV/K


class FenwickTree:
    """Fenwick tree for prefix sums over nonnegative weights."""

    def __init__(self, values: np.ndarray) -> None:
        self.n = int(values.size)
        self.bit = np.zeros(self.n + 1, dtype=float)
        for i, v in enumerate(values, start=1):
            self._add(i, float(v))

    def _add(self, i1: int, delta: float) -> None:
        n = self.n
        while i1 <= n:
            self.bit[i1] += delta
            i1 += i1 & -i1

    def update(self, idx0: int, new_value: float, old_value: float) -> None:
        delta = float(new_value - old_value)
        if delta != 0.0:
            self._add(idx0 + 1, delta)

    def total(self) -> float:
        s = 0.0
        i = self.n
        while i > 0:
            s += self.bit[i]
            i -= i & -i
        return s

    def find_prefix(self, target: float) -> int:
        """Return smallest idx such that prefix_sum(idx) >= target."""
        idx = 0
        bitmask = 1 << (self.n.bit_length() - 1)
        while bitmask:
            t = idx + bitmask
            if t <= self.n and self.bit[t] < target:
                idx = t
                target -= self.bit[t]
            bitmask >>= 1
        return idx  # 0-based index


@dataclass
class Edge:
    i: int
    j: int
    shift: Tuple[int, int, int]
    delta_cart_A: np.ndarray  # 3-vector displacement in angstrom


def load_lattice(lattice_path: Path) -> Tuple[np.ndarray, np.ndarray, List[List[Dict]]]:
    data = json.loads(lattice_path.read_text())
    cell = np.array(data["cell_A"], dtype=float)
    frac = np.array(data["site_frac_coords"], dtype=float)
    neighbors = data["neighbors"]
    return cell, frac, neighbors


def rate_constant(
    rate_model: str,
    nu: float,
    barrier_eV: float,
    T: float,
    Ei: float,
    Ej: float,
) -> float:
    if T <= 0:
        return 0.0
    beta = 1.0 / (K_B_EV_K * T)
    if rate_model == "constant":
        return nu * math.exp(-barrier_eV * beta)
    if rate_model == "symmetric_site_energy":
        b = barrier_eV + max(0.0, Ej - Ei)
        return nu * math.exp(-b * beta)
    raise ValueError(f"Unknown rate_model='{rate_model}'")


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Run rejection-free lattice KMC for carrier hops."
    )
    ap.add_argument("--config", required=True, help="Path to KMC config JSON")
    args = ap.parse_args()

    cfg = json.loads(Path(args.config).read_text())
    lattice_path = Path(cfg["lattice"])
    cell, frac, neighbors = load_lattice(lattice_path)

    model = cfg["model"]
    T = float(model["temperature_K"])
    nu = float(model["prefactor_Hz"])
    rate_model = str(model.get("rate_model", "constant"))
    barrier_eV = float(model["barrier_eV"])

    n_sites = int(frac.shape[0])
    site_E = model.get("site_energies_eV", None)
    if site_E is None:
        site_E_arr = np.zeros(n_sites, dtype=float)
    else:
        site_E_arr = np.array(site_E, dtype=float)
        if site_E_arr.size != n_sites:
            raise ValueError("site_energies_eV length must match number of sites")

    init_occ = [int(x) for x in cfg["initial_state"]["occupied_sites"]]
    if len(set(init_occ)) != len(init_occ):
        raise ValueError("occupied_sites contains duplicates")

    occupied = np.zeros(n_sites, dtype=bool)
    occupied[init_occ] = True

    site_to_carrier = -np.ones(n_sites, dtype=int)
    carrier_sites = np.array(init_occ, dtype=int)
    n_carriers = int(carrier_sites.size)
    for cid, s in enumerate(carrier_sites):
        site_to_carrier[s] = cid

    cart0 = frac @ cell
    carrier_r0 = cart0[carrier_sites].copy()
    carrier_r = carrier_r0.copy()

    # build directed edge list with displacement vectors
    edges: List[Edge] = []
    edge_id: Dict[Tuple[int, int], int] = {}
    for i in range(n_sites):
        fi = frac[i]
        for nb in neighbors[i]:
            j = int(nb["j"])
            sx, sy, sz = int(nb["shift"][0]), int(nb["shift"][1]), int(nb["shift"][2])
            fj_img = frac[j] + np.array([sx, sy, sz], dtype=float)
            dfrac = fj_img - fi
            dcart = dfrac @ cell
            eid = len(edges)
            edges.append(Edge(i=i, j=j, shift=(sx, sy, sz), delta_cart_A=dcart))
            edge_id[(i, j)] = eid

    m_edges = len(edges)
    if m_edges == 0:
        raise RuntimeError("No edges found in lattice neighbor list.")

    # initialize rates
    rates = np.zeros(m_edges, dtype=float)
    for eid, e in enumerate(edges):
        if occupied[e.i] and (not occupied[e.j]):
            rates[eid] = rate_constant(
                rate_model, nu, barrier_eV, T, site_E_arr[e.i], site_E_arr[e.j]
            )

    ft = FenwickTree(rates)

    sim = cfg["simulation"]
    max_steps = int(sim.get("max_steps", 100000))
    max_time_s = sim.get("max_time_s", None)
    max_time_s = float(max_time_s) if max_time_s is not None else None
    save_every = int(sim.get("save_every", 1000))
    seed = int(sim.get("seed", 12345))

    out_dir = Path(cfg["output"]["out_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    rng = np.random.default_rng(seed)

    times: list[float] = []
    msd: list[float] = []
    steps_saved: list[int] = []

    t = 0.0
    step = 0

    def record() -> None:
        disp = carrier_r - carrier_r0
        msd_val = float(np.mean(np.sum(disp * disp, axis=1)))
        times.append(t)
        msd.append(msd_val)
        steps_saved.append(step)

    record()

    def recompute_edge(eid_local: int) -> None:
        e = edges[eid_local]
        old = rates[eid_local]
        if occupied[e.i] and (not occupied[e.j]):
            new = rate_constant(
                rate_model, nu, barrier_eV, T, site_E_arr[e.i], site_E_arr[e.j]
            )
        else:
            new = 0.0
        if new != old:
            rates[eid_local] = new
            ft.update(eid_local, new, old)

    while step < max_steps:
        R = ft.total()
        if R <= 0.0:
            break

        r1 = rng.random()
        target = r1 * R
        if target == 0.0:
            target = np.nextafter(0.0, 1.0) * R
        eid = ft.find_prefix(target)

        r2 = rng.random()
        if r2 <= 0.0:
            r2 = np.nextafter(0.0, 1.0)
        dt = -math.log(r2) / R
        t += dt

        e = edges[eid]
        i, j = e.i, e.j

        if (not occupied[i]) or occupied[j]:
            raise RuntimeError("Selected a disabled event. Rate table corrupted.")

        cid = site_to_carrier[i]
        if cid < 0:
            raise RuntimeError("Occupied site has no carrier id; inconsistent state.")

        carrier_r[cid] += e.delta_cart_A

        occupied[i] = False
        occupied[j] = True
        site_to_carrier[i] = -1
        site_to_carrier[j] = cid
        carrier_sites[cid] = j

        # local rate updates for affected edges
        impacted: set[int] = set()

        for nb in neighbors[i]:
            impacted.add(edge_id[(i, int(nb["j"]))])
        for nb in neighbors[j]:
            impacted.add(edge_id[(j, int(nb["j"]))])

        for nb in neighbors[i]:
            k = int(nb["j"])
            if (k, i) in edge_id:
                impacted.add(edge_id[(k, i)])
        for nb in neighbors[j]:
            k = int(nb["j"])
            if (k, j) in edge_id:
                impacted.add(edge_id[(k, j)])

        for eid_local in impacted:
            recompute_edge(eid_local)

        step += 1

        if step % save_every == 0:
            record()

        if max_time_s is not None and t >= max_time_s:
            break

    if steps_saved[-1] != step:
        record()

    np.savez_compressed(
        out_dir / "kmc_trace.npz",
        time_s=np.array(times, dtype=float),
        msd_A2=np.array(msd, dtype=float),
        steps=np.array(steps_saved, dtype=int),
        carrier_r_A=carrier_r,
        carrier_r0_A=carrier_r0,
        carrier_sites=carrier_sites,
    )

    terminated = "absorbing_state"
    if step >= max_steps:
        terminated = "max_steps"
    elif max_time_s is not None and t >= max_time_s:
        terminated = "max_time"

    summary = {
        "config": cfg,
        "lattice": str(lattice_path),
        "n_sites": n_sites,
        "n_edges": m_edges,
        "n_carriers": n_carriers,
        "steps_executed": step,
        "time_s": t,
        "terminated_reason": terminated,
        "seed": seed,
    }
    (out_dir / "kmc_summary.json").write_text(json.dumps(summary, indent=4))

    print(f"Wrote: {out_dir / 'kmc_trace.npz'}")
    print(f"Wrote: {out_dir / 'kmc_summary.json'}")
    print(f"Steps executed: {step}")
    print(f"Simulated time: {t:.6e} s")


if __name__ == "__main__":
    main()
