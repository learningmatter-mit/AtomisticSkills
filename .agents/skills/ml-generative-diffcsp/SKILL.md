---
name: ml-generative-diffcsp
description: Generate crystal structures with exact composition control using DiffCSP++ (space group + Wyckoff positions), or unconditionally from trained distributions.
category: [machine-learning]
---

# DiffCSP++ Crystal Structure Generation

## Goal

Generate novel crystal structures using DiffCSP++ (ICLR 2024), a diffusion model that leverages space group symmetry constraints for crystal structure prediction (CSP) and ab initio generation.

## 1. Prerequisites

> [!IMPORTANT]
> **GPU Required**: DiffCSP++ inference is significantly faster on GPU.

- The `diffcsp-agent` conda environment must be installed.
- DiffCSP++ repo cloned to `/home/bdeng/projects/DiffCSP-PP`.
- Pre-trained checkpoints downloaded to `checkpoints/` directory.

## 2. Available Models

| Model | Type | Description |
|-------|------|-------------|
| `mp_csp` | CSP | Materials Project — composition-constrained generation |
| `mp_gen` | Gen | Materials Project — unconditional generation |
| `perov_csp` | CSP | Perovskite — composition-constrained generation |
| `perov_gen` | Gen | Perovskite — unconditional generation |
| `carbon_gen` | Gen | Carbon — unconditional generation |
| `mpts_csp` | CSP | MPTS-52 — composition-constrained generation |

## 3. Usage Modes

### Mode 1: Single Composition via MCP Tool (Recommended)

Generate structures with exact composition using the `generate_structures_with_symmetry` MCP tool:

```bash
mcp_diffcsp_generate_structures_with_symmetry(
    spacegroup=58,                        # Space group number (1-230)
    wyckoff_letters="2a,2d,4g",           # Wyckoff positions (comma-separated or shorthand "adg")
    atom_types="Mn,Li,O",                 # Element per Wyckoff position
    model_name="mp_csp",                  # CSP model
    num_samples=5,                        # Number of structures to generate
    step_lr=1e-5,                         # Langevin step size
    output_dir="research/my_project"
)
```

### Mode 2: Batch Generation from JSON File

Generate multiple structures from a JSON specification file. This is useful when you have many different compositions to generate at once.

JSON format (see [examples/example.json](examples/example.json)):
```json
[
    {"spacegroup_number": 58, "wyckoff_letters": ["2a","2d","4g"], "atom_types": ["Mn","Li","O"]},
    {"spacegroup_number": 194, "wyckoff_letters": "abff", "atom_types": ["Tm","Tm","Ni","As"]}
]
```

Run the batch generation script:
```bash
# Env: diffcsp-agent
python .agents/skills/ml-generative-diffcsp/scripts/batch_generate.py \
    --json_file .agents/skills/ml-generative-diffcsp/examples/example.json \
    --model mp_csp \
    --output_dir diffcsp_batch_output \
    --step_lr 1e-5
```

### Mode 3: Ab Initio (Unconditional) Generation

Generate structures from the training distribution without specifying composition. Requires a generation model (`mp_gen`, `perov_gen`, or `carbon_gen`).

```bash
# Env: diffcsp-agent
python .agents/skills/ml-generative-diffcsp/scripts/unconditional_generate.py \
    --model mp_gen \
    --num_structures 100 \
    --output_dir diffcsp_gen_output \
    --step_lr 5e-6
```

## 4. Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `spacegroup` | — | Space group number (1-230) |
| `wyckoff_letters` | — | Wyckoff positions (e.g., `"2a,2d,4g"` or shorthand `"adg"`) |
| `atom_types` | — | Element for each Wyckoff position (e.g., `"Mn,Li,O"`) |
| `model_name` | `mp_csp` | Pre-trained model name |
| `num_samples` | `1` | Number of structures per composition |
| `step_lr` | `1e-5` | Langevin dynamics step size |
| `batch_size` | `128` | Batch size for parallel generation |

## 5. Output Files

- `structure_XXXX.cif`: Generated crystal structure files (pymatgen CIF format)
- `generation_metadata.json`: Generation parameters and statistics

## 6. Constraints

> [!WARNING]
> **Space Group Knowledge Required**: You need to know the space group number and Wyckoff positions for your target composition. Use ICSD, Materials Project, or pyxtal to find these.

> [!NOTE]
> **Wyckoff Notation**: Positions can be given as full labels (`"2a,2d,4g"`) or shorthand letters (`"adg"`). The number prefix is the site multiplicity — it's automatically determined from the space group.

- **Environments**: All scripts require the `diffcsp-agent` conda environment.
- **GPU**: A CUDA GPU is recommended for reasonable generation speed.
- **CSP vs Gen models**: CSP models require `atom_types`; Gen models can generate without them.

## 7. Workflow Integration

DiffCSP++ works well in combination with:
- **Structure relaxation**: Use MLIP tools ([MACE](../ml-foundation-potentials/SKILL.md), FairChem, MatGL) to optimize generated structures
- **Stability analysis**: Use [mat-stability](../mat-stability/SKILL.md) to calculate E_hull
- **Comparison**: Generate structures with DiffCSP++, [ADiT](../ml-generative-adit/SKILL.md), and [MatterGen](../ml-generative-mattergen/SKILL.md) for diversity

---

**Author:** Bowen Deng  
**Contact:** [GitHub @bowen-bd](https://github.com/bowen-bd)
