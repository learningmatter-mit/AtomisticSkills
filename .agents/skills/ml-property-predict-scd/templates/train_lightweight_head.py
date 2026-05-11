import argparse
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import torch
import torch.nn.functional as F
from torch import nn
from torch_geometric.loader import DataLoader


DEFAULT_HF_PREFIX = "Ty-Perez/"
HEAD_MODES = ("scalar_head", "atom_emb_mlp", "mol_emb_mlp")
POOL_CHOICES = ("sum", "mean")
ACTIVATIONS = {
    "relu": nn.ReLU,
    "silu": nn.SiLU,
    "gelu": nn.GELU,
}


def parse_split(value):
    if value is None:
        return None
    text = str(value).strip().lower()
    if text in {"none", "null", ""}:
        return None
    if any(ch in text for ch in [".", "e"]):
        return float(text)
    return int(text)


def resolve_repo_root(user_value):
    candidates = []
    if user_value is not None:
        candidates.append(Path(user_value).expanduser())

    cwd = Path.cwd()
    this_file = Path(__file__).resolve()
    candidates.extend(
        [
            cwd,
            cwd / "SelfConditionedDenoisingAtoms",
            this_file.parents[5] / "SelfConditionedDenoisingAtoms",
            this_file.parents[4].parent / "SelfConditionedDenoisingAtoms",
        ]
    )

    for candidate in candidates:
        if (candidate / "train.py").exists() and (candidate / "models").exists():
            return candidate.resolve()

    raise FileNotFoundError(
        "Could not locate SelfConditionedDenoisingAtoms. Pass --repo-root explicitly."
    )


def bootstrap_repo(repo_root):
    repo_root = str(repo_root)
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)


def build_parser():
    parser = argparse.ArgumentParser(
        description="Train lightweight frozen-backbone heads on top of a pretrained SCD checkpoint."
    )
    parser.add_argument("--repo-root", default=None, help="Path to SelfConditionedDenoisingAtoms.")
    parser.add_argument("--model-name", default="ct-scd-pcq", help="Public checkpoint name.")
    parser.add_argument("--checkpoint-path", default=None, help="Local checkpoint path. Overrides --model-name.")
    parser.add_argument("--dataset", required=True, help="Dataset name exported by data/datasets/__init__.py.")
    parser.add_argument("--dataset-root", required=True, help="Dataset root path.")
    parser.add_argument("--dataset-arg", default=None, help="Optional dataset_arg such as a target property.")
    parser.add_argument("--head-mode", required=True, choices=HEAD_MODES)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--num-workers", type=int, default=4)
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--weight-decay", type=float, default=0.0)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--train-size", default=None)
    parser.add_argument("--val-size", default=0.1)
    parser.add_argument("--test-size", default=0.1)
    parser.add_argument("--predefined-splits", action="store_true")
    parser.add_argument("--standardize-targets", action="store_true")
    parser.add_argument("--allow-periodic", action="store_true")
    parser.add_argument("--noise-in-loader", action="store_true")
    parser.add_argument("--graph-cutoff", type=float, default=5.0)
    parser.add_argument("--neighbor-method", default="brute")
    parser.add_argument("--max-neighbors", type=int, default=32)
    parser.add_argument("--p-cell-repeat", type=float, default=0.0)
    parser.add_argument("--cell-repeat-iters", type=int, default=0)
    parser.add_argument("--rep-min-atoms", type=int, default=0)
    parser.add_argument("--device", default=None)
    parser.add_argument("--output-dir", default="lightweight_head_results")

    parser.add_argument(
        "--reset-head",
        action="store_true",
        help="Reset scalar_head before scalar_head-only training.",
    )
    parser.add_argument(
        "--set-head-agg",
        choices=POOL_CHOICES,
        default=None,
        help="Native scalar_head reduction for scalar_head mode.",
    )

    parser.add_argument(
        "--pool",
        choices=POOL_CHOICES,
        default="mean",
        help="Pooling for atom_emb_mlp mode.",
    )
    parser.add_argument(
        "--mlp-layers",
        type=int,
        choices=[1, 2],
        default=2,
        help="Number of layers for external MLP heads.",
    )
    parser.add_argument(
        "--hidden-dim",
        type=int,
        default=None,
        help="Hidden size for 2-layer external MLP heads. Defaults to emb_dim.",
    )
    parser.add_argument("--activation", choices=sorted(ACTIVATIONS.keys()), default="silu")
    return parser


