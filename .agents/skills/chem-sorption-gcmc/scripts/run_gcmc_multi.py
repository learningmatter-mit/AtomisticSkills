"""
Multicomponent BVT GCMC (N-component mixture) in a periodic framework using UMA (FairChem).

Same interface as COFclean/gcmc/uma_ase_gcmc_multicomponent.py: arbitrary mixture via
--gases, --y, --p-total-bar. Species order is canonical (e.g. CO2, N2); partial pressures
are p_i = y_i * p_total.

Usage:
    python run_gcmc_uma_multi.py --cif path/to/relaxed.cif --output-dir ./out --weights path/to/uma.pt \\
        --steps 100000 --temperature-K 298 --gases CO2 N2 --y 0.15 0.85 --p-total-bar 1.0

Requirements:
    - Conda environment: Varies based on `--calculator`
    - Required packages: ase, ase-mc, numpy, matplotlib, torch, MLIP backend package
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path
from typing import Optional

import numpy as np
from ase import Atoms, build
from ase.io import read
from ase.optimize import LBFGS

_project_root = Path(__file__).resolve().parents[4]
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from ase_mc import BVT, BVT_GCMCOnly, MonteCarlo
from gcmc_common import (
    B_peng_robinson_mixture_for_framework,
    analyze_and_plot_multicomponent,
    build_moveset_bvt,
    canonicalize_species_key,
    ensure_tags,
    get_radius_probe,
    load_host_atoms,
    load_restart_atoms,
    print_restart_sanity_multicomponent,
    run_mc,
    write_timing_kv,
    compute_eq_loading_from_traj_multicomponent,
    gcmc_standalone_payload_multicomponent,
    write_gcmc_results_json,
    GAS_PR_PARAMS_CO2_N2,
    gcmc_output_dir,
    _parse_kij_entry,
    _resolve_species_name,
    qst_multicomponent_fluctuation_from_series,
)
from src.utils.mlips.loader import load_wrapper


LOGGER = logging.getLogger(__name__)

# Gas DB: same as single-component skill (CO2, N2). Extend here or via JSON if needed.
GAS_DB = GAS_PR_PARAMS_CO2_N2


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


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Multicomponent BVT GCMC (N-component mixture) in a periodic host (CIF) using UMA/FairChem."
    )
    p.add_argument("--cif", type=Path, required=True, help="Path to periodic framework CIF file.")
    p.add_argument("--steps", type=int, required=True, help="Number of Monte Carlo steps.")
    p.add_argument("--temperature-K", type=float, required=True, help="Simulation temperature in Kelvin.")
    p.add_argument("--scheme", choices=["gcmc", "hmc"], default="gcmc")
    p.add_argument(
        "--output-dir",
        type=Path,
        default=Path("."),
        help="Directory for results (multi_gcmc.json + PNGs).",
    )
    p.add_argument("--restart-traj", type=Path, default=None, help="Optional: restart from previous ASE .traj.")
    p.add_argument("--restart-frame", type=int, default=-1, help="Frame index to restart from (default -1).")
    p.add_argument("--device", type=str, default="auto", help="Device string (e.g. 'cuda', 'cpu', 'auto').")
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
    p.add_argument(
        "--output",
        "-o",
        type=Path,
        default=None,
        help="Output JSON path (default: output_dir/multi_gcmc.json)",
    )
    p.add_argument(
        "--starting-tag",
        type=int,
        default=1,
        help="Starting tag for species; tags assigned in canonical order: tag = starting_tag + i.",
    )
    p.add_argument("--grid-resolution", type=int, default=10, help="BVT cavity grid resolution.")
    p.add_argument("--translate-max", type=float, default=5.0, help="Translate move max_delta (Å).")
    p.add_argument("--probe-fmax", type=float, default=0.05, help="LBFGS fmax for probe relaxation.")
    p.add_argument("--probe-steps", type=int, default=200, help="LBFGS max steps for probe relaxation.")
    # Mixture: N components (same as COFclean)
    p.add_argument("--gases", nargs="+", type=str, default=None, help="Gas species list, e.g. --gases CO2 N2")
    p.add_argument(
        "--y",
        nargs="+",
        type=float,
        default=None,
        help="Mole fractions aligned with --gases, e.g. --y 0.15 0.85 (will be normalized).",
    )
    p.add_argument("--p-total-bar", type=float, default=None, help="Total pressure in bar.")
    p.add_argument("--kij", action="append", default=[], help="Optional PR kij entries like 'CO2,N2,0.0'. Repeatable.")
    return p.parse_args(args=argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv)

    if args.gases is None or args.y is None or args.p_total_bar is None:
        raise ValueError("Must pass --gases, --y, and --p-total-bar.")

    cif_path = args.cif
    T = float(args.temperature_K)

    # Resolve species names against GAS_DB (same as COFclean)
    gases_in = [_resolve_species_name(g, GAS_DB) for g in args.gases]
    y_in = np.asarray(args.y, dtype=float)

    if len(gases_in) != len(y_in):
        raise ValueError(f"--gases (n={len(gases_in)}) and --y (n={len(y_in)}) must match.")
    if len(set(gases_in)) != len(gases_in):
        raise ValueError(f"Duplicate gas in --gases: {gases_in}")
    if np.any(y_in < 0) or y_in.sum() <= 0:
        raise ValueError(f"Invalid --y: {y_in}")

    # Normalize composition and canonicalize ordering for restart stability
    y_in = y_in / y_in.sum()
    y_map = {g: float(yi) for g, yi in zip(gases_in, y_in)}
    species_names = sorted(y_map.keys(), key=canonicalize_species_key)
    y = np.array([y_map[nm] for nm in species_names], dtype=float)

    p_total_bar = float(args.p_total_bar)
    if p_total_bar <= 0:
        raise ValueError(f"--p-total-bar must be > 0 (got {p_total_bar})")
    p_bar_map = {nm: float(y_i * p_total_bar) for nm, y_i in zip(species_names, y)}

    out_dir = gcmc_output_dir(args.output_dir)
    # Use a distinct default filename from the single-component script
    gcmc_json_path = args.output if args.output is not None else out_dir / "multi_gcmc.json"
    starting_tag = int(args.starting_tag)
    species_tags = [starting_tag + i for i in range(len(species_names))]

    LOGGER.info("CIF            : %s", cif_path)
    LOGGER.info("Calculator     : %s", args.calculator)
    LOGGER.info("Model name     : %s", args.model_name)
    LOGGER.info("Task name      : %s", args.task_name)
    LOGGER.info("Device         : %s", args.device)
    LOGGER.info("Steps (MC)     : %d", args.steps)
    LOGGER.info("T [K]          : %.3f", T)
    LOGGER.info("Scheme         : %s", args.scheme)
    LOGGER.info("Species (canon): %s", species_names)
    LOGGER.info("y (canon)      : %s", y)
    LOGGER.info("p_total [bar]  : %.6f", p_total_bar)
    LOGGER.info("p_partial [bar]: %s", p_bar_map)
    LOGGER.info("Output dir     : %s", out_dir)
    LOGGER.info("starting_tag   : %d", starting_tag)
    LOGGER.info("species_tags   : %s", species_tags)

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

    # Build + relax probes (vacuum), same logic as COFclean
    probes: list[Atoms] = []
    ref_energies: list[float] = []
    radii: list[float] = []

    for nm, tag in zip(species_names, species_tags):
        gas = GAS_DB[nm]
        mol_name = gas.get("mol_name", nm)
        build_mode = str(gas.get("build", "")).lower()
        if build_mode == "atom":
            probe = Atoms(mol_name)
        else:
            try:
                probe = build.molecule(mol_name)
            except Exception:
                probe = Atoms(mol_name)
        normalize_charge_spin(probe)
        for a in probe:
            a.tag = int(tag)
        probe.calc = calc_mol
        opt = LBFGS(probe, trajectory=None, logfile=None)
        opt.run(fmax=float(args.probe_fmax), steps=int(args.probe_steps))
        E_probe = float(probe.get_potential_energy())
        r_probe = float(get_radius_probe(probe))
        probe.calc = None
        LOGGER.info(
            "Probe %s: E_ref=%.6f eV | radius=%.3f Å | tag=%d",
            nm,
            E_probe,
            r_probe,
            tag,
        )
        probes.append(probe)
        ref_energies.append(E_probe)
        radii.append(r_probe)

    rcavity = 0.8 * min(radii)

    host, host_natoms, restart_label = load_host_atoms(
        cif_path=cif_path,
        restart_traj=args.restart_traj,
        restart_frame=args.restart_frame,
        read_fn=read,
        load_restart_atoms_fn=load_restart_atoms,
    )
    normalize_charge_spin(host)
    host.calc = calc_host
    tags = ensure_tags(host)
    try:
        host_max = int(np.max(np.asarray(tags[:host_natoms], dtype=int))) if host_natoms > 0 else int(np.max(tags))
        if starting_tag <= host_max:
            LOGGER.warning(
                "starting_tag=%d <= host_max_tag=%d. Consider using --starting-tag %d to avoid overlap.",
                starting_tag,
                host_max,
                host_max + 1,
            )
    except Exception:
        pass

    print_restart_sanity_multicomponent(
        host,
        host_natoms,
        species_list=probes,
        species_names=species_names,
        species_tags=species_tags,
        label=restart_label,
    )
    LOGGER.info(
        "Host atoms=%d | host_natoms(from CIF)=%d | pbc=%s",
        len(host),
        host_natoms,
        tuple(bool(x) for x in host.pbc),
    )

    # PR mixture -> per-component B (same as COFclean)
    Tc = np.array([float(GAS_DB[nm]["Tc"]) for nm in species_names], dtype=float)
    Pc = np.array([float(GAS_DB[nm]["Pc"]) for nm in species_names], dtype=float)
    omega = np.array([float(GAS_DB[nm]["omega"]) for nm in species_names], dtype=float)
    M = np.array(
        [float(GAS_DB[nm].get("M", GAS_DB[nm].get("molar_mass", 0.0))) for nm in species_names],
        dtype=float,
    )
    kij = None
    if args.kij:
        kij = np.zeros((len(species_names), len(species_names)), dtype=float)
        for entry in args.kij:
            a, b, val = _parse_kij_entry(entry)
            a = _resolve_species_name(a, GAS_DB)
            b = _resolve_species_name(b, GAS_DB)
            ia = species_names.index(a)
            ib = species_names.index(b)
            kij[ia, ib] = float(val)
            kij[ib, ia] = float(val)

    B_ads, beta_mu, phi, V_cell_m3, Z = B_peng_robinson_mixture_for_framework(
        atoms=host,
        T=T,
        p_total_bar=p_total_bar,
        y=y,
        Tc=Tc,
        Pc=Pc,
        omega=omega,
        molar_mass=M,
        kij=kij,
        phase="vapor",
        p_ref_bar=1.0,
    )
    LOGGER.info(
        "Framework volume: %.3f Å^3 (%.3e m^3) | Z=%.6f",
        host.get_volume(),
        V_cell_m3,
        Z,
    )
    for nm, Bv, phiv, bmu in zip(species_names, B_ads, phi, beta_mu):
        LOGGER.info(
            "PR mixture: %6s phi=%.6f  beta_mu=%.6f  B=%.6f",
            nm,
            phiv,
            bmu,
            Bv,
        )

    exclusion_list = np.arange(host_natoms, dtype=int)
    grid_resolution = int(args.grid_resolution)
    translate_max = float(args.translate_max)
    bvt_kwargs = dict(
        temperature_K=T,
        b_parameter=[float(x) for x in B_ads],
        species=probes,
        reference_energy=[float(x) for x in ref_energies],
        rcavity=float(rcavity),
        grid_resolution=grid_resolution,
        cavity_bias=True,
        exclusion_list=exclusion_list,
        starting_tag=starting_tag,
    )
    EnsembleClass = BVT_GCMCOnly if args.scheme == "gcmc" else BVT
    ensemble = EnsembleClass(**bvt_kwargs)
    moveset = build_moveset_bvt(ensemble, scheme=args.scheme)
    moveset.adjust_parameter("Translate", "max_delta", translate_max)

    restarting = args.restart_traj is not None
    traj_path, log_path, dt_mc, steps_per_sec = run_mc(
        MonteCarlo_cls=MonteCarlo,
        atoms=host,
        moveset=moveset,
        dft_calc=calc_host,
        out_dir=out_dir,
        io_stub="multi_mc",
        steps=int(args.steps),
        scheme=args.scheme,
        restarting=restarting,
        loginterval=20,
        perf_counter=time.perf_counter,
        info_prefix="[INFO] ",
    )
    LOGGER.info("MC completed in %.3f s | %.2f steps/s", dt_mc, steps_per_sec)

    write_timing_kv(
        out_dir=out_dir,
        kv={
            "scheme": args.scheme,
            "steps": int(args.steps),
            "temperature_K": float(T),
            "p_total_bar": f"{p_total_bar:.8f}",
            "species_order": ",".join(species_names),
            "p_partial_bar": ",".join(f"{nm}:{p_bar_map[nm]:.8f}" for nm in species_names),
            "restart_traj": str(args.restart_traj) if args.restart_traj is not None else "",
            "restart_frame": int(args.restart_frame),
            "host_natoms": int(host_natoms),
            "starting_tag": int(starting_tag),
            "species_tags": ",".join(str(t) for t in species_tags),
            "wall_time_s": f"{dt_mc:.6f}",
            "steps_per_s": f"{steps_per_sec:.6f}",
        },
    )

    LOGGER.info("Analyzing trajectory and writing nmols/energy plots...")
    analyze_and_plot_multicomponent(
        traj_path=traj_path,
        out_dir=out_dir,
        host_natoms=host_natoms,
        species_list=probes,
        species_names=species_names,
        species_tags=species_tags,
        combined_plot=False,
    )

    # Qst_i (partial isosteric heats) via fluctuation formula from time series
    qst_mean_by_adsorbate = None
    qst_std_by_adsorbate = None
    qst_n_blocks = None
    qst_block_size = None
    try:
        energy_path = out_dir / "energy.npy"
        if energy_path.exists():
            energy_eV = np.load(energy_path)
            nmols_by_species: dict[str, np.ndarray] = {}
            all_present = True
            for nm in species_names:
                nm_path = out_dir / f"nmols_{nm}.npy"
                if not nm_path.exists():
                    all_present = False
                    break
                nmols_by_species[nm] = np.load(nm_path)

            if all_present:
                mol_energy_eV_by_species = {
                    nm: float(ref) for nm, ref in zip(species_names, ref_energies)
                }
                (
                    qst_mean_by_adsorbate,
                    qst_std_by_adsorbate,
                    qst_n_blocks,
                    qst_block_size,
                ) = qst_multicomponent_fluctuation_from_series(
                    energy_eV=energy_eV,
                    nmols_by_species=nmols_by_species,
                    species_names=species_names,
                    temperature_K=T,
                    mol_energy_eV_by_species=mol_energy_eV_by_species,
                )
    except Exception as e:
        LOGGER.warning("Failed to compute multicomponent Qst from series: %s", e)

    q_by_adsorbate, q_total = compute_eq_loading_from_traj_multicomponent(
        traj_path=traj_path,
        species_list=probes,
        species_names=species_names,
        species_tags=species_tags,
        host=host,
        host_natoms=host_natoms,
        frac_tail=0.05,
    )
    payload = gcmc_standalone_payload_multicomponent(
        species_names=species_names,
        temperature_K=T,
        pressure_partial_bar={nm: float(p_bar_map[nm]) for nm in species_names},
        scheme=args.scheme,
        q_by_adsorbate=q_by_adsorbate,
        q_total=q_total,
    )
    payload["wall_time_s"] = dt_mc
    payload["steps_per_s"] = steps_per_sec
    payload["qst_kJ_mol_by_adsorbate"] = qst_mean_by_adsorbate
    payload["qst_std_kJ_mol_by_adsorbate"] = qst_std_by_adsorbate
    payload["qst_n_blocks"] = qst_n_blocks
    payload["qst_block_size"] = qst_block_size
    write_gcmc_results_json(gcmc_json_path, payload)
    LOGGER.info("Wrote %s", gcmc_json_path)

    # Remove traj/log and .npy intermediates; keep JSON and PNGs
    cleanup_paths = [traj_path, log_path, out_dir / "energy.npy"]
    for name in species_names:
        cleanup_paths.append(out_dir / f"nmols_{name}.npy")
    for p in cleanup_paths:
        try:
            if p is not None and p.exists():
                p.unlink()
        except Exception as e:
            LOGGER.warning("Could not remove %s: %s", p, e)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
