#!/usr/bin/env python
"""Generate CO on Cu(111) initial and relaxed structures using pymatgen."""

from pymatgen.core import Structure, Molecule
from pymatgen.analysis.adsorption import AdsorbateSiteFinder
from pymatgen.core.surface import SlabGenerator
import numpy as np

# Load Cu bulk structure
cu_bulk = Structure.from_file('.agents/skills/mat-surface-adsorption/examples/CO_on_Cu111/Cu_bulk.cif')
print(f"Loaded Cu bulk with {len(cu_bulk)} atoms")

# Generate Cu(111) slab - increase size for better example
slabgen = SlabGenerator(cu_bulk, (1, 1, 1), min_slab_size=10, min_vacuum_size=15, center_slab=True)
slabs = slabgen.get_slabs()
slab = slabs[0]

# Make a 3x3 supercell for better visualization
slab.make_supercell([3, 3, 1])
print(f"Generated Cu(111) slab (3x3 supercell) with {len(slab)} atoms")

# Load CO molecule
co_mol = Molecule.from_file('.agents/skills/mat-surface-adsorption/examples/CO_on_Cu111/CO.xyz')
print(f"Loaded CO molecule: {co_mol.composition}")

# Find adsorption sites
asf = AdsorbateSiteFinder(slab)
ads_sites = asf.find_adsorption_sites()
print(f"Found adsorption sites: {list(ads_sites.keys())}")

# Get ontop site coordinate (first ontop site)
if 'ontop' in ads_sites and len(ads_sites['ontop']) > 0:
    # Get a central ontop site
    ontop_sites = ads_sites['ontop']
    # Find site closest to center
    center = np.array([0.5, 0.5, ontop_sites[0][2]])
    distances = [np.linalg.norm(np.array(site) - center) for site in ontop_sites]
    central_idx = np.argmin(distances)
    ads_coord = ontop_sites[central_idx]
    print(f"Selected ontop site at: {ads_coord}")
else:
    # Fallback: place at center of slab
    ads_coord = [0.5, 0.5, 0.7]
    print(f"Using default site at: {ads_coord}")

# Add CO at ontop site - initial structure
initial_struct = asf.add_adsorbate(co_mol, ads_coord, translate=True, reorient=True)
print(f"Created initial structure with {len(initial_struct)} atoms")

# Save initial structure using pymatgen's structure.to()
initial_struct.to(filename='.agents/skills/mat-surface-adsorption/examples/CO_on_Cu111/CO_Cu111_initial.cif')
print("✓ Saved CO_Cu111_initial.cif using pymatgen structure.to()")

# Create relaxed structure by moving CO slightly closer to surface
# In real calculation, this would be the result of geometry optimization
relaxed_struct = initial_struct.copy()

# Find C and O atoms (last 2 atoms added)
co_indices = [len(relaxed_struct) - 2, len(relaxed_struct) - 1]
print(f"CO atoms at indices: {co_indices}")

# Move CO molecule down (closer to surface) by moving in Cartesian coords
c_site = relaxed_struct[co_indices[0]]
o_site = relaxed_struct[co_indices[1]]

# Move both C and O down by 0.2 Å in z-direction (Cartesian)
c_cart = c_site.coords.copy()
o_cart = o_site.coords.copy()
c_cart[2] -= 0.2
o_cart[2] -= 0.2

# Update positions
relaxed_struct.replace(co_indices[0], c_site.specie, c_cart, coords_are_cartesian=True)
relaxed_struct.replace(co_indices[1], o_site.specie, o_cart, coords_are_cartesian=True)

# Save relaxed structure using pymatgen's structure.to()
relaxed_struct.to(filename='.agents/skills/mat-surface-adsorption/examples/CO_on_Cu111/CO_Cu111_relaxed.cif')
print("✓ Saved CO_Cu111_relaxed.cif using pymatgen structure.to()")

print("\n✅ Structure generation complete!")
print(f"  Initial: {len(initial_struct)} atoms ({len(initial_struct)-2} Cu + 2 CO)")
print(f"  Relaxed: {len(relaxed_struct)} atoms ({len(relaxed_struct)-2} Cu + 2 CO)")
print(f"  CO moved 0.2 Å closer to surface")