def build_datamodule_config(args):
    return {
        "dataset": args.dataset,
        "dataset_root": args.dataset_root,
        "dataset_arg": args.dataset_arg,
        "log_dir": str(Path(args.output_dir).resolve()),
        "train_size": None if args.predefined_splits else parse_split(args.train_size),
        "val_size": None if args.predefined_splits else parse_split(args.val_size),
        "test_size": None if args.predefined_splits else parse_split(args.test_size),
        "batch_size": args.batch_size,
        "inference_batch_size": args.batch_size,
        "num_workers": args.num_workers,
        "seed": args.seed,
        "predefined_splits": args.predefined_splits,
        "prior_model": None,
        "standardize": False,
        "p_invert": 0.0,
        "torsion_angle_std": 0.0,
        "max_bonds_rotated": 0,
        "random_rotate": False,
        "center": True,
        "noise_in_loader": args.noise_in_loader,
        "graph_cutoff": args.graph_cutoff,
        "neighbor_method": args.neighbor_method,
        "max_neighbors": args.max_neighbors,
        "allow_periodic": args.allow_periodic,
        "p_cell_repeat": args.p_cell_repeat,
        "cell_repeat_iters": args.cell_repeat_iters,
        "rep_min_atoms": args.rep_min_atoms,
        "noise_scale": 0.0,
        "self_cond": False,
        "pretraining": False,
    }


def make_loader(dataset, batch_size, num_workers, shuffle):
    return DataLoader(
        dataset=dataset,
        batch_size=batch_size,
        shuffle=shuffle,
        num_workers=num_workers,
        pin_memory=torch.cuda.is_available(),
    )


def get_targets(batch):
    y = batch.y.float()
    return y.reshape(batch.num_graphs, -1)


def compute_target_stats(loader):
    ys = []
    for batch in loader:
        ys.append(get_targets(batch))
    stacked = torch.cat(ys, dim=0)
    mean = stacked.mean(dim=0)
    std = stacked.std(dim=0)
    std[std == 0] = 1.0
    return mean, std


def configure_model_graph_mode(model, allow_periodic, noise_in_loader):
    if allow_periodic:
        model.rep_model.legacy = False
    else:
        model.rep_model.legacy = not noise_in_loader


def freeze_all(model):
    for param in model.parameters():
        param.requires_grad = False


def unfreeze_module(module):
    for param in module.parameters():
        param.requires_grad = True


def reset_output_affine(model):
    if hasattr(model, "mean") and model.mean is not None:
        model.mean.data.zero_()
    if hasattr(model, "std") and model.std is not None:
        model.std.data.fill_(1)


def build_model_inputs(batch, use_graph_batch):
    inputs = {
        "z": batch.z,
        "pos": batch.pos,
        "batch": batch.batch,
    }
    if use_graph_batch:
        inputs["graph_batch"] = batch
    return inputs


def pool_atom_embeddings(atom_embs, batch_index, pool):
    num_graphs = int(batch_index.max().item() + 1)
    pooled = torch.zeros(
        num_graphs,
        atom_embs.size(-1),
        device=atom_embs.device,
        dtype=atom_embs.dtype,
    )
    pooled.index_add_(0, batch_index, atom_embs)

    if pool == "mean":
        counts = torch.bincount(batch_index, minlength=num_graphs).clamp(min=1).to(atom_embs.device)
        pooled = pooled / counts.unsqueeze(-1)

    return pooled


def build_mlp_head(input_dim, output_dim, args):
    if args.mlp_layers == 1:
        return nn.Linear(input_dim, output_dim)

    hidden_dim = args.hidden_dim or input_dim
    activation = ACTIVATIONS[args.activation]
    return nn.Sequential(
        nn.Linear(input_dim, hidden_dim),
        activation(),
        nn.Linear(hidden_dim, output_dim),
    )


