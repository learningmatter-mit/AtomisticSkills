"""
CLI tool for generating ordered structures from disordered starting points.

Usage:
    python run_ordering.py disordered.cif --n_structures 50 --output_dir ordered_results
"""

import argparse
import os
import sys
import logging
from pathlib import Path
from ase.io import read

# Add project root to path for imports
project_root = Path(__file__).parents[4].absolute()
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from order_disorder_sampler import OrderDisorderSampler

def setup_logging(output_dir: str = None):
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        logging.basicConfig(
            level=logging.INFO,
            format=log_format,
            handlers=[
                logging.FileHandler(os.path.join(output_dir, "ordering.log")),
                logging.StreamHandler(sys.stdout)
            ]
        )
    else:
        logging.basicConfig(level=logging.INFO, format=log_format)

def run_ordering():
    parser = argparse.ArgumentParser(description="Generate ordered structures from disordered input.")
    parser.add_argument("input", help="Path to the disordered structure file (CIF/POSCAR)")
    parser.add_argument("--n_structures", type=int, default=100, help="Number of ordered structures to generate")
    parser.add_argument("--target_atoms", type=int, default=50, help="Target number of atoms per structure after supercell expansion")
    parser.add_argument("--include_perturbation", type=int, default=1, help="Number of perturbations per ordered structure")
    parser.add_argument("--perturbation_length", type=float, default=0.1, help="Length of random displacements (A)")
    parser.add_argument("--output_dir", default="ordered_results", help="Directory to save ordered structures")

    args = parser.parse_args()
    
    setup_logging(args.output_dir)
    logger = logging.getLogger("RunOrdering")
    
    logger.info(f"Loading disordered structure from {args.input}")
    try:
        atoms = read(args.input)
    except Exception as e:
        logger.error(f"Failed to read input file: {e}")
        sys.exit(1)
    
    sampler = OrderDisorderSampler(
        atoms=atoms,
        n_structures=args.n_structures,
        target_atoms=args.target_atoms,
        include_perturbation=args.include_perturbation,
        perturbation_length=args.perturbation_length
    )
    
    structures = sampler.sample(output_dir=args.output_dir)
    
    # Save results
    os.makedirs(args.output_dir, exist_ok=True)
    for i, struct in enumerate(structures):
        fname = os.path.join(args.output_dir, f"ordered_{i}.cif")
        struct.write(fname)
    
    logger.info(f"Successfully generated {len(structures)} structures in {args.output_dir}")

    # Save input configs for reproducibility
    from src.utils.config_utils import save_skill_inputs
    save_skill_inputs(args, args.output_dir)

if __name__ == "__main__":
    run_ordering()
