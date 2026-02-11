import argparse
import os
import sys
import json
import logging
from typing import Dict, Any, Optional, Union, List
from pathlib import Path

# Add project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../"))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.utils.serialization_utils import recursive_tolist
from src.utils.research_utils import get_current_research_dir
from ase.io import read
import numpy as np

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("QHA-Skill")


def load_wrapper(model_type: str, model_name: Optional[str] = None, device: str = "auto"):
    """
    Load the appropriate model wrapper.
    """
    model_type = model_type.lower()
    
    if model_type == "mace":
        from src.utils.mlips.mace.mace_wrapper import MACEWrapper
        wrapper = MACEWrapper(model_name=model_name, device=device)
    elif model_type == "fairchem":
        from src.utils.mlips.fairchem.fairchem_wrapper import FAIRCHEMWrapper
        wrapper = FAIRCHEMWrapper(model_name=model_name, device=device)
    elif model_type == "matgl":
        from src.utils.mlips.matgl.matgl_wrapper import MatGLWrapper
        wrapper = MatGLWrapper(model_name=model_name, device=device)
    else:
        raise ValueError(f"Unknown model type: {model_type}. Supported: mace, fairchem, matgl")
        
    wrapper.load()
    return wrapper


def run_qha(args, wrapper, atoms):
    from matcalc import QHACalc
    
    if not args.output_dir:
        args.output_dir = str(get_current_research_dir() / "vibrational" / "qha")
    os.makedirs(args.output_dir, exist_ok=True)
    
    calc = wrapper.create_calculator()
    
    qha_calc = QHACalc(
        calculator=calc,
        t_step=args.t_step,
        t_max=args.t_max,
        t_min=args.t_min,
        eos=args.eos,
        write_gibbs_temperature=os.path.join(args.output_dir, "gibbs_temperature.dat"),
        write_thermal_expansion=os.path.join(args.output_dir, "thermal_expansion.dat")
    )
    
    logger.info("Starting QHA calculation...")
    result = qha_calc.calc(atoms)
    
    summary = {
        "summary": {
            "temp_range": [args.t_min, args.t_max],
            "num_points": len(result.get("temperatures", [])),
            "eos": args.eos
        },
        "output_dir": args.output_dir,
        "saved_files": ["gibbs_temperature.dat", "thermal_expansion.dat"]
    }
    
    with open(os.path.join(args.output_dir, "qha_results.json"), "w") as f:
        json.dump(recursive_tolist(summary), f, indent=4)
        
    logger.info(f"QHA calculation completed. Results saved to {args.output_dir}")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Calculate QHA thermal properties with MLIPs")
    parser.add_argument("--structure", required=True, help="Path to structure file")
    parser.add_argument("--model_type", required=True, choices=["mace", "fairchem", "matgl"], help="Model type")
    parser.add_argument("--model_name", default=None, help="Specific model name")
    parser.add_argument("--t_min", type=float, default=0.0, help="Minimum temperature (K)")
    parser.add_argument("--t_max", type=float, default=1000.0, help="Maximum temperature (K)")
    parser.add_argument("--t_step", type=float, default=10.0, help="Temperature step (K)")
    parser.add_argument("--eos", default="vinet", help="Equation of state for QHA")
    parser.add_argument("--output_dir", help="Output directory")
    parser.add_argument("--device", default="auto", help="Device (cpu, cuda, auto)")
    
    args = parser.parse_args()
    
    wrapper = load_wrapper(args.model_type, args.model_name, device=args.device)
    atoms = read(args.structure)
    run_qha(args, wrapper, atoms)
