import argparse
import os
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path

DEFAULT_CONDA_ENV = "scd-agent"


def resolve_repo_root(user_value=None):
    candidates = []
    if user_value is not None:
        candidates.append(Path(user_value).expanduser())

    cwd = Path.cwd()
    this_file = Path(__file__).resolve()
    candidates.extend(
        [
            cwd,
            cwd / "SelfConditionedDenoisingAtoms",
            this_file.parents[6] / "SelfConditionedDenoisingAtoms",
            this_file.parents[5].parent / "SelfConditionedDenoisingAtoms",
        ]
    )

    for candidate in candidates:
        if (candidate / "train.py").exists() and (candidate / "configs").exists():
            return candidate.resolve()

    raise FileNotFoundError(
        "Could not locate SelfConditionedDenoisingAtoms. Pass --repo-root explicitly."
    )


def resolve_config_path(repo_root, config_value):
    config_path = Path(config_value)
    if not config_path.is_absolute():
        config_path = repo_root / config_path

    if not config_path.exists():
        raise FileNotFoundError(f"Could not find config file: {config_path}")

    if config_path.is_relative_to(repo_root):
        return str(config_path.relative_to(repo_root))
    return str(config_path)


def build_parser():
    parser = argparse.ArgumentParser(
        description="Run the CT-SCD Matbench MBgap finetuning example with the ct-scd-amp checkpoint."
    )
    parser.add_argument("--repo-root", default=None, help="Path to SelfConditionedDenoisingAtoms.")
    parser.add_argument("--config", default="configs/finetune_matbench.yaml", help="Run config relative to the SCD repo.")
    parser.add_argument("--dataset-class", default="MBgap", help="Dataset class passed to --dataset.")
    parser.add_argument("--fold", type=int, default=0, help="Matbench fold index passed through --dataset-arg.")
    parser.add_argument("--checkpoint", default="ct-scd-amp", help="Checkpoint name passed to --load-hf.")
    parser.add_argument("--job-id", default=None, help="Optional explicit job id.")
    parser.add_argument(
        "--conda-env",
        default=os.environ.get("SCD_EXAMPLE_CONDA_ENV", DEFAULT_CONDA_ENV),
        help="Conda environment used to run SelfConditionedDenoisingAtoms.",
    )
    parser.add_argument(
        "--wandb-mode",
        choices=("online", "offline", "disabled"),
        default=os.environ.get("SCD_EXAMPLE_WANDB_MODE"),
        help="Optional WANDB_MODE override passed to the training subprocess.",
    )
    parser.add_argument(
        "--cuda-visible-devices",
        default=os.environ.get("CUDA_VISIBLE_DEVICES"),
        help=(
            "Physical GPU ids to expose to the run, for example '0' or '1,2'. "
            "Use a single id by default when a free GPU is preferred."
        ),
    )
    parser.add_argument(
        "--use-all-visible-gpus",
        action="store_true",
        help="Train on every GPU visible through CUDA_VISIBLE_DEVICES instead of only logical GPU 0.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print the resolved training command without launching it.")
    parser.add_argument("--full-run", action="store_true", help="Run the full upstream schedule instead of a smoke test.")
    parser.add_argument("--num-steps", type=int, default=100, help="Smoke-test max steps when --full-run is not used.")
    parser.add_argument("--val-interval", type=int, default=1, help="Validation interval for smoke tests.")
    return parser


def maybe_restart_in_conda_env(target_env):
    current_env = os.environ.get("CONDA_DEFAULT_ENV", "")
    if current_env == target_env:
        return
    print(f"Restarting CT-SCD_matbench example in {target_env} environment...", flush=True)
    subprocess.run(["conda", "run", "-n", target_env, "python", __file__, *sys.argv[1:]], check=True)
    raise SystemExit(0)


