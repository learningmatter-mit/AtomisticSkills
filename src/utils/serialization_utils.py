import numpy as np
from pathlib import Path

import math

def format_temperature_key(temperature: float) -> str:
    """Format temperature as a string key (e.g. 298.15K or 300K)."""
    rounded = round(temperature)
    if abs(temperature - rounded) < 1e-6:
        return f"{int(rounded)}K"
    return f"{temperature:g}K"

def finite_or_none(x: any) -> float | None:
    """Convert value to float, returning None if not finite or on error."""
    if x is None:
        return None
    try:
        val = float(x)
        return val if math.isfinite(val) else None
    except (ValueError, TypeError):
        return None

def recursive_tolist(obj):
    """
    Recursively convert objects to list/dict structures compatible with JSON.
    Handles numpy arrays, Path objects, and objects with as_dict() method.
    """
    if isinstance(obj, np.ndarray):
        return recursive_tolist(obj.tolist())
    elif isinstance(obj, (Path,)):
        return str(obj)
    elif isinstance(obj, dict):
        return {k: recursive_tolist(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [recursive_tolist(x) for x in obj]
    elif hasattr(obj, "item"):  # numpy scalars
        val = obj.item()
        if isinstance(val, float):
             if np.isnan(val): return None
             if np.isinf(val): return None
        return val
    elif isinstance(obj, float):
        if np.isnan(obj): return None
        if np.isinf(obj): return None
        return obj
    elif hasattr(obj, "as_dict"): # pymatgen or others
        return recursive_tolist(obj.as_dict())
    elif hasattr(obj, "get_atomic_numbers"): # ASE Atoms
        from pymatgen.io.ase import AseAtomsAdaptor
        return recursive_tolist(AseAtomsAdaptor.get_structure(obj).as_dict())
    elif hasattr(obj, "potential_energies") and hasattr(obj, "total_energies"): # TrajectoryObserver
        return {
            "potential_energies": recursive_tolist(obj.potential_energies),
            "kinetic_energies": recursive_tolist(obj.kinetic_energies),
            "total_energies": recursive_tolist(obj.total_energies),
            "forces": recursive_tolist(obj.forces),
            "stresses": recursive_tolist(obj.stresses),
            "atom_positions": recursive_tolist(obj.atom_positions),
            "cells": recursive_tolist(obj.cells),
        }
    else:
        return obj
