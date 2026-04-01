import os
import json
import logging
import numpy as np
import glob
from smol.capp.generate import generate_random_ordered_occupancy
from monty.serialization import loadfn
from typing import List, Dict, Any, Optional, Union, Tuple

# Runtime monkey-patch for smol to handle pymatgen 2025+ Composition objects and Vacancy strings
# Must be applied BEFORE importing other smol modules that use get_species
try:
    from smol.cofe.space import domain as smol_domain
    from smol.cofe.space import Vacancy
    import logging
    _log = logging.getLogger(__name__)
    
    _original_get_species = getattr(smol_domain, "_original_get_species", smol_domain.get_species)
    _original_get_el_sp = getattr(smol_domain, "_original_get_el_sp", smol_domain.get_el_sp)

    def _patched_get_species(obj):
        if isinstance(obj, str) and "vac" in obj.lower():
            return Vacancy()
        if hasattr(obj, "keys") and len(obj) == 1:
            try:
                obj = next(iter(obj.keys()))
            except Exception: pass
        return _original_get_species(obj)

    def _patched_get_el_sp(obj):
        if hasattr(obj, "keys") and len(obj) == 1:
             try:
                obj = next(iter(obj.keys()))
             except Exception: pass
        return _original_get_el_sp(obj)

    smol_domain.get_species = _patched_get_species
    smol_domain.get_el_sp = _patched_get_el_sp
    smol_domain._original_get_species = _original_get_species
    smol_domain._original_get_el_sp = _original_get_el_sp
except ImportError:
    pass

from pymatgen.core import Structure
from pymatgen.entries.computed_entries import ComputedStructureEntry
from smol.cofe import ClusterSubspace, ClusterExpansion, StructureWrangler
# No longer need monkey-patch - smol 0.5.8+ natively supports pymatgen 2025+
from smol.moca import Ensemble, Sampler, CompositionSpace
from sklearn.linear_model import LinearRegression, Lasso, Ridge
from ase import Atoms
from pymatgen.io.ase import AseAtomsAdaptor
from pymatgen.analysis.structure_matcher import StructureMatcher, ElementComparator, SpeciesComparator
from .enumeration_utils import (
    enumerate_matrices, 
    truncate_cluster_subspace, 
    generate_training_structures,
    sample_ordered_structures
)
import matplotlib.pyplot as plt
from sklearn.model_selection import LeaveOneOut
from sklearn.metrics import mean_squared_error

logger = logging.getLogger(__name__)

