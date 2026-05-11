"""
Run a Frenkel-Ladd free-energy calculation for a pre-equilibrated periodic solid.

This script implements a portable Frenkel-Ladd workflow for a periodic solid.
It expects a structure that is already relaxed and equilibrated at the target
state point.

Usage:
    python run_frenkel_ladd.py --structure path/to/solid.cif --name Si_demo \
        --calculator mace --model-name MACE-OMAT-0-small \
        --temperature 300 --output-dir ./frenkel_ladd/Si_demo

Requirements:
    - Conda environment: depends on --calculator
        mace                  -> use 'mace-agent' conda env
        fairchem              -> use 'fairchem-agent' conda env
        matgl                 -> use 'matgl-agent' conda env
    - The transferable skill repo must provide `src.utils.mlips.loader`.
"""

from __future__ import annotations

import argparse
import importlib
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

import numpy as np
from ase import units
from ase.calculators.calculator import Calculator
from ase.calculators.mixing import MixedCalculator
from ase.io import read, write
from ase.md.langevin import Langevin
from ase.md.velocitydistribution import MaxwellBoltzmannDistribution, Stationary

try:
    from tqdm.auto import tqdm
except Exception:  # pragma: no cover - optional dependency

    def tqdm(iterable, **_: Any):
        return iterable


os.environ.setdefault("MATGL_BACKEND", "DGL")

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("FrenkelLadd-Skill")

TRAPEZOID = getattr(np, "trapezoid", np.trapz)


class HarmonicOscillatorCalculator(Calculator):
    """Harmonic oscillator with per-atom spring constants."""

    implemented_properties = ["energy", "forces"]

    def __init__(
        self,
        spring_constants: np.ndarray,
        equilibrium_positions: np.ndarray,
    ) -> None:
        super().__init__()
        self.spring_constants = np.asarray(spring_constants, dtype=float)
        self.equilibrium_positions = np.asarray(equilibrium_positions, dtype=float)

    def calculate(
        self,
        atoms=None,
        properties=None,
        system_changes=None,
    ) -> None:
        super().calculate(atoms, properties, system_changes)
        displacements = atoms.get_positions() - self.equilibrium_positions
        energy = 0.5 * np.sum(self.spring_constants * np.sum(displacements**2, axis=1))
        forces = -self.spring_constants[:, None] * displacements
        self.results = {"energy": float(energy), "forces": forces}


def find_project_root() -> Path:
    """Find the nearest parent that looks like the project root."""

    script_path = Path(__file__).resolve()
    for parent in script_path.parents:
        if (parent / "src").exists():
            return parent
    fallback_index = min(4, len(script_path.parents) - 1)
    return script_path.parents[fallback_index]


def load_wrapper_module():
    """Import the transferable MLIP wrapper loader lazily."""

    project_root = find_project_root()
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    try:
        loader_module = importlib.import_module("src.utils.mlips.loader")
    except Exception as exc:  # pragma: no cover - depends on target repo
        raise RuntimeError(
            "Could not import `src.utils.mlips.loader`. "
            "This portable skill expects the transferable MLIP wrapper stack "
            "to be available in the target repo."
        ) from exc

    if not hasattr(loader_module, "load_wrapper"):
        raise RuntimeError(
            "`src.utils.mlips.loader` was imported, but `load_wrapper` is missing."
        )

    return loader_module


def select_device(device: str) -> str:
    if device != "auto":
        return device

    try:
        import torch
    except Exception:
        logger.warning("Torch is unavailable; defaulting to CPU.")
        return "cpu"

    return "cuda" if torch.cuda.is_available() else "cpu"


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


def build_lambda_schedule(switching_steps: int, switching_type: str) -> np.ndarray:
    if switching_type == "linear":
        return np.linspace(0.0, 1.0, switching_steps)
    if switching_type == "polynomial":
        t = np.linspace(0.0, 1.0, switching_steps)
        return t**5 * (70 * t**4 - 315 * t**3 + 540 * t**2 - 420 * t + 126)
    raise ValueError(f"Invalid switching type: {switching_type}")


