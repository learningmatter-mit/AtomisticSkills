"""
BVT/GCMC Monte Carlo adsorption of CO2 or N2 into a periodic framework using any supported MLIP.

Usage:
    python run_gcmc.py --cif path/to/relaxed.cif --output-dir ./out \\
        --calculator fairchem --model-name uma-s-1p1.pt --task-name odac \\
        --steps 100000 --temperature-K 298 --pressure-bar 1

Requirements:
    - Conda environment: Varies based on `--calculator`
    - Required packages: ase, ase-mc, numpy, matplotlib, torch, MLIP backend package
"""

import argparse
import logging
import sys
import time
from pathlib import Path

_project_root = Path(__file__).resolve().parents[4]
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import numpy as np
from ase import Atoms, build
from ase.io import read
from ase.optimize import LBFGS

from ase_mc import BVT, BVT_GCMCOnly, MonteCarlo
from gcmc_common import (
    B_peng_robinson_for_framework,
    analyze_and_plot_single,
    build_moveset_bvt,
    get_radius_probe,
    load_restart_atoms,
    print_restart_sanity_single,
    GAS_PR_PARAMS_CO2_N2,
    gcmc_output_dir,
    load_host_atoms,
    mc_traj_log_paths,
    maybe_record_starting_config,
    run_mc_with_timing,
    write_timing_kv,
    compute_eq_loading_from_traj_single,
    gcmc_standalone_payload_single,
    write_gcmc_results_json,
    ensure_tags,
    qst_single_fluctuation_from_series,
)
from src.utils.mlips.loader import load_wrapper


LOGGER = logging.getLogger(__name__)


def normalize_charge_spin(atoms) -> None:
    info = atoms.info if isinstance(atoms.info, dict) else {}
    if atoms.info is not info:
        atoms.info = info
    try:
        charge = int(info.get("charge", info.get("chg", 0)))
    except Exception:
        charge = 0
    try:
        spin_mult = int(
            info.get("spin_multiplicity", info.get("multiplicity", info.get("spin", 1)))
        )
    except Exception:
        spin_mult = 1
    atoms.info["charge"] = charge
    atoms.info["spin_multiplicity"] = spin_mult
    atoms.info["spin"] = spin_mult


