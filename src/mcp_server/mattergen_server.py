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
os.environ["PYTHONWARNINGS"] = "ignore"

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("MatterGen-Server")

# Initialize FastMCP server
mcp = FastMCP("MatterGen")


@mcp.tool()
def generate_structures(
    num_structures: int = 10,
    model_name: str = "mattergen_base",
    chemical_system: Optional[str] = None,
    properties: Optional[Dict[str, Any]] = None,
    batch_size: int = 10,
    guidance_scale: float = 0.0,
    device: str = "auto",
    output_dir: Optional[str] = None
) -> Dict[str, Any]:
    """
    Generate inorganic material structures using MatterGen.
    
    Args:
        num_structures: Total number of structures to generate (default: 10).
        model_name: Pretrained model to use (default: "mattergen_base").
                   Options: "mattergen_base", "mp_20_base", "dft_mag_density", "chemical_system"
                   NOTE: If chemical_system is provided, this will be automatically set to "chemical_system"
        chemical_system: Chemical system to condition on (e.g., "Li-Zr-Cl").
                        Automatically uses the "chemical_system" model.
                        NOTE: Controls which elements appear, but NOT exact stoichiometry.
        properties: Optional properties to condition on.
                   Examples:
                   - {"dft_mag_density": 0.15}
                   NOTE: chemical_system parameter overrides this
        batch_size: Batch size for generation (default: 10).
        guidance_scale: Diffusion guidance factor (gamma). 
                       0.0 for unconditional, >0 for stronger conditioning.
                       Recommended: 1.0 for chemical_system conditioning
        device: Device to use ("auto", "cpu", "cuda"). Default: "auto"
        output_dir: Directory to save results. If not provided, saves to research_dir.
        
    Returns:
        Dictionary with:
        - 'num_generated': Number of structures generated
        - 'output_dir': Path to output directory
        - 'structures': List of generated structure file paths
    """
    if not output_dir:
        output_dir = str(get_current_research_dir() / "mattergen" / "generated")
    os.makedirs(output_dir, exist_ok=True)
    
    try:
        from src.utils.mlips.mattergen.mattergen_wrapper import MatterGenWrapper
        
        # Auto-select chemical_system model if chemical system is provided
        if chemical_system:
            model_name = "chemical_system"
            properties = {"chemical_system": chemical_system}
            if guidance_scale == 0.0:
                guidance_scale = 1.0  # Use guidance for chemical system conditioning
        
        # Create wrapper with model
        wrapper = MatterGenWrapper(
            model_name=model_name,
            device=device,
            properties_to_condition_on=properties,
            guidance_scale=guidance_scale
        )
        
        # Generate structures
        result = wrapper.generate_structures(
            num_structures=num_structures,
            batch_size=batch_size,
            output_dir=output_dir
        )
        return recursive_tolist(result)
    except Exception as e:
        traceback.print_exc(file=sys.stderr)
        return {"error": f"Generation failed: {str(e)}", "traceback": traceback.format_exc()}


if __name__ == "__main__":
    run_fastmcp_server(mcp, mcp_pipe_binary)

