import argparse
import os
import sys
import json
import logging

# Add project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.utils.serialization_utils import recursive_tolist
from src.utils.research_utils import get_current_research_dir
from ase.io import read

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("QHA-Skill")


from src.utils.mlips.loader import load_wrapper


def scale_factors_from_volume_window(window, n_volumes):
    """Linear scale factors spanning +/-`window` in VOLUME about the relaxed cell.

    QHACalc scales the lattice, so a volume window maps to the cube root.
    """
    import numpy as np

    return tuple(
        float(v) ** (1.0 / 3.0)
        for v in np.linspace(1.0 - window, 1.0 + window, n_volumes)
    )


def run_qha(args, wrapper, atoms):
    from matcalc import QHACalc

    if not args.output_dir:
        args.output_dir = str(get_current_research_dir() / "vibrational" / "qha")
    os.makedirs(args.output_dir, exist_ok=True)

    calc = wrapper.create_calculator()

    scale_kwargs = {}
    if args.volume_window is not None:
        scale_kwargs["scale_factors"] = scale_factors_from_volume_window(
            args.volume_window, args.n_volumes
        )

    qha_calc = QHACalc(
        calculator=calc,
        t_step=args.t_step,
        t_max=args.t_max,
        t_min=args.t_min,
        eos=args.eos,
        # matcalc defaults fmax to 1e-5 eV/A, which MLIP forces routinely cannot
        # reach: QHACalc then raises out of its pre-relaxation instead of
        # returning. 1e-3 is tight enough for QHA and is reachable.
        fmax=args.fmax,
        max_steps=args.max_steps,
        write_gibbs_temperature=os.path.join(args.output_dir, "gibbs_temperature.dat"),
        write_thermal_expansion=os.path.join(args.output_dir, "thermal_expansion.dat"),
        **scale_kwargs,
    )

    logger.info("Starting QHA calculation...")
    result = qha_calc.calc(atoms)

    summary = {
        "summary": {
            "temp_range": [args.t_min, args.t_max],
            "num_points": len(result.get("temperatures", [])),
            "eos": args.eos,
        },
        "output_dir": args.output_dir,
        "saved_files": ["gibbs_temperature.dat", "thermal_expansion.dat"],
    }

    with open(os.path.join(args.output_dir, "qha_results.json"), "w") as f:
        json.dump(recursive_tolist(summary), f, indent=4)

    logger.info(f"QHA calculation completed. Results saved to {args.output_dir}")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Calculate QHA thermal properties with MLIPs"
    )
    parser.add_argument("--structure", required=True, help="Path to structure file")
    parser.add_argument(
        "--model_type",
        required=True,
        choices=["mace", "fairchem", "matgl"],
        help="Model type",
    )
    parser.add_argument("--model_name", default=None, help="Specific model name")
    parser.add_argument(
        "--t_min", type=float, default=0.0, help="Minimum temperature (K)"
    )
    parser.add_argument(
        "--t_max", type=float, default=1000.0, help="Maximum temperature (K)"
    )
    parser.add_argument(
        "--t_step", type=float, default=10.0, help="Temperature step (K)"
    )
    parser.add_argument("--eos", default="vinet", help="Equation of state for QHA")
    parser.add_argument(
        "--fmax",
        type=float,
        default=1e-3,
        help="Force tolerance (eV/A) for the pre-relaxation and the per-volume "
        "relaxations. matcalc's own default of 1e-5 is below what MLIP forces "
        "usually reach and makes QHACalc raise rather than return.",
    )
    parser.add_argument(
        "--max_steps", type=int, default=1000, help="Max relaxation steps per structure"
    )
    parser.add_argument(
        "--volume_window",
        type=float,
        default=None,
        help="Half-width of the sampled volume range as a fraction of the relaxed "
        "volume, e.g. 0.10 for +/-10%% in VOLUME. Default: matcalc's own "
        "scale_factors, which are +/-5%% in LINEAR strain and so -14%%/+16%% in "
        "volume -- the same window atomate2 and phonopy's Si-QHA example use. "
        "Set this only when you need to match someone else's window.",
    )
    parser.add_argument(
        "--n_volumes",
        type=int,
        default=11,
        help="Number of sampled volumes when --volume_window is given (phonopy needs >= 5)",
    )
    parser.add_argument("--output_dir", help="Output directory")
    parser.add_argument("--device", default="auto", help="Device (cpu, cuda, auto)")

    args = parser.parse_args()

    wrapper = load_wrapper(args.model_type, args.model_name, device=args.device)
    atoms = read(args.structure)
    run_qha(args, wrapper, atoms)

    # Save input configs for reproducibility
    from src.utils.config_utils import save_skill_inputs

    save_skill_inputs(args, args.output_dir)
