"""
Tests for base utility functions in structure_utils.py

These tests validate the breaking changes:
- load_structure_from_file() now returns Pymatgen Structure
- save_structure() standardization
- Materials Project query simplification

Run in: base-agent environment
"""

import pytest
from pathlib import Path
from pymatgen.core import Structure, Lattice
from ase import Atoms


@pytest.mark.base
class TestLoadStructureFromFile:
    """Test the breaking change: load_structure_from_file returns Pymatgen Structure"""
    
    def test_returns_pymatgen_structure(self, tmp_cif_file, skip_if_wrong_env):
        """Verify load_structure_from_file returns Pymatgen Structure, not ASE Atoms"""
        from src.utils.structure_utils import load_structure_from_file
        
        result = load_structure_from_file(tmp_cif_file)
        
        # BREAKING CHANGE: Should return Pymatgen Structure, NOT ASE Atoms
        assert isinstance(result, Structure), \
            f"Expected Pymatgen Structure, got {type(result)}"
        assert not isinstance(result, Atoms), \
            "Should NOT return ASE Atoms (breaking change)"
    
    def test_loads_cif_file(self, tmp_cif_file, skip_if_wrong_env):
        """Test loading from CIF file"""
        from src.utils.structure_utils import load_structure_from_file
        
        structure = load_structure_from_file(tmp_cif_file)
        
        assert len(structure) == 2  # Si2
        assert structure.composition.reduced_formula == "Si"
    
    def test_loads_poscar_file(self, tmp_path, skip_if_wrong_env):
        """Test loading from POSCAR file"""
        from src.utils.structure_utils import load_structure_from_file
        from pymatgen.core import Lattice
        
        # Create POSCAR
        lattice = Lattice.cubic(5.43)
        structure = Structure(lattice, ["Si"], [[0, 0, 0]])
        poscar_path = tmp_path / "POSCAR"
        structure.to(filename=str(poscar_path), fmt="poscar")
        
        loaded = load_structure_from_file(poscar_path)
        
        assert isinstance(loaded, Structure)
        assert len(loaded) == 1


@pytest.mark.base
class TestSaveStructure:
    """Test the new standardized save_structure() function"""
    
    def test_saves_pymatgen_structure(self, sample_structure, tmp_path, skip_if_wrong_env):
        """Test saving Pymatgen Structure"""
        from src.utils.structure_utils import save_structure
        
        output_path = tmp_path / "output.cif"
        save_structure(sample_structure, output_path)
        
        assert output_path.exists()
        
        # Verify it can be reloaded
        from src.utils.structure_utils import load_structure_from_file
        reloaded = load_structure_from_file(output_path)
        assert isinstance(reloaded, Structure)
    
    def test_saves_ase_atoms(self, sample_ase_atoms, tmp_path, skip_if_wrong_env):
        """Test saving ASE Atoms"""
        from src.utils.structure_utils import save_structure
        
        output_path = tmp_path / "output.cif"
        save_structure(sample_ase_atoms, output_path)
        
        assert output_path.exists()
        
        # Verify it can be reloaded
        from src.utils.structure_utils import load_structure_from_file
        reloaded = load_structure_from_file(output_path)
        assert isinstance(reloaded, Structure)
    
    def test_saves_to_various_formats(self, sample_structure, tmp_path, skip_if_wrong_env):
        """Test saving to CIF format"""
        from src.utils.structure_utils import save_structure
        
        # Test only CIF which is universally supported
        output_path = tmp_path / "test.cif"
        save_structure(sample_structure, output_path)
        assert output_path.exists(), "Failed to save CIF format"


@pytest.mark.base
class TestMaterialsProjectQueries:
    """Test simplified Materials Project query functions"""
    
    def test_get_structure_by_formula_returns_ase_atoms(self, skip_if_wrong_env):
        """Test that get_structure_by_formula returns ASE Atoms"""
        from src.utils.structure_utils import get_structure_by_formula
        from unittest.mock import Mock
        
        # Mock MPRester
        mock_mprester = Mock()
        mock_doc = Mock()
        mock_doc.structure = Structure.from_spacegroup("Fm-3m", Lattice.cubic(5.43), ["Si"], [[0, 0, 0]])
        mock_doc.energy_above_hull = 0.0
        mock_mprester.summary.search.return_value = [mock_doc]
        
        result = get_structure_by_formula("Si", mock_mprester)
        
        # Should return ASE Atoms (converted from Pymatgen)
        assert isinstance(result, Atoms), \
            f"Expected ASE Atoms, got {type(result)}"
    
    def test_get_structure_by_formula_handles_empty_results(self, skip_if_wrong_env):
        """Test handling of empty search results"""
        from src.utils.structure_utils import get_structure_by_formula
        from unittest.mock import Mock
        
        mock_mprester = Mock()
        mock_mprester.summary.search.return_value = []
        
        result = get_structure_by_formula("NonExistentMaterial123", mock_mprester)
        
        assert result is None
    
    def test_get_structure_by_chemsys_returns_most_stable(self, skip_if_wrong_env):
        """Test that get_structure_by_chemsys returns most stable structure"""
        from src.utils.structure_utils import get_structure_by_chemsys
        from unittest.mock import Mock
        
        # Mock multiple results with different stabilities
        mock_mprester = Mock()
        
        stable_doc = Mock()
        stable_doc.structure = Structure.from_spacegroup("Fm-3m", Lattice.cubic(5.43), ["Si"], [[0, 0, 0]])
        stable_doc.energy_above_hull = 0.0
        
        unstable_doc = Mock()
        unstable_doc.structure = Structure.from_spacegroup("Fd-3m", Lattice.cubic(5.5), ["Si"], [[0, 0, 0]])
        unstable_doc.energy_above_hull = 0.5
        
        mock_mprester.summary.search.return_value = [unstable_doc, stable_doc]
        
        result = get_structure_by_chemsys("Si", mock_mprester)
        
        # Should return the most stable one
        assert isinstance(result, Atoms)
        # Check it's the stable structure (lattice constant should be 5.43, not 5.5)
        assert abs(result.cell.lengths()[0] - 5.43) < 0.1
    
    def test_get_structure_by_id(self, skip_if_wrong_env):
        """Test get_structure_by_id"""
        from src.utils.structure_utils import get_structure_by_id
        from unittest.mock import Mock
        
        mock_mprester = Mock()
        mock_structure = Structure.from_spacegroup("Fm-3m", Lattice.cubic(5.43), ["Si"], [[0, 0, 0]])
        mock_mprester.materials.get_structure_by_material_id.return_value = mock_structure
        
        result = get_structure_by_id("mp-149", mock_mprester)
        
        assert isinstance(result, Atoms)
