
import os
import argparse
import logging
import json
import numpy as np
from pathlib import Path
from ase.io import read, write
from sklearn.metrics import mean_squared_error
from sklearn.model_selection import KFold
import sys

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def parse_args():
    parser = argparse.ArgumentParser(description="Iterative Cluster Expansion Training")
    parser.add_argument("primordial_structure", help="Path to the primordial disordered structure (CIF/POSCAR)")
    parser.add_argument("--iterations", type=int, default=5, help="Number of iterations")
    parser.add_argument("--n_samples", type=int, default=50, help="Number of samples per iteration")
    parser.add_argument("--mlip_model", default="mace", choices=["mace", "chgnet", "m3gnet"], help="MLIP model to use for relaxation")
    parser.add_argument("--temperature", type=float, default=1000, help="MC temperature for sampling")
    parser.add_argument("--output_dir", default="iterative_ce_results", help="Output directory")
    return parser.parse_args()

def relax_structures(structures, mlip_model, output_dir):
    """
    Relax structures using the specified MLIP model.
    This function handles the environment switching/subprocess calls.
    """
    # Construct command to run relaxation using dedicated wrapper script
    relax_script = Path("/home/bdeng/projects/AtomisticSkills/.agent/skills/disordered-material/scripts/relax_wrapper.py")
    
    # Determine python executable for mace-agent
    python_exe = "/home/bdeng/miniforge3/envs/mace-agent/bin/python"
    
    cmd = [
        python_exe, str(relax_script),
        "--input_dir", str(relax_input_dir),
        "--output_dir", str(relax_output_dir),
        "--model", mlip_model
    ]
    
    import subprocess
    logger.info(f"Running relaxation: {' '.join(cmd)}")
    ret = subprocess.run(cmd, capture_output=True, text=True)
    
    if ret.returncode != 0:
        logger.error(f"Relaxation failed: {ret.stderr}")
        print(ret.stdout) # Print stdout for debugging
        return []
        
    # Read back results
    relaxed_atoms = []
    # wrapper saves with same basename
    # MACEWrapper saves as .xyz (extxyz) or .json depending on implementation. 
    # MACEWrapper.relax_structure typically saves as .xyz or .cif depending on source?
    # Actually MACEWrapper relax_structure implementation saves as .xyz by default or preserves extension?
    # Let's check potential output files.
    
    # Check for both .cif and .xyz files in output dir
    import glob
    found_files = list(relax_output_dir.glob("*"))
    logger.info(f"Found {len(found_files)} files in output dir")
    
    # We iterate over input_paths to maintain order if possible, but relax wrapper might change names slightly?
    # Typically name is preserved.
    for p in input_paths:
        basename = os.path.basename(p)
        # Try finding the file with likely extensions
        stem = Path(basename).stem
        candidates = [relax_output_dir / basename, relax_output_dir / f"{stem}.xyz", relax_output_dir / f"{stem}.extxyz"]
        
        found = False
        for outfile in candidates:
            if outfile.exists():
                try:
                    # Use ASE to read, which supports extxyz and preserves energy/stress
                    atoms = read(str(outfile))
                    relaxed_atoms.append(atoms)
                    found = True
                    break
                except Exception as e:
                    logger.warning(f"Failed to read {outfile}: {e}")
        
        if not found:
            logger.warning(f"Result for {basename} not found.")
            
    return relaxed_atoms

def compute_bic(mse, n_samples, n_features):
    """
    Bayesian Information Criterion (BIC)
    BIC = n * ln(MSE) + k * ln(n)
    Assumes Gaussian errors.
    """
    if mse <= 0: return float('inf')
    return n_samples * np.log(mse) + n_features * np.log(n_samples)

