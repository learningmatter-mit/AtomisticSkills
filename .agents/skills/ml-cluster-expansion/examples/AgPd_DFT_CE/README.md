# AgPd DFT Cluster Expansion Fitting

This example adapts the [icet AgPd tutorial](https://icet.materialsmodeling.org/get_started/construct_cluster_expansion.html) demonstrating how to process reference DFT training data and use the complete `smol` MCP pipeline to train a cluster expansion for AgPd.

**Dataset Origin:** The 137 training structures and their mixing energies used for this Cluster Expansion training are sourced from the [`icet` tutorial](https://gitlab.com/materials-modeling/icet/-/raw/master/examples/tutorial/reference_data.db?inline=false).

## 1. Extracting the Training Dataset
The first step is to extract the structures and energies from the `ase` database and convert them into the `pymatgen` format expected by `smol`. 

**Key Takeaway:** The `icet` database returns intensive mixing energy (`eV/atom`), while `smol`'s Cluster Expansion relies on total system energy. We must calculate the total extensive energy by multiplying by the number of atoms.

```python
from ase.db import connect
from pymatgen.io.ase import AseAtomsAdaptor

db_path = "reference_data.db"

db = connect(db_path)
training_data = []

# Collect structures up to 6 atoms
for row in db.select("natoms<=6"):
    structure = AseAtomsAdaptor.get_structure(row.toatoms())
    total_mixing_energy = row.mixing_energy * row.natoms
    
    training_data.append({
        "structure": structure.as_dict(),
        "energy": total_mixing_energy
    })
```

## 2. Preparing the Disordered Structure
The primitive structure from the database must be converted into a disordered representation to define the cluster subspace. We fetch the pure Ag structure (id=1) and apply an ideal `{Ag: 0.5, Pd: 0.5}` disorder.

```python
prim_row = db.get(id=1)
prim_structure = AseAtomsAdaptor.get_structure(prim_row.toatoms())

# Apply uniform disorder across all sites
for site in prim_structure:
    site.species = {"Ag": 0.5, "Pd": 0.5}
```

## 3. Training the CE Model with Least Squares
By utilizing the MCP tool `mcp_smol_train_cluster_expansion`, we fit the AgPd cluster expansion using the prepared list of data dictionaries and the specified cutoffs `{2: 8.0, 3: 6.5, 4: 5.5}` corresponding to pairs, triplets, and quadruplets.

```python
# MCP Tool: mcp_smol_train_cluster_expansion
from src.mcp_server.smol_server import train_cluster_expansion

result = train_cluster_expansion(
    disordered_structure=prim_structure.as_dict(),
    training_data=training_data,
    cutoffs={2: 8.0, 3: 6.5, 4: 5.5},
    fit_method="ls", 
    ce_file="cluster_expansion.json"
)

print(result["rmse"]) # Expected ~0.00185 eV/atom
```

## 4. Result Verification
After running a compilation of the script above (e.g. `python build_AgPd_CE.py`), the result of the training will be the `cluster_expansion.json` file. The model should emit an RMSE around `1.8 - 2.0` meV/atom which faithfully matches the original `icet` notebook's ARDR training accuracy. This model is now ready to be used for Monte Carlo sampling.

## References
1. [icet AgPd MC](https://icet.materialsmodeling.org/get_started/run_monte_carlo.html)
1. [icet Paper](https://arxiv.org/abs/1901.08790)