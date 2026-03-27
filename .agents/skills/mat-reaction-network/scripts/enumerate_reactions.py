"""
Enumerate thermodynamically balanced reactions within a chemical system using various enumerator classes.

Usage:
    python enumerate_reactions.py --chemsys Y-Mn-O --enumerator-type basic_open --open-phases O2
    python enumerate_reactions.py --chemsys Y-Mn-O --enumerator-type minimize_grand_potential --open-elem O

Requirements:
    - Conda environment: base-agent
    - Required packages: mp-api, rxn-network, pymatgen
"""

import argparse
import logging
import warnings

from mp_api.client import MPRester
from pymatgen.core.periodic_table import Element

from rxn_network.entries.entry_set import GibbsEntrySet
from rxn_network.enumerators.basic import BasicEnumerator, BasicOpenEnumerator
from rxn_network.enumerators.minimize import MinimizeGibbsEnumerator, MinimizeGrandPotentialEnumerator


def main():
    parser = argparse.ArgumentParser(
        description="Enumerate chemical reactions using rxn_network enumerators."
    )
    parser.add_argument("--chemsys", required=True, help="Chemical system to query, e.g., 'Y-Mn-O'")
    parser.add_argument("--temperature", type=int, default=1000, help="Synthesis temperature in Kelvin (default: 1000)")
    parser.add_argument("--stability-tol", type=float, default=0.05, help="Energy above hull tolerance in eV/atom (default: 0.05)")
    parser.add_argument("--enumerator-type", choices=["basic", "basic_open", "minimize_gibbs", "minimize_grand_potential"], default="basic", help="Which enumerator to use.")
    
    # Optional constraints
    parser.add_argument("--precursors", nargs="+", help="Restrict enumeration to include these precursors.")
    parser.add_argument("--targets", nargs="+", help="Restrict enumeration to form these targets.")
    parser.add_argument("--exclusive-precursors", action="store_true", help="If --precursors is set, require ALL precursors in reactions.")
    parser.add_argument("--exclusive-targets", action="store_true", help="If --targets is set, require ALL targets in reactions.")
    
    # Open system params
    parser.add_argument("--open-phases", nargs="+", help="For basic_open: Phases to act as open reservoirs (e.g. 'O2')")
    parser.add_argument("--open-elem", help="For minimize_grand_potential: Element to be open (e.g. 'O')")
    parser.add_argument("--chempot", type=float, default=0.0, help="For minimize_grand_potential: Chemical potential of --open-elem (default: 0.0)")
    
    parser.add_argument("--limit", type=int, default=20, help="Max reactions to print (default: 20)")
    
    args = parser.parse_args()
    
    warnings.filterwarnings("ignore")
    logging.getLogger("rxn_network").setLevel(logging.ERROR)
    
    print(f"Chemical System: {args.chemsys}")
    print(f"Temperature: {args.temperature} K")
    print("Retrieving entries from Materials Project...")
    try:
        with MPRester() as mpr:
            entries = mpr.get_entries_in_chemsys(args.chemsys)
    except Exception as e:
        print(f"Failed to connect to MP API. Ensure MP_API_KEY is set. Error: {e}")
        return
        
    print(f"Retrieved {len(entries)} total entries.")
    
    entry_set = GibbsEntrySet.from_computed_entries(entries, temperature=args.temperature)
    filtered_entries = entry_set.filter_by_stability(args.stability_tol)
    print(f"Filtered to {len(filtered_entries)} stable entries (tol <= {args.stability_tol} eV/atom).\n")
    
    # Instantiate enumerator
    kwargs = {}
    if args.precursors:
        kwargs["precursors"] = args.precursors
        kwargs["exclusive_precursors"] = args.exclusive_precursors
    if args.targets:
        kwargs["targets"] = args.targets
        kwargs["exclusive_targets"] = args.exclusive_targets
        
    if args.enumerator_type == "basic":
        print("Using BasicEnumerator...")
        enumerator = BasicEnumerator(**kwargs)
    elif args.enumerator_type == "basic_open":
        if not args.open_phases:
            print("Error: --open-phases is required for basic_open.")
            return
        print(f"Using BasicOpenEnumerator with open_phases={args.open_phases}...")
        enumerator = BasicOpenEnumerator(open_phases=args.open_phases, **kwargs)
    elif args.enumerator_type == "minimize_gibbs":
        print("Using MinimizeGibbsEnumerator...")
        enumerator = MinimizeGibbsEnumerator(**kwargs)
    elif args.enumerator_type == "minimize_grand_potential":
        if not args.open_elem:
            print("Error: --open-elem is required for minimize_grand_potential.")
            return
        elem = Element(args.open_elem)
        print(f"Using MinimizeGrandPotentialEnumerator with open_elem={elem}, chempot={args.chempot}...")
        enumerator = MinimizeGrandPotentialEnumerator(open_elem=elem, mu=args.chempot, **kwargs)
    
    print("Enumerating reactions...")
    rxns = enumerator.enumerate(filtered_entries)
    
    print(f"\nEnumerated {len(rxns)} reactions using {args.enumerator_type}.")
    
    print(f"\nShowing top {min(len(rxns), args.limit)} reactions:")
    for idx, r in enumerate(rxns):
        if idx >= args.limit:
            break
        print(f"[{idx+1}] {r}")
        if hasattr(r, "energy_per_atom"):
            print(f"    dG = {round(r.energy_per_atom, 4)} eV/atom")

if __name__ == "__main__":
    main()
