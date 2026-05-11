
import os
import yaml
import warnings
from typing import Dict, Any, Optional
from pathlib import Path

# Config file locations
CONFIG_FILE = Path.home() / ".config" / "atomistic_skills.yaml"
OLD_CONFIG_FILE = Path.home() / ".atomistic_skills.yaml"
ENV_VAR_PREFIX = "MLIP_"

def load_config() -> Dict[str, Any]:
    """
    Load configuration from yaml file and environment variables.
    
    Priority:
    1. Environment variables (MLIP_*)
    2. Config file (~/.config/mlip_agent.yaml or ~/.mlip_agent.yaml)
    """
    settings: Dict[str, Any] = {}
    
    # 1. Load from YAML
    config_path = None
    if CONFIG_FILE.exists():
        config_path = CONFIG_FILE
    elif OLD_CONFIG_FILE.exists():
        config_path = OLD_CONFIG_FILE
        
    if config_path:
        try:
            with open(config_path, "r") as f:
                loaded = yaml.safe_load(f)
                if loaded:
                    settings.update(loaded)
        except Exception as e:
            warnings.warn(f"Error loading config from {config_path}: {e}")
            
    # 2. Override with env vars starting with MLIP_
    for key, val in os.environ.items():
        if key.startswith(ENV_VAR_PREFIX):
            clean_key = key[len(ENV_VAR_PREFIX):] # Remove prefix
            settings[clean_key] = val
            
    # 3. Path expansion
    for key, val in settings.items():
        if isinstance(val, str) and (key.endswith("_DIR") or key.endswith("_FILE") or key.endswith("_PATH")):
            settings[key] = os.path.expandvars(os.path.expanduser(val))
            
    return settings

def inject_config_into_env():
    """
    Load config and inject into os.environ if not already set.
    """
    settings = load_config()
    for key, val in settings.items():
        # Only set if not already in env (to allow manual override in shell)
        # OR should we force it? 
        # Pymatgen logic: "Override .pmgrc.yaml with env vars (if present)"
        # But here we are SETTING env vars for other tools.
        # If the user set overrides in their shell, we shouldn't overwrite them.
        if key not in os.environ:
             if isinstance(val, (dict, list)):
                 import json
                 os.environ[key] = json.dumps(val)
             else:
                 os.environ[key] = str(val)


def save_skill_inputs(args, output_path: str):
    """
    Robustly save argparse arguments to an input_configs.yaml file.
    Handles non-standard paths (extracts parent dir if path is a file).
    """
    try:
        import yaml
        from pathlib import Path
        
        # Convert args namespace to dict, handling non-standard types (like Path objects)
        if hasattr(args, "__dict__"):
            cfg = {k: str(v) if hasattr(v, "__fspath__") else v for k, v in vars(args).items()}
        elif isinstance(args, dict):
            cfg = {k: str(v) if hasattr(v, "__fspath__") else v for k, v in args.items()}
        else:
            cfg = {"arguments": str(args)}
            
        if not output_path:
            return
            
        base_path = Path(output_path)
        # If the path looks like a file (has a common config extension), use its parent directory
        if base_path.suffix.lower() in [".yaml", ".yml", ".json", ".txt"]:
            yaml_dir = base_path.parent
        else:
            yaml_dir = base_path
            
        yaml_dir.mkdir(parents=True, exist_ok=True)
        with open(yaml_dir / "input_configs.yaml", "w") as f:
            yaml.dump(cfg, f, default_flow_style=False, sort_keys=False)
    except Exception as e:
        print(f"Warning: Failed to save input_configs.yaml: {e}")
