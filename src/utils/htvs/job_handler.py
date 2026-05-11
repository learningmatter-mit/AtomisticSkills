"""
HTVS Job Management.

This module provides utilities for managing the HTVS job lifecycle:
requesting jobs, building job directories, and parsing completed jobs.
"""

import os
import sys
import json
import subprocess
import logging
from typing import Dict, Any, Optional, List


from .config_handler import HTVSConfigHandler

logger = logging.getLogger(__name__)


class HTVSJobHandler:
    """
    Manages HTVS job lifecycle operations via Django management commands.
    
    Handles requesting, building, and parsing HTVS jobs with centralized
    configuration and error handling.
    
    Example:
        >>> handler = HTVSJobHandler("orgel")
        >>> result = handler.request_job("my_group", "pbe_config", {"ENCUT": 500})
    """
    
    def __init__(self, settings_module: str, djangochem_dir: Optional[str] = None):
        """
        Initialize handler with Django configuration.
        
        Args:
            settings_module: Django settings module (e.g., 'orgel', 'toy')
            djangochem_dir: Optional override for DJANGOCHEM_DIR
            
        Raises:
            ValueError: If HTVS environment is not configured
        """
        self.settings_module = settings_module
        self.djangochem_dir = self._resolve_djangochem_dir(djangochem_dir)
        self.manage_py = os.path.join(self.djangochem_dir, "manage.py")
    
    def _resolve_djangochem_dir(self, djangochem_dir: Optional[str]) -> str:
        """
        Resolve and validate djangochem_dir.
        
        Args:
            djangochem_dir: Optional override path
            
        Returns:
            Validated path to djangochem directory
            
        Raises:
            ValueError: If path cannot be resolved
        """
        if djangochem_dir:
            return djangochem_dir
        
        config_handler = HTVSConfigHandler()
        resolved = config_handler.djangochem_dir
        
        if not resolved:
            raise ValueError(
                "HTVS environment not configured. "
                "Set HTVSDIR and DJANGOCHEMDIR environment variables or "
                "provide djangochem_dir parameter."
            )
        
        return resolved
    
    def _run_command(self, cmd: List[str]) -> str:
        """
        Execute Django management command with unified error handling.
        
        Args:
            cmd: Command list for subprocess.run
            
        Returns:
            Success or error message with command output
        """
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=self.djangochem_dir,
                env={**os.environ, "PYTHONUNBUFFERED": "1"}
            )
            
            if result.returncode != 0:
                return f"Command Failed:\\nSTDOUT:\\n{result.stdout}\\nSTDERR:\\n{result.stderr}"
            
            return f"Success:\\n{result.stdout}"
        
        except Exception as e:
            return f"Execution Error: {str(e)}"
    
    def request_job(
        self,
        group_name: str,
        chem_config: str,
        details: Dict[str, Any],
        requester: Optional[str] = None,
        parent_pks: Optional[List[int]] = None,
        parent_config: Optional[str] = None
    ) -> str:
        """
        Request new HTVS jobs via manage.py requestjobs.
        
        Args:
            group_name: Name of the project/group
            chem_config: Chemical configuration name
            details: Job details dictionary
            requester: Optional requester name
            parent_pks: Optional list of parent job PKs
            parent_config: Optional parent configuration name
        
        Returns:
            Command output string
        """
        # Pre-flight validation for Perlmutter
        cp = details.get("compute_platform", "")
        if cp and "perlmutter" in cp.lower():
            if not details.get("project_name"):
                return "Error: 'project_name' is missing but compute_platform is Perlmutter. Please provide it in ~/.atomistic_skills.yaml or tool details."
        
        cmd = [
            sys.executable, self.manage_py, "requestjobs",
            group_name,
            chem_config,
            "--settings", self.settings_module,
            "--details", json.dumps(details)
        ]
        
        if requester:
            cmd.extend(["--requester", requester])
        if parent_pks:
            cmd.extend(["--parentpks"] + [str(pk) for pk in parent_pks])
        if parent_config:
            cmd.extend(["--parent_config", parent_config])
        
        if details.get("force", False):
            cmd.append("--force")
        
        return self._run_command(cmd)
    
    def build_jobs(
        self,
        group_name: str,
        inbox_path: Optional[str] = None,
        config_name: Optional[str] = None,
        limit: Optional[int] = None,
        compute_platform: Optional[str] = None
    ) -> str:
        """
        Build HTVS job directories via manage.py buildjobs.
        
        Args:
            group_name: Name of the project/group
            inbox_path: Path to inbox directory (auto-detected if not provided)
            config_name: Optional configuration filter
            limit: Optional limit on number of jobs
            compute_platform: Optional compute platform filter
        
        Returns:
            Command output string
        """
        # Determine inbox_path if not provided
        if not inbox_path:
            htvs_job_root = os.environ.get("HTVS_JOB_ROOT")
            if htvs_job_root:
                inbox_path = os.path.join(htvs_job_root, "inbox")
            else:
                inbox_path = os.path.join(os.getcwd(), "inbox")
        
        cmd = [
            sys.executable, self.manage_py, "buildjobs",
            group_name,
            inbox_path,
            "--settings", self.settings_module,
        ]
        
        if config_name:
            cmd.extend(["--config", config_name])
        
        if limit is not None:
            cmd.extend(["--limit", str(limit)])
        
        if compute_platform:
            cmd.extend(["--compute_platform", compute_platform])
        
        return self._run_command(cmd)
    
    def parse_jobs(
        self,
        group_name: str,
        completed_path: str,
        config_name: Optional[str] = None,
        limit: Optional[int] = None
    ) -> str:
        """
        Parse completed HTVS jobs via manage.py parsejobs.
        
        Args:
            group_name: Name of the project/group
            completed_path: Path to completed jobs directory
            config_name: Optional configuration filter
            limit: Optional limit on number of jobs
        
        Returns:
            Command output string
        """
        cmd = [
            sys.executable, self.manage_py, "parsejobs",
            group_name,
            completed_path,
            "--settings", self.settings_module,
        ]
        
        if config_name:
            cmd.extend(["--config", config_name])
        
        if limit is not None:
            cmd.extend(["--limit", str(limit)])
        
        return self._run_command(cmd)

    def request_followup_job(
        self,
        group_name: str,
        chem_config: str,
        parent_job_pks: List[int],
        details: Dict[str, Any],
        requester: Optional[str] = None,
        parent_config: Optional[str] = None
    ) -> str:
        """
        Request follow-up jobs based on parent job primary keys.
        
        Args:
            group_name: Name of the project/group
            chem_config: New chemical configuration name
            parent_job_pks: List of parent job PKs
            details: Job details dictionary
            requester: Optional requester name
            parent_config: Optional parent configuration name
        
        Returns:
            Command output string
        """
        return self.request_job(
            group_name=group_name,
            chem_config=chem_config,
            details=details,
            requester=requester,
            parent_pks=parent_job_pks,
            parent_config=parent_config
        )


# Backward-compatible wrapper functions for existing API
