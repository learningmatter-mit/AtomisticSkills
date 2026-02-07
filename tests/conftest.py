"""
Shared pytest fixtures and utilities for multi-environment testing.

This conftest.py provides:
- Project root path setup
- Environment detection
- Shared test fixtures (temporary structures, directories)
- Auto-skip logic for wrong environment tests
"""

import pytest
import os
import sys
import tempfile
import shutil
from pathlib import Path
from typing import Optional

# Add project root to Python path for src imports
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))



def detect_conda_env() -> str:
    """
    Detect the current conda environment.
    
    Returns:
        Environment name (e.g., 'mace-agent', 'base-agent')
    """
    conda_env = os.environ.get('CONDA_DEFAULT_ENV', 'unknown')
    return conda_env


@pytest.fixture(scope="session")
def current_env() -> str:
    """Fixture that returns the current conda environment name."""
    return detect_conda_env()


@pytest.fixture
def skip_if_wrong_env(request, current_env):
    """
    Auto-skip test if running in wrong environment.
    
    Usage:
        @pytest.mark.mace
        def test_mace_feature(skip_if_wrong_env):
            # This will auto-skip if not in mace-agent environment
            pass
    """
    markers = [m.name for m in request.node.iter_markers()]
    
    # Define environment requirements
    env_map = {
        'mace': 'mace-agent',
        'matgl': 'matgl-agent',
        'fairchem': 'fairchem-agent',
        'atomate2': 'atomate2-agent',
        'base': 'base-agent'
    }
    
    for marker, required_env in env_map.items():
        if marker in markers and current_env != required_env:
            pytest.skip(f"Test requires {required_env} environment, but running in {current_env}")


@pytest.fixture
def tmp_cif_file(tmp_path):
    """
    Create a temporary CIF file with a simple cubic structure.
    
    Returns:
        Path to temporary CIF file
    """
    from pymatgen.core import Structure, Lattice
    
    # Create simple cubic Si structure
    lattice = Lattice.cubic(5.43)
    structure = Structure(
        lattice,
        ["Si", "Si"],
        [[0, 0, 0], [0.25, 0.25, 0.25]]
    )
    
    cif_path = tmp_path / "test_structure.cif"
    structure.to(filename=str(cif_path), fmt="cif")
    
    return cif_path


@pytest.fixture
def sample_structure():
    """
    Create a sample Pymatgen Structure for testing.
    
    Returns:
        Pymatgen Structure object
    """
    from pymatgen.core import Structure, Lattice
    
    lattice = Lattice.cubic(5.43)
    structure = Structure(
        lattice,
        ["Si", "Si"],
        [[0, 0, 0], [0.25, 0.25, 0.25]]
    )
    return structure


@pytest.fixture
def sample_ase_atoms():
    """
    Create a sample ASE Atoms object for testing.
    
    Returns:
        ASE Atoms object
    """
    from ase import Atoms
    
    atoms = Atoms(
        'Si2',
        positions=[[0, 0, 0], [1.35, 1.35, 1.35]],
        cell=[5.43, 5.43, 5.43],
        pbc=True
    )
    return atoms


@pytest.fixture
def tmp_research_dir(tmp_path, monkeypatch):
    """
    Create a temporary research directory and mock the environment.
    
    This fixture:
    1. Creates a temporary directory structure
    2. Sets CURRENT_RESEARCH_DIR environment variable
    3. Cleans up after test
    """
    research_dir = tmp_path / "research" / "test_session"
    research_dir.mkdir(parents=True)
    
    # Mock the environment variable
    monkeypatch.setenv("CURRENT_RESEARCH_DIR", str(research_dir))
    
    yield research_dir
    
    # Cleanup is automatic with tmp_path


@pytest.fixture
def mock_mp_api_key(monkeypatch):
    """
    Mock Materials Project API key for tests that don't actually query MP.
    """
    monkeypatch.setenv("MP_API_KEY", "test_fake_api_key_12345")


# Helper function for test assertions
def assert_structure_equal(struct1, struct2, tol=1e-5):
    """
    Assert that two structures are equal within tolerance.
    
    Args:
        struct1: First structure (ASE Atoms or Pymatgen Structure)
        struct2: Second structure (ASE Atoms or Pymatgen Structure)
        tol: Numerical tolerance for comparison
    """
    from pymatgen.io.ase import AseAtomsAdaptor
    from pymatgen.core import Structure
    from ase import Atoms
    
    # Convert to Pymatgen if needed
    if isinstance(struct1, Atoms):
        struct1 = AseAtomsAdaptor.get_structure(struct1)
    if isinstance(struct2, Atoms):
        struct2 = AseAtomsAdaptor.get_structure(struct2)
    
    # Compare
    assert struct1.lattice.matrix.shape == struct2.lattice.matrix.shape
    assert len(struct1) == len(struct2)
    assert struct1.composition.reduced_formula == struct2.composition.reduced_formula