def ensure_runtime_env(args):
    env = os.environ.copy()
    if args.wandb_mode:
        env["WANDB_MODE"] = args.wandb_mode
    if args.cuda_visible_devices:
        env["CUDA_VISIBLE_DEVICES"] = args.cuda_visible_devices

    if "MPLCONFIGDIR" not in env:
        default_mpl_dir = Path.home() / ".config" / "matplotlib"
        try:
            default_mpl_dir.mkdir(parents=True, exist_ok=True)
            if not os.access(default_mpl_dir, os.W_OK):
                raise OSError
        except OSError:
            env["MPLCONFIGDIR"] = tempfile.mkdtemp(prefix="mplconfig-", dir="/tmp")
    return env


def apply_runtime_env_locally(runtime_env):
    for key in ("CUDA_VISIBLE_DEVICES", "WANDB_MODE", "MPLCONFIGDIR"):
        if key in runtime_env:
            os.environ[key] = runtime_env[key]


def require_cuda_for_training():
    import torch

    if torch.cuda.is_available():
        return

    raise RuntimeError(
        "No CUDA GPUs are available in the active scd-agent environment. "
        "The upstream SelfConditionedDenoisingAtoms train.py entrypoint hard-codes "
        "GPU training, so use --dry-run on CPU-only hosts or rerun this example on a CUDA machine."
    )


def build_device_args(args):
    import torch

    if not args.use_all_visible_gpus:
        return ["--use-devices", "0"], 1

    if args.dry_run and args.cuda_visible_devices:
        visible_count = len([x for x in args.cuda_visible_devices.split(",") if x.strip()])
        logical_ids = [str(i) for i in range(visible_count)]
        return ["--use-devices", *logical_ids], visible_count

    visible_count = torch.cuda.device_count()
    if visible_count < 1:
        raise RuntimeError("No CUDA GPUs are visible after applying CUDA_VISIBLE_DEVICES.")
    logical_ids = [str(i) for i in range(visible_count)]
    return ["--use-devices", *logical_ids], visible_count


def main():
    args = build_parser().parse_args()
    maybe_restart_in_conda_env(args.conda_env)
    runtime_env = ensure_runtime_env(args)
    apply_runtime_env_locally(runtime_env)

    repo_root = resolve_repo_root(args.repo_root)
    config_path = resolve_config_path(repo_root, args.config)

    job_id = args.job_id
    if job_id is None:
        job_id = f"CT-SCD_matbench_{args.dataset_class}_fold{args.fold}"
        if not args.full_run:
            job_id += "_smoke"

    cmd = [
        "python",
        "train.py",
        "--conf",
        config_path,
        "--load-hf",
        args.checkpoint,
        "--job-id",
        job_id,
        "--dataset",
        args.dataset_class,
        "--dataset-arg",
        str(args.fold),
    ]

    if not args.full_run:
        cmd.extend(["--num-steps", str(args.num_steps), "--val-interval", str(args.val_interval)])

    device_args, visible_count = build_device_args(args)
    cmd.extend(device_args)

    print(f"Using conda environment: {args.conda_env}")
    print("Running CT-SCD Matbench command from", repo_root)
    print(shlex.join(cmd))
    if args.wandb_mode:
        print(f"WANDB_MODE={args.wandb_mode}")
    if runtime_env.get("CUDA_VISIBLE_DEVICES"):
        print(f"CUDA_VISIBLE_DEVICES={runtime_env['CUDA_VISIBLE_DEVICES']}")
    if args.use_all_visible_gpus:
        print(f"Using all {visible_count} visible GPU(s).")
    else:
        print("Using a single visible GPU: logical device 0.")
    if runtime_env.get("MPLCONFIGDIR"):
        print(f"MPLCONFIGDIR={runtime_env['MPLCONFIGDIR']}")
    print(
        "Note: this example assumes the StructureCloud-backed Matbench dataset wrapper is available "
        "in your SelfConditionedDenoisingAtoms checkout."
    )
    if args.dry_run:
        print("Dry run only; training command was not launched.")
        return

    require_cuda_for_training()
    subprocess.run(cmd, cwd=repo_root, env=runtime_env, check=True)


if __name__ == "__main__":
    main()
