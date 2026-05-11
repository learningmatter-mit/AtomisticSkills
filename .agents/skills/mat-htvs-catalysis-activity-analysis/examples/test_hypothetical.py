import os
import sys
import json
import argparse
from pathlib import Path

# Add project root to python path to access src package
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../..")))

from src.utils.htvs.catalysis_utils import REACTIONS

def test_hypothetical(output_dir: Path, reaction_name: str):
    """Provides standard hypothetical surfaces for testing."""
    print(f"Running in hypothetical test mode for {reaction_name}...")
    
    if reaction_name not in REACTIONS:
         print(f"Error: {reaction_name} not supported.")
         return
         
    mechanism = REACTIONS[reaction_name]()
    
    # Typical electronic binding energies normalized relative to H2O and H2 limits
    # where dE = E(slab+ads) - E(slab) - ...
    test_data = {
        "Pt(111)": {"OH": 0.8, "O": 2.5, "OOH": 4.1},
        "IrO2(110)": {"OH": 0.3, "O": 1.7, "OOH": 3.4},
        "RuO2(110)": {"OH": 0.1, "O": 1.4, "OOH": 3.3},
        "NiFeOx(001)": {"OH": 0.5, "O": 2.1, "OOH": 3.7},
        "Co3O4(311)": {"OH": 0.9, "O": 2.4, "OOH": 4.0},
    }
    
    results = {}
    for name, energies in test_data.items():
        res = mechanism.calculate_steps(energies)
        results[name] = res
        print(f"[{name}] overpotential η = {res['eta']:.3f} V (PDS: Step {res['pds']})")
        
    out_json = output_dir / f"{reaction_name.lower()}_results.json"
    with open(out_json, "w") as f:
        json.dump(results, f, indent=2)
        
    out_step = output_dir / f"{reaction_name.lower()}_free_energy_steps.png"
    out_volc = output_dir / f"{reaction_name.lower()}_volcano.png"
    
    mechanism.plot_free_energy(results, str(out_step))
    mechanism.plot_volcano(results, str(out_volc))
    
    print(f"Saved test output JSON and plot artifacts to {output_dir}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--reaction", type=str, default="OER", choices=list(REACTIONS.keys()), help="Target catalytic reaction mechanism.")
    parser.add_argument("--output_dir", type=str, default=".", help="Output directory for plots")
    args = parser.parse_args()
    
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    test_hypothetical(out_dir, args.reaction)
