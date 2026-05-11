
import os
from typing import Any, Union, Optional, List
from pathlib import Path

def normalize_charge_spin(atoms: Any, task_name: str = None) -> None:
    """Write charge/spin into atoms.info only for the omol head.
    
    For odac/omat/omc/oc20, leave atoms.info untouched so fairchem's
    AtomicData.from_ase falls back to spin=0 (the trained default for
    those heads). Forcing spin=1 on non-omol systems perturbs the
    shared-backbone csd_embedding and biases energies.
    """
    if task_name != "omol":
        return

    info = atoms.info if isinstance(atoms.info, dict) else {}
    if atoms.info is not info:
        atoms.info = info
    try:
        charge = int(info.get("charge", info.get("chg", 0)))
    except Exception:
        charge = 0
    try:
        spin_mult = int(
            info.get("spin_multiplicity", info.get("multiplicity", info.get("spin", 1)))
        )
    except Exception:
        spin_mult = 1
    atoms.info["charge"] = charge
    atoms.info["spin_multiplicity"] = spin_mult
    atoms.info["spin"] = spin_mult

def save_structure(structure: Any, filename: Union[str, Path]):
    """
    Standardized function to save an atomic structure to a file.
    Handles ASE Atoms and Pymatgen Structure objects.
    
    Args:
        structure: The structure object to save (ASE Atoms or Pymatgen Structure).
        filename: Path to the output file (e.g., "relaxed_structure.cif").
    """
    from ase import Atoms
    from pymatgen.core import Structure
    
    filename_str = str(filename)
    
    if isinstance(structure, Structure):
        # Pymatgen Structure
        structure.to(filename=filename_str)
    elif isinstance(structure, Atoms):
        # ASE Atoms
        structure.write(filename_str)
    elif hasattr(structure, "to"):
        # Generic 'to' method (usually Pymatgen-like)
        structure.to(filename=filename_str)
    elif hasattr(structure, "write"):
        # Generic 'write' method (usually ASE-like)
        structure.write(filename_str)
    elif isinstance(structure, list) and len(structure) > 0:
        # Batch of atoms (e.g. trajectory)
        from ase.io import write
        write(filename_str, structure)
    else:
        # Fallback using Adaptor
        from pymatgen.io.ase import AseAtomsAdaptor
        try:
            # Try converting to ASE Atoms first for broad format support
            atoms = AseAtomsAdaptor.get_atoms(structure)
            atoms.write(filename_str)
        except Exception:
            # Last ditch effort: Pymatgen
            pmg_struct = AseAtomsAdaptor.get_structure(structure)
            pmg_struct.to(filename=filename_str)

def load_structure_from_file(filename: Union[str, Path]):
    """
    Load a structure from a file and return it as a Pymatgen Structure.
    """
    from pymatgen.core import Structure
    return Structure.from_file(str(filename))

def get_structure_by_formula(formula: str, mprester: Any, return_all: bool = False) -> Any:
    """
    Search for structures by formula in Materials Project.
    Returns ASE Atoms object (most stable) or list of ASE Atoms (if return_all=True).
    """
    docs = mprester.summary.search(formula=formula, fields=["structure", "energy_above_hull", "material_id", "theoretical", "database_IDs"])
    if not docs:
        return [] if return_all else None
        
    from pymatgen.io.ase import AseAtomsAdaptor
    
    if return_all:
        atoms_list = []
        for doc in docs:
            atoms = AseAtomsAdaptor.get_atoms(doc.structure)
            atoms.info['material_id'] = doc.material_id
            atoms.info['formula'] = formula
            atoms.info['energy_above_hull'] = doc.energy_above_hull
            atoms.info['theoretical'] = doc.theoretical
            atoms_list.append(atoms)
        return atoms_list
    else:
        # Sort by stability
        stable_doc = min(docs, key=lambda x: x.energy_above_hull)
        atoms = AseAtomsAdaptor.get_atoms(stable_doc.structure)
        atoms.info['material_id'] = stable_doc.material_id
        atoms.info['theoretical'] = stable_doc.theoretical
        return atoms

