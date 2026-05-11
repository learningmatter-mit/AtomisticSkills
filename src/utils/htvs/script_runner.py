"""
HTVS Django Script Execution.

This module provides utilities for executing Python scripts within the
HTVS Django environment, either via in-process Django setup or subprocess
execution with the Django boilerplate injected automatically.
"""

import os
import sys
import subprocess
import tempfile
import logging
from typing import Optional

from .config_handler import HTVSConfigHandler

logger = logging.getLogger(__name__)


def setup_django(
    settings_module: str,
    djangochem_dir: Optional[str] = None,
    htvs_dir: Optional[str] = None,
) -> None:
    """Initialize the Django environment in-process.

    Resolves ``djangochem_dir`` and ``htvs_dir`` from
    :class:`HTVSConfigHandler` when not provided explicitly.  The
    settings module is normalized so that short names like ``"orgel"``
    are automatically expanded to ``"djangochem.settings.orgel"``.

    Must be called **once** before any Django ORM imports in a script.

    Args:
        settings_module: Django settings module.  Short aliases such as
            ``"orgel"`` or ``"toy"`` are accepted in addition to the
            fully-qualified ``"djangochem.settings.orgel"`` form.
        djangochem_dir: Absolute path to the djangochem project root.  If
            *None*, the value stored in ``HTVSConfigHandler`` is used.
        htvs_dir: Absolute path to the HTVS repository root.  If *None*,
            the value stored in ``HTVSConfigHandler`` is used.

    Raises:
        RuntimeError: If neither the caller nor ``HTVSConfigHandler``
            provides a valid ``djangochem_dir``.
    """
    # Resolve paths from config when not explicitly passed
    if not djangochem_dir or not htvs_dir:
        config = HTVSConfigHandler().load_config()
        djangochem_dir = djangochem_dir or config.get("htvs_djangochem_dir")
        htvs_dir = htvs_dir or config.get("htvs_dir")

    if not djangochem_dir:
        raise RuntimeError(
            "djangochem_dir is required but not configured. "
            "Pass --djangochem or set htvs_djangochem_dir in the HTVS config."
        )

    # Inject paths so Django apps and htvs packages are importable
    for path in [
        os.path.abspath(djangochem_dir),
        os.path.abspath(os.path.join(djangochem_dir, "..")),
    ]:
        if path not in sys.path:
            sys.path.insert(0, path)

    if htvs_dir and os.path.abspath(htvs_dir) not in sys.path:
        sys.path.insert(0, os.path.abspath(htvs_dir))

    # Normalize settings module
    if not settings_module.startswith("djangochem.settings."):
        settings_module = f"djangochem.settings.{settings_module}"

    os.environ["DJANGO_SETTINGS_MODULE"] = settings_module

    import django
    django.setup()
    logger.debug("Django configured with settings: %s", settings_module)


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
sys.path.append("{os.path.dirname(os.path.abspath(__file__))}")
# Ensure the root of AtomisticSkills is in the path to allow 'src.*' imports
sys.path.append(os.path.abspath(os.path.join("{os.path.dirname(os.path.abspath(__file__))}", "../../..")))

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
