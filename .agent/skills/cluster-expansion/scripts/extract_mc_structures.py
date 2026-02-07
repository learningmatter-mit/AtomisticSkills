
import os
import argparse
import numpy as np
import json
from smol.moca import SampleContainer
from pymatgen.core import Structure
from tqdm import tqdm

def main():
    parser = argparse.ArgumentParser(description="Extract structures from MC trajectory")
    parser.add_argument("--trajectory_file", type=str, required=True, help="Path to MC trajectory file (HDF5)")
    parser.add_argument("--cluster_expansion", type=str, required=True, help="Path to Cluster Expansion file (JSON)")
    parser.add_argument("--output_dir", type=str, required=True, help="Directory to save extracted CIFs")
    parser.add_argument("--num_structures", type=int, default=20, help="Number of structures to extract")
    parser.add_argument("--strategy", type=str, default="random", choices=["random", "last", "stride", "low_energy"], help="Extraction strategy")
    parser.add_argument("--stride", type=int, default=1, help="Stride for 'stride' strategy")
    
    args = parser.parse_args()
    
    print(f"Loading trajectory from {args.trajectory_file}...")
    try:
        container = SampleContainer.from_hdf5(args.trajectory_file)
    except Exception as e:
        print(f"Error loading trajectory: {e}")
        # Try loading as JSON/Monty if HDF5 fails (just in case)
        try:
            from monty.serialization import loadfn
            container = loadfn(args.trajectory_file)
        except Exception as e2:
            print(f"Error loading as JSON: {e2}")
            return

    # To convert occupancies to structures, we need the processor from the ensemble
    # The container usually has the ensemble attached if loaded from HDF5
    processor = None
    if hasattr(container, "ensemble") and container.ensemble is not None:
        try:
            processor = container.ensemble.processor
        except Exception as e:
            print(f"Warning: Could not get processor from container ensemble: {e}")

    if processor is None:
        print("Attempting to load processor from Cluster Expansion file...")
        try:
            from smol.cofe import ClusterExpansion
            from smol.moca import Ensemble
            ce = ClusterExpansion.load(args.cluster_expansion)
            
            # We need the supercell matrix to create a compatible processor
            # Try to infer from the first occupancy size? 
            # This is tricky without metadata. 
            # For now, let's assume the container metadata might verify this or we fail.
            # But wait, if container doesn't have ensemble, maybe we can't easily reconstruct 
            # without knowing the supercell size used.
            
            # Fallback: Create a processor for the PRIMITIVE cell (might not work for supercells)
            # ce.cluster_subspace is for primitive.
            # We need an Ensemble for the supercell.
            
            print("Error: Container does not have an attached Ensemble. "
                  "Structure reconstruction from raw CE without knowing supercell matrix is not yet implemented.")
            return
            
        except Exception as e:
            print(f"Error loading Cluster Expansion: {e}")
            return

    occupancies = container.get_occupancies(flat=False)
    energies = container.get_energies(flat=False)
    
    n_walkers, n_samples, n_sites = occupancies.shape
    total_samples = n_walkers * n_samples
    print(f"Traj: {n_walkers} walkers, {n_samples} samples. Total: {total_samples}")
    
    # Flattening indices for selection logic
    indices = []
    if args.strategy == "random":
        indices = np.random.choice(total_samples, min(total_samples, args.num_structures), replace=False)
    elif args.strategy == "last":
        indices = np.arange(total_samples - min(total_samples, args.num_structures), total_samples)
    elif args.strategy == "stride":
        indices = np.arange(0, total_samples, args.stride)
        if args.num_structures and len(indices) > args.num_structures:
             indices = indices[:args.num_structures]
    elif args.strategy == "low_energy":
        # Flatten energies for sorting
        flat_energies = energies.flatten()
        sorted_indices = np.argsort(flat_energies)
        indices = sorted_indices[:min(total_samples, args.num_structures)]
        
    print(f"Extracting {len(indices)} structures...")
    
    os.makedirs(args.output_dir, exist_ok=True)
    
    extracted_info = []
    
    for i, idx in enumerate(tqdm(indices)):
        # Map flat index back to walker/sample
        w_idx = idx // n_samples
        s_idx = idx % n_samples
        
        occu = occupancies[w_idx, s_idx]
        energy = energies[w_idx, s_idx]
        
        try:
            # Generate structure
            struct = processor.structure_from_occupancy(occu)
            
            # Filename
            fname = f"mc_sample_{idx}.cif"
            fpath = os.path.join(args.output_dir, fname)
            struct.to(fmt="cif", filename=fpath)
            
            extracted_info.append({
                "filename": fname,
                "energy": float(energy),
                "sample_index": int(idx),
                "path": fpath
            })
        except Exception as e:
            print(f"Failed to generate structure for index {idx}: {e}")
            
    # Save info json
    with open(os.path.join(args.output_dir, "extracted_structures.json"), "w") as f:
        json.dump(extracted_info, f, indent=2)
        
    print(f"Done. Extracted {len(extracted_info)} structures to {args.output_dir}")

if __name__ == "__main__":
    main()
