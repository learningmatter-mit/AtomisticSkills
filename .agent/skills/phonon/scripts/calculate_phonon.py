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
logger = logging.getLogger("Phonon-Skill")


def load_wrapper(model_type: str, model_name: Optional[str] = None, device: str = "auto"):
    """
    Load the appropriate model wrapper.
    """
    model_type = model_type.lower()
    
    if model_type == "mace":
        from src.utils.mlips.mace.mace_wrapper import MACEWrapper
        model_name = model_name or "MACE-OMAT-0-small"
        wrapper = MACEWrapper(model_name=model_name, device=device)
    elif model_type == "fairchem":
        from src.utils.mlips.fairchem.fairchem_wrapper import FAIRCHEMWrapper
        model_name = model_name or "uma-s-1p1"
        wrapper = FAIRCHEMWrapper(model_name=model_name, device=device)
    elif model_type == "matgl":
        from src.utils.mlips.matgl.matgl_wrapper import MatGLWrapper
        model_name = model_name or "CHGNet-MatPES-PBE-2025.2.10-2.7M-PES"
        wrapper = MatGLWrapper(model_name=model_name, device=device)
    else:
        raise ValueError(f"Unknown model type: {model_type}. Supported: mace, fairchem, matgl")
        
    wrapper.load()
    return wrapper


def run_phonon(args, wrapper, atoms):
    from matcalc import PhononCalc
    
    if not args.output_dir:
        args.output_dir = str(get_current_research_dir() / "vibrational" / "phonon")
    os.makedirs(args.output_dir, exist_ok=True)
    
    calc = wrapper.create_calculator()
    
    # Parse supercell matrix
    if args.supercell_matrix:
        try:
            if isinstance(args.supercell_matrix, str):
                s_matrix = json.loads(args.supercell_matrix)
            else:
                s_matrix = args.supercell_matrix
        except Exception:
             s_matrix = [[2, 0, 0], [0, 2, 0], [0, 0, 2]]
    else:
        s_matrix = [[2, 0, 0], [0, 2, 0], [0, 0, 2]]

    phonon_calc = PhononCalc(
        calculator=calc,
        supercell_matrix=s_matrix,
        t_step=args.t_step,
        t_max=args.t_max,
        t_min=args.t_min,
        write_phonon=os.path.join(args.output_dir, "phonon.yaml"),
        write_band_structure=os.path.join(args.output_dir, "band_structure.yaml"),
        write_total_dos=os.path.join(args.output_dir, "total_dos.dat")
    )
    
    logger.info("Starting phonon calculation...")
    result = phonon_calc.calc(atoms)
    
    summary = {
        "thermal_properties_summary": {
            "temp_300K": {k: v[30] if len(v) > 30 else v[-1] for k, v in result.get("thermal_properties", {}).items() if isinstance(v, (list, np.ndarray))} 
            if "thermal_properties" in result else "N/A"
        },
        "output_dir": args.output_dir,
        "saved_files": ["phonon.yaml", "band_structure.yaml", "total_dos.dat"]
    }
    
    with open(os.path.join(args.output_dir, "phonon_results.json"), "w") as f:
        json.dump(recursive_tolist(summary), f, indent=4)
        
    logger.info(f"Phonon calculation completed. Results saved to {args.output_dir}")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Calculate phonon properties with MLIPs")
    parser.add_argument("--structure", required=True, help="Path to structure file")
    parser.add_argument("--model_type", required=True, choices=["mace", "fairchem", "matgl"], help="Model type")
    parser.add_argument("--model_name", default=None, help="Specific model name")
    parser.add_argument("--supercell_matrix", help="Supercell matrix (JSON string, e.g. [[2,0,0],[0,2,0],[0,0,2]])")
    parser.add_argument("--t_min", type=float, default=0.0, help="Minimum temperature (K)")
    parser.add_argument("--t_max", type=float, default=1000.0, help="Maximum temperature (K)")
    parser.add_argument("--t_step", type=float, default=10.0, help="Temperature step (K)")
    parser.add_argument("--output_dir", help="Output directory")
    parser.add_argument("--device", default="auto", help="Device (cpu, cuda, auto)")
    
    args = parser.parse_args()
    
    wrapper = load_wrapper(args.model_type, args.model_name, device=args.device)
    atoms = read(args.structure)
    run_phonon(args, wrapper, atoms)
