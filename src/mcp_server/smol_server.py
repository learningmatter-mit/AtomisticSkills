import os
import sys

# Add project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.utils.mcp_utils import setup_mcp_stdout, run_fastmcp_server

# Setup stdout redirection for MCP
mcp_pipe_binary = setup_mcp_stdout()

import io
import logging
import contextlib
import warnings
import json
from pathlib import Path
from mcp.server.fastmcp import FastMCP
from typing import Dict, Any, Optional, List, Union
import numpy as np

# Silence warnings to prevent protocol pollution
os.environ["PYTHONWARNINGS"] = "ignore"
warnings.filterwarnings("ignore")

logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger("Smol-Server")

# Initialize FastMCP server
mcp = FastMCP("Smol")
from src.utils.disordered_material.smol_utils import SmolWrapper
from src.utils.research_utils import get_current_research_dir

# Global wrapper removed for stateless operation
# wrapper = SmolWrapper()


@mcp.tool()
def sample_ordered_structures(
    disordered_structure: Union[Dict[str, Any], str],
    cutoffs: Dict[int, float],
    num_structures: int = 1000,
    target_num_sites: int = 32,
    basis_set: str = "chebyshev",
    max_cluster_size: int = 2,
    output_dir: Optional[str] = None
) -> Dict[str, Any]:
    """
    Generate diverse ordered structures for iteration 0 via enumeration and D-optimality.
    
    Args:
        disordered_structure: Path to structure or dict representation.
        cutoffs: Dict of cluster sizes to cutoffs.
        num_structures: Target number of structures (default 1000).
        target_num_sites: Target supercell size for enumeration.
        basis_set: Basis set type.
        max_cluster_size: Max cluster size.
        output_dir: Optional directory to save CIF files. 
                    If not provided, uses 'smol_ordered_structures' in research dir.
    """
    wrapper = SmolWrapper()
    try:
        structs = wrapper.sample_ordered_structures(
            disordered_structure=disordered_structure,
            cutoffs=cutoffs,
            num_structures=num_structures,
            target_num_sites=target_num_sites,
            basis_set=basis_set,
            max_cluster_size=max_cluster_size
        )
        
        if not output_dir:
            output_dir = str(get_current_research_dir() / "smol_ordered_structures")
        
        os.makedirs(output_dir, exist_ok=True)
        
        saved_paths = []
        for i, s in enumerate(structs):
            path = os.path.join(output_dir, f"ordered_struct_{i}.cif")
            s.to(fmt="cif", filename=path)
            saved_paths.append(path)
            
        return {
            "status": "success",
            "count": len(structs),
            "output_dir": output_dir,
            "sample_path": saved_paths[0] if saved_paths else None
        }
    except Exception as e:
        return {"error": f"Structure sampling failed: {str(e)}"}

