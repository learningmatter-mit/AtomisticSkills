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
from mcp.server.fastmcp import FastMCP
from typing import Dict, Any, Optional, List
from pathlib import Path

# Suppress all warnings to prevent protocol pollution
warnings.filterwarnings("ignore")
os.environ["PYTHONWARNINGS"] = "ignore"

from src.utils.dft.atomate2_utils import Atomate2Handler

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Atomate2Server")

# Create MCP server
mcp = FastMCP("atomate2")


@mcp.tool()
def run_atomate2_vasp_calculation(
    structures_path: str,
    output_dir: str,
    preset_type: str = "omat",
    calculation_type: str = "static",
    config: Optional[Dict[str, Any]] = None,
    execution_mode: str = "remote",
    check_only: bool = False,
    job_id: Optional[str] = None,
    remote_settings: Optional[Dict[str, str]] = None,
    bandstructure_mode: str = "line"
) -> str:
    """
    Run VASP calculations using atomate2 flows.
    
    This tool supports MatPES presets (matpes-pbe, matpes-r2scan) and standard MP presets.
    It can run calculations locally (blocking) or remote.
    
    Args:
        structures_path: Path to structure files or directory.
        output_dir: Directory to save results and logs.
        preset_type: VASP input preset ("omat", "mp", "matpes-pbe", "matpes-r2scan").
        calculation_type: "static", "relaxation", "band_structure", or "optics".
        preset_type: VASP input preset ("omat", "mp", "matpes-pbe", "matpes-r2scan", "mp-r2scan").
        calculation_type: "static", "relaxation", or "band_structure".
        config: Optional custom INCAR settings to override preset.
        execution_mode: "local" (blocking) or "remote".
        check_only: If True, only check environment or job status without running.
        job_id: Optional Job ID to check status or extract results from.
        remote_settings: Optional dict for remote execution. 
                        Keys: 'project' (default: remote_perlmutter), 'worker' (default: perlmutter_worker).
        bandstructure_mode: For 'band_structure' type: "line", "uniform", or "both" (default: "line").
        
    Returns:
        Status message or results summary.
    """
    handler = Atomate2Handler(output_dir)
        
    # 1. Job status / Result extraction check
    if job_id:
        if check_only:
            status = handler.check_status(job_id)
            return json.dumps(status, indent=2)
        else:
            results = handler.extract_results(job_id)
            if "error" in results:
                return results["error"]
            return f"Successfully extracted results for {len(results.get('results', []))} jobs."

    # 2. Environment check
    env_checks = handler.check_environment()
    
    if execution_mode == "remote":
        if not env_checks["atomate2"]:
             return f"Environment check failed: atomate2 not found. {env_checks.get('error','')}"
    else:
        if not all([env_checks["atomate2"], env_checks["vasp"], env_checks["potcar"]]):
            return f"Environment check failed: {env_checks['error']}"
    
    if check_only:
        return "Environment is ready for Atomate2 VASP calculations."

    # 3. Load structures
    structures = handler.load_structures(structures_path)
    if not structures:
        return f"No structures found at {structures_path}"

    # 4. Create flows
    if calculation_type == "band_structure":
        config = config or {}
        config["bandstructure_type"] = bandstructure_mode
    elif calculation_type == "optics":
        config = config or {}

    flow_maker = handler.get_flow_maker(preset_type, calculation_type, config)
    flows = []
    
    from datetime import datetime
    job_id = f"atomate2_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    for i, struct in enumerate(structures):
        flow = flow_maker.make(struct)
        flow.name = f"{preset_type}_{calculation_type}_{i}"
        flows.append(flow)

    # 5. Run flows
    if execution_mode == "local":
        from jobflow import run_locally
        all_responses = {}
        for i, flow in enumerate(flows):
            struct_dir = handler.results_dir / f"structure_{i}"
            struct_dir.mkdir(exist_ok=True)
            responses = run_locally(flow, create_folders=True, ensure_success=True, root_dir=str(struct_dir))
            all_responses[str(flow.uuid)] = {"responses": responses, "dir": str(struct_dir)}
        
        import pickle
        with open(handler.output_path / f"{job_id}_responses.pkl", 'wb') as f:
            pickle.dump(all_responses, f)
        
        status = {"status": "completed", "completed": len(flows), "failed": 0, "total": len(flows)}
        with open(handler.output_path / f"{job_id}_status.json", 'w') as f:
            json.dump(status, f)
            
        return f"Calculations completed locally. Job ID: {job_id}"

    elif execution_mode == "remote":
        from jobflow import Flow
        remote_opts = remote_settings or {}
        project = remote_opts.get("project")
        worker = remote_opts.get("worker")
        
        parent_flow = Flow(flows, name=f"batch_{preset_type}_{calculation_type}")
        
        try:
            # Resolve project name
            project = handler.get_project_name(project)
            job_id = handler.run_remote(parent_flow, project_name=project, worker_name=worker)
            return f"Calculations submitted remotely to project '{project}' (worker: {worker}). Job ID: {job_id}."
        except Exception as e:
            return f"Remote submission failed: {e}"
    
    return f"Unknown execution_mode: {execution_mode}"

