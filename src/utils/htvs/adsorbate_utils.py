from catkit import Gratoms

def get_adsorbate(species: str) -> Gratoms:
    """Build the Gratoms adsorbate object for the requested species.
    The first atom in the string/positions is the Anchor atom, placed at (0,0,0).
    The rest of the molecule is oriented predominantly in the +Z direction (away from surface).

    Args:
        species: Adsorbate species string (e.g. "O", "OH", "OOH", "CO", "NH2").

    Returns:
        catkit.Gratoms: Adsorbate structure.

    Raises:
        ValueError: If species is not supported.
    """

    # Single atoms
    if species in ["O", "H", "C", "N", "S", "P"]:
        return Gratoms(species, positions=[(0, 0, 0)])
        
    # Oxygen-based
    elif species == "OH":
        return Gratoms("OH", positions=[(0, 0, 0), (0, 0, 0.96)])
    elif species == "OOH":
        ads = Gratoms("OOH", positions=[(0, 0, 0), (0, 1.1, 0.9), (0, 1.2, 1.8)])
        ads.set_initial_magnetic_moments([0.7, 0.7, 0])
        return ads
        
    # Carbon-based
    elif species == "CO":
        return Gratoms("CO", positions=[(0, 0, 0), (0, 0, 1.13)])
    elif species == "CHO":
        return Gratoms("CHO", positions=[(0, 0, 0), (0, 1.1, 0.6), (0, -0.9, 0.6)])
    elif species == "COOH":
        return Gratoms("COOH", positions=[(0, 0, 0), (0, 1.1, 0.6), (0, -1.0, 0.8), (0, -1.0, 1.8)])
    elif species == "CH3":
        return Gratoms("CH3", positions=[(0, 0, 0), (0, 1.0, 0.4), (0.87, -0.5, 0.4), (-0.87, -0.5, 0.4)])
        
    # Nitrogen-based
    elif species == "NO":
        ads = Gratoms("NO", positions=[(0, 0, 0), (0, 0, 1.15)])
        ads.set_initial_magnetic_moments([1.0, 0])
        return ads
    elif species == "NH":
        return Gratoms("NH", positions=[(0, 0, 0), (0, 0, 1.02)])
    elif species == "NH2":
        return Gratoms("NH2", positions=[(0, 0, 0), (0, 0.8, 0.6), (0, -0.8, 0.6)])
    elif species == "NH3":
        return Gratoms("NH3", positions=[(0, 0, 0), (0, 0.9, 0.4), (0.8, -0.4, 0.4), (-0.8, -0.4, 0.4)])
        
    else:
        # Generic robust fallback using ase.build.molecule
        from ase.build import molecule
        import numpy as np
        try:
            mol = molecule(species)
        except Exception:
            raise ValueError(f"Unsupported generic species: {species!r}. Provide custom coordinates in get_adsorbate().")
        
        # Shift anchor atom (index 0) to origin
        mol.translate(-mol.positions[0])
        
        # Apply mathematical rotation to align the tail's center of mass into the +Z plane (vacuum)
        if len(mol) > 1:
            tail_com = np.mean(mol.positions[1:], axis=0)
            tail_norm = np.linalg.norm(tail_com)
            if tail_norm > 1e-4:
                v1 = tail_com / tail_norm
                v2 = np.array([0, 0, 1.0])
                axis = np.cross(v1, v2)
                axis_norm = np.linalg.norm(axis)
                if axis_norm > 1e-4:
                    angle = np.degrees(np.arcsin(axis_norm))
                    if np.dot(v1, v2) < 0:
                        angle = 180 - angle
                    mol.rotate(angle, axis, center=(0, 0, 0))
                elif np.dot(v1, v2) < 0:
                    mol.rotate(180, [1, 0, 0], center=(0, 0, 0))
                    
        return Gratoms(mol)
