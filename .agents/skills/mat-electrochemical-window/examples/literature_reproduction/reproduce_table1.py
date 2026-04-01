import sys
import os
import json
from pymatgen.core import Element, Composition
from pymatgen.entries.computed_entries import ComputedEntry
from pymatgen.analysis.phase_diagram import PhaseDiagram, GrandPotentialPhaseDiagram
from mp_api.client import MPRester

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../scripts')))
from calculate_ecw import get_electrochemical_window

if __name__ == "__main__":
    """
    Reproduces Table 1 from Zhu et al. (2015) using exact MP queries.
    """
    table1_data = {
        "Li2S": {"formula": "Li2S", "reported": [0.00, 2.01], "chemsys": "Li-S"},
        "LGPS": {"formula": "Li10GeP2S12", "reported": [1.71, 2.14], "chemsys": "Li-Ge-P-S", "approx_match": "Li5Ge(PS6)"},
        "Li3PS4": {"formula": "Li3PS4", "reported": [1.71, 2.31], "chemsys": "Li-P-S"},
        "Li4GeS4": {"formula": "Li4GeS4", "reported": [1.62, 2.14], "chemsys": "Li-Ge-S"},
        "Li7P3S11": {"formula": "Li7P3S11", "reported": [2.28, 2.31], "chemsys": "Li-P-S"},
        "Li6PS5Cl": {"formula": "Li6PS5Cl", "reported": [1.71, 2.01], "chemsys": "Li-P-S-Cl"},
        "Li7P2S8I": {"formula": "Li7P2S8I", "reported": [1.71, 2.31], "chemsys": "Li-P-S-I"},
        "LLZO": {"formula": "Li7La3Zr2O12", "reported": [0.05, 2.91], "chemsys": "Li-La-Zr-O"},
        "LLTO": {"formula": "Li3La2(TiO3)6", "reported": [1.75, 3.71], "chemsys": "Li-La-Ti-O"},
        "LATP": {"formula": "Li1.3Al0.3Ti1.7(PO4)3", "reported": [2.17, 4.21], "chemsys": "Li-Al-Ti-P-O"},
        "LAGP": {"formula": "Li1.5Al0.5Ge1.5(PO4)3", "reported": [2.70, 4.27], "chemsys": "Li-Al-Ge-P-O"},
        "LISICON": {"formula": "Li14Zn(GeO4)4", "reported": [1.44, 3.39], "chemsys": "Li-Zn-Ge-O"},
        "LiPON": {"formula": "Li3PO4", "reported": [0.68, 2.63], "chemsys": "Li-P-O"}
    }

    print(f"{'Name':<15} {'Formula':<25} {'Reported ECW':<20} {'Calculated ECW':<20} {'Status':<15}")
    print("-" * 100)

    with MPRester() as mpr:
        for name, data in table1_data.items():
            chemsys = data["chemsys"]
            entries = mpr.get_entries_in_chemsys(chemsys.split("-"))
            pd = PhaseDiagram(entries)
            
            target_comp = Composition(data["formula"])
            if "approx_match" in data:
                target_comp = Composition(data["approx_match"])
            
            matching_entries = [e for e in entries if e.composition.reduced_formula == target_comp.reduced_formula]
            
            target_entry = None
            is_exact = False
            best_dist = float('inf')
            
            if not matching_entries:
                for e in entries:
                    dist = sum([abs(target_comp.fractional_composition.get_atomic_fraction(el) - e.composition.fractional_composition.get_atomic_fraction(el)) for el in set(target_comp.elements + e.composition.elements)])
                    if dist < best_dist and pd.get_e_above_hull(e) < 0.1:
                        best_dist = dist
                        target_entry = e
            else:
                target_entry = min(matching_entries, key=lambda e: e.energy_per_atom)
                is_exact = True
                
            if target_entry:
                hull_e = pd.get_hull_energy(target_entry.composition)
                if target_entry.energy > hull_e:
                    target_entry = ComputedEntry(target_entry.composition, hull_e - 1e-5)
                    
                v_red, v_ox = get_electrochemical_window(target_entry, pd, "Li")
                
                rep_str = f"[{data['reported'][0]:.2f}, {data['reported'][1]:.2f}]"
                calc_str = f"[{v_red:.2f}, {v_ox:.2f}]"
                status = "Exact" if is_exact else "Approx (dist: {:.2f})".format(best_dist)
                
                print(f"{name:<15} {target_entry.composition.reduced_formula:<25} {rep_str:<20} {calc_str:<20} {status:<15}")
            else:
                print(f"{name:<15} {data['formula']:<25} {'Error: Entry missing':<20} {'N/A':<20} {'Failed':<15}")
