"""
Structure sampling methods for MLIP Agent
"""

import logging
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
import tempfile
import os

# Core ASE imports - safe to import at module level
from ase import Atoms
from ase.io import write

logger = logging.getLogger(__name__)

# Try to import dependencies - handle gracefully if not available
# Note: MLIP-specific imports (torch, matgl) should only be used in appropriate conda environments
try:
    from ase.md import MDLogger, VelocityVerlet, Langevin
    from ase.md.nptberendsen import Inhomogeneous_NPTBerendsen, NPTBerendsen
    from ase.md.velocitydistribution import MaxwellBoltzmannDistribution
    from ase.optimize import BFGS
    from ase.constraints import ExpCellFilter
    from ase.calculators.calculator import Calculator
    ASE_MD_AVAILABLE = True
except (ImportError, ValueError, TypeError) as e:
    ASE_MD_AVAILABLE = False
    logger.warning(f"ASE MD modules not available: {e}")
    MDLogger = None
    VelocityVerlet = None
    Langevin = None
    Inhomogeneous_NPTBerendsen = None
    NPTBerendsen = None
    MaxwellBoltzmannDistribution = None
    BFGS = None
    ExpCellFilter = None
    Calculator = None

try:
    from sklearn.cluster import KMeans
    from sklearn.preprocessing import StandardScaler
    SKLEARN_AVAILABLE = True
except (ImportError, ValueError, TypeError) as e:
    SKLEARN_AVAILABLE = False
    logger.warning(f"sklearn not available: {e}")
    KMeans = None
    StandardScaler = None

try:
    import torch
    from torch import nn
    from torch.autograd import grad
    TORCH_AVAILABLE = True
except (ImportError, ValueError, TypeError, AttributeError) as e:
    TORCH_AVAILABLE = False
    logger.warning(f"PyTorch not available: {e}. Required for MLIP model operations.")
    torch = None
    nn = None
    grad = None

try:
    import matgl
    MATGL_AVAILABLE = True
except (ImportError, ValueError, TypeError, AttributeError) as e:
    MATGL_AVAILABLE = False
    logger.warning(f"MatGL not available: {e}. Required for MatGL model operations in matgl-agent environment.")
    matgl = None




class TrajectoryObserver:
    """
    Observer to record intermediate structures during MD simulation.
    
    Follows CHGNet's TrajectoryObserver pattern.
    """
    
    def __init__(self, atoms: Atoms, log_interval: int = 10):
        """
        Initialize trajectory observer.
        
        Args:
            atoms: ASE Atoms object to observe
            log_interval: Interval between structure recordings
        """
        self.atoms = atoms
        self.log_interval = log_interval
        self.structures = []
        self.step_count = 0
    
    def __call__(self) -> None:
        """
        Record structure at current step.
        
        Follows CHGNet's pattern - no arguments, direct access to atoms.
        """
        # ASE handles the interval via dyn.attach(..., interval)
        # So we just record every time we are called
        atoms_copy = self.atoms.copy()
        # Preserve the calculator
        atoms_copy.calc = self.atoms.calc
        self.structures.append(atoms_copy)
        self.step_count += self.log_interval # Estimate step count increment
    
    def __len__(self) -> int:
        """The number of steps in the trajectory."""
        return len(self.structures)
    
    def save(self, filename: str) -> None:
        """Save the trajectory to file."""
        import pickle
        out_pkl = {
            "structures": self.structures,
            "atomic_number": self.atoms.get_atomic_numbers(),
        }
        with open(filename, "wb") as file:
            pickle.dump(out_pkl, file)


