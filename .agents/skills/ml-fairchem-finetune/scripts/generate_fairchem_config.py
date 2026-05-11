#!/usr/bin/env python
"""
Generate a configuration YAML for Fairchem fine-tuning.

Usage:
    python generate_fairchem_config.py --data-metadata path/to/dataset_metadata.json \
        --model uma-s-1p1 --epochs 200 --lr 1e-2 --batch-size 2 --output-dir ./finetune_dir
"""

import argparse
import json
import logging
import os
import shutil
import sys
from pathlib import Path
from typing import Dict, Any, List

import yaml

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

def _create_finetune_yaml(configs_dir, train_lmdb_path, val_lmdb_path, force_rms, linref_coeff,
                          output_dir, dataset_name, regression_tasks, base_model_name, args):
    """Generate finetune YAML configs from bundled templates."""
    output_dir = Path(output_dir)
    output_yaml_path = output_dir / "uma_sm_finetune_template.yaml"
    yaml_config_path = Path(output_yaml_path)
    
    # Also need to copy the 'data' directory if it exists, because hydra searches for it.
    src_data_dir = configs_dir / "data"
    dst_data_dir = yaml_config_path.parent / "data"
    if src_data_dir.exists():
        if not dst_data_dir.exists():
            shutil.copytree(src_data_dir, dst_data_dir)
            
    # Determine the data task YAML file based on regression_tasks
    data_yaml_dir = Path("data")
    regression_label_to_yaml = {
        "e": data_yaml_dir / "uma_conserving_data_task_energy.yaml",
        "ef": data_yaml_dir / "uma_conserving_data_task_energy_force.yaml",
        "efs": data_yaml_dir / "uma_conserving_data_task_energy_force_stress.yaml",
    }
    data_task_yaml_name = regression_label_to_yaml[regression_tasks].name
    
    # Load the data task template and save it to the output directory's data folder
    data_task_template_path = configs_dir / data_yaml_dir / data_task_yaml_name
    with open(data_task_template_path) as f:
        template = yaml.safe_load(f)
    
    template["dataset_name"] = dataset_name
    template["normalizer_rmsd"] = force_rms
    template["elem_refs"] = linref_coeff
    template["train_dataset"]["splits"]["train"]["src"] = train_lmdb_path
    template["val_dataset"]["splits"]["val"]["src"] = val_lmdb_path
    
    (output_dir / data_yaml_dir).mkdir(parents=True, exist_ok=True)
    with open(output_dir / regression_label_to_yaml[regression_tasks], "w") as f:
        yaml.dump(template, f, default_flow_style=False, sort_keys=False)
    
    # Use text replacement for `defaults` to avoid pyyaml mangling hydra's special syntax
    uma_yaml = configs_dir / "uma_sm_finetune_template.yaml"
    with open(uma_yaml, 'r') as f:
        template_text = f.read()

    data_cfg_name = data_task_yaml_name.replace(".yaml", "")
    template_text = template_text.replace("- data: ??", f"- data: {data_cfg_name}")
    
    template_ft = yaml.safe_load(template_text)
    
    template_ft["base_model_name"] = base_model_name
    template_ft["epochs"] = args.epochs
    template_ft["lr"] = args.lr
    template_ft["batch_size"] = args.batch_size
    template_ft["weight_decay"] = args.weight_decay
    template_ft["evaluate_every_n_steps"] = args.evaluate_every_n_steps
    template_ft["checkpoint_every_n_steps"] = args.checkpoint_every_n_steps
    
    scheduler_cfg = template_ft["runner"]["train_eval_unit"]["cosine_lr_scheduler_fn"]
    scheduler_cfg["warmup_factor"] = args.warmup_factor
    scheduler_cfg["warmup_epochs"] = args.warmup_epochs
    scheduler_cfg["lr_min_factor"] = args.lr_min_factor
    
    template_ft["runner"]["train_eval_unit"]["clip_grad_norm"] = args.clip_grad_norm
    template_ft["runner"]["train_eval_unit"]["ema_decay"] = args.ema_decay
    
    if args.freeze_backbone:
        helper_path = output_dir / "_freeze_backbone_helper.py"
        helper_code = (
            "import torch\n"
            "from fairchem.core.units.mlip_unit.mlip_unit import initialize_finetuning_model\n\n"
            "def initialize_finetuning_model_frozen(checkpoint_location, overrides=None, heads=None, strict=True):\n"
            "    model = initialize_finetuning_model(\n"
            "        checkpoint_location=checkpoint_location, overrides=overrides, heads=heads, strict=strict\n"
            "    )\n"
            "    for param in model.backbone.parameters():\n"
            "        param.requires_grad = False\n"
            "    return model\n"
        )
        with open(helper_path, "w") as f:
            f.write(helper_code)
        
        model_cfg = template_ft["runner"]["train_eval_unit"]["model"]
        model_cfg["_target_"] = "_freeze_backbone_helper.initialize_finetuning_model_frozen"
        logging.info("freeze_backbone=True: backbone params will be frozen")
    
    template_ft["train_dataloader"]["num_workers"] = 0
    template_ft["eval_dataloader"]["num_workers"] = 0
    
    if "logger" in template_ft.get("job", {}):
        template_ft["job"]["logger"] = {
            "_target_": "fairchem.core.common.logger.TensorboardLogger",
            "_partial_": True
        }
    
    template_ft["train_dataset"]["dataset_configs"][dataset_name] = template_ft["train_dataset"]["dataset_configs"].pop("DATASET_NAME")
    template_ft["val_dataset"]["dataset_configs"][dataset_name] = template_ft["val_dataset"]["dataset_configs"].pop("DATASET_NAME")
    
    final_yaml_path = output_dir / "uma_sm_finetune_template.yaml"
    with open(final_yaml_path, "w") as f:
        yaml.dump(template_ft, f, default_flow_style=False, sort_keys=False)
    
    run_script_path = output_dir / "run_fairchem_finetuning.py"
    run_code = f"""#!/usr/bin/env python
import sys
import logging
from pathlib import Path
import hydra

# Fairchem imports
from fairchem.core._cli import get_hydra_config_from_yaml

def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    
    config_path = "{final_yaml_path.name}"
    run_dir = "{run_dir.absolute()}"
    timestamp_id = "{timestamp_id}"
    
    overrides = [f"job.run_dir={{run_dir}}", f"+job.timestamp_id={{timestamp_id}}"]
    
    logging.info(f"Loading YAML config: {{config_path}}")
    cfg = get_hydra_config_from_yaml(config_path, overrides)
    
    logging.info("Instantiating runner...")
    runner = hydra.utils.instantiate(cfg.runner, _recursive_=False)
    
    # Force an initial validation (Epoch 0) BEFORE any training steps occur
    logging.info("Executing initial zero-shot performance evaluation (Epoch 0)...")
    runner.evaluate()
    
    logging.info("Starting fine-tuning...")
    runner.train()

if __name__ == "__main__":
    main()
"""
    with open(run_script_path, "w") as f:
        f.write(run_code)
        
    return final_yaml_path, run_script_path

