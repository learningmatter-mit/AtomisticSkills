
import os
import yaml
import sys
import argparse
from typing import Optional

def require_mp2020_correction(mlip_name: str, head_name: Optional[str] = None) -> bool:
    """
    Check if a given MLIP model (and optional head) requires MP2020 energy corrections.
    
    Args:
        mlip_name (str): Name of the MLIP model (e.g., "MACE-MH-1").
        head_name (str, optional): Name of the model head (e.g., "omat_pbe").
        
    Returns:
        bool: True if MP2020 correction is required, False otherwise.
    """
    # Locate the YAML file relative to this script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    yaml_path = os.path.join(script_dir, "../resources/gga-ggau-mixed-mlips.yaml")
    
    if not os.path.exists(yaml_path):
        print(f"Warning: Configuration file not found at {yaml_path}")
        return False
        
    try:
        with open(yaml_path, 'r') as f:
            data = yaml.safe_load(f)
            
        checkpoints = data.get("checkpoints_requiring_mp2020_compatibility", [])
        
        for ckpt in checkpoints:
            name_match = ckpt.get("name") == mlip_name
            
            if name_match:
                # If the checkpoint config specifies a head, we must match it
                config_head = ckpt.get("head")
                if config_head:
                    if head_name == config_head:
                        return True
                    else:
                        # Name matched but head didn't match
                        continue
                else:
                    # No head specified in config means it applies to all heads of this model name 
                    # OR the model doesn't use heads.
                    # Assumption: If config has no head, it covers all instances of that name.
                    return True
                    
        return False
        
    except Exception as e:
        print(f"Error reading compatibility configuration: {e}")
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Check if an MLIP requires MP2020 energy corrections.")
    parser.add_argument("--name", type=str, required=True, help="MLIP Model Name")
    parser.add_argument("--head", type=str, default=None, help="Model Head Name (optional)")
    
    args = parser.parse_args()
    
    required = require_mp2020_correction(args.name, args.head)
    print(f"Requires MP2020 Correction: {required}")
    
    # Exit with status 0 if True, 1 if False (useful for shell scripts)
    sys.exit(0 if required else 1)
