---
name: ml-generative-adit
description: Generate novel crystal structures and molecules using ADiT (All-atom Diffusion Transformer), a unified latent diffusion model.
category: [machine-learning, materials, chemistry]
---

# ADiT Structure Generation Skill

## Goal

Generate novel crystal structures and molecules using ADiT (All-atom Diffusion Transformers, ICML 2025), a unified latent diffusion framework from Meta FAIR Chemistry that jointly generates both periodic materials and non-periodic molecular systems from a shared latent space.

## 1. Prerequisites

> [!IMPORTANT]
> **GPU Required**: ADiT requires a CUDA-compatible GPU. CPU inference is extremely slow.

- The `adit-agent` conda environment must be installed and configured.
- The AADT repository must be cloned to `.agents/tmp/adit/`.
- Pre-trained weights are automatically downloaded from HuggingFace on first use.

## 2. Available Models

ADiT provides a joint pre-trained model trained on:

- **MP20**: Materials Project 2020 dataset (inorganic crystals, ~45K structures)
- **QM9**: Small organic molecules (~134K molecules)

The single checkpoint handles both crystal and molecule generation, selected via the `generation_type` parameter.

## 3. MCP Tool Usage

### Crystal Generation

Generate novel periodic crystal structures (saved as CIF files):

```bash
mcp_adit_generate_structures(
    generation_type="crystals",    # Generate periodic crystals
    num_structures=10,             # Number of structures to generate
    batch_size=100,                # Batch size for GPU efficiency
    cfg_scale=2.0,                 # Classifier-free guidance scale
    output_dir="research/my_project/crystals"
)
```

### Molecule Generation

Generate novel non-periodic molecules (saved as XYZ files):

```bash
mcp_adit_generate_structures(
    generation_type="molecules",   # Generate molecules
    num_structures=10,
    batch_size=100,
    cfg_scale=2.0,
    output_dir="research/my_project/molecules"
)
```

## 4. Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `generation_type` | `"crystals"` | `"crystals"` for periodic structures (CIF), `"molecules"` for non-periodic (XYZ) |
| `num_structures` | `10` | Total number of structures to generate |
| `batch_size` | `100` | Batch size (larger = faster on GPU) |
| `cfg_scale` | `2.0` | Classifier-free guidance scale. Higher = more typical but less diverse |
| `device` | `"auto"` | Device: `"auto"`, `"cpu"`, or `"cuda"` |
| `output_dir` | auto | Output directory. Auto-creates under research dir |

## 5. Output Files

### Crystal Generation
- `crystal_XXXX.cif`: Generated crystal structure files (pymatgen CIF format)
- `generation_metadata.json`: Generation parameters and statistics

### Molecule Generation
- `molecule_XXXX.xyz`: Generated molecule files (ASE XYZ format)
- `generation_metadata.json`: Generation parameters and statistics

## 6. Limitations

> [!WARNING]
> **No Conditional Generation**: The public checkpoint is unconditional only — you cannot
> condition on specific compositions, space groups, or properties.
> To get specific compositions: generate many structures and filter.

> [!WARNING]
> **No Fine-Tuning via MCP**: Fine-tuning requires the full AADT training pipeline
> with multi-GPU setup and wandb logging. Use the raw codebase for training.

> [!NOTE]
> **Atom Count Distribution**: The number of atoms per generated structure is sampled from
> the training dataset distribution. For crystals (MP20), this peaks around 8-20 atoms.
> For molecules (QM9), this peaks around 18 atoms including hydrogens.

## 7. Best Practices

> [!TIP]
> - **Start with crystals**: Crystal generation on MP20 tends to produce more valid structures
> - **Guidance scale**: Use 2.0 (default) for balanced diversity/quality. Increase to 3.0-4.0 for more "typical" structures
> - **Validate outputs**: Always validate generated structures via relaxation and stability analysis
> - **Batch size**: Use batch_size=100 for best GPU throughput

## 8. Workflow Integration

ADiT works well in combination with:
- **Structure relaxation**: Use MLIP tools (MACE, FairChem, MatGL) to optimize generated structures
- **Stability analysis**: Calculate E_hull to identify thermodynamically stable phases
- **Property prediction**: Use MLIPs or DFT to calculate properties of generated structures
- **Comparison with MatterGen**: Generate structures with both ADiT and MatterGen for diversity

## 9. Architecture

ADiT uses a two-stage latent diffusion approach:
1. **VAE Autoencoder**: Maps all-atom representations (atoms, coords, lattice) to a shared latent space
2. **DiT Denoiser**: Trained via flow matching to generate new latent embeddings
3. **Decoder**: Converts latent embeddings back to atomic structures

This unified framework handles both periodic (crystals) and non-periodic (molecules) systems.

---
---

**Author:** Bowen Deng  
**Contact:** [GitHub @bowen-bd](https://github.com/bowen-bd)