def main():
    parser = argparse.ArgumentParser(description="Generate fairchem training config.")
    parser.add_argument("--data-metadata", required=True, help="Path to dataset_metadata.json generated by prepare_fairchem_data.py")
    
    parser.add_argument("--model", default="uma-s-1p1", help="Base model name or path to checkpoint")
    parser.add_argument("--task-name", default="omat", help="Task name ('omat', 'omol', etc)")
    
    parser.add_argument("--epochs", type=int, default=200, help="Number of training epochs")
    parser.add_argument("--lr", type=float, default=1e-2, help="Peak learning rate")
    parser.add_argument("--batch-size", type=int, default=2, help="Batch size")
    parser.add_argument("--freeze-backbone", action="store_true", help="Freeze backbone parameters")
    
    parser.add_argument("--weight-decay", type=float, default=1e-3)
    parser.add_argument("--warmup-factor", type=float, default=0.2)
    parser.add_argument("--warmup-epochs", type=float, default=0.01)
    parser.add_argument("--lr-min-factor", type=float, default=0.01)
    parser.add_argument("--clip-grad-norm", type=float, default=100.0)
    parser.add_argument("--evaluate-every-n-steps", type=int, default=100)
    parser.add_argument("--checkpoint-every-n-steps", type=int, default=1000)
    parser.add_argument("--ema-decay", type=float, default=0.999)
    parser.add_argument("--output-dir", default="./fairchem_finetuning", help="Directory to save the configuration")

    args = parser.parse_args()

    logging.info(f"Loading dataset metadata from {args.data_metadata}...")
    with open(args.data_metadata, 'r') as f:
        metadata = json.load(f)

    save_dir = Path(args.output_dir).absolute()
    save_dir.mkdir(parents=True, exist_ok=True)

    repo_root = Path(__file__).resolve().parents[4]
    config_dir = repo_root / "src" / "utils" / "mlips" / "fairchem" / "finetune_configs"
    if not config_dir.exists():
        logging.error(f"Cannot find Fairchem config templates at {config_dir}. Check repository structure.")
        sys.exit(1)
        
    yaml_config_path, run_script_path = _create_finetune_yaml(
        configs_dir=config_dir,
        train_lmdb_path=metadata["train_lmdb_path"],
        val_lmdb_path=metadata["val_lmdb_path"],
        force_rms=metadata["force_rms"],
        linref_coeff=metadata["linref_coeff"],
        output_dir=save_dir,
        dataset_name=args.task_name,
        regression_tasks=metadata["regression_tasks"],
        base_model_name=args.model,
        args=args
    )
    
    print("\\n=======================================================")
    print("Configuration and Run Script successfully generated!")
    print(f"Configuration written to: {yaml_config_path}")
    print(f"Runner script written to: {run_script_path}")
    print("=======================================================\\n")
    print("To evaluate zero-shot performance and then start training, run:")
    print(f"  conda activate fairchem-agent")
    print(f"  export PYTHONPATH={save_dir.absolute()}:$PYTHONPATH")
    print(f"  cd {save_dir.absolute()}")
    print(f"  python {run_script_path.name} | tee fairchem_cli_output.log")

    # Save input configs for reproducibility
    from src.utils.config_utils import save_skill_inputs
    save_skill_inputs(args, args.output_dir)

if __name__ == "__main__":
    main()
