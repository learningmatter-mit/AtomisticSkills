import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

try:
    from src.utils.dft.vasp_writer import PYMATGEN_AVAILABLE
    print(f"PYMATGEN_AVAILABLE: {PYMATGEN_AVAILABLE}")
    if PYMATGEN_AVAILABLE:
        import pymatgen
        print(f"pymatgen version: {pymatgen.__version__}")
except ImportError as e:
    print(f"ImportError: {e}")
except Exception as e:
    print(f"Error: {e}")
