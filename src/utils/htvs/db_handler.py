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
    
    def save_crystals(
        self,
        structure_file: str,
        config_name: str,
        group_name: str,
        method_name: Optional[str] = None,
        framework_name: Optional[str] = None
    ) -> str:
        """
        Save bulk structures from a file to the HTVS database as Crystals.
        
        Args:
            structure_file: Absolute path to structure file
            config_name: JobConfig name
            group_name: Project/group name
            method_name: Optional Method name
            framework_name: Optional Framework name
        
        Returns:
            JSON string containing list of created Crystal IDs
        """
        script = f"""
import os
import json
from ase import io
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from jobs.models import Job, JobConfig
from pgmols.models import Crystal, Group, Method, Framework

structure_file = "{structure_file}"
config_name = "{config_name}"
group_name = "{group_name}"
method_name = {repr(method_name)}
framework_name = {repr(framework_name)}

try:
    if not os.path.exists(structure_file):
        print(json.dumps({{"error": f"File not found: {{structure_file}}"}}))
        exit(1)

    samples = io.read(structure_file, ":")
    created_ids = []
    
    group_obj, _ = Group.objects.get_or_create(name=group_name)
    config_obj, _ = JobConfig.objects.get_or_create(name=config_name)
    
    default_method_name = method_name if method_name else "manual_import"
    method_obj, _ = Method.objects.get_or_create(name=default_method_name)
    
    for atoms in samples:
        obj = Crystal.from_ase_atoms(atoms)
        obj.method = method_obj
        if hasattr(obj, 'generate_hash'):
            obj.chemical_tag = obj.generate_hash()
        
        # Save Crystal first to get an ID for GenericForeignKey
        obj.save() 

        # Create Parent Job and link using robust pattern
        job = Job(
            config=config_obj,
            group=group_obj,
            status="done",
            parentct=ContentType.objects.get_for_model(obj),
            parentid=obj.id,
            completetime=timezone.now(),
        )
        job.save()
        
        obj.parentjob = job
        
        # Handle Framework if specified
        if framework_name:
            framework, _ = Framework.objects.get_or_create(
                name=framework_name, 
                prototype=obj, 
                group=group_obj
            )
            obj.framework = framework
            
        obj.save()
        created_ids.append(obj.id)
            
    print(json.dumps(created_ids))

except Exception as e:
    import traceback
    traceback.print_exc()
    print(json.dumps({{"error": str(e)}}))
"""
        return self._run_script(script)
    
    def save_surfaces(
        self,
        structure_file: str,
        config_name: str,
        parent_bulk_id: int,
        group_name: str,
        miller_index: List[int],
        method_name: Optional[str] = None,
        framework_name: Optional[str] = None
    ) -> str:
        """
        Save surface structures from a file to the HTVS database as Surfaces.
        
        Includes comprehensive surface atom and adsorbate atom tagging logic
        with multiple detection methods.
        
        Args:
            structure_file: Absolute path to structure file
            config_name: JobConfig name
            parent_bulk_id: ID of parent Crystal or Surface
            group_name: Project/group name
            miller_index: Miller index [h, k, l]
            method_name: Optional Method name
            framework_name: Optional Framework name
        
        Returns:
            JSON string containing list of created Surface IDs
        """
        script = f"""
import os
import json
import numpy as np
from ase import io
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from jobs.models import Job, JobConfig
from pgmols.models import Crystal, Group, MillerIndex, Surface, Method, Framework

structure_file = "{structure_file}"
config_name = "{config_name}"
parent_bulk_id = {parent_bulk_id}
miller_index_arg = {miller_index}
group_name = "{group_name}"
method_name = {repr(method_name)}
framework_name = {repr(framework_name)}

def get_miller_index(hkl):
    mi, _ = MillerIndex.objects.get_or_create(hkl=hkl)
    return mi

try:
    if not os.path.exists(structure_file):
        print(json.dumps({{"error": f"File not found: {{structure_file}}"}}))
        exit(1)

    samples = io.read(structure_file, ":")
    created_ids = []
    
    group_obj, _ = Group.objects.get_or_create(name=group_name)
    config_obj, _ = JobConfig.objects.get_or_create(name=config_name)
    
    default_method_name = method_name if method_name else "manual_import"
    default_method, _ = Method.objects.get_or_create(name=default_method_name)
    mi_obj = get_miller_index(miller_index_arg)
    
    # Try finding parent
    parent_obj = None
    try:
        parent_obj = Surface.objects.get(id=parent_bulk_id)
    except Surface.DoesNotExist:
        try:
            parent_obj = Crystal.objects.get(id=parent_bulk_id)
        except Crystal.DoesNotExist:
            print(json.dumps({{"error": f"Parent ID {{parent_bulk_id}} not found"}}))
            exit(1)

    for atoms in samples:
        surf = Surface.from_ase_atoms(atoms)
        surf.method = default_method
        
        if hasattr(parent_obj, "miller_index"):
            surf.miller_index = parent_obj.miller_index
        else:
            surf.miller_index = mi_obj
            
        surf.chemical_tag = surf.generate_hash()
        
        # Comprehensive surface/adsorbate atoms tagging logic (3 methods)
        # Method 1: Check atoms.info dict for explicit surf_atoms
        if atoms.info.get("surf_atoms", None) is not None:
            surf_atoms = atoms.info.get("surf_atoms")
            surf.surface_atoms = np.array(surf_atoms, dtype=int).tolist()
            try:
                surf.adsorbate_atoms = np.array(atoms.ads_atoms, dtype=int).tolist()
            except AttributeError:
                # Fallback to tags
                surf.adsorbate_atoms = (atoms.get_tags() == 2).tolist()
        
        # Method 2: Check for get_surface_atoms() method
        elif hasattr(atoms, "get_surface_atoms"):
            surf.surface_atoms = np.isin(
                np.arange(len(atoms)),
                np.array(atoms.get_surface_atoms(), dtype=int)
            ).tolist()
            try:
                surf_indices = np.array(atoms.get_adsorbate_atoms(), dtype=int).tolist()
            except AttributeError:
                surf_indices = []
            surf.adsorbate_atoms = np.isin(np.arange(len(atoms)), surf_indices).tolist()
        
        # Method 3: Fallback to ASE tags (tag=1 for surface, tag=2 for adsorbate)
        else:
            tags = atoms.get_tags()
            surf.surface_atoms = (tags == 1).tolist()
            surf.adsorbate_atoms = (tags == 2).tolist()

        # Save surface first to get ID
        surf.save()

        # Create Job
        job = Job(
            config=config_obj,
            group=group_obj,
            status="done",
            parentct=ContentType.objects.get_for_model(parent_obj),
            parentid=parent_obj.id,
            completetime=timezone.now(),
        )
        job.save()
        
        surf.parentjob = job
        
        # Handle Framework if specified
        if framework_name:
            framework, _ = Framework.objects.get_or_create(
                name=framework_name, 
                prototype=surf, 
                group=group_obj
            )
            surf.framework = framework
            
        surf.save()
        created_ids.append(surf.id)
            
    print(json.dumps(created_ids))

except Exception as e:
    import traceback
    traceback.print_exc()
    print(json.dumps({{"error": str(e)}}))
"""
        return self._run_script(script)


    
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
        file_patterns: List[str] = ["*.cif", "*.xyz", "*.vasp", "*.poscar"]
    ) -> str:
        """
        Batch save multiple structures from a directory or file list.
        
        Auto-detects structure type (Crystal vs Surface) based on:
        - Filename keywords (bulk, crystal, surf, surface, slab, ads)
        - parent_bulk_id parameter
        - ASE tags in structures
        
        Args:
            structure_path: Directory containing structures or single file path
            config_name: JobConfig name
            group_name: Project/group name
            structure_type: "auto", "crystal", or "surface"
            parent_bulk_id: Optional parent bulk ID for surfaces
            miller_index: Default Miller index for surfaces
            method_name: Optional Method name
            framework_name: Optional Framework name
            file_patterns: File patterns to search for (default: cif, xyz, vasp, poscar)
        
        Returns:
            JSON string with summary of created structures
        """
        import os
        import glob
        
        # Determine if path is directory or file
        if os.path.isdir(structure_path):
            # Scan directory for structure files
            structure_files = []
            for pattern in file_patterns:
                structure_files.extend(glob.glob(os.path.join(structure_path, pattern)))
            
            if not structure_files:
                return json.dumps({
                    "error": f"No structure files found in {structure_path}",
                    "patterns": file_patterns
                })
        elif os.path.isfile(structure_path):
            structure_files = [structure_path]
        else:
            return json.dumps({"error": f"Path not found: {structure_path}"})
        
        results = {
            "total_files": len(structure_files),
            "successful": 0,
            "failed": 0,
            "structures": []
        }
        
        for file_path in structure_files:
            try:
                filename_lower = os.path.basename(file_path).lower()
                
                # Auto-detect structure type from filename
                if structure_type == "auto":
                    bulk_keywords = ["bulk", "crystal", "solid", "initial"]
                    surf_keywords = ["surf", "surface", "slab", "ads"]
                    
                    is_bulk = any(k in filename_lower for k in bulk_keywords)
                    is_surf = any(k in filename_lower for k in surf_keywords)
                    
                    if (is_surf or parent_bulk_id) and not is_bulk:
                        detected_type = "surface"
                    else:
                        detected_type = "crystal"
                else:
                    detected_type = structure_type
                
                # Call appropriate save method
                if detected_type == "crystal":
                    result = self.save_crystals(
                        file_path, config_name, group_name,
                        method_name, framework_name
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
                        group_name, miller_index, method_name, framework_name
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
        """
        Create a new Group (Project) in the HTVS database if it doesn't exist.
        
        Args:
            group_name: Name of the group to create
        
        Returns:
            JSON string indicating if the group was created or already existed
        """
        script = f"""
import json
from pgmols.models import Group

group_name = "{group_name}"

group, created = Group.objects.get_or_create(name=group_name)

result = {{
    "group_name": group_name,
    "group_id": group.id,
    "created": created
}}

print(json.dumps(result))
"""
        return self._run_script(script)
