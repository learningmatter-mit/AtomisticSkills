---
name: ml-generative-mattergen
description: Generate inorganic material structures using MatterGen, a diffusion-based generative model.
category: [machine-learning, materials]
---

# MatterGen Structure Generation Skill

This skill provides tools for generating novel inorganic material structures using MatterGen, a state-of-the-art diffusion-based generative model for crystalline materials.

## 1. Prerequisites

> [!IMPORTANT]
> **ARM/aarch64 Support**: MatterGen CAN work on ARM-based systems like NVIDIA DGX Spark. However, PyG dependencies (torch-scatter, torch-cluster) must be compiled from source with CUDA_HOME properly configured. See installation guide below.

- The `mattergen-agent` conda environment must be installed and configured.
- MatterGen requires Python 3.10 and CUDA 13.0 compatible GPU for efficient generation.
- **For ARM/aarch64 systems**: See [Installing torch-scatter on ARM](../../docs/installing_torch_scatter_arm.md) for detailed installation instructions.

## 2. Available Models

MatterGen provides several pretrained models:

- `mattergen_base`: Base unconditional generative model
- `mp_20_base`: Materials Project base model
- `dft_mag_density`: Model for magnetic density conditioning
- `chemical_system`: Model for chemical system conditioning

## 3. MCP Tool Usage

The MCP tool automatically loads models when needed - no explicit load step required.

### Unconditional Generation

Generate novel structures without conditioning:

```python
from mcp_base import mcp_mattergen_generate_structures

result = mcp_mattergen_generate_structures(
    model_name="mattergen_base",
    num_structures=10,
    batch_size=10,
    output_dir="research/my_project/generated"
)
```

### Chemical System Conditioning

Generate structures from a specific chemical system (controls which elements appear):

```python
result = mcp_mattergen_generate_structures(
    chemical_system="Li-Fe-P-O",  # Automatically uses chemical_system model
    guidance_scale=1.0,  # Recommended for chemical system conditioning
    num_structures=20,
    batch_size=10,
    output_dir="research/cathode_materials/generated"
)
```

> [!NOTE]
> Chemical system conditioning controls which **elements** appear, but **NOT** the exact stoichiometry.
> For example, `chemical_system="Li-Zr-Cl"` can generate Li3Cl5, LiZrCl4, Li2ZrCl5, etc., but you cannot specify exactly "Li2ZrCl6".



## 4. Fine-Tuning (Skill Scripts)

Fine-tune MatterGen on custom datasets using the skill scripts:

### Step 1: Prepare Training Data

```bash
cd /home/bdeng/projects/AtomisticSkills/.agents/skills/ml-generative-mattergen
conda activate mattergen-agent

# Convert structures and properties to CSV format
python scripts/prepare_training_data.py \
  --structures-json training_structures.json \
  --property-name "formation_energy" \
  --output training_data.csv
```

**Training data JSON format**:
```json
[
  {
    "structure": {<pymatgen Structure dict>},
    "properties": {"formation_energy": -2.5}
  },
  ...
]
```

### Step 2: Run Fine-Tuning

```bash
python scripts/run_finetuning.py \
  --training-data training_data.csv \
  --property-name "formation_energy" \
  --base-model "mattergen_base" \
  --epochs 100 \
  --output-dir finetuned_formation_energy
```

**Fine-tuning parameters**:
- `--training-data`: Path to CSV from Step 1
- `--property-name`: Property to condition on (must match CSV column)
- `--base-model`: Starting model (mattergen_base, chemical_system, etc.)
- `--epochs`: Training epochs (100-200 recommended)
- `--learning-rate`: Learning rate (default: 5e-6)
- `--batch-size`: Batch size (default: 32)

> [!TIP]
> - Start with 2 epochs for quick testing
> - Use 100-200 epochs for actual fine-tuning
> - GPU required (fine-tuning on CPU is extremely slow)

## 5. Output Files

### Generation Output
- `structure_XXXX.cif`: Generated structure files
- `generation_metadata.json`: Metadata about generation parameters

### Fine-Tuning Output
- `checkpoints/`: Model checkpoint files (.ckpt)
- `config.yaml`: Hydra configuration used
- Training logs and metrics

## 6. Limitations

> [!WARNING]
> **Chemical System vs. Stoichiometry**
> - `chemical_system` parameter controls which **elements** are encouraged to be present.
> - It does **NOT** guarantee that all specified elements will be in the output structure.
> - It does **NOT** prevent other elements from occasionally appearing if guidance is too low.
> - Example: `chemical_system="Li-Zr-Cl"` might generate LiCl, ZrCl4, or even structures missing Li, alongside the desired ternaries (e.g., Li2ZrCl6).
> - **Action Required:** You MUST write a post-processing script to filter the output `.cif` files and keep only the ones that match your exact target elemental composition.

> [!WARNING]
> **CSP Mode Not Available**
> - Target composition control (`target_compositions` parameter) requires CSP-trained models
> - CSP models are NOT publicly available - must be custom-trained
> - Public models (mattergen_base, chemical_system, etc.) are **generation models** only

## 7. Best Practices

> [!IMPORTANT]
> - **GPU Required**: MatterGen requires a CUDA-compatible GPU. CPU is extremely slow.
> - **Batch Size**: Use larger batches (10-50) for efficient GPU utilization
> - **Guidance Scale**: Higher values (1.0-5.0) enforce stronger conditioning
> - **Composition Filtering**: Always filter the generated output CIFs using `pymatgen` to verify that the structures contain exactly the target elements.
> - **Validation**: Always validate generated structures via relaxation and stability analysis

> [!TIP]
> - Start with unconditional generation to understand model behavior
> - Use chemical_system conditioning to explore specific element combinations
> - Fine-tune on domain-specific data for specialized applications (e.g., cathode materials)

## 8. Workflow Integration

MatterGen works well in combination with:
- **Structure relaxation**: Use MCP MLIP tools to optimize generated structures
- **Stability analysis**: Calculate E_hull to identify stable phases
- **Property prediction**: Use MLIPs or DFT to calculate properties
- **High-throughput screening**: Generate → Relax → Screen workflow

## 9. Examples

See `examples/` for:
- Unconditional generation workflow
- Chemical system conditioning
- Fine-tuning on custom datasets with complete example data

---
---

**Author:** Bowen Deng  
**Contact:** [GitHub @bowen-bd](https://github.com/bowen-bd)
