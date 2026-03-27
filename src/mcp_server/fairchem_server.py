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
import json
from pathlib import Path
from mcp.server.fastmcp import FastMCP
from typing import Dict, Any, Optional, List, Union
from src.utils.serialization_utils import recursive_tolist
from src.utils.research_utils import get_current_research_dir

# Configure logging to go to the real stderr
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastMCP server
mcp = FastMCP("FAIRCHEM")

# Global variables to hold state
wrapper: Optional[Any] = None


@mcp.tool()
def load_model(
    model_name: str = "uma-s-1p1", 
    device: str = "auto", 
    task_name: Optional[str] = None,
    inference_settings: str = "default"
) -> str:
    """
    Load a FAIRCHEM model.
    
    Supported models include:
    - UMA (Universal): 'uma-s-1p1', 'uma-m-1p1', 'uma-s-1'
    - ESEN (Organic/Molecular): 'esen-md-direct-all-omol', 'esen-sm-conserving-all-omol', 'esen-sm-direct-all-omol'
    - ESEN (Catalysis/OC25): 'esen-sm-conserving-all-oc25', 'esen-md-direct-all-oc25'
    - Fine-tuned checkpoint: provide the full path to an inference_ckpt.pt file
    
    Args:
        model_name: Name of the model to load (default: "uma-s-1p1").
                   Can also be a file path to a fine-tuned inference checkpoint
                   (e.g., "/path/to/inference_ckpt.pt" from fairchem CLI fine-tuning).
        device: Device to use ("auto", "cpu", "cuda").
        task_name: Optional task name for UMA multi-task models.
                  'omat' (default for bulk/periodic): Inorganic materials (PBE-level, OMat24 dataset).
                  'omol': Molecules and polymers (PBE-level).
                  'oc20': Heterogeneous catalysis / surface reactions (PBE-level).
                  'odac': Metal-Organic Frameworks / CO2 capture (PBE-level).
                  'omc': Molecular crystals (PBE-level).
        inference_settings: Inference settings preset (default: "default").
    
    Returns:
        Confirmation message.
    
    CRITICAL: This tool must be called before using any other tool to load the model into memory.
    """
    global wrapper
    try:
        # Lazy import to speed up server startup and avoid timeout
        from src.utils.mlips.fairchem.fairchem_wrapper import FAIRCHEMWrapper
        
        wrapper = FAIRCHEMWrapper(
            model_name=model_name, 
            device=device, 
            task_name=task_name,
            inference_settings=inference_settings
        )
        wrapper.load()
        return f"Successfully loaded FAIRCHEM model: {model_name}"
    except Exception as e:
        return f"Error loading model: {str(e)}"

@mcp.tool()
def predict_structure(structure_data: Union[Dict[str, Any], str, List[Union[Dict[str, Any], str]]]) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
    """
    Predict energy, forces, and stress for a structure or a batch of structures.
    
    Args:
        structure_data: Single structure or batch (directory path, list of dicts/paths).
            
    Returns:
        Dict: {'energy': eV, 'forces': eV/A, 'stress': eV/Å³}
    """
    global wrapper
    if wrapper is None:
        return {"error": "Model not loaded. Please call load_model first."}
    
    return wrapper.static_calculation(structure_data)
    

@mcp.tool()
def get_info() -> Dict[str, Any]:
    """
    Get information about the current loaded model.
    """
    global wrapper
    if wrapper is None:
        return {"status": "no_model_loaded"}
    return wrapper.get_model_info()


@mcp.tool()
def relax_structure(
    structure_data: Union[Dict[str, Any], str, List[Union[Dict[str, Any], str]]],
    fmax: float = 0.02,
    steps: int = 500,
    optimizer: str = "FIRE",
    relax_cell: bool = True,
    output_dir: Optional[str] = None
) -> Dict[str, Any]:
    """
    Relax one or multiple structures using the loaded FAIRCHEM model.
    
    Args:
        structure_data: Single structure or batch (directory path, list of dicts/paths).
        fmax: Force convergence criterion (eV/Ang).
        steps: Maximum number of optimization steps.
        optimizer: Optimizer to use ("FIRE", "BFGS", "LBFGS").
        relax_cell: Whether to relax the unit cell (default: True).
        output_dir: Directory to save results. For batch mode, each structure gets a subdirectory.
        
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
        relax_cell=relax_cell,  # Use passed argument
        output_dir=output_dir
    ))

@mcp.tool()
def run_md(
    structure_data: Union[Dict[str, Any], str, List[Union[Dict[str, Any], str]]],
    temperature: float = 300,
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
    supercell_min_length: Optional[float] = None
) -> Dict[str, Any]:
    """
    Run molecular dynamics simulation using MatCalc.
    
    Args:
        structure_data: Single structure or batch (directory path, list of dicts/paths).
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
        monitor_type: Type of monitor ("melting", "explosion", "overshoot", "volume") or list of types.
        monitor_params: Optional dictionary of parameters for the monitors (e.g., {"upper_limit_ratio": 4.0}).
        supercell_min_length: Minimum length (Å) for each lattice vector. Automatically expands supercell.
        
    Returns:
        Dictionary with MD results (trajectory_path, final_structure).
    """
    global wrapper
    if wrapper is None or not wrapper.is_loaded:
        return {"error": "Model not loaded. Please call load_model first."}
        
    # Setup Directory
    if not output_dir:
        output_dir = str(get_current_research_dir() / "fairchem" / "md")
    os.makedirs(output_dir, exist_ok=True)

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
            monitor_params=monitor_params,
            supercell_min_length=supercell_min_length
        )
        
        return recursive_tolist(result)
            
    except Exception as e:
        import traceback
        traceback.print_exc(file=sys.stderr)
        return {"error": f"MD execution failed: {str(e)}", "traceback": traceback.format_exc()}


if __name__ == "__main__":
    run_fastmcp_server(mcp, mcp_pipe_binary)

