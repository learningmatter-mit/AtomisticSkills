"""
Run Grand Canonical Monte Carlo (GCMC) sweep over chemical potentials.

This script performs systematic Grand Canonical Monte Carlo simulations across
a range of chemical potentials and temperatures to map composition-temperature
phase diagrams for alloy systems.

Usage:
    python run_gcmc_sweep.py \\
        --ce_file cluster_expansion.json \\
        --supercell 3 3 3 \\
        --temperatures 400 600 800 \\
        --mu_min -0.3 --mu_max 0.3 --num_mu_points 15 \\
        --steps 50000 --equilibration_steps 10000 \\
        --element Ag \\
        --output_dir gcmc_results/

Requirements:
    - Conda environment: smol-agent
    - Required packages: smol, pymatgen, numpy
"""

import os
import sys
import json
import argparse
import numpy as np
from pathlib import Path
from typing import List, Dict, Any, Tuple

# Add project root to path
try:
    project_root = Path(__file__).resolve().parents[4]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
except Exception:
    pass

from smol.cofe import ClusterExpansion
from smol.moca import Ensemble, Sampler
from pymatgen.core import Structure


def run_gcmc_single_point(
    ce: ClusterExpansion,
    supercell_matrix: List[List[int]],
    temperature: float,
    chemical_potential: float,
    element: str,
    steps: int,
    equilibration_steps: int,
    trajectory_file: str = None
) -> Dict[str, Any]:
    """
    Run a single GCMC simulation at specified T and μ.
    
    Args:
        ce: Cluster expansion model
        supercell_matrix: Supercell size (3x3 list)
        temperature: Temperature in Kelvin
        chemical_potential: Chemical potential in eV
        element: Element species to control (e.g., "Ag")
        steps: Total MC steps
        equilibration_steps: Burn-in steps to discard
        trajectory_file: Optional HDF5 file to save trajectory
        
    Returns:
        Dictionary with composition, energy, and convergence data
    """
    # Get all species from the cluster expansion
    # For binary alloys, we need to specify both elements
    prim = ce.cluster_subspace.structure
    all_species = set()
    for site in prim:
        for sp in site.species:
            if not str(sp).lower().startswith('vac'):  # Skip vacancies
                all_species.add(str(sp))
    
    all_species = sorted(list(all_species))  # Sort for consistency
    
    # Build chemical potential dict: set controlled element to mu, others to 0
    chem_pots = {}
    for sp in all_species:
        if sp == element:
            chem_pots[sp] = chemical_potential
        else:
            chem_pots[sp] = 0.0  # Reference species
    
    # Create ensemble with chemical potentials
    ensemble = Ensemble.from_cluster_expansion(
        ce,
        supercell_matrix=supercell_matrix,
        chemical_potentials=chem_pots
    )
    
    # Create sampler with flip moves (semigrand canonical)
    sampler = Sampler.from_ensemble(
        ensemble,
        temperature=temperature,
        step_type='flip'
    )
    
    # Generate initial random occupancy
    from smol.capp.generate import generate_random_ordered_occupancy
    num_sites = ensemble.processor.num_sites
    initial_occu = np.zeros(num_sites, dtype=int)  # Start with all zeros (first species)
    
    # Run equilibration without saving
    print(f"  Equilibration: {equilibration_steps} steps...")
    sampler.run(equilibration_steps, initial_occupancies=initial_occu, thin_by=1)
    
    # Get last occupancy from equilibration to use as start for production
    # This ensures continuity even if clear_samples() affects state
    last_occu = sampler.samples.get_occupancies(flat=True)[-1]
    
    # Clear equilibration samples
    sampler.clear_samples()
    
    # Configure trajectory saving
    run_kwargs = {"thin_by": max(1, steps // 1000)}  # Save ~1000 samples
    if trajectory_file:
        run_kwargs["stream_file"] = trajectory_file
        run_kwargs["stream_chunk"] = 1
        run_kwargs["keep_last_chunk"] = True
    
    print(f"  Production: {steps} steps...")
    sampler.run(steps, initial_occupancies=last_occu, **run_kwargs)
    
    # Analyze results
    samples = sampler.samples
    
    if len(samples.get_occupancies()) == 0:
        return {"error": "No samples collected"}
    
    # Get occupancies and structures
    occupancies = samples.get_occupancies(flat=False)  # (nsamples, nwalkers, nsites)
    
    # Extract final structure and composition
    final_occu = occupancies[-1, 0, :]
    final_structure = ensemble.processor.structure_from_occupancy(final_occu)
    
    # Calculate mean composition and energy from production run
    compositions = []
    energies = []
    
    for i in range(len(occupancies)):
        occu = occupancies[i, 0, :]
        struct = ensemble.processor.structure_from_occupancy(occu)
        
        # Get composition of controlled element
        comp = struct.composition
        total_sites = len(struct)
        element_count = comp.get(element, 0)
        mole_fraction = element_count / total_sites
        compositions.append(mole_fraction)
        
        # Get energy using processor
        energy = ensemble.processor.compute_property(occu)
        energies.append(energy / total_sites)  # Energy per atom

    
    mean_composition = float(np.mean(compositions))
    std_composition = float(np.std(compositions))
    mean_energy = float(np.mean(energies))
    std_energy = float(np.std(energies))
    
    return {
        "temperature": temperature,
        "chemical_potential": chemical_potential,
        "element": element,
        "mean_composition": mean_composition,
        "std_composition": std_composition,
        "mean_energy": mean_energy,
        "std_energy": std_energy,
        "final_structure": final_structure.as_dict(),
        "num_samples": len(compositions)
    }


def main():
    parser = argparse.ArgumentParser(
        description="Run Grand Canonical Monte Carlo chemical potential sweep"
    )
    parser.add_argument(
        "--ce_file",
        type=str,
        required=True,
        help="Path to cluster expansion JSON file"
    )
    parser.add_argument(
        "--supercell",
        type=int,
        nargs=3,
        default=[3, 3, 3],
        help="Supercell size (e.g., 3 3 3)"
    )
    parser.add_argument(
        "--temperatures",
        type=float,
        nargs='+',
        required=True,
        help="List of temperatures in Kelvin (e.g., 400 600 800)"
    )
    parser.add_argument(
        "--mu_min",
        type=float,
        required=True,
        help="Minimum chemical potential in eV"
    )
    parser.add_argument(
        "--mu_max",
        type=float,
        required=True,
        help="Maximum chemical potential in eV"
    )
    parser.add_argument(
        "--num_mu_points",
        type=int,
        default=20,
        help="Number of chemical potential points to sample"
    )
    parser.add_argument(
        "--steps",
        type=int,
        default=50000,
        help="Number of MC production steps per point"
    )
    parser.add_argument(
        "--equilibration_steps",
        type=int,
        default=10000,
        help="Number of equilibration (burn-in) steps"
    )
    parser.add_argument(
        "--element",
        type=str,
        required=True,
        help="Element to control chemical potential (e.g., 'Ag')"
    )
    parser.add_argument(
        "--output_dir",
        type=str,
        default="gcmc_results",
        help="Output directory for results"
    )
    parser.add_argument(
        "--save_trajectories",
        action="store_true",
        help="Save HDF5 trajectory files (can be large)"
    )
    
    args = parser.parse_args()
    
    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Load cluster expansion
    print(f"\n{'='*60}")
    print(f"Loading cluster expansion from: {args.ce_file}")
    ce = ClusterExpansion.load(args.ce_file)
    print(f"  Number of clusters: {len(ce.cluster_subspace)}")
    print(f"  Controlled element: {args.element}")
    
    # Create supercell matrix
    sc_matrix = np.diag(args.supercell).tolist()
    print(f"  Supercell: {args.supercell}")
    
    # Generate chemical potential points
    mu_values = np.linspace(args.mu_min, args.mu_max, args.num_mu_points)
    print(f"  Chemical potential range: {args.mu_min:.3f} to {args.mu_max:.3f} eV")
    print(f"  Number of μ points: {args.num_mu_points}")
    print(f"  Temperatures: {args.temperatures}")
    print(f"{'='*60}\n")
    
    # Run sweeps
    all_results = []
    total_points = len(args.temperatures) * len(mu_values)
    current_point = 0
    
    for temp in args.temperatures:
        print(f"\n{'─'*60}")
        print(f"Temperature: {temp} K")
        print(f"{'─'*60}")
        
        for mu in mu_values:
            current_point += 1
            print(f"\n[{current_point}/{total_points}] T={temp}K, μ={mu:.4f} eV")
            
            # Setup trajectory file if requested
            traj_file = None
            if args.save_trajectories:
                traj_file = str(output_dir / f"T{temp}_mu{mu:.3f}.h5")
            
            # Run simulation
            result = run_gcmc_single_point(
                ce=ce,
                supercell_matrix=sc_matrix,
                temperature=temp,
                chemical_potential=mu,
                element=args.element,
                steps=args.steps,
                equilibration_steps=args.equilibration_steps,
                trajectory_file=traj_file
            )
            
            if "error" not in result:
                print(f"  ✓ Composition: {result['mean_composition']:.4f} ± {result['std_composition']:.4f}")
                print(f"  ✓ Energy: {result['mean_energy']:.4f} ± {result['std_energy']:.4f} eV/atom")
                
                # Save final structure
                final_struct = Structure.from_dict(result["final_structure"])
                cif_path = output_dir / f"T{temp}_mu{mu:.3f}_final.cif"
                final_struct.to(filename=str(cif_path))
                result["structure_file"] = str(cif_path)
                
                # Remove structure dict from results (too large for JSON)
                del result["final_structure"]
                
                all_results.append(result)
            else:
                print(f"  ✗ Error: {result['error']}")
                # If error is critical, better to stop? 
                # But since user wants no try-except, we let python errors crash it.
                # The 'error' key comes from internal logic, not exception.

    
    # Save aggregated results
    results_file = output_dir / "results_summary.json"
    with open(results_file, 'w') as f:
        json.dump({
            "metadata": {
                "ce_file": args.ce_file,
                "element": args.element,
                "supercell": args.supercell,
                "temperatures": args.temperatures,
                "mu_range": [args.mu_min, args.mu_max],
                "num_mu_points": args.num_mu_points,
                "steps": args.steps,
                "equilibration_steps": args.equilibration_steps
            },
            "results": all_results
        }, f, indent=2)
    
    num_success = len(all_results)
    num_total = total_points
    
    print(f"\n{'='*60}")
    if num_success > 0:
        if num_success == num_total:
            print(f"✓ GCMC sweep completed successfully!")
        else:
            print(f"⚠ GCMC sweep completed with some failures.")
    else:
        print(f"✗ GCMC sweep failed. No successful simulations.")
        
    print(f"  Success rate: {num_success}/{num_total}")
    print(f"  Results saved to: {results_file}")
    print(f"{'='*60}\n")
    
    if num_success == 0:
        sys.exit(1)

    # Save input configs for reproducibility
    from src.utils.config_utils import save_skill_inputs
    save_skill_inputs(args, args.output_dir)


if __name__ == "__main__":
    main()
