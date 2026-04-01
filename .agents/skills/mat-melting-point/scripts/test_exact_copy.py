import sys
from pathlib import Path
sys.path.append("/home/bdeng/projects/simulation_mcp")
import numpy as np
import os
import logging

from src.utils.mlips.mace.mace_wrapper import MACEWrapper

logging.basicConfig(level=logging.INFO)

def main():
    research_dir = Path("/home/bdeng/projects/simulation_mcp/research/2026-01-26_Al_melting_point_MACE")
    solid_path = research_dir / "Al_solid.cif"
    liquid_path = research_dir / "Al_liquid.cif"
    
    wrapper = MACEWrapper(model_name="MACE-OMAT-0-small", device="cuda")
    wrapper.load()
    
    print("Extracting solid features (MACE)...")
    solid_res = wrapper.predict_atomic_features(str(solid_path))
    solid_feats = np.array(solid_res["atomic_features"])
    solid_mean = np.mean(solid_feats, axis=0)
    
    print("Extracting liquid features (MACE)...")
    liquid_res = wrapper.predict_atomic_features(str(liquid_path))
    liquid_feats = np.array(liquid_res["atomic_features"])
    liquid_mean = np.mean(liquid_feats, axis=0)
    
    ref_file = research_dir / "phase_references.npz"
    np.savez(ref_file, solid_mean=solid_mean, liquid_mean=liquid_mean, model_name="MACE-OMAT-0-small")
    print(f"Saved references to {ref_file}")

if __name__ == "__main__":
    main()
