---
name: ml-cluster-expansion
description: train a Cluster Expansion (CE) for lattice-based Monte Carlo simulation of disordered materials.
category: [machine-learning, materials]
---

# Cluster Expansion

## Goal

To automatically build and refine a Cluster Expansion (CE) model for a disordered material system using an **Agent-driven iterative workflow** that leverages MCP tools for efficient training, sampling, and labeling.

## Workflow Overview

1.  **Preparation**: Generate a disordered primordial structure.
2.  **Iteration 0**: systematic enumeration to generate initial structures.
3.  **Labeling**: Relax structures with an MLIP (e.g., MACE, CHGNet) via MCP.
4.  **Training**: Train the CE model using `mcp_smol_train_cluster_expansion`.
5.  **Sampling**: Run MC with `mcp_smol_run_monte_carlo` to explore configuration space.
6.  **Selection**: Extract structures from MC, compute features, and select novel configurations.
7.  **Loop**: Repeat labeling, training, and sampling until convergence.

---

### Step 1: Prepare the Primordial Structure

Use `prepare_disordered.py` to handle symmetry refinement and disorder creation. It is highly recommended to save the primordial structure as a **JSON** file to preserve exact occupancy and species information, avoiding "unrecognized species" errors during matching.

```bash
# Env: smol-agent
python .agents/skills/ml-cluster-expansion/scripts/prepare_disordered.py \
    input_structure.cif \
    Li \
    0.5 \
    -o primordial.cif
```

---

### Step 2: Iteration 0 (Ordered Structure Sampling)

Generate an initial set of structures using systematic enumeration and D-optimality via the MCP tool. It is recommended to generate around **1000 structures** to ensure high coverage of the configuration space.

```python
# MCP Tool: mcp_smol_sample_ordered_structures
result = mcp_smol_sample_ordered_structures(
    disordered_structure="primordial.cif",
    cutoffs={2: 5.0, 3: 4.0},
    num_structures=1000,
    target_num_sites=32,
    output_dir="./ce_project/iter_0/to_label"
)
```

> [!NOTE]
> **Training Workflow**: You can perform a **Simple Training** by only using the initially `sample_ordered_structures` set. This is often sufficient for basic property predictions. For high-accuracy ground-state exploration, you should continue with the **Active Learning** loop (MC sampling and iterative refinement).

> [!TIP]
> This tool works for arbitrary disorder, including **multi-element alloys** (e.g., Co-Ni-Cr) and **multi-sublattice systems** (e.g., (Li-Na)(Cl-Br)).

---

### Step 3: Label Structures (Agent/MCP)

Use the appropriate MLIP MCP tool to **relax** the structures. 

> [!IMPORTANT]
> **Fixed Cell**: Always set `relax_cell=False` during MLIP relaxation for cluster expansion training. The cluster expansion model is built on a fixed lattice.
> **Fixed Lattice**: Ensure the supercell matrix used for enumeration/sampling matches your expectation.

**Example (MACE)**:
```python
mcp_mace_load_model(model_name="MACE-OMAT-0-small", device="cuda")
mcp_mace_relax_structure(
    structure_data="./ce_project/iter_0/to_label",
    fmax=0.02,
    relax_cell=False,
    output_dir="./ce_project/iter_0/results"
)
```

---

### Step 4: Train CE

The `mcp_smol_train_cluster_expansion` tool can directly accept the directory containing relaxation results (from Step 3). It will automatically find and aggregate the training data.

```python
result = mcp_smol_train_cluster_expansion(
    disordered_structure="primordial.cif",
    training_data="ce_project/iter_0/results", 
    cutoffs={2: 5.0, 3: 4.0},
    ce_file="ce_project/cluster_expansion.json"
)
```

---

> [!NOTE]
> **Training Workflow**: You can perform a **Simple Training** by only using the initially `sample_ordered_structures` set. This is often sufficient for basic property predictions. For high-accuracy ground-state exploration, you should continue with the **Active Learning** loop (MC sampling and iterative refinement).

### Step 5: Direct Feature Matrix Fitting (Optional)

In some scenarios, you may have pre-computed feature matrices and energies (e.g., from literature or external workflows). You can directly fit these without building a `ClusterSubspace` first, using the `mcp_smol_fit_feature_matrix` tool. This is also how you can utilize advanced techniques like **Sparse Group Lasso (SGL)**.

```python
# MCP Tool: mcp_smol_fit_feature_matrix
result = mcp_smol_fit_feature_matrix(
    feature_matrix_path="fm.npy",
    energies_path="e.npy",
    groups_path="groups.npy", # Required for sgl
    fit_method="sgl",         # 'ls', 'lasso', 'ridge', or 'sgl'
    alpha=0.002,
    lambda_mixing=0.5,
    test_size=0.2
)
```
> [!TIP]
> **Sparse Group Lasso (SGL)** is highly recommended for complex, high-component systems as it naturally selects important cluster groups while maintaining sparsity. It requires a `groups.npy` file that assigns each feature column to a cluster orbit group.

---

### Step 6: Active Learning Loop (Optional)

#### A. Run Monte Carlo Sampling
```python
mc_result = mcp_smol_run_monte_carlo(
    supercell_matrix=[[2,0,0], [0,2,0], [0,0,2]],
    temperature=2000, 
    steps=100000,
    ce_file="./ce_project/cluster_expansion.json",
    trajectory_file="./ce_project/iter_1/mc_trajectory.h5"
)
```

#### B. Extract & Select Candidates
Extract structures from the trajectory. The skill script handles dimension squeeze for single-sample trajectories.

```bash
python .agents/skills/ml-cluster-expansion/scripts/extract_mc_structures.py \
    --trajectory_file ./ce_project/iter_1/mc_trajectory.h5 \
    --cluster_expansion ./ce_project/cluster_expansion.json \
    --output_dir ./ce_project/iter_1/to_label \
    --num_structures 20 \
    --strategy random
```

> [!IMPORTANT]
> **Loop Back**: After extracting these new candidate structures, go back to **Step 3** to relax and label them. Then, add these new results to your training set and repeat **Step 4** to refine your Cluster Expansion.

## Energy Format for Training Data

> [!IMPORTANT]
> **Use Total Energy (Extensive Property)**  
> Training structures should include the **total energy** for the entire supercell (not per-atom energy).
> Smol automatically normalizes energies by the primitive cell size during training via `get_property_vector('energy', normalize=True)`.

**Example**: For a 32-atom supercell with total DFT energy of -160.0 eV:
- ✅ Correct: `{"structure": {...}, "energy": -160.0}`
- ❌ Incorrect: `{"structure": {...}, "energy": -5.0}` (per-atom)

**Formation Energy**: If you want to train on formation energies instead of total energies, calculate the formation energy for each structure first, then provide it as the total (extensive) energy value. Smol will still normalize by primitive cell size.

## Constraints & Tips

-   **Primordial Format**: Use `.cif` for primordial structures. Ensure partial occupancies are correctly defined.
-   **Supercell Matrices**: If automatic matching fails (e.g. "Could not determine supercell matrix"), provide `sc_matrix` explicitly in the training data JSON.
-   **Fixed Cell**: Always set `relax_cell=False` to maintain the cluster expansion mapping.
-   **Convergence**: Target LOOCV < 10 meV/atom for high-accuracy models.
-   **Simulations**: For finite-temperature MC simulations using your trained model, refer to the [mat-disorder](../mat-disorder/SKILL.md) skill.
---

**Author:** Bowen Deng  
**Contact:** [GitHub @bowen-bd](https://github.com/bowen-bd)
