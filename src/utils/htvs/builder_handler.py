
import os
import sys
import json
import django
import logging
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

class HTVSBuilder:
    """
    Modular HTVS Builder that interacts with JobDirBuilder directly.
    Replaces the need for manage.py buildjobs CLI calls.
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
        
    def build_jobs(
        self,
        group_name: str,
        inbox_path: str,
        config_name: Optional[str] = None,
        limit: Optional[int] = None,
        compute_platform: Optional[str] = None,
        batch_size: int = 1,
        num_parallel: int = 1
    ) -> List[str]:
        """
        Equivalent to manage.py buildjobs.
        """
        from jobs.models import Job, JobConfig
        from pgmols.models import Group
        from jobs.dbinterface.postgresinterface import PostgresInterface
        from jobs.jobdirbuilder import JobDirBuilder
        
        group = Group.objects.get(name=group_name)
        
        if config_name:
            # Resolve config_name if it's a path
            if os.path.isdir(config_name) and not config_name.endswith(".json"):
                 config_json_path = os.path.join(config_name, "config.json")
            else:
                 config_json_path = config_name
                 
            # Find the JobConfig object
            if os.path.exists(config_json_path):
                with open(config_json_path) as f:
                    cfg_data = json.load(f)
                jc = JobConfig.objects.get(name=cfg_data["name"])
            else:
                jc = JobConfig.objects.get(name=config_name)
        else:
            # Find the most common config for claimed jobs?
            # Buildjobs logic:
            query = Job.objects.filter(status__in=["", "error"], group=group)
            job_configs = JobConfig.objects.filter(pk__in=query.values_list("config", flat=True).distinct())
            if job_configs.count() != 1:
                raise ValueError(f"Found {job_configs.count()} configs. Please specify one.")
            jc = job_configs[0]
            
        config_path = jc.configpath
        if not os.path.exists(config_path):
            htvs_dir = os.getenv("HTVSDIR")
            if htvs_dir:
                config_path = os.path.join(htvs_dir, "djangochem", config_path)
        
        with open(config_path) as f:
            config = json.load(f)
            
        config_dir = os.path.dirname(config_path)
        db_interface = PostgresInterface()
        
        if compute_platform and config.get(compute_platform):
            compute_dict = config[compute_platform]
        else:
            compute_dict = config
            
        builder = JobDirBuilder(
            name=jc.name,
            project=group_name,
            config_path=config_dir,
            db_interface=db_interface,
            job_filename=compute_dict["job_template_filename"],
            storage_kwargs={"inbox_job_dir": inbox_path},
            jobspec_prep_module_name=config.get("jobspec_prep"),
            batch_filename=compute_dict.get("batch_template_filename"),
            batch_temp_names=compute_dict.get("extra_batch_template_filenames"),
            compute_platform=compute_platform,
            template_filenames=config.get("extra_template_filenames", [])
        )
        
        job_dirs = builder.build_job_dirs(
            limit=limit,
            batch_size=batch_size,
            num_parallel=num_parallel
        )
        
        return [jd["storage"].job_path for jd in job_dirs]
