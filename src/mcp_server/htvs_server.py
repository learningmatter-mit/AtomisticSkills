import os
import sys
import json
import subprocess
from typing import Optional, Dict, Any, List

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


@mcp.tool()
def save_htvs_structure(
    structure_file: str,
    config_name: str,
    group_name: str,
    settings_module: str,
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
    if not HTVS_UTILS_AVAILABLE:
        return "Error: HTVS utilities not available"
    
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
        return handler.save_crystals(
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
        return handler.save_surfaces(
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


@mcp.tool()
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
    if not HTVS_UTILS_AVAILABLE:
        import json
        return json.dumps({"error": "HTVS utilities not available"})
    
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
def htvs_query_results(
    settings_module: str,
    group_name: str,
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
    if not HTVS_UTILS_AVAILABLE:
        return "Error: HTVS utilities not available"
    handler = HTVSDbHandler(settings_module, djangochem_dir, htvs_dir)
    return handler.query_results(group_name, config_name, formula, limit)


@mcp.tool()
def htvs_query_structures(
    settings_module: str,
    group_name: str,
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
    if not HTVS_UTILS_AVAILABLE:
        return "Error: HTVS utilities not available"
    handler = HTVSDbHandler(settings_module, djangochem_dir, htvs_dir)
    return handler.query_structures(group_name, structure_type, config_name, formula, limit)


@mcp.tool()
def htvs_get_structure(
    settings_module: str,
    structure_id: int,
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
    if not HTVS_UTILS_AVAILABLE:
        return "Error: HTVS utilities not available"
    handler = HTVSDbHandler(settings_module, djangochem_dir, htvs_dir)
    return handler.get_structure_as_json(structure_id, structure_type)


@mcp.tool()
def htvs_query_jobs(
    settings_module: str,
    group_name: str,
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
    if not HTVS_UTILS_AVAILABLE:
        return "Error: HTVS utilities not available"
    handler = HTVSDbHandler(settings_module, djangochem_dir)
    return handler.query_jobs(group_name, status, config_name, limit)


@mcp.tool()
def htvs_request_job(
    settings_module: str,
    group_name: str,
    chem_config: str,
    details: Dict[str, Any],
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
    if not HTVS_UTILS_AVAILABLE:
        return "Error: HTVS utilities not available"
    handler = HTVSJobHandler(settings_module, djangochem_dir)
    return handler.request_job(group_name, chem_config, details, requester, parent_pks, parent_config)


@mcp.tool()
def htvs_request_followup_job(
    settings_module: str,
    group_name: str,
    chem_config: str,
    parent_job_pks: List[int],
    details: Dict[str, Any],
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
    if not HTVS_UTILS_AVAILABLE:
        return "Error: HTVS utilities not available"
    handler = HTVSJobHandler(settings_module, djangochem_dir)
    return handler.request_followup_job(group_name, chem_config, parent_job_pks, details, requester, parent_config)


@mcp.tool()
def htvs_build_jobs(
    settings_module: str,
    group_name: str,
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
    if not HTVS_UTILS_AVAILABLE:
        return "Error: HTVS utilities not available"
    handler = HTVSJobHandler(settings_module, djangochem_dir)
    return handler.build_jobs(group_name, inbox_path, config_name, limit, compute_platform)


@mcp.tool()
def htvs_parse_jobs(
    settings_module: str,
    group_name: str,
    completed_path: str,
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
    if not HTVS_UTILS_AVAILABLE:
        return "Error: HTVS utilities not available"
    handler = HTVSJobHandler(settings_module, djangochem_dir)
    return handler.parse_jobs(group_name, completed_path, config_name, limit)

if __name__ == "__main__":
    mcp.run()
