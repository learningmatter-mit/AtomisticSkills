"""
Calculate and plot Equilibrium Phase Fractions vs Temperature using PyCalphad.

Usage:
    python plot_phase_fractions.py input.tdb --elements Al Zn --composition Zn 0.1 --t-range 300 1000 10 --output phase_fractions.png

Requirements:
    - Conda environment: calphad-agent
    - Required packages: pycalphad, matplotlib
"""
import argparse
import logging
import matplotlib.pyplot as plt
from pycalphad import Database, equilibrium
import pycalphad.variables as v
import numpy as np

logging.basicConfig(level=logging.INFO)

def main():
    parser = argparse.ArgumentParser(description="Plot equilibrium phase fractions vs temperature for a specific alloy.")
    parser.add_argument("tdb", help="Path to the Thermodynamic Database (.tdb) file.")
    parser.add_argument("--elements", nargs=2, required=True, help="The two atomic elements (e.g., Al Zn).")
    parser.add_argument("--composition", nargs=2, required=True, help="Target solute element and its mole fraction (e.g., Zn 0.1).")
    parser.add_argument("--t-range", nargs=3, type=float, default=[300, 1000, 10], 
                        help="Temperature range and step in Kelvin: START STOP STEP.")
    parser.add_argument("--output", default="phase_fractions.png", help="Path to save the resulting plot.")
    
    args = parser.parse_args()

    el1, el2 = args.elements[0].upper(), args.elements[1].upper()
    solute, comp_val = args.composition[0].upper(), float(args.composition[1])

    logging.info(f"Loading database from {args.tdb}...")
    dbf = Database(args.tdb)
    
    comps = [el1, el2, 'VA'] 
    phases = list(dbf.phases.keys())
    
    t_start, t_stop, t_step = args.t_range
    
    conds = {
        v.N: 1, 
        v.P: 101325, 
        v.T: (t_start, t_stop, t_step), 
        v.X(solute): comp_val
    }

    logging.info(f"Calculating Equilibrium for {comps} at X({solute})={comp_val}...")
    eq = equilibrium(dbf, comps, phases, conds)
    
    logging.info("Plotting Phase Fractions...")
    fig, ax = plt.subplots(figsize=(8, 6))
    
    # eq.NP gives the phase fractions (Molar Amount of Phase)
    # eq.Phase gives the name of the phase present
    
    temperatures = eq.T.values
    for phase_name in phases:
        # Get phase indices where the phase is present
        phase_indices = np.nonzero(eq.Phase.values == phase_name)
        if len(phase_indices[0]) > 0:
            # We plot NP (phase fraction) for this phase
            # Flatten across the temperature dimensions safely
            phase_fractions = np.zeros_like(temperatures)
            for temp_idx in range(len(temperatures)):
                # Find if phase exists at this temp
                idx = np.where(eq.Phase.values[0, 0, temp_idx, 0, :] == phase_name)[0]
                if len(idx) > 0:
                    phase_fractions[temp_idx] = eq.NP.values[0, 0, temp_idx, 0, idx[0]]
            
            # Only plot if it actually appears in >= 1% amount at some point
            if np.max(phase_fractions) > 1e-3:
                ax.plot(temperatures, phase_fractions, label=phase_name, linewidth=2)

    ax.set_title(f"Phase Fractions: {el1}-{comp_val*100}% {solute}")
    ax.set_xlabel("Temperature (K)")
    ax.set_ylabel("Phase Fraction")
    ax.set_ylim(-0.05, 1.05)
    ax.grid(alpha=0.3)
    ax.legend(loc='upper right')
    
    plt.savefig(args.output, dpi=300, bbox_inches='tight')

    # Save input configs for reproducibility
    from src.utils.config_utils import save_skill_inputs
    save_skill_inputs(args, args.output_dir)
    _params_path.parent.mkdir(parents=True, exist_ok=True)
    _params_path.write_text(_json.dumps(_config, indent=2, default=str))
    logging.info(f"Phase fractions plot successfully saved to {args.output}")

if __name__ == "__main__":
    main()
