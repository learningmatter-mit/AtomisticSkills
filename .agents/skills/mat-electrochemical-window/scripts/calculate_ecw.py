"""
Calculates the intrinsic electrochemical window of a material using Materials Project data.

Usage:
    python calculate_ecw.py --mp-id mp-1183147 --mobile-ion Li

Requirements:
    - Conda environment: base-agent
    - Required packages: pymatgen, mp_api
"""

import argparse
import sys
from pymatgen.core import Element
from pymatgen.analysis.phase_diagram import PhaseDiagram, GrandPotentialPhaseDiagram
from mp_api.client import MPRester
from pymatgen.entries.computed_entries import ComputedEntry

def get_electrochemical_window(entry, pd, mobile_ion="Li") -> tuple:
    """
    Compute intrinsic electrochemical window against {mobile_ion}/{mobile_ion}+.
    
    Args:
        entry: ComputedEntry for the material
        pd: PhaseDiagram containing all competing phases
        mobile_ion: Symbol of the mobile ion (default: Li)
        
    Returns:
        Tuple of (V_red, V_ox) in Volts
    """
    el_ion = Element(mobile_ion)
    
    if el_ion not in pd.elements:
        return 0.0, 0.0
        
    all_entries = pd.entries
    if entry not in all_entries:
        all_entries = all_entries + [entry]
        
    mu_ref = pd.el_refs[el_ion].energy_per_atom
    critical_mus = pd.get_transition_chempots(el_ion)
    
    stable_vs = []
    
    for i in range(len(critical_mus) - 1):
        mu_mid = (critical_mus[i] + critical_mus[i+1]) / 2.0
        gpd = GrandPotentialPhaseDiagram(all_entries, {el_ion: mu_mid}, pd.elements)
        
        is_stable = False
        for stable_entry in gpd.stable_entries:
            if stable_entry.original_comp.reduced_formula == entry.composition.reduced_formula:
                is_stable = True
                break
                
        if is_stable:
            v1 = -(critical_mus[i] - mu_ref)
            v2 = -(critical_mus[i+1] - mu_ref)
            stable_vs.extend([v1, v2])
            
    if len(critical_mus) > 0:
        mu_high = critical_mus[0] + 0.5 
        mu_low = critical_mus[-1] - 0.5 
        
        for mu_mid in [mu_high, mu_low]:
            gpd = GrandPotentialPhaseDiagram(all_entries, {el_ion: mu_mid}, pd.elements)
            for stable_entry in gpd.stable_entries:
                if stable_entry.original_comp.reduced_formula == entry.composition.reduced_formula:
                    v = -(mu_mid - mu_ref)
                    limit_v = -(critical_mus[0]-mu_ref) if mu_mid == mu_high else -(critical_mus[-1]-mu_ref)
                    stable_vs.extend([limit_v, v])
            
    if not stable_vs:
        return 0.0, 0.0
        
    v_red = min(stable_vs)
    v_ox = max(stable_vs)
    
    v_red = max(0.0, min(10.0, v_red))
    v_ox = max(0.0, min(10.0, v_ox))
    
    return float(v_red), float(v_ox)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Calculate the electrochemical stability window for a Materials Project compound."
    )
    parser.add_argument("--mp-id", required=True, help="Materials Project ID to calculate ECW for (e.g., mp-1183147)")
    parser.add_argument("--mobile-ion", default="Li", help="Mobile ion (default: Li)")
    
    args = parser.parse_args()
    
    with MPRester() as mpr:
        # Get target entry
        docs = mpr.materials.search(material_ids=[args.mp_id])
        if not docs:
            print(f"Could not find material: {args.mp_id}")
            sys.exit(1)
            
        chemsys = docs[0].chemsys
            
        # Build PD
        entries = mpr.get_entries_in_chemsys(chemsys.split("-"))
        pd = PhaseDiagram(entries)
        
        # Find the entry that matches our target MP-ID exactly
        target_entry = None
        for e in entries:
            if getattr(e, "entry_id", "") == args.mp_id:
                target_entry = e
                break
                
        if not target_entry:
            print(f"Found elements for {args.mp_id} but lacking explicit thermodynamic entry. Looking for matching composition...")
            target_comp = docs[0].composition
            matching_entries = [e for e in entries if e.composition.reduced_formula == target_comp.reduced_formula]
            if matching_entries:
                target_entry = min(matching_entries, key=lambda e: e.energy_per_atom)
            else:
                print("Could not match entry to Phase Diagram.")
                sys.exit(1)
        
        # Force onto hull for metastables to get bounds
        hull_e = pd.get_hull_energy(target_entry.composition)
        if target_entry.energy > hull_e:
            target_entry = ComputedEntry(target_entry.composition, hull_e - 1e-5)
            print(f"Note: Material {args.mp_id} is theoretically metastable. Artificially forced onto the convex hull to calculate pseudo-stability ECW.")

        v_red, v_ox = get_electrochemical_window(target_entry, pd, args.mobile_ion)
        
        print(f"\nResults for {args.mp_id} ({target_entry.composition.reduced_formula}):")
        print(f"Reduction Potential (V_red): {v_red:.2f} V vs Li/Li+")
        print(f"Oxidation Potential (V_ox): {v_ox:.2f} V vs Li/Li+")
        print(f"Electrochemical Window: [{v_red:.2f}, {v_ox:.2f}] V")
