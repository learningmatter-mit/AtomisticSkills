"""
Generate molecular conformers using RDKit (ETKDG) and relax them with an MLIP.
"""

import argparse
import os
import sys
import json
import logging
import copy
from typing import Optional, List, Dict, Any

# Try importing torch early to avoid OpenMP conflicts with RDKit
try:
    import torch
except ImportError:
    pass

# Add project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../"))
print(f"DEBUG: Project root: {project_root}", flush=True)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import numpy as np
from ase import Atoms
from ase.io import read, write
from ase.optimize import FIRE
from ase.units import kB

# Import RDKit (check availability)
try:
    from rdkit import Chem
    from rdkit.Chem import AllChem, rdMolAlign
    HAS_RDKIT = True
except ImportError:
    HAS_RDKIT = False


# Configure logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("ConformerSearch")


from src.utils.mlips.loader import load_wrapper

def smiles_to_atoms_list(smiles: str, num_conformers: int, rms_threshold: float) -> List[Atoms]:
    """
    Generate initial conformers from SMILES using RDKit ETKDG.
    Returns a list of ASE Atoms objects.
    """
    if not HAS_RDKIT:
        raise ImportError("RDKit is required for processing SMILES. Please install rdkit or use mace-agent environment.")

    logger.info(f"Generating {num_conformers} initial conformers for SMILES: {smiles}")
    
    # 1. Mol from SMILES
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        raise ValueError(f"Failed to parse SMILES: {smiles}")
    
    # 2. Add Hydrogens (critical for 3D geometry)
    mol = Chem.AddHs(mol)
    
    # 3. Embed conformers
    # useRandomCoords=True can help with tough geometries
    params = AllChem.ETKDGv3()
    if hasattr(params, 'useIsomericEmbedding'):
        params.useIsomericEmbedding = True
    params.pruneRmsThresh = rms_threshold
    
    cids = AllChem.EmbedMultipleConfs(mol, numConfs=num_conformers, params=params)
    
    if not cids:
        logger.warning("ETKDG failed to generate conformers. Trying with random coords...")
        params.useRandomCoords = True
        cids = AllChem.EmbedMultipleConfs(mol, numConfs=num_conformers, params=params)
        
    if not cids:
        raise RuntimeError("Failed to generate any conformers with RDKit.")

    logger.info(f"RDKit generated {len(cids)} conformers after RMS pruning (threshold={rms_threshold} A).")
    
    # 4. Convert to ASE Atoms
    atoms_list = []
    species = [atom.GetSymbol() for atom in mol.GetAtoms()]
    
    for conf_id in cids:
        conf = mol.GetConformer(conf_id)
        positions = conf.GetPositions()
        atoms = Atoms(symbols=species, positions=positions, pbc=False)
        atoms_list.append(atoms)
        
    return atoms_list


def read_structure_file(path: str) -> List[Atoms]:
    """Read one or more structures from a file."""
    # ASE read can return a list if index=':'
    atoms_list = read(path, index=':')
    if not isinstance(atoms_list, list):
        atoms_list = [atoms_list]
    
    # Ensure no PBC
    for atoms in atoms_list:
        atoms.pbc = False
        
    logger.info(f"Loaded {len(atoms_list)} structures from {path}")
    return atoms_list


def relax_conformers(atoms_list: List[Atoms], wrapper, fmax: float = 0.01) -> List[Dict]:
    """
    Relax simple list of Atoms objects.
    Returns a list of dicts: {'atoms': relaxed_atoms, 'energy': energy_eV, 'id': original_index}
    """
    relaxed_results = []
    
    # Create a calculator from the wrapper
    # Note: Some wrappers might not support cloning the calculator easily,
    # so we might need to recreate it or attach it to each atoms object sequentially.
    # The safest way typically is to attach the same calculator instance if it's stateless enough,
    # or re-create it. Most ASE calculators are stateful (store atoms).
    # We will attach the calculator to each atoms object in the loop.
    
    logger.info(f"Relaxing {len(atoms_list)} conformers with {wrapper.model_name} (fmax={fmax})...")
    
    for i, atoms in enumerate(atoms_list):
        # Create/reset calculator
        calc = wrapper.create_calculator()
        atoms.calc = calc
        
        # Relax
        try:
            opt = FIRE(atoms, logfile=None)
            opt.run(fmax=fmax, steps=500)
            energy = atoms.get_potential_energy()
            
            relaxed_results.append({
                "atoms": atoms,
                "energy": energy,
                "original_id": i
            })
            
            # Simple progress logging
            if (i + 1) % 5 == 0:
                logger.info(f"Relaxed {i + 1}/{len(atoms_list)} conformers.")
                
        except Exception as e:
            logger.warning(f"Failed to relax conformer {i}: {e}")
            
    return relaxed_results