class SmolWrapper:
    """
    A wrapper around the smol package to facilitate common cluster expansion (CE)
    and Monte Carlo (MC) workflows.
    """
    
    def __init__(self):
        self.subspace: Optional[ClusterSubspace] = None
        self.wrangler: Optional[StructureWrangler] = None
        self.expansion: Optional[ClusterExpansion] = None
        
    @staticmethod
    def get_matcher():
        """Get standard StructureMatcher with optimized tolerances."""
        return StructureMatcher(
            ltol=0.3, stol=0.3, angle_tol=10,
            primitive_cell=False, scale=False,
            allow_subset=True,
            comparator=SpeciesComparator(),
            ignored_species=[Vacancy()]
        )


    def create_subspace(self, 
                        disordered_structure: Union[Structure, Dict, Atoms],
                        cutoffs: Dict[int, float],
                        max_cluster_size: int = 2,
                        basis_set: str = "chebyshev") -> str:
        """
        Create a cluster subspace from a disordered structure.
        """
        from src.utils.structure_utils import load_structures
        
        # Load locally to avoid import cycle or handle varied inputs
        # load_structures returns a list. We expect one structure.
        if isinstance(disordered_structure, (str, bytes, os.PathLike)):
             loaded = load_structures(disordered_structure)
             if not loaded:
                 raise ValueError(f"Could not load structure from {disordered_structure}")
             struct = loaded[0]
        else:
             struct = self._ensure_pmg_structure(disordered_structure)

        if isinstance(cutoffs, (float, int)):
            cutoffs = {i: float(cutoffs) for i in range(2, max_cluster_size + 1)}
            
        self.subspace = ClusterSubspace.from_cutoffs(
            struct,
            cutoffs=cutoffs,
            basis=basis_set
        )
        # Don't assign matcher to subspace - it causes pymatgen incompatibility with monkey-patched sites
        # m = self.get_matcher()
        # self.subspace._sc_matcher = m
        # self.subspace._site_matcher = m

        self.wrangler = StructureWrangler(self.subspace)
        return f"ClusterSubspace created with {len(self.subspace)} clusters."

    def add_training_data(self, data: Union[List[Dict[str, Any]], Dict[str, Any], str], prim: Optional[Structure] = None) -> str:
        """
        Add training data to the StructureWrangler.
        
        Args:
            data: Can be:
                - List of dicts (standard format).
                - Single dict (result).
                - String path to a JSON file containing the list.
                - String path to a directory containing relaxation results.
            prim: Disordered (primordial) structure (uses subspace's if None).
            
        Returns:
            Status message.
        """
        if self.wrangler is None:
            return "Error: ClusterSubspace must be created before adding training data."
        
        # Use primordial from subspace if not provided
        if prim is None:
            prim = self.subspace.structure

        data_list = []
        
        # Case 1: Path (String)
        if isinstance(data, (str, os.PathLike)):
            path = str(data)
            if os.path.isfile(path):
                # Load from file
                try:
                    loaded = loadfn(path)
                    if isinstance(loaded, list):
                        data_list = loaded
                    elif isinstance(loaded, dict):
                        data_list = [loaded]
                except Exception as e:
                    return f"Error loading training data file {path}: {e}"
            elif os.path.isdir(path):
                # Directory loading logic
                logger.info(f"Scanning directory {path} for training data...")
                
                # 1. Look for standard JSON result files
                search_patterns = [
                    os.path.join(path, "**", "relaxation_results.json"),
                    os.path.join(path, "**", "result.json")
                ]
                files = []
                for p in search_patterns:
                    files.extend(glob.glob(p, recursive=True))
                
                for f in files:
                    try:
                        res = loadfn(f)
                        data_list.append(res)
                    except Exception as e:
                        logger.warning(f"Failed to load {f}: {e}")
                        
                # 2. Look for CIF + Energy TXT pairs (Agent workflow style)
                cif_files = glob.glob(os.path.join(path, "**", "relaxed_structure.cif"), recursive=True)
                for cif in cif_files:
                    try:
                        dir_path = os.path.dirname(cif)
                        energy_file = os.path.join(dir_path, "relaxed_energy.txt")
                        sc_file = os.path.join(dir_path, "sc_matrix.json")
                        
                        if os.path.exists(energy_file):
                            struct = Structure.from_file(cif).as_dict()
                            with open(energy_file, "r") as ef:
                                energy = float(ef.read().strip())
                                
                            entry = {
                                "structure": struct,
                                "energy": energy,
                                "path": cif
                            }
                            if os.path.exists(sc_file):
                                with open(sc_file, "r") as sf:
                                    entry["sc_matrix"] = json.load(sf)
                            data_list.append(entry)
                    except Exception as e:
                        logger.warning(f"Failed to load CIF result {cif}: {e}")

                # 3. Fallback: load_structures for other formats (e.g. vasprun.xml, extxyz)
                if not data_list:
                    from src.utils.structure_utils import load_structures
                    logger.info("No standard result files types 1/2 found. Trying generic load_structures.")
                    try:
                        structs = load_structures(path)
                        for s in structs:
                            # Check for energy in properties or attributes
                            e = None
                            if hasattr(s, "entry") and hasattr(s.entry, "energy"):
                                e = s.entry.energy
                            elif hasattr(s, "properties") and s.properties.get("energy"):
                                e = s.properties.get("energy")
                            
                            # If we have energy, add it
                            if e is not None:
                                data_list.append({"structure": s, "energy": e})
                    except Exception as e:
                         logger.warning(f"Generic load_structures failed: {e}")

            else:
                return f"Error: Path {path} not found."
                
        # Case 2: Dict (Single Entry)
        elif isinstance(data, dict):
            # Check if it's a structure dict or a result dict
            if "structure" in data and "energy" in data:
                 data_list = [data]
            elif "results" in data:
                 data_list = data["results"]
            else:
                 # maybe it is a structure dict itself? Unlikely to have energy detached.
                 data_list = [data] # Let the loop handle it
            
        # Case 3: List (Already list of dicts)
        elif isinstance(data, list):
            data_list = data
            
        if not data_list:
            return "No training data found."

        count = 0
        added_entries = []
        
        for entry in data_list:
            try:
                struct_data = entry.get("final_structure") or entry.get("structure")
                energy = entry.get("final_energy") or entry.get("energy")
                sc_matrix = entry.get("sc_matrix")
                
                if struct_data is None or energy is None:
                    continue

                s = self._ensure_pmg_structure(struct_data)
                
                # If no supercell matrix provided, try to determine it
                if sc_matrix is None:
                    try:
                        sc_matrix = self.subspace.scmatrix_from_structure(s)
                    except Exception:
                        # logger.warning("Could not determine supercell matrix for structure")
                        pass
                
                # Create ComputedStructureEntry
                comp_entry = ComputedStructureEntry(s, energy)
                
                # Use smol's native add_entry
                # Pass supercell_matrix if we found it, otherwise let smol try
                kwargs = {"entry": comp_entry}
                if sc_matrix is not None:
                    kwargs["supercell_matrix"] = sc_matrix
                    
                self.wrangler.add_entry(**kwargs)
                count += 1
                added_entries.append(entry)
            except Exception as e:
                # logger.warning(f"Failed to add entry: {e}")
                pass
                
        return f"Successfully added {count} entries."

    def get_feature_matrix(self) -> np.ndarray:
        """Return the current feature matrix from the wrangler."""
        if self.wrangler is None: return np.array([])
        return self.wrangler.feature_matrix

    def is_same_configuration(self, s1_data: Any, s2_data: Any) -> bool:
        """Check if two structures represent the same configuration in the current subspace."""
        if self.subspace is None:
            raise ValueError("Subspace not initialized.")
        
        s1 = self._ensure_pmg_structure(s1_data)
        s2 = self._ensure_pmg_structure(s2_data)
        
        # Try to get supercell matrices
        try:
            m1 = self.subspace.scmatrix_from_structure(s1)
            m2 = self.subspace.scmatrix_from_structure(s2)
        except Exception:
            # If we can't determine the matrices, structures are too different
            return False
        
        # Compare correlation vectors
        try:
            corr1 = self.subspace.corr_from_structure(s1, scmatrix=m1)
            corr2 = self.subspace.corr_from_structure(s2, scmatrix=m2)
            return np.allclose(corr1, corr2, atol=1e-6)
        except Exception:
            return False


    def fit_expansion(self, method: str = "ls", **kwargs) -> Dict[str, Any]:
        """
        Fit the cluster expansion using the data in the wrangler.
        methods: 'ls' (least squares), 'lasso', 'ridge', 'sgl' (Sparse Group Lasso)
        """
        from sklearn.linear_model import Lasso, Ridge, LinearRegression, LassoCV
        from sklearn.model_selection import LeaveOneOut
        from sklearn.metrics import mean_squared_error
        from smol.cofe import ClusterExpansion
        
        if self.wrangler is None or len(self.wrangler.entries) == 0:
            return {"error": "No training data available for fitting."}
            
        # Get feature matrix and target values
        feature_matrix = self.wrangler.feature_matrix
        # By default, smol uses 'energy' as the property name for ComputedStructureEntry
        try:
            energies = self.wrangler.get_property_vector('energy')
        except Exception:
            # Fallback for older versions or different property names
            energies = np.array([entry.energy for entry in self.wrangler.entries])
        
        if method == "sgl":
            # Special handling for Sparse Group Lasso as per high-component-ce-tools authors
            from .sparse_group_lasso import SparseGroupLasso, make_groups
            alpha = kwargs.get("alpha", 0.002)
            lambd = kwargs.get("lambda_mixing", 0.5)
            # Find groups
            groups = make_groups(self.wrangler, ignore=1) # 1 means ignore point terms
            groups = np.array(groups)
            
            # Point clusters are typically index 1 to N_points
            # Find point clusters manually from subspace if ignore=1
            point_cluster_start = 1 # Assuming 0 is empty cluster
            point_cluster_end = 1
            if 1 in self.subspace.orbits_by_size:
                for orbit in self.subspace.orbits_by_size[1]:
                    point_cluster_end += len(orbit.bit_combos)
                    
            e0 = np.mean(energies)
            # Fit Lasso to point terms first
            lasso_cv = LassoCV(fit_intercept=True).fit(
                feature_matrix[:, point_cluster_start:point_cluster_end], energies.ravel() - e0)
            e1 = lasso_cv.predict(feature_matrix[:, point_cluster_start:point_cluster_end]).reshape(-1, 1)
            
            y_remainder = energies.reshape(-1, 1) - e0 - e1
            
            sgl = SparseGroupLasso(groups=groups, lambd=lambd)
            sgl.set_params(alpha)
            sgl.fit(feature_matrix[:, point_cluster_end:], y_remainder)
            
            eci = np.concatenate(([e0 + lasso_cv.intercept_], lasso_cv.coef_, sgl.coef_), axis=0)
            model = sgl # For RMSE prediction purposes later
            
            y_pred = e0 + e1.ravel() + np.dot(feature_matrix[:, point_cluster_end:], sgl.coef_)
        else:
            if method == "lasso":
                model = Lasso(**kwargs)
            elif method == "ridge":
                model = Ridge(**kwargs)
            else:
                model = LinearRegression()
                
            # Fit model
            model.fit(feature_matrix, energies)
            eci = model.coef_
            y_pred = model.predict(feature_matrix)

        # Scikit-learn intercept is separate, but smol ClusterExpansion
        # handles it via the empty cluster correlation (which should be the first column)
        # We need to make sure the constant is handled correctly.
        # smol typically includes a constant column in the feature matrix.
        self.expansion = ClusterExpansion(self.subspace, coefficients=eci)
        
        # Calculate RMSE
        rmse = float(np.sqrt(mean_squared_error(energies, y_pred)))
        
        loocv = None
        if method != "sgl":
            # Calculate LOOCV
            loo = LeaveOneOut()
            errors = []
            for train_index, test_index in loo.split(feature_matrix):
                X_train, X_test = feature_matrix[train_index], feature_matrix[test_index]
                y_train, y_test = energies[train_index], energies[test_index]
                model.fit(X_train, y_train)
                errors.append((model.predict(X_test)[0] - y_test[0])**2)
            loocv = float(np.sqrt(np.mean(errors)))
        
        return {
            "status": "success",
            "rmse": rmse,
            "loocv": loocv,
            "coef_count": len(np.where(np.abs(eci) > 1e-5)[0]) if method == "sgl" else len(eci)
        }

    def fit_feature_matrix(
        self,
        feature_matrix_path: str,
        energies_path: str,
        groups_path: Optional[str] = None,
        fit_method: str = "ls",
        alpha: float = 0.002,
        lambda_mixing: float = 0.5,
        point_features_count: int = 1,
        test_size: float = 0.2
    ) -> Dict[str, Any]:
        """
        Fit directly from pre-computed feature matrices.
        
        Args:
            feature_matrix_path: Path to the .npy file containing the feature matrix (n_samples, n_features).
            energies_path: Path to the .npy file containing the target energies.
            groups_path: Path to the .npy file containing the cluster group assignments (required for 'sgl').
            fit_method: The fitting method to use ('ls', 'lasso', 'ridge', or 'sgl').
            alpha: The regularization strength for 'lasso', 'ridge', and 'sgl'.
            lambda_mixing: The L1/L2 mixing parameter for 'sgl' (1.0 goes to Lasso, 0.0 to Ridge).
            point_features_count: The number of unpenalized point/constant features at the start of the feature matrix. 
                                  Used by SGL to fit these via CV Lasso before grouping the remaining features.
            test_size: The proportion of the dataset to include in the test split for RMSE validation.
            
        Returns:
            Dictionary containing the fitting results, method used, RMSEs, and coefficient count.
        """
        from sklearn.linear_model import Lasso, Ridge, LinearRegression, LassoCV
        from sklearn.model_selection import train_test_split
        from sklearn.metrics import mean_squared_error

        X = np.load(feature_matrix_path)
        y = np.load(energies_path)
        if len(y.shape) == 2 and y.shape[1] == 1:
            y = y.ravel()

        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=test_size)

        if fit_method == "sgl":
            from .sparse_group_lasso import SparseGroupLasso
            if not groups_path:
                return {"error": "groups_path is required for sgl fit."}
            groups = np.load(groups_path)
            
            # If groups array covers the whole feature matrix, slice it
            non_grouped_cols = point_features_count
            if len(groups) == X.shape[1]:
                sgl_groups = groups[non_grouped_cols:]
            elif len(groups) == X.shape[1] - non_grouped_cols:
                sgl_groups = groups
            else:
                return {"error": f"Size of groups ({len(groups)}) doesn't match X features ({X.shape[1]}) minus point_features_count ({non_grouped_cols})."}
            
            first_point = 1 # Assuming 0 is the constant
            last_point = non_grouped_cols
            
            e0 = np.mean(y_train)
            lasso_cv = LassoCV(fit_intercept=True).fit(
                X_train[:, first_point:last_point], y_train - e0)
            e1 = lasso_cv.predict(X_train[:, first_point:last_point]).reshape(-1, 1)
            e1_test = lasso_cv.predict(X_test[:, first_point:last_point]).reshape(-1, 1)
            
            y_train_rem = y_train.reshape(-1, 1) - e0 - e1
            y_test_rem = y_test.reshape(-1, 1) - e0 - e1_test
            
            sgl = SparseGroupLasso(groups=sgl_groups, lambd=lambda_mixing)
            sgl.set_params(alpha)
            sgl.fit(X_train[:, last_point:], y_train_rem)
            
            y_train_pred = np.dot(X_train[:, last_point:], sgl.coef_).ravel()
            y_test_pred = np.dot(X_test[:, last_point:], sgl.coef_).ravel()
            
            train_rmse = np.sqrt(mean_squared_error(y_train_rem.ravel(), y_train_pred))
            test_rmse = np.sqrt(mean_squared_error(y_test_rem.ravel(), y_test_pred))
            
            coef = np.concatenate(([e0 + lasso_cv.intercept_], lasso_cv.coef_, sgl.coef_), axis=0)
            coef_count = len(np.where(np.abs(coef) > 1e-5)[0])
        else:
            if fit_method == "lasso":
                model = Lasso(alpha=alpha)
            elif fit_method == "ridge":
                model = Ridge(alpha=alpha)
            else:
                model = LinearRegression()
                
            model.fit(X_train, y_train)
            y_train_pred = model.predict(X_train)
            y_test_pred = model.predict(X_test)
            
            train_rmse = np.sqrt(mean_squared_error(y_train, y_train_pred))
            test_rmse = np.sqrt(mean_squared_error(y_test, y_test_pred))
            coef = model.coef_
            coef_count = len(np.where(np.abs(coef) > 1e-5)[0])

        return {
            "status": "success",
            "method": fit_method,
            "train_rmse": float(train_rmse),
            "test_rmse": float(test_rmse),
            "coef_count": int(coef_count),
            "test_size": float(test_size)
        }

    def sample_ordered_structures(
        self,
        disordered_structure: Union[Structure, Dict, Atoms, str],
        cutoffs: Dict[int, float],
        num_structures: int = 100,
        target_num_sites: int = 32,
        basis_set: str = "chebyshev",
        max_cluster_size: int = 2
    ) -> List[Structure]:
        """
        Generate diverse ordered structures for iteration 0 via enumeration.
        """
        # 1. Ensure PMG structure
        from src.utils.structure_utils import load_structures
        if isinstance(disordered_structure, (str, bytes, os.PathLike)):
             loaded = load_structures(disordered_structure)
             if not loaded:
                 raise ValueError(f"Could not load structure from {disordered_structure}")
             prim = loaded[0]
        else:
             prim = self._ensure_pmg_structure(disordered_structure)
        
        # 2. Setup subspace
        self.create_subspace(prim, cutoffs, max_cluster_size, basis_set)
        
        # 3. Enumerate matrices
        sc_matrices = enumerate_matrices(target_num_sites, self.subspace)
        self.subspace = truncate_cluster_subspace(self.subspace, sc_matrices)
        
        # 4. Composition Space
        # Use dummy CE for processor/ensemble setup
        dummy_ce = ClusterExpansion(self.subspace, np.zeros(self.subspace.num_corr_functions))
        ensemble = Ensemble.from_cluster_expansion(dummy_ce, np.eye(3, dtype=int), processor_type="expansion")
        
        site_spaces = [list(sl.site_space.keys()) for sl in ensemble.sublattices if sl.is_active]
        sublattice_sizes = [len(sl.sites) for sl in ensemble.sublattices if sl.is_active]
        comp_space = CompositionSpace(site_spaces, sublattice_sizes)
        
        # 5. Generate and select
        selected_structs, _, _ = generate_training_structures(
            self.subspace,
            sc_matrices,
            comp_space,
            num_structs=num_structures
        )
        
        return selected_structs

    def save_ce(self, file_path: str) -> str:
        """
        Save the fitted cluster expansion to a file.
        """
        if self.expansion is None:
            return "Error: No ClusterExpansion to save."
        
        self.expansion.save(file_path, strict=False)
        return f"ClusterExpansion saved to {file_path}"

    def load_ce(self, file_path: str) -> str:
        """
        Load a cluster expansion from a file.
        """
        try:
            self.expansion = ClusterExpansion.load(file_path)
            self.subspace = self.expansion.cluster_subspace
            # If subspace is loaded, we can recreate a wrangler if needed
            self.wrangler = StructureWrangler(self.subspace)
            return f"ClusterExpansion loaded from {file_path}"
        except Exception as e:
            return f"Error loading ClusterExpansion: {str(e)}"

    def run_mc(self, 
               supercell_matrix: List[List[int]],
               temperature: float,
               steps: int,
               ensemble_type: str = "canonical",
               initial_occupancies: Optional[np.ndarray] = None,
               initial_composition: Optional[Dict[str, float]] = None,
               trajectory_file: Optional[str] = None,
               log_interval: int = 1) -> Dict[str, Any]:
        """
        Run Monte Carlo simulation using the fitted Cluster Expansion.

        Args:
            supercell_matrix: 3x3 matrix defining the supercell to run MC on.
            temperature: Simulation temperature in Kelvin.
            steps: Number of MC steps to run.
            ensemble_type: Type of ensemble ('canonical' or 'semigrand').
            initial_occupancies: Optional initial configuration.
            initial_composition: Optional target composition for random initialization (e.g. {'Li': 0.5}).
                                Used only if initial_occupancies is None.
            trajectory_file: Optional path to save the MC trajectory (HDF5 format).
            log_interval: Interval for saving samples to the trajectory file. 
                     For example, log_interval=10 saves every 10th step.
                     Lower values create larger files but higher resolution trajectories.
            
        Returns:
            Dictionary with final energy, structure, and status.
        """
        if self.expansion is None:
            return {"error": "ClusterExpansion must be fitted before running MC."}
            
        # Create Ensemble
        ensemble = Ensemble.from_cluster_expansion(
            self.expansion,
            supercell_matrix=supercell_matrix
        )
        
        # Create Sampler
        step_type = 'swap' if ensemble_type == 'canonical' else 'flip'
        
        sampler = Sampler.from_ensemble(
            ensemble,
            temperature=temperature,
            step_type=step_type
        )
        
        # Run simulation
        if initial_occupancies is None:
            if initial_composition is not None:
                try:
                    from pymatgen.core import Composition
                    from smol.cofe.space.domain import get_species
                    
                    sublattices = ensemble.processor.get_sublattices()
                    logger.info(f"Ensemble has {len(sublattices)} sublattices.")
                    
                    if isinstance(initial_composition, dict):
                        processed_comp = []
                        for sl in sublattices:
                            sl_dict = {}
                            for sp in sl.site_space:
                                sp_name = str(sp)
                                if sp_name in initial_composition:
                                    sl_dict[sp] = initial_composition[sp_name]
                                elif sp_name.replace("A0+", "") in initial_composition:
                                    sl_dict[sp] = initial_composition[sp_name.replace("A0+", "")]
                            
                            if not sl_dict:
                                sl_dict = {sp: 1.0/len(sl.species) for sp in sl.species}
                            
                            # Normalize fractions to 1.0 to ensure supercell is fully occupied
                            total_frac = sum(sl_dict.values())
                            sl_dict = {k: v / total_frac for k, v in sl_dict.items()}
                            
                            # smol strict fraction checking workaround: convert to exact atom counts
                            n_sites = len(sl.active_sites) if len(sl.active_sites) > 0 else len(sl.sites)
                            exact_dict = {}
                            remaining_sites = n_sites
                            
                            for i, (k, v) in enumerate(sl_dict.items()):
                                if i == len(sl_dict) - 1:
                                    exact_dict[k] = remaining_sites
                                else:
                                    count = int(round(v * n_sites))
                                    exact_dict[k] = count
                                    remaining_sites -= count
                            
                            processed_comp.append(Composition(exact_dict))
                        
                        initial_comp_obj = processed_comp
                    elif isinstance(initial_composition, list):
                        initial_comp_obj = [Composition({get_species(k): v for k, v in d.items()}) for d in initial_composition]
                    else:
                        initial_comp_obj = initial_composition

                    logger.info(f"Generating random initial state with composition: {initial_comp_obj}")
                    initial_occupancies = generate_random_ordered_occupancy(
                        ensemble.processor, 
                        composition=initial_comp_obj
                    )
                    
                except Exception as e:
                    logger.error(f"Failed to generate random composition: {e}")
                    # Fallback to zero-index occupancy (usually first species in each sublattice)
                    num_sites = ensemble.processor.num_sites
                    initial_occupancies = np.zeros(num_sites, dtype=int)
            else:
                # Default to zero-index occupancy if no composition provided
                num_sites = ensemble.processor.num_sites
                initial_occupancies = np.zeros(num_sites, dtype=int)

        # Configure streaming if trajectory_file is provided
        run_kwargs = {"thin_by": log_interval}
        if trajectory_file:
            run_kwargs["stream_file"] = trajectory_file
            # Default chunk size: 100 or total steps if smaller
            run_kwargs["stream_chunk"] = 1
            run_kwargs["keep_last_chunk"] = True
            
        sampler.run(steps, initial_occupancies=initial_occupancies, **run_kwargs)
        
        # Get results
        # Get results
        samples = sampler.samples
        if len(samples.get_occupancies()) == 0:
             return {"error": "No samples generated. Check steps and thin_by."}

        occupancies = samples.get_occupancies(flat=False)
        print(f"DEBUG: occupancies shape: {occupancies.shape}")
        # occupancies shape is (nsamples, nwalkers, nsites)
        # We take the last sample and first walker
        final_occu = occupancies[-1, 0, :]
        final_structure = self._occu_to_structure(ensemble, final_occu)
        
        # Save final structure to CIF instead of returning it
        if trajectory_file:
            base_name = os.path.splitext(trajectory_file)[0]
            cif_path = f"{base_name}_final.cif"
        else:
            cif_path = "mc_final_structure.cif"
            
        final_structure.to(filename=cif_path)
        
        return {
            "status": "success",
            "final_structure_path": cif_path,
            "trajectory_file": trajectory_file
        }

    def compute_feature_vectors(self, structures: List[Union[Structure, Dict, str]]) -> Dict[str, Any]:
        """
        Compute feature vectors (correlations) for a list of structures using the current subspace.

        This method processes a list of structures (objects, dicts, or paths), automatically 
        determines the appropriate supercell matrix for each structure relative to the 
        subspace, and calculates the correlation vector.

        Args:
            structures: List of input structures. Each element can be:
                        - A pymatgen Structure object.
                        - A dictionary representation of a structure (pymatgen or ASE).
                        - A file path string pointing to a structure file.

        Returns:
            Dictionary containing:
                - 'features': List of calculated correlation vectors (each is a list of floats).
                - 'valid_indices': Indices of the input structures that were successfully processed.
                - 'errors': List of error messages for structures that failed processing.
        """
        if self.subspace is None:
            return {"error": "Cluster subspace must be initialized first."}
            
        features = []
        valid_indices = []
        errors = []
        
        for i, s_data in enumerate(structures):
            try:
                s = self._ensure_pmg_structure(s_data)
                # Try to determine supercell matrix automatically
                # This uses smol's structure matching to find the transformation
                sc_matrix = self.subspace.scmatrix_from_structure(s)
                
                # Calculate correlation vector
                feat = self.subspace.corr_from_structure(s, scmatrix=sc_matrix)
                features.append(feat.tolist())
                valid_indices.append(i)
            except Exception as e:
                errors.append(f"Structure {i}: {str(e)}")
                
        return {
            "features": features,
            "valid_indices": valid_indices,
            "errors": errors
        }

    def _ensure_pmg_structure(self, structure_data: Any) -> Structure:
        from pymatgen.core import Structure, Element
        import re
        
        s = None
        if isinstance(structure_data, Structure):
            s = structure_data.copy()
        elif isinstance(structure_data, dict):
            if "lattice" in structure_data:
                s = Structure.from_dict(structure_data)
            elif "numbers" in structure_data or "symbols" in structure_data:
                 atoms = Atoms.from_dict(structure_data)
                 s = AseAtomsAdaptor.get_structure(atoms)
        elif isinstance(structure_data, Atoms):
            s = AseAtomsAdaptor.get_structure(structure_data)
        elif isinstance(structure_data, str) and os.path.exists(structure_data):
            # If it's a JSON/MSON file, load it using loadfn
            if structure_data.endswith((".json", ".mson")):
                s = loadfn(structure_data)
            else:
                s = Structure.from_file(structure_data)
        
        if s is None:
            raise ValueError(f"Unsupported structure format: {type(structure_data)}")
            
        # Standard cleaning: remove oxidation states, site properties, and STRIP LABELS
        s.remove_oxidation_states()
        for site in s:
            # Reconstruct species with pure element objects to strip labels
            # This is the "canonical" way to clean labels in pymatgen
            new_sp = {Element(sp.symbol): occu for sp, occu in site.species.items()}
            site.species = new_sp
            # Strip all site properties
            site.properties = {}
            
        return s

    def _occu_to_structure(self, ensemble: Ensemble, occupancies: np.ndarray) -> Structure:
        """Convert occupancy array to a sanitized Structure."""
        from pymatgen.core import Composition
        
        # Use ensemble's processor to get structure from occupancy
        processor = ensemble.processor
        structure = processor.structure_from_occupancy(occupancies)
        
        # Sanitize structure: ensure no sites have partial occupancies (disordered species)
        # This happens for inactive sites in smol if the primordial structure was disordered.
        for i, site in enumerate(structure):
            if isinstance(site.species, Composition) and not site.species.is_element:
                # Pick the majority species (exclude Vacancy if possible, or just pick most common)
                best_sp = sorted(site.species.items(), key=lambda x: x[1], reverse=True)[0][0]
                structure.replace(i, best_sp)
                
        return structure

    def sweep_cutoffs_and_train(self, 
                                 disordered_structure: Union[Structure, Dict, str], 
                                 training_data: List[Dict],
                                 fit_method: str = "ls",
                                 cutoff_ranges: Optional[Dict] = None,
                                 save_plot_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Sweep over cutoffs to find the optimal model using BIC.
        """
        from src.utils.structure_utils import load_structures
        if isinstance(disordered_structure, (str, bytes, os.PathLike)):
             loaded = load_structures(disordered_structure)
             if not loaded:
                 raise ValueError(f"Could not load structure from {disordered_structure}")
             prim = loaded[0]
        else:
             prim = self._ensure_pmg_structure(disordered_structure)
        if cutoff_ranges is None:
            cutoff_ranges = {
                2: [3.5, 4.0, 4.5, 5.0, 5.5, 6.0],
                3: [0, 4.0, 4.5, 5.0],
                4: [0, 4.0]
            }
            
        best_bic = float('inf')
        best_results = {}
        all_metrics = []
        
        for c2 in cutoff_ranges.get(2, [5.0]):
            for c3 in cutoff_ranges.get(3, [0]):
                for c4 in cutoff_ranges.get(4, [0]):
                    cutoffs = {2: c2}
                    if c3 > 0: cutoffs[3] = c3
                    if c4 > 0: cutoffs[4] = c4
                    
                    try:
                        self.create_subspace(prim, cutoffs=cutoffs)
                        self.add_training_data(training_data, prim=prim)
                        
                        n_entries = len(self.wrangler.entries)
                        n_params = len(self.subspace)
                        
                        if n_entries < 1:
                            continue
                            
                        res = self.fit_expansion(method=fit_method)
                        if "error" in res:
                            continue
                        
                        mse = res["rmse"]**2
                        bic = n_entries * np.log(max(mse, 1e-10)) + n_params * np.log(n_entries)
                        
                        metric = {"cutoffs": cutoffs, "rmse": res["rmse"], "bic": bic, "num_params": n_params}
                        all_metrics.append(metric)
                        if bic < best_bic:
                            best_bic = bic
                            best_results = metric
                    except Exception:
                        continue
        
        if not best_results:
            return {"error": "No valid model found during sweep. Try more data or smaller cutoffs."}
        
        # Restore best
        self.create_subspace(prim, cutoffs=best_results["cutoffs"])
        self.add_training_data(training_data, prim=prim)
        self.fit_expansion(method=fit_method)
        
        if save_plot_path and all_metrics:
            try:
                plt.figure()
                bics = [m["bic"] for m in all_metrics]
                plt.plot(range(len(bics)), bics, 'o-')
                plt.xlabel("Trial Index")
                plt.ylabel("BIC")
                plt.title("Cutoff Sweep BIC")
                plt.savefig(save_plot_path)
                plt.close()
            except Exception: pass
             
        return {
            "best_cutoffs": best_results["cutoffs"],
            "best_bic": best_bic,
            "rmse": best_results["rmse"],
            "num_params": best_results["num_params"],
            "all_metrics": all_metrics
        }
