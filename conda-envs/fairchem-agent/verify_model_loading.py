#!/usr/bin/env python
"""Verify FairChem model loading."""
import sys
import os
import logging

# Add project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger("FairChemVerification")

FAIRCHEM_MODELS = [
    "uma-s-1p1", "uma-m-1p1",
    "esen-md-direct-all-omol", "esen-sm-conserving-all-omol", "esen-sm-direct-all-omol",
    # "esen-sm-conserving-all-oc25", "esen-md-direct-all-oc25"
]

def main():
    logger.info("Verifying FairChem models...")
    from src.utils.mlips.fairchem.fairchem_wrapper import FAIRCHEMWrapper
    
    results = {}
    for model_name in FAIRCHEM_MODELS:
        logger.info(f"Testing load: {model_name}")
        try:
            wrapper = FAIRCHEMWrapper(model_name=model_name, device="cpu")
            wrapper.load()
            logger.info(f"SUCCESS: {model_name}")
            results[model_name] = "SUCCESS"
        except Exception as e:
            logger.error(f"FAILED: {model_name} - {str(e)}")
            results[model_name] = f"FAILED: {str(e)}"
    
    # Summary
    print("\nXXX_SUMMARY_START_XXX")
    print("Agent: fairchem")
    for model, status in results.items():
        print(f"{model}: {status}")
    print("XXX_SUMMARY_END_XXX")
    
    # Exit with error if any failed
    if any("FAILED" in s for s in results.values()):
        sys.exit(1)

if __name__ == "__main__":
    main()
