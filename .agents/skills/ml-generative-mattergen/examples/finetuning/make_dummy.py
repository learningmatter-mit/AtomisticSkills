import json
from pymatgen.core import Lattices, Structure

struct = Structure(Lattices.cubic(3.0), ["Li"], [[0,0,0]])
s_dict = struct.as_dict()
data = [
    {"structure": s_dict, "formation_energy": -1.2},
    {"structure": s_dict, "formation_energy": -1.3}
]
with open('example_training_data.json', 'w') as f:
    json.dump(data, f)
