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
logger = logging.getLogger("LatticeThermalConductivity-Skill")


from src.utils.mlips.loader import load_wrapper

def run_thermal_conductivity(args, wrapper, atoms):
    from matcalc import Phonon3Calc
    
    if not args.output_dir:
        args.output_dir = str(get_current_research_dir() / "vibrational" / "lattice_thermal_conductivity")
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

    # Parse supercell matrix for 3rd order force constant
    if args.supercell_matrix_3rd:
        try:
            if isinstance(args.supercell_matrix_3rd, str):
                s_matrix_3rd = json.loads(args.supercell_matrix_3rd)
            else:
                s_matrix_3rd = args.supercell_matrix_3rd
        except Exception:
             s_matrix_3rd = s_matrix
    else:
        s_matrix_3rd = s_matrix

    thermal_conductivity_calc = Phonon3Calc(
        calculator=calc,
        fc2_supercell=s_matrix,
        fc3_supercell=s_matrix_3rd,
        mesh_numbers=args.mesh_numbers,
        t_min=args.t_min,
        t_max=args.t_max,
        t_step=args.t_step,
        write_phonon3=os.path.join(args.output_dir, "phonon3.yaml"),
    )
    
    logger.info("Starting lattice thermal conductivity calculation...")
    result = thermal_conductivity_calc.calc(atoms)

    def get_T_idx(temp_array, t):
        return np.argmin(np.abs(np.array(temp_array) - t))
    
    # Get all kappa files in hdf5 format
    # kappa_files = [f.name for f in list(Path(args.output_dir).glob('kappa-m*.hdf5'))]
    
    summary = {
        "thermal_conductivity_summary": {
            "temp_300K": result["thermal_conductivity"][get_T_idx(result["temperatures"], 300)]
            if "thermal_conductivity" in result else "N/A",
            "temp_100K": result["thermal_conductivity"][get_T_idx(result["temperatures"], 100)]
            if "thermal_conductivity" in result else "N/A",
        },
        "output_dir": args.output_dir,
        "saved_files": ["phonon3.yaml"] # + kappa_files
    }
    
    with open(os.path.join(args.output_dir, "lattice_thermal_conductivity_results.json"), "w") as f:
        json.dump(recursive_tolist(summary), f, indent=4)
        
    logger.info(f"Lattice thermal conductivity calculation completed. Results saved to {args.output_dir}")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Calculate lattice thermal conductivity using MLIPs")
    parser.add_argument("--structure", required=True, help="Path to structure file")
    parser.add_argument("--model_type", required=True, choices=["mace", "fairchem", "matgl"], help="Model type")
    parser.add_argument("--model_name", default=None, help="Specific model name")
    parser.add_argument("--supercell_matrix", help="Supercell matrix for 2nd order force constant (JSON string, e.g. [[2,0,0],[0,2,0],[0,0,2]])")
    parser.add_argument("--supercell_matrix_3rd", help="Supercell matrix for 3rd order force constant (JSON string, e.g. [[2,0,0],[0,2,0],[0,0,2]])")
    parser.add_argument("--mesh_numbers", type=int, nargs=3, default=[5, 5, 5], help="Mesh numbers for 3rd order force constant")
    parser.add_argument("--t_min", type=float, default=0.0, help="Minimum temperature (K)")
    parser.add_argument("--t_max", type=float, default=1000.0, help="Maximum temperature (K)")
    parser.add_argument("--t_step", type=float, default=10.0, help="Temperature step (K)")
    parser.add_argument("--output_dir", help="Output directory")
    parser.add_argument("--device", default="auto", help="Device (cpu, cuda, auto)")
    
    args = parser.parse_args()
    
    wrapper = load_wrapper(args.model_type, args.model_name, device=args.device)
    atoms = read(args.structure)
    run_thermal_conductivity(args, wrapper, atoms)

    # Save input configs for reproducibility
    from src.utils.config_utils import save_skill_inputs
    save_skill_inputs(args, args.output_dir)


