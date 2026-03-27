#!/usr/bin/env python3
"""
Run MatterGen fine-tuning with proper Hydra configuration.

This script wraps MatterGen's fine-tuning functionality and generates
the necessary Hydra config overrides.
"""

import argparse
import sys
import subprocess
from pathlib import Path


def run_finetuning(
    training_data_path: Path,
    property_name: str,
    base_model: str = "mattergen_base",
    epochs: int = 100,
    output_dir: Path = None,
    learning_rate: float = 5e-6,
    batch_size: int = 32
) -> None:
    """
    Run MatterGen fine-tuning.
    
    Args:
        training_data_path: Path to training data CSV
        property_name: Property name to condition on
        base_model: Base model to fine-tune from
        epochs: Number of training epochs
        output_dir: Output directory for checkpoints
        learning_rate: Learning rate for adapter training
        batch_size: Training batch size
    """
    if output_dir is None:
        output_dir = Path(f"finetuned_{property_name}")
    
    output_dir = Path(output_dir).absolute()
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"=== MatterGen Fine-Tuning ===")
    print(f"Training data: {training_data_path}")
    print(f"Property: {property_name}")
    print(f"Base model: {base_model}")
    print(f"Epochs: {epochs}")
    print(f"Output directory: {output_dir}")
    print(f"Learning rate: {learning_rate}")
    print(f"Batch size: {batch_size}")
    print()
    
    # Create temporary config directory for custom property
    config_dir = output_dir / "config"
    config_dir.mkdir(exist_ok=True)
    
    # Get MatterGen's config directory
    import mattergen
    mattergen_dir = Path(mattergen.__file__).parent
    property_embeddings_dir = mattergen_dir / "conf" / "lightning_module" / "diffusion_module" / "model" / "property_embeddings"
    
    # Create property embedding YAML file
    property_config_path = property_embeddings_dir / f"{property_name}.yaml"
    property_config_content = f"""_target_: mattergen.property_embeddings.PropertyEmbedding
name: {property_name}
unconditional_embedding_module:
  _target_: mattergen.property_embeddings.EmbeddingVector
  hidden_dim: ${{lightning_module.diffusion_module.model.hidden_dim}}
conditional_embedding_module:
  _target_: mattergen.diffusion.model_utils.NoiseLevelEncoding
  d_model: ${{lightning_module.diffusion_module.model.hidden_dim}}
scaler:
  _target_: mattergen.common.utils.data_utils.StandardScalerTorch
"""
    
    # Save to both locations (MatterGen dir and backup in output dir)
    with open(property_config_path, 'w') as f:
        f.write(property_config_content)
    
    backup_path = config_dir / f"{property_name}.yaml"
    with open(backup_path, 'w') as f:
        f.write(property_config_content)
    
    print(f"✓ Created property config in MatterGen: {property_config_path}")
    print(f"✓ Backup saved to: {backup_path}")
    
    # Create custom adapter config in output directory
    adapter_config_dir = mattergen_dir / "conf" / "adapter"
    adapter_config_path = adapter_config_dir / "custom_property.yaml"
    adapter_config_content = f"""pretrained_name: {base_model}
model_path: null
load_epoch: last
full_finetuning: true

adapter:
  _target_: mattergen.adapter.GemNetTAdapter
  property_embeddings_adapt: {{}}

defaults:
  - /lightning_module/diffusion_module/model/property_embeddings@adapter.property_embeddings_adapt.{property_name}: {property_name}
"""
    
    with open(adapter_config_path, 'w') as f:
        f.write(adapter_config_content)
    
    backup_adapter_path = config_dir / "adapter_custom.yaml"
    with open(backup_adapter_path, 'w') as f:
        f.write(adapter_config_content)
    
    print(f"✓ Created adapter config in MatterGen: {adapter_config_path}")
    print(f"✓ Backup saved to: {backup_adapter_path}")
    
    # Create custom data module config for CSV dataset
    data_module_config_dir = mattergen_dir / "conf" / "data_module"
    data_module_config_path = data_module_config_dir / "custom_csv.yaml"
    
    # Create cache directory for CSV parsing
    cache_dir = output_dir / "cache"
    cache_dir.mkdir(exist_ok=True)
    
    data_module_config_content = f"""_target_: mattergen.common.data.datamodule.CrystDataModule
_recursive_: true
properties: [{property_name}]

transforms:
- _target_: mattergen.common.data.transform.symmetrize_lattice
  _partial_: true
- _target_: mattergen.common.data.transform.set_chemical_system_string
  _partial_: true

dataset_transforms: 
  - _target_: mattergen.common.data.dataset_transform.filter_sparse_properties
    _partial_: true

average_density: 0.05771451654022283

train_dataset:
  _target_: mattergen.common.data.dataset.CrystalDataset.from_csv
  csv_path: {training_data_path.absolute()}
  cache_path: {cache_dir.absolute()}/train
  transforms: ${{data_module.transforms}}

val_dataset:
  _target_: mattergen.common.data.dataset.CrystalDataset.from_csv
  csv_path: {training_data_path.absolute()}
  cache_path: {cache_dir.absolute()}/val
  transforms: ${{data_module.transforms}}

num_workers:
  train: 0
  val: 0
  test: 0

batch_size:
  train: {batch_size}
  val: {batch_size}
  test: {batch_size}

max_epochs: {epochs}
"""
    
    with open(data_module_config_path, 'w') as f:
        f.write(data_module_config_content)
    
    backup_data_module_path = config_dir / "data_module_custom.yaml"
    with open(backup_data_module_path, 'w') as f:
        f.write(data_module_config_content)
    
    print(f"✓ Created data module config in MatterGen: {data_module_config_path}")
    print(f"✓ Backup saved to: {backup_data_module_path}")
    print()
    
    
    # Build Hydra config overrides using the custom adapter config
    # Following official MatterGen fine-tuning approach from README
    overrides = [
        "adapter=custom_property",
        "data_module=custom_csv",
        f"trainer.max_epochs={epochs}",
        f"lightning_module.optimizer_partial.lr={learning_rate}",
        "trainer.check_val_every_n_epoch=1",  # CRITICAL FIX: Validate every epoch so ModelCheckpoint can save
        "~trainer.logger"  # Disable WandB logging
    ]
    
    # Build command using official mattergen-finetune CLI
    # This ensures Hydra's automatic checkpoint management is used
    cmd = ["mattergen-finetune"] + overrides
    
    print(f"Running command:")
    print(" ".join(cmd))
    print()
    
    try:
        result = subprocess.run(
            cmd,
            check=True,
            cwd=output_dir,  # Run in output dir so Hydra outputs are relative to it
            text=True,
            env={**subprocess.os.environ, "OUTPUT_DIR": str(output_dir)}
        )
        
        
        print(f"\n✓ Fine-tuning completed successfully")
        
        # Find checkpoints in Hydra's output directory structure
        # Hydra saves to outputs/singlerun/YYYY-MM-DD/HH-MM-SS/checkpoints/
        hydra_outputs = output_dir / "outputs" / "singlerun"
        checkpoint_paths = []
        
        if hydra_outputs.exists():
            # Find all checkpoint directories
            for date_dir in sorted(hydra_outputs.iterdir(), reverse=True):
                if date_dir.is_dir():
                    for time_dir in sorted(date_dir.iterdir(), reverse=True):
                        checkpoint_dir = time_dir / "checkpoints"
                        if checkpoint_dir.exists():
                            checkpoints = list(checkpoint_dir.glob("*.ckpt"))
                            if checkpoints:
                                checkpoint_paths.extend(checkpoints)
                                print(f"✓ Found {len(checkpoints)} checkpoint(s) in {checkpoint_dir}:")
                                for ckpt in checkpoints:
                                    print(f"  - {ckpt.name}")
                                break  # Use most recent time directory
                    if checkpoint_paths:
                        break  # Use most recent date directory
        
        if not checkpoint_paths:
            print("⚠ Warning: No checkpoints found. Check outputs/singlerun/ directory.")
        
        return 0
        
    except subprocess.CalledProcessError as e:
        print(f"\n✗ Fine-tuning failed with return code {e.returncode}", file=sys.stderr)
        return e.returncode
    except Exception as e:
        print(f"\n✗ Error: {e}", file=sys.stderr)
        return 1


