#!/usr/bin/env python
"""Verify MACE model loading."""
import sys
import os
import logging

# Add project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger("MACEVerification")

MACE_MODELS = [
    "MACE-MH-1", "MACE-MH-0",
    "MACE-MP-small", "MACE-MP-medium", "MACE-MP-large",
    "MACE-OMAT-0-small", "MACE-OMAT-0-medium",
    "MACE-MATPES-PBE-0", "MACE-MATPES-R2SCAN-0",
    "MACE-OFF23-small", "MACE-OFF23-medium", "MACE-OFF23-large",
    "MACE-ANI-CC", "MACE-OMOL-extra-large"
]

def main():
    logger.info("Verifying MACE models...")
    from src.utils.mlips.mace.mace_wrapper import MACEWrapper
    
    results = {}
    for model_name in MACE_MODELS:
        logger.info(f"Testing load: {model_name}")
        try:
            wrapper = MACEWrapper(model_name=model_name, device="cpu")  # Use CPU to avoid OOM
            wrapper.load()
            logger.info(f"SUCCESS: {model_name}")
            results[model_name] = "SUCCESS"
        except Exception as e:
            logger.error(f"FAILED: {model_name} - {str(e)}")
            results[model_name] = f"FAILED: {str(e)}"
    
    # Summary
    print("\nXXX_SUMMARY_START_XXX")
    print("Agent: mace")
    for model, status in results.items():
        print(f"{model}: {status}")
    print("XXX_SUMMARY_END_XXX")
    
    # Exit with error if any failed
    if any("FAILED" in s for s in results.values()):
        sys.exit(1)

if __name__ == "__main__":
    main()
