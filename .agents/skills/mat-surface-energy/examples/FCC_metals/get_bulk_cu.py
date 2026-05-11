import ase.build
from pymatgen.io.ase import AseAtomsAdaptor

atoms = ase.build.bulk('Cu', 'fcc', a=3.61)
structure = AseAtomsAdaptor.get_structure(atoms)
structure.to(filename='Cu_bulk.cif')