def prepare_backbone(args, checkpoint_path, device, load_model):
    load_kwargs = {}
    if args.head_mode == "scalar_head":
        load_kwargs["reset_head"] = args.reset_head
        if args.set_head_agg is not None:
            load_kwargs["set_head_agg"] = args.set_head_agg

    backbone, _ema_model, _ckpt = load_model(checkpoint_path, device=device, **load_kwargs)
    backbone.denoise = False
    configure_model_graph_mode(backbone, args.allow_periodic, args.noise_in_loader)
    freeze_all(backbone)
    backbone.eval()

    if args.head_mode == "scalar_head":
        unfreeze_module(backbone.scalar_head)
        reset_output_affine(backbone)

    return backbone


def scalar_head_forward(backbone, batch, use_graph_batch):
    out = backbone(**build_model_inputs(batch, use_graph_batch))
    return out["y"].reshape(batch.num_graphs, -1)


def external_head_forward(backbone, head, batch, head_mode, pool, use_graph_batch):
    with torch.no_grad():
        out = backbone(
            **build_model_inputs(batch, use_graph_batch),
            return_atom_embs=(head_mode == "atom_emb_mlp"),
        )

        if head_mode == "atom_emb_mlp":
            features = pool_atom_embeddings(out["atom_embs"], batch.batch, pool)
        else:
            features = out["mol_emb"]

    return head(features)


def evaluate(backbone, head, loader, target_mean, target_std, device, args, use_graph_batch):
    backbone.eval()
    if args.head_mode == "scalar_head":
        backbone.scalar_head.eval()
    elif head is not None:
        head.eval()

    preds = []
    targets = []

    with torch.no_grad():
        for batch in loader:
            batch = batch.to(device)
            target = get_targets(batch)

            if args.head_mode == "scalar_head":
                pred = scalar_head_forward(backbone, batch, use_graph_batch)
            else:
                pred = external_head_forward(backbone, head, batch, args.head_mode, args.pool, use_graph_batch)

            if args.standardize_targets:
                pred = pred * target_std + target_mean

            preds.append(pred.detach().cpu())
            targets.append(target.detach().cpu())

    pred = torch.cat(preds, dim=0)
    target = torch.cat(targets, dim=0)
    mae = torch.mean(torch.abs(pred - target)).item()
    rmse = torch.sqrt(torch.mean((pred - target) ** 2)).item()
    return {"mae": mae, "rmse": rmse}


def train_scalar_head_epoch(backbone, loader, optimizer, target_mean, target_std, device, use_graph_batch, standardize_targets):
    backbone.eval()
    backbone.scalar_head.train()

    total_loss = 0.0
    total_graphs = 0

    for batch in loader:
        batch = batch.to(device)
        target = get_targets(batch)
        target_for_loss = target
        if standardize_targets:
            target_for_loss = (target - target_mean) / target_std

        pred = scalar_head_forward(backbone, batch, use_graph_batch)
        loss = F.mse_loss(pred, target_for_loss)

        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        optimizer.step()

        total_loss += loss.item() * batch.num_graphs
        total_graphs += batch.num_graphs

    return total_loss / max(total_graphs, 1)


def train_external_head_epoch(backbone, head, loader, optimizer, target_mean, target_std, device, args, use_graph_batch):
    backbone.eval()
    head.train()

    total_loss = 0.0
    total_graphs = 0

    for batch in loader:
        batch = batch.to(device)
        target = get_targets(batch)
        target_for_loss = target
        if args.standardize_targets:
            target_for_loss = (target - target_mean) / target_std

        pred = external_head_forward(backbone, head, batch, args.head_mode, args.pool, use_graph_batch)
        loss = F.mse_loss(pred, target_for_loss)

        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        optimizer.step()

        total_loss += loss.item() * batch.num_graphs
        total_graphs += batch.num_graphs

    return total_loss / max(total_graphs, 1)


