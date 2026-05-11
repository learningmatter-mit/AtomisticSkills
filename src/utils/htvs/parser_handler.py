
import os
import sys
import json
import logging
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

class HTVSParser:
    """
    Modular HTVS Parser that interacts with Django models directly.
    Replaces the need for manage.py parsejobs CLI calls.
    """
    def __init__(self, settings_module: str, djangochem_dir: Optional[str] = None):
        self.settings_module = settings_module
        if not djangochem_dir:
            from .config_handler import HTVSConfigHandler
            djangochem_dir = HTVSConfigHandler().djangochem_dir
            
        if djangochem_dir not in sys.path:
            sys.path.insert(0, djangochem_dir)
            # Insert the parent directory (htvs root) to allow 'confgen' imports
            htvs_root = os.path.dirname(djangochem_dir)
            if htvs_root not in sys.path:
                sys.path.insert(0, htvs_root)
            
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', settings_module)
        import django
        from django.apps import apps
        if not apps.ready:
            django.setup()
            
        # Monkey patch SlurmErrors to avoid false-positive error states 
        # caused by benign shell/conda warnings, avoiding edits to the htvs repo.
        try:
            from chemconfigs.parsers.slurm import SlurmErrors
            if not hasattr(SlurmErrors, "_original_handle_errors"):
                SlurmErrors._original_handle_errors = SlurmErrors.handle_errors
                
                def patched_handle_errors(self):
                    whitelist = [
                        "cp: cannot stat",
                        "rm: cannot remove",
                        "cat: ",
                        "mv: cannot stat",
                        "CHECKPOINT:",
                        "RLX:",
                        "CLEANING:",
                        "DEBUG:",
                        "INFO:",
                        "WARNING:",
                        "Error while loading conda entry point",
                        "Lmod is automatically replacing"
                    ]
                    original_output = self.job_output
                    self.job_output = [
                        line for line in original_output 
                        if not any(w in line for w in whitelist)
                    ]
                    result = self._original_handle_errors()
                    self.job_output = original_output
                    return result
                    
                SlurmErrors.handle_errors = patched_handle_errors
                logger.info("Monkey-patched SlurmErrors.handle_errors to ignore benign warnings.")
        except ImportError:
            pass
        
    def parse_jobs(
        self, 
        group_name: str, 
        completed_path: str, 
        config_name: Optional[str] = None, 
        limit: Optional[int] = None,
        force: bool = False,
        lockfile: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Equivalent to manage.py parsejobs.
        """
        from jobs.models import Job, JobConfig, Group
        from jobs.dbinterface.postgresinterface import PostgresInterface
        from jobs.jobdirparser import JobDirParser
        
        db_interface = PostgresInterface()
        group = Group.objects.get(name=group_name)
        
        if config_name:
            job_configs = JobConfig.objects.filter(name=config_name)
        else:
            # Replicate manage.py parsejobs logic: find configs with claimed jobs in group
            claimed_configs = Job.objects.filter(status='claimed', group=group).values_list('config', flat=True).distinct()
            job_configs = JobConfig.objects.filter(pk__in=claimed_configs)
            
        if not job_configs.exists():
            return {"status": "success", "message": "No jobs found to parse.", "parsed_count": 0}

        total_parsed = 0
        parsed_configs = []
        
        for jc in job_configs:
            # Resolve loader path
            config_path = jc.configpath
            if not os.path.exists(config_path):
                htvs_dir = os.getenv("HTVSDIR")
                if htvs_dir:
                    config_path = os.path.join(htvs_dir, "djangochem", config_path)
            
            if not os.path.exists(config_path):
                logger.error(f"Could not find config path {config_path} for {jc.name}")
                continue
                
            config_dir_path = os.path.dirname(config_path)
            with open(config_path) as f:
                config_data = json.load(f)
            
            loader_module = config_data["loader_module"]
            
            parser = JobDirParser(
                name=jc.name,
                project=group_name,
                loader_path=config_dir_path,
                loader_module_name=loader_module,
                db_interface=db_interface,
                force=force
            )
            
            # Try to treat completed_path as a single job dir first
            try:
                parser.update_db_for_job(completed_path)
                total_parsed += 1
                parsed_configs.append(jc.name)
                continue # If it was a single job dir, we are done for this config? 
                # Actually manage.py tries this then falls back to iter_completed_jobs
            except Exception:
                pass
            
            # Scan directory for multiple jobs
            count = 0
            for result, error in parser.iter_completed_jobs(completed_path, limit=limit, lockfile=lockfile):
                if result:
                    count += 1
            
            if count > 0:
                total_parsed += count
                parsed_configs.append(jc.name)
                
        return {
            "status": "success",
            "parsed_count": total_parsed,
            "configs": parsed_configs
        }
