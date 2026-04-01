"""
Order-Disorder Sampler for generating ordered structures from disordered structures.
"""

import logging
import os
import numpy as np
from typing import List, Optional, Tuple, Dict, Any
from ase import Atoms

logger = logging.getLogger(__name__)

class OrderDisorderSampler:
    """
    Order-Disorder Sampler for generating ordered structures from disordered structures.
    
    Uses pymatgen's OrderDisorderTransformation to generate ordered structures
    from a disordered input structure with fractional occupancies.
    """
    
    def __init__(self, atoms, n_structures: int = 100, target_atoms: int = 50, 
                 include_perturbation: int = 1, perturbation_length: float = 0.1):
        """
        Initialize OrderDisorderSampler.
        
        Args:
            atoms: Initial disordered atomic structure (ASE Atoms or pymatgen Structure)
                   For disordered structures with fractional occupancies, use pymatgen Structure
            n_structures: Number of ordered structures to generate (default: 100)
            target_atoms: Target number of atoms per structure after supercell expansion (default: 50)
            include_perturbation: Number of perturbations per ordered structure (default: 1)
            perturbation_length: Length of random displacement in Angstroms (default: 0.1)
        """
        self.atoms = atoms
        self.n_structures = n_structures
        self.target_atoms = target_atoms
        self.include_perturbation = include_perturbation
        self.perturbation_length = perturbation_length
        self.supercell_matrix = None
    
    def _perturb_structure(self, atoms: Atoms, perturbation_length: float) -> Atoms:
        """
        Apply random perturbation to atomic positions.
        """
        perturbed = atoms.copy()
        # Generate random displacements
        displacements = np.random.normal(0, perturbation_length / 3.0, size=perturbed.positions.shape)
        # Normalize to ensure max displacement is approximately perturbation_length
        max_disp = np.max(np.linalg.norm(displacements, axis=1))
        if max_disp > 0:
            displacements = displacements * (perturbation_length / max_disp) * np.random.random()
        perturbed.positions += displacements
        return perturbed
    
    def sample(self, output_dir: Optional[str] = None) -> List[Atoms]:
        """
        Generate ordered structures from disordered input structure.
        """
        logger.info(f"Starting order-disorder sampling: generating {self.n_structures} ordered structures")

        # Convert atoms to pymatgen Structure if needed
        from pymatgen.io.ase import AseAtomsAdaptor
        from pymatgen.core import Structure as PymatgenStructure
        
        if isinstance(self.atoms, PymatgenStructure):
            pmg_structure = self.atoms
        else:
            adaptor = AseAtomsAdaptor()
            pmg_structure = adaptor.get_structure(self.atoms)

        # Step 1: Expand supercell to target size
        logger.info(f"Step 1: Expanding supercell to target size ({self.target_atoms} atoms)")
        
        current_atoms = len(pmg_structure)
        expansion_factor = (self.target_atoms / current_atoms) ** (1.0 / 3.0)
        
        # Search space: try expansion matrices
        best_exp = None
        best_score = float('inf')
        
        max_expansion = int(expansion_factor * 2) + 2
        max_expansion = min(max_expansion, 6) # Cap to avoid huge search
        for nx in range(1, max_expansion + 1):
            for ny in range(1, max_expansion + 1):
                for nz in range(1, max_expansion + 1):
                    num_atoms = current_atoms * nx * ny * nz
                    if num_atoms < 1: continue
                    
                    # Check stoichiometry consistency
                    valid_stoichiometry = True
                    expansion_factor_int = nx * ny * nz
                    
                    for el, amt in pmg_structure.composition.items():
                        total_amt = amt * expansion_factor_int
                        if abs(total_amt - round(total_amt)) > 1e-3:
                            valid_stoichiometry = False
                            break
                    
                    if not valid_stoichiometry:
                        continue
                    
                    target_dist = abs(num_atoms - self.target_atoms) / self.target_atoms
                    # Prefer cubic-like expansion
                    cubicness = (max(nx, ny, nz) - min(nx, ny, nz)) / max(nx, ny, nz) if max(nx, ny, nz) > 0 else 0.0
                    score = 0.6 * target_dist + 0.4 * cubicness
                    
                    if score < best_score:
                        best_score = score
                        best_exp = (nx, ny, nz)
                        
        if best_exp:
            expanded_pmg = pmg_structure * best_exp
            logger.info(f"Using expansion matrix: {best_exp}")
            self.supercell_matrix = np.diag(best_exp)
        else:
            # Fallback: simple expansion
            nx = ny = nz = max(1, int(round(expansion_factor)))
            expanded_pmg = pmg_structure * (nx, ny, nz)
            self.supercell_matrix = np.diag([nx, ny, nz])
            
        logger.info(f"Expanded supercell has {len(expanded_pmg)} atoms")


        # Persistence: Save disordered supercell immediately
        if output_dir:
            try:
                from pymatgen.io.cif import CifWriter
                disordered_path = os.path.join(output_dir, "disordered_supercell.cif")
                CifWriter(expanded_pmg).write_file(disordered_path)
                logger.info(f"Saved disordered supercell to {disordered_path}")
            except Exception as e:
                logger.warning(f"Failed to save disordered supercell: {e}")
        
        # Step 2: Use pymatgen's OrderDisorderedStructureTransformation
        logger.info(f"Step 2: Performing OrderDisorderedStructureTransformation to generate candidates")
        
        ordered_structures = []
        try:
            from pymatgen.transformations.standard_transformations import OrderDisorderedStructureTransformation
            from pymatgen.analysis.ewald import EwaldMinimizer
            
            transformation = OrderDisorderedStructureTransformation(
                algo=EwaldMinimizer.ALGO_FAST, 
                no_oxi_states=True
            )
            
            n_candidates = max(self.n_structures * 5, 50) 
            ranked_list = transformation.apply_transformation(expanded_pmg, return_ranked_list=n_candidates)
            
            if not isinstance(ranked_list, list):
                ranked_list = [{'structure': ranked_list, 'energy': 0.0}]
            
            logger.info(f"Generated {len(ranked_list)} candidate ordered structures")
            
            # Step 3: Uniform sampling from the ranked list
            if len(ranked_list) <= self.n_structures:
                selected_entries = ranked_list
            else:
                indices = np.linspace(0, len(ranked_list) - 1, self.n_structures, dtype=int)
                indices = np.unique(indices)
                selected_entries = [ranked_list[i] for i in indices]
                
                if len(selected_entries) < self.n_structures:
                    remaining_indices = [i for i in range(len(ranked_list)) if i not in indices]
                    for i in remaining_indices[:self.n_structures - len(selected_entries)]:
                        selected_entries.append(ranked_list[i])

            ordered_structures = [entry['structure'] for entry in selected_entries]
                
        except Exception as e:
            logger.error(f"OrderDisorder transformation failed: {e}")
            logger.info("Attempting fallback with random ordering...")
            try:
                transformation = OrderDisorderedStructureTransformation(
                    algo=EwaldMinimizer.ALGO_FAST,
                    no_oxi_states=True
                ) 
                s = transformation.apply_transformation(expanded_pmg)
                ordered_structures = [s]
            except Exception as e2:
                logger.error(f"Fallback failed: {e2}")
                ordered_structures = []
            
        # Step 4: Convert to ASE and perturbation
        all_sampled_structures = []
        adaptor = AseAtomsAdaptor()
        
        logger.info(f"Step 3: Converting {len(ordered_structures)} structures to ASE")
        
        for i, pmg_struct in enumerate(ordered_structures):
            atoms = adaptor.get_atoms(pmg_struct)
            atoms.info['config_id'] = f"ordered_{i}"
            atoms.info['source'] = "order_disorder"
            all_sampled_structures.append(atoms)
            
            if self.include_perturbation:
                atoms_perturbed = atoms.copy()
                atoms_perturbed.rattle(stdev=self.perturbation_length)
                atoms_perturbed.info['config_id'] = f"ordered_{i}_perturbed"
                all_sampled_structures.append(atoms_perturbed)
                
        logger.info(f"Total structures generated: {len(all_sampled_structures)}")
        return all_sampled_structures