def main():
    args = build_parser().parse_args()
    repo_root = resolve_repo_root(args.repo_root)
    bootstrap_repo(repo_root)

    from huggingface_hub import hf_hub_download
    from data.loaders import DataModule
    from models.model_helper import load_model

    torch.manual_seed(args.seed)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.checkpoint_path is None:
        checkpoint_path = hf_hub_download(
            repo_id=f"{DEFAULT_HF_PREFIX}{args.model_name}",
            filename="last.ckpt",
            cache_dir=str(output_dir / "hf_cache"),
        )
    else:
        checkpoint_path = args.checkpoint_path

    device = args.device or ("cuda" if torch.cuda.is_available() else "cpu")
    use_graph_batch = args.allow_periodic or args.noise_in_loader

    dm_config = build_datamodule_config(args)
    data = DataModule(SimpleNamespace(**dm_config))
    data.prepare_data()
    data.setup("fit")

    train_loader = make_loader(data.train_dataset, args.batch_size, args.num_workers, shuffle=True)
    val_loader = make_loader(data.val_dataset, args.batch_size, args.num_workers, shuffle=False)
    test_loader = make_loader(data.test_dataset, args.batch_size, args.num_workers, shuffle=False)

    first_batch = next(iter(train_loader)).to(device)
    out_dim = get_targets(first_batch).shape[-1]

    backbone = prepare_backbone(args, checkpoint_path, device, load_model)
    head = None
    if args.head_mode == "scalar_head":
        trainable = list(backbone.scalar_head.parameters())
    else:
        head = build_mlp_head(backbone.emb_dim, out_dim, args).to(device)
        trainable = list(head.parameters())

    optimizer = torch.optim.AdamW(trainable, lr=args.lr, weight_decay=args.weight_decay)

    target_mean = torch.zeros(out_dim, device=device)
    target_std = torch.ones(out_dim, device=device)
    if args.standardize_targets:
        mean_cpu, std_cpu = compute_target_stats(train_loader)
        target_mean = mean_cpu.to(device)
        target_std = std_cpu.to(device)

    best_val_mae = float("inf")
    best_metrics = None
    history = []

    for epoch in range(1, args.epochs + 1):
        if args.head_mode == "scalar_head":
            train_loss = train_scalar_head_epoch(
                backbone,
                train_loader,
                optimizer,
                target_mean,
                target_std,
                device,
                use_graph_batch,
                args.standardize_targets,
            )
        else:
            train_loss = train_external_head_epoch(
                backbone,
                head,
                train_loader,
                optimizer,
                target_mean,
                target_std,
                device,
                args,
                use_graph_batch,
            )

        val_metrics = evaluate(backbone, head, val_loader, target_mean, target_std, device, args, use_graph_batch)
        test_metrics = evaluate(backbone, head, test_loader, target_mean, target_std, device, args, use_graph_batch)

        epoch_record = {
            "epoch": epoch,
            "head_mode": args.head_mode,
            "train_mse": train_loss,
            "val_mae": val_metrics["mae"],
            "val_rmse": val_metrics["rmse"],
            "test_mae": test_metrics["mae"],
            "test_rmse": test_metrics["rmse"],
        }
        history.append(epoch_record)
        print(json.dumps(epoch_record))

        if val_metrics["mae"] < best_val_mae:
            best_val_mae = val_metrics["mae"]
            best_metrics = {
                "epoch": epoch,
                "head_mode": args.head_mode,
                "val": val_metrics,
                "test": test_metrics,
                "train_mse": train_loss,
            }
            payload = {
                "checkpoint_path": checkpoint_path,
                "head_mode": args.head_mode,
                "emb_dim": backbone.emb_dim,
                "out_dim": out_dim,
                "standardize_targets": args.standardize_targets,
                "target_mean": target_mean.detach().cpu(),
                "target_std": target_std.detach().cpu(),
                "args": vars(args),
            }
            if args.head_mode == "scalar_head":
                payload["scalar_head_state_dict"] = backbone.scalar_head.state_dict()
            else:
                payload["head_state_dict"] = head.state_dict()
            torch.save(payload, output_dir / "best_lightweight_head.pt")

    (output_dir / "metrics.json").write_text(json.dumps({"best": best_metrics, "history": history}, indent=2))
    print(f"Saved best lightweight head checkpoint to {output_dir / 'best_lightweight_head.pt'}")
    print(f"Saved metrics to {output_dir / 'metrics.json'}")


if __name__ == "__main__":
    main()
