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
from typing import Dict, Any, Optional
from src.utils.serialization_utils import recursive_tolist
from src.utils.research_utils import get_current_research_dir
import traceback

# Suppress all warnings to prevent protocol pollution
warnings.filterwarnings("ignore")
warnings.filterwarnings("ignore", category=UserWarning)
os.environ["PYTHONWARNINGS"] = "ignore"

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ADiT-Server")

# Initialize FastMCP server
mcp = FastMCP("ADiT")

# Global wrapper instance (lazy-loaded)
_wrapper = None


def _get_wrapper(device: str = "auto") -> "ADiTWrapper":
    """
    Get or create the global ADiTWrapper instance.

    Args:
        device: Device to use ('auto', 'cpu', 'cuda').

    Returns:
        Initialized ADiTWrapper instance.
    """
    global _wrapper
    if _wrapper is None:
        from src.utils.mlips.adit.adit_wrapper import ADiTWrapper
        _wrapper = ADiTWrapper(device=device)
    return _wrapper


@mcp.tool()
def generate_structures(
    generation_type: str = "crystals",
    num_structures: int = 10,
    batch_size: int = 100,
    cfg_scale: float = 2.0,
    device: str = "auto",
    output_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Generate crystal or molecule structures using ADiT (All-atom Diffusion Transformer).

    Args:
        generation_type: Type of structures to generate.
                        "crystals" - Generate periodic crystal structures (MP20-trained, saved as CIF)
                        "molecules" - Generate non-periodic molecules (QM9-trained, saved as XYZ)
        num_structures: Total number of structures to generate (default: 10).
        batch_size: Batch size for generation (default: 100). Larger = faster on GPU.
        cfg_scale: Classifier-free guidance scale (default: 2.0).
                  Higher values produce more "typical" but less diverse structures.
                  Recommended range: 1.0-4.0
        device: Device to use ("auto", "cpu", "cuda"). Default: "auto"
        output_dir: Directory to save results. If not provided, saves to research_dir.

    Returns:
        Dictionary with:
        - 'num_generated': Number of valid structures generated
        - 'output_dir': Path to output directory
        - 'structures': List of generated structure file paths
        - 'generation_type': Type of generation performed
        - 'metadata_path': Path to metadata JSON file
    """
    if not output_dir:
        subdir = "crystals" if generation_type == "crystals" else "molecules"
        output_dir = str(get_current_research_dir() / "adit" / subdir)
    os.makedirs(output_dir, exist_ok=True)

    wrapper = _get_wrapper(device=device)

    result = wrapper.generate_structures(
        generation_type=generation_type,
        num_structures=num_structures,
        batch_size=batch_size,
        cfg_scale=cfg_scale,
        output_dir=output_dir,
    )
    return recursive_tolist(result)


if __name__ == "__main__":
    run_fastmcp_server(mcp, mcp_pipe_binary)
