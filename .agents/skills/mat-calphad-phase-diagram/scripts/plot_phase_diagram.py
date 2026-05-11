"""
Generate a Binary Temperature-Composition (T-x) Phase Diagram using PyCalphad.

Usage:
    python plot_phase_diagram.py input.tdb --elements Al Zn --t-range 300 1000 10 --output phase_diagram.png

Requirements:
    - Conda environment: calphad-agent
    - Required packages: pycalphad, matplotlib
"""
import argparse
import logging
import matplotlib.pyplot as plt
from pycalphad import Database, binplot
import pycalphad.variables as v

logging.basicConfig(level=logging.INFO)

def main():
    parser = argparse.ArgumentParser(description="Plot a binary phase diagram from a TDB database.")
    parser.add_argument("tdb", help="Path to the Thermodynamic Database (.tdb) file.")
    parser.add_argument("--elements", nargs=2, required=True, help="The two atomic elements to plot (e.g., Al Zn).")
    parser.add_argument("--t-range", nargs=3, type=float, default=[300, 1000, 10], 
                        help="Temperature range and step in Kelvin: START STOP STEP (default: 300 1000 10).")
    parser.add_argument("--output", default="phase_diagram.png", help="Path to save the resulting plot (default: phase_diagram.png).")
    
    args = parser.parse_args()

    # PyCalphad elements are implicitly uppercase in TDB files
    el1, el2 = args.elements[0].upper(), args.elements[1].upper()

    logging.info(f"Loading database from {args.tdb}...")
    dbf = Database(args.tdb)
    
    # In PyCalphad, the 'VA' (Vacancy) component must explicitly be included.
    comps = [el1, el2, 'VA'] 
    
    # Find all phases in the database
    phases = list(dbf.phases.keys())
    logging.info(f"Identified phases: {phases}")
    
    # Conditions
    t_start, t_stop, t_step = args.t_range
    conds = {
        v.N: 1, 
        v.P: 101325, 
        v.T: (t_start, t_stop, t_step), 
        v.X(el2): (0, 1, 0.02)
    }

    logging.info(f"Generating Phase Diagram for {el1}-{el2} at P=1atm, T={t_start}-{t_stop} K...")
    fig = plt.figure(figsize=(9,6))
    ax = fig.add_subplot(111)
    
    # Perform the binary plot computation
    binplot(dbf, comps, phases, conds, plot_kwargs={'ax': ax})
    
    # Formatting
    plt.title(f"{el1}-{el2} Phase Diagram")
    plt.xlabel(f"Mole Fraction {el2}")
    plt.ylabel("Temperature (K)")
    
    plt.savefig(args.output, dpi=300, bbox_inches='tight')

    # Save input configs for reproducibility
    from src.utils.config_utils import save_skill_inputs
    save_skill_inputs(args, args.output_dir)
    _params_path.parent.mkdir(parents=True, exist_ok=True)
    _params_path.write_text(_json.dumps(_config, indent=2, default=str))
    logging.info(f"Phase diagram successfully saved to {args.output}")

if __name__ == "__main__":
    main()