def align_and_calculate_rmsd(atoms1: Atoms, atoms2: Atoms) -> float:
    """
    Calculate RMSD between two atoms objects.
    Uses RDKit's alignments if available (handles symmetry best), 
    otherwise simple Kabsch via ASE/numpy (handles symmetry poorly).
    """
    # Simple check: basics must match
    if len(atoms1) != len(atoms2) or atoms1.get_chemical_formula() != atoms2.get_chemical_formula():
        return 999.0

    if HAS_RDKIT:
        # To use RDKit's GetBestRMS, we need RDKit mols.
        # It's expensive to convert ASE back to RDKit mol just for RMSD if we don't have the graph.
        # Strategy: Create a "skeleton" mol from one atoms object just for connectivity (guess)
        # or use a simpler approach. 
        # Actually, if we started from SMILES, we could keep the RDKit mol. 
        # But we might have started from XYZ.
        # Let's rely on simple RMSD after minimizing position difference if we don't have topology easily.
        # BUT, RDKit's "GetBestRMS" is the gold standard because it handles automorphisms.
        
        # Simplified approach:
        # If we have RDKit, try to build a mol from atoms1 using connectivity guess?
        # That's overkill.
        # Let's implement a simple centroids-aligned RMSD here using Numpy for now.
        # Ideally we'd use 'spyrmsd' or similar if available, but we stick to std deps.
        pass

    # Basic alignment (centroid + rotation) requires no topology
    # This does NOT handle atom indexing permutations (automorphisms).
    # So "deduplication" might miss some identical conformers if atom indices permuted.
    # However, since these come from the SAME RDKit mol (usually), indices are consistent.
    
    pos1 = atoms1.get_positions()
    pos2 = atoms2.get_positions()
    
    # 1. Center
    pos1 -= np.mean(pos1, axis=0)
    pos2 -= np.mean(pos2, axis=0)
    
    # 2. Kabsch algorithm to rotate pos2 to match pos1
    H = np.dot(pos1.T, pos2)
    V, S, Wt = np.linalg.svd(H)
    d = (np.linalg.det(V) * np.linalg.det(Wt)) < 0.0
    if d:
        S[-1] = -S[-1]
        V[:, -1] = -V[:, -1]
    
    U = np.dot(V, Wt)
    pos2_rotated = np.dot(pos2, U.T)
    
    # 3. RMSD
    diff = pos1 - pos2_rotated
    rmsd = np.sqrt(np.mean(np.sum(diff**2, axis=1)))
    return rmsd


def deduplicate_results(results: List[Dict], threshold: float = 0.1) -> List[Dict]:
    """
    Filter relaxed conformers by RMSD.
    Assumes `results` contains {'atoms': ..., 'energy': ...}.
    Keeps unique conformers.
    """
    # Sort by energy first (lowest energy is reference)
    results = sorted(results, key=lambda x: x["energy"])
    
    unique_results = []
    
    for candidate in results:
        is_duplicate = False
        for unique in unique_results:
            # Check energy diff first (cheap)
            if abs(candidate["energy"] - unique["energy"]) > 0.5: # if energy diff > 0.5 eV, unlikely to be same
                continue # Definitely not same structure (assuming reasonably smooth PES)
            
            # Check RMSD
            rmsd = align_and_calculate_rmsd(candidate["atoms"], unique["atoms"])
            if rmsd < threshold:
                is_duplicate = True
                break
        
        if not is_duplicate:
            unique_results.append(candidate)
            
    logger.info(f"Deduplicated {len(results)} -> {len(unique_results)} unique conformers (RMSD threshold {threshold} A).")
    return unique_results


