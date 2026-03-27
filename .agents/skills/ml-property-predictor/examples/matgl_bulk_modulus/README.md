# MatGL Bulk Modulus Property Predictor Tutorial

This directory contains a complete, self-contained example demonstrating how to use the `.agents/skills/ml-property-predictor/scripts/train_matgl_property.py` script to fine-tune a PyTorch Lightning-based MatGL MEGNet model to predict materials' **bulk modulus** (an intensive property).

## Contents
1. `run_matgl.py`: A Python wrapper script that automates loading the `.agents/test/mp_bulk_modulus.json` dataset as native PyTorch `in_memory` graph datasets (circumventing caching deadlocks), evaluating 25 epochs of optimization via `matgl-agent`, and crucially **automatically cleaning up** any massively serialized internal lightning checkpoint states to save disk space!

## Running the Example
First, ensure you are operating from the `base-agent` environment. The script will automatically trigger a sub-process inside the isolated `matgl-agent` conda environment for resolving dependency packages.

```bash
conda run -n base-agent python run_matgl.py
```

### Outputs
After successful execution, this directory will contain:
- `matgl_results/`: The core output directory hosting the final, optimized Lightning `matgl_model` artifact that encapsulates the generated DGL graph properties.
- **Reload Test Summary**: The script will independently test the inference capabilities of the newly dumped checkpoint bypassing Lightning entirely and using just the custom `MatGLWrapper`, proving identical matching of the final MAE precision metrics (typically hovering ~80 GPa after a micro-fine-tune).
