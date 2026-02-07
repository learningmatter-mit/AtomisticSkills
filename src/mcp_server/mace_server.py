import os
import sys

# Add project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.utils.mcp_utils import setup_mcp_stdout, run_fastmcp_server

# Setup stdout redirection for MCP
mcp_pipe_binary = setup_mcp_stdout()

import logging
import io
import warnings
import json
from pathlib import Path
from mcp.server.fastmcp import FastMCP
from typing import Dict, Any, Optional, Union, List
from src.utils.serialization_utils import recursive_tolist
from src.utils.research_utils import get_current_research_dir
import traceback

# Suppress all warnings to prevent protocol pollution
warnings.filterwarnings("ignore")
warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", module="matplotlib")
os.environ["PYTHONWARNINGS"] = "ignore"

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("MACE-Server")

# Initialize FastMCP server
mcp = FastMCP("MACE")

# Global variables to hold state
wrapper: Optional[Any] = None


@mcp.tool()
def load_model(model_name: str = "MACE-OMAT-0-small", device: str = "auto", task_name: Optional[str] = None) -> str:
    """
    Load a MACE model.
    
    Supported models include:
    - MACE-MH (Multi-Head): 'MACE-MH-1' (latest), 'MACE-MH-0'
    - MACE-MP (Materials Project): 'MACE-MP-small', 'MACE-MP-medium', 'MACE-MP-large'
    - MACE-OMAT (OMAT dataset): 'MACE-OMAT-0-small', 'MACE-OMAT-0-medium'
    - MACE-MATPES: 'MACE-MATPES-PBE-0', 'MACE-MATPES-R2SCAN-0'
    - MACE-OFF (Organic): 'MACE-OFF23-small', 'MACE-OFF23-medium', 'MACE-OFF23-large'
    - Special: 'MACE-ANI-CC', 'MACE-OMOL-extra-large'
    
    Args:
        model_name: Name of the model to load (default: "MACE-OMAT-0-small").
        device: Device to use ("auto", "cpu", "cuda").
        task_name: Optional task name that sets the model's head. 
                  Supported options for multi-head models (MACE-MH): 
                  'omat_pbe' (default), 'matpes_r2scan', 'omol', 'spice_wB97M', 'oc20_usemppbe'.
        
    Returns:
        Confirmation message.
    
    CRITICAL: This tool must be called before using any other tool to load the model into memory.
    """
    global wrapper
    import contextlib
    
    # Isolate execution from stdout/stderr to prevent MCP protocol violation
    # We redirect stdout to sys.stderr (which logs to file) so we don't lose the output,
    # but we keep the actual stdout (MCP pipe) clean.
    # Note: sys.stderr is already redirected to a log file in the header of this script.
    try:
        from src.utils.mlips.mace.mace_wrapper import MACEWrapper
        wrapper = MACEWrapper(model_name=model_name, device=device, head=task_name)
        # Load the model - this might take a while and produce output
        wrapper.load(model_path=model_name if os.path.exists(model_name) else None)
        
        # If task_name is provided, set the head
        if task_name:
            # Set head if the wrapper supports it
            if hasattr(wrapper, "set_head"):
                wrapper.set_head(task_name)
            else:
                logger.warning(f"Model wrapper does not support setting head to {task_name}")
        
        return f"Successfully loaded MACE model: {model_name}"
    except Exception as e:
        logger.error(f"Failed to load model {model_name}: {e}")
        return f"Error loading model: {str(e)}"

@mcp.tool()
def predict_structure(structure_data: Union[Dict[str, Any], str]) -> Dict[str, Any]:
    """
    Predict energy, forces, and stress for a structure.
    
    Args:
        structure_data: Structure data (dict, ASE Atoms, pymatgen Structure, or file path).
    
    Returns:
        Dict: {'energy': eV, 'forces': eV/A, 'stress': eV/A^3}
    """
    global wrapper
    import contextlib
    if wrapper is None or not wrapper.is_loaded:
        return {"error": "Model not loaded. Please call load_model first."}
    
    return recursive_tolist(wrapper.static_calculation(structure_data))

