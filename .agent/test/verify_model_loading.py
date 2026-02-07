import sys
import os
import argparse
import logging
from pathlib import Path

# Add project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger("ModelVerification")

# Defined model lists from server files
MACE_MODELS = [
    "MACE-MH-1", "MACE-MH-0",
    "MACE-MP-small", "MACE-MP-medium", "MACE-MP-large",
    "MACE-OMAT-0-small", "MACE-OMAT-0-medium",
    "MACE-MATPES-PBE-0", "MACE-MATPES-R2SCAN-0",
    "MACE-OFF23-small", "MACE-OFF23-medium", "MACE-OFF23-large",
    "MACE-ANI-CC", "MACE-OMOL-extra-large"
]

MATGL_MODELS = [
    "CHGNet-MatPES-PBE-2025.2.10-2.7M-PES", "CHGNet-MatPES-r2SCAN-2025.2.10-2.7M-PES",
    "CHGNet-MPtrj-2024.2.13-11M-PES", "CHGNet-MPtrj-2023.12.1-2.7M-PES",
    "M3GNet-MP-2021.2.8-PES", "M3GNet-MatPES-PBE-v2025.1-PES",
    "M3GNet-MatPES-r2SCAN-v2025.1-PES", "M3GNet-MP-2021.2.8-DIRECT-PES",
    "TensorNet-MatPES-PBE-v2025.1-PES", "TensorNet-MatPES-r2SCAN-v2025.1-PES",
    "M3GNet-ANI-1x-Subset-PES", "SO3Net-ANI-1x-Subset-PES"
]

FAIRCHEM_MODELS = [
    "uma-s-1p1", "uma-m-1p1", "uma-s-1",
    "esen-md-direct-all-omol", "esen-sm-conserving-all-omol", "esen-sm-direct-all-omol",
    "esen-sm-conserving-all-oc25", "esen-md-direct-all-oc25"
]

def verify_mace():
    logger.info("Verifying MACE models...")
    from src.utils.mlips.mace.mace_wrapper import MACEWrapper
    
    results = {}
    for model_name in MACE_MODELS:
        logger.info(f"Testing load: {model_name}")
        try:
            wrapper = MACEWrapper(model_name=model_name, device="cpu") # Use CPU for verification to avoid OOM
            wrapper.load()
            logger.info(f"SUCCESS: {model_name}")
            results[model_name] = "SUCCESS"
        except Exception as e:
            logger.error(f"FAILED: {model_name} - {str(e)}")
            results[model_name] = f"FAILED: {str(e)}"
    return results

def verify_matgl():
    logger.info("Verifying MatGL models...")
    from src.utils.mlips.matgl.matgl_wrapper import MatGLWrapper
    
    results = {}
    for model_name in MATGL_MODELS:
        logger.info(f"Testing load: {model_name}")
        try:
            wrapper = MatGLWrapper(model_name=model_name, device="cpu")
            wrapper.load()
            logger.info(f"SUCCESS: {model_name}")
            results[model_name] = "SUCCESS"
        except Exception as e:
            logger.error(f"FAILED: {model_name} - {str(e)}")
            results[model_name] = f"FAILED: {str(e)}"
    return results

def verify_fairchem():
    logger.info("Verifying FairChem models...")
    from src.utils.mlips.fairchem.fairchem_wrapper import FAIRCHEMWrapper
    
    results = {}
    for model_name in FAIRCHEM_MODELS:
        logger.info(f"Testing load: {model_name}")
        try:
            wrapper = FAIRCHEMWrapper(model_name=model_name, device="cpu")
            # FairChem might require 'inference_settings' for some, but defaults should load
            wrapper.load()
            logger.info(f"SUCCESS: {model_name}")
            results[model_name] = "SUCCESS"
        except Exception as e:
            logger.error(f"FAILED: {model_name} - {str(e)}")
            results[model_name] = f"FAILED: {str(e)}"
    return results

def main():
    parser = argparse.ArgumentParser(description="Verify MLIP model loading")
    parser.add_argument("--agent", required=True, choices=["mace", "matgl", "fairchem"], help="Agent verification target")
    args = parser.parse_args()
    
    if args.agent == "mace":
        results = verify_mace()
    elif args.agent == "matgl":
        results = verify_matgl()
    elif args.agent == "fairchem":
        results = verify_fairchem()
        
    # Summary
    print("\nXXX_SUMMARY_START_XXX")
    print(f"Agent: {args.agent}")
    for model, status in results.items():
        print(f"{model}: {status}")
    print("XXX_SUMMARY_END_XXX")
    
    # Exit with error if any failed
    if any("FAILED" in s for s in results.values()):
        sys.exit(1)

if __name__ == "__main__":
    main()
