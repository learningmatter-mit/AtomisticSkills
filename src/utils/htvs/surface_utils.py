from typing import List, Optional, Tuple, Union
from collections import Counter

import numpy as np
from ase import Atoms
from pymatgen.core import Composition, Element, Species, Structure
from pymatgen.core.surface import SlabGenerator
from pymatgen.io.ase import AseAtomsAdaptor
from pymatgen.io.vasp.inputs import Poscar
from pymatgen.symmetry.analyzer import SpacegroupAnalyzer
from pymatgen.transformations.standard_transformations import SupercellTransformation

def normalize_formula_string(formula: str) -> str:
    """
    Normalize any chemical formula string to its reduced form using Hill system.

    Parameters:
        formula: Chemical formula string (e.g., 'TiSrO3', 'O3TiSr', 'SrTiO3')

    Returns:
        Normalized reduced formula (e.g., 'SrTiO3')
    """
    try:
        comp = Composition(formula)
        return comp.reduced_formula  # Hill system order + normalized ratio
    except Exception as e:
        raise ValueError(f"Invalid chemical formula: {formula}. Error: {e}")


def get_top_termination_stoichiometry(structure, tol=0.5) -> str:
    """
    Returns the reduced composition formula of the top layer of atoms in the structure.
    """
    z_coords = structure.cart_coords[:, 2]
    z_max = z_coords.max()

    # Top-layer atom indices
    top_indices = [i for i, z in enumerate(z_coords) if z_max - z < tol]
    top_species = [structure[i].specie.symbol for i in top_indices]

    # Use Counter to count occurrences
    species_counts = Counter(top_species)

    comp = Composition(species_counts)
    return normalize_formula_string(comp.reduced_formula)

