"""
Calculate surface adsorption energies using MatCalc's AdsorptionCalc.

This script calculates adsorption energies for adsorbate-surface combinations
using Machine Learning Interatomic Potentials (MLIPs) via MatCalc's AdsorptionCalc class.

Usage:
    python calculate_adsorption.py \\
        --bulk Cu_bulk.cif \\
        --adsorbate CO.xyz \\
        --miller_index '[1,1,1]' \\
        --model_type mace \\
        --model_name MACE-OMAT-0-small \\
        --output_dir results/adsorption

Requirements:
    - Conda environment: mace-agent, matgl-agent, or fairchem-agent
    - Required packages: matcalc, pymatgen, ase, mlip wrapper
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
from ase.io import read
from pymatgen.core import Molecule
import numpy as np

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Adsorption-Skill")


from src.utils.mlips.loader import load_wrapper

def run_adsorption(args, wrapper, bulk_atoms, adsorbate):
    """
    Run adsorption energy calculation using MatCalc's AdsorptionCalc.
    
    Args:
        args: Command-line arguments containing calculation settings
        wrapper: MLIP wrapper (MACEWrapper, MatGLWrapper, or FAIRCHEMWrapper)
        bulk_atoms: ASE Atoms object for bulk structure
        adsorbate: Pymatgen Molecule object for adsorbate
        
    Returns:
        Summary dictionary with adsorption energies and site information
    """
    from matcalc import AdsorptionCalc
    
    # Setup output directory
    if not args.output_dir:
        args.output_dir = str(get_current_research_dir() / "adsorption")
    os.makedirs(args.output_dir, exist_ok=True)
    
    # Create calculator from wrapper
    calc = wrapper.create_calculator()
    
    # Parse Miller index
    miller_index = json.loads(args.miller_index) if isinstance(args.miller_index, str) else args.miller_index
    miller_index = tuple(miller_index)
    
    logger.info(f"Miller index: {miller_index}")
    logger.info(f"Bulk structure: {bulk_atoms.get_chemical_formula()}, {len(bulk_atoms)} atoms")
    logger.info(f"Adsorbate: {adsorbate.composition.formula}")
    
    # Initialize AdsorptionCalc
    ads_calc = AdsorptionCalc(
        calculator=calc,
        relax_adsorbate=args.relax_adsorbate,
        relax_slab=args.relax_slab,
        relax_bulk=args.relax_bulk,
        fmax=args.fmax,
        optimizer=args.optimizer,
        max_steps=args.max_steps
    )
    
    logger.info("Starting adsorption calculation...")
    logger.info(f"Settings: relax_bulk={args.relax_bulk}, relax_slab={args.relax_slab}, relax_adsorbate={args.relax_adsorbate}")
    logger.info(f"Convergence: fmax={args.fmax} eV/Å, max_steps={args.max_steps}")
    
    # Run calculation using calc_adslabs
    # This returns a list of results for different adsorption sites
    results_list = ads_calc.calc_adslabs(
        adsorbate=adsorbate,
        bulk=bulk_atoms,
        miller_index=miller_index,
        min_slab_size=args.min_slab_size,
        min_vacuum_size=args.min_vacuum_size,
        adsorption_sites=args.adsorption_sites,
        height=args.height,
        dry_run=False
    )
    
    logger.info(f"Calculation completed. Found {len(results_list)} adsorption configurations")
    
    # Process results
    adsorption_energies = []
    for i, result in enumerate(results_list):
        ads_energy = result.get("adsorption_energy", None)
        site_info = result.get("site", "unknown")
        if ads_energy is not None:
            adsorption_energies.append({
                "site_index": i,
                "site": str(site_info),
                "adsorption_energy": float(ads_energy),
                "adslab_energy": result.get("adslab_energy", None),
                "slab_energy": result.get("slab_energy", None),
                "adsorbate_energy": result.get("adsorbate_energy", None)
            })
            logger.info(f"  Site {i}: E_ads = {ads_energy:.3f} eV")
    
    # Find most stable site
    if adsorption_energies:
        min_energy_site = min(adsorption_energies, key=lambda x: x["adsorption_energy"])
        logger.info(f"Most stable site: {min_energy_site['site']} with E_ads = {min_energy_site['adsorption_energy']:.3f} eV")
    
    # Create summary
    summary = {
        "miller_index": list(miller_index),
        "bulk_formula": bulk_atoms.get_chemical_formula(),
        "adsorbate_formula": adsorbate.composition.formula,
        "num_sites": len(adsorption_energies),
        "adsorption_sites": adsorption_energies,
        "most_stable_site": min_energy_site if adsorption_energies else None,
        "calculation_settings": {
            "relax_bulk": args.relax_bulk,
            "relax_slab": args.relax_slab,
            "relax_adsorbate": args.relax_adsorbate,
            "fmax": args.fmax,
            "max_steps": args.max_steps,
            "min_slab_size": args.min_slab_size,
            "min_vacuum_size": args.min_vacuum_size
        },
        "output_dir": args.output_dir
    }
    
    # Save JSON summary
    output_file = os.path.join(args.output_dir, "adsorption_results.json")
    with open(output_file, "w") as f:
        json.dump(recursive_tolist(summary), f, indent=4)
    
    logger.info(f"Results saved to {output_file}")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Calculate surface adsorption energies using MLIPs and MatCalc"
    )
    
    # Required arguments
    parser.add_argument("--bulk", required=True, 
                       help="Path to bulk structure file (CIF, POSCAR, etc.)")
    parser.add_argument("--adsorbate", required=True, 
                       help="Path to adsorbate molecule file (XYZ, CIF) or SMILES string")
    parser.add_argument("--miller_index", required=True, 
                       help="Miller index as JSON list, e.g. '[1,1,1]'")
    parser.add_argument("--model_type", required=True, 
                       choices=["mace", "fairchem", "matgl"],
                       help="Type of MLIP model to use")
    
    # Optional model and calculation settings
    parser.add_argument("--model_name", default=None, 
                       help="Specific model name (uses default for model_type if not provided)")
    parser.add_argument("--relax_bulk", action="store_true", default=True,
                       help="Relax bulk structure (default: True)")
    parser.add_argument("--no_relax_bulk", dest="relax_bulk", action="store_false",
                       help="Do not relax bulk structure")
    parser.add_argument("--relax_slab", action="store_true", default=True,
                       help="Relax clean slab structure (default: True)")
    parser.add_argument("--no_relax_slab", dest="relax_slab", action="store_false",
                       help="Do not relax slab structure")
    parser.add_argument("--relax_adsorbate", action="store_true", default=True,
                       help="Relax adsorbate molecule (default: True)")
    parser.add_argument("--no_relax_adsorbate", dest="relax_adsorbate", action="store_false",
                       help="Do not relax adsorbate")
    
    # Convergence settings
    parser.add_argument("--fmax", type=float, default=0.05, 
                       help="Force convergence criterion in eV/Å (default: 0.05)")
    parser.add_argument("--optimizer", default="BFGS", 
                       help="ASE optimizer to use (default: BFGS)")
    parser.add_argument("--max_steps", type=int, default=500, 
                       help="Maximum optimization steps (default: 500)")
    
    # Slab generation settings
    parser.add_argument("--min_slab_size", type=float, default=10.0,
                       help="Minimum slab thickness in Å (default: 10.0)")
    parser.add_argument("--min_vacuum_size", type=float, default=20.0,
                       help="Minimum vacuum layer size in Å (default: 20.0)")
    parser.add_argument("--adsorption_sites", default="all",
                       help="Adsorption sites to consider: 'all', 'ontop', 'bridge', 'hollow' (default: all)")
    parser.add_argument("--height", type=float, default=0.9,
                       help="Initial height of adsorbate above surface in Å (default: 0.9)")
    
    # Output settings
    parser.add_argument("--output_dir", help="Output directory (auto-generated if not provided)")
    parser.add_argument("--device", default="auto", 
                       help="Device for computation: 'cpu', 'cuda', or 'auto' (default: auto)")
    
    args = parser.parse_args()
    
    # Load MLIP wrapper
    wrapper = load_wrapper(args.model_type, args.model_name, device=args.device)
    
    # Load bulk structure
    bulk_atoms = read(args.bulk)
    logger.info(f"Loaded bulk structure from {args.bulk}")
    
    # Load adsorbate (support both file and SMILES)
    if os.path.exists(args.adsorbate):
        try:
            adsorbate = Molecule.from_file(args.adsorbate)
            logger.info(f"Loaded adsorbate from file: {args.adsorbate}")
        except Exception as e:
            logger.error(f"Failed to load adsorbate from file: {e}")
            sys.exit(1)
    else:
        # Try as SMILES string
        try:
            from pymatgen.io.babel import BabelMolAdaptor
            adaptor = BabelMolAdaptor.from_string(args.adsorbate, "smi")
            adsorbate = adaptor.pymatgen_mol
            logger.info(f"Created adsorbate from SMILES: {args.adsorbate}")
        except Exception as e:
            logger.error(f"Failed to parse adsorbate as SMILES or file: {e}")
            sys.exit(1)
    
    # Run calculation
    run_adsorption(args, wrapper, bulk_atoms, adsorbate)

    # Save input configs for reproducibility
    from src.utils.config_utils import save_skill_inputs
    save_skill_inputs(args, args.output_dir)
