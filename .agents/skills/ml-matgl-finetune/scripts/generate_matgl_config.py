#!/usr/bin/env python
"""
Generate a training configuration JSON for MatGL.

Usage:
    python generate_matgl_config.py --train-data path/to/train_data.json --model CHGNet-MatPES-PBE-2025.2.10-2.7M-PES \
        --epochs 200 --lr 1e-2 --batch-size 2 --output-dir ./fine_tuning
"""

import argparse
import json
import os
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(description="Generate a finetune_config.json for MatGL")
    parser.add_argument("--train-data", required=True, help="Path to JSON file containing training data")
    parser.add_argument("--val-data", help="Path to JSON file containing validation data (optional)")
    parser.add_argument("--model", default="CHGNet-MatPES-PBE-2025.2.10-2.7M-PES", help="Base model name or path to a checkpoint")
    
    # MACE Default hyperparameters as requested
    parser.add_argument("--epochs", type=int, default=200, help="Number of training epochs")
    parser.add_argument("--lr", type=float, default=1e-2, help="Learning rate")
    parser.add_argument("--batch-size", type=int, default=2, help="Batch size")
    parser.add_argument("--patience", type=int, default=20, help="Early stopping patience (epochs)")
    parser.add_argument("--scheduler", default="ReduceLROnPlateau", choices=["CosineAnnealingLR", "ReduceLROnPlateau"], help="Learning rate scheduler")
    
    # Other parameters
    parser.add_argument("--freeze-backbone", action="store_true", help="Freeze model backbone and only train readout heads")
    parser.add_argument("--reinit-head", action="store_true", help="Re-initialize readout head weights")
    parser.add_argument("--energy-weight", type=float, default=1.0, help="Loss weight for energy")
    parser.add_argument("--force-weight", type=float, default=10.0, help="Loss weight for forces")
    parser.add_argument("--stress-weight", type=float, default=1.0, help="Loss weight for stress (if present)")
    parser.add_argument("--device", default="auto", help="Device to use (auto, cuda, cpu)")
    parser.add_argument("--output-dir", default="./fine_tuning", help="Directory to save the configuration")

    args = parser.parse_args()

    output_path = Path(args.output_dir).absolute()
    output_path.mkdir(parents=True, exist_ok=True)

    config = {
        "train_data": str(Path(args.train_data).absolute()),
        "val_data": str(Path(args.val_data).absolute()) if args.val_data else None,
        "model": args.model,
        "epochs": args.epochs,
        "lr": args.lr,
        "batch_size": args.batch_size,
        "patience": args.patience,
        "scheduler": args.scheduler,
        "freeze_backbone": args.freeze_backbone,
        "reinit_head": args.reinit_head,
        "energy_weight": args.energy_weight,
        "force_weight": args.force_weight,
        "stress_weight": args.stress_weight,
        "device": args.device,
        "output_dir": str(output_path)
    }

    config_file = output_path / "finetune_config.json"
    with open(config_file, "w") as f:
        json.dump(config, f, indent=4)

    print("\n=======================================================")
    print(f"Configuration written to: {config_file}")
    print("=======================================================\n")
    print("To start training, simply run:")
    print(f"  conda activate matgl-agent")
    print(f"  python train_matgl.py --config {config_file.absolute()}")

if __name__ == "__main__":
    main()
