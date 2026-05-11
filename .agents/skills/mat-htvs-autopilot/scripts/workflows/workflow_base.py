from abc import ABC, abstractmethod
import os
import sys
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

class BaseHTVSWorkflow(ABC):
    """
    Base class for HTVS workflows.
    Custom workflows should inherit from this class and implement the abstract methods.
    """
    
    def __init__(self, settings: str, group_name: str, research_dir: str = "."):
        self.settings = settings
        self.group_name = group_name
        self.research_dir = research_dir
        self.python_exe = sys.executable

    @abstractmethod
    def pre_flight_check(self) -> bool:
        """
        Perform checks before starting the monitor loop.
        E.g., verify stoichiometric references, partition availability, etc.
        """
        pass

    @abstractmethod
    def post_process(self) -> bool:
        """
        Perform analysis or follow-up actions after all jobs are completed.
        E.g., run analysis scripts, generate plots, request refinement jobs.
        """
        pass

    def get_job_counts(self) -> Dict[str, int]:
        """
        Get counts of pending/done jobs in the database for the current group.
        Returns a dictionary with status counts.
        """
        import django
        import sys
        # Need to ensure HTVS paths are available to avoid missing confgen ModuleNotFoundError
        sys.path.insert(0, "/mnt/data0/hojechun/repos/htvs")
        sys.path.insert(0, "/mnt/data0/hojechun/repos/htvs/djangochem")
        os.environ['DJANGO_SETTINGS_MODULE'] = self.settings
        django.setup()
        from jobs.models import Job
        
        jobs = Job.objects.filter(group__name=self.group_name)
        pending = jobs.exclude(status='done').count()
        done = jobs.filter(status='done').count()
        total = jobs.count()
        
        return {
            "pending": pending,
            "done": done,
            "total": total
        }

    def run_subcommand(self, cmd: List[str]) -> bool:
        """Helper to run a subcommand and log output."""
        import subprocess
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            logger.debug(f"Subcommand stdout: {result.stdout}")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Subcommand failed: {e.stderr}")
            return False
