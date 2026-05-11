import os
import sys
import json
import re
import subprocess
from datetime import datetime
from typing import Optional, Dict, Any, List
from pathlib import Path

try:
    from mcp.server.fastmcp import FastMCP
    mcp = FastMCP("htvs")
except ImportError:
    # Fallback for environments without FastMCP (e.g., standalone scripts in htvs-agent)
    class DummyMCP:
        def tool(self, *args, **kwargs):
            return lambda x: x
    mcp = DummyMCP()

try:
    from src.utils.htvs import (
        HTVSConfigHandler,
        run_htvs_script,
        HTVSJobHandler,
        HTVSVaspHandler,
        HTVSDbHandler,
    )
    HTVS_UTILS_AVAILABLE = True
except ImportError:
    HTVS_UTILS_AVAILABLE = False

# --- GLOBAL HTVS CONTEXT ---
GLOBAL_HTVS_CONTEXT = {
    "settings_module": None,
    "group_name": None
}

def _log_to_research_dir(tool_name: str, data: Dict[str, Any]):
    """Helper to log tool results to the current research directory if active."""
    try:
        from src.utils.research_utils import get_current_research_dir
        res_dir = get_current_research_dir()
        if res_dir:
            log_file = Path(res_dir) / f"{tool_name}_tracking.json"
            
            # Load existing if available
            history = []
            if log_file.exists():
                try:
                    with open(log_file, "r") as f:
                        history = json.load(f)
                        if not isinstance(history, list):
                            history = [history]
                except Exception:
                    history = []
            
            history.append(data)
            
            with open(log_file, "w") as f:
                json.dump(history, f, indent=2)
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Failed to log {tool_name} to research dir: {e}")

@mcp.tool()
def htvs_get_config() -> str:
    """
    Retrieve the current resolved HTVS configuration from environment and ~/.atomistic_skills.yaml.
    Use this to verify compute_platform, inbox_path, and other global settings.
    """
    if not HTVS_UTILS_AVAILABLE:
        return "Error: HTVS utilities not available."
    
    config = HTVSConfigHandler().load_config()
    return json.dumps(config, indent=2)


@mcp.tool()
def htvs_set_project_context(settings_module: Optional[str] = None, group_name: Optional[str] = None) -> str:
    """
    Set the global database configuration and project group for all subsequent HTVS operations.
    If arguments are omitted, attempts to load defaults from ~/.atomistic_skills.yaml.
    
    Args:
        settings_module: Django settings module name (e.g., 'orgel').
        group_name: HTVS project group name.
    """
    msg = ""
    if settings_module is None or group_name is None:
        config = HTVSConfigHandler().load_config()
        if settings_module is None:
            settings_module = config.get("settings_module")
            msg += f" (settings_module resolved to '{settings_module}')"
        if group_name is None:
            group_name = config.get("group_name")
            msg += f" (group_name resolved to '{group_name}')"

    GLOBAL_HTVS_CONTEXT["settings_module"] = settings_module
    GLOBAL_HTVS_CONTEXT["group_name"] = group_name
    return f"Successfully set global HTVS context: settings_module='{settings_module}', group_name='{group_name}'.{msg}"

def _get_context(settings_module: Optional[str] = None, group_name: Optional[str] = None):
    s = settings_module if settings_module is not None else GLOBAL_HTVS_CONTEXT.get("settings_module")
    g = group_name if group_name is not None else GLOBAL_HTVS_CONTEXT.get("group_name")
    
    if not s or not g:
        config = HTVSConfigHandler().load_config()
        s = s or config.get("settings_module")
        g = g or config.get("group_name")
        
    if not s:
        raise ValueError("settings_module is required. Pass it via argument, call htvs_set_project_context, or set it in ~/.atomistic_skills.yaml.")
    if not g:
        raise ValueError("group_name is required. Pass it via argument, call htvs_set_project_context, or set it in ~/.atomistic_skills.yaml.")
        
    return s, g


import functools
import inspect

