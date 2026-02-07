
import argparse
import sys
import os
import logging
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).resolve().parents[4]))

from src.utils.mlips.mace.mace_wrapper import MACEWrapper

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("RelaxWrapper")

def main():
    parser = argparse.ArgumentParser(description="Run MACE relaxation via MACEWrapper")
    parser.add_argument("--input_dir", required=True, help="Directory containing input structures")
    parser.add_argument("--output_dir", required=True, help="Directory to save relaxed structures")
    parser.add_argument("--model", default="medium", help="MACE model size (small, medium, large)")
    parser.add_argument("--fmax", type=float, default=0.05, help="Force convergence criterion")
    parser.add_argument("--device", default="cuda", help="Device to run on")
    
    args = parser.parse_args()
    
    # Initialize Wrapper
    # Map 'small/medium' to actual model names if needed, but MACEWrapper might handle "medium" 
    # if we pass it as model path? 
    # MACEWrapper expects model_name to be one of the keys or a path.
    # The MCP tool uses "MACE-MP-medium" etc.
    # Let's try to map generic names to specific MACE-MP models for robustness
    model_map = {
        "small": "MACE-MP-small",
        "medium": "MACE-MP-medium",
        "large": "MACE-MP-large"
    }
    model_name = model_map.get(args.model, args.model)
    
    logger.info(f"Loading model: {model_name}")
    wrapper = MACEWrapper(model_name=model_name, device=args.device)
    wrapper.load()
    
    # Run batch relaxation
    logger.info(f"Relaxing structures in {args.input_dir}")
    os.makedirs(args.output_dir, exist_ok=True)
    
    # MACEWrapper.relax_structure supports directory path
    results = wrapper.relax_structure(
        structure_data=args.input_dir,
        fmax=args.fmax,
        output_dir=args.output_dir,
        relax_cell=True
    )
    
    logger.info("Relaxation complete.")

if __name__ == "__main__":
    main()
