import pytest
import numpy as np
import os
import shutil
from pymatgen.core import Structure, Lattice
from src.utils.disordered_material.smol_utils import SmolWrapper
from src.utils.disordered_material.enumeration_utils import enumerate_matrices

@pytest.fixture
def smol_wrapper():
    return SmolWrapper()

def test_ternary_alloy_enumeration(smol_wrapper):
    """Test generating structures for Co-Ni-Cr ternary alloy."""
    # Simple cubic FCC-like cell for Co-Ni-Cr
    lattice = Lattice.from_parameters(3.5, 3.5, 3.5, 90, 90, 90)
    # Disordered site with Co, Ni, Cr
    struct = Structure(lattice, [{"Co": 0.33, "Ni": 0.33, "Cr": 0.34}], [[0, 0, 0]])
    
    cutoffs = {2: 5.0}
    num_structures = 20 # Small number for fast test
    
    structs = smol_wrapper.sample_ordered_structures(
        primordial_structure=struct,
        cutoffs=cutoffs,
        num_structures=num_structures,
        target_num_sites=16 # small target for test
    )
    
    assert len(structs) > 0
    assert len(structs) <= num_structures
    
    # Check that structures have correct elements
    elements = set()
    for s in structs:
        for site in s:
            elements.add(site.specie.symbol)
    
    assert "Co" in elements
    assert "Ni" in elements
    assert "Cr" in elements
    print(f"Generated {len(structs)} structures for ternary alloy.")

def test_binary_sublattice_enumeration(smol_wrapper):
    """Test generating structures for (Li-Na)(Cl-Br) two-sublattice system."""
    # NaCl-type structure
    lattice = Lattice.from_parameters(5.6, 5.6, 5.6, 90, 90, 90)
    # Li/Na on (0,0,0) and Cl/Br on (0.5,0.5,0.5)
    struct = Structure(lattice, 
                       [{"Li": 0.5, "Na": 0.5}, {"Cl": 0.5, "Br": 0.5}], 
                       [[0, 0, 0], [0.5, 0.5, 0.5]])
    
    cutoffs = {2: 4.0}
    num_structures = 20
    
    structs = smol_wrapper.sample_ordered_structures(
        primordial_structure=struct,
        cutoffs=cutoffs,
        num_structures=num_structures,
        target_num_sites=16
    )
    
    assert len(structs) > 0
    
    # Check elements
    elements = set()
    for s in structs:
        for site in s:
            elements.add(site.specie.symbol)
    
    assert all(el in elements for el in ["Li", "Na", "Cl", "Br"])
    print(f"Generated {len(structs)} structures for two-sublattice system.")

def test_large_enumeration(smol_wrapper):
    """Verify that we can generate 100 structures (scaling down for test speed, but verifying logic)."""
    # Simple Li-Ag system
    lattice = Lattice.cubic(3.5)
    struct = Structure(lattice, [{"Li": 0.5, "Ag": 0.5}], [[0, 0, 0]])
    
    cutoffs = {2: 5.0}
    num_structures = 100
    
    structs = smol_wrapper.sample_ordered_structures(
        primordial_structure=struct,
        cutoffs=cutoffs,
        num_structures=num_structures,
        target_num_sites=32
    )
    
    assert len(structs) > 50 # Ensure we get a decent number
    print(f"Verified large scale generation: {len(structs)} structures.")

if __name__ == "__main__":
    # For manual running
    wrapper = SmolWrapper()
    print("Testing ternary alloy...")
    test_ternary_alloy_enumeration(wrapper)
    print("Testing binary sublattice...")
    test_binary_sublattice_enumeration(wrapper)
    print("Testing large enumeration...")
    test_large_enumeration(wrapper)