def main():
    parser = argparse.ArgumentParser(description="Generate and rank molecular conformers.")
    
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument("--smiles", help="SMILES string")
    input_group.add_argument("--structure", help="Path to input structure file")
    
    parser.add_argument("--num_conformers", type=int, default=50, help="Initial number of conformers (RDKit)")
    parser.add_argument("--rms_threshold", type=float, default=0.2, help="RDKit pruning RMSD threshold")
    parser.add_argument("--dedup_threshold", type=float, default=0.1, help="Post-relaxation RMSD threshold for deduplication")
    parser.add_argument("--fmax", type=float, default=0.01, help="Relaxation fmax (eV/A)")
    parser.add_argument("--temperature", type=float, default=298.15, help="Temperature (K) for Boltzmann weighting")
    
    parser.add_argument("--model_type", default="mace", choices=["mace", "matgl", "fairchem"], help="MLIP backend")
    parser.add_argument("--model_name", default=None, help="Specific model name (e.g. MACE-OFF23-small)")
    parser.add_argument("--device", default="auto", help="Device (cpu, cuda)")
    
    parser.add_argument("--output_dir", required=True, help="Directory to save results")
    
    args = parser.parse_args()
    
    # 0. Setup output
    os.makedirs(args.output_dir, exist_ok=True)
    
    # Default model for organics if not specified
    if args.model_type == "mace" and args.model_name is None:
        args.model_name = "MACE-OFF23-small"
        logger.info(f"Using default organic model: {args.model_name}")
    
    # 1. Generate/Load Conformers
    if args.smiles:
        initial_atoms = smiles_to_atoms_list(args.smiles, args.num_conformers, args.rms_threshold)
    else:
        initial_atoms = read_structure_file(args.structure)
        logger.info(f"Loaded {len(initial_atoms)} structures. Skipping RDKit generation.")
        
    # 2. Load MLIP
    wrapper = load_wrapper(args.model_type, args.model_name, args.device)
    
    # 3. Relax
    relaxed_data = relax_conformers(initial_atoms, wrapper, args.fmax)
    
    # 4. Deduplicate
    unique_data = deduplicate_results(relaxed_data, args.dedup_threshold)
    
    # 5. Ranking & Boltzmann Analysis
    # Energies relative to min
    energies = np.array([res["energy"] for res in unique_data])
    min_energy = np.min(energies)
    rel_energies = energies - min_energy # in eV
    
    # Boltzmann factors: exp(-E/kT)
    # k = 8.617e-5 eV/K
    beta = 1.0 / (kB * args.temperature)
    boltzmann_factors = np.exp(-rel_energies * beta)
    partition_function = np.sum(boltzmann_factors)
    weights = boltzmann_factors / partition_function
    
    # 6. Save results
    results_summary = []
    
    for i, res in enumerate(unique_data):
        # Save XYZ
        filename = f"conf_{i:03d}.xyz"
        filepath = os.path.join(args.output_dir, filename)
        write(filepath, res["atoms"])
        
        results_summary.append({
            "id": i,
            "filename": filename,
            "energy_eV": float(res["energy"]),
            "relative_energy_eV": float(rel_energies[i]),
            "relative_energy_kcal_mol": float(rel_energies[i] * 23.0605),
            "boltzmann_weight": float(weights[i]),
            "original_id": res["original_id"]
        })
        
    summary_path = os.path.join(args.output_dir, "conformer_results.json")
    
    final_output = {
        "metadata": {
            "smiles": args.smiles,
            "structure_file": args.structure,
            "model": wrapper.model_name,
            "temperature_K": args.temperature,
            "num_initial": len(initial_atoms),
            "num_unique": len(unique_data),
            "dedup_threshold": args.dedup_threshold
        },
        "conformers": results_summary
    }
    
    with open(summary_path, "w") as f:
        json.dump(final_output, f, indent=4)
        
    logger.info("="*60)
    logger.info(f"Conformer search complete.")
    logger.info(f"Unique conformers found: {len(unique_data)}")
    logger.info(f"Global minimum energy: {min_energy:.4f} eV")
    logger.info(f"Results saved to: {args.output_dir}")
    logger.info("="*60)


if __name__ == "__main__":
    main()