@mcp.tool()
def get_atomate2_results_by_id(
    job_ids: Optional[List[str]] = None,
    flow_ids: Optional[List[str]] = None,
    project_name: Optional[str] = None,
    save_to_file: Optional[str] = None,
    convert_units: bool = True
) -> Dict[str, Any]:
    """
    Retrieve VASP calculation results from Atomate2 MongoDB by Job IDs or Flow IDs.
    
    Args:
        job_ids: List of Job IDs (UUIDs or DB IDs).
        flow_ids: List of Flow IDs (UUIDs or DB IDs).
        project_name: Name of the jobflow-remote project (default: None, auto-detected).
        save_to_file: Optional path to save the results as a JSON file.
        convert_units: Whether to convert stress from kB to eV/Å³ (default: True).
        
    Returns:
        Dictionary containing the extracted training data and count.
    """
    handler = Atomate2Handler()
    
    # Resolve project name if needed (e.g. for remote results fetching inside handler)
    if not project_name:
         # We try to resolve it, but if it fails (e.g. local only), we catch it or let specific methods handle it.
         # For get_results_by_id, checks happen inside handler, but we can resolve it here to be safe
         try:
             project_name = handler.get_project_name(project_name)
         except Exception:
             pass # Might be local check, so ignore if remote resolution fails

    results = handler.get_results_by_id(
        job_ids=job_ids,
        flow_ids=flow_ids,
        project_name=project_name,
        convert_units=convert_units
    )
    
    if save_to_file:
        save_path = Path(save_to_file)
        save_path.parent.mkdir(parents=True, exist_ok=True)
        with open(save_path, 'w') as f:
            from monty.json import jsanitize
            json.dump(jsanitize(results), f, indent=2)
        return {
            "message": f"Successfully extracted {len(results)} results to {save_to_file}", 
            "count": len(results), 
            "file_path": str(save_path.absolute())
        }
        
    return {"results": results, "count": len(results)}

@mcp.tool()
def get_atomate2_results_by_formula(
    formula: Optional[str] = None,
    chemsys: Optional[str] = None,
    project_name: Optional[str] = None,
    save_to_file: Optional[str] = None,
    convert_units: bool = True,
    limit: int = 100
) -> Dict[str, Any]:
    """
    Retrieve VASP calculation results from Atomate2 MongoDB by chemical formula or system.
    
    Args:
        formula: Chemical formula filter (e.g., "Al2O3").
        chemsys: Chemical system filter (e.g., "Al-O").
        project_name: Name of the jobflow-remote project (default: None, auto-detected).
        save_to_file: Optional path to save the results as a JSON file.
        convert_units: Whether to convert stress from kB to eV/Å³ (default: True).
        limit: Maximum number of results to retrieve (default: 100).
        
    Returns:
        Dictionary containing the extracted training data and count.
    """
    handler = Atomate2Handler()
    
    # Resolve project name if needed
    if not project_name:
         try:
             project_name = handler.get_project_name(project_name)
         except Exception:
             pass

    results = handler.get_results_by_formula(
        formula=formula,
        chemsys=chemsys,
        project_name=project_name,
        convert_units=convert_units,
        limit=limit
    )
    
    if save_to_file:
        save_path = Path(save_to_file)
        save_path.parent.mkdir(parents=True, exist_ok=True)
        with open(save_path, 'w') as f:
            from monty.json import jsanitize
            json.dump(jsanitize(results), f, indent=2)
        return {
            "message": f"Successfully extracted {len(results)} results to {save_to_file}", 
            "count": len(results), 
            "file_path": str(save_path.absolute())
        }
        
    return {"results": results, "count": len(results)}

