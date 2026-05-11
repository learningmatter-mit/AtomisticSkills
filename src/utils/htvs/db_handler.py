"""
HTVS Database Operations.

This module provides utilities for saving structures to the HTVS database
and managing database operations.
"""

import logging
import json
from typing import List, Optional, Dict, Any

from .script_runner import run_htvs_script

logger = logging.getLogger(__name__)


class HTVSDbHandler:
    """
    Handler for HTVS database operations.
    
    Manages saving structures (Crystals, Surfaces) and creating groups
    in the HTVS Django database via embedded Python scripts.
    
    Example:
        >>> handler = HTVSDbHandler("orgel")
        >>> result = handler.save_crystals("structure.cif", "config", "group")
    """
    
    def __init__(
        self,
        settings_module: str,
        djangochem_dir: Optional[str] = None,
        htvs_dir: Optional[str] = None
    ):
        """
        Initialize with Django configuration.
        
        Args:
            settings_module: Django settings module (e.g., 'orgel', 'toy')
            djangochem_dir: Optional override for DJANGOCHEM_DIR
            htvs_dir: Optional override for HTVS_DIR
        """
        self.settings_module = settings_module
        self.djangochem_dir = djangochem_dir
        self.htvs_dir = htvs_dir
    
    def _run_script(self, script: str) -> str:
        """
        Centralized Django script execution.
        
        Args:
            script: Python script to execute in Django context
            
        Returns:
            Script output string
        """
        return run_htvs_script(
            script,
            self.settings_module,
            djangochem_dir=self.djangochem_dir,
            htvs_dir=self.htvs_dir
        )
    
    def _execute_template(self, script_name: str, payload: Dict[str, Any]) -> str:
        """
        Execute a standalone Python script template with a JSON payload.
        """
        import os
        import json
        
        # Resolve script path
        script_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "db_scripts")
        script_path = os.path.join(script_dir, f"{script_name}.py")
        
        if not os.path.exists(script_path):
            return json.dumps({"error": f"Script template not found: {script_path}"})
            
        with open(script_path, "r") as f:
            script_body = f.read()
            
        # Inject payload into environment for subprocess
        os.environ["HTVS_PAYLOAD"] = json.dumps(payload)
        
        return self._run_script(script_body)

    def save_crystals(
        self,
        structure_file: str,
        config_name: str,
        group_name: str,
        method_name: Optional[str] = None,
        framework_name: Optional[str] = None
    ) -> str:
        payload = {
            "structure_type": "crystal",
            "structure_file": structure_file,
            "config_name": config_name,
            "group_name": group_name,
            "method_name": method_name,
            "framework_name": framework_name
        }
        return self._execute_template("save_structures", payload)
    
    def save_surfaces(
        self,
        structure_file: str,
        config_name: str,
        parent_bulk_id: int,
        group_name: str,
        miller_index: List[int],
        method_name: Optional[str] = None,
        framework_name: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> str:
        payload = {
            "structure_type": "surface",
            "structure_file": structure_file,
            "config_name": config_name,
            "group_name": group_name,
            "method_name": method_name,
            "framework_name": framework_name,
            "parent_bulk_id": parent_bulk_id,
            "miller_index": miller_index,
            "details": details
        }
        return self._execute_template("save_structures", payload)

    def save_structures(
        self,
        structure_path: str,
        config_name: str,
        group_name: str,
        structure_type: str = "auto",
        parent_bulk_id: Optional[int] = None,
        miller_index: List[int] = [0, 1, 0],
        method_name: Optional[str] = None,
        framework_name: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Batch save structures from a directory or file with auto-detection.
        """
        import os, json
        from ase.io import read
        
        results = {"total": 0, "successful": 0, "failed": 0, "structures": []}
        files = []
        if os.path.isdir(structure_path):
            files = [os.path.join(structure_path, f) for f in os.listdir(structure_path) 
                     if f.endswith(('.cif', '.xyz', '.poscar', 'POSCAR'))]
        else:
            files = [structure_path]
            
        results["total"] = len(files)
        
        for file_path in files:
            try:
                # Type detection
                detected_type = structure_type
                if structure_type == "auto":
                    atoms = read(file_path, index=0)
                    if hasattr(atoms, 'get_tags') and any(atoms.get_tags()):
                        detected_type = "surface"
                    else:
                        detected_type = "crystal"
                
                if detected_type == "crystal":
                    result = self.save_crystals(
                        file_path, config_name, group_name, method_name, framework_name
                    )
                elif detected_type == "surface":
                    if parent_bulk_id is None:
                        results["structures"].append({
                            "file": os.path.basename(file_path),
                            "error": "parent_bulk_id required for surface"
                        })
                        results["failed"] += 1
                        continue
                    
                    result = self.save_surfaces(
                        file_path, config_name, parent_bulk_id,
                        group_name, miller_index, method_name, framework_name, details
                    )
                else:
                    results["structures"].append({
                        "file": os.path.basename(file_path),
                        "error": f"Unknown structure_type: {detected_type}"
                    })
                    results["failed"] += 1
                    continue
                
                # Parse result
                result_data = json.loads(result)
                if isinstance(result_data, dict) and "error" in result_data:
                    results["structures"].append({
                        "file": os.path.basename(file_path),
                        "type": detected_type,
                        "error": result_data["error"]
                    })
                    results["failed"] += 1
                else:
                    results["structures"].append({
                        "file": os.path.basename(file_path),
                        "type": detected_type,
                        "ids": result_data,
                        "count": len(result_data) if isinstance(result_data, list) else 1
                    })
                    results["successful"] += 1
                    
            except Exception as e:
                results["structures"].append({
                    "file": os.path.basename(file_path),
                    "error": str(e)
                })
                results["failed"] += 1
        
        return json.dumps(results, indent=2)
    
    def create_group(self, group_name: str) -> str:
        payload = {"action": "create_group", "group_name": group_name}
        return self._execute_template("group_management", payload)

    def query_results(
        self,
        group_name: str,
        config_name: Optional[str] = None,
        formula: Optional[str] = None,
        limit: Optional[int] = None
    ) -> str:
        payload = {
            "query_type": "results",
            "group_name": group_name,
            "config_name": config_name,
            "formula": formula,
            "limit": limit
        }
        return self._execute_template("query_db", payload)

    def query_structures(
        self,
        group_name: str,
        structure_type: str = "crystal",
        config_name: Optional[str] = None,
        formula: Optional[str] = None,
        limit: Optional[int] = None
    ) -> str:
        payload = {
            "query_type": "structures",
            "group_name": group_name,
            "structure_type": structure_type,
            "config_name": config_name,
            "formula": formula,
            "limit": limit
        }
        return self._execute_template("query_db", payload)

    def query_jobs(
        self,
        group_name: str,
        status: Optional[str] = None,
        config_name: Optional[str] = None,
        limit: Optional[int] = None
    ) -> str:
        payload = {
            "query_type": "jobs",
            "group_name": group_name,
            "status": status,
            "config_name": config_name,
            "limit": limit
        }
        return self._execute_template("query_db", payload)

    def get_structure_as_json(
        self,
        structure_id: int,
        structure_type: str = "crystal"
    ) -> str:
        payload = {
            "query_type": "get_structure",
            "structure_id": structure_id,
            "structure_type": structure_type
        }
        return self._execute_template("query_db", payload)

    def save_binding_energies(
        self,
        entries: List[Dict[str, Any]],
        metric: str = "surface_binding_dE"
    ) -> str:
        """
        Bulk save binding energy records.
        Each entry dict should have: clean_id, ads_id, value, adsorbate (formula).
        """
        payload = {
            "entries": entries,
            "metric": metric
        }
        return self._execute_template("save_binding_energies", payload)

    def save_adsorbate_surface(
        self,
        payload: Dict[str, Any]
    ) -> str:
        """
        Save a single adsorbate surface.
        Payload dict should contain: xyz, lattice, stoichiometry, bulk_id, 
        miller_index, active_site, adsorbate_atoms, surface_atoms, 
        parent_id, group_name, magmoms (optional).
        """
        return self._execute_template("save_adsorbate_surface", payload)

    def save_surface_entries(
        self,
        entries: List[Dict[str, Any]],
        config_name: str,
        group_name: str,
        method_name: Optional[str] = None
    ) -> str:
        """
        Bulk save surface records generated in-memory.
        Each entry dict should contain: xyz, lattice, stoichiometry, bulk_id, 
        miller_index, surface_atoms, adsorbate_atoms, details, magmoms (optional).
        """
        payload = {
            "entries": entries,
            "config_name": config_name,
            "group_name": group_name,
            "method_name": method_name
        }
        return self._execute_template("save_surface_entries", payload)