@mcp.tool()
def predict_atomic_features(structure_data: Union[Dict[str, Any], str], output_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Predict atomic latent features (descriptors) for a structure.
    Automatically saves features to the current research directory.
    
    Args:
        structure_data: Structure data (dict, ASE Atoms, pymatgen Structure, or file path).
        output_path: Optional custom path for saving features. If not provided, auto-generates
                     based on structure filename (e.g., 'solid.cif' -> 'solid_features.json').
    
    Returns:
        Dict: {
            'atomic_features': [[...], ...], 
            'feature_dim': int, 
            'num_atoms': int,
            'saved_path': str  # Path to saved JSON file
        }
    """
    global wrapper
    import contextlib
    import json
    from pathlib import Path
    from src.utils.research_utils import get_current_research_dir
    
    if wrapper is None or not wrapper.is_loaded:
        return {"error": "Model not loaded. Please call load_model first."}
    
    # Get features
    result = wrapper.predict_atomic_features(structure_data)
    
    if "error" in result:
        return result
    
    # Save to research directory
    try:
        # Use custom path if provided, otherwise auto-generate
        if output_path:
            save_path = Path(output_path)
        else:
            research_dir = get_current_research_dir()
            
            # Generate filename based on structure path or use generic name
            if isinstance(structure_data, str):
                struct_path = Path(structure_data)
                feature_filename = f"{struct_path.stem}_features.json"
            else:
                feature_filename = "atomic_features.json"
            
            save_path = research_dir / feature_filename
        
        # Save features
        with open(save_path, 'w') as f:
            json.dump(recursive_tolist(result), f)
        
        # Add saved path to result
        result["saved_path"] = str(save_path)
        
        # Remove heavy data from return value
        if "atomic_features" in result:
            del result["atomic_features"]
        
        return result
        
    except Exception as e:
        # If saving fails, still return the features but with error info
        result["save_error"] = f"Failed to save features: {str(e)}"
        return result

@mcp.tool()
def relax_structure(
    structure_data: Union[Dict[str, Any], str, List[Union[Dict[str, Any], str]]],
    fmax: float = 0.02,
    steps: int = 500,
    optimizer: str = "FIRE",
    relax_cell: bool = True,
    output_dir: Optional[str] = None,
    fixed_atoms: Optional[List[int]] = None
) -> Dict[str, Any]:
    """
    Relax one or multiple structures using the loaded MACE model.
    
    Args:
        structure_data: Can be:
            - Single structure (dict, ASE Atoms, pymatgen Structure, or file path)
            - Directory path containing CIF/POSCAR files (batch mode)
            - List of file paths (batch mode)
            - List of structure dicts (batch mode)
        fmax: Force convergence criterion (eV/Ang).
        steps: Maximum number of optimization steps.
        optimizer: Optimizer to use ("FIRE", "BFGS", "LBFGS").
        relax_cell: Whether to relax the unit cell.
        output_dir: Directory to save results. For batch mode, each structure gets a subdirectory.
        fixed_atoms: List of indices of atoms to keep fixed during relaxation.
        
    Returns:
        For single: Dict with energy, trajectory_path, cif_path, json_path
        For batch: Dict with mode="batch", total_structures, successful, failed, results list
    """
    global wrapper
    if wrapper is None or not wrapper.is_loaded:
        return {"error": "Model not loaded. Please call load_model first."}
    
    # Simply delegate to base wrapper's unified relax_structure method
    return recursive_tolist(wrapper.relax_structure(
        structure_data=structure_data,
        fmax=fmax,
        steps=steps,
        optimizer=optimizer,
        relax_cell=relax_cell,
        output_dir=output_dir,
        fixed_atoms=fixed_atoms
    ))

@mcp.tool()
def run_md(
    structure_data: Union[Dict[str, Any], str],
    temperature: float = 300.0,
    steps: int = 1000,
    timestep: float = 1.0,
    ensemble: str = "nvt",
    log_interval: int = 10,
    pressure: float = 0.0,
    pressure_mask: Optional[List[int]] = None,
    output_dir: Optional[str] = None,
    monitor: bool = False,
    monitor_type: Optional[Union[str, List[str]]] = None,
    monitor_params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Run molecular dynamics simulation using MatCalc.
    
    Args:
        structure_data: Structure data.
        temperature: Temperature in Kelvin.
        steps: Number of steps.
        timestep: Timestep in fs.
        ensemble: Ensemble "nve", "nvt" (Nose-Hoover), or "npt" (NPT).
                  Also supports variants like "nvt_langevin", "nvt_andersen", "npt_berendsen", "npt_mtk".
        log_interval: Interval for logging to trajectory and logfile.
        pressure: Target pressure in bar (for NPT).
        pressure_mask: Mask for anisotropic NPT (e.g., [1, 0, 0] for 1D).
        output_dir: Directory to save results.
        monitor: Whether to enable automatic MD monitoring.
        monitor_type: Type of monitor ("melting", "explosion", "overshoot", "volume") 
                     or a list of types.
        monitor_params: Optional dictionary of parameters for the monitors 
                        (e.g., {"upper_limit_ratio": 4.0}).
        
    Returns:
        Dictionary with MD results.
    """
    if wrapper is None or not wrapper.is_loaded:
        return {"error": "Model not loaded. Please call load_model first."}

    # Setup Directory
    if not output_dir:
        output_dir = str(get_current_research_dir() / "mace" / "md")
    os.makedirs(output_dir, exist_ok=True)

    import contextlib
    import traceback
    import sys # Added for sys.stderr
    
    try:
        # Run MD via wrapper's unified run_md (supports monitoring callbacks)
        result = wrapper.run_md(
            structure_data=structure_data,
            temperature=temperature,
            steps=steps,
            timestep=timestep,
            ensemble=ensemble,
            log_interval=log_interval,
            pressure=pressure,
            pressure_mask=pressure_mask,
            output_dir=output_dir,
            monitor=monitor,
            monitor_type=monitor_type,
            monitor_params=monitor_params
        )
        
        if "error" in result:
            return result
            
        return recursive_tolist(result)
            
    except Exception as e:
        traceback.print_exc(file=sys.stderr) # Reverted to original traceback.print_exc
        return {"error": f"MD execution failed: {str(e)}", "traceback": traceback.format_exc()}



@mcp.tool()
def fine_tune_model(
    training_data_path: str,
    epochs: int = 10,
    learning_rate: float = 1e-4,
    output_dir: Optional[str] = None,
    training_config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Fine-tune the current MACE model.
    
    Args:
        training_data_path: Path to a JSON file containing the training data list.
                             Each sample must have:
                               - 'structure': Dict (ASE atoms or pymatgen format)
                               - 'energy': Total potential energy (float, eV)
                               - 'forces': Atomic forces (list/array, eV/A)
                               - 'stress': (Optional) Stress tensor (list/array) in eV/A^3.
        epochs: Number of training epochs.
        learning_rate: Learning rate.
        output_dir: Directory to save the fine-tuned model.
        training_config: Optional dictionary for advanced configuration.
        
    Returns:
        Dictionary with fine-tuning results.
    """
    import json
    import contextlib
    global wrapper
    if wrapper is None or not wrapper.is_loaded:
        return {"error": "Model not loaded. Please call load_model first."}
    
    if not output_dir:
        output_dir = str(get_current_research_dir() / "mace" / "fine_tuning")
        
    # Load training data
    try:
        with open(training_data_path, 'r') as f:
            training_data = json.load(f)
    except Exception as e:
        return {"error": f"Failed to load training data from {training_data_path}: {e}"}
        
    # Prepare config
    config = training_config or {}
    config.update({
        "max_epochs": epochs,
        "learning_rate": learning_rate
    })
        
    result = wrapper.fine_tune(
        training_data=training_data,
        output_dir=output_dir,
        training_config=config
    )
    return recursive_tolist(result)

@mcp.tool()
def get_info() -> Dict[str, Any]:
    """
    Get information about the current loaded model.
    
    Returns:
        Dictionary with model status, name, device, and head.
    """
    global wrapper
    import contextlib
    if wrapper is None:
        return {"status": "no model loaded"}
    
    return {
        "status": "loaded",
        "model_name": wrapper.model_name,
        "device": str(wrapper.device),
        "head": wrapper.head,
        "is_mh": getattr(wrapper, "is_mh", False)
    }

if __name__ == "__main__":
    run_fastmcp_server(mcp, mcp_pipe_binary)
