#!/bin/bash
set -e

echo "=== Surface Energy and Wulff Shape Example ==="
echo

# 1. Create a simple bulk FCC Cu structure
echo "Creating bulk Cu structure..."
cat << 'EOF' > get_bulk_cu.py
import ase.build
from pymatgen.io.ase import AseAtomsAdaptor

atoms = ase.build.bulk('Cu', 'fcc', a=3.61)
structure = AseAtomsAdaptor.get_structure(atoms)
structure.to(filename='Cu_bulk.cif')
EOF
conda run -n base-agent python get_bulk_cu.py

# 2. Mock surface energies from literature for Cu (units format usually expected: J/m2)
echo "Setting up surface_energies.json..."
cat << 'EOF' > surface_energies.json
{
  "unique_min_slabs": [
    {
      "miller_index": [1, 1, 1],
      "gamma_j_m2": 1.30
    },
    {
      "miller_index": [1, 0, 0],
      "gamma_j_m2": 1.45
    },
    {
      "miller_index": [1, 1, 0],
      "gamma_j_m2": 1.55
    }
  ]
}
EOF

# 3. Generate Wulff shape
echo "Generating Wulff shape..."
conda run -n base-agent python ../../scripts/generate_wulff.py --energies_json surface_energies.json --bulk Cu_bulk.cif --output wulff_shape.png

echo "=== Success ==="