@mcp.tool()
def get_atomate2_summary(
    project_name: Optional[str] = None,
    save_to_file: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get a summary of the Atomate2 database (total labels, convergence, chemsys distribution).
    
    Args:
        project_name: Name of the jobflow-remote project (default: None, auto-detected).
        save_to_file: Optional path to save the results as a JSON file.
        
    Returns:
        Dictionary with database statistics.
    """
    handler = Atomate2Handler()
    
    try:
        project_name = handler.get_project_name(project_name)
    except Exception as e:
        return {"error": f"Could not determine project name: {str(e)}"}
        
    summary = handler.get_database_summary(project_name=project_name)
    
    if save_to_file:
        save_path = Path(save_to_file)
        save_path.parent.mkdir(parents=True, exist_ok=True)
        with open(save_path, 'w') as f:
            from monty.json import jsanitize
            json.dump(jsanitize(summary), f, indent=2)
            
    return summary

@mcp.tool()
def get_atomate2_recent_jobs(
    project_name: Optional[str] = None,
    limit: int = 10,
    save_to_file: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    List recently completed Job IDs and their status.
    
    Args:
        project_name: Name of the jobflow-remote project (default: None, auto-detected).
        limit: Number of jobs to retrieve.
        save_to_file: Optional path to save the results as a JSON file.
        
    Returns:
        List of job information dictionaries.
    """
    handler = Atomate2Handler()
    
    try:
        project_name = handler.get_project_name(project_name)
    except Exception as e:
        # Return empty list or specific error structure? 
        # Tool expects List[Dict], so maybe return empty and log error, or let it fail?
        # Let's return a list with one error dict to be visible
        return [{"error": f"Could not determine project name: {str(e)}"}]
        
    jobs = handler.get_recent_jobs(project_name=project_name, limit=limit)
    
    if save_to_file:
        save_path = Path(save_to_file)
        save_path.parent.mkdir(parents=True, exist_ok=True)
        with open(save_path, 'w') as f:
            from monty.json import jsanitize
            json.dump(jsanitize(jobs), f, indent=2)
            
    return jobs

@mcp.tool()
def get_atomate2_job_status(
    job_id: str,
    project_name: Optional[str] = None,
    save_to_file: Optional[str] = None
) -> Dict[str, Any]:
    """
    Check the detailed status of a single Atomate2 job by ID.
    
    Args:
        job_id: The Job ID or Flow ID (UUID or DB ID).
        project_name: Name of the jobflow-remote project (default: None, auto-detected).
        save_to_file: Optional path to save the results as a JSON file.
        
    Returns:
        Dictionary with job status information.
    """
    handler = Atomate2Handler()
    
    # helper to check remote status
    try:
        project_name = handler.get_project_name(project_name)
    except Exception:
        pass # Might be local

    status = handler.check_status(job_id, project_name=project_name)
    
    if save_to_file:
        save_path = Path(save_to_file)
        save_path.parent.mkdir(parents=True, exist_ok=True)
        with open(save_path, 'w') as f:
            from monty.json import jsanitize
            json.dump(jsanitize(status), f, indent=2)
            
    return status

if __name__ == "__main__":
    run_fastmcp_server(mcp, mcp_pipe_binary)