def get_structure_by_chemsys(chemsys: str, mprester: Any) -> List[Any]:
    """
    Search for all stable structures on the convex hull by chemical system in Materials Project.
    Returns list of ASE Atoms objects for structures with energy_above_hull = 0.
    
    Args:
        chemsys: Chemical system (e.g., "Li-O")
        mprester: MPRester instance
        
    Returns:
        List of ASE Atoms objects for all structures on the hull (E_hull < 1e-6 eV/atom)
    """
    docs = mprester.summary.search(
        chemsys=chemsys, 
        fields=["structure", "energy_above_hull", "material_id", "formula_pretty"]
    )
    if not docs:
        return []
    
    # Filter for structures on the hull (E_hull = 0, using tiny tolerance for floating point)
    hull_docs = [doc for doc in docs if doc.energy_above_hull < 1e-6]
    
    if not hull_docs:
        return []
    
    # Convert all hull structures to ASE Atoms
    from pymatgen.io.ase import AseAtomsAdaptor
    atoms_list = []
    for doc in hull_docs:
        atoms = AseAtomsAdaptor.get_atoms(doc.structure)
        # Store metadata as info dict
        atoms.info['material_id'] = doc.material_id
        atoms.info['formula'] = doc.formula_pretty
        atoms.info['energy_above_hull'] = doc.energy_above_hull
        atoms_list.append(atoms)
    
    return atoms_list

def get_structure_by_id(material_id: str, mprester: Any) -> Any:
    """
    Search for a structure by Material ID in Materials Project.
    Returns ASE Atoms object.
    """
    doc = mprester.materials.get_structure_by_material_id(material_id)
    if not doc:
        return None
    from pymatgen.io.ase import AseAtomsAdaptor
    return AseAtomsAdaptor.get_atoms(doc)

def load_structures(inputs: Union[str, Path, dict, List, Any]) -> List[Any]:
    """
    Universal function to load structures into a list of Pymatgen Structures.
    
    Args:
        inputs: Can be:
            - Path string or Path object (file or directory)
            - Structure/Atoms object
            - Dict representation
            - List of any of the above
            
    Returns:
        List[Structure]: List of Pymatgen Structure objects.
    """
    from pymatgen.core import Structure
    from ase import Atoms
    from pymatgen.io.ase import AseAtomsAdaptor
    import glob
    
    structures = []
    
    # Handle single items by wrapping in list, unless it's a directory path
    if isinstance(inputs, (str, Path)):
        path = Path(inputs)
        if path.is_dir():
            # Directory: expand to list of files
            exts = ["cif", "CIF", "poscar", "POSCAR", "vasp", "xyz", "json"]
            files = []
            for ext in exts:
                files.extend(glob.glob(str(path / f"**/*.{ext}"), recursive=True))
            files = sorted(list(set(files)))
            # Recursively call with list of files
            return load_structures(files)
        elif "*" in str(inputs):
            # Glob string
            files = sorted(glob.glob(str(inputs)))
            return load_structures(files)
        else:
            # Single file
            raw_items = [inputs]
    elif isinstance(inputs, list):
        raw_items = inputs
    else:
        raw_items = [inputs]
        
    for item in raw_items:
        try:
            struct = None
            if isinstance(item, (str, Path)):
                # Load from file
                struct = Structure.from_file(str(item))
            elif isinstance(item, dict):
                # Load from dict
                struct = Structure.from_dict(item)
            elif isinstance(item, Structure):
                # Already Structure
                struct = item
            elif isinstance(item, Atoms):
                # ASE Atoms
                struct = AseAtomsAdaptor.get_structure(item)
            else:
                # Try generic conversion or fail gracefully
                if hasattr(item, "as_dict"):
                    struct = Structure.from_dict(item.as_dict())
                else:
                    print(f"Warning: Could not convert item of type {type(item)} to Structure.")
            
            if struct:
                structures.append(struct)
        except Exception as e:
            print(f"Error loading structure from {item}: {e}")
            
    return structures