@mcp.tool()
def train_cluster_expansion(
    disordered_structure: Union[Dict[str, Any], str],
    training_data: Union[List[Dict[str, Any]], Dict[str, Any], str],
    cutoffs: Optional[Dict[int, float]] = None,
    max_cluster_size: int = 2,
    basis_set: str = "chebyshev",
    fit_method: str = "ls",
    alpha: float = 1.0,
    ce_file: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create a cluster subspace, add training data, and fit a cluster expansion.
    
    This tool orchestrates the full training workflow for a cluster expansion model.
    If 'cutoffs' is NOT provided, it will automatically sweep over 2/3/4-body cutoffs
    to find the optimal model based on BIC, and generate a plot.
    
    The resulting Cluster Expansion is saved to disk.
    
    Args:
        disordered_structure: Disordered structure (dict or file path, .cif is preferred).
        training_data: Training data source. Can be:
            - Path to a DIRECTORY containing relaxation results (e.g. from mcp_mace_relax_structure).
              The tool will recursively search for 'relaxation_results.json', 'result.json', 
              or 'relaxed_structure.cif' + 'relaxed_energy.txt'.
            - List of calculation dictionaries.
            - Path to a JSON file containing the list.
        cutoffs: Dict of cluster sizes to cutoff distances (e.g., {2: 5.0, 3: 4.0}).
                 If None, an automatic sweep is performed.
        max_cluster_size: Maximum cluster size to include (used if cutoffs provided).
        basis_set: Basis set type ("chebyshev", "sinusoid", "indicator").
        fit_method: Fitting method ('ls', 'lasso', 'ridge').
        alpha: Regularization parameter for Lasso/Ridge.
        ce_file: Optional path to save the CE. If not provided, it will be saved 
                 in the current research directory as 'cluster_expansion.json'.
        
    Returns:
        Dictionary with fitting results (RMSE, coefficient count) and sweep metrics.
    """
    wrapper = SmolWrapper()
    try:
        # Determine save path
        if not ce_file:
            ce_dir = get_current_research_dir() / "smol"
            os.makedirs(ce_dir, exist_ok=True)
            ce_file = str(ce_dir / "cluster_expansion.json")
            
        # Branch 1: Automatic Sweep (if cutoffs is None)
        if cutoffs is None:
            # Prepare plot path
            plot_path = str(Path(ce_file).parent / "cutoff_sweep_bic.png")
            
            # Run sweep
            sweep_res = wrapper.sweep_cutoffs_and_train(
                disordered_structure=disordered_structure,
                training_data=training_data,
                fit_method=fit_method,
                save_plot_path=plot_path
            )
            
            if "error" in sweep_res:
                return sweep_res
            
            # Save the best model
            save_msg = wrapper.save_ce(ce_file)
            
            sweep_res["save_status"] = save_msg
            sweep_res["ce_file"] = ce_file
            return sweep_res

        # Branch 2: Standard Validation/Train (if cutoffs provided)
        # 1. Create subspace
        subspace_msg = wrapper.create_subspace(
            disordered_structure=disordered_structure,
            cutoffs=cutoffs,
            max_cluster_size=max_cluster_size,
            basis_set=basis_set
        )
        
        # 2. Add training data
        data_msg = wrapper.add_training_data(training_data)
        
        # 3. Fit expansion
        kwargs = {}
        if fit_method in ["lasso", "ridge"]:
            kwargs["alpha"] = alpha
        
        fit_res = wrapper.fit_expansion(method=fit_method, **kwargs)
        
        # 4. Save CE
        save_msg = wrapper.save_ce(ce_file)
        
        # Add messages to result
        if "status" in fit_res:
            fit_res["subspace_status"] = subspace_msg
            fit_res["data_status"] = data_msg
            fit_res["save_status"] = save_msg
            fit_res["ce_file"] = ce_file
        
        return fit_res
        
    except Exception as e:
        return {"error": f"Training failed: {str(e)}"}

@mcp.tool()
def run_monte_carlo(
    supercell_matrix: List[List[int]],
    temperature: float,
    steps: int,
    ensemble_type: str = "canonical",
    ce_file: Optional[str] = None,
    trajectory_file: Optional[str] = None,
    log_interval: int = 1,
    initial_composition: Optional[Dict[str, float]] = None
) -> Dict[str, Any]:
    """
    Run Monte Carlo simulation using the fitted Cluster Expansion.

    Args:
        supercell_matrix: 3x3 matrix defining the supercell to run MC on.
        temperature: Simulation temperature in Kelvin.
        steps: Number of MC steps to run.
        ensemble_type: "canonical" or "semigrand".
        ce_file: Path to the Cluster Expansion file. 
                 REQUIRED: Default loading is removed. You must provide the path.
        trajectory_file: Optional path to save the MC trajectory (HDF5 format).
        log_interval: Interval for saving samples.
        initial_composition: Optional JSON string for initial composition (e.g. '{"Li": 0.5, "Ag": 0.5}').
                             If provided, generates a random initial structure with this composition.
    """
    try:
        if not ce_file:
             return {"error": "ce_file argument is required."}

        wrapper = SmolWrapper()
        load_status = wrapper.load_ce(ce_file)
        if "Error" in load_status:
            return {"error": load_status}
        
        comp_dict = initial_composition

        return wrapper.run_mc(
            supercell_matrix=supercell_matrix,
            temperature=temperature,
            steps=steps,
            ensemble_type=ensemble_type,
            trajectory_file=trajectory_file,
            log_interval=log_interval,
            initial_composition=comp_dict
        )
    except Exception as e:
        return {"error": f"Monte Carlo failed: {str(e)}"}

@mcp.tool()
def compute_feature_vectors(
    structures: List[Any],
    ce_file: Optional[str] = None
) -> Dict[str, Any]:
    """
    Compute feature vectors (correlations) for a list of structures using the current Cluster Expansion.
    
    Args:
        structures: List of structures (dicts or file paths).
        ce_file: Optional path to load ClusterExpansion/Subspace if not already in memory.
        
    Returns:
        Dict with keys 'features' (list of vectors), 'valid_indices', and 'errors'.
    """
    wrapper = SmolWrapper()
    try:
        if ce_file:
            wrapper.load_ce(ce_file)
            
        if wrapper.subspace is None:
             return {"error": "No ClusterSubspace loaded. Please provide 'ce_file'."}
        
        return wrapper.compute_feature_vectors(structures)
    except Exception as e:
        return {"error": str(e)}

@mcp.tool()
def get_feature_matrix(ce_file: str) -> Dict[str, Any]:
    """
    Get the feature matrix of the current training set.
    """
    wrapper = SmolWrapper()
    try:
        load_res = wrapper.load_ce(ce_file)
        if "Error" in load_res: return {"error": load_res}

        if wrapper.wrangler is None:
             return {"error": "No training data available in loaded CE."}
        
        return {
            "feature_matrix": wrapper.get_feature_matrix(),
            "shape": list(np.shape(wrapper.get_feature_matrix()))
        }
    except Exception as e:
        return {"error": str(e)}

@mcp.tool()
def fit_feature_matrix(
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
    Fit a feature matrix directly, typically used with SGL or external pipelines.

    Args:
        feature_matrix_path: Path to .npy file of the feature matrix (n_samples, n_features)
        energies_path: Path to .npy file of the energies (n_samples,)
        groups_path: Path to .npy file of the groups (n_features,)
        fit_method: "ls", "lasso", "ridge", or "sgl" (Sparse Group Lasso)
        alpha: Regularization parameter for Lasso/Ridge/SGL
        lambda_mixing: L1/L2 mixing parameter for SGL
        point_features_count: For SGL, the first N features (typically 1 constant + point clusters) 
                              that are not penalized via the group penalty.
        test_size: Test split ratio for RMSE evaluation

    Returns:
        Dictionary with fitting results, including training RMSE, testing RMSE, and coefficient count.
    """
    try:
        wrapper = SmolWrapper()
        return wrapper.fit_feature_matrix(
            feature_matrix_path=feature_matrix_path,
            energies_path=energies_path,
            groups_path=groups_path,
            fit_method=fit_method,
            alpha=alpha,
            lambda_mixing=lambda_mixing,
            point_features_count=point_features_count,
            test_size=test_size
        )
    except Exception as e:
        import traceback
        return {"error": f"Direct feature matrix fitting failed: {str(e)}\n{traceback.format_exc()}"}


@mcp.tool()
def check_mapping(
    initial_structure: Union[Dict[str, Any], str],
    relaxed_structure: Union[Dict[str, Any], str]
) -> Dict[str, Any]:
    """
    Check if a relaxed structure still maps to the same configuration (correlation vector)
    as the initial structure.
    
    Args:
        initial_structure: The structure before relaxation.
        relaxed_structure: The structure after relaxation.
        
    Returns:
        Dict with 'match' (bool) and optionally error message.
    """
    wrapper = SmolWrapper()
    try:
        match = wrapper.is_same_configuration(initial_structure, relaxed_structure)
        return {"match": match}
    except Exception as e:
        return {"error": str(e), "match": False}


if __name__ == "__main__":
    run_fastmcp_server(mcp, mcp_pipe_binary)
