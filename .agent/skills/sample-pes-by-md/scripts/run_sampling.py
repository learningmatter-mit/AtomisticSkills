"""
Unified script for PES sampling using MD-clustering or Order-Disorder methods.

Usage:
    # Off-equilibrium sampling with MatGL (CHGNet)
    python run_sampling.py input.cif --model_type matgl --model_name CHGNet-MatPES-PBE-2025.2.10-2.7M-PES \\
        --total_steps 2000 --temperature 1000 --n_clusters 10 --output_dir results_dir

    # Order-disorder sampling
    python run_sampling.py disordered.cif --sampling_type order_disorder --n_structures 50 --output_dir ordered_dir

Requirements:
    - Conda environment: matgl-agent (for MatGL/CHGNet), mace-agent (for MACE), or base-agent (for Order-Disorder)
    - Required packages: ase, pymatgen, matgl/mace, matcalc
"""

import argparse
import os
import sys
import logging
import numpy as np
from typing import Optional, List, Dict, Any, Tuple
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parents[4].absolute()
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from ase.io import read

# Set MatGL backend
os.environ["MATGL_BACKEND"] = "DGL"

def setup_logging(output_dir: Optional[str] = None):
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        logging.basicConfig(
            level=logging.INFO,
            format=log_format,
            handlers=[
                logging.FileHandler(os.path.join(output_dir, "sampling.log")),
                logging.StreamHandler(sys.stdout)
            ]
        )
    else:
        logging.basicConfig(level=logging.INFO, format=log_format)

def run_sampling():
    parser = argparse.ArgumentParser(description="Sample structures for PES training data augmentation.")
    
    # Arguments
    parser.add_argument("input", help="Path to the initial structure file (CIF/POSCAR)")
    parser.add_argument("--output_dir", default="sampling_results", help="Directory to save sampled structures")
    
    # Off-equilibrium specific
    parser.add_argument("--model_type", choices=["matgl", "mace"], default="matgl", 
                        help="MLIP framework for off-equilibrium sampling")
    parser.add_argument("--model_name", help="Name of the MLIP model to use")
    parser.add_argument("--total_steps", type=int, default=10000, help="Total MD steps for off-equilibrium")
    parser.add_argument("--temperature", type=float, default=1000.0, help="MD temperature in Kelvin")
    parser.add_argument("--n_clusters", type=int, default=20, help="Number of structures to sample/clusters")
    parser.add_argument("--target_atoms", type=int, default=50, help="Target number of atoms for supercell expansion")
    parser.add_argument("--time_step", type=float, help="MD time step in fs (default auto-detected)")

    args = parser.parse_args()
    
    setup_logging(args.output_dir)
    logger = logging.getLogger("RunSampling")
    
    logger.info(f"Loading structure from {args.input}")
    atoms = read(args.input)
    
    from feature_calculators import MatGLCrystalFeatureCalculator, MaceCrystalFeatureCalculator
    from sampler import OffEquilibriumSampler
    
    logger.info(f"Starting off-equilibrium sampling using {args.model_type} ({args.model_name})")
    
    # 1. Setup Wrapper and Calculator
    if args.model_type == "matgl":
        from src.utils.mlips.matgl.matgl_wrapper import MatGLWrapper
        model_name = args.model_name or "CHGNet-MatPES-PBE-2025.2.10-2.7M-PES"
        wrapper = MatGLWrapper(model_name=model_name, device="auto")
        wrapper.load()
        pes_calc = wrapper.create_calculator()
        calc = MatGLCrystalFeatureCalculator(potential=pes_calc)
    else: # mace
        from src.utils.mlips.mace.mace_wrapper import MACEWrapper
        model_name = args.model_name or "MACE-OMAT-0-small"
        wrapper = MACEWrapper(model_name=model_name, device="auto")
        wrapper.load()
        pes_calc = wrapper.create_calculator()
        calc = MaceCrystalFeatureCalculator(mace_calculator=pes_calc)
        
    # 2. Run Sampler
    sampler = OffEquilibriumSampler(
        calculator=calc,
        atoms=atoms,
        total_steps=args.total_steps,
        temperature=args.temperature,
        n_clusters=args.n_clusters,
        output_dir=args.output_dir,
        target_atoms=args.target_atoms,
        time_step=args.time_step
    )
    
    structures, metadata = sampler.sample()
    logger.info(f"Sampling completed. Metadata: {metadata}")

if __name__ == "__main__":
    run_sampling()
