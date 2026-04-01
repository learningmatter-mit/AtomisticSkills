import os
import json
import numpy as np
from pymatgen.core import Structure, Lattice

def parse_atat_str(str_out_path):
    with open(str_out_path, 'r') as f:
        lines = [line.strip() for line in f if line.strip()]
        
    # First 3 lines are lattice vectors (u, v, w) multiplied by coordinate system?
    # wait, ATAT format: 
    # a b c alpha beta gamma  (or vector 1)
    # vector 2
    # vector 3
    # Actually lines 1-3 are the unrelaxed lattice vectors? 
    # Let's just read lines 1-3 as lattice
    u = [float(x) for x in lines[0].split()][:3]
    v = [float(x) for x in lines[1].split()][:3]
    w = [float(x) for x in lines[2].split()][:3]
    lattice_scale = [u, v, w] # Usually these are a,b,c vectors or length/angles
    
    # Actually lines 4-6 are lattice vectors
    vec1 = [float(x) for x in lines[3].split()][:3]
    vec2 = [float(x) for x in lines[4].split()][:3]
    vec3 = [float(x) for x in lines[5].split()][:3]
    
    # ATAT lattice is vec(i) * scale ?
    # Let's just use the direct pymatgen ATAT parser if we can, or manual.
    # Actually, in str_relax.out, the lattice vectors are the same format.
    # Let's parse str_relax.out for lattice and coords, and str.out for species.
    pass

def parse_dataset(data_dir):
    data = []
    
    lat_in_path = os.path.join(data_dir, "lat.in")
    
    # Find all subdirectories that are numbers
    dirs = [d for d in os.listdir(data_dir) if os.path.isdir(os.path.join(data_dir, d)) and d.isdigit()]
    
    for d in sorted(dirs, key=int):
        folder = os.path.join(data_dir, d)
        str_out = os.path.join(folder, "str.out")
        str_relax = os.path.join(folder, "str_relax.out")
        energy_file = os.path.join(folder, "energy")
        
        if not os.path.exists(str_out) or not os.path.exists(str_relax) or not os.path.exists(energy_file):
            continue
            
        with open(energy_file, 'r') as f:
            energy = float(f.read().strip())
            
        # Parse species from str.out
        with open(str_out, 'r') as f:
            str_lines = [l.strip() for l in f if l.strip()]
        
        species = []
        for line in str_lines[6:]:
            parts = line.split()
            if len(parts) >= 4:
                # E.g. Ag_T or Pd_T -> just take the first part before _
                spec = parts[3].split('_')[0]
                species.append(spec)
                
        # Parse relaxed coordinates and lattice from str_relax.out
        with open(str_relax, 'r') as f:
            rel_lines = [l.strip() for l in f if l.strip()]
            
        # ATAT lattice:
        # line 1: a b c alpha beta gamma
        # line 2-4: lattice vectors u v w
        # actual lattice is usually a*u, b*v, c*w if orthogonal, or a more complex metric tensor.
        # However, looking at str_relax.out:
        # 5.955 0 0
        # -2.9775 5.15718 0
        # 0 0 32.1555
        # 1 0 0
        # 0 1 0
        # 0 0 1
        # This means the first 3 lines are the actual Cartesian Cartesian lattice vectors!
        # The next 3 lines are just the identity matrix.
        lat_vecs = []
        for i in range(3):
            lat_vecs.append([float(x) for x in rel_lines[i].split()])
            
        lattice = Lattice(lat_vecs)
        
        coords = []
        for line in rel_lines[6:]:
            parts = [float(x) for x in line.split()[:3]]
            coords.append(parts)
            
        if len(coords) != len(species):
            print(f"Warning: size mismatch in {d} (coords: {len(coords)}, species: {len(species)})")
            continue
            
        struct = Structure(lattice, species, coords, coords_are_cartesian=False)
        
        data.append({
            "structure": struct.as_dict(),
            "energy": energy,
            "id": d
        })
        
    return data

if __name__ == "__main__":
    data_dir = "."
    dataset = parse_dataset(data_dir)
    print(f"Parsed {len(dataset)} structures.")
    
    with open("training_data.json", "w") as f:
        json.dump(dataset, f)
    print("Saved to training_data.json")
