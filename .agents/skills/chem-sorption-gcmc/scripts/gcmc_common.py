"""Shared helpers for (multi-)component GCMC / ASE-MC pipelines.

This module was previously an accidental concatenation of two divergent
implementations (duplicate function names, conflicting staging logic, and
missing imports). It is now de-duplicated into a single, coherent set of
utilities.

Refactor rule for the surrounding project: preserve external behavior for the
helpers used by the COF pipeline scripts (directory layout, file names, JSON
schema, and PR-EOS conventions).
"""

from pathlib import Path
from typing import Any, Callable, Optional, Tuple, TypeVar
import json
import logging
import sys

import numpy as np
import matplotlib.pyplot as plt
from ase import Atoms
from ase.io import read
from ase.io.trajectory import Trajectory
from ase_mc import Moveset

# Energy/temperature conversion constants for Qst calculations
EV_TO_KJMOL = 96.4853321233  # 1 eV per molecule = 96.485... kJ/mol
KB_EVK = 8.617333262145e-5   # Boltzmann constant in eV/K

LOGGER = logging.getLogger(__name__)

TAtoms = TypeVar("TAtoms")


# -----------------------------------------------------------------------------
# Gas parameters (Peng–Robinson) shared across scripts
# -----------------------------------------------------------------------------

def _default_pr_gas_params() -> dict[str, dict[str, float | str]]:
    """Built-in PR parameters for core gases (CO2, N2).

    These values are ported from the original COFclean benchmark scripts.
    Additional species should be supplied via the external JSON resource.
    """
    return {
        "CO2": dict(
            mol_name="CO2",
            Tc=304.1282,  # K
            Pc=7.3773e6,  # Pa
            omega=0.225,  # -
            M=44.01e-3,  # kg/mol
        ),
        "N2": dict(
            mol_name="N2",
            Tc=126.192,  # K
            Pc=3.3958e6,  # Pa
            omega=0.0372,  # -
            M=28.0134e-3,  # kg/mol
        ),
    }


def _load_pr_gas_db_from_resources() -> dict[str, dict[str, float | str]]:
    """Load extended PR gas parameters from the skill's resources, if present.

    Expected schema: mapping from species name → parameter dict with keys
    compatible with the built-in defaults (e.g. mol_name, Tc, Pc, omega, M).
    """
    base = _default_pr_gas_params()

    try:
        # resources/ is sibling to scripts/ inside the chem-sorption skill.
        script_dir = Path(__file__).resolve().parent
        resources_dir = script_dir.parent / "resources"
        json_path = resources_dir / "pr_eos_gases.json"
        if not json_path.exists():
            return base

        raw = json.loads(json_path.read_text())
        if not isinstance(raw, dict):
            LOGGER.warning("PR gas DB JSON is not a dict: %s", json_path)
            return base

        for name, params in raw.items():
            if not isinstance(params, dict):
                LOGGER.warning("Skipping non-dict gas entry for %s in %s", name, json_path)
                continue
            merged = dict(base.get(name, {}))
            merged.update(params)
            base[name] = merged
    except Exception as exc:  # pragma: no cover - defensive
        LOGGER.warning("Failed to load PR gas DB from resources: %s", exc)

    return base


# Public gas database used by GCMC scripts.
# Historically named GAS_PR_PARAMS_CO2_N2, but now may contain additional
# species loaded from the external JSON file.
GAS_PR_PARAMS_CO2_N2: dict[str, dict[str, float | str]] = _load_pr_gas_db_from_resources()


# -----------------------------------------------------------------------------
# Output directory (no staging)
# -----------------------------------------------------------------------------