class CrystalFeatureObserver:
    """
    Observer to record crystal features during MD simulation.
    
    Follows CHGNet's CrystalFeasObserver pattern exactly.
    """
    
    def __init__(self, atoms: Atoms, log_interval: int = 10):
        """
        Initialize crystal feature observer.
        
        Args:
            atoms: ASE Atoms object to observe
            log_interval: Interval between feature recordings
        """
        self.atoms = atoms
        self.log_interval = log_interval
        self.crystal_feature_vectors = []
        self.step_count = 0
    
    def __call__(self) -> None:
        """
        Record crystal feature vectors after an MD/relaxation step.
        
        Follows CHGNet's pattern exactly - no arguments, direct access to atoms.
        """
        # ASE handles the interval via dyn.attach(..., interval)
        if hasattr(self.atoms, "calc") and self.atoms.calc is not None:
             # Depending on calculator, results might be in .results or computed
             # For some calculators (like MACE), we might need to ensure calculation happens
             # But usually dyn.run() triggers calculation before calling observers
             
             if hasattr(self.atoms.calc, 'results') and 'crystal_fea' in self.atoms.calc.results:
                 crystal_features = self.atoms.calc.results['crystal_fea']
                 self.crystal_feature_vectors.append(crystal_features)
                 # print(f"Recorded crystal features at step {self.step_count}, shape: {crystal_features.shape}")
             else:
                 # Warn once or debug log, but don't crash
                 # logger.debug("Crystal features not found in calculator results")
                 pass
        else:
             # raise RuntimeError("No calculator attached to atoms")
             logger.warning("No calculator attached to atoms in CrystalFeatureObserver")
             pass
             
        self.step_count += self.log_interval
    
    def __len__(self) -> int:
        """Number of recorded steps."""
        return len(self.crystal_feature_vectors)
    
    def save(self, filename: str) -> None:
        """Save the crystal feature vectors to filename in pickle format."""
        import pickle
        out_pkl = {"crystal_feas": self.crystal_feature_vectors}
        with open(filename, "wb") as file:
            pickle.dump(out_pkl, file)
    