def integrate_switching(
    forward_lambda_steps: np.ndarray,
    forward_integrand: np.ndarray,
    backward_lambda_steps: np.ndarray,
    backward_integrand: np.ndarray,
) -> dict[str, float]:
    forward_work = TRAPEZOID(forward_integrand, forward_lambda_steps)
    backward_work = TRAPEZOID(backward_integrand, backward_lambda_steps)
    return {
        "free_energy_difference": 0.5 * float(forward_work - backward_work),
        "dissipated_energy": 0.5 * float(forward_work + backward_work),
        "forward_work": float(forward_work),
        "backward_work": float(backward_work),
    }


def analyze_frenkel_ladd(
    forward_energy_contributions: np.ndarray,
    backward_energy_contributions: np.ndarray,
    lambda_steps: np.ndarray,
    spring_constants: np.ndarray,
    masses: np.ndarray,
    temperature_K: float,
) -> dict[str, float]:
    energy_weights = np.array([-1.0, 1.0], dtype=float)[None, :]
    forward_integrand = np.sum(energy_weights * forward_energy_contributions, axis=1)
    backward_integrand = np.sum(energy_weights * backward_energy_contributions, axis=1)

    integrate_results = integrate_switching(
        forward_lambda_steps=lambda_steps,
        forward_integrand=forward_integrand,
        backward_lambda_steps=lambda_steps[::-1],
        backward_integrand=backward_integrand,
    )

    omega = np.sqrt(spring_constants / masses)
    kT = units.kB * temperature_K
    hbar = units._hbar / units._e * units.s
    harmonic_reference_free_energy = 3.0 * kT * np.sum(np.log(hbar * omega / kT))

    helmholtz_free_energy = (
        harmonic_reference_free_energy - integrate_results["free_energy_difference"]
    )

    return {
        "helmholtz_free_energy": float(helmholtz_free_energy),
        "dissipated_energy": float(integrate_results["dissipated_energy"]),
        "free_energy_difference": float(integrate_results["free_energy_difference"]),
        "harmonic_reference_free_energy": float(harmonic_reference_free_energy),
        "forward_work": float(integrate_results["forward_work"]),
        "backward_work": float(integrate_results["backward_work"]),
    }


def get_equivalent_indices(atoms) -> list[list[int]]:
    try:
        from pymatgen.io.ase import AseAtomsAdaptor
        from pymatgen.symmetry.analyzer import SpacegroupAnalyzer
    except Exception as exc:  # pragma: no cover - depends on target repo
        raise RuntimeError("Spring-constant symmetrization requires pymatgen.") from exc

    structure = AseAtomsAdaptor.get_structure(atoms)
    sga = SpacegroupAnalyzer(structure)
    return sga.get_symmetrized_structure().equivalent_indices


def ensure_finite(name: str, values: Any) -> None:
    array = np.asarray(values, dtype=float)
    if not np.all(np.isfinite(array)):
        raise ValueError(f"Non-finite values detected in `{name}`.")