def gcmc_output_dir(output_dir: Path) -> Path:
    """Ensure output directory exists and return it."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    return out


# -----------------------------------------------------------------------------
# Host loading / restart
# -----------------------------------------------------------------------------


def load_host_atoms(
    *,
    cif_path: Path,
    restart_traj: Optional[Path],
    restart_frame: int,
    read_fn: Callable[[str], TAtoms],
    load_restart_atoms_fn: Callable[[Path, Path, int], tuple[TAtoms, int]],
) -> tuple[TAtoms, int, str]:
    """Load host atoms from CIF or restart trajectory.

    Returns (host, host_natoms, restart_label).
    """
    if restart_traj is None:
        host = read_fn(str(cif_path))
        host_natoms = len(host)  # type: ignore[arg-type]
        restart_label = "Fresh start (no restart-traj)"
    else:
        host, host_natoms = load_restart_atoms_fn(cif_path, restart_traj, restart_frame)
        restart_label = f"Restart from {restart_traj} (frame {restart_frame})"
    return host, host_natoms, restart_label


def load_restart_atoms(cif_path: Path, restart_traj: Path, restart_frame: int) -> tuple[Atoms, int]:
    """Return (atoms_start, host_natoms) where host_natoms is taken from CIF."""
    host_ref = read(str(cif_path))
    host_natoms = len(host_ref)

    traj = Trajectory(str(restart_traj))
    if len(traj) == 0:
        raise RuntimeError(f"Restart trajectory is empty: {restart_traj}")

    atoms = traj[restart_frame].copy()
    if len(atoms) < host_natoms:
        raise RuntimeError(
            f"Restart frame has fewer atoms ({len(atoms)}) than CIF host ({host_natoms})."
        )

    # Light sanity check: host composition/order vs CIF
    try:
        if not np.array_equal(atoms.get_atomic_numbers()[:host_natoms], host_ref.get_atomic_numbers()):
            LOGGER.warning("Restart frame host atoms do not match CIF ordering/composition.")
            LOGGER.warning("If ordering differs, host/guest masking may be wrong.")
    except Exception:
        pass

    # Ensure PBC is on (some writers can drop this)
    try:
        if not np.any(atoms.get_pbc()):
            atoms.set_pbc(True)
    except Exception:
        pass

    return atoms, host_natoms


# -----------------------------------------------------------------------------
# MC run helpers
# -----------------------------------------------------------------------------


def mc_traj_log_paths(*, out_dir: Path, restarting: bool, stub: str = "mc") -> tuple[Path, Path]:
    """Return (traj_path, log_path) with the canonical fresh/continue naming."""
    traj_path = out_dir / (f"{stub}_continue.traj" if restarting else f"{stub}.traj")
    log_path = out_dir / (f"{stub}_continue.log" if restarting else f"{stub}.log")
    return traj_path, log_path


def maybe_record_starting_config(dyn: Any) -> None:
    """Best-effort: record the initial configuration into the trajectory."""
    try:
        if getattr(dyn, "trajectory", None) is not None:
            dyn.save_to_traj(dyn.last_accepted_config, dyn.trajectory)
    except Exception:
        pass


def run_mc_with_timing(*, dyn: Any, steps: int, perf_counter: Callable[[], float]) -> tuple[float, float]:
    """Run MC and return (wall_time_seconds, steps_per_second)."""
    t0 = perf_counter()
    dyn.run(int(steps))
    dt = perf_counter() - t0
    steps_per_sec = float(steps) / dt if dt > 0 else float("nan")
    return float(dt), float(steps_per_sec)


def run_mc(
    *,
    MonteCarlo_cls: Any,
    atoms: Atoms,
    moveset: Any,
    dft_calc: Any,
    out_dir: Path,
    io_stub: str = "mc",
    steps: int,
    scheme: str,
    restarting: bool,
    loginterval: int,
    perf_counter: Callable[[], float],
    info_prefix: str = "",
) -> tuple[Path, Path, float, float]:
    """Construct and run an ASE-MC MonteCarlo object, returning timing info.

    Returns (traj_path, log_path, wall_time_s, steps_per_s).
    """
    traj_path, log_path = mc_traj_log_paths(out_dir=out_dir, restarting=restarting, stub=io_stub)

    dyn = MonteCarlo_cls(
        atoms=atoms,
        moveset=moveset,
        dft_calc=dft_calc,
        trajectory=str(traj_path),
        logfile=str(log_path),
        loginterval=int(loginterval),
        gcmc_energy_only=(scheme == "gcmc"),
    )

    # Optional: ensure the starting config is recorded
    maybe_record_starting_config(dyn)

    LOGGER.info(
        "%sStarting MC run: scheme=%s, steps=%s, traj=%s, log=%s",
        info_prefix,
        scheme,
        steps,
        traj_path.name,
        log_path.name,
    )

    dt, steps_per_sec = run_mc_with_timing(dyn=dyn, steps=steps, perf_counter=perf_counter)
    return traj_path, log_path, dt, steps_per_sec


def write_lines(path: Path, lines: list[str]) -> None:
    """Write pre-formatted lines to a file (each line should include '\n')."""
    with open(path, "w") as f:
        for line in lines:
            f.write(line)


def write_timing_kv(
    *,
    out_dir: Path,
    kv: dict[str, object],
    filename: str = "timing.txt",
) -> None:
    """Write a simple key/value timing file.

    NOTE: Callers control insertion order by the order they build `kv`.
    """
    lines = [f"{k} {v}\n" for k, v in kv.items()]
    write_lines(out_dir / filename, lines)


# -----------------------------------------------------------------------------
# Physical constants (SI)
# -----------------------------------------------------------------------------

R = 8.314462618  # J / (mol K)
kB = 1.380649e-23  # J / K
h = 6.62607015e-34  # J s
NA = 6.02214076e23  # 1 / mol


# -----------------------------------------------------------------------------
# Peng–Robinson EOS helpers (pure component)
# -----------------------------------------------------------------------------


def _peng_robinson_Z_phi(
    T: float,
    p: float,
    Tc: float,
    Pc: float,
    omega: float,
    phase: str = "vapor",
) -> tuple[float, float]:
    Tr = T / Tc
    kappa = 0.37464 + 1.54226 * omega - 0.26992 * omega**2
    alpha = (1.0 + kappa * (1.0 - np.sqrt(Tr))) ** 2

    a = 0.45724 * R**2 * Tc**2 / Pc
    b = 0.07780 * R * Tc / Pc

    A = a * alpha * p / (R**2 * T**2)
    B = b * p / (R * T)

    coeffs = [
        1.0,
        -(1.0 - B),
        A - 3.0 * B**2 - 2.0 * B,
        -(A * B - B**2 - B**3),
    ]
    roots = np.roots(coeffs)
    roots = np.real(roots[np.isreal(roots)])
    if roots.size == 0:
        raise RuntimeError("No real PR root for Z")

    Z = np.max(roots) if phase == "vapor" else np.min(roots)

    sqrt2 = np.sqrt(2.0)
    ln_phi = (
        Z
        - 1.0
        - np.log(Z - B)
        - (A / (2.0 * sqrt2 * B))
        * np.log((Z + (1.0 + sqrt2) * B) / (Z + (1.0 - sqrt2) * B))
    )
    phi = float(np.exp(ln_phi))
    return float(Z), phi


def B_peng_robinson(
    T: float,
    p: float,
    Tc: float,
    Pc: float,
    omega: float,
    *,
    molar_mass: float | None = None,  # kg/mol
    V_cell: float = 1.0,  # m^3
    phase: str = "vapor",
    p_ref: float = 1.0e5,  # Pa
) -> tuple[float, float, float]:
    """Return (B, beta_mu, phi) for a pure component.

    Convention (ASE-MC BVT):
      B = ln(f V / (kB T)) where f = phi * p.
    """
    _Z, phi = _peng_robinson_Z_phi(T, p, Tc, Pc, omega, phase=phase)
    f = float(phi * p)  # fugacity [Pa]

    # Adams parameter
    B = float(np.log(f * V_cell / (kB * T)))

    # Useful provenance quantity
    if molar_mass is None:
        beta_mu = float(np.log(f / p_ref))
    else:
        m = molar_mass / NA  # kg per molecule
        Lambda = h / np.sqrt(2.0 * np.pi * m * kB * T)  # m
        beta_mu = float(np.log((Lambda**3) * f / (kB * T)))

    return B, beta_mu, float(phi)


def B_peng_robinson_for_framework(
    atoms: Atoms,
    T: float,
    p_bar: float,
    Tc: float,
    Pc: float,
    omega: float,
    molar_mass: float,  # kg/mol
    *,
    phase: str = "vapor",
    p_ref_bar: float = 1.0,
) -> tuple[float, float, float, float]:
    p = p_bar * 1.0e5
    p_ref = p_ref_bar * 1.0e5

    V_ang3 = atoms.get_volume()
    V_cell_m3 = V_ang3 * 1.0e-30

    B, beta_mu, phi = B_peng_robinson(
        T,
        p,
        Tc,
        Pc,
        omega,
        molar_mass=molar_mass,
        V_cell=V_cell_m3,
        phase=phase,
        p_ref=p_ref,
    )
    return B, beta_mu, phi, V_cell_m3


# -----------------------------------------------------------------------------
# Peng–Robinson EOS helpers (mixture)
# -----------------------------------------------------------------------------


def peng_robinson_mixture_phi(
    T: float,
    P: float,  # Pa (total pressure)
    y: np.ndarray,  # mole fractions, shape (N,)
    Tc: np.ndarray,  # K, shape (N,)
    Pc: np.ndarray,  # Pa, shape (N,)
    omega: np.ndarray,  # shape (N,)
    kij: np.ndarray | None = None,  # shape (N,N), kij[i,i]=0
    phase: str = "vapor",
) -> tuple[float, np.ndarray]:
    """Return (Z, phi) for a PR mixture."""
    y = np.asarray(y, dtype=float)
    if y.ndim != 1:
        raise ValueError("y must be 1D")
    if np.any(y < 0) or y.sum() <= 0:
        raise ValueError("Invalid composition y")
    y = y / y.sum()

    Tc = np.asarray(Tc, dtype=float)
    Pc = np.asarray(Pc, dtype=float)
    omega = np.asarray(omega, dtype=float)

    N = y.size
    if not (Tc.size == Pc.size == omega.size == N):
        raise ValueError("Tc, Pc, omega must all have same length as y")

    if kij is None:
        kij = np.zeros((N, N), dtype=float)
    else:
        kij = np.asarray(kij, dtype=float)
        if kij.shape != (N, N):
            raise ValueError("kij must be NxN")
    kij = 0.5 * (kij + kij.T)
    np.fill_diagonal(kij, 0.0)

    # pure-component a_i(T), b_i
    Tr = T / Tc
    kappa = 0.37464 + 1.54226 * omega - 0.26992 * omega**2
    alpha = (1.0 + kappa * (1.0 - np.sqrt(Tr))) ** 2

    a0 = 0.45724 * R**2 * Tc**2 / Pc
    bi = 0.07780 * R * Tc / Pc
    ai = a0 * alpha

    # mixing rules
    aij = np.sqrt(ai[:, None] * ai[None, :]) * (1.0 - kij)
    amix = float(np.sum(y[:, None] * y[None, :] * aij))
    bmix = float(np.sum(y * bi))

    A = amix * P / (R**2 * T**2)
    B = bmix * P / (R * T)

    # solve cubic for Z
    coeffs = [
        1.0,
        -(1.0 - B),
        A - 3.0 * B**2 - 2.0 * B,
        -(A * B - B**2 - B**3),
    ]
    roots = np.roots(coeffs)
    roots = np.real(roots[np.isreal(roots)])
    if roots.size == 0:
        raise RuntimeError("No real PR root for Z (mixture)")

    Z = float(np.max(roots) if phase == "vapor" else np.min(roots))

    sqrt2 = np.sqrt(2.0)
    log_arg = (Z + (1.0 + sqrt2) * B) / (Z + (1.0 - sqrt2) * B)
    ln_term = float(np.log(log_arg))

    # S_i = sum_j y_j a_ij
    Si = aij @ y

    ln_phi = (
        (bi / bmix) * (Z - 1.0)
        - np.log(Z - B)
        - (A / (2.0 * sqrt2 * B)) * ((2.0 * Si / amix) - (bi / bmix)) * ln_term
    )

    phi = np.exp(ln_phi)
    return Z, phi


def B_peng_robinson_mixture_for_framework(
    atoms: Atoms,
    T: float,
    p_total_bar: float,
    y: list[float] | np.ndarray,
    Tc: list[float] | np.ndarray,
    Pc: list[float] | np.ndarray,  # Pa
    omega: list[float] | np.ndarray,
    molar_mass: list[float] | np.ndarray,  # kg/mol
    kij: np.ndarray | None = None,
    *,
    phase: str = "vapor",
    p_ref_bar: float = 1.0,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, float, float]:
    """Mixture PR EOS -> per-component Adams B for a periodic framework.

    Convention (ASE-MC BVT):
      B_i = ln(f_i V / (kB T)), where f_i = phi_i y_i P.
    """
    P = float(p_total_bar) * 1.0e5
    p_ref = float(p_ref_bar) * 1.0e5

    V_ang3 = atoms.get_volume()
    V_cell_m3 = V_ang3 * 1.0e-30

    y_arr = np.asarray(y, dtype=float)
    Z, phi = peng_robinson_mixture_phi(
        T=T,
        P=P,
        y=y_arr,
        Tc=np.asarray(Tc, float),
        Pc=np.asarray(Pc, float),
        omega=np.asarray(omega, float),
        kij=kij,
        phase=phase,
    )

    # component fugacities
    f = y_arr / y_arr.sum() * phi * P

    # Adams parameters per component
    B_ads = np.log(f * V_cell_m3 / (kB * T))

    # provenance beta_mu per component
    molar_mass_arr = np.asarray(molar_mass, dtype=float)
    beta_mu = np.empty_like(B_ads)
    for i in range(len(B_ads)):
        if molar_mass_arr[i] <= 0:
            beta_mu[i] = np.log(f[i] / p_ref)
        else:
            m = molar_mass_arr[i] / NA
            Lambda = h / np.sqrt(2.0 * np.pi * m * kB * T)
            beta_mu[i] = np.log((Lambda**3) * f[i] / (kB * T))

    return B_ads, beta_mu, phi, V_cell_m3, float(Z)


# -----------------------------------------------------------------------------
# Restart-safe helpers
# -----------------------------------------------------------------------------


def get_radius_probe(probe: Atoms) -> float:
    """Geometric radius of a probe molecule in Å (max distance to COM)."""
    coords_com = probe.get_positions() - probe.get_center_of_mass()
    r_arr = np.linalg.norm(coords_com, axis=1)
    return float(r_arr.max()) if r_arr.size else 0.0


def build_moveset_bvt(ensemble: Any, scheme: str) -> Moveset:
    """Build a Moveset; optionally drop HMC for GCMC scheme."""
    all_moves = ensemble.get_moves()
    if scheme == "gcmc":
        moves = [m for m in all_moves if type(m).__name__ != "HMC"]
    elif scheme == "hmc":
        moves = all_moves
    else:
        raise ValueError(f"Unknown scheme: {scheme}")
    return Moveset(moves)


def count_probe_molecules_by_blocks(atoms: Atoms, host_natoms: int, probe: Atoms) -> int:
    """Count probe molecules assuming guests are appended as contiguous blocks."""
    len_probe = len(probe)
    probe_numbers = probe.get_atomic_numbers()

    total = len(atoms)
    extra = total - host_natoms
    if extra <= 0:
        return 0

    if len_probe > 0 and extra % len_probe == 0:
        return extra // len_probe

    # Fallback: scan blocks and count matching sequences
    nm = 0
    for ind in range(host_natoms, total - len_probe + 1, max(len_probe, 1)):
        slice_numbers = atoms[ind : ind + len_probe].get_atomic_numbers()
        if np.all(slice_numbers == probe_numbers):
            nm += 1
    return nm


def count_molecules_by_tag(atoms: Atoms, host_natoms: int, tag: int, len_probe: int) -> int:
    """Count molecules by tag, dividing tagged atom count by len(probe)."""
    if len(atoms) <= host_natoms:
        return 0
    tags = np.asarray(atoms.get_tags(), dtype=int)
    if tags.shape[0] != len(atoms):
        return 0
    n_atoms = int(np.sum(tags[host_natoms:] == tag))
    return int(n_atoms // max(int(len_probe), 1))


def _safe_energy(atoms: Atoms) -> float:
    try:
        return float(atoms.get_total_energy())
    except Exception as exc:
        LOGGER.warning("Failed to read total energy from atoms: %s", exc)
    for key in ("energy", "E", "total_energy", "potential_energy"):
        if key in atoms.info:
            try:
                return float(atoms.info[key])
            except Exception:
                continue
    return float("nan")


def print_restart_sanity_single(atoms: Atoms, host_natoms: int, probe: Atoms, label: str = "") -> None:
    total = len(atoms)
    extra = total - host_natoms
    nmols = count_probe_molecules_by_blocks(atoms, host_natoms, probe)

    try:
        tags = atoms.get_tags()
        tmin = int(np.min(tags))
        tmax = int(np.max(tags))
        guest_unique = int(len(np.unique(tags[host_natoms:]))) if extra > 0 else 0
    except Exception:
        tmin, tmax, guest_unique = 0, 0, 0

    LOGGER.info("================= RESTART SANITY =================")
    if label:
        LOGGER.info("%s", label)
    LOGGER.info("Total atoms              : %d", total)
    LOGGER.info("Host atoms (from CIF)    : %d", host_natoms)
    LOGGER.info("Guest atoms              : %d", max(extra, 0))
    probe_formula = probe.get_chemical_formula()
    LOGGER.info("Estimated # %s molecules: %d", probe_formula, nmols)
    LOGGER.info("Move/delete masking:")
    LOGGER.info(
        "  exclusion_list = [0..%d] (host excluded, guests eligible)",
        host_natoms - 1,
    )
    LOGGER.info("Tags:")
    LOGGER.info("  tag min/max            : %d / %d", tmin, tmax)
    if extra > 0:
        LOGGER.info("  unique guest tags       : %d", guest_unique)
    LOGGER.info("==================================================")


def print_restart_sanity_multicomponent(
    atoms: Atoms,
    host_natoms: int,
    species_list: list[Atoms],
    species_names: list[str],
    species_tags: list[int],
    label: str = "",
) -> None:
    total = len(atoms)
    extra = total - host_natoms

    try:
        tags = np.asarray(atoms.get_tags(), dtype=int)
        tmin = int(np.min(tags)) if tags.size else 0
        tmax = int(np.max(tags)) if tags.size else 0
    except Exception:
        tmin, tmax = 0, 0

    LOGGER.info("================= RESTART SANITY =================")
    if label:
        LOGGER.info("%s", label)
    LOGGER.info("Total atoms           : %d", total)
    LOGGER.info("Host atoms (from CIF) : %d", host_natoms)
    LOGGER.info("Guest atoms           : %d", max(extra, 0))
    LOGGER.info("Move/delete masking:")
    LOGGER.info(
        "  exclusion_list = [0..%d] (host excluded, guests eligible)",
        host_natoms - 1,
    )
    LOGGER.info("Tags:")
    LOGGER.info("  tag min/max         : %d / %d", tmin, tmax)
    LOGGER.info("Estimated molecule counts (by tag):")
    for nm, sp, tg in zip(species_names, species_list, species_tags):
        n = count_molecules_by_tag(atoms, host_natoms, tg, len(sp))
        LOGGER.info("  %3s (tag %3d, n_atoms=%2d): %d", nm, tg, len(sp), n)
    LOGGER.info("==================================================")


def analyze_and_plot_single(traj_path: Path, probe: Atoms, out_dir: Path, host_natoms: int) -> None:
    traj = Trajectory(str(traj_path))
    nframes = len(traj)
    if nframes == 0:
        LOGGER.warning("Trajectory is empty, skipping analysis.")
        return

    nmols = np.zeros(nframes, dtype=int)
    t_energy = np.zeros(nframes)

    for frame_idx, atoms in enumerate(traj):
        nmols[frame_idx] = count_probe_molecules_by_blocks(atoms, host_natoms, probe)
        t_energy[frame_idx] = _safe_energy(atoms)

    plt.figure()
    plt.plot(nmols)
    plt.xlabel("MC step (frame index)")
    probe_formula = probe.get_chemical_formula()
    plt.ylabel(f"No. {probe_formula}")
    plt.tight_layout()
    plt.savefig(out_dir / "nmols.png", dpi=150)
    plt.close()

    plt.figure()
    plt.plot(t_energy)
    plt.xlabel("MC step (frame index)")
    plt.ylabel("Total Energy [eV]")
    plt.tight_layout()
    plt.savefig(out_dir / "energy.png", dpi=150)
    plt.close()

    np.save(out_dir / "nmols.npy", nmols)
    np.save(out_dir / "energy.npy", t_energy)


def analyze_and_plot_multicomponent(
    traj_path: Path,
    out_dir: Path,
    host_natoms: int,
    species_list: list[Atoms],
    species_names: list[str],
    species_tags: list[int],
    *,
    combined_plot: bool = False,
) -> None:
    traj = Trajectory(str(traj_path))
    nframes = len(traj)
    if nframes == 0:
        LOGGER.warning("Trajectory is empty, skipping analysis.")
        return

    t_energy = np.zeros(nframes)
    nmols = {name: np.zeros(nframes, dtype=int) for name in species_names}
    lens = {name: len(sp) for name, sp in zip(species_names, species_list)}

    for frame_idx, atoms in enumerate(traj):
        t_energy[frame_idx] = _safe_energy(atoms)
        for name, tag in zip(species_names, species_tags):
            nmols[name][frame_idx] = count_molecules_by_tag(atoms, host_natoms, tag, lens[name])

    # Per-species plots
    for name in species_names:
        plt.figure()
        plt.plot(nmols[name])
        plt.xlabel("MC step (frame index)")
        plt.ylabel(f"No. {name}")
        plt.tight_layout()
        plt.savefig(out_dir / f"nmols_{name}.png", dpi=150)
        plt.close()
        np.save(out_dir / f"nmols_{name}.npy", nmols[name])

    if combined_plot:
        plt.figure()
        for name in species_names:
            plt.plot(nmols[name], label=name)
        plt.xlabel("MC step (frame index)")
        plt.ylabel("No. molecules")
        plt.legend()
        plt.tight_layout()
        plt.savefig(out_dir / "nmols.png", dpi=150)
        plt.close()

    # Energy plot
    plt.figure()
    plt.plot(t_energy)
    plt.xlabel("MC step (frame index)")
    plt.ylabel("Total Energy [eV]")
    plt.tight_layout()
    plt.savefig(out_dir / "energy.png", dpi=150)
    plt.close()
    np.save(out_dir / "energy.npy", t_energy)


# -----------------------------------------------------------------------------
# properties.json helpers (isotherm schema)
# -----------------------------------------------------------------------------


def _format_temperature_key(temperature: float) -> str:
    rounded = round(temperature)
    if abs(temperature - rounded) < 1e-6:
        return f"{int(rounded)}K"
    return f"{temperature:g}K"


def _load_properties_json(properties_path: Path, cof_name: str) -> dict:
    properties_path = Path(properties_path)
    properties_path.parent.mkdir(parents=True, exist_ok=True)
    if properties_path.exists():
        try:
            data = json.loads(properties_path.read_text())
        except Exception:
            data = {}
    else:
        data = {}

    data.setdefault("schema_version", "0.1.0")
    data.setdefault("cof", {})
    data["cof"].setdefault("name", cof_name)
    return data


def _write_properties_json(properties_path: Path, data: dict) -> None:
    # Enforce strict JSON (no NaN/Infinity).
    Path(properties_path).write_text(json.dumps(data, indent=2, allow_nan=False) + "\n")


def _finite_or_none(x: float) -> float | None:
    try:
        xf = float(x)
    except Exception:
        return None
    return xf if np.isfinite(xf) else None


def _same_partial_pressure(a: dict | None, b: dict | None) -> bool:
    if a is None and b is None:
        return True
    if not isinstance(a, dict) or not isinstance(b, dict):
        return False
    if set(a.keys()) != set(b.keys()):
        return False
    for k in a.keys():
        av = _finite_or_none(a.get(k))
        bv = _finite_or_none(b.get(k))
        if av != bv:
            return False
    return True


def _upsert_isotherm_point(points: list, new_point: dict) -> list:
    """Insert or update a point in an isotherm points list.

    Matching rule: same p_total and same p_partial (per-adsorbate partials).
    """
    p_new = _finite_or_none(new_point.get("p_total"))
    pp_new = new_point.get("p_partial")
    if p_new is None:
        return list(points) + [new_point]

    out = list(points) if isinstance(points, list) else []
    for i, pt in enumerate(out):
        if not isinstance(pt, dict):
            continue
        p_old = _finite_or_none(pt.get("p_total"))
        if p_old != p_new:
            continue
        if not _same_partial_pressure(pt.get("p_partial"), pp_new):
            continue
        merged = dict(pt)
        merged.update(new_point)
        out[i] = merged
        break
    else:
        out.append(new_point)

    # Keep points sorted by total pressure for readability
    try:
        out.sort(key=lambda d: float(d.get("p_total", float("inf"))))
    except Exception:
        pass
    return out


def _compute_eq_nmols(nmols_path: Path, frac_tail: float = 0.05) -> float:
    nmols = np.load(str(nmols_path))
    if nmols.size == 0:
        return float("nan")
    start = int((1.0 - float(frac_tail)) * nmols.size)
    start = min(max(start, 0), nmols.size - 1)
    return float(np.mean(nmols[start:]))


def _eq_nmols_from_array(nmols: np.ndarray, frac_tail: float = 0.05) -> float:
    """Equilibrium nmols from in-memory array (last frac_tail fraction)."""
    if nmols.size == 0:
        return float("nan")
    start = int((1.0 - float(frac_tail)) * nmols.size)
    start = min(max(start, 0), nmols.size - 1)
    return float(np.mean(nmols[start:]))


def compute_eq_loading_from_traj_single(
    traj_path: Path,
    probe: Atoms,
    host: Atoms,
    host_natoms: int,
    frac_tail: float = 0.05,
) -> float:
    """Compute equilibrium loading (mmol/g) from trajectory without writing npy/png."""
    traj = Trajectory(str(traj_path))
    nframes = len(traj)
    if nframes == 0:
        return float("nan")
    nmols = np.zeros(nframes, dtype=int)
    for i, atoms in enumerate(traj):
        nmols[i] = count_probe_molecules_by_blocks(atoms, host_natoms, probe)
    eq_nmols = _eq_nmols_from_array(nmols, frac_tail=frac_tail)
    host_mass_kg = _host_mass_kg(host, host_natoms)
    return _mol_per_kg_from_nmols(eq_nmols, host_mass_kg) * 1000.0  # mol/kg -> mmol/g


def _host_mass_kg(host: Atoms, host_natoms: int) -> float:
    masses_amu = host.get_masses()
    host_mass_amu = float(np.sum(masses_amu[:host_natoms]))
    # 1 amu = 1.66053906660e-27 kg
    return host_mass_amu * 1.66053906660e-27


def _mol_per_kg_from_nmols(eq_nmols: float, host_mass_kg: float) -> float:
    if not np.isfinite(eq_nmols) or host_mass_kg <= 0.0:
        return float("nan")
    return (float(eq_nmols) / NA) / float(host_mass_kg)


def update_properties_json_gcmc_single(
    properties_path: Path,
    *,
    cof_name: str,
    adsorbate: str,
    temperature_K: float,
    pressure_bar: float,
    scheme: str,
    out_dir: Path,
    nmols_path: Path,
    host: Atoms,
    host_natoms: int,
    frac_tail: float = 0.05,
) -> None:
    data = _load_properties_json(properties_path, cof_name)

    eq_nmols = _compute_eq_nmols(nmols_path, frac_tail=frac_tail)
    host_mass_kg = _host_mass_kg(host, host_natoms)
    mol_per_kg = _mol_per_kg_from_nmols(eq_nmols, host_mass_kg)
    # Numerically, 1 mol/kg == 1 mmol/g
    mmol_per_g = _finite_or_none(mol_per_kg)

    props = data.setdefault("properties", {})
    adsorption = props.setdefault("adsorption", {})
    isotherms = adsorption.setdefault("isotherms", {})

    temp_key = _format_temperature_key(temperature_K)
    iso_key = f"{adsorbate}@{temp_key}:simulation"

    try:
        run_relpath = str(Path(out_dir).resolve().relative_to(properties_path.parent.resolve()))
    except Exception:
        run_relpath = str(out_dir)

    point = {
        "p_total": float(pressure_bar),
        "p_partial": {adsorbate: float(pressure_bar)},
        "q_total": mmol_per_g,
        "q_by_adsorbate": {adsorbate: mmol_per_g},
        "from_run": run_relpath,
    }

    existing = isotherms.get(iso_key)
    if isinstance(existing, dict):
        existing.setdefault("adsorbates", [adsorbate])
        existing.setdefault("temperature_K", float(temperature_K))
        existing.setdefault("source", "simulation")
        existing.setdefault(
            "units",
            {
                "pressure_total": "bar",
                "pressure_partial": "bar",
                "loading_total": "mmol/g",
                "loading_by_adsorbate": "mmol/g",
            },
        )
        existing["points"] = _upsert_isotherm_point(existing.get("points", []), point)
        # legacy top-level field as "most recent run"
        existing["from_run"] = run_relpath
        existing.setdefault("ref", None)
        if existing.get("notes") is None:
            existing["notes"] = f"scheme={scheme}"
    else:
        isotherms[iso_key] = {
            "adsorbates": [adsorbate],
            "temperature_K": float(temperature_K),
            "source": "simulation",
            "units": {
                "pressure_total": "bar",
                "pressure_partial": "bar",
                "loading_total": "mmol/g",
                "loading_by_adsorbate": "mmol/g",
            },
            "points": [point],
            "from_run": run_relpath,
            "ref": None,
            "notes": f"scheme={scheme}",
        }

    _write_properties_json(properties_path, data)


def update_properties_json_gcmc_multicomponent(
    properties_path: Path,
    *,
    cof_name: str,
    species_names: list[str],
    temperature_K: float,
    pressure_partial_bar: dict[str, float],
    scheme: str,
    out_dir: Path,
    nmols_paths: dict[str, Path],
    host: Atoms,
    host_natoms: int,
    frac_tail: float = 0.05,
) -> None:
    data = _load_properties_json(properties_path, cof_name)

    host_mass_kg = _host_mass_kg(host, host_natoms)

    q_by_adsorbate: dict[str, float | None] = {}
    for name in species_names:
        nmols_path = nmols_paths.get(name)
        if nmols_path is None or not nmols_path.exists():
            q_by_adsorbate[name] = None
            continue
        eq_nmols = _compute_eq_nmols(nmols_path, frac_tail=frac_tail)
        mol_per_kg = _mol_per_kg_from_nmols(eq_nmols, host_mass_kg)
        q_by_adsorbate[name] = _finite_or_none(mol_per_kg)

    finite_vals = [v for v in q_by_adsorbate.values() if v is not None]
    q_total = float(np.sum(finite_vals)) if finite_vals else None
    p_total = float(np.sum(list(pressure_partial_bar.values())))

    props = data.setdefault("properties", {})
    adsorption = props.setdefault("adsorption", {})
    isotherms = adsorption.setdefault("isotherms", {})

    temp_key = _format_temperature_key(temperature_K)
    mix_key = "-".join(sorted(species_names))
    iso_key = f"{mix_key}@{temp_key}:simulation"

    try:
        run_relpath = str(Path(out_dir).resolve().relative_to(properties_path.parent.resolve()))
    except Exception:
        run_relpath = str(out_dir)

    point = {
        "p_total": float(p_total),
        "p_partial": {k: float(v) for k, v in pressure_partial_bar.items()},
        "q_total": q_total,
        "q_by_adsorbate": {k: v for k, v in q_by_adsorbate.items()},
        "from_run": run_relpath,
    }

    existing = isotherms.get(iso_key)
    if isinstance(existing, dict):
        existing.setdefault("adsorbates", list(species_names))
        existing.setdefault("temperature_K", float(temperature_K))
        existing.setdefault("source", "simulation")
        existing.setdefault(
            "units",
            {
                "pressure_total": "bar",
                "pressure_partial": "bar",
                "loading_total": "mmol/g",
                "loading_by_adsorbate": "mmol/g",
            },
        )
        existing["points"] = _upsert_isotherm_point(existing.get("points", []), point)
        existing["from_run"] = run_relpath
        existing.setdefault("ref", None)
        if existing.get("notes") is None:
            existing["notes"] = f"scheme={scheme}"
    else:
        isotherms[iso_key] = {
            "adsorbates": list(species_names),
            "temperature_K": float(temperature_K),
            "source": "simulation",
            "units": {
                "pressure_total": "bar",
                "pressure_partial": "bar",
                "loading_total": "mmol/g",
                "loading_by_adsorbate": "mmol/g",
            },
            "points": [point],
            "from_run": run_relpath,
            "ref": None,
            "notes": f"scheme={scheme}",
        }

    _write_properties_json(properties_path, data)

def _tail_blockify_fixed_nblocks(
    arrays_1d: list[np.ndarray],
    *,
    frac_tail: float,
    n_blocks_target: int,
) -> tuple[list[np.ndarray], int, int]:
    """Align multiple 1D series, take tail, and reshape into equal-sized blocks.

    Returns:
      (blocked_arrays, n_blocks_used, block_size_used)

    blocked_arrays[i] has shape (n_blocks, block_size).
    """
    if not arrays_1d:
        return [], 0, 0

    arrs = [np.asarray(a, dtype=float).ravel() for a in arrays_1d]
    lens = [a.size for a in arrs]
    if any(n == 0 for n in lens):
        return [np.zeros((0, 0), float) for _ in arrs], 0, 0

    # Align by truncating to the *last* min length (so tails correspond)
    n = int(min(lens))
    arrs = [a[-n:] for a in arrs]

    # Tail selection
    frac_tail = float(frac_tail)
    frac_tail = min(max(frac_tail, 0.0), 1.0)
    start = int((1.0 - frac_tail) * n)
    start = min(max(start, 0), n - 1)
    arrs = [a[start:] for a in arrs]
    tail_n = int(arrs[0].size)
    if tail_n <= 0:
        return [np.zeros((0, 0), float) for _ in arrs], 0, 0

    n_blocks = min(int(n_blocks_target), tail_n)
    if n_blocks <= 0:
        return [np.zeros((0, 0), float) for _ in arrs], 0, 0

    block_size = tail_n // n_blocks
    if block_size <= 0:
        # extremely short tail: fall back to a single block
        n_blocks = 1
        block_size = tail_n

    trim = n_blocks * block_size
    out = [a[:trim].reshape(n_blocks, block_size) for a in arrs]
    return out, int(n_blocks), int(block_size)

def qst_single_fluctuation_from_series(
    *,
    energy_eV: np.ndarray,
    nmols: np.ndarray,
    temperature_K: float,
    frac_tail: float = 0.8,
    n_blocks_target: int = 30,
    mol_energy_eV: float = 0
) -> tuple[float | None, float | None, int, int]:
    """Single-component Qst via Qst = kBT - Cov(U,N)/Var(N), with block-averaged uncertainty.

    If mol_energy_eV is provided, uses corrected energy:
        U_corr(t) = U_total(t) - mol_energy_eV * N(t)

    Returns:
      (qst_mean_kJmol, qst_std_kJmol, n_blocks, block_size)
    """
    (U_blk, N_blk), n_blocks, block_size = _tail_blockify_fixed_nblocks(
        [energy_eV, nmols], frac_tail=frac_tail, n_blocks_target=n_blocks_target
    )
    if n_blocks <= 0 or block_size <= 0:
        return None, None, 0, 0

    kBT_eV = float(KB_EVK * float(temperature_K))
    qst_blocks = np.full(n_blocks, np.nan, dtype=float)

    e_ref = None if mol_energy_eV is None else float(mol_energy_eV)

    for b in range(n_blocks):
        U = U_blk[b]
        N = N_blk[b]

        # Subtract per-molecule reference energy if requested
        if e_ref is not None and np.isfinite(e_ref):
            U = U - e_ref * N

        # Var(N) and Cov(U,N) using expectation form
        N_mean = float(np.mean(N))
        U_mean = float(np.mean(U))
        varN = float(np.mean(N * N) - N_mean * N_mean)
        if not np.isfinite(varN) or varN <= 0.0:
            continue
        covUN = float(np.mean(U * N) - U_mean * N_mean)

        qst_eV = kBT_eV - (covUN / varN)
        qst_blocks[b] = qst_eV * EV_TO_KJMOL

    good = qst_blocks[np.isfinite(qst_blocks)]
    if good.size == 0:
        return None, None, int(n_blocks), int(block_size)

    mean = float(np.mean(good))
    std = float(np.std(good, ddof=1)) if good.size >= 2 else float("nan")
    return _finite_or_none(mean), _finite_or_none(std), int(n_blocks), int(block_size)


def qst_multicomponent_fluctuation_from_series(
    *,
    energy_eV: np.ndarray,
    nmols_by_species: dict[str, np.ndarray],
    species_names: list[str],
    temperature_K: float,
    frac_tail: float = 0.8,
    n_blocks_target: int = 30,
    mol_energy_eV_by_species: dict[str, float] | None = None,
) -> tuple[dict[str, float | None], dict[str, float | None], int, int]:
    """Multicomponent partial Qst_i via solving C x = c, then Qst_i = kBT - x_i.

    If mol_energy_eV_by_species is provided, uses corrected energy:
        U_corr(t) = U_total(t) - sum_i mol_energy_eV_by_species[i] * N_i(t)

    Returns:
      (qst_mean_by_species_kJmol, qst_std_by_species_kJmol, n_blocks, block_size)
    """
    arrays = [energy_eV] + [nmols_by_species[nm] for nm in species_names]
    blocked, n_blocks, block_size = _tail_blockify_fixed_nblocks(
        arrays, frac_tail=frac_tail, n_blocks_target=n_blocks_target
    )
    if n_blocks <= 0 or block_size <= 0:
        return ({nm: None for nm in species_names}, {nm: None for nm in species_names}, 0, 0)

    U_blk = blocked[0]      # (B, M)
    N_blks = blocked[1:]    # list of (B, M)

    kBT_eV = float(KB_EVK * float(temperature_K))
    S = len(species_names)
    qst_blocks = np.full((n_blocks, S), np.nan, dtype=float)

    # Build per-species ref energies in the same order as species_names
    if mol_energy_eV_by_species is None:
        e_ref_vec = None
    else:
        e_ref_vec = np.array(
            [float(mol_energy_eV_by_species[nm]) for nm in species_names],
            dtype=float,
        )

    for b in range(n_blocks):
        U = U_blk[b]
        Nmat = np.stack([Nb[b] for Nb in N_blks], axis=1)  # (M, S)

        # Subtract per-molecule reference energies if requested:
        # U_corr = U - sum_i e_ref_i * N_i
        if e_ref_vec is not None and np.all(np.isfinite(e_ref_vec)):
            U = U - (Nmat @ e_ref_vec)

        # Centered for covariance
        Uc = U - np.mean(U)
        Nc = Nmat - np.mean(Nmat, axis=0, keepdims=True)

        M = float(U.size)
        if M <= 0:
            continue

        C = (Nc.T @ Nc) / M     # (S,S)
        c = (Nc.T @ Uc) / M     # (S,)

        try:
            x = np.linalg.solve(C, c)
        except np.linalg.LinAlgError:
            x, *_ = np.linalg.lstsq(C, c, rcond=None)

        qst_eV = kBT_eV - x
        qst_blocks[b, :] = qst_eV * EV_TO_KJMOL

    q_mean: dict[str, float | None] = {}
    q_std: dict[str, float | None] = {}
    for i, nm in enumerate(species_names):
        vals = qst_blocks[:, i]
        vals = vals[np.isfinite(vals)]
        if vals.size == 0:
            q_mean[nm] = None
            q_std[nm] = None
        else:
            q_mean[nm] = _finite_or_none(float(np.mean(vals)))
            q_std[nm] = _finite_or_none(float(np.std(vals, ddof=1))) if vals.size >= 2 else None

    return q_mean, q_std, int(n_blocks), int(block_size)


def compute_eq_loading_from_traj_multicomponent(
    traj_path: Path,
    species_list: list[Atoms],
    species_names: list[str],
    species_tags: list[int],
    host: Atoms,
    host_natoms: int,
    frac_tail: float = 0.05,
) -> tuple[dict[str, float | None], float | None]:
    """Compute equilibrium loadings (mmol/g) per species from trajectory. Returns (q_by_adsorbate, q_total)."""
    traj = Trajectory(str(traj_path))
    nframes = len(traj)
    if nframes == 0:
        return {n: None for n in species_names}, None
    lens = {name: len(sp) for name, sp in zip(species_names, species_list)}
    nmols = {name: np.zeros(nframes, dtype=int) for name in species_names}
    for i, atoms in enumerate(traj):
        for name, tag in zip(species_names, species_tags):
            nmols[name][i] = count_molecules_by_tag(atoms, host_natoms, tag, lens[name])
    host_mass_kg = _host_mass_kg(host, host_natoms)
    q_by_adsorbate: dict[str, float | None] = {}
    for name in species_names:
        eq_nmols = _eq_nmols_from_array(nmols[name], frac_tail=frac_tail)
        mol_per_kg = _mol_per_kg_from_nmols(eq_nmols, host_mass_kg)
        q_by_adsorbate[name] = _finite_or_none(mol_per_kg * 1000.0) if np.isfinite(mol_per_kg) else None
    finite_vals = [v for v in q_by_adsorbate.values() if v is not None]
    q_total = float(np.sum(finite_vals)) if finite_vals else None
    return q_by_adsorbate, q_total


def gcmc_standalone_payload_multicomponent(
    *,
    species_names: list[str],
    temperature_K: float,
    pressure_partial_bar: dict[str, float],
    scheme: str,
    q_by_adsorbate: dict[str, float | None],
    q_total: float | None,
) -> dict[str, Any]:
    """COFclean isotherm entry (multicomponent) as a standalone JSON."""
    p_total = float(np.sum(list(pressure_partial_bar.values())))
    point = {
        "p_total": p_total,
        "p_partial": {k: float(v) for k, v in pressure_partial_bar.items()},
        "q_total": q_total,
        "q_by_adsorbate": dict(q_by_adsorbate),
    }
    return {
        "adsorbates": list(species_names),
        "temperature_K": float(temperature_K),
        "source": "simulation",
        "units": {
            "pressure_total": "bar",
            "pressure_partial": "bar",
            "loading_total": "mmol/g",
            "loading_by_adsorbate": "mmol/g",
        },
        "points": [point],
        "ref": None,
        "notes": f"scheme={scheme}",
    }


def gcmc_standalone_payload_single(
    *,
    adsorbate: str,
    temperature_K: float,
    pressure_bar: float,
    scheme: str,
    q_total_mmol_g: float | None,
) -> dict[str, Any]:
    """COFclean isotherm entry as a standalone JSON (single point)."""
    point = {
        "p_total": float(pressure_bar),
        "p_partial": {adsorbate: float(pressure_bar)},
        "q_total": _finite_or_none(q_total_mmol_g) if q_total_mmol_g is not None else None,
        "q_by_adsorbate": {adsorbate: _finite_or_none(q_total_mmol_g) if q_total_mmol_g is not None else None},
    }
    return {
        "adsorbates": [adsorbate],
        "temperature_K": float(temperature_K),
        "source": "simulation",
        "units": {
            "pressure_total": "bar",
            "pressure_partial": "bar",
            "loading_total": "mmol/g",
            "loading_by_adsorbate": "mmol/g",
        },
        "points": [point],
        "ref": None,
        "notes": f"scheme={scheme}",
    }


def write_gcmc_results_json(output_path: Path, payload: dict[str, Any]) -> None:
    """Write standalone GCMC results JSON (no global properties.json)."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n")


