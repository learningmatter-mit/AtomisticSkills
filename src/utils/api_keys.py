"""
API keys configuration management for MLIP Agent
"""

import os
import yaml
from pathlib import Path
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


def load_api_keys(config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Load API keys from configuration file or environment variables.
    
    Args:
        config_path: Path to the API keys configuration file.
                    If None, looks for 'api_keys.yaml' in the project root.
    
    Returns:
        Dictionary containing API keys and configuration.
    """
    if config_path is None:
        # Look for api_keys.yaml in the project root
        # File is at src/utils/api_keys.py
        # Root is AtomisticSkills/
        project_root = Path(__file__).parent.parent.parent
        config_path = project_root / "api_keys.yaml"
    
    config_path = Path(config_path)
    
    config = {}
    
    # Load from file if it exists
    if config_path.exists():
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f) or {}
            logger.info(f"Loaded API keys from {config_path}")
        except Exception as e:
            logger.warning(f"Failed to load config from {config_path}: {e}")
            config = {}
    
    # Override with environment variables if available
    env_config = {
        "openai": {
            "api_key": os.getenv("OPENAI_API_KEY")
        },
        "materials_project": {
            "api_key": os.getenv("MP_API_KEY")
        }
    }
    
    # Merge configurations (environment variables take precedence)
    for service, keys in env_config.items():
        if service not in config:
            config[service] = {}
        for key, value in keys.items():
            if value is not None:
                config[service][key] = value
                logger.info(f"Using {service}.{key} from environment variable")
    
    return config


def get_openai_key(config: Optional[Dict[str, Any]] = None) -> str:
    """
    Get OpenAI API key from configuration.
    """
    if config is None:
        config = load_api_keys()
    
    api_key = config.get("openai", {}).get("api_key")
    if not api_key:
        raise ValueError(
            "OpenAI API key not found. Please set OPENAI_API_KEY environment variable "
            "or add it to api_keys.yaml file."
        )
    
    return api_key


def get_mp_key(config: Optional[Dict[str, Any]] = None) -> Optional[str]:
    """
    Get Materials Project API key from configuration.
    """
    if config is None:
        config = load_api_keys()
    
    api_key = config.get("materials_project", {}).get("api_key")
    if not api_key:
        logger.warning(
            "Materials Project API key not found. Some features may not work. "
            "Please set MP_API_KEY environment variable or add it to api_keys.yaml file."
        )
    
    return api_key


def validate_api_keys(config: Optional[Dict[str, Any]] = None) -> bool:
    """
    Validate that required API keys are available.
    """
    try:
        get_openai_key(config)
        return True
    except ValueError:
        return False