def sweep_cutoffs(structure, entries, supercell_matrix):
    """
    Sweep over 2-body, 3-body, and 4-body cutoffs to find best CE model.
    """
    # 1. Sweep 2-body: 5 to 10 A
    best_2b = 5.0
    best_score = float('inf')
    
    # Define bounds
    two_body_range = np.arange(5.0, 10.5, 1.0)
    
    logger.info("Sweeping 2-body cutoffs...")
    for r2 in two_body_range:
        cutoffs = {2: r2}
        subspace = ClusterSubspace.from_cutoffs(structure, cutoffs=cutoffs, basis='sinusoid', supercell_size="O2-")
        
        # We need to process entries for this subspace
        # This is expensive, but necessary for sweeping
        try:
            wrangler = StructureWrangler(subspace)
            for entry in entries:
                wrangler.add_entry(entry, verbose=False) # Suppress warnings
            
            if len(wrangler.entries) < 10: continue

            # Fit and Evaluate
            feature_matrix = wrangler.feature_matrix
            energies = wrangler.get_property_vector("energy")
            
            from sklearn.linear_model import LassoCV
            # Use LassoCV for robust CV score inside the sweep
            model = LassoCV(cv=5, n_jobs=1) # 5-fold CV
            model.fit(feature_matrix, energies)
            
            # Metric: CV MSE? Or BIC on full fit? 
            # User asked for "CV score and some redundancy metrics like BIC".
            # LassoCV optimizes alpha based on CV.
            # We can use the MSE of the best alpha path.
            mse = np.min(model.mse_path_.mean(axis=1)) # Mean MSE across folds for best alpha
            
            # Compute BIC using number of non-zero coefficients
            n_features = np.sum(model.coef_ != 0)
            n_samples = len(energies)
            bic = compute_bic(mse, n_samples, n_features)
            
            # Combined score? Or just BIC?
            # Let's trust BIC for "redundancy" penalty.
            score = bic
            
            logger.info(f"2-body={r2:.1f}: MSE={mse:.5f}, k={n_features}, BIC={bic:.2f}")
            
            if score < best_score:
                best_score = score
                best_2b = r2
        except Exception as e:
            logger.warning(f"Sweep failed for 2-body={r2}: {e}")
            
    logger.info(f"Best 2-body cutoff: {best_2b:.1f}")

    # 2. Sweep 3-body: 4.0 to best_2b
    best_3b = None
    best_score_3 = best_score # Compare against 2-body only model
    
    three_body_range = np.arange(4.0, best_2b + 0.1, 1.0)
    logger.info(f"Sweeping 3-body cutoffs (range 4.0 - {best_2b})...")
    
    for r3 in three_body_range:
        cutoffs = {2: best_2b, 3: r3}
        # ... (Duplicate logic, consider helper function if time, but linear flow is fine)
        try:
            subspace = ClusterSubspace.from_cutoffs(structure, cutoffs=cutoffs, basis='sinusoid', supercell_size="O2-")
            wrangler = StructureWrangler(subspace)
            for entry in entries: wrangler.add_entry(entry, verbose=False)
            if len(wrangler.entries) < 10: continue

            feature_matrix = wrangler.feature_matrix
            energies = wrangler.get_property_vector("energy")
            model = LassoCV(cv=5, n_jobs=1)
            model.fit(feature_matrix, energies)
            mse = np.min(model.mse_path_.mean(axis=1))
            n_features = np.sum(model.coef_ != 0)
            bic = compute_bic(mse, len(energies), n_features)
            
            logger.info(f"3-body={r3:.1f}: MSE={mse:.5f}, k={n_features}, BIC={bic:.2f}")
            
            if bic < best_score_3: # Use BIC to decide
                best_score_3 = bic
                best_3b = r3
        except Exception: pass

    final_cutoffs = {2: best_2b}
    if best_3b:
        final_cutoffs[3] = best_3b
        logger.info(f"Best 3-body cutoff: {best_3b:.1f}")
    else:
        logger.info("Adding 3-body did not improve BIC.")

    # 3. Sweep 4-body: 3.0 to best_3b
    if best_3b:
        best_4b = None
        best_score_4 = best_score_3
        four_body_range = np.arange(3.0, best_3b + 0.1, 1.0)
        
        logger.info(f"Sweeping 4-body cutoffs (range 3.0 - {best_3b})...")
        for r4 in four_body_range:
            cutoffs = {2: best_2b, 3: best_3b, 4: r4}
            try:
                subspace = ClusterSubspace.from_cutoffs(structure, cutoffs=cutoffs, basis='sinusoid', supercell_size="O2-")
                wrangler = StructureWrangler(subspace)
                for entry in entries: wrangler.add_entry(entry, verbose=False)
                if len(wrangler.entries) < 10: continue

                feature_matrix = wrangler.feature_matrix
                energies = wrangler.get_property_vector("energy")
                model = LassoCV(cv=5, n_jobs=1)
                model.fit(feature_matrix, energies)
                mse = np.min(model.mse_path_.mean(axis=1))
                n_features = np.sum(model.coef_ != 0)
                bic = compute_bic(mse, len(energies), n_features)
                
                logger.info(f"4-body={r4:.1f}: MSE={mse:.5f}, k={n_features}, BIC={bic:.2f}")

                if bic < best_score_4:
                    best_score_4 = bic
                    best_4b = r4
            except Exception: pass
            
        if best_4b:
            final_cutoffs[4] = best_4b
            logger.info(f"Best 4-body cutoff: {best_4b:.1f}")
        else:
            logger.info("Adding 4-body did not improve BIC.")

    logger.info(f"Final determined cutoffs: {final_cutoffs}")
    
    # Return final wrangler fitted with these cutoffs
    subspace = ClusterSubspace.from_cutoffs(structure, cutoffs=final_cutoffs, basis='sinusoid', supercell_size="O2-")
    wrangler = StructureWrangler(subspace)
    for entry in entries:
        wrangler.add_entry(entry, verbose=False)
    return wrangler, subspace


