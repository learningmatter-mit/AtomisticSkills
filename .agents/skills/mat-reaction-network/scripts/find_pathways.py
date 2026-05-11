"""
Find balanced, thermodynamically optimal synthesis pathways for a target material from specified precursors.

Usage:
    python find_pathways.py --target YMnO3 --precursors YCl3 Mn2O3 Li2CO3 --byproducts LiCl CO2 --temperature 923

Requirements:
    - Conda environment: base-agent
    - Required packages: mp-api, rxn-network, pymatgen
"""

import argparse
import logging
import warnings
from typing import List

from mp_api.client import MPRester
from pymatgen.core.composition import Composition

from rxn_network.costs.functions import Softplus
from rxn_network.entries.entry_set import GibbsEntrySet
from rxn_network.enumerators.basic import BasicEnumerator
from rxn_network.network.network import ReactionNetwork
from rxn_network.pathways.solver import PathwaySolver
from rxn_network.reactions.computed import ComputedReaction

def get_chemsys_from_formulas(formulas: List[str]) -> str:
    """Extract a chemical system string from a list of formulas."""
    elements = set()
    for f in formulas:
        comp = Composition(f)
        for el in comp.elements:
            elements.add(el.symbol)
    return "-".join(sorted(list(elements)))

def main():
    parser = argparse.ArgumentParser(
        description="Find optimal solid-state synthesis pathways using reaction-network."
    )
    parser.add_argument("--target", required=True, help="Target material formula (e.g., 'YMnO3')")
    parser.add_argument("--precursors", nargs="+", required=True, help="List of precursor formulas (e.g., 'YCl3' 'Mn2O3' 'Li2CO3')")
    parser.add_argument("--byproducts", nargs="*", default=[], help="List of byproduct formulas to allow in the net reaction (e.g., 'LiCl' 'CO2')")
    parser.add_argument("--temperature", type=int, default=1000, help="Synthesis temperature in Kelvin (default: 1000)")
    parser.add_argument("--k-paths", type=int, default=5, help="Number of shortest paths to find (default: 5)")
    parser.add_argument("--paths-to-solve", type=int, default=4, help="Number of balanced pathway combinations to solve (default: 4)")
    parser.add_argument("--stability-tol", type=float, default=0.0, help="Energy above hull tolerance in eV/atom (default: 0.0 for stable only)")
    parser.add_argument("--output", type=str, help="Optional text file to save the output logs to.")
    
    args = parser.parse_args()
    
    warnings.filterwarnings("ignore")
    logging.getLogger("rxn_network").setLevel(logging.ERROR)
    
    all_formulas = [args.target] + args.precursors + args.byproducts
    chemsys = get_chemsys_from_formulas(all_formulas)
    
    import json
    
    print(f"Target: {args.target}")
    print(f"Precursors: {args.precursors}")
    if args.byproducts:
        print(f"Byproducts: {args.byproducts}")
    print(f"Inferred Chemical System: {chemsys}")
    print(f"Temperature: {args.temperature} K\n")
    
    print("Retrieving entries from Materials Project...")
    try:
        with MPRester() as mpr:
            entries = mpr.get_entries_in_chemsys(chemsys)
    except Exception as e:
        print(f"Failed to connect to MP API. Ensure MP_API_KEY is set. Error: {e}")
        return
        
    print(f"Retrieved {len(entries)} total entries.")
    
    entry_set = GibbsEntrySet.from_computed_entries(entries, temperature=args.temperature)
    filtered_entries = entry_set.filter_by_stability(args.stability_tol)
    print(f"Filtered to {len(filtered_entries)} stable entries (tol <= {args.stability_tol} eV/atom).\n")
    
    print("Enumerating basic reactions (this may take a minute)...")
    be = BasicEnumerator()
    rxns = be.enumerate(filtered_entries)
    print(f"Enumerated {len(rxns)} balanced reactions.\n")
    
    print("Building Reaction Network...")
    cf = Softplus(temp=args.temperature)
    rn = ReactionNetwork(rxns, cf)
    rn.build()
    
    try:
        rn.set_precursors(args.precursors)
        rn.set_target(args.target)
    except KeyError as e:
        print(f"Error: Could not find precursor or target in the stable entries: {e}")
        print("Try increasing --stability-tol.")
        return
    
    pathfinding_targets = [args.target] + args.byproducts
    print(f"Finding top {args.k_paths} pathways to {pathfinding_targets}...")
    paths = rn.find_pathways(pathfinding_targets, k=args.k_paths)
    
    if not paths or not paths.paths:
        print("No pathways found. Try increasing --stability-tol or changing precursors.")
        return
        
    print(f"Found {len(paths.paths)} elementary pathway(s).\n")
    
    ps = PathwaySolver(paths, rn.entries, cf)
    
    product_entries = []
    for f in pathfinding_targets:
        entry = rn.entries.get_min_entry_by_formula(f)
        if not entry:
            print(f"Error: Could not find pure entry for {f}!")
            return
        product_entries.append(entry)
        
    precursor_entries = []
    for f in args.precursors:
        entry = rn.entries.get_min_entry_by_formula(f)
        if not entry:
            print(f"Error: Could not find pure entry for {f}!")
            return
        precursor_entries.append(entry)
        
    net_rxn = ComputedReaction.balance(precursor_entries, product_entries)
    print(f"Target Net Reaction:\n{net_rxn}\n")
    
    print(f"Solving {args.paths_to_solve} balanced pathway combinations...")
    try:
        balanced_paths = ps.solve(net_rxn, max_num_combos=args.paths_to_solve,
                                  intermediate_rxn_energy_cutoff=0.0,
                                  use_minimize_enumerator=False,
                                  filter_interdependent=True)
    except ValueError as e:
        logger.warning(f"PathwaySolver could not find balanced combinations: {e}")
        from rxn_network.pathways.pathway_set import PathwaySet
        balanced_paths = PathwaySet([])

    # The PathwaySolver explicitly filters out the net_reaction (1-step path) 
    # to find multi-step combinations. We must manually re-add the 1-step path 
    # if it exists in the elementary pathways.
    from rxn_network.pathways.balanced import BalancedPathway
    from rxn_network.pathways.pathway_set import PathwaySet
    direct_path = None
    for p in paths:
        if len(p.reactions) == 1:
            rxn = p.reactions[0]
            if {e.reduced_formula for e in rxn.reactants} == {e.reduced_formula for e in net_rxn.reactants} and \
               {e.reduced_formula for e in rxn.products} == {e.reduced_formula for e in net_rxn.products}:
                direct_path = BalancedPathway([rxn], [1.0], [p.costs[0]], balanced=True)
                break
    
    if direct_path:
        all_paths = [direct_path] + list(balanced_paths)
        balanced_paths = PathwaySet.from_paths(all_paths)
                              
    if not balanced_paths:
        print("No balanced pathways could be resolved for the net reaction.")
    else:
        print("=== Optimal Balanced Pathways ===\n")
        for idx, path in enumerate(balanced_paths):
            print(f"Pathway {idx+1}")
            print(path)
            print()
            
    # Save clean JSON output if requested
    if args.output:
        output_data = {
            "target": args.target,
            "precursors": args.precursors,
            "byproducts": args.byproducts,
            "temperature": args.temperature,
            "net_reaction": str(net_rxn),
            "pathways": []
        }
        
        for path in balanced_paths:
            path_dict = {
                "total_cost": getattr(path, "average_cost", getattr(path, "cost", None)),
                "steps": []
            }
            if hasattr(path, "reactions"):
                for rxn in path.reactions:
                    # Some reaction network implementations store dG in energy_per_atom, some directly in the string
                    path_dict["steps"].append({
                        "reaction_string": str(rxn),
                        "dG_eV_per_atom": getattr(rxn, "energy_per_atom", None)
                    })
            output_data["pathways"].append(path_dict)
            
        with open(args.output, "w") as f:
            json.dump(output_data, f, indent=4)
        print(f"Saved clean pathway data to {args.output}")

    # Force a hard exit to prevent Ray's atexit shutdown sequence from 
    # deadlocking on heavily loaded servers (e.g., when VASP is maxing out CPUs).
    import os
    os._exit(0)

    # Save input configs for reproducibility
    from src.utils.config_utils import save_skill_inputs
    save_skill_inputs(args, args.output)

if __name__ == "__main__":
    main()
