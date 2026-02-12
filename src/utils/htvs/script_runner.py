"""
HTVS Django Script Execution.

This module provides utilities for executing Python scripts within the
HTVS Django environment.
"""

import os
import sys
import subprocess
import tempfile
import logging
from typing import Optional

from .config_handler import HTVSConfigHandler

logger = logging.getLogger(__name__)


def run_htvs_script(
    script_body: str,
    settings_module: str = "orgel",
    djangochem_dir: Optional[str] = None,
    htvs_dir: Optional[str] = None
) -> str:
    """
    Execute a Python script within the HTVS Django environment.
    
    Args:
        script_body: Python code to execute
        settings_module: Django settings module (e.g., 'orgel', 'toy')
        djangochem_dir: Optional override for DJANGOCHEM_DIR
        htvs_dir: Optional override for HTVS_DIR
    
    Returns:
        stdout from script execution
        
    Raises:
        RuntimeError: If HTVS environment is not configured
    """
    # Load config if paths not provided
    if not djangochem_dir or not htvs_dir:
        handler = HTVSConfigHandler()
        config = handler.load_config()
        djangochem_dir = djangochem_dir or config.get("htvs_djangochem_dir")
        htvs_dir = htvs_dir or config.get("htvs_dir")
    
    if not djangochem_dir or not htvs_dir:
        return "Error: HTVS environment not configured."
    
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as temp_file:
        temp_file_path = temp_file.name
        
        boilerplate = f"""
import sys
import os
import django
import json

# Add HTVS paths
sys.path.append("{htvs_dir}")
sys.path.append("{djangochem_dir}")
sys.path.append(os.path.abspath(os.path.join("{djangochem_dir}", "..")))

settings_mod = "{settings_module}"
if not settings_mod.startswith("djangochem.settings."):
    settings_mod = "djangochem.settings." + settings_mod

os.environ.setdefault("DJANGO_SETTINGS_MODULE", settings_mod)
# Force override
os.environ["DJANGO_SETTINGS_MODULE"] = settings_mod

try:
    django.setup()
except Exception as e:
    print(json.dumps({{"error": f"Django setup failed: {{str(e)}}"}}))
    sys.exit(1)

"""
        temp_file.write(boilerplate + script_body)
    
    try:
        cmd = [sys.executable, temp_file_path]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            env={**os.environ, "PYTHONUNBUFFERED": "1"}
        )
        
        if result.returncode != 0:
            return f"Script Execution Failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        
        return result.stdout.strip()
    
    except Exception as e:
        return f"Execution Error: {str(e)}"
    finally:
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
