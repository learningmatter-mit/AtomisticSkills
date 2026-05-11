
import os
import sys
import json
import django
import logging
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

class HTVSRequester:
    """
    Modular HTVS Requester that interacts with JobRequester directly.
    Replaces the need for manage.py requestjobs CLI calls.
    """
    def __init__(self, settings_module: str, djangochem_dir: Optional[str] = None):
        self.settings_module = settings_module
        if not djangochem_dir:
            from .config_handler import HTVSConfigHandler
            djangochem_dir = HTVSConfigHandler().djangochem_dir
            
        if djangochem_dir not in sys.path:
            sys.path.insert(0, djangochem_dir)
            
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', settings_module)
        from django.apps import apps
        if not apps.ready:
            django.setup()
        
    def request_job(
        self,
        group_name: str,
        config_name: str,
        details: Dict[str, Any],
        parent_config: Optional[str] = None,
        parent_pks: Optional[List[int]] = None,
        requester: Optional[str] = None,
        limit: Optional[int] = None,
        force: bool = False
    ) -> List[int]:
        """
        Equivalent to manage.py requestjobs.
        """
        from jobs import jobrequester
        
        # request_jobs returns a list of Job objects
        jobs = jobrequester.request_jobs(
            project=group_name,
            requested_config_name=config_name,
            details=details,
            parent_config_name=parent_config,
            parentpks=parent_pks,
            requester=requester,
            limit=limit,
            force=force,
            avoid_dupes=True # Default for HTVS
        )
        
        return [j.id for j in jobs]

    def request_followup_job(
        self,
        group_name: str,
        chem_config: str,
        parent_job_pks: List[int],
        details: Dict[str, Any],
        requester: Optional[str] = None,
        parent_config: Optional[str] = None
    ) -> List[int]:
        """
        Request jobs for specific parent jobs.
        """
        return self.request_job(
            group_name=group_name,
            config_name=chem_config,
            details=details,
            parent_pks=parent_job_pks,
            requester=requester,
            parent_config=parent_config
        )
