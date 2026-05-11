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
from typing import List, Optional, Dict, Any

from .config_handler import HTVSConfigHandler

logger = logging.getLogger(__name__)

class HTVSJobHandler:
    """
    Modular HTVS Job Handler that interacts with Django models directly via dedicated handlers.
    
    Handles requesting, building, and parsing HTVS jobs with centralized
    configuration and error handling.
    
    Example:
        >>> handler = HTVSJobHandler("orgel")
        >>> result = handler.request_job("my_group", "pbe_config", {"ENCUT": 500})
    """
    
    def __init__(
        self,
        settings_module: str,
        djangochem_dir: Optional[str] = None
    ):
        """
        Initialize handler with Django configuration.
        
        Args:
            settings_module: Django settings module (e.g., 'orgel', 'toy')
            djangochem_dir: Optional override for DJANGOCHEM_DIR
        """
        self.settings_module = settings_module
        if not djangochem_dir:
            djangochem_dir = HTVSConfigHandler().djangochem_dir
        self.djangochem_dir = djangochem_dir
        self.manage_py = os.path.join(self.djangochem_dir, "manage.py") if self.djangochem_dir else None

    def _run_command(self, cmd: List[str]) -> str:
        """
        Execute Django management command with unified error handling.
        (Kept for backward compatibility and internal tool use)
        """
        if not self.djangochem_dir:
            return "Error: djangochem_dir not configured."
            
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=self.djangochem_dir,
                env={**os.environ, "PYTHONUNBUFFERED": "1"}
            )
            
            if result.returncode != 0:
                return f"Command Failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
            
            return f"Success:\n{result.stdout}"
        
        except Exception as e:
            return f"Execution Error: {str(e)}"

    def request_job(
        self,
        group_name: str,
        chem_config: str,
        details: Dict[str, Any],
        requester: Optional[str] = None,
        parent_pks: Optional[List[int]] = None,
        parent_config: Optional[str] = None,
        limit: Optional[int] = None
    ) -> str:
        """
        Request new HTVS jobs via modular HTVSRequester.
        """
        # Pre-flight validation for Perlmutter
        cp = details.get("compute_platform", "")
        if cp and "perlmutter" in cp.lower():
            if not details.get("project_name"):
                return "Error: 'project_name' is missing but compute_platform is Perlmutter. Please provide it in ~/.atomistic_skills.yaml or tool details."

        try:
            from .requester_handler import HTVSRequester
            requester_obj = HTVSRequester(self.settings_module, self.djangochem_dir)
            job_ids = requester_obj.request_job(
                group_name, chem_config, details,
                parent_config=parent_config,
                parent_pks=parent_pks,
                requester=requester,
                limit=limit
            )
            return f"Success: Requested {len(job_ids)} jobs: {job_ids}"
        except Exception as e:
            import traceback
            return f"Request Error: {str(e)}\n{traceback.format_exc()}"

    def build_jobs(
        self,
        group_name: str,
        inbox_path: Optional[str] = None,
        config_name: Optional[str] = None,
        limit: Optional[int] = None,
        compute_platform: Optional[str] = None
    ) -> str:
        """
        Build HTVS job directories via modular HTVSBuilder.
        """
        try:
            if not inbox_path:
                htvs_job_root = os.environ.get("HTVS_JOB_ROOT")
                if htvs_job_root:
                    inbox_path = os.path.join(htvs_job_root, "inbox")
                else:
                    inbox_path = os.path.join(os.getcwd(), "inbox")
            
            from .builder_handler import HTVSBuilder
            builder = HTVSBuilder(self.settings_module, self.djangochem_dir)
            job_paths = builder.build_jobs(
                group_name, inbox_path,
                config_name=config_name,
                limit=limit,
                compute_platform=compute_platform
            )
            return f"Success: Built {len(job_paths)} job directories in {inbox_path}."
        except Exception as e:
            import traceback
            return f"Building Error: {str(e)}\n{traceback.format_exc()}"

    def parse_jobs(
        self,
        group_name: str,
        completed_path: str,
        config_name: Optional[str] = None,
        limit: Optional[int] = None
    ) -> str:
        """
        Parse completed HTVS jobs via modular HTVSParser.
        """
        try:
            from .parser_handler import HTVSParser
            parser = HTVSParser(self.settings_module, self.djangochem_dir)
            result = parser.parse_jobs(group_name, completed_path, config_name, limit)
            return f"Success: Parsed {result['parsed_count']} jobs across {len(result['configs'])} configurations."
        except Exception as e:
            import traceback
            return f"Parsing Error: {str(e)}\n{traceback.format_exc()}"

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
        Request follow-up jobs via modular HTVSRequester.
        """
        try:
            from .requester_handler import HTVSRequester
            requester_obj = HTVSRequester(self.settings_module, self.djangochem_dir)
            job_ids = requester_obj.request_followup_job(
                group_name, chem_config, parent_job_pks, details,
                requester=requester,
                parent_config=parent_config
            )
            return f"Success: Requested {len(job_ids)} follow-up jobs: {job_ids}"
        except Exception as e:
            import traceback
            return f"Request Error: {str(e)}\n{traceback.format_exc()}"

    def monitor_jobs(self, group_name: str) -> str:
        """
        Modular monitor placeholder.
        """
        return "Monitoring triggered (Modular Monitor placeholder)."
