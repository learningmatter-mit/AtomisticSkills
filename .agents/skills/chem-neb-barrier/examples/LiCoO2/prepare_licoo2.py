import sys
import os

# Add project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../../"))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from pymatgen.ext.matproj import MPRester
from pymatgen.core import Structure
from pymatgen.io.ase import AseAtomsAdaptor
from ase.io import write
from ase.optimize import FIRE
from src.utils.mlips.mace.mace_wrapper import MACEWrapper

def relax_structure(pmg_struct, model_name="MACE-OMAT-0-small", device="cuda"):
    """Relax structure using MACE to ensure valid starting point."""
    atoms = AseAtomsAdaptor.get_atoms(pmg_struct)
    
    # Init MACE via Wrapper
    wrapper = MACEWrapper(model_name=model_name, device=device)
    wrapper.load()
    calc = wrapper.create_calculator()
        
    atoms.calc = calc
    
    dyn = FIRE(atoms)
    dyn.run(fmax=0.02, steps=200)
    
    return atoms

def main():
    # 1. Get LiCoO2 Structure
    # Using mp-22526 (R-3m ground state)
    # Since we don't have API key in script, assuming we might need to search or use direct ID.
    # If MCP is unstable, we can use the mcp tool to fetch first. 
    # For this script, I'll rely on the mcp tool to fetch the CIF first, OR I will assume I can query if API key env is set.
    # Actually, simpler: Use `search_materials_project_by_id` tool from the agent workflow, 
    # but since I am writing a python script to run inside the environment, I should probably fetch it using pymatgen if env var is set.
    # Let's assume the user has MP_API_KEY set or we use the mcp tool before this script.
    
    # CHANGE: I will assume the structure is fetched via MCP and saved as 'LiCoO2.cif' in current dir.
    # This makes the script dependent on the previous step, which is safer for agents.
    
    if not os.path.exists("LiCoO2.cif"):
        print("Please fetch LiCoO2.cif (mp-22526) first.")
        return

    # Load primitive
    struct = Structure.from_file("LiCoO2.cif")
    
    # 2. Make Supercell
    # LiCoO2 hexagonal cell is small. 
    # a ~ 2.8, c ~ 14. 
    # 4x4x1 supercell ensures > 10 A separation in basal plane.
    struct.make_supercell([4, 4, 1])
    
    # 3. Create Vacancy
    # Find a Li site. Li is typically 3a or 3b site.
    # Let's pick the first Li index.
    li_indices = [i for i, site in enumerate(struct) if site.species_string == "Li"]
    if not li_indices:
        raise ValueError("No Li atoms found!")
    
    # Vacancy at site A
    vac_index = li_indices[0]
    struct_vac_A = struct.copy()
    struct_vac_A.remove_sites([vac_index]) # Site 0 is now empty.
    
    # 4. Create Hopping Path
    # We need a neighbor Li to jump into vac_index.
    # In the original full supercell, find NN Li to the atom we just removed.
    # The atom at vac_index is gone in struct_vac_A, so we use original struct to find neighbors.
    
    vac_site = struct[vac_index]
    # Get neighbors of the vacancy (which was a Li)
    neighbors = struct.get_neighbors(vac_site, r=3.5) # Li-Li distance ~ 2.8A
    
    # Filter for Li neighbors
    li_neighbors = [n for n in neighbors if n.species_string == "Li"]
    
    if not li_neighbors:
        raise ValueError("No Li neighbors found for migration!")
        
    start_li_site = li_neighbors[0]
    
    # Now we construct the End state.
    # Start State (struct_vac_A): Vacancy at vac_site. Neighbor Li is at start_li_site.
    # End State: Neighbor Li moves to vac_site. Vacancy is now at start_li_site.
    
    # Actually, it's easier to think:
    # State 1: Atom X is at Pos 1. Atom Y is at Pos 2. Vacancy at Pos 3.
    # ... straightforward vacancy hopping:
    # 
    # Let's define:
    # Structure 1: Remove Atom 0. (Vacancy at 0)
    # Structure 2: Remove a Neighbor of 0. (Vacancy at Neighbor) AND Ensure Atom that WAS at Neighbor is now at 0.
    # Wait, simpler:
    # Structure 1 = All atoms except Li_0.
    # Structure 2 = Take Structure 1, find a Li (Li_neighbor), move it to position of Li_0.
    
    # Re-finding neighbor in struct_vac_A might be tricky due to index shifts.
    # Let's use the fractional coords.
    
    # Finder neighbor in original struct
    neighbor = li_neighbors[0] # This is a PeriodicSite
    
    # Find the index of this neighbor in struct_vac_A
    # Since we removed one site (index < neighbor index?), indices shift.
    # Safer to match by close coords.
    
    neighbor_in_vac_A_index = -1
    for i, site in enumerate(struct_vac_A):
        if site.distance(neighbor) < 0.1 and site.species_string == "Li":
            neighbor_in_vac_A_index = i
            break
            
    if neighbor_in_vac_A_index == -1:
        raise ValueError("Could not find neighbor in vacancy structure.")
        
    # Create End Structure
    struct_vac_B = struct_vac_A.copy()
    # Move the neighbor atom to the vacancy position
    # vac_site.frac_coords is where the vacancy is (target pos)
    struct_vac_B.replace(neighbor_in_vac_A_index, "Li", vac_site.frac_coords)
    
    # 5. Relax Endpoints
    print("Relaxing start structure...")
    atoms_start = relax_structure(struct_vac_A)
    print("Relaxing end structure...")
    atoms_end = relax_structure(struct_vac_B)
    
    os.makedirs("neb_input", exist_ok=True)
    write("neb_input/start.cif", atoms_start)
    write("neb_input/end.cif", atoms_end)
    
    print("NEB inputs prepared in neb_input/")

if __name__ == "__main__":
    main()
