
import os
import sys
import json
import logging
from typing import List, Optional, Dict, Any

logger = logging.getLogger(__name__)

class HTVSJobHandler:
    """
    Modular HTVS Job Handler that interacts with Django models directly.
    Replaces the need for manage.py subprocess calls.
    """
    
    def __init__(
        self,
        settings_module: str,
        djangochem_dir: Optional[str] = None
    ):
        self.settings_module = settings_module
        if not djangochem_dir:
            from .config_handler import HTVSConfigHandler
            djangochem_dir = HTVSConfigHandler().djangochem_dir
        self.djangochem_dir = djangochem_dir
        
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
