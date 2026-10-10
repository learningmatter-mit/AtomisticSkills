"""
Analyze monitored NVT runs of a crystal and compare them with classical theory.

Reads the ASE MD logs written by ``mace.run_md`` / ``matgl.run_md`` (columns
``Time[ps] Etot[eV] Epot[eV] Ekin[eV] T[K]``) together with the ``md_inputs.json``
saved next to each log, and reports:

* for each equilibration (stage-1) log: where the ``equilibration`` monitor
  stopped the run and the std(T) of its last window, recomputed exactly as
  ``EquilibrationMonitor`` does;
* for each production log: the mean temperature, the std of the instantaneous
  temperature against the canonical value T*sqrt(2/(3N)), and the mean
  potential-energy rise above the relaxed minimum against the classical
  equipartition value (3/2) k_B T per atom;
* with two or more production temperatures: the finite-difference heat capacity
  against the Dulong-Petit limit 3 k_B per atom (3R per mole).

Usage:
    python analyze_md_monitor_run.py \
        --relax-dir relax \
        --stage1-logs stage1/Cu256_300.0K_nvt.log stage1b/Cu256_300.0K_nvt.log \
        --stage1-labels "300 K, threshold 50 K" "300 K, threshold 30 K" \
        --production-logs prod300/Cu256_300.0K_nvt.log prod100/Cu256_100.0K_nvt.log \
        --n-atoms 256 --output-dir results

Requirements:
    - Environment: cpu (or mlip)
    - Required packages: numpy, matplotlib, ase, pyyaml
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from ase.io import read  # noqa: E402

from src.utils.config_utils import save_skill_inputs  # noqa: E402

# CODATA 2022 exact values (https://physics.nist.gov/cgi-bin/cuu/Value?kev and ?r)
KB_EV_PER_K = 8.617333262e-5
R_J_PER_MOL_K = 8.314462618
DEFAULT_TEMP_STD_THRESHOLD = 50.0  # EquilibrationMonitor default (K)

plt.rcParams.update({"font.size": 14})


def load_md_log(log_path: Path) -> dict[str, np.ndarray]:
    """
    Load an ASE MD log file.

    Args:
        log_path: Path to the log written by ASE's MDLogger.

    Returns:
        Dictionary with arrays 'time_ps', 'etot', 'epot', 'ekin' (eV) and 'temp' (K).
    """
    data = np.loadtxt(log_path, skiprows=1, ndmin=2)
    return {
        "time_ps": data[:, 0],
        "etot": data[:, 1],
        "epot": data[:, 2],
        "ekin": data[:, 3],
        "temp": data[:, 4],
    }


def load_md_inputs(log_path: Path) -> dict:
    """
    Load the md_inputs.json that run_md writes next to its log.

    Args:
        log_path: Path to the MD log file.

    Returns:
        Dictionary of run_md input parameters.
    """
    return json.loads((log_path.parent / "md_inputs.json").read_text())


def window_entries(md_inputs: dict) -> int:
    """
    Number of logged entries in one EquilibrationMonitor window.

    Args:
        md_inputs: run_md input parameters (timestep, log_interval, monitor_params).

    Returns:
        Window length in log entries, as computed by EquilibrationMonitor.
    """
    params = md_inputs.get("monitor_params") or {}
    window_ps = params.get("window_ps", 1.0)
    return max(
        2, int(window_ps * 1000 / md_inputs["timestep"] / md_inputs["log_interval"])
    )


def rolling_std(values: np.ndarray, n_window: int) -> np.ndarray:
    """
    Population std over the trailing window, NaN until the window is full.

    Args:
        values: Time series.
        n_window: Window length in samples.

    Returns:
        Array of the same length with the trailing-window std.
    """
    out = np.full(len(values), np.nan)
    for i in range(n_window - 1, len(values)):
        out[i] = np.std(values[i - n_window + 1 : i + 1])
    return out


def block_mean_sem(values: np.ndarray, n_blocks: int) -> tuple[float, float]:
    """
    Mean and standard error of the mean from non-overlapping block averages.

    Args:
        values: Time series.
        n_blocks: Number of contiguous blocks.

    Returns:
        Tuple (mean, standard error of the mean).
    """
    blocks = np.array([b.mean() for b in np.array_split(values, n_blocks)])
    return float(values.mean()), float(blocks.std(ddof=1) / np.sqrt(n_blocks))


def analyze_stage1(log_path: Path, label: str) -> dict:
    """
    Summarize where the equilibration monitor stopped a stage-1 run.

    Args:
        log_path: Stage-1 MD log.
        label: Label used in plots and the JSON summary.

    Returns:
        Dictionary with the stop time, step, threshold and recomputed std(T).
    """
    log = load_md_log(log_path)
    md_inputs = load_md_inputs(log_path)
    n_win = window_entries(md_inputs)
    params = md_inputs.get("monitor_params") or {}
    threshold = params.get("temp_std_threshold", DEFAULT_TEMP_STD_THRESHOLD)
    stds = rolling_std(log["temp"], n_win)
    return {
        "label": label,
        "log": log_path.name,
        "target_temperature_K": md_inputs["temperature"],
        "max_steps": md_inputs["steps"],
        "temp_std_threshold_K": threshold,
        "window_entries": n_win,
        "stop_time_ps": float(log["time_ps"][-1]),
        "stop_step": int(round(log["time_ps"][-1] * 1000 / md_inputs["timestep"])),
        "std_T_last_window_K": float(stds[-1]),
        "T_at_stop_K": float(log["temp"][-1]),
        "max_T_K": float(log["temp"].max()),
    }


def analyze_production(
    log_path: Path, n_atoms: int, e_min_per_atom: float, n_blocks: int
) -> dict:
    """
    Compare production-run averages with classical canonical theory.

    Args:
        log_path: Production MD log.
        n_atoms: Number of atoms in the simulation cell.
        e_min_per_atom: Relaxed (0 K) potential energy per atom in eV.
        n_blocks: Number of blocks for the standard error.

    Returns:
        Dictionary of measured averages and theoretical reference values.
    """
    log = load_md_log(log_path)
    md_inputs = load_md_inputs(log_path)
    t_target = float(md_inputs["temperature"])
    # Skip the first entry: it is the restart frame shared with stage 1.
    temp = log["temp"][1:]
    d_epot = (log["epot"][1:] / n_atoms - e_min_per_atom) * 1000.0  # meV/atom
    ekin = log["ekin"][1:] / n_atoms * 1000.0  # meV/atom
    t_mean, t_sem = block_mean_sem(temp, n_blocks)
    u_mean, u_sem = block_mean_sem(d_epot, n_blocks)
    k_mean, k_sem = block_mean_sem(ekin, n_blocks)
    e_mean, e_sem = block_mean_sem(d_epot + ekin, n_blocks)
    equip_target = 1.5 * KB_EV_PER_K * t_target * 1000.0
    equip_mean_t = 1.5 * KB_EV_PER_K * t_mean * 1000.0
    sigma_t_canonical = t_target * np.sqrt(2.0 / (3.0 * n_atoms))
    return {
        "log": log_path.name,
        "target_temperature_K": t_target,
        "duration_ps": float(log["time_ps"][-1] - log["time_ps"][0]),
        "n_samples": int(len(temp)),
        "T_mean_K": t_mean,
        "T_sem_K": t_sem,
        "T_rel_error_pct": 100.0 * (t_mean - t_target) / t_target,
        "T_std_K": float(temp.std()),
        "T_std_canonical_K": float(sigma_t_canonical),
        "dEpot_mean_meV_per_atom": u_mean,
        "dEpot_sem_meV_per_atom": u_sem,
        "Ekin_mean_meV_per_atom": k_mean,
        "Ekin_sem_meV_per_atom": k_sem,
        "Etot_minus_Emin_mean_meV_per_atom": e_mean,
        "Etot_minus_Emin_sem_meV_per_atom": e_sem,
        "equipartition_1p5kT_target_meV": equip_target,
        "equipartition_1p5kT_meanT_meV": equip_mean_t,
        "dEpot_vs_1p5kT_target_pct": 100.0 * (u_mean - equip_target) / equip_target,
        "dEpot_over_Ekin": u_mean / k_mean,
        "dEpot_over_Ekin_sem": u_sem / k_mean,
        "time_ps": log["time_ps"][1:] - log["time_ps"][0],
        "dEpot_series": d_epot,
    }


def dulong_petit(productions: list[dict]) -> dict:
    """
    Finite-difference heat capacity between the lowest and highest temperature.

    Args:
        productions: Production summaries from analyze_production.

    Returns:
        Dictionary with c_v in k_B/atom and J/(mol K), and the 3R reference.
    """
    lo = min(productions, key=lambda p: p["T_mean_K"])
    hi = max(productions, key=lambda p: p["T_mean_K"])
    d_e = (
        hi["Etot_minus_Emin_mean_meV_per_atom"]
        - lo["Etot_minus_Emin_mean_meV_per_atom"]
    )
    d_t = hi["T_mean_K"] - lo["T_mean_K"]
    d_e_err = np.hypot(
        hi["Etot_minus_Emin_sem_meV_per_atom"], lo["Etot_minus_Emin_sem_meV_per_atom"]
    )
    cv_kb = d_e / 1000.0 / d_t / KB_EV_PER_K
    cv_kb_err = d_e_err / 1000.0 / d_t / KB_EV_PER_K
    return {
        "T_low_K": lo["T_mean_K"],
        "T_high_K": hi["T_mean_K"],
        "cv_kB_per_atom": float(cv_kb),
        "cv_kB_per_atom_sem": float(cv_kb_err),
        "cv_J_per_mol_K": float(cv_kb * R_J_PER_MOL_K),
        "cv_J_per_mol_K_sem": float(cv_kb_err * R_J_PER_MOL_K),
        "dulong_petit_kB_per_atom": 3.0,
        "dulong_petit_J_per_mol_K": 3.0 * R_J_PER_MOL_K,
        "rel_error_pct": 100.0 * (cv_kb - 3.0) / 3.0,
    }


def plot_stage1(
    logs: list[Path], labels: list[str], summaries: list[dict], n_atoms: int, out: Path
) -> None:
    """
    Plot T(t) and the trailing-window std(T) of the stage-1 runs with stop points.

    Args:
        logs: Stage-1 MD logs.
        labels: Legend labels.
        summaries: Outputs of analyze_stage1 (same order).
        n_atoms: Number of atoms (for the canonical std band).
        out: Output path without suffix.
    """
    colors = plt.get_cmap("tab10").colors
    fig, (ax_t, ax_s) = plt.subplots(2, 1, figsize=(6, 5), sharex=True)
    for i, (log_path, label, summ) in enumerate(zip(logs, labels, summaries)):
        log = load_md_log(log_path)
        c = colors[i % len(colors)]
        t_target = summ["target_temperature_K"]
        sigma = t_target * np.sqrt(2.0 / (3.0 * n_atoms))
        ax_t.plot(log["time_ps"], log["temp"], color=c, linewidth=2.5, label=label)
        ax_t.axhspan(t_target - sigma, t_target + sigma, color=c, alpha=0.08)
        stds = rolling_std(log["temp"], summ["window_entries"])
        ax_s.plot(log["time_ps"], stds, color=c, linewidth=2.5)
        ax_s.axhline(
            summ["temp_std_threshold_K"], color=c, linestyle=":", linewidth=1.5
        )
        for ax in (ax_t, ax_s):
            ax.axvline(summ["stop_time_ps"], color=c, linestyle="--", linewidth=1.5)
        ax_s.plot(summ["stop_time_ps"], summ["std_T_last_window_K"], "o", color=c)
    ax_t.set_ylabel("T (K)", fontweight="bold")
    ax_s.set_ylabel("std(T), 1 ps (K)", fontweight="bold")
    ax_s.set_xlabel("Time (ps)", fontweight="bold")
    ax_t.legend(frameon=False, fontsize=10, loc="center right")
    for ax in (ax_t, ax_s):
        ax.grid(False)
    plt.tight_layout()
    for suffix in (".png", ".svg"):
        plt.savefig(out.with_suffix(suffix), dpi=200, bbox_inches="tight")
    plt.close(fig)


def plot_production(productions: list[dict], out: Path) -> None:
    """
    Plot the potential-energy rise per atom against (3/2) k_B T.

    Args:
        productions: Outputs of analyze_production.
        out: Output path without suffix.
    """
    colors = plt.get_cmap("tab10").colors
    fig, ax = plt.subplots(figsize=(6, 5))
    for i, prod in enumerate(sorted(productions, key=lambda p: -p["T_mean_K"])):
        c = colors[(i + 3) % len(colors)]
        t = prod["time_ps"]
        series = prod["dEpot_series"]
        running = np.cumsum(series) / np.arange(1, len(series) + 1)
        ax.plot(t, series, color=c, linewidth=0.8, alpha=0.35)
        ax.plot(
            t,
            running,
            color=c,
            linewidth=2.5,
            label=f"{prod['target_temperature_K']:.0f} K running mean",
        )
        ax.axhline(
            prod["equipartition_1p5kT_target_meV"],
            color="k",
            linestyle="--",
            linewidth=1.5,
        )
    ax.plot([], [], "k--", linewidth=1.5, label=r"$\frac{3}{2}k_BT$ (harmonic)")
    ax.set_xlabel("Production time (ps)", fontweight="bold")
    ax.set_ylabel(r"$E_{pot}-E_{min}$ (meV/atom)", fontweight="bold")
    ax.legend(frameon=False, fontsize=11)
    ax.grid(False)
    plt.tight_layout()
    for suffix in (".png", ".svg"):
        plt.savefig(out.with_suffix(suffix), dpi=200, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare monitored NVT runs of a crystal with classical theory."
    )
    parser.add_argument(
        "--relax-dir",
        required=True,
        help="relax_structure output dir (relaxed_structure.cif, relaxed_energy.txt)",
    )
    parser.add_argument(
        "--stage1-logs", nargs="+", required=True, help="Equilibration (monitor) logs"
    )
    parser.add_argument(
        "--stage1-labels", nargs="+", default=None, help="Labels for the stage-1 logs"
    )
    parser.add_argument(
        "--production-logs", nargs="+", required=True, help="Production MD logs"
    )
    parser.add_argument(
        "--n-atoms", type=int, required=True, help="Atoms in the MD supercell"
    )
    parser.add_argument(
        "--n-blocks", type=int, default=5, help="Blocks for the standard error"
    )
    parser.add_argument("--output-dir", default=".", help="Where to write results")
    args = parser.parse_args()

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    relax_dir = Path(args.relax_dir)
    relaxed = read(relax_dir / "relaxed_structure.cif")
    e_relaxed = float((relax_dir / "relaxed_energy.txt").read_text())
    e_min_per_atom = e_relaxed / len(relaxed)

    stage1_logs = [Path(p) for p in args.stage1_logs]
    labels = args.stage1_labels or [p.parent.name for p in stage1_logs]
    stage1 = [analyze_stage1(p, lab) for p, lab in zip(stage1_logs, labels)]
    productions = [
        analyze_production(Path(p), args.n_atoms, e_min_per_atom, args.n_blocks)
        for p in args.production_logs
    ]

    summary = {
        "n_atoms": args.n_atoms,
        "relaxed_lattice_a_A": float(relaxed.cell.lengths()[0]),
        "E_min_eV_per_atom": e_min_per_atom,
        "stage1_equilibration": stage1,
        "production": [
            {k: v for k, v in p.items() if k not in ("time_ps", "dEpot_series")}
            for p in productions
        ],
    }
    if len(productions) >= 2:
        summary["dulong_petit"] = dulong_petit(productions)

    (out_dir / "md_monitor_validation.json").write_text(json.dumps(summary, indent=2))
    plot_stage1(
        stage1_logs, labels, stage1, args.n_atoms, out_dir / "equilibration_monitor"
    )
    plot_production(productions, out_dir / "potential_energy_equipartition")
    save_skill_inputs(args, str(out_dir))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
