"""
Vendored Widom insertion implementation.

This package is vendored from the widom package by CuspAI (Apache 2.0)
to keep the chem-sorption skill self-contained. The public API is re-exported as:

- `WidomInsertionResults`
- `run_widom_insertion()`

Requirements:
    - Conda environment: fairchem-agent
    - Required packages: ase, numpy, pydantic, pymatgen
"""

# Copyright (c) 2025 CuspAI
# Vendored from the widom package (CuspAI) for chem-sorption skill.
# Modified by AtomisticSkills (docstring and attribution).

from .run import WidomInsertionResults, run_widom_insertion

__all__ = ["WidomInsertionResults", "run_widom_insertion"]