def expand_structure(structure: Any, target_atoms: int = 50, max_atoms: Optional[int] = None, min_length: Optional[float] = None) -> Any:
    """
    Expand a structure to reach a target number of atoms with a close-to-cubic supercell.
    
    Args:
        structure: Structure to expand (ASE Atoms or pymatgen Structure)
        target_atoms: Target total number of atoms (default: 50)
        max_atoms: Optional maximum number of atoms limit.
        min_length: Optional minimum length for each lattice vector.
        
    Returns:
        Expanded structure in the same format as input.
    """
    from ase import Atoms
    import numpy as np
    from pymatgen.io.ase import AseAtomsAdaptor
    import logging
    
    logger = logging.getLogger(__name__)
    
    # Convert to ASE Atoms for uniform handling of expansion logic
    is_pmg = False
    if hasattr(structure, "as_dict") and hasattr(structure, "lattice"):
        is_pmg = True
        atoms = AseAtomsAdaptor.get_atoms(structure)
    else:
        atoms = structure
        
    current_atoms = len(atoms)
    
    # Safety Check
    if max_atoms and current_atoms > max_atoms:
        logger.warning(f"Structure already has {current_atoms} atoms, exceeding limit {max_atoms}. No expansion.")
        return structure
        
    if current_atoms >= target_atoms * 0.9:
        if min_length is None:
            logger.info(f"Structure already has {current_atoms} atoms, sufficient size. No expansion.")
            return structure
        else:
            # Check if current lengths meet min_length
            cell_lengths = atoms.cell.lengths()
            if all(l >= min_length for l in cell_lengths):
                logger.info(f"Structure has {current_atoms} atoms and meets min_length. No expansion.")
                return structure

    # Calculate expansion factor needed
    expansion_factor = (target_atoms / current_atoms) ** (1.0 / 3.0)
    
    best_expansion = None
    best_score = float('inf')
    
    # Search space: try expansion matrices from 1x1x1 to 6x6x6
    max_search = int(expansion_factor * 2) + 1
    max_search = min(max_search, 8)
    
    for nx in range(1, max_search + 1):
        for ny in range(1, max_search + 1):
            for nz in range(1, max_search + 1):
                num_atoms = current_atoms * nx * ny * nz
                
                # Check bounds
                if num_atoms < target_atoms * 0.5:
                    continue
                if max_atoms and num_atoms > max_atoms:
                    continue
                
                # Score: 0.5 * distance from target + 0.5 * non-cubicness
                target_dist = abs(num_atoms - target_atoms) / target_atoms
                # Cubicness = 0 if nx=ny=nz, max 1
                max_exp = max(nx, ny, nz)
                cubicness = (max_exp - min(nx, ny, nz)) / max_exp if max_exp > 0 else 0
                
                # Check min_length if specified
                length_penalty = 0
                if min_length is not None:
                    cell_lengths = atoms.cell.lengths()
                    new_lengths = [nx * cell_lengths[0], ny * cell_lengths[1], nz * cell_lengths[2]]
                    for l in new_lengths:
                        if l < min_length:
                            length_penalty += (min_length - l)  # Heavy penalty for being too short
                            
                score = 0.5 * target_dist + 0.5 * cubicness + length_penalty
                
                if score < best_score:
                    best_score = score
                    best_expansion = (nx, ny, nz)
    
    if best_expansion is None:
        # Fallback
        nx = ny = nz = max(1, int(round(expansion_factor)))
        best_expansion = (nx, ny, nz)
    
    logger.info(f"Expanding structure from {current_atoms} to {current_atoms * best_expansion[0] * best_expansion[1] * best_expansion[2]} atoms using {best_expansion}")
    
    expanded_atoms = atoms.repeat(best_expansion)
    
    if is_pmg:
        return AseAtomsAdaptor.get_structure(expanded_atoms)
    return expanded_atoms
