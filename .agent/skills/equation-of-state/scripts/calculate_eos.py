"""
Calculate equation of state (EOS) using Machine Learning Interatomic Potentials.

This script computes the energy-volume relationship by applying volumetric strains,
fits the Birch-Murnaghan equation of state, and extracts bulk modulus and equilibrium volume.

Usage:
    python calculate_eos.py --structure Si.cif --model_type mace --output_dir eos_results

Requirements:
    - Conda environment: mace-agent, matgl-agent, or fairchem-agent
    - Required packages: ase, matcalc, pymatgen
"""

import argparse
import os
import sys
import json
import logging
from typing import Dict, Any, Optional
from pathlib import Path

# Add project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../"))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.utils.serialization_utils import recursive_tolist
from src.utils.research_utils import get_current_research_dir
from ase.io import read, write
import numpy as np

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger("EOS-Skill")


def load_wrapper(model_type: str, model_name: Optional[str] = None, device: str = "auto"):
    """
    Load the appropriate MLIP wrapper.
    
    Args:
        model_type: Type of model ('mace', 'fairchem', 'matgl')
        model_name: Specific model name (optional, uses default if None)
        device: Device to use ('auto', 'cpu', 'cuda')
        
    Returns:
        Loaded MLIP wrapper instance
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
    logger.info(f"Loaded {model_type} model: {wrapper.model_name}")
    return wrapper


def run_eos(args, wrapper, atoms):
    """
    Run equation of state calculation.
    
    Args:
        args: Parsed command-line arguments
        wrapper: MLIP wrapper instance
        atoms: ASE Atoms object
        
    Returns:
        Dictionary with EOS results
    """
    from matcalc import EOSCalc
    
    if not args.output_dir:
        args.output_dir = str(get_current_research_dir() / "mechanical" / "eos")
    os.makedirs(args.output_dir, exist_ok=True)
    
    calc = wrapper.create_calculator()
    
    logger.info(f"Starting EOS calculation with {args.n_points} points, ±{args.max_abs_strain*100}% strain")
    
    eos_calc = EOSCalc(
        calculator=calc,
        n_points=args.n_points,
        max_abs_strain=args.max_abs_strain,
        relax_structure=args.relax_structure,
        fmax=args.fmax,
        max_steps=args.max_steps
    )
    
    result = eos_calc.calc(atoms)
    
    # Extract key results - MatCalc EOSCalc may use different key names
    # Common keys: b0_GPa (bulk modulus), v0 (equilibrium volume), e0 (equilibrium energy)
    logger.info(f"Available result keys: {list(result.keys())}")
    
    bulk_modulus = result.get("bulk_modulus_bm")
    equilibrium_volume = result.get("volume")
    equilibrium_energy = result.get("energy")
    r2_score = result.get("r2_score_bm")
    
    if bulk_modulus is not None:
        logger.info(f"Bulk modulus: {bulk_modulus:.2f} GPa")
    if equilibrium_volume is not None:
        logger.info(f"Equilibrium volume: {equilibrium_volume:.4f} ų")
    if equilibrium_energy is not None:
        logger.info(f"Equilibrium energy: {equilibrium_energy:.6f} eV")
    if r2_score is not None:
        logger.info(f"R² fit score: {r2_score:.6f}")
    
    # Save energy-volume data
    if "volumes" in result and "energies" in result:
        data_file = os.path.join(args.output_dir, "energies_volumes.dat")
        with open(data_file, "w") as f:
            f.write("# Volume (ų)    Energy (eV)\n")
            for v, e in zip(result["volumes"], result["energies"]):
                f.write(f"{v:12.6f}  {e:16.8f}\n")
        logger.info(f"Saved energy-volume data to {data_file}")
    
    # Create summary
    summary = {
        "bulk_modulus_GPa": bulk_modulus,
        "equilibrium_volume_A3": equilibrium_volume,
        "equilibrium_energy_eV": equilibrium_energy,
        "r2_score": r2_score,
        "n_points": args.n_points,
        "max_abs_strain": args.max_abs_strain,
        "output_dir": args.output_dir,
        "model_type": args.model_type,
        "model_name": wrapper.model_name
    }
    
    # Save results
    results_file = os.path.join(args.output_dir, "eos_results.json")
    with open(results_file, "w") as f:
        json.dump(recursive_tolist(summary), f, indent=4)
        
    logger.info(f"EOS calculation completed. Results saved to {args.output_dir}")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Calculate equation of state with MLIPs",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument("--structure", required=True, help="Path to structure file (CIF, POSCAR, etc.)")
    parser.add_argument("--model_type", required=True, choices=["mace", "fairchem", "matgl"], 
                       help="MLIP type")
    parser.add_argument("--model_name", default=None, help="Specific model name (optional)")
    parser.add_argument("--n_points", type=int, default=11, 
                       help="Number of strain points")
    parser.add_argument("--max_abs_strain", type=float, default=0.1, 
                       help="Maximum absolute volumetric strain (0.1 = ±10%%)")
    parser.add_argument("--relax_structure", action="store_true", default=True,
                       help="Relax atomic positions at each strain point")
    parser.add_argument("--fmax", type=float, default=0.1, 
                       help="Force convergence tolerance (eV/Å)")
    parser.add_argument("--max_steps", type=int, default=500,
                       help="Maximum relaxation steps")
    parser.add_argument("--output_dir", help="Output directory")
    parser.add_argument("--device", default="auto", help="Device (cpu, cuda, auto)")
    
    args = parser.parse_args()
    
    wrapper = load_wrapper(args.model_type, args.model_name, device=args.device)
    atoms = read(args.structure)
    
    logger.info(f"Input structure: {args.structure}")
    logger.info(f"Formula: {atoms.get_chemical_formula()}")
    logger.info(f"Number of atoms: {len(atoms)}")
    
    run_eos(args, wrapper, atoms)
