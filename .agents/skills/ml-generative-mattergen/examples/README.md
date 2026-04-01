# MatterGen Fine-Tuning Examples

This directory contains example data and scripts for fine-tuning MatterGen on custom datasets.

## Example Files

- `example_training_data.json` - Sample training data with structures and properties
- `run_finetune_example.sh` - Complete fine-tuning workflow script

## Quick Start

### 1. Prepare Your Training Data

Create a JSON file with your structures and properties:

```json
[
  {
    "structure": {
      "@module": "pymatgen.core.structure",
      "@class": "Structure",
      ...
    },
    "properties": {
      "formation_energy": -2.5,
      "band_gap": 1.2
    }
  }
]
```

Or use the preparation script:

```bash
conda activate mattergen-agent

python ../scripts/prepare_training_data.py \
  --structures-json your_data.json \
  --property-name "formation_energy" \
  --output training_data.csv
```

### 2. Run Fine-Tuning

```bash
# Quick test (2 epochs)
python ../scripts/run_finetuning.py \
  --training-data training_data.csv \
  --property-name "formation_energy" \
  --base-model "mattergen_base" \
  --epochs 2 \
  --output-dir ./test_finetune

# Full fine-tuning (100 epochs)
python ../scripts/run_finetuning.py \
  --training-data training_data.csv \
  --property-name "formation_energy" \
  --epochs 100 \
  --learning-rate 5e-6 \
  --batch-size 32 \
  --output-dir ./finetuned_formation_energy
```

### 3. Use the Fine-Tuned Model

Currently, using a fine-tuned model requires loading it via the MatterGen Python API directly. MCP tool support is planned for a future update.

## Notes

- **GPU Required**: Fine-tuning requires a CUDA-compatible GPU
- **Training Time**: Expect several hours for 100 epochs on typical datasets
- **Data Requirements**: Minimum 50-100 structures recommended for meaningful fine-tuning
- **Property Range**: Ensure your property values have reasonable variance
