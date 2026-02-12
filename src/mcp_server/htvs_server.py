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
        magnetism: Whether to apply default magnetic moments (Cr, Co, Ni).

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
        magnetism=magnetism
    )

if __name__ == "__main__":
    mcp.run()
