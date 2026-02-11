#!/usr/bin/env python
"""Verify MatGL model loading."""
import sys
import os
import logging

# Add project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger("MatGLVerification")

MATGL_MODELS = [
    "CHGNet-MatPES-PBE-2025.2.10-2.7M-PES", "CHGNet-MatPES-r2SCAN-2025.2.10-2.7M-PES",
    "CHGNet-MPtrj-2024.2.13-11M-PES", "CHGNet-MPtrj-2023.12.1-2.7M-PES",
    "M3GNet-MP-2021.2.8-PES", "M3GNet-MatPES-PBE-v2025.1-PES",
    "M3GNet-MatPES-r2SCAN-v2025.1-PES", "M3GNet-MP-2021.2.8-DIRECT-PES",
    "TensorNet-MatPES-PBE-v2025.1-PES", "TensorNet-MatPES-r2SCAN-v2025.1-PES",
    "M3GNet-ANI-1x-Subset-PES", "SO3Net-ANI-1x-Subset-PES"
]

def main():
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
    
    # Summary
    print("\nXXX_SUMMARY_START_XXX")
    print("Agent: matgl")
    for model, status in results.items():
        print(f"{model}: {status}")
    print("XXX_SUMMARY_END_XXX")
    
    # Exit with error if any failed
    if any("FAILED" in s for s in results.values()):
        sys.exit(1)

if __name__ == "__main__":
    main()
