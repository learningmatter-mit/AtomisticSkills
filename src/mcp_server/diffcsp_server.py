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
from typing import Dict, Any, Optional, List
from src.utils.serialization_utils import recursive_tolist
from src.utils.research_utils import get_current_research_dir
import traceback

# Suppress all warnings to prevent protocol pollution
warnings.filterwarnings("ignore")
warnings.filterwarnings("ignore", category=UserWarning)
os.environ["PYTHONWARNINGS"] = "ignore"

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("DiffCSP-Server")

# Initialize FastMCP server
mcp = FastMCP("DiffCSP")

# Global wrapper instances (lazy-loaded per model)
_wrappers: Dict[str, Any] = {}


def _get_wrapper(model_name: str = "mp_csp", device: str = "auto"):
    """Get or create a DiffCSPWrapper instance for the given model.

    Args:
        model_name: Name of the pre-trained model.
        device: Device to run on.

    Returns:
        DiffCSPWrapper instance.
    """
    global _wrappers
    if model_name not in _wrappers:
        from src.utils.mlips.diffcsp.diffcsp_wrapper import DiffCSPWrapper
        _wrappers[model_name] = DiffCSPWrapper(model_name=model_name, device=device)
    return _wrappers[model_name]


@mcp.tool()
def generate_structures_with_symmetry(
    spacegroup: int,
    wyckoff_letters: str,
    atom_types: str,
    model_name: str = "mp_csp",
    num_samples: int = 1,
    step_lr: float = 1e-5,
    batch_size: int = 128,
    device: str = "auto",
    output_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Generate crystal structures with exact composition control using DiffCSP++.

    DiffCSP++ (ICLR 2024) uses space group + Wyckoff positions to constrain generation,
    providing exact control over stoichiometry. For example, to generate Li2ZrCl6:
    specify the appropriate space group, Wyckoff positions, and atom types.

    Args:
        spacegroup: Space group number (1-230).
        wyckoff_letters: Comma-separated Wyckoff position labels (e.g., "2a,4g,4h,4i,4i").
                        Or single-char shorthand (e.g., "adf").
        atom_types: Comma-separated element symbols for each Wyckoff position
                   (e.g., "Zr,Li,Cl,Cl,Cl"). Must have same length as wyckoff_letters.
        model_name: Pre-trained model name. Options:
                   "mp_csp" (default) - Materials Project CSP model
                   "perov_csp" - Perovskite CSP model
                   "mpts_csp" - MPTS-52 CSP model
        num_samples: Number of structure samples to generate (default: 1).
        step_lr: Langevin dynamics step size (default: 1e-5).
        batch_size: Batch size for parallel generation (default: 128).
        device: Device to use ("auto", "cpu", "cuda"). Default: "auto".
        output_dir: Directory to save CIF files. If not provided, saves to research_dir.

    Returns:
        Dictionary with 'num_generated' and 'output_dir'.
    """
    if not output_dir:
        output_dir = str(get_current_research_dir() / "diffcsp" / "symmetry_constrained")
    os.makedirs(output_dir, exist_ok=True)

    wrapper = _get_wrapper(model_name=model_name, device=device)
    result = wrapper.generate_with_symmetry(
        spacegroup=spacegroup,
        wyckoff_letters=wyckoff_letters,
        atom_types=atom_types,
        num_samples=num_samples,
        step_lr=step_lr,
        batch_size=batch_size,
        output_dir=output_dir,
    )
    return {
        "num_generated": result["num_generated"],
        "output_dir": result["output_dir"],
    }


if __name__ == "__main__":
    run_fastmcp_server(mcp, mcp_pipe_binary)
