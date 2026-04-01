import json
from pymatgen.core import Structure, Lattice, Composition

def snap_xy(val):
    return round(val * 6) / 6.0

def parse_lat_in(file_path):
    with open(file_path, 'r') as f:
        lines = [l.strip() for l in f if l.strip()]
        
    a, b, c, alpha, beta, gamma = map(float, lines[0].split())
    lattice = Lattice.from_parameters(a, b, c, alpha, beta, gamma)
    
    species = []
    coords = []
    
    for line in lines[4:]:
        parts = line.split()
        if len(parts) >= 4:
            x, y, z = map(float, parts[:3])
            
            # Snap x and y to exact fractions
            x = snap_xy(x)
            y = snap_xy(y)
            
            coords.append([x, y, z])
            
            raw_spec = parts[3]
            elements = raw_spec.split(',')
            clean_elements = [el.split('_')[0] for el in elements]
            
            if len(clean_elements) == 1:
                comp = {clean_elements[0]: 1.0}
            else:
                frac = 1.0 / len(clean_elements)
                comp = {el: frac for el in clean_elements}
                
            species.append(comp)
            
    struct = Structure(lattice, species, coords, coords_are_cartesian=False)
    return struct

if __name__ == "__main__":
    s = parse_lat_in("lat.in")
    print(s)
    s.to(filename="primordial.cif")
    print("Saved to primordial.cif")
