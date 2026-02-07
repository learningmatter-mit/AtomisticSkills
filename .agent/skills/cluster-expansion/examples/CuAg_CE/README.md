# Cu-Ag Cluster Expansion Example

This example demonstrates a complete workflow for training a Cluster Expansion (CE) model for the Cu-Ag alloy system and running a Monte Carlo (MC) simulation.

## Files
- `cluster_expansion.json`: The trained Cluster Expansion model (serialized).

## Workflow Description

### 1. Training (Iteration 0)
- **Disordered Structure**: A 50-50 Cu-Ag SQS-like supercell was used as the starting point.
- **Sampling**: 200 ordered structures were sampled using `mcp_smol_sample_ordered_structures`.
- **Relaxation**: Structures were relaxed using the `MACE-MP-small` MLIP model.
- **Fitting**: The CE model was trained on the relaxation results using `mcp_smol_train_cluster_expansion`.
    - **RMSE**: 3.6 meV/prim
    - **LOOCV**: 3.8 meV/prim
    - **Clusters**: 9 (Pair and Triplet)

## How to use
You can load the cluster expansion model using `smol`:

```python
from smol.cofe import ClusterExpansion

ce = ClusterExpansion.from_json("cluster_expansion.json")
print(ce)
```