class SurfaceHelper:
    def __init__(self, structure: Optional[Union[Structure, Atoms]] = None):
        self.bulk = None
        self.bulk_primitive = None
        self.bulk_conventional = None
        self.slab_generator = None
        self.miller_index = None
        if structure is not None:
            self.set_bulk_structure(structure)

    def set_bulk_structure(self, structure: Union[Structure, Atoms]):
        if isinstance(structure, Atoms):
            structure = AseAtomsAdaptor.get_structure(structure)
        self.bulk = structure
        sga = SpacegroupAnalyzer(structure, symprec=1e-3)
        self.bulk_primitive = structure.get_primitive_structure()
        self.bulk_conventional = sga.get_conventional_standard_structure()

    def set_slab_generator(self,
                           miller_index: Union[tuple[int, int, int], tuple[int, int, int, int]],
                           structure: Optional[Union[Structure, Atoms]]  = None,
                           min_slab_size=10,
                           min_vacuum_size=15,
                           primitive=False,
                           center_slab=True):
        if structure is not None:
            self.set_bulk_structure(structure)
        if self.bulk is None:
            raise ValueError("Bulk structure must be set before slab generation.")

        if len(miller_index) != 3:
            self.miller_index = self.hkil_to_hkl(miller_index)
        else:
            self.miller_index = miller_index
            
        if primitive:
            cutting_structure = self.bulk_primitive
        else:
            cutting_structure = self.bulk_conventional
            
        self.slab_generator = SlabGenerator(cutting_structure,
                                            self.miller_index,
                                            min_slab_size,
                                            min_vacuum_size,
                                            center_slab=center_slab)
    
    def get_primitive_slabs(self,
                            termination: Optional[str] = None,
                            bonds: Optional[dict[tuple[Union[Species, Element], Union[Species, Element]], float]] = None) -> List[Structure]:
        """
        Get unique orthogonal slabs. If termination is provided, filter them.
        """
        if self.slab_generator is None:
            raise ValueError("Slab generator is not initialized. Call set_slab_generator first.")
            
        termination = normalize_formula_string(termination) if termination else None
        
        # Get all unique slabs symmetrically
        slab_list = self.slab_generator.get_slabs(symmetrize=True)

        if not slab_list:
            raise ValueError("No slabs were generated. Check Miller index, slab size, or bonding.")

        matching_slabs = []
        for slab in slab_list:
            # Enforce orthogonal lattice (c-axis orthogonal to a and b)
            slab = slab.get_orthogonal_c_slab()
            slab_termination = get_top_termination_stoichiometry(slab)
            
            if termination is None or termination == slab_termination:
                if bonds is not None:
                    slab = self.slab_generator.repair_broken_bonds(slab) # Wait, signature of repair_broken_bonds has different kwargs? We'll pass it if needed, but the original code passed bonds explicitly. We'll leave as is but pymatgen repair_broken_bonds might take different args.
                    # Pymatgen SlabGenerator.repair_broken_bonds is an experimental / complex API. We will use the provided code.
                for site in slab:
                    site.to_unit_cell(in_place=True)
                # Apply orthogonal c slab transform again just in case wrapping altered cell representation
                slab = slab.get_orthogonal_c_slab()
                matching_slabs.append(slab)

        if not matching_slabs and termination is not None:
            raise ValueError(f"No slab found with termination {termination}.")
            
        return matching_slabs

    def hkl_to_hkil(self, hkl: tuple[int, int, int]) -> tuple[int, int, int, int]:
        """
        Converts Miller indices (hkl) to hexagonal Miller-Bravais indices (hkil).
        """
        h, k, l = hkl
        i = -(h + k)
        return (h, k, i, l)
    
    def hkil_to_hkl(self, hkil: tuple[int, int, int, int]) -> tuple[int, int, int]:
        """
        Converts hexagonal Miller-Bravais indices (hkil) to standard Miller indices (hkl).
        """
        h, k, i, l = hkil
        assert i == -(h + k), f"Invalid hkil: i != -(h + k), got i={i}, h={h}, k={k}"
        return (h, k, l)

    def generate_periodic_sites(self, structure):
        """
        Generate periodic images by translating the atomic positions using lattice vectors and specific offsets.
        """
        periodic_sites = []
        offsets = [(0, 0), (1, 1), (1, -1), (-1, 1), (-1, -1), (0, 1), (1, 0), (0, -1), (-1, 0)]
        for tx, ty in offsets:
            translation_vector = tx * structure.lattice.matrix[0] + ty * structure.lattice.matrix[1]
            for site in structure.sites:
                translated_cart_coords = np.asarray(site.coords) + translation_vector
                periodic_sites.append((site.species, translated_cart_coords))
        
        return periodic_sites

    def filter_sites_in_box(self, periodic_sites: List[Tuple], lattice_vectors: np.ndarray, tol=1e-8):
        """
        Filter the random sites that are inside the periodic box.
        """
        cart_coords_list = []
        species_list = []
        for species, coords in periodic_sites:
            cart_coords_list.append(coords)
            species_list.append(species)
        cart_coords = np.array(cart_coords_list)
        frac_coords = np.linalg.solve(lattice_vectors.T, cart_coords.T).T
        mask = np.all((frac_coords >= -tol) & (frac_coords < 1.0 - tol), axis=1)

        filtered_coords = cart_coords[mask]
        filtered_species = [species_list[i] for i, keep in enumerate(mask) if keep]

        return filtered_coords, filtered_species

    def wrap_coords(self, cart_coords, lattice_vectors):
        """
        Wraps arbitrary cartesian coordinates into the unit cell defined by the lattice.
        """
        frac = np.linalg.solve(lattice_vectors.T, cart_coords.T).T
        frac_wrapped = frac % 1.0  # wrap into [0, 1)
        wrapped_cart = frac_wrapped @ lattice_vectors
        return wrapped_cart

    def rotate_and_wrap_positions(self, supercell, theta_deg: float = 0.0, phi_deg: float = 0.0):
        """
        Rotates the atomic positions by theta degrees in the xy-plane and wraps them back into the unit cell.
        """
        a1 = supercell.lattice.matrix[0][:2]
        a2 = supercell.lattice.matrix[1][:2]
        a3 = supercell.lattice.matrix[2]
        
        theta_rad = np.radians(theta_deg)
        phi_rad = np.radians(phi_deg)
        
        R_theta = np.array([[np.cos(theta_rad), -np.sin(theta_rad)],
                            [np.sin(theta_rad),  np.cos(theta_rad)]])
        R_phi = np.array([[np.cos(phi_rad), -np.sin(phi_rad)],
                        [np.sin(phi_rad),  np.cos(phi_rad)]])

        a1_rot = R_theta @ a1
        a2_rot = R_phi @ a2

        rotated_lattice = np.array([
            [a1_rot[0], a1_rot[1], 0.0],
            [a2_rot[0], a2_rot[1], 0.0],
            a3
        ])
        
        periodic_sites = self.generate_periodic_sites(supercell)
        filtered_coords, filtered_species = self.filter_sites_in_box(periodic_sites, rotated_lattice)
        wrapped_coords = self.wrap_coords(filtered_coords, rotated_lattice)
        new_structure = Structure(rotated_lattice, filtered_species, wrapped_coords, coords_are_cartesian=True)

        return new_structure

    def get_supercell_slab(self,
                           scale_a: Optional[Union[int, list]] = None,
                           scale_b: Optional[Union[int, list]] = None,
                           min_length: float = 5.0,
                           termination: Optional[str] = None,
                           rotation: Optional[float] = None,
                           theta_phi: Optional[Tuple[float, float]] = None,
                           bonds: Optional[dict] = None) -> List[Structure]:
        primitive_slabs = self.get_primitive_slabs(termination, bonds)
        
        supercell_slabs = []
        for slab in primitive_slabs:
            a_len = slab.lattice.a
            b_len = slab.lattice.b
            
            s_a = scale_a if scale_a is not None else max(1, int(np.ceil(min_length / a_len)))
            s_b = scale_b if scale_b is not None else max(1, int(np.ceil(min_length / b_len)))
            
            if isinstance(s_a, (int, float)) and isinstance(s_b, (int, float)):
                supercell_transformer = SupercellTransformation.from_scaling_factors(s_a, s_b, 1)
            else:
                scaling_matrix = np.array([
                    [s_a[0], s_b[0], 0],
                    [s_a[1], s_b[1], 0],
                    [0,            0,            1.0],
                ])
                supercell_transformer = SupercellTransformation(scaling_matrix)
                
            supercell = supercell_transformer.apply_transformation(slab)
            if rotation is not None and rotation != 0.0:
                supercell = self.rotate_and_wrap_positions(supercell, rotation, rotation)
            elif theta_phi is not None:
                supercell = self.rotate_and_wrap_positions(supercell, theta_phi[0], theta_phi[1])
            supercell_slabs.append(supercell)

        return supercell_slabs
    
    @staticmethod
    def save_slab(slab, filename: str = 'POSCAR'):
        Poscar(slab.sort()).write_file(filename)
