import os
import sys
from pathlib import Path
from ase.io import read
from pymatgen.ext.matproj import MPRester

# Set MatGL backend BEFORE importing matgl (via wrapper or calculator)
os.environ["MATGL_BACKEND"] = "DGL"

# Add project root and skill scripts to path
project_root = Path(__file__).parents[5].absolute()
sys.path.insert(0, str(project_root))
skill_scripts = project_root / ".agent/skills/sample-pes-by-md/scripts"
sys.path.insert(0, str(skill_scripts))

from feature_calculators import MatGLCrystalFeatureCalculator
from sampler import OffEquilibriumSampler

def sample_limno2_matgl():
    # 1. Get Structure (LiMnO2)
    print("Fetching LiMnO2 structure from Materials Project...")
    try:
        with MPRester() as mpr:
            structure = mpr.get_structure_by_material_id("mp-18767")
            structure.to(filename="LiMnO2_initial.cif")
            atoms = read("LiMnO2_initial.cif")
            print(f"Structure loaded: {atoms.get_chemical_formula()}")
    except Exception as e:
        print(f"Failed to fetch structure: {e}")
        return

    # 2. Setup MatGL (CHGNet)
    # CHGNet-MatPES is a state-of-the-art model for inorganic materials
    print("Loading MatGL model (CHGNet-MatPES-PBE)...")
    from src.utils.mlips.matgl.matgl_wrapper import MatGLWrapper
    wrapper = MatGLWrapper(model_name="CHGNet-MatPES-PBE-2025.2.10-2.7M-PES", device="auto")
    wrapper.load()
    pes_calc = wrapper.create_calculator()

    # 3. Setup Optimized Feature Calculator and Sampler
    # MatGLCrystalFeatureCalculator uses return_all_layer_output=True for single-pass calculation
    print("Setting up optimized calculator and sampler...")
    calc = MatGLCrystalFeatureCalculator(potential=pes_calc)
    
    # 4. Run Off-Equilibrium Sampling
    print("Starting sampling (10 ps, 2000K, 10 samples)...")
    output_dir = "LiMnO2_matgl_results"
    os.makedirs(output_dir, exist_ok=True)

    sampler = OffEquilibriumSampler(
        calculator=calc,
        atoms=atoms,
        total_steps=2000,
        temperature=2000,
        n_clusters=10,
        output_dir=output_dir,
        target_atoms=50
    )
    
    sampled_structures, metadata = sampler.sample()

    print("\n--- MatGL Sampling Results ---")
    print(f"Total MD steps: {metadata['total_steps']}")
    steps = metadata['sampled_md_steps']
    times_ps = [round(s * metadata['time_step'] / 1000.0, 3) for s in steps]
    print(f"Sampled timestamps (ps): {times_ps}")
    print(f"Sampled structures saved to: {output_dir}/")

if __name__ == "__main__":
    sample_limno2_matgl()