class OffEquilibriumSampler:
    """
    Off-Equilibrium Sampler (formerly PESSampler).
    
    Implements MD simulation with clustering-based sampling as specified in sampler.mdc.
    Now accepts a calculator directly for dependency injection.
    """
    
    def __init__(self, 
                 calculator: Calculator, 
                 atoms: Atoms, 
                 total_steps: Optional[int] = None, 
                 output_dir: Optional[str] = None,
                 target_atoms: int = 50, 
                 temperature: float = 1000.0, 
                 ensemble: str = "npt",
                 n_clusters: int = 200,
                 min_length: Optional[float] = None,
                 time_step: Optional[float] = None):
        """
        Initialize OffEquilibriumSampler.
        
        Args:
            calculator: ASE Calculator to use for MD and relaxation.
            atoms: Initial atomic structure
            total_steps: Number of MD steps (default: 10000). Use smaller values for testing.
            output_dir: Directory to save MD log file and other outputs (default: current directory)
            target_atoms: Target number of atoms after supercell expansion (default: 50, range: 40-100)
                         Note: Maximum safe limit is 120 atoms to prevent OOM in VASP calculations.
                               Structures with >120 atoms may cause memory issues during DFT labeling.
            temperature: Temperature in Kelvin (default: 1000.0)
            ensemble: MD ensemble ("nvt", "npt") (default: "npt")
            n_clusters: Number of structures to sample via clustering (default: 200)
            min_length: Minimum lattice length for supercell expansion in Angstroms
            time_step: Time step in fs. (default: 5.0 fs, or 2.0 fs if H is present)
        """
        self.calculator = calculator
        if self.calculator is None:
             raise ValueError("Calculator must be provided to OffEquilibriumSampler")

        # Relax structure before supercell expansion to avoid high stress
        atoms = self._relax_structure(atoms)
        
        # Expand supercell to reach target number of atoms (around 50) with cubic-like expansion
        from src.utils.structure_utils import expand_structure
        MAX_SAFE_ATOMS = 120  # Enforce safety limit to prevent OOM
        expanded_atoms = expand_structure(atoms, target_atoms=target_atoms, max_atoms=MAX_SAFE_ATOMS, min_length=min_length)
        
        # Re-relax after supercell expansion to remove any residual stress
        # This is critical for stable MD - expanded cells often have residual stress
        self.atoms = self._relax_structure(expanded_atoms)
        logger.info("Structure relaxed after supercell expansion to remove residual stress")
        
        self.trajectory_observer = None
        self.crystal_feature_observer = None
        self.output_dir = output_dir
        if self.output_dir:
            import os
            os.makedirs(self.output_dir, exist_ok=True)
        
        # Determine time step
        if time_step is not None:
            self.time_step = time_step
            logger.info(f"Using provided time step: {self.time_step} fs")
        else:
            # Check if H is present
            symbols = atoms.get_chemical_symbols()
            if 'H' in symbols:
                self.time_step = 2.0  # fs - smaller time step for light atoms
                logger.info(f"Hydrogen detected, using {self.time_step} fs time step")
            else:
                self.time_step = 5.0  # fs - standard time step per user request
                logger.info(f"No Hydrogen detected, using {self.time_step} fs time step")
            
        self.total_steps = total_steps if total_steps is not None else 10000
        self.log_interval = 10  # Log every 5 steps for real-time monitoring
        self.temperature = temperature  # K
        self.ensemble = ensemble.lower()
        
        # Slower heating: reach target in around half of total time
        # Assuming 5 * tau ~ equilibration time => 5 * tau = total_time / 2
        # tau = total_time / 20 = (total_steps * time_step) / 20
        calculated_taut = (self.total_steps * self.time_step) / 20
        min_taut = 100 * self.time_step
        self.taut = max(calculated_taut, min_taut)
        
        self.taup = 1000.0  * self.time_step
        self.pressure_au = 0.0  
        self.compressibility_au = 4.57e-5 
        
        # Clustering parameters
        self.n_clusters = n_clusters  # Number of representative structures
    
    def _relax_structure(self, atoms: Atoms) -> Atoms:
        """
        Relax structure using MatCalc before supercell expansion.
        
        This prevents high stress that can cause MD instability.
        Always uses relax_cell=True for full structure relaxation.
        
        Args:
            atoms: Initial atomic structure to relax
            
        Returns:
            Relaxed ASE Atoms object
        """
        if self.calculator is None:
            raise ValueError("Calculator not set")

        import matcalc as mtc
        from pymatgen.io.ase import AseAtomsAdaptor
        
        logger.info(f"Relaxing structure before supercell expansion")
        
        # Convert ASE Atoms to pymatgen Structure
        adaptor = AseAtomsAdaptor()
        pmg_structure = adaptor.get_structure(atoms)
        
        # Create RelaxCalc with the injected calculator - always use relax_cell=True
        relax_calc = mtc.RelaxCalc(
            calculator=self.calculator,
            optimizer="FIRE",
            relax_atoms=True,
            relax_cell=True,  # Always relax cell - required for stable MD
            fmax=0.05,  # Force convergence threshold
        )
        
        # Perform relaxation
        result = relax_calc.calc(pmg_structure)
        
        # Extract relaxed structure from result
        # MatCalc returns a dict with 'structure' or 'final_structure' key
        if isinstance(result, dict):
            if 'structure' in result:
                relaxed_pmg = result['structure']
            elif 'final_structure' in result:
                relaxed_pmg = result['final_structure']
            else:
                raise ValueError(f"Could not find relaxed structure in result. Result keys: {list(result.keys())}")
        elif hasattr(result, 'structure'):  # Result object with structure attribute
            relaxed_pmg = result.structure
        else:
            raise ValueError(f"Unexpected result type from relaxation: {type(result)}")
        
        # Convert back to ASE Atoms
        relaxed_atoms = adaptor.get_atoms(relaxed_pmg)
        
        energy = result.get('energy', 'N/A') if isinstance(result, dict) else getattr(result, 'energy', 'N/A')
        logger.info(f"Structure relaxed successfully. Energy: {energy} eV")
        return relaxed_atoms

    def run_md_simulation(self) -> Tuple[List[Atoms], List[np.ndarray]]:
        """
        Run NPT MD simulation with trajectory and crystal feature observers.
        
        Returns:
            Tuple of (sampled_structures, crystal_features)
        """
        if self.calculator is None:
             raise ValueError("Calculator must be set")
        
        # Calculate total simulation time in ps
        total_time_ps = (self.total_steps * self.time_step) / 1000.0
        
        # Set up atoms with calculator
        atoms = self.atoms.copy()
        atoms.calc = self.calculator
        
        logger.info(f"Starting {self.ensemble.upper()} MD simulation:")
        logger.info(f"  - Number of atoms: {len(atoms)}")
        logger.info(f"  - Number of MD steps: {self.total_steps}")
        logger.info(f"  - Total simulation time: {total_time_ps:.2f} ps")
        logger.info(f"  - Temperature: {self.temperature} K")
        
        # Initialize observers (CHGNet style)
        self.trajectory_observer = TrajectoryObserver(atoms, log_interval=self.log_interval)
        self.crystal_feature_observer = CrystalFeatureObserver(atoms, log_interval=self.log_interval)
        
        # Start from low temperature (50K) instead of 0K to allow gradual motion
        # Starting from 0K can cause stress buildup and then violent motion when thermostat kicks in
        # Small initial temperature allows atoms to move gradually under stress
        from ase.md.velocitydistribution import MaxwellBoltzmannDistribution
        initial_temp = 50.0  # K - small initial temperature for gradual motion
        MaxwellBoltzmannDistribution(atoms, temperature_K=initial_temp)
        logger.info(f"Starting MD from {initial_temp}K, will gradually heat to {self.temperature}K via thermostat")
        
        # Create NPT MD using Inhomogeneous_NPTBerendsen for better pressure control
        # This allows anisotropic pressure control and prevents kinetic energy runaway
        if Inhomogeneous_NPTBerendsen is None:
            raise RuntimeError("Inhomogeneous_NPTBerendsen not available. Please ensure ASE is properly installed.")
        
        # Ensure pressure_au is in correct units
        import ase.units as units
        if not hasattr(self, 'pressure_au') or self.pressure_au == 0.0:
            self.pressure_au = 0.0 * units.bar  # 0 GPa = ambient pressure
        
        # Create trajectory file path if needed
        trajfile = None
        if self.output_dir:
            from pathlib import Path
            trajfile = str(Path(self.output_dir) / "md_trajectory.traj")
            
        if self.ensemble == "npt":
            dyn = Inhomogeneous_NPTBerendsen(
                atoms,
                timestep=self.time_step * units.fs,
                temperature_K=self.temperature,
                pressure_au=self.pressure_au,
                taut=self.taut,
                taup=self.taup,
                compressibility_au=self.compressibility_au,
                trajectory=trajfile,
                logfile=None,  # We use MDLogger separately
                loginterval=self.log_interval,
                append_trajectory=False,
            )
        elif self.ensemble == "nvt":
            from ase.md.langevin import Langevin
            dyn = Langevin(
                atoms,
                timestep=self.time_step * units.fs,
                temperature_K=self.temperature,
                friction=0.02, # Usually 0.01 to 0.05
                trajectory=trajfile,
                logfile=None,
                loginterval=self.log_interval,
                append_trajectory=False,
            )
        else:
            raise ValueError(f"Unsupported ensemble '{self.ensemble}'. Must be 'nvt' or 'npt'.")
        
        # Add observers
        dyn.attach(self.trajectory_observer, interval=self.log_interval)
        dyn.attach(self.crystal_feature_observer, interval=self.log_interval)
        
        # Add logger - save to output_dir if specified, otherwise current directory
        from pathlib import Path
        if self.output_dir:
            log_path = Path(self.output_dir) / "pes_md.log"
            log_path.parent.mkdir(parents=True, exist_ok=True)
        else:
            log_path = Path("pes_md.log")
            
        logger_md = MDLogger(dyn, atoms, str(log_path), 
                           header=True, stress=True, peratom=True, mode="w")
        dyn.attach(logger_md, interval=self.log_interval)
        logger.info(f"  - MD log saved to: {log_path}")
        
        # Run MD simulation
        dyn.run(self.total_steps)
        logger.info("MD simulation completed successfully")
        
        return self.trajectory_observer.structures, self.crystal_feature_observer.crystal_feature_vectors, {
            "num_atoms": len(atoms),
            "total_steps": self.total_steps,
            "time_step": self.time_step,
            "total_time_ps": total_time_ps,
            "temperature": self.temperature,
            "pressure": self.pressure_au
        }
    
    def cluster_structures(self, structures: List[Atoms], features: List[np.ndarray]) -> Tuple[List[Atoms], List[int]]:
        """
        Perform clustering sampling on crystal features to downselect representative structures.
        
        Args:
            structures: List of structures from MD simulation
            features: List of crystal features corresponding to structures
            
        Returns:
        Returns:
            List of representative structures (max 200), List of indices
        """
        if len(structures) == 0:
            logger.warning("No structures to cluster")
            return [], []
        
        logger.info(f"Clustering {len(structures)} structures to {min(self.n_clusters, len(structures))} representatives")
        
        # Ensure we don't ask for more clusters than structures
        n_clusters = min(self.n_clusters, len(structures))
        
        if n_clusters >= len(structures):
            logger.info("Number of clusters >= number of structures, returning all structures")
            return structures, list(range(len(structures)))
        
        # Features are now crystal-level features (64,) from averaged atom features
        # Convert to 2D array for clustering
        features_array = np.array(features)  # Shape: (n_structures, 64)
        logger.info(f"Features shape: {features_array.shape}")
        
        # Handle very small datasets with simple selection
        if len(structures) <= 3:
            logger.info("Small dataset: using simple selection strategy")
            return self._simple_selection(structures, features_array, n_clusters)
        
        # Standardize features
        scaler = StandardScaler()
        features_scaled = scaler.fit_transform(features_array)
        
        # Use more robust clustering for small datasets
        if len(structures) < 10:
            # Use hierarchical clustering for small datasets
            from sklearn.cluster import AgglomerativeClustering
            clustering = AgglomerativeClustering(n_clusters=n_clusters, linkage='ward')
            cluster_labels = clustering.fit_predict(features_scaled)
        else:
            # Use K-means for larger datasets
            kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10, max_iter=100)
            cluster_labels = kmeans.fit_predict(features_scaled)
        
        # Select representative structures
        representative_structures, representative_indices = self._select_representatives(
            structures, features_scaled, cluster_labels, n_clusters
        )
        
        logger.info(f"Clustering completed. Selected {len(representative_structures)} representative structures")
        return representative_structures, representative_indices
    
    def _aggregate_to_crystal_features(self, features: List[np.ndarray]) -> np.ndarray:
        """
        Aggregate per-atom features to crystal-level features.
        Uses multiple aggregation strategies inspired by MAML approach.
        """
        crystal_features_list = []
        
        for feature in features:
            if feature.ndim == 2 and feature.shape[1] == 1:
                # Per-atom features (N_atoms, 1) - aggregate to crystal level
                per_atom = feature.flatten()
                
                # Multiple aggregation strategies for robustness
                crystal_feature = np.concatenate([
                    [np.mean(per_atom)],      # Mean
                    [np.std(per_atom)],       # Standard deviation
                    [np.min(per_atom)],       # Minimum
                    [np.max(per_atom)],       # Maximum
                    [np.median(per_atom)],    # Median
                    [np.percentile(per_atom, 25)],  # 25th percentile
                    [np.percentile(per_atom, 75)],  # 75th percentile
                    [np.sum(per_atom)],       # Sum (extensive property)
                ])
            else:
                # Already crystal-level features
                crystal_feature = feature.flatten()
            
            crystal_features_list.append(crystal_feature)
        
        return np.array(crystal_features_list)
    
    def _simple_selection(self, structures: List[Atoms], features: np.ndarray, n_clusters: int) -> List[Atoms]:
        """
        Simple selection strategy for very small datasets.
        Selects structures with maximum diversity.
        """
        if len(structures) <= n_clusters:
            return structures
        
        # Calculate pairwise distances
        from sklearn.metrics.pairwise import euclidean_distances
        distances = euclidean_distances(features)
        
        # Select most diverse structures
        selected_indices = [0]  # Start with first structure
        
        for _ in range(n_clusters - 1):
            max_min_distance = -1
            best_candidate = -1
            
            for i in range(len(structures)):
                if i not in selected_indices:
                    min_distance = min(distances[i][j] for j in selected_indices)
                    if min_distance > max_min_distance:
                        max_min_distance = min_distance
                        best_candidate = i
            
            if best_candidate != -1:
                selected_indices.append(best_candidate)
        
        return [structures[i] for i in selected_indices], selected_indices
    
    def _select_representatives(self, structures: List[Atoms], features_scaled: np.ndarray, 
                              cluster_labels: np.ndarray, n_clusters: int) -> List[Atoms]:
        """
        Select representative structures from clusters.
        """
        representative_structures = []
        representative_indices = []
        
        for cluster_id in range(n_clusters):
            cluster_mask = cluster_labels == cluster_id
            cluster_structures = [structures[i] for i in range(len(structures)) if cluster_mask[i]]
            cluster_features = features_scaled[cluster_mask]
            
            if len(cluster_structures) > 0:
                if len(cluster_structures) == 1:
                    # Single structure in cluster
                    representative_structures.append(cluster_structures[0])
                    # Find index
                    idx = [i for i, mask in enumerate(cluster_mask) if mask][0]
                    representative_indices.append(idx)
                else:
                    # Find structure closest to cluster centroid
                    cluster_centroid = np.mean(cluster_features, axis=0)
                    distances = np.linalg.norm(cluster_features - cluster_centroid, axis=1)
                    closest_local_idx = np.argmin(distances)
                    # Map back to global index
                    # cluster_structures was created by iterating range(len(structures)) with mask
                    # so we need to find the index in original list
                    # It's cleaner to re-derive indices
                    cluster_indices = [i for i, mask in enumerate(cluster_mask) if mask]
                    closest_global_idx = cluster_indices[closest_local_idx]
                    
                    representative_structures.append(structures[closest_global_idx])
                    representative_indices.append(closest_global_idx) # type: ignore
        
        return representative_structures, representative_indices
    
    def sample(self) -> Tuple[List[Atoms], Dict[str, Any]]:
        """
        Main sampling method that runs MD simulation and clustering.
        
        Returns:
            List of representative structures, Metadata dictionary
        """
        logger.info("Starting PES sampling")
        
        # Run MD simulation
        structures, features, metadata = self.run_md_simulation()
        
        # Cluster structures
        if len(features) == 0:
            logger.warning("No crystal features extracted. Improving fall-back to uniform temporal sampling.")
            # Fallback to simple uniform sampling
            n_samples = min(self.n_clusters, len(structures))
            if n_samples > 0:
                indices = np.linspace(0, len(structures)-1, n_samples, dtype=int).tolist()
                representative_structures = [structures[i] for i in indices]
                representative_indices = indices
            else:
                 representative_structures = []
                 representative_indices = []
        else:
            representative_structures, representative_indices = self.cluster_structures(structures, features)
        
        # Add indices to metadata
        # Convert to actual MD steps
        md_steps = [idx * self.log_interval for idx in representative_indices]
        metadata["sampled_indices"] = representative_indices # Index in the structure list
        metadata["sampled_md_steps"] = md_steps # Actual MD step number
        
        # Save individual structures if output_dir provided
        if self.output_dir:
            try:
                import os
                from ase.io import write
                os.makedirs(self.output_dir, exist_ok=True)
                for i, struct in enumerate(representative_structures):
                    fname = os.path.join(self.output_dir, f"sampled_{i}.cif")
                    write(fname, struct)
                logger.info(f"Saved {len(representative_structures)} structures to {self.output_dir}")
            except Exception as e:
                logger.warning(f"Failed to save sampled structures: {e}")

        logger.info(f"PES sampling completed. Generated {len(representative_structures)} representative structures")
        return representative_structures, metadata