def require_htvs_context(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        if not HTVS_UTILS_AVAILABLE:
            import json
            return json.dumps({"error": "HTVS utilities not available"})
        
        sig = inspect.signature(func)
        bound = sig.bind(*args, **kwargs)
        bound.apply_defaults()
        
        sm = bound.arguments.get('settings_module')
        gn = bound.arguments.get('group_name')
        
        try:
            s, g = _get_context(sm, gn)
            if 'settings_module' in bound.arguments:
                bound.arguments['settings_module'] = s
            if 'group_name' in bound.arguments:
                bound.arguments['group_name'] = g
        except ValueError as e:
            return f"Error: {e}"
            
        return func(*bound.args, **bound.kwargs)
    return wrapper


@mcp.tool()
@require_htvs_context
def save_htvs_structure(
    structure_file: str,
    config_name: str,
    group_name: Optional[str] = None,
    settings_module: Optional[str] = None,
    structure_type: str = "auto",
    parent_bulk_id: Optional[int] = None,
    miller_index: Optional[List[int]] = None,
    method_name: Optional[str] = None,
    framework_name: Optional[str] = None,
    djangochem_dir: Optional[str] = None,
    htvs_dir: Optional[str] = None,
) -> str:
    """
    Save structures to HTVS database with automatic type detection.
    
    Automatically detects whether to save as Crystal or Surface based on
    provided parameters or structure properties. Extensible for future
    Molecule support.
    
    Args:
        structure_file: Absolute path to the structure file (must be readable by ase.io).
        config_name: Name of the JobConfig to use as the parent config.
        group_name: Name of the project/group.
        settings_module: Django settings module.
        structure_type: Type of structure ("auto", "crystal", "surface", "molecule").
                       "auto" will detect based on parent_bulk_id and structure properties.
        parent_bulk_id: ID of the parent Crystal or Surface (required for surfaces).
        miller_index: List of 3 integers for Miller index (e.g. [1, 1, 1]).
                     Defaults to [0, 0, 1] for surfaces.
        method_name: Optional name of the Method to associate with the structures.
        framework_name: Optional name of the Framework to associate with the structures.
        djangochem_dir: Optional override for DJANGOCHEM_DIR.
        htvs_dir: Optional override for HTVS_DIR.
        
    Returns:
        JSON string containing list of created structure IDs.
        
    Auto-detection logic:
        - If parent_bulk_id is provided → Surface
        - If structure has ASE tags → Surface  
        - Otherwise → Crystal
        - Future: Molecule detection based on lack of periodicity
    """
    
    # Auto-detect structure type
    if structure_type == "auto":
        if parent_bulk_id is not None:
            structure_type = "surface"
        else:
            # Read first structure to check for surface markers
            try:
                from ase.io import read
                atoms = read(structure_file, index=0)
                # Check for ASE tags indicating surface atoms
                if hasattr(atoms, 'get_tags') and any(atoms.get_tags()):
                    structure_type = "surface"
                else:
                    structure_type = "crystal"
            except Exception:
                # Default to crystal if cannot read
                structure_type = "crystal"
    
    # Create handler
    handler = HTVSDbHandler(settings_module, djangochem_dir, htvs_dir)
    
    # Dispatch to appropriate method
    if structure_type == "crystal":
        result = handler.save_crystals(
            structure_file=structure_file,
            config_name=config_name,
            group_name=group_name,
            method_name=method_name,
            framework_name=framework_name
        )
    elif structure_type == "surface":
        if miller_index is None:
            miller_index = [0, 1, 0]
        if parent_bulk_id is None:
            import json
            return json.dumps({"error": "parent_bulk_id required for surface structures"})
        result = handler.save_surfaces(
            structure_file=structure_file,
            config_name=config_name,
            parent_bulk_id=parent_bulk_id,
            group_name=group_name,
            miller_index=miller_index,
            method_name=method_name,
            framework_name=framework_name
        )
    # Future: elif structure_type == "molecule":
    #     return handler.save_molecules(...)
    else:
        import json
        return json.dumps({"error": f"Unknown structure_type: {structure_type}. Use 'auto', 'crystal', 'surface', or 'molecule'"})

    # Log to research dir
    try:
        ids_data = json.loads(result)
        _log_to_research_dir("save_htvs_structure", {
            "timestamp": datetime.now().isoformat(),
            "structure_file": structure_file,
            "structure_type": structure_type,
            "config_name": config_name,
            "group_name": group_name,
            "ids": ids_data
        })
    except Exception:
        pass

    return result


@mcp.tool()
@require_htvs_context
def prepare_vasp_job_details(
    structure_file: str,
    preset_type: str = "mp",
    calculation_type: str = "static",
    custom_settings: Optional[Dict[str, Any]] = None,
    magnetism: bool = True,
    magnetism_scheme: str = "fm",
) -> str:
    """
    Prepare VASP job details (INCAR parameters) using Pymatgen presets.
    
    Generates comprehensive VASP input parameters from a structure file using
    Pymatgen's preset input sets. Returns JSON-formatted details ready for
    HTVS job submission.
    
    Args:
        structure_file: Path to the structure file (readable by ASE/Pymatgen).
        preset_type: Pymatgen preset to use ("mp", "omat", "matpes-pbe", "matpes-r2scan").
        calculation_type: "static" or "relaxation".
        custom_settings: Dictionary of custom settings to override defaults.
        magnetism: Whether to apply default magnetic moments.
        magnetism_scheme: "fm" (ferromagnetic), "afm" (antiferromagnetic), or "nm" (non-magnetic).

    Returns:
        JSON string of the 'details' dictionary ready for HTVS submission.
    """
    
    handler = HTVSVaspHandler()
    return handler.generate_details(
        structure_file=structure_file,
        preset_type=preset_type,
        calculation_type=calculation_type,
        custom_settings=custom_settings,
        magnetism=magnetism,
        magnetism_scheme=magnetism_scheme
    )


@mcp.tool()
@require_htvs_context
def htvs_query_results(
    settings_module: Optional[str] = None,
    group_name: Optional[str] = None,
    config_name: Optional[str] = None,
    formula: Optional[str] = None,
    limit: Optional[int] = None,
    djangochem_dir: Optional[str] = None,
    htvs_dir: Optional[str] = None,
) -> str:
    """
    Query calculation results (energies, forces, stress) from HTVS database.
    
    Args:
        settings_module: Django settings module (e.g., 'orgel').
        group_name: HTVS project group name.
        config_name: Optional JobConfig name filter.
        formula: Optional chemical formula filter.
        limit: Optional results limit.
        djangochem_dir: Optional override for DJANGOCHEM_DIR.
        htvs_dir: Optional override for HTVS_DIR.
    """
    handler = HTVSDbHandler(settings_module, djangochem_dir, htvs_dir)
    return handler.query_results(group_name, config_name, formula, limit)


@mcp.tool()
@require_htvs_context
def htvs_query_structures(
    settings_module: Optional[str] = None,
    group_name: Optional[str] = None,
    structure_type: str = "crystal",
    config_name: Optional[str] = None,
    formula: Optional[str] = None,
    limit: Optional[int] = None,
    djangochem_dir: Optional[str] = None,
    htvs_dir: Optional[str] = None,
) -> str:
    """
    Query Crystals or Surfaces from the HTVS database.
    
    Args:
        settings_module: Django settings module.
        group_name: HTVS project group name.
        structure_type: "crystal" or "surface".
        config_name: Optional JobConfig name filter.
        formula: Optional chemical formula filter.
        limit: Optional results limit.
        djangochem_dir: Optional override for DJANGOCHEM_DIR.
        htvs_dir: Optional override for HTVS_DIR.
    """
    handler = HTVSDbHandler(settings_module, djangochem_dir, htvs_dir)
    return handler.query_structures(group_name, structure_type, config_name, formula, limit)


@mcp.tool()
@require_htvs_context
def htvs_get_structure(
    structure_id: int,
    settings_module: Optional[str] = None,
    structure_type: str = "crystal",
    djangochem_dir: Optional[str] = None,
    htvs_dir: Optional[str] = None,
) -> str:
    """
    Retrieve structural data (ASE Atoms compatible JSON) for a database record.
    
    Args:
        settings_module: Django settings module.
        structure_id: ID of the record in the database.
        structure_type: "crystal" or "surface".
        djangochem_dir: Optional override for DJANGOCHEM_DIR.
        htvs_dir: Optional override for HTVS_DIR.
    """
    handler = HTVSDbHandler(settings_module, djangochem_dir, htvs_dir)
    return handler.get_structure_as_json(structure_id, structure_type)


@mcp.tool()
@require_htvs_context
def htvs_query_jobs(
    settings_module: Optional[str] = None,
    group_name: Optional[str] = None,
    status: Optional[str] = None,
    config_name: Optional[str] = None,
    limit: Optional[int] = None,
    djangochem_dir: Optional[str] = None,
) -> str:
    """
    Query HTVS Job records from the database.
    
    Args:
        settings_module: Django settings module.
        group_name: HTVS project group name.
        status: Filter by status (done, error, claimed, requested).
        config_name: Filter by JobConfig name.
        limit: Optional limit.
        djangochem_dir: Optional override for DJANGOCHEM_DIR.
    """
        
    handler = HTVSDbHandler(settings_module, djangochem_dir)
    result_str = handler.query_jobs(group_name, status, config_name, limit)
    
    # Attempt to log to the current research directory if available
    try:
        import json
        from pathlib import Path
        from src.utils.research_utils import get_current_research_dir
        
        res_dir = get_current_research_dir()
        if res_dir:
            jobs = json.loads(result_str)
            if isinstance(jobs, list):
                from collections import Counter
                counts = Counter([j.get('status', 'unknown') for j in jobs])
                
                log_file = Path(res_dir) / f"{group_name}_jobs_status.json"
                log_data = {
                    "group_name": group_name,
                    "status_filter": status,
                    "config_filter": config_name,
                    "total_jobs": len(jobs),
                    "status_counts": dict(counts),
                    "jobs": jobs
                }
                with open(log_file, "w") as f:
                    json.dump(log_data, f, indent=2)
                    
                # Prepend a small readable summary since full JSON is logged
                summary = f"Queried {len(jobs)} jobs. Log saved to {log_file}\\nStatus counts: {dict(counts)}\\n"
                # Still return the full json but we can add summary at start if needed, 
                # but returning JSON string is standard. We will return the plain JSON
                # so other tools can parse it, but print a note. Wait, if we prepend text,
                # it breaks JSON parsing for AI! So we should just write to log, and return the original JSON.
                # OR we return a new structure.
                # Since MCP tools text output goes to the LLM, returning a text summary + JSON output works.
                # Actually, just returning the original JSON is safer so we don't break expected standard structure.
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning("Failed to log query_jobs to research dir: %s", e)

    return result_str


@mcp.tool()
@require_htvs_context
def htvs_request_job(
    chem_config: str,
    details: Dict[str, Any],
    settings_module: Optional[str] = None,
    group_name: Optional[str] = None,
    requester: Optional[str] = None,
    parent_pks: Optional[List[int]] = None,
    parent_config: Optional[str] = None,
    djangochem_dir: Optional[str] = None,
) -> str:
    """
    Request new HTVS jobs in the database.
    
    Args:
        settings_module: Django settings module.
        group_name: Project group name.
        chem_config: Chemical configuration name.
        details: Job details dictionary (use prepare_vasp_job_details to generate).
        requester: Optional requester name.
        parent_pks: Optional list of parent job PKs.
        parent_config: Optional parent configuration name filter for parents.
        djangochem_dir: Optional override for DJANGOCHEM_DIR.
    """
    
    config = HTVSConfigHandler().load_config()
    details.setdefault("compute_platform", config.get("compute_platform"))
    details.setdefault("pseudo_dir", config.get("potcar_path"))
    details.setdefault("requester", config.get("requester"))
    details.setdefault("project_name", config.get("project_name"))
    
    handler = HTVSJobHandler(settings_module, djangochem_dir)
    result = handler.request_job(group_name, chem_config, details, requester, parent_pks, parent_config)
    
    # Log to research dir
    try:
        # Extract Job IDs (PKs) from output string
        # Standard output usually looks like "Success: Created job(s): [123, 124]" or lists them
        pks = []
        pk_matches = re.findall(r"PK[:\s]*(\d+)", result)
        if not pk_matches:
            pk_matches = re.findall(r"\[([\d,\s]+)\]", result)
            if pk_matches:
                pks = [int(x.strip()) for x in pk_matches[0].split(",")]
        else:
            pks = [int(x) for x in pk_matches]
            
        if pks:
            _log_to_research_dir("htvs_request_job", {
                "timestamp": datetime.now().isoformat(),
                "group_name": group_name,
                "chem_config": chem_config,
                "job_pks": pks,
                "details": details
            })
    except Exception:
        pass
        
    return result


@mcp.tool()
@require_htvs_context
def htvs_request_followup_job(
    chem_config: str,
    parent_job_pks: List[int],
    details: Dict[str, Any],
    settings_module: Optional[str] = None,
    group_name: Optional[str] = None,
    requester: Optional[str] = None,
    parent_config: Optional[str] = None,
    djangochem_dir: Optional[str] = None,
) -> str:
    """
    Request follow-up jobs based on previous job IDs.
    
    Args:
        settings_module: Django settings module.
        group_name: Project group name.
        chem_config: New chemical configuration name.
        parent_job_pks: List of parent job PKs (IDs).
        details: New job details dictionary.
        requester: Optional requester name.
        parent_config: Optional parent configuration name filter for parents.
        djangochem_dir: Optional override for DJANGOCHEM_DIR.
    """
        
    config = HTVSConfigHandler().load_config()
    details.setdefault("compute_platform", config.get("compute_platform"))
    details.setdefault("pseudo_dir", config.get("potcar_path"))
    details.setdefault("requester", config.get("requester"))
    details.setdefault("project_name", config.get("project_name"))
    
    handler = HTVSJobHandler(settings_module, djangochem_dir)
    result = handler.request_followup_job(group_name, chem_config, parent_job_pks, details, requester, parent_config)
    
    # Log to research dir
    try:
        # Extract Job IDs (PKs) from output string
        pks = []
        pk_matches = re.findall(r"PK[:\s]*(\d+)", result)
        if not pk_matches:
            pk_matches = re.findall(r"\[([\d,\s]+)\]", result)
            if pk_matches:
                pks = [int(x.strip()) for x in pk_matches[0].split(",")]
        else:
            pks = [int(x) for x in pk_matches]
            
        if pks:
            _log_to_research_dir("htvs_request_job", {
                "timestamp": datetime.now().isoformat(),
                "group_name": group_name,
                "chem_config": chem_config,
                "job_pks": pks,
                "parent_pks": parent_job_pks,
                "details": details
            })
    except Exception:
        pass
        
    return result


@mcp.tool()
@require_htvs_context
def htvs_build_jobs(
    settings_module: Optional[str] = None,
    group_name: Optional[str] = None,
    inbox_path: Optional[str] = None,
    config_name: Optional[str] = None,
    limit: Optional[int] = None,
    compute_platform: Optional[str] = None,
    djangochem_dir: Optional[str] = None,
) -> str:
    """
    Build HTVS job directories from requested records.
    
    Args:
        settings_module: Django settings module.
        group_name: Project group name.
        inbox_path: Path to inbox directory (where jobs will be built).
        config_name: Optional filter by configuration.
        limit: Optional job limit.
        compute_platform: Optional compute platform filter.
        djangochem_dir: Optional override for DJANGOCHEM_DIR.
    """
        
    config = HTVSConfigHandler().load_config()
    inbox_path = inbox_path or config.get("inbox_path")
    compute_platform = compute_platform or config.get("compute_platform")
    
    if not inbox_path:
        return "Error: inbox_path is required. Pass it via argument or set it in ~/.atomistic_skills.yaml."
        
    handler = HTVSJobHandler(settings_module, djangochem_dir)
    return handler.build_jobs(group_name, inbox_path, config_name, limit, compute_platform)


@mcp.tool()
@require_htvs_context
def htvs_parse_jobs(
    completed_path: str,
    settings_module: Optional[str] = None,
    group_name: Optional[str] = None,
    config_name: Optional[str] = None,
    limit: Optional[int] = None,
    djangochem_dir: Optional[str] = None,
) -> str:
    """
    Parse completed HTVS jobs into the database.
    
    Args:
        settings_module: Django settings module.
        group_name: Project group name.
        completed_path: Path to directory containing completed jobs.
        config_name: Optional filter by configuration.
        limit: Optional job limit.
        djangochem_dir: Optional override for DJANGOCHEM_DIR.
    """
        
    config = HTVSConfigHandler().load_config()
    completed_path = completed_path or config.get("completed_path")
    
    if not completed_path:
        return "Error: completed_path is required. Pass it via argument or set it in ~/.atomistic_skills.yaml."
        
    handler = HTVSJobHandler(settings_module, djangochem_dir)
    return handler.parse_jobs(group_name, completed_path, config_name, limit)





@mcp.tool()
@require_htvs_context
def htvs_create_group(
    settings_module: Optional[str] = None,
    group_name: Optional[str] = None,
    djangochem_dir: Optional[str] = None,
) -> str:
    """
    Create a new project Group in the HTVS database.
    
    Args:
        settings_module: Django settings module.
        group_name: Project group name to create.
        djangochem_dir: Optional override for DJANGOCHEM_DIR.
    """
        
    handler = HTVSDbHandler(settings_module, djangochem_dir)
    return handler.create_group(group_name)


if __name__ == "__main__":
    mcp.run()


