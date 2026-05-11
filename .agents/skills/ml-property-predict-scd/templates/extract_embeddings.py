import argparse
import sys
from pathlib import Path

import torch


DEFAULT_HF_PREFIX = "Ty-Perez/"


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


def build_model_inputs(batch, use_graph_batch):
    inputs = {
        "z": batch.z,
        "pos": batch.pos,
        "batch": batch.batch,
    }
    if use_graph_batch:
        inputs["graph_batch"] = batch
    return inputs


class FrozenSCDEmbedder:
    def __init__(
        self,
        repo_root,
        model_name=None,
        checkpoint_path=None,
        allow_periodic=False,
        noise_in_loader=False,
        device=None,
    ):
        from huggingface_hub import hf_hub_download
        from models.model_helper import load_model

        self.repo_root = Path(repo_root)
        self.allow_periodic = allow_periodic
        self.noise_in_loader = noise_in_loader
        self.use_graph_batch = allow_periodic or noise_in_loader
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")

        if checkpoint_path is None:
            if model_name is None:
                raise ValueError("Provide either model_name or checkpoint_path.")
            checkpoint_path = hf_hub_download(
                repo_id=f"{DEFAULT_HF_PREFIX}{model_name}",
                filename="last.ckpt",
                cache_dir=str(self.repo_root / "experiments"),
            )

        self.checkpoint_path = checkpoint_path
        self.model, _ema_model, _ckpt = load_model(checkpoint_path, device=self.device)
        self.model.eval()
        self.model.denoise = False

        for param in self.model.parameters():
            param.requires_grad = False

        if self.allow_periodic:
            self.model.rep_model.legacy = False
        else:
            self.model.rep_model.legacy = not self.noise_in_loader

    def encode_batch(self, batch, return_atom_embs=False):
        batch = batch.to(self.device)
        with torch.no_grad():
            out = self.model(
                **build_model_inputs(batch, self.use_graph_batch),
                return_atom_embs=return_atom_embs,
            )

        payload = {"mol_emb": out["mol_emb"].detach().cpu()}
        if return_atom_embs:
            payload["atom_embs"] = out["atom_embs"].detach().cpu()
        return payload


def build_parser():
    parser = argparse.ArgumentParser(description="Load a frozen SCD checkpoint for live embedding inference.")
    parser.add_argument("--repo-root", default=None, help="Path to SelfConditionedDenoisingAtoms.")
    parser.add_argument("--model-name", default="ct-scd-pcq", help="Public checkpoint name.")
    parser.add_argument("--checkpoint-path", default=None, help="Local checkpoint path. Overrides --model-name.")
    parser.add_argument("--allow-periodic", action="store_true", help="Use periodic/materials graph mode.")
    parser.add_argument("--noise-in-loader", action="store_true", help="Use loader-side graph mode. Required for periodic data.")
    parser.add_argument("--device", default=None, help="Torch device, default auto.")
    return parser


def main():
    args = build_parser().parse_args()
    repo_root = resolve_repo_root(args.repo_root)
    bootstrap_repo(repo_root)

    embedder = FrozenSCDEmbedder(
        repo_root=repo_root,
        model_name=args.model_name,
        checkpoint_path=args.checkpoint_path,
        allow_periodic=args.allow_periodic,
        noise_in_loader=args.noise_in_loader,
        device=args.device,
    )

    print(f"Loaded frozen checkpoint from {embedder.checkpoint_path}")
    print(f"emb_dim={embedder.model.emb_dim}")
    print("Import FrozenSCDEmbedder from this template and call encode_batch(batch) inside your downstream ML pipeline.")


if __name__ == "__main__":
    main()