def to_serializable(obj: Any) -> Any:
    if isinstance(obj, Path):
        return str(obj)
    if isinstance(obj, dict):
        return {key: to_serializable(value) for key, value in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_serializable(value) for value in obj]
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.bool_):
        return bool(obj)
    return obj


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a Frenkel-Ladd free-energy calculation with a portable MLIP wrapper stack."
    )
    parser.add_argument(
        "--structure", type=Path, required=True, help="Input periodic structure file."
    )
    parser.add_argument(
        "--name", type=str, required=True, help="Identifier for output files."
    )
    parser.add_argument(
        "--calculator",
        type=str,
        required=True,
        choices=["mace", "fairchem", "matgl"],
        help="Backend MLIP calculator to use.",
    )
    parser.add_argument(
        "--model-name", type=str, required=True, help="Model name or checkpoint path."
    )
    parser.add_argument(
        "--task-name",
        type=str,
        default=None,
        help="Optional task name for multitask models.",
    )
    parser.add_argument(
        "--temperature", type=float, required=True, help="Temperature in Kelvin."
    )
    parser.add_argument(
        "--pressure-gpa",
        type=float,
        default=None,
        help="Optional pressure in GPa to also report Gibbs free energy.",
    )
    parser.add_argument(
        "--timestep-fs",
        type=float,
        default=1.0,
        help="Langevin timestep in femtoseconds.",
    )
    parser.add_argument(
        "--thermostat-damping-fs",
        type=float,
        default=100.0,
        help="Langevin thermostat damping time in femtoseconds.",
    )
    parser.add_argument(
        "--msd-equilibration-steps",
        type=int,
        default=1000,
        help="NVT equilibration steps before MSD production.",
    )
    parser.add_argument(
        "--msd-production-steps",
        type=int,
        default=10000,
        help="NVT production steps used to estimate mean squared displacement.",
    )
    parser.add_argument(
        "--equilibration-steps",
        type=int,
        default=5000,
        help="Harmonic-potential equilibration steps between forward and backward switching.",
    )
    parser.add_argument(
        "--switching-steps",
        type=int,
        default=25000,
        help="Forward and backward switching steps.",
    )
    parser.add_argument(
        "--switching-type",
        type=str,
        default="polynomial",
        choices=["linear", "polynomial"],
        help="Switching schedule.",
    )
    parser.add_argument(
        "--record-interval",
        type=int,
        default=1,
        help="Record every N MD steps.",
    )
    parser.add_argument(
        "--symmetrize-spring-constants",
        dest="symmetrize_spring_constants",
        action="store_true",
        default=True,
        help="Average spring constants across symmetry-equivalent atoms (default: True).",
    )
    parser.add_argument(
        "--no-symmetrize-spring-constants",
        dest="symmetrize_spring_constants",
        action="store_false",
        help="Do not symmetrize spring constants.",
    )
    parser.add_argument(
        "--device",
        type=str,
        default="auto",
        choices=["auto", "cuda", "cpu"],
        help="Device to use ('auto' picks CUDA if available).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Directory to save outputs. Defaults to ./frenkel_ladd/<name>.",
    )
    return parser.parse_args()


def validate_inputs(args: argparse.Namespace, atoms) -> None:
    if args.temperature <= 0:
        raise ValueError("`--temperature` must be positive.")
    if args.timestep_fs <= 0:
        raise ValueError("`--timestep-fs` must be positive.")
    if args.thermostat_damping_fs <= 0:
        raise ValueError("`--thermostat-damping-fs` must be positive.")
    if args.record_interval <= 0:
        raise ValueError("`--record-interval` must be a positive integer.")
    if args.msd_equilibration_steps < 0:
        raise ValueError("`--msd-equilibration-steps` cannot be negative.")
    if args.msd_production_steps <= 0:
        raise ValueError("`--msd-production-steps` must be positive.")
    if args.equilibration_steps < 0:
        raise ValueError("`--equilibration-steps` cannot be negative.")
    if args.switching_steps < 2:
        raise ValueError("`--switching-steps` must be at least 2.")
    if not np.any(atoms.pbc):
        raise ValueError(
            "Frenkel-Ladd requires a periodic solid. The input structure is not periodic."
        )
    try:
        volume = float(atoms.get_volume())
    except Exception as exc:
        raise ValueError("Could not determine the input cell volume.") from exc
    if volume <= 0:
        raise ValueError("The input structure must have a positive cell volume.")


