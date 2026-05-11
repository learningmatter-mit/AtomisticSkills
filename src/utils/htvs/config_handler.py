"""
HTVS Configuration Handler.

This module provides a class-based handler for HTVS configuration management,
environment validation, and chemical configuration inspection.
"""

import os
import json
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# Try to import pymatgen for environment checking
try:
    from pymatgen.io.ase import AseAtomsAdaptor
    PYMATGEN_AVAILABLE = True
except ImportError:
    PYMATGEN_AVAILABLE = False


class HTVSConfigHandler:
    """
    Handle HTVS configuration, environment validation, and chemical config inspection.
    
    This handler consolidates:
    - Configuration loading from environment/mcp_config.json
    - Environment validation checks
    - Chemical configuration (job.sh) inspection
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the HTVS configuration handler.
        
        Args:
            config_path: Optional path to mcp_config.json. If not provided,
                        searches in repo root.
        """
        self.config = self.load_config(config_path)
    
    def load_config(self, config_path: Optional[str] = None) -> Dict[str, str]:
        """
        Load HTVS configuration from environment variables or mcp_config.json.
        
        Args:
            config_path: Optional path to mcp_config.json. If not provided,
                        searches in repo root.
        
        Returns:
            Dictionary with 'htvs_dir' and 'htvs_djangochem_dir' keys.
        """
        if not config_path:
            # Assume repo root structure: src/utils/htvs/config_handler.py -> ../../../../mcp_config.json
            repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
            config_path = os.path.join(repo_root, "mcp_config.json")
        
        # 1. First check environment variables
        # Base paths
        htvs_dir = os.environ.get("HTVS_DIR") or os.environ.get("HTVSDIR")
        htvs_djangochem_dir = os.environ.get("HTVS_DJANGOCHEM_DIR") or os.environ.get("DJANGOCHEMDIR")
        
        # New cluster/project defaults
        settings_module = os.environ.get("HTVS_SETTINGS_MODULE")
        group_name = os.environ.get("HTVS_GROUP_NAME")
        compute_platform = os.environ.get("HTVS_COMPUTE_PLATFORM")
        requester = os.environ.get("HTVS_REQUESTER")
        inbox_path = os.environ.get("HTVS_INBOX_PATH")
        potcar_path = os.environ.get("HTVS_POTCAR_PATH")
        project_name = os.environ.get("HTVS_PROJECT_NAME")
        completed_path = os.environ.get("HTVS_COMPLETED_PATH")
        
        # 2. Check ~/.atomistic_skills.yaml (Primary global config)
        yaml_config_path = os.path.expanduser("~/.atomistic_skills.yaml")
        if os.path.exists(yaml_config_path):
            try:
                import yaml
                with open(yaml_config_path, 'r') as f:
                    yaml_config = yaml.safe_load(f) or {}
                    if not htvs_dir:
                        htvs_dir = yaml_config.get("HTVS_DIR", yaml_config.get("HTVSDIR"))
                    if not htvs_djangochem_dir:
                        htvs_djangochem_dir = yaml_config.get("HTVS_DJANGOCHEM_DIR", yaml_config.get("DJANGOCHEMDIR"))
                    
                    # Fetch extra configuration keys if present
                    settings_module = settings_module or yaml_config.get("settings_module")
                    group_name = group_name or yaml_config.get("group_name")
                    compute_platform = compute_platform or yaml_config.get("compute_platform")
                    requester = requester or yaml_config.get("requester")
                    inbox_path = inbox_path or yaml_config.get("inbox_path")
                    potcar_path = potcar_path or yaml_config.get("potcar_path")
                    project_name = project_name or yaml_config.get("project_name")
                    completed_path = completed_path or yaml_config.get("completed_path")
            except Exception as e:
                logger.warning(f"Failed to load config from {yaml_config_path}: {e}")
        
        # 3. Fallback to mcp_config.json
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    config = json.load(f)
                    htvs_server_env = config.get("mcpServers", {}).get("htvs", {}).get("env", {})
                    if not htvs_dir:
                        htvs_dir = htvs_server_env.get("HTVS_DIR")
                    if not htvs_djangochem_dir:
                        htvs_djangochem_dir = htvs_server_env.get("HTVS_DJANGOCHEM_DIR")
            except Exception as e:
                logger.warning(f"Failed to load config from {config_path}: {e}")
        
        if not htvs_dir or not htvs_djangochem_dir:
            logger.warning("HTVS environment variables (HTVS_DIR, HTVS_DJANGOCHEM_DIR) not found in environment or config files.")
            
        vasp_steps = {}
        if 'yaml_config' in locals() and isinstance(yaml_config, dict):
            vasp_steps = yaml_config.get("vasp_steps", {})
        
        return {
            "htvs_dir": htvs_dir, 
            "htvs_djangochem_dir": htvs_djangochem_dir,
            "settings_module": settings_module,
            "group_name": group_name,
            "compute_platform": compute_platform,
            "requester": requester,
            "inbox_path": inbox_path,
            "potcar_path": potcar_path,
            "project_name": project_name,
            "completed_path": completed_path,
            "vasp_steps": vasp_steps
        }
    
    def check_environment(self) -> Dict[str, Any]:
        """
        Check if HTVS environment is correctly configured.
        
        Returns:
            Dictionary with boolean checks for each component.
        """
        htvs_dir = self.config.get("htvs_dir")
        djangochem_dir = self.config.get("htvs_djangochem_dir")
        
        checks = {
            "htvs_dir": bool(htvs_dir and os.path.exists(htvs_dir)),
            "djangochem_dir": bool(djangochem_dir and os.path.exists(djangochem_dir)),
            "manage_py": False,
            "pymatgen": PYMATGEN_AVAILABLE
        }
        
        if djangochem_dir:
            manage_py = os.path.join(djangochem_dir, "manage.py")
            checks["manage_py"] = os.path.exists(manage_py)
        
        return checks
    
    def inspect_chemconfig(
        self,
        config_name: str,
        htvs_repo_root: Optional[str] = None,
        tool: Optional[str] = None
    ) -> str:
        """
        Inspect the job script (job.sh) for a given chemical configuration.
        
        Useful for determining cluster requirements (compute_platform, partitions, etc.).
        
        Args:
            config_name: Configuration name (e.g., 'pbe_d3_paw_bomd_vasp')
            htvs_repo_root: Path to HTVS repository root
            tool: Optional tool name (e.g., 'vasp') to narrow search
        
        Returns:
            Content of job.sh file or error message
        """
        if htvs_repo_root is None:
            htvs_repo_root = "/home/hojechun/ssd_mnt/repos/htvs"
        
        chemconfigs_root = os.path.join(htvs_repo_root, "chemconfigs")
        if not os.path.exists(chemconfigs_root):
            return f"Error: chemconfigs directory not found at {chemconfigs_root}"
        
        search_root = chemconfigs_root
        if tool:
            search_root = os.path.join(chemconfigs_root, tool)
            if not os.path.exists(search_root):
                return f"Error: Tool directory '{tool}' not found in {chemconfigs_root}"
        
        # Search for the config directory
        found_path = None
        for root, dirs, files in os.walk(search_root):
            if config_name in dirs:
                found_path = os.path.join(root, config_name)
                break
        
        if not found_path:
            return f"Error: Configuration '{config_name}' not found in {search_root}"
        
        job_sh_path = os.path.join(found_path, "job.sh")
        if not os.path.exists(job_sh_path):
            return f"Error: job.sh not found in {found_path}"
        
        try:
            with open(job_sh_path, "r") as f:
                content = f.read()
            return f"Found config at: {found_path}\n\n--- job.sh content ---\n{content}"
        except Exception as e:
            return f"Error reading job.sh: {str(e)}"
    
    @property
    def htvs_dir(self) -> Optional[str]:
        """Get HTVS directory path."""
        return self.config.get("htvs_dir")
    
    @property
    def djangochem_dir(self) -> Optional[str]:
        """Get Djangochem directory path."""
        return self.config.get("htvs_djangochem_dir")