# -----------------------------------------------------------------------------
# Small helpers (kept for callers)
# -----------------------------------------------------------------------------


def canonicalize_species_key(s: str) -> str:
    """Canonicalize a species string for stable sorting (e.g., CO2->co2)."""
    return "".join(ch.lower() for ch in (s or "").strip() if ch.isalnum())


def _resolve_species_name(name: str, gas_db: dict) -> str:
    """Resolve species name against gas DB (accept CO2/co2/etc)."""
    if name in gas_db:
        return name
    if name.upper() in gas_db:
        return name.upper()
    can = canonicalize_species_key(name)
    for k in gas_db.keys():
        if canonicalize_species_key(k) == can:
            return k
    raise KeyError(f"Unknown gas '{name}'. Available: {sorted(gas_db.keys())}")


def _parse_kij_entry(s: str) -> tuple[str, str, float]:
    """Parse a single kij entry string, e.g. 'CO2,N2,0.0' -> (A, B, val)."""
    parts = [x.strip() for x in s.split(",")]
    if len(parts) != 3:
        raise ValueError(f"Bad --kij '{s}'. Expected 'A,B,val'")
    return parts[0], parts[1], float(parts[2])


def ensure_tags(atoms: Atoms, *, default: int = 0) -> np.ndarray:
    """Ensure atoms has a tags array of correct length; returns the tags view."""
    n = len(atoms)
    tags = np.asarray(atoms.get_tags(), dtype=int)
    if tags.shape[0] != n:
        tags = np.full(n, int(default), dtype=int)
        atoms.set_tags(tags)
    return tags


def a3_to_m3(v_a3: float) -> float:
    """Convert Å^3 to m^3."""
    return float(v_a3) * 1e-30


def bar_to_pa(p_bar: float) -> float:
    """Convert bar to Pa (1 bar = 1e5 Pa)."""
    return float(p_bar) * 1e5
