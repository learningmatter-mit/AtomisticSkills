import argparse
import os
import json
from collections import defaultdict
from rdkit import Chem
from rdkit.Chem import AllChem
from pymatgen.core import Structure, Molecule

from VOID.dockers import BatchDocker, Subdocker
from VOID.samplers import VoronoiClustering
from VOID.fitness import MinDistanceFitness, MultipleFitness
from VOID.utils.structure import get_loading

def prepare_ligand(smiles: str, num_conformers: int, seed: int = 42):
    """Generates 3D conformers for the given SMILES and selects the lowest energy ones."""
    mol = Chem.MolFromSmiles(smiles)
    if not mol:
        raise ValueError(f"Invalid SMILES string: {smiles}")
        
    mol = Chem.AddHs(mol)
    
    # Generate conformers
    cids = AllChem.EmbedMultipleConfs(mol, numConfs=num_conformers*5, randomSeed=seed)
    if not cids:
        print("Failed to embed conformers, trying with different params...")
        cids = AllChem.EmbedMultipleConfs(mol, numConfs=num_conformers*5, useRandomCoords=True, randomSeed=seed)
    
    if not cids:
        raise RuntimeError("Failed to generate any conformers.")
        
    # Optimize with MMFF94
    res = AllChem.MMFFOptimizeMoleculeConfs(mol, numThreads=0)
    
    # Associate energies with conformer IDs
    energies = []
    for i, (not_converged, energy) in enumerate(res):
        energies.append((energy, cids[i]))
        
    # Sort by energy
    energies.sort(key=lambda x: x[0])
    top_cids = [cid for eng, cid in energies[:num_conformers]]
    
    # Convert best conformers to pymatgen molecules
    pymatgen_mols = []
    for cid in top_cids:
        conf = mol.GetConformer(cid)
        species = []
        coords = []
        for idx in range(mol.GetNumAtoms()):
            species.append(mol.GetAtomWithIdx(idx).GetSymbol())
            pos = conf.GetAtomPosition(idx)
            coords.append([pos.x, pos.y, pos.z])
        pymatgen_mols.append(Molecule(species, coords))
        
    return pymatgen_mols, [eng for eng, _ in energies[:num_conformers]]

def main():
    parser = argparse.ArgumentParser(description="Dock a small molecule into a porous material using VOID.")
    parser.add_argument("--smiles", type=str, required=True, help="SMILES string of the guest ligand.")
    parser.add_argument("--host_cif", type=str, required=True, help="Path to the CIF file for the host material.")
    parser.add_argument("--output_dir", type=str, default="docking_output", help="Directory to save docked complexes (CIF format).")
    
    # RDKit parameters
    parser.add_argument("--num_conformers", type=int, default=5, help="Number of lowest energy conformers to test for docking.")
    
    # VOID Docking Hyperparameters
    parser.add_argument("--threshold", type=float, default=1.8, help="MinDistanceFitness threshold for complex.")
    parser.add_argument("--attempts", type=int, default=50, help="Number of attempts for Subdocker.")
    parser.add_argument("--structs_per_loading", type=int, default=2, help="Max structures to keep per molecule loading.")
    parser.add_argument("--num_clusters", type=int, default=5, help="Number of clusters for Voronoi sampler.")
    parser.add_argument("--min_radius", type=float, default=3.0, help="Minimum radius for Voronoi sampler.")
    parser.add_argument("--probe_radius", type=float, default=0.1, help="Probe radius for Voronoi sampler.")
    parser.add_argument("--remove_species", type=str, nargs="*", default=[], help="Species to remove from host before docking.")
    parser.add_argument("--max_loading", type=int, default=20, help="Max loading of guest molecules per host.")
    parser.add_argument("--max_subdock", type=int, default=1, help="Max structures generated per docking run.")

    args = parser.parse_args()
    
    os.makedirs(args.output_dir, exist_ok=True)
    
    # Load and prepare Host
    print(f"Loading host from {args.host_cif}...")
    host = Structure.from_file(args.host_cif)
    if args.remove_species:
        for s in args.remove_species:
            host.remove_species([s])
            
    # Prepare Ligand
    print(f"Preparing up to {args.num_conformers} lowest-energy 3D conformers for {args.smiles}...")
    guest_mols, energies = prepare_ligand(args.smiles, args.num_conformers)
    print(f"Generated {len(guest_mols)} viable conformers.")
        
    # Collect all complexes with their conformer index and guest molecule
    raw_complexes = []  # list of (conformer_idx, guest_mol, complex)
    
    for idx, (guest, eng) in enumerate(zip(guest_mols, energies)):
        print(f"\n--- Docking Conformer {idx+1}/{len(guest_mols)} (Energy: {eng:.2f} kcal/mol) ---")
        
        # Sampler
        sampler = VoronoiClustering(
            num_clusters=args.num_clusters, 
            min_radius=args.min_radius, 
            probe_radius=args.probe_radius
        )
        
        # Fitness functions
        cpxfit = MinDistanceFitness(args.threshold, step=True)
        molfit = MinDistanceFitness(0.8, structure="guest", step=True)
        fitness = MultipleFitness([cpxfit, molfit], [1, 1e-3])
        
        # Dockers
        docker = BatchDocker(host, guest, sampler, fitness=fitness)
        subdocker = Subdocker(docker, args.max_subdock, args.max_loading)
        
        complexes = subdocker.dock(args.attempts)
        print(f"Subdocker generated {len(complexes)} valid poses for this conformer.")
        
        for c in complexes:
            raw_complexes.append((idx, guest, c))
    
    # Group complexes by molecule loading and keep structs_per_loading per group
    loading_groups = defaultdict(list)  # loading_level -> [(conf_idx, complex)]
    for conf_idx, guest_mol, cpx in raw_complexes:
        loading = get_loading(host, guest_mol, cpx.pose)
        loading_groups[loading].append((conf_idx, cpx))
    
    all_complexes = []  # list of (conformer_idx, loading, complex)
    for loading in sorted(loading_groups.keys()):
        group = loading_groups[loading]
        selected = group[:args.structs_per_loading]
        print(f"Loading {loading}: {len(group)} poses found, keeping {len(selected)}.")
        for conf_idx, cpx in selected:
            all_complexes.append((conf_idx, loading, cpx))
    
    print(f"\nExporting {len(all_complexes)} total docked structures...")
    results_metadata = []
    
    for i, (conf_idx, loading, cpx) in enumerate(all_complexes):
        out_name = f"pose_{i+1}_loading_{loading}_conf_{conf_idx+1}.cif"
        out_path = os.path.join(args.output_dir, out_name)
        
        # Saving CIF
        cpx.pose.to(filename=out_path, fmt="cif")
        
        results_metadata.append({
            "pose_id": i+1,
            "filename": out_name,
            "loading": loading,
            "conformer_idx": conf_idx + 1,
            "conformer_energy": energies[conf_idx]
        })
        
    # Save combined output metadata
    with open(os.path.join(args.output_dir, "docking_results.json"), "w") as f:
        json.dump({
            "hyperparameters": vars(args),
            "results": results_metadata
        }, f, indent=4)
        
    print("Docking complete! Results saved to:", args.output_dir)

if __name__ == "__main__":
    main()
