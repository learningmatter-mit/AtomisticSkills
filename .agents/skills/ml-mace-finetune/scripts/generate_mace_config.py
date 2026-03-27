#!/usr/bin/env python
"""
Generate a finetune_config.yaml for MACE training.

Usage:
    python generate_mace_config.py --train-file path/to/train.xyz --model MACE-MP-small \\
        --epochs 100 --lr 1e-4 --output-dir ./fine_tuning
"""

import argparse
import os
from pathlib import Path
import yaml
from ase.io import read

def main():
    parser = argparse.ArgumentParser(description="Generate a finetune_config.yaml for MACE")
    parser.add_argument("--train-file", required=True, help="Path to train.xyz")
    parser.add_argument("--valid-file", default=None, help="Path to valid.xyz")
    parser.add_argument("--model", default="MACE-MP-small", help="Base model name or path to a checkpoint")
    parser.add_argument("--epochs", type=int, default=200, help="Number of training epochs")
    parser.add_argument("--lr", type=float, default=0.01, help="Peak learning rate for training")
    parser.add_argument("--batch-size", type=int, default=2, help="Batch size for training")
    parser.add_argument("--output-dir", default="./fine_tuning", help="Directory to save the configuration")
    parser.add_argument("--device", default="cuda", help="Device to use for training (cuda or cpu). Defaults to cuda.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--freeze-backbone", action="store_true", help="Sets MACE to freeze its layers up to the readout")
    parser.add_argument("--reinit-head", action="store_true", help="Discard pre-trained readout and initialize a new one")
    parser.add_argument("--multiheads", action="store_true", help="Add a new head for fine-tuning while preserving existing ones")
    parser.add_argument("--energy-weight", type=float, default=1.0, help="Loss weight for energy")
    parser.add_argument("--forces-weight", type=float, default=10.0, help="Loss weight for forces")
    parser.add_argument("--stress-weight", type=float, default=1.0, help="Loss weight for stress (automatically used if stress data is present)")
    parser.add_argument("--patience", type=int, default=20, help="Patience for early stopping")
    parser.add_argument("--scheduler", type=str, default="ReduceLROnPlateau", help="Learning rate scheduler")
    parser.add_argument("--scheduler-patience", type=int, default=5, help="Patience for ReduceLROnPlateau scheduler")
    parser.add_argument("--lr-scheduler-gamma", type=float, default=0.9, help="Gamma parameter for learning rate decay")

    args = parser.parse_args()

    output_path = Path(args.output_dir).absolute()
    output_path.mkdir(parents=True, exist_ok=True)
    checkpoints_dir = output_path / "checkpoints"
    results_dir = output_path / "results"
    log_dir = output_path / "logs"

    train_atoms = read(args.train_file, index=0)
    has_stress = 'REF_stress' in train_atoms.info

    # Model resolution logic
    model_name_upper = args.model.upper()
    if "MATPES-R2SCAN" in model_name_upper or "MATPES-r2SCAN" in model_name_upper:
        foundation_model_name = "mace-matpes-r2scan-0"
    elif "MATPES-PBE" in model_name_upper:
        foundation_model_name = "mace-matpes-pbe-0"
    elif "MPA" in model_name_upper:
        foundation_model_name = "mace-mpa-0"
    elif "OMAT" in model_name_upper:
        if "SMALL" in model_name_upper:
            foundation_model_name = "small-omat-0"
        else:
            foundation_model_name = "medium-omat-0"
    else:
        foundation_model_name = args.model if os.path.exists(args.model) else "small"

    e0s_dict = "average"
    atomic_numbers_str = None
    # Extract E0s directly from MACE internals if possible
    try:
        from mace.calculators import mace_mp
        foundation_calc = mace_mp(model=foundation_model_name, dispersion=False)
        if hasattr(foundation_calc, 'models') and len(foundation_calc.models) > 0:
            model = foundation_calc.models[0]
            if hasattr(model, "atomic_energies_fn"):
                atomic_energies_fn = model.atomic_energies_fn
                atomic_numbers = model.atomic_numbers
                e0s_tensor = atomic_energies_fn.atomic_energies
                temp_dict = {}
                for i, z in enumerate(atomic_numbers):
                    if e0s_tensor.dim() == 1:
                        val = e0s_tensor[i].item()
                    else:
                        val = e0s_tensor[0, i].item()
                    temp_dict[int(z.item())] = float(val)
                if temp_dict:
                    e0s_dict = str(temp_dict)
                    atomic_numbers_str = str(list(sorted(temp_dict.keys())))
    except Exception as e:
        print(f"Could not extract E0s automatically ({e}), defaulting to 'average'")

    config = {
        "name": f"{args.model.lower().replace('/', '_')}_fine_tuned",
        "train_file": str(Path(args.train_file).absolute()),
        "valid_file": str(Path(args.valid_file).absolute()) if args.valid_file else None,
        "max_num_epochs": args.epochs,
        "lr": args.lr,
        "batch_size": args.batch_size,
        "valid_batch_size": args.batch_size,
        "energy_key": "REF_energy",
        "forces_key": "REF_forces",
        "device": args.device,
        "seed": args.seed,
        "checkpoints_dir": str(checkpoints_dir),
        "results_dir": str(results_dir),
        "log_dir": str(log_dir),
        "plot": True,
        "plot_frequency": 1,
        "multiheads_finetuning": args.multiheads,
        "energy_weight": args.energy_weight,
        "forces_weight": args.forces_weight,
        "foundation_model": foundation_model_name,
        "E0s": e0s_dict,
        "patience": args.patience,
        "scheduler": args.scheduler,
        "scheduler_patience": args.scheduler_patience,
        "lr_scheduler_gamma": args.lr_scheduler_gamma,
    }

    if atomic_numbers_str:
        config["atomic_numbers"] = atomic_numbers_str

    if args.freeze_backbone:
        config["freeze"] = 2  # As per MACE conventions to freeze interaction blocks but keep readout free. If 2 fails, use "-1" or positive block count.

    if args.reinit_head:
        config["foundation_model_readout"] = False 
    else:
        config["foundation_model_readout"] = True

    if has_stress:
        config.update({
            "loss": "universal",
            "stress_weight": args.stress_weight,
            "stress_key": "REF_stress",
            "compute_stress": True,
            "error_table": "PerAtomRMSEstressvirials"
        })

    config_path = output_path / "finetune_config.yaml"
    with open(config_path, "w") as f:
        yaml.dump(config, f, sort_keys=False)

    print("\\n=======================================================")
    print(f"Configuration written to: {config_path}")
    print("=======================================================\\n")
    print("To start training, simply run:")
    print(f"  conda activate mace-agent")
    print(f"  mace_run_train --config {config_path.absolute()}")

if __name__ == "__main__":
    main()