def retag_all_guests_single_species(atoms: Atoms, host_natoms: int) -> int | None:
    total = len(atoms)
    if total <= host_natoms:
        return None
    tags = np.asarray(atoms.get_tags(), dtype=int)
    if tags.shape[0] != total:
        tags = np.zeros(total, dtype=int)
    host_max = int(tags[:host_natoms].max()) if host_natoms > 0 else int(tags.max())
    guest_tag = host_max + 1
    tags[host_natoms:] = guest_tag
    atoms.set_tags(tags)
    return guest_tag


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="BVT Monte Carlo adsorption of a probe gas into a periodic host using a generic MLIP."
    )
    p.add_argument("--cif", type=Path, required=True, help="Path to periodic framework CIF file.")
    p.add_argument("--steps", type=int, required=True, help="Number of Monte Carlo steps.")
    p.add_argument("--temperature-K", type=float, required=True, help="Simulation temperature in Kelvin.")
    p.add_argument("--pressure-bar", type=float, default=1.0, help="Gas pressure in bar.")
    p.add_argument("--scheme", choices=["gcmc", "hmc"], default="gcmc")
    p.add_argument("--adsorbate", choices=["CO2", "N2"], default="CO2", help="Probe gas to adsorb.")
    p.add_argument("--output-dir", type=Path, default=Path("."), help="Directory for results.")
    p.add_argument("--restart-traj", type=Path, default=None, help="Optional: restart from previous ASE trajectory.")
    p.add_argument("--restart-frame", type=int, default=-1, help="Frame index to restart from.")
    p.add_argument(
        "--calculator",
        type=str,
        required=True,
        choices=["mace", "fairchem", "matgl"],
        help="Backend MLIP calculator to use."
    )
    p.add_argument("--model-name", type=str, required=True, help="Name or path of the model checkpoint")
    p.add_argument(
        "--task-name",
        type=str,
        default=None,
        help="Optional task name required by some calculators (e.g. odac for fairchem).",
    )
    p.add_argument("--device", type=str, default="auto", help="Device string (e.g. 'cuda', 'cpu', 'auto').")
    p.add_argument("--model-tag", type=str, default=None, help="Model tag for metadata.")
    p.add_argument("--output", "-o", type=Path, default=None, help="Output JSON path (default: output_dir/gcmc_results.json)")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    cif_path = args.cif

    out_dir = gcmc_output_dir(args.output_dir)
    if args.output is not None:
        gcmc_json_path = args.output
    else:
        gcmc_json_path = out_dir / "gcmc_results.json"

    LOGGER.info("CIF          : %s", cif_path)
    LOGGER.info("Calculator   : %s", args.calculator)
    LOGGER.info("Model name   : %s", args.model_name)
    LOGGER.info("Task name    : %s", args.task_name)
    LOGGER.info("Device       : %s", args.device)
    LOGGER.info("Steps (MC)   : %d", args.steps)
    LOGGER.info("T [K]        : %.3f", args.temperature_K)
    LOGGER.info("p [bar]      : %.3f", args.pressure_bar)
    LOGGER.info("Scheme       : %s", args.scheme)
    LOGGER.info("Adsorbate    : %s", args.adsorbate)
    LOGGER.info("Output dir   : %s", out_dir)

    t0 = time.perf_counter()
    wrapper = load_wrapper(
        args.calculator,
        model_name=args.model_name,
        device=args.device,
        task_name=args.task_name,
    )
    calc_mol = wrapper.create_calculator()
    calc_host = wrapper.create_calculator()
    LOGGER.info("Loaded generic MLIP calculators in %.3f s", time.perf_counter() - t0)

    PR_PARAMS = GAS_PR_PARAMS_CO2_N2
    gas = PR_PARAMS[args.adsorbate]
    t1 = time.perf_counter()
    probe = build.molecule(gas["mol_name"])
    normalize_charge_spin(probe)
    probe.calc = calc_mol
    out_dir.mkdir(parents=True, exist_ok=True)
    opt = LBFGS(probe, trajectory=None, logfile=None)
    opt.run(fmax=0.05, steps=200)
    E_probe = probe.get_potential_energy()
    LOGGER.info(
        "Probe relaxation done in %.3f s | E_probe = %.6f eV",
        time.perf_counter() - t1,
        E_probe,
    )

    host, host_natoms, restart_label = load_host_atoms(
        cif_path=cif_path,
        restart_traj=args.restart_traj,
        restart_frame=args.restart_frame,
        read_fn=read,
        load_restart_atoms_fn=load_restart_atoms,
    )
    normalize_charge_spin(host)
    host.calc = calc_host

    retagged = False
    guest_tag = None
    if args.restart_traj is not None:
        guest_tag = retag_all_guests_single_species(host, host_natoms)
        retagged = guest_tag is not None
    tags = ensure_tags(host)
    host_max = int(tags[:host_natoms].max()) if host_natoms > 0 else int(tags.max())
    starting_tag = guest_tag if guest_tag is not None else (host_max + 1)

    print_restart_sanity_single(
        host, host_natoms, probe,
        label=restart_label + (" [retagged guests]" if retagged else ""),
    )
    LOGGER.info(
        "Host atoms=%d | host_natoms(from CIF)=%d | pbc=%s",
        len(host),
        host_natoms,
        tuple(bool(x) for x in host.pbc),
    )

    T = args.temperature_K
    p_bar = args.pressure_bar
    B_val, beta_mu, phi, V_cell_m3 = B_peng_robinson_for_framework(
        host,
        T=T,
        p_bar=p_bar,
        Tc=gas["Tc"],
        Pc=gas["Pc"],
        omega=gas["omega"],
        molar_mass=gas["M"],
    )
    LOGGER.info(
        "Framework volume: %.3f Å^3 (%.3e m^3)",
        host.get_volume(),
        V_cell_m3,
    )
    LOGGER.info(
        "PR EOS: B = %.3f, beta_mu = %.6f, phi = %.6f",
        B_val,
        beta_mu,
        phi,
    )

    t3 = time.perf_counter()
    exclusion_list = np.arange(host_natoms)
    rcavity = 0.8 * get_radius_probe(probe)
    grid_resolution = 10
    translate_max = 5.0
    bvt_kwargs = dict(
        temperature_K=T,
        b_parameter=[B_val],
        species=[probe],
        reference_energy=[E_probe],
        rcavity=rcavity,
        grid_resolution=grid_resolution,
        cavity_bias=True,
        exclusion_list=exclusion_list,
        starting_tag=starting_tag,
    )
    EnsembleClass = BVT_GCMCOnly if args.scheme == "gcmc" else BVT
    ensemble = EnsembleClass(**bvt_kwargs)
    moveset = build_moveset_bvt(ensemble, scheme=args.scheme)
    moveset.adjust_parameter("Translate", "max_delta", translate_max)
    LOGGER.info(
        "BVT/moveset ready in %.3f s | rcavity=%.2f Å | grid=%d | b=%.2f | translate_max=%.2f Å",
        time.perf_counter() - t3,
        rcavity,
        grid_resolution,
        B_val,
        translate_max,
    )

    restarting = args.restart_traj is not None
    traj_path, log_path = mc_traj_log_paths(out_dir=out_dir, restarting=restarting, stub="mc")
    dyn = MonteCarlo(
        atoms=host,
        dft_calc=calc_host,
        moveset=moveset,
        trajectory=str(traj_path),
        logfile=str(log_path),
        loginterval=20,
        gcmc_energy_only=(args.scheme == "gcmc"),
    )
    maybe_record_starting_config(dyn)
    LOGGER.info(
        "Starting MC run: scheme=%s, steps=%d, traj=%s, log=%s",
        args.scheme,
        args.steps,
        traj_path.name,
        log_path.name,
    )
    dt_mc, steps_per_sec = run_mc_with_timing(dyn=dyn, steps=args.steps, perf_counter=time.perf_counter)
    LOGGER.info("MC completed in %.3f s | %.2f steps/s", dt_mc, steps_per_sec)

    write_timing_kv(
        out_dir=out_dir,
        kv={
            "scheme": args.scheme,
            "steps": args.steps,
            "temperature_K": args.temperature_K,
            "pressure_bar": args.pressure_bar,
            "restart_traj": args.restart_traj,
            "restart_frame": args.restart_frame,
            "host_natoms": host_natoms,
            "wall_time_s": f"{dt_mc:.6f}",
            "steps_per_s": f"{steps_per_sec:.6f}",
        },
    )

    LOGGER.info("Analyzing trajectory and writing nmols/energy plots...")
    analyze_and_plot_single(traj_path, probe, out_dir, host_natoms=host_natoms)

    # Qst (isosteric heat) via fluctuation formula from time series
    qst_kJ_mol = None
    qst_std_kJ_mol = None
    qst_n_blocks = None
    qst_block_size = None
    try:
        nmols_path = out_dir / "nmols.npy"
        energy_path = out_dir / "energy.npy"
        if nmols_path.exists() and energy_path.exists():
            energy_eV = np.load(energy_path)
            nmols = np.load(nmols_path)
            (
                qst_kJ_mol,
                qst_std_kJ_mol,
                qst_n_blocks,
                qst_block_size,
            ) = qst_single_fluctuation_from_series(
                energy_eV=energy_eV,
                nmols=nmols,
                temperature_K=args.temperature_K,
                mol_energy_eV=E_probe,
            )
    except Exception as e:
        LOGGER.warning("Failed to compute Qst from series: %s", e)

    q_mmol_g = compute_eq_loading_from_traj_single(
        traj_path=traj_path,
        probe=probe,
        host=host,
        host_natoms=host_natoms,
        frac_tail=0.05,
    )
    payload = gcmc_standalone_payload_single(
        adsorbate=args.adsorbate,
        temperature_K=args.temperature_K,
        pressure_bar=args.pressure_bar,
        scheme=args.scheme,
        q_total_mmol_g=q_mmol_g,
    )
    payload["wall_time_s"] = dt_mc
    payload["steps_per_s"] = steps_per_sec
    payload["qst_kJ_mol"] = qst_kJ_mol
    payload["qst_std_kJ_mol"] = qst_std_kJ_mol
    payload["qst_n_blocks"] = qst_n_blocks
    payload["qst_block_size"] = qst_block_size
    write_gcmc_results_json(gcmc_json_path, payload)
    LOGGER.info("Wrote %s", gcmc_json_path)

    # Remove traj/log and .npy intermediates; keep JSON and PNGs (nmols.png, energy.png)
    for p in (
        traj_path,
        log_path,
        out_dir / "nmols.npy",
        out_dir / "energy.npy",
    ):
        try:
            if p is not None and p.exists():
                p.unlink()
        except Exception as e:
            LOGGER.warning("Could not remove %s: %s", p, e)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