def main():
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(exist_ok=True)
    
    # 1. Initialize Sampler & Smol wrapper
    try:
        from smol.cofe import ClusterSubspace, StructureWrangler, ClusterExpansion
        from smol.moca import Ensemble, Sampler
        from pymatgen.core import Structure
        from pymatgen.io.ase import AseAtomsAdaptor
        
        # Add local scripts to path to import OrderDisorderSampler
        sys.path.append(str(Path(__file__).parent))
        from order_disorder_sampler import OrderDisorderSampler
    except ImportError:
        logger.error("Failed to import smol or local modules. Make sure you are in the 'smol-agent' environment.")
        return

    prim_structure = Structure.from_file(args.primordial_structure)
    all_entries = [] # Master list of entries
    expansion = None # Hold reference to latest expansion
    
    # Initial Pool Generation
    logger.info("Generating initial pool of structures...")
    sampler = OrderDisorderSampler(prim_structure, n_structures=args.n_samples)
    initial_pool = sampler.sample(output_dir=str(output_dir / "initial_pool"))
    
    # Store the supercell matrix used for sampling
    sc_matrix = sampler.supercell_matrix
    if sc_matrix is None:
        logger.warning("Sampler supercell matrix not found. Mapping might fail.")
    else:
        logger.info(f"Using supercell matrix from sampler: {sc_matrix.tolist()}")
    
    # Iteration Loop
    for iteration in range(args.iterations):
        logger.info(f"=== Iteration {iteration+1}/{args.iterations} ===")
        
        # 1. Relax Pool
        relaxed_structures = relax_structures(initial_pool, args.mlip_model, output_dir / f"iter_{iteration}")
        
        # 2. Check Mapping & Add to Entries
        added_count = 0
        for atoms in relaxed_structures:
            struct = AseAtomsAdaptor.get_structure(atoms)
            try:
                # Check if it maps to valid correlation
                subspace_check = ClusterSubspace.from_cutoffs(prim_structure, cutoffs={2: 5.0}, supercell_size="O2-")
                corr = subspace_check.corr_from_structure(struct, scmatrix=sc_matrix)
                
                # Compute energy 
                energy = atoms.get_potential_energy()
                
                from pymatgen.entries.computed_entries import ComputedStructureEntry
                c_entry = ComputedStructureEntry(struct, energy)
                all_entries.append(c_entry)
                added_count += 1
            except Exception as e:
                logger.warning(f"Failed to map structure: {e}")
                
        logger.info(f"Added {added_count} structures. Total pool: {len(all_entries)}")
        
        if len(all_entries) < 10:
             logger.warning(f"Not enough data to train CE (have {len(all_entries)}). Skipping fit.")
             continue
             
        # 3. Sweep Cutoffs and Select Best Model
        wrangler, subspace = sweep_cutoffs(prim_structure, all_entries, sc_matrix)
        
        # Fit final model with LassoCV for error reporting and getting coefficients
        from sklearn.linear_model import LassoCV
        feature_matrix = wrangler.feature_matrix
        energies = wrangler.get_property_vector("energy")
        
        model = LassoCV(cv=5) 
        model.fit(feature_matrix, energies)
        
        # Define expansion for this iteration
        expansion = ClusterExpansion(subspace, coefficients=model.coef_)
        
        # Report Metrics
        mse = np.min(model.mse_path_.mean(axis=1))
        rmse = np.sqrt(mse)
        n_feat = np.sum(model.coef_ != 0)
        logger.info(f"Iteration {iteration} Final Model: CV-RMSE={rmse:.4f} eV/prim, Features={n_feat}")
        
        # 4. Run MC & Active Learning
        # Setup Ensemble
        sc_matrix_mc = np.diag([2, 2, 2]) # Example supercell for MC
        ensemble = Ensemble.from_cluster_expansion(expansion, supercell_matrix=sc_matrix_mc)
        
        mc_sampler = Sampler.from_ensemble(ensemble, temperature=args.temperature)
        mc_sampler.run(steps=10000)
        
        # 5. Coverage Check
        samples = mc_sampler.samples
        new_candidates = []
        
        occus = samples.get_occupancies(flat=True)
        unique_occus = np.unique(occus, axis=0)
        
        initial_pool = [] # Reset for next batch
        found_new = 0
        
        # Compute features for training set to compare against
        train_features = feature_matrix # Already computed
        
        for occu in unique_occus:
            if len(initial_pool) >= args.n_samples: break
            
            # Check if this occu exists in training data
            feat = ensemble.compute_feature_vector(occu)
            
            # Dist to training
            dists = np.linalg.norm(train_features - feat, axis=1)
            if np.min(dists) > 1e-4:
                # It's new!
                struct = ensemble.processor.structure_from_occupancy(occu)
                initial_pool.append(AseAtomsAdaptor.get_atoms(struct))
                found_new += 1
                
        logger.info(f"Found {found_new} new configurations from MC coverage check.")
        
        if found_new == 0:
            logger.info("Convergence reached! No new structures found.")
            break
            
    # Save final CE
    if expansion:
        expansion.save(str(output_dir / "final_cluster_expansion.json"))
        logger.info("Saved final Cluster Expansion.")
    else:
        logger.warning("No expansion created, nothing to save.")
    
    all_entries = []
    
    # Initial Pool Generation
    
    # Initial Pool Generation
    logger.info("Generating initial pool of structures...")
    sampler = OrderDisorderSampler(prim_structure, n_structures=args.n_samples)
    sampler = OrderDisorderSampler(prim_structure, n_structures=args.n_samples)
    initial_pool = sampler.sample(output_dir=str(output_dir / "initial_pool"))
    
    # Store the supercell matrix used for sampling
    sc_matrix = sampler.supercell_matrix
    if sc_matrix is None:
        # Fallback if accessed before sample (unlikley) or if not set?
        # It should be set after sample()
        logger.warning("Sampler supercell matrix not found. Mapping might fail.")
    else:
        logger.info(f"Using supercell matrix from sampler: {sc_matrix.tolist()}")
    
    # Iteration Loop
    for iteration in range(args.iterations):

        logger.info(f"=== Iteration {iteration+1}/{args.iterations} ===")
        
        # 1. Relax Pool
        relaxed_structures = relax_structures(initial_pool, args.mlip_model, output_dir / f"iter_{iteration}")
        
        # 2. Check Mapping & Add to Wrangler
        added_count = 0
        for atoms in relaxed_structures:
            struct = AseAtomsAdaptor.get_structure(atoms)
            try:
                # Check if it maps to valid correlation
                # Pass the explicit supercell matrix to avoid StructureMatcher guessing issues
                corr = subspace.corr_from_structure(struct, scmatrix=sc_matrix)
                # Compute energy (dummy extraction, assuming 'energy' or 'free_energy' in info/calc)
                # For ASE atoms read from file, energy might be in get_potential_energy() if saved correctly
                # or we need to parse it. 
                # The relax script above uses write(..., atoms), which nicely preserves results in extxyz/json, 
                # but might be tricky in CIF. CIF usually doesn't store energy.
                # Let's update relax script to save as .xyz or .json/traj for energy preservation.
                # Just assuming 'energy' property for now.
                energy = atoms.get_potential_energy()
                
                # Check if configuration changed (optional but requested)
                # We need the initial unrelaxed structure to compare.
                # Using 'info' to track provenance would be good.
                
                entry = {"structure": struct, "energy": energy} 
                # In real usage, use ComputedStructureEntry
                from pymatgen.entries.computed_entries import ComputedStructureEntry
                c_entry = ComputedStructureEntry(struct, energy)
                wrangler.add_entry(c_entry)
                added_count += 1
            except Exception as e:
                logger.warning(f"Failed to map structure: {e}")
                
        logger.info(f"Added {added_count} structures to training set.")
        
        if added_count == 0 and len(wrangler.entries) == 0:
            logger.warning("No structures available for training. Skipping iteration.")
            continue

        # 3. Train CE
        if len(wrangler.entries) < 10:
             logger.warning(f"Not enough data to train CE (have {len(wrangler.entries)}). Skipping fit.")
             continue
             
        # 3. Sweep Cutoffs and Select Best Model
        # We need to preserve the entries and re-initialize the wrangler with best cutoffs
        current_entries = wrangler.entries
        wrangler, subspace = sweep_cutoffs(prim_structure, current_entries, sc_matrix)
        
        # Fit final model with LassoCV for error reporting
        from sklearn.linear_model import LassoCV
        
        feature_matrix = wrangler.feature_matrix
        energies = wrangler.get_property_vector("energy")
        
        model = LassoCV(cv=5) # 5-fold CV
        model.fit(feature_matrix, energies)
        
        # Report Metrics
        mse = np.min(model.mse_path_.mean(axis=1))
        rmse = np.sqrt(mse)
        n_feat = np.sum(model.coef_ != 0)
        
        logger.info(f"Iteration {iteration} Final Model: CV-RMSE={rmse:.4f} eV/prim, Features={n_feat}")
        
        # 4. Run MC & Active Learning
        # Setup Ensemble
        sc_matrix = np.diag([2, 2, 2]) # Example supercell
        ensemble = Ensemble.from_cluster_expansion(expansion, supercell_matrix=sc_matrix)
        
        mc_sampler = Sampler.from_ensemble(ensemble, temperature=args.temperature)
        mc_sampler.run(steps=10000)
        
        # 5. Coverage Check
        # Get sampled structures (unique)
        samples = mc_sampler.samples
        # Extract unique structures from samples?
        # Actually simplest is to just take the final few or random samples
        # and check if their correlation vectors are close to any in feature_matrix
        
        new_candidates = []
        # Get flattened correlations from samples
        sampled_corrs = samples.get_feature_vectors(flat=True)
        # sampled_corrs shape: (n_samples, n_features)
        
        # Check against training set (feature_matrix)
        # We want to find samples where min_dist(sample, train) > threshold
        
        # Logic to pick coverage...
        # For simplicity in this script:
        # Just pick a few random ones and if they are "different" add them.
        # "Different" = dist > 1e-4
        
        # If we find new unique ones, we generate their unrelaxed versions (from occupancy)
        # convert to structure, and add to 'initial_pool' for next iteration
        
        initial_pool = [] # Reset for next batch
        
        # Convert sampled correlations back to structures?
        # Ensembe has processor.structure_from_occupancy(occu)
        
        occus = samples.get_occupancies(flat=True)
        unique_occus = np.unique(occus, axis=0)
        
        found_new = 0
        for occu in unique_occus:
            if len(initial_pool) >= args.n_samples: break
            
            # Check if this occu exists in training data
            # occu -> feature vector
            feat = ensemble.compute_feature_vector(occu)
            
            # Dist to training
            dists = np.linalg.norm(feature_matrix - feat, axis=1)
            if np.min(dists) > 1e-4:
                # It's new!
                struct = ensemble.processor.structure_from_occupancy(occu)
                initial_pool.append(AseAtomsAdaptor.get_atoms(struct))
                found_new += 1
                
        logger.info(f"Found {found_new} new configurations from MC coverage check.")
        
        if found_new == 0:
            logger.info("Convergence reached! No new structures found.")
            break
            
    # Save final CE
    expansion.save(str(output_dir / "final_cluster_expansion.json"))
    logger.info("Saved final Cluster Expansion.")

if __name__ == "__main__":
    main()
