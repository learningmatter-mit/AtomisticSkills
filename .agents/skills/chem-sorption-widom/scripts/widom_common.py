"""
Shared Widom insertion logic for UMA (port from COFclean widom/widom_common.py).
Output: single standalone JSON with COFclean Henry fields (no staging, no other files).
"""

from pathlib import Path
import argparse
import json
import logging
import math
import sys
from typing import Any

from ase import Atoms
from ase.calculators.calculator import Calculator
from ase.io import read

# Vendored widom package (same dir as this file)
_SCRIPT_DIR = Path(__file__).resolve().parent
_WIDOM_SRC = _SCRIPT_DIR / "widom_src"
if _WIDOM_SRC.is_dir() and str(_WIDOM_SRC) not in sys.path:
    sys.path.insert(0, str(_WIDOM_SRC))

from widom import WidomInsertionResults, run_widom_insertion  # noqa: E402

LOGGER = logging.getLogger(__name__)


def select_device(requested: str) -> str:
    if requested != "auto":
        return requested
    try:
        import torch
    except Exception as exc:
        raise RuntimeError("Device selection requires torch when using --device auto.") from exc
    return "cuda" if torch.cuda.is_available() else "cpu"


def read_structure(structure_path: Path | str) -> Atoms:
    atoms = read(str(structure_path))
    try:
        if not any(atoms.get_pbc()):
            atoms.set_pbc(True)
    except Exception:
        pass
    return atoms


def add_common_widom_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--structure", type=Path, required=True, help="Path to input structure (.cif or .xyz)")
    parser.add_argument("--name", type=str, required=True, help="Name or id of the framework")
    parser.add_argument("--gas", type=str, required=True, help="Gas molecule name (e.g. CO2, N2)")
    parser.add_argument("--temperature", type=float, required=True, help="Temperature in Kelvin")
    parser.add_argument("--num-insertions", type=int, default=5000, help="Number of Widom insertion attempts")
    parser.add_argument("--optimize-structures", action="store_true", help="Optimize framework and gas before insertion (default: use structure as-is)")
    parser.add_argument("--cutoff-distance", type=float, default=1.0, help="Minimum framework-gas distance (Å)")
    parser.add_argument("--cutoff-to-com", action="store_false", help="Use gas center-of-mass for cutoff checks")
    parser.add_argument("--min-interplanar-distance", type=float, default=12.0, help="Min interplanar distance before supercell (Å)")
    parser.add_argument("--random-seed", type=int, default=0, help="Random seed for sampling and bootstrap")
    parser.add_argument("--min-interaction-energy", type=float, default=-1.25, help="Minimum valid interaction energy (eV)")
    parser.add_argument("--model-outputs-interaction-energy", action="store_false", help="Treat model energies as interaction energies")
    parser.add_argument("--output-dir", type=Path, default=Path("."), help="Directory for output JSON")


def _format_temperature_key(temperature: float) -> str:
    rounded = round(temperature)
    if abs(temperature - rounded) < 1e-6:
        return f"{int(rounded)}K"
    return f"{temperature:g}K"


def _finite_or_none(x: Any) -> float | None:
    try:
        xf = float(x)
    except Exception:
        return None
    return xf if math.isfinite(xf) else None


def widom_standalone_payload(
    *,
    cof_name: str,
    gas: str,
    temperature: float,
    results: WidomInsertionResults,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """COFclean Henry fields as a standalone JSON (no from_run)."""
    return {
        "cof_name": cof_name,
        "adsorbates": [gas],
        "temperature_K": float(temperature),
        "henry_mol_kg_Pa": _finite_or_none(results.henry_coefficient),
        "henry_stderr_mol_kg_Pa": _finite_or_none(results.henry_coefficient_std),
        "heat_of_adsorption_kJ_mol": _finite_or_none(results.heat_of_adsorption),
        "heat_of_adsorption_std_kJ_mol": _finite_or_none(results.heat_of_adsorption_std),
        "source": "computed",
        "method": "widom",
        "ref": None,
        "notes": None,
        "config": config or {},
    }


def run_widom_job(
    *,
    calculator: Calculator,
    structure: Atoms,
    gas: str,
    temperature: float,
    model_outputs_interaction_energy: bool,
    num_insertions: int,
    optimize_structures: bool,
    cutoff_distance: float,
    cutoff_to_com: bool,
    min_interplanar_distance: float,
    random_seed: int,
    min_interaction_energy: float,
    output_path: Path,
    name: str,
    model_tag: str,
    extra_config: dict[str, Any] | None = None,
) -> WidomInsertionResults:
    """Run Widom insertion and write a single standalone JSON (COFclean Henry fields)."""
    config: dict[str, Any] = {
        "name": name,
        "model_tag": model_tag,
        "gas": gas,
        "temperature": temperature,
        "num_insertions": num_insertions,
        "optimize_structures": optimize_structures,
        "cutoff_distance": cutoff_distance,
        "cutoff_to_com": cutoff_to_com,
        "min_interplanar_distance": min_interplanar_distance,
        "random_seed": random_seed,
        "min_interaction_energy": min_interaction_energy,
        "model_outputs_interaction_energy": model_outputs_interaction_energy,
    }
    if extra_config:
        config.update(extra_config)
    LOGGER.debug("Widom configuration: %s", config)

    results = run_widom_insertion(
        calculator=calculator,
        structure=structure,
        gas=gas,
        temperature=temperature,
        model_outputs_interaction_energy=False,
        num_insertions=num_insertions,
        cutoff_distance=cutoff_distance,
        cutoff_to_com=cutoff_to_com,
        min_interplanar_distance=min_interplanar_distance,
        random_seed=random_seed,
        min_interaction_energy=min_interaction_energy,
    )

    payload = widom_standalone_payload(
        cof_name=name,
        gas=gas,
        temperature=temperature,
        results=results,
        config=config,
    )
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n")
    LOGGER.info("Wrote Widom results to %s", output_path)
    return results