def run_frenkel_ladd(args: argparse.Namespace) -> dict[str, Any]:
    atoms = read(str(args.structure))
    normalize_charge_spin(atoms)
    validate_inputs(args, atoms)

    output_dir = args.output_dir or Path("frenkel_ladd") / args.name
    output_dir.mkdir(parents=True, exist_ok=True)

    input_structure_path = output_dir / "input_structure.cif"
    write(str(input_structure_path), atoms)

    logger.info(
        "Loaded %s (%d atoms) from %s",
        atoms.get_chemical_formula(),
        len(atoms),
        args.structure,
    )

    device = select_device(args.device)
    loader_module = load_wrapper_module()
    wrapper = loader_module.load_wrapper(
        args.calculator,
        model_name=args.model_name,
        device=device,
        task_name=args.task_name,
    )
    calc = wrapper.create_calculator()
    atoms.calc = calc

    lambda_steps = build_lambda_schedule(args.switching_steps, args.switching_type)
    trace_lambda_steps = lambda_steps[:: args.record_interval]

    dyn = Langevin(
        atoms,
        timestep=args.timestep_fs * units.fs,
        temperature_K=args.temperature,
        friction=1 / (args.thermostat_damping_fs * units.fs),
    )
    MaxwellBoltzmannDistribution(atoms, temperature_K=args.temperature)
    Stationary(atoms)

    equilibrium_positions = atoms.get_positions().copy()

    logger.info("Running NVT equilibration for MSD estimation...")
    for _ in tqdm(range(args.msd_equilibration_steps), desc="MSD NVT eq"):
        dyn.run(steps=1)

    logger.info("Running NVT production for MSD estimation...")
    squared_disp_record = []
    for step in tqdm(range(args.msd_production_steps), desc="MSD NVT prod"):
        dyn.run(steps=1)
        if step % args.record_interval == 0:
            squared_disp_record.append(
                np.sum((atoms.get_positions() - equilibrium_positions) ** 2, axis=1)
            )

    squared_disp_record = np.asarray(squared_disp_record, dtype=float)
    mean_squared_displacement = np.mean(squared_disp_record, axis=0)
    ensure_finite("mean_squared_displacement", mean_squared_displacement)
    if np.any(mean_squared_displacement <= 0.0):
        raise ValueError(
            "Encountered non-positive mean squared displacement values. "
            "The structure may be over-constrained or the sampling is insufficient."
        )

    spring_constants = 3.0 * units.kB * args.temperature / mean_squared_displacement

    if args.symmetrize_spring_constants:
        logger.info("Symmetrizing spring constants over equivalent sites...")
        equivalent_indices = get_equivalent_indices(atoms)
        for indices in equivalent_indices:
            spring_constants[indices] = np.mean(spring_constants[indices])

    ensure_finite("spring_constants", spring_constants)

    harmonic_calc = HarmonicOscillatorCalculator(
        spring_constants=spring_constants,
        equilibrium_positions=equilibrium_positions,
    )
    mixed_calc = MixedCalculator(
        calc1=calc,
        calc2=harmonic_calc,
        weight1=1.0,
        weight2=0.0,
    )

    logger.info("Running forward switching from physical to harmonic potential...")
    atoms.calc = mixed_calc
    forward_energy_contributions = []
    for step in tqdm(range(args.switching_steps), desc="FL NVT fwd"):
        atoms.calc.set_weights(1.0 - lambda_steps[step], lambda_steps[step])
        dyn.run(steps=1)
        if step % args.record_interval == 0:
            energies = np.asarray(
                atoms.calc.results["energy_contributions"],
                dtype=float,
            )
            forward_energy_contributions.append(energies)

    forward_energy_contributions = np.asarray(forward_energy_contributions, dtype=float)
    ensure_finite("forward_energy_contributions", forward_energy_contributions)

    logger.info("Equilibrating in the harmonic reference potential...")
    atoms.calc = harmonic_calc
    for _ in tqdm(range(args.equilibration_steps), desc="FL NVT eq"):
        dyn.run(steps=1)

    logger.info("Running backward switching from harmonic to physical potential...")
    atoms.calc = mixed_calc
    backward_energy_contributions = []
    for step in tqdm(range(args.switching_steps - 1, -1, -1), desc="FL NVT rev"):
        atoms.calc.set_weights(1.0 - lambda_steps[step], lambda_steps[step])
        dyn.run(steps=1)
        if step % args.record_interval == 0:
            energies = np.asarray(
                atoms.calc.results["energy_contributions"],
                dtype=float,
            )
            backward_energy_contributions.append(energies)

    backward_energy_contributions = np.asarray(
        backward_energy_contributions, dtype=float
    )
    ensure_finite("backward_energy_contributions", backward_energy_contributions)

    logger.info("Analyzing switching trajectories...")
    analysis = analyze_frenkel_ladd(
        forward_energy_contributions=forward_energy_contributions,
        backward_energy_contributions=backward_energy_contributions,
        lambda_steps=trace_lambda_steps,
        spring_constants=spring_constants,
        masses=atoms.get_masses(),
        temperature_K=args.temperature,
    )

    ensure_finite("analysis", list(analysis.values()))

    if args.pressure_gpa is not None:
        gibbs_free_energy = (
            analysis["helmholtz_free_energy"]
            + args.pressure_gpa * units.GPa * atoms.get_volume()
        )
        analysis["gibbs_free_energy"] = float(gibbs_free_energy)
        ensure_finite("gibbs_free_energy", gibbs_free_energy)

    final_structure_path = output_dir / "final_structure.cif"
    write(str(final_structure_path), atoms)

    traces_path = output_dir / "frenkel_ladd_traces.npz"
    np.savez(
        traces_path,
        lambda_steps=trace_lambda_steps,
        forward_energy_contributions=forward_energy_contributions,
        backward_energy_contributions=backward_energy_contributions,
        spring_constants=spring_constants,
        mean_squared_displacement=mean_squared_displacement,
    )

    model_name = getattr(wrapper, "model_name", args.model_name)
    results: dict[str, Any] = {
        "name": args.name,
        "formula": atoms.get_chemical_formula(),
        "num_atoms": len(atoms),
        "calculator": args.calculator,
        "model_name": model_name,
        "device": device,
        "temperature_K": float(args.temperature),
        "timestep_fs": float(args.timestep_fs),
        "thermostat_damping_fs": float(args.thermostat_damping_fs),
        "msd_equilibration_steps": int(args.msd_equilibration_steps),
        "msd_production_steps": int(args.msd_production_steps),
        "equilibration_steps": int(args.equilibration_steps),
        "switching_steps": int(args.switching_steps),
        "switching_type": args.switching_type,
        "record_interval": int(args.record_interval),
        "symmetrize_spring_constants": bool(args.symmetrize_spring_constants),
        "volume_A3": float(atoms.get_volume()),
        "helmholtz_free_energy": analysis["helmholtz_free_energy"],
        "dissipated_energy": analysis["dissipated_energy"],
        "free_energy_difference": analysis["free_energy_difference"],
        "harmonic_reference_free_energy": analysis["harmonic_reference_free_energy"],
        "forward_work": analysis["forward_work"],
        "backward_work": analysis["backward_work"],
        "input_structure": input_structure_path,
        "final_structure": final_structure_path,
        "trace_file": traces_path,
        "structure_source": args.structure,
        "units": {
            "free_energy": "eV (total cell)",
            "dissipated_energy": "eV (total cell)",
            "volume": "A^3",
            "pressure": "GPa",
            "temperature": "K",
            "spring_constants": "eV/A^2",
            "mean_squared_displacement": "A^2",
        },
        "quality_checks": {
            "dissipated_energy_per_atom": analysis["dissipated_energy"] / len(atoms),
            "mean_squared_displacement_min_A2": float(
                np.min(mean_squared_displacement)
            ),
            "mean_squared_displacement_max_A2": float(
                np.max(mean_squared_displacement)
            ),
            "spring_constant_min_eV_per_A2": float(np.min(spring_constants)),
            "spring_constant_max_eV_per_A2": float(np.max(spring_constants)),
        },
    }
    if args.task_name is not None:
        results["task_name"] = args.task_name
    if args.pressure_gpa is not None:
        results["pressure_GPa"] = float(args.pressure_gpa)
        results["gibbs_free_energy"] = analysis["gibbs_free_energy"]

    results_path = output_dir / "frenkel_ladd_results.json"
    with open(results_path, "w", encoding="utf-8") as handle:
        json.dump(to_serializable(results), handle, indent=2)

    logger.info("Results saved to %s", results_path)
    logger.info("Traces saved to %s", traces_path)
    return results


def main() -> int:
    args = parse_args()
    run_frenkel_ladd(args)
    # Save input configs for reproducibility
    from src.utils.config_utils import save_skill_inputs
    save_skill_inputs(args, args.output_dir)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
