import argparse
import os
import sys
import json
import matplotlib
matplotlib.use('Agg') # Use non-interactive backend
import matplotlib.pyplot as plt
from pathlib import Path
from ase.io import read, write, Trajectory
from ase.mep import NEBTools, NEB
from ase.optimize import FIRE, BFGS
from itertools import chain
from pymatgen.core import PeriodicSite, Structure
from pymatgen.io.ase import AseAtomsAdaptor

# Add project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../"))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

def generate_path_cif_from_images(images: list, filename: str) -> None:
    """Generate a cif file from a list of image atoms."""
    image_structs = [AseAtomsAdaptor.get_structure(image) for image in images]
    sites = set()
    lattice = image_structs[0].lattice
    sites.update(
        PeriodicSite(site.species, site.frac_coords, lattice) for site in chain(*(struct for struct in image_structs))
    )
    # Sort sites to make some sense of them, though messy
    neb_path = Structure.from_sites(sorted(sites, key=lambda s: (s.species_string, s.frac_coords[0])))
    neb_path.to(filename, "cif")

def load_wrapper(model_type, model_name, device="auto"):
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

def plot_barrier(neb, output_dir):
    """
    Plot the NEB barrier using ASE NEBTools.
    """
    try:
        images = neb.images
        neb_tools = NEBTools(images)
        
        # Plot band
        fig = neb_tools.plot_band()
        fig.savefig(os.path.join(output_dir, "neb_barrier_plot.png"), dpi=300)
        plt.close(fig)
        
    except Exception as e:
        print(f"Plotting failed: {e}")

def run_neb(args):
    # Setup output
    os.makedirs(args.output_dir, exist_ok=True)
    
    # Load structures
    initial_ase = read(args.start_structure)
    final_ase = read(args.end_structure)
    
    # Load Wrapper
    wrapper = load_wrapper(args.model_type, args.model_name)
    calc = wrapper.create_calculator()
    
    # --- 1. Path Generation (Interpolation) ---
    print(f"Generating initial path using {args.interpolation} interpolation...")
    
    images = [initial_ase]
    for _ in range(args.n_images):
        images.append(initial_ase.copy())
    images.append(final_ase)
    
    neb = NEB(images, climb=args.climb, allow_shared_calculator=True)
    
    if args.interpolation == 'idpp':
        # IDPP requires internal images to be copies of start/end or linear interpolated first
        # ASE's interpolate('idpp') does a linear interpolation first if positions are same
        neb.interpolate(method='idpp', mic=True)
    else:
        neb.interpolate(method='linear', mic=True)
        
    # --- 2. Attach Calculator ---
    # MLIP models usually handle efficient batching or can be attached to all
    # For wrappers that return a fresh calculator, we might need one per image if not thread-safe/shared
    # But usually one calculator instance attached to all is fine for serial calculation or if calculator handles it.
    # MACE, FairChem, MatGL usually support single calculator instance.
    
    for image in images:
        image.calc = calc
        
    # --- 3. Optimization ---
    print("Starting NEB optimization...")
    
    if args.optimizer.upper() == "BFGS":
        optimizer = BFGS(neb, trajectory=os.path.join(args.output_dir, 'neb.traj'))
    else:
        optimizer = FIRE(neb, trajectory=os.path.join(args.output_dir, 'neb.traj'))
        
    optimizer.run(fmax=args.fmax)
    
    # --- 4. Analysis and Output ---
    
    neb_tools = NEBTools(images)
    barrier = neb_tools.get_barrier()[0]
    
    # Plotting
    plot_barrier(neb, args.output_dir)
    
    # Save Path CIF
    cif_filename = os.path.join(args.output_dir, "neb_path.cif")
    generate_path_cif_from_images(images, cif_filename)
    print(f"Saved NEB path to {cif_filename}")
            
    # Save results
    results = {
        "barrier_eV": barrier,
        "fmax": args.fmax,
        "n_images": args.n_images,
        "climb": args.climb,
        "model": args.model_type,
        "interpolation": args.interpolation
    }
    
    with open(os.path.join(args.output_dir, "neb_results.json"), "w") as f:
        json.dump(results, f, indent=4)
        
    print(f"NEB Calculation Completed. Barrier: {barrier:.4f} eV")
    print(f"Results saved to {args.output_dir}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run NEB Calculation with MLIPs")
    parser.add_argument("--start_structure", required=True, help="Start structure file")
    parser.add_argument("--end_structure", required=True, help="End structure file")
    parser.add_argument("--model_type", required=True, choices=["mace", "fairchem", "matgl"], help="Model type")
    parser.add_argument("--model_name", default=None, help="Specific model name")
    parser.add_argument("--n_images", type=int, default=7, help="Number of intermediate images")
    parser.add_argument("--fmax", type=float, default=0.02, help="Force convergence (eV/A)")
    parser.add_argument("--interpolation", type=str, default="idpp", choices=["linear", "idpp"], help="Interpolation method for initial path.")
    parser.add_argument("--climb", action="store_true", default=True, help="Use Climbing Image NEB")
    parser.add_argument("--optimizer", default="FIRE", help="Optimizer (FIRE, BFGS, etc.)")
    parser.add_argument("--output_dir", required=True, help="Output directory")
    
    args = parser.parse_args()
    
    run_neb(args)
