import os
import logging
import subprocess
from .workflow_base import BaseHTVSWorkflow

logger = logging.getLogger(__name__)

class TaskWorkflow(BaseHTVSWorkflow):
    """
    Declarative workflow that executes shell commands from a task dictionary.
    Supports variable interpolation using {var} syntax.
    """
    
    def __init__(self, settings, group_name, research_dir="."):
        super().__init__(settings, group_name, research_dir)
        self.pre_flight_cmds = []
        self.post_process_cmds = []
        self.active_monitoring_cmds = []
        self.vars = {}

    def set_task(self, task_data, vars_dict):
        """Load task configuration and variables."""
        self.pre_flight_cmds = task_data.get("pre_flight", [])
        self.post_process_cmds = task_data.get("post_process", [])
        self.active_monitoring_cmds = task_data.get("active_monitoring", [])
        self.vars = vars_dict
        
        # Ensure some standard vars are present
        self.vars.setdefault("settings", self.settings)
        self.vars.setdefault("group_name", self.group_name)
        self.vars.setdefault("research_dir", self.research_dir)
        self.vars.setdefault("python_exe", self.python_exe)
        
        # Add djangochem_dir if available in base class
        if hasattr(self, "djangochem_dir") and self.djangochem_dir:
            self.vars.setdefault("djangochem_dir", self.djangochem_dir)

    def _run_cmds(self, cmds, stage_name):
        """Run a list of commands with interpolation."""
        if not cmds:
            logger.info(f"{stage_name}: No commands to run.")
            return True
            
        for cmd_template in cmds:
            try:
                cmd_str = cmd_template.format(**self.vars)
            except KeyError as e:
                logger.error(f"{stage_name}: Missing variable for interpolation: {e}")
                return False
                
            logger.info(f"{stage_name}: Executing -> {cmd_str}")
            # Use shell=True to support pipes/redirection if needed in tasks
            # But we should be careful. For safety, we'll use a split list if no shell chars.
            try:
                subprocess.run(cmd_str, shell=True, check=True, text=True)
            except subprocess.CalledProcessError as e:
                logger.error(f"{stage_name}: Command failed with exit code {e.returncode}")
                return False
        return True

    def pre_flight_check(self) -> bool:
        logger.info("TASK_WF: Running pre-flight steps...")
        return self._run_cmds(self.pre_flight_cmds, "PRE_FLIGHT")

    def run_active_monitoring(self) -> bool:
        """Executes the active monitoring scripts without aborting on failure."""
        if self.active_monitoring_cmds:
            logger.info("TASK_WF: Running active monitoring steps...")
            # We don't want a failure in monitoring to abort the main polling loop, 
            # so we catch exceptions internally if needed, but _run_cmds logs and returns False.
            self._run_cmds(self.active_monitoring_cmds, "ACTIVE_MONITORING")
        return True

    def post_process(self) -> bool:
        logger.info("TASK_WF: Running post-processing steps...")
        return self._run_cmds(self.post_process_cmds, "POST_PROCESS")
