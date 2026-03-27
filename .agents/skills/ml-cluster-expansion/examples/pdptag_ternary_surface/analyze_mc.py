from pymatgen.core import Structure
import numpy as np

try:
    s = Structure.from_file("mc_trajectory_final.cif")
    print(s.composition)
    
    # Let's get z coordinates to identify layers
    z_coords = [site.frac_coords[2] for site in s]
    unique_z = sorted(list(set(np.round(z_coords, 3))))
    print("Unique Z layers:", unique_z)
    
    for z in unique_z:
        layer_sites = [site for site in s if abs(site.frac_coords[2] - z) < 0.01]
        
        comps = {}
        for site in layer_sites:
            el = site.species_string
            comps[el] = comps.get(el, 0) + 1
            
        print(f"Layer Z={z:.3f} | Total atoms: {len(layer_sites)} | Composition: {comps}")
        
except Exception as e:
    print("Error:", e)