def main():
    parser = argparse.ArgumentParser(
        description="Fine-tune MatterGen model on custom dataset",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Fine-tune on formation energy data
  python run_finetuning.py \\
    --training-data training_data.csv \\
    --property-name formation_energy \\
    --base-model mattergen_base \\
    --epochs 100 \\
    --output-dir ./finetuned_formation_energy

  # Quick test with 2 epochs
  python run_finetuning.py \\
    --training-data test_data.csv \\
    --property-name band_gap \\
    --epochs 2 \\
    --output-dir ./test_finetune
        """
    )
    parser.add_argument(
        "--training-data",
        type=Path,
        required=True,
        help="Path to training data CSV file (output from prepare_training_data.py)"
    )
    parser.add_argument(
        "--property-name",
        required=True,
        help="Name of the property to condition on (must match column in CSV)"
    )
    parser.add_argument(
        "--base-model",
        default="mattergen_base",
        choices=["mattergen_base", "mp_20_base", "dft_mag_density", "chemical_system"],
        help="Base model to start fine-tuning from (default: mattergen_base)"
    )
    parser.add_argument(
        "--epochs",
        type=int,
        default=100,
        help="Number of training epochs (default: 100)"
    )
    parser.add_argument(
        "--learning-rate",
        type=float,
        default=5e-6,
        help="Learning rate for adapter training (default: 5e-6)"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=32,
        help="Training batch size (default: 32)"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Output directory for checkpoints (default: ./finetuned_{property_name})"
    )
    
    args = parser.parse_args()
    
    # Validate training data exists
    if not args.training_data.exists():
        print(f"Error: Training data file not found: {args.training_data}", file=sys.stderr)
        sys.exit(1)
    
    # Run fine-tuning
    exit_code = run_finetuning(
        training_data_path=args.training_data,
        property_name=args.property_name,
        base_model=args.base_model,
        epochs=args.epochs,
        output_dir=args.output_dir,
        learning_rate=args.learning_rate,
        batch_size=args.batch_size
    )
    
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
