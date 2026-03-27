"""
ADiT (All-atom Diffusion Transformer) wrapper for structure generation.

Wraps the official AADT codebase for crystal and molecule generation
via latent diffusion with a VAE autoencoder and DiT denoiser.

Pretrained weights from: https://huggingface.co/chaitjo/all-atom-diffusion-transformer

Requirements:
    - Conda environment: adit-agent
    - AADT repo cloned and accessible (see conda-envs/adit-agent/README.md)
"""

import logging
import os
import json
from pathlib import Path
from typing import Dict, Any, Optional, List

import numpy as np
import torch

logger = logging.getLogger(__name__)

# Dataset index mapping used by ADiT
# 0 -> MP20 (periodic crystals), 1 -> QM9 (non-periodic molecules)
GENERATION_TYPE_TO_DATASET_IDX = {
    "crystals": 0,   # MP20
    "molecules": 1,  # QM9
}

# Default number-of-atoms distributions (from the training datasets)
# These are used to sample random structure sizes during generation.
# MP20 distribution (mode ~8-20 atoms, max ~200)
MP20_NUM_ATOMS_PROBS = None  # Will be loaded from checkpoint/data
# QM9 distribution (fixed at 9 heavy atoms + H, typically ~18-29 total)
QM9_NUM_ATOMS_PROBS = None

# HuggingFace repo for pretrained weights
HF_REPO_ID = "chaitjo/all-atom-diffusion-transformer"
HF_DIFFUSION_CKPT = "ldm.ckpt"
HF_VAE_CKPT = "vae.ckpt"


class ADiTWrapper:
    """
    ADiT wrapper for crystal and molecule generation.

    Uses a pretrained VAE + DiT model to generate novel structures
    via latent diffusion and flow matching.

    Args:
        device: Device to use ('auto', 'cpu', 'cuda').
        adit_repo_path: Path to the cloned AADT repository.
    """

    def __init__(
        self,
        device: str = "auto",
        adit_repo_path: Optional[str] = None,
    ):
        """
        Initialize the ADiT wrapper and download/load pretrained checkpoints.

        Args:
            device: Device to use ('auto', 'cpu', 'cuda').
            adit_repo_path: Path to the cloned AADT repository.
                           Auto-discovered from project siblings or PYTHONPATH.
        """
        import sys
        import importlib

        # Set device
        if device == "auto":
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device

        # Find the AADT repo path
        if adit_repo_path is None:
            # Try common locations
            project_root = os.environ.get(
                "PYTHONPATH", ""
            ).split(":")[0]
            # Look for the AADT repo as a sibling of the project root,
            # or in common locations relative to the project.
            project_dir = os.path.dirname(project_root) if project_root else ""
            candidates = [
                os.path.join(project_dir, "adit"),
                os.path.join(project_root, "adit"),
                os.path.join(os.path.expanduser("~"), "projects", "adit"),
            ]
            for c in candidates:
                if os.path.isdir(c):
                    adit_repo_path = os.path.abspath(c)
                    break
            if adit_repo_path is None:
                raise RuntimeError(
                    "AADT repository not found. Please clone it with: "
                    "git clone https://github.com/facebookresearch/all-atom-diffusion-transformer <path>/adit "
                )

        self.adit_repo_path = adit_repo_path
        logger.info(f"Using AADT repository at: {self.adit_repo_path}")

        # CRITICAL: Handle namespace collision between project src/ and AADT src/
        # Both the project root and AADT repo have a src/ directory.
        # We must ensure AADT's src/ is found first when importing AADT modules.
        # Strategy: put AADT repo at position 0 of sys.path and invalidate caches
        # so Python's module finder re-discovers the src namespace.
        if self.adit_repo_path in sys.path:
            sys.path.remove(self.adit_repo_path)
        sys.path.insert(0, self.adit_repo_path)

        # Remove any cached 'src' module so Python re-discovers it from the new path order
        modules_to_remove = [k for k in sys.modules if k == "src" or k.startswith("src.")]
        for mod_key in modules_to_remove:
            del sys.modules[mod_key]
        importlib.invalidate_caches()

        # Set PROJECT_ROOT env var required by rootutils / Hydra configs
        os.environ["PROJECT_ROOT"] = self.adit_repo_path

        # Download checkpoints from HuggingFace
        self._download_checkpoints()

        # Load the model
        self._load_model()

        self.is_loaded = True
        logger.info("ADiT model loaded successfully")


    def _download_checkpoints(self) -> None:
        """Download pretrained checkpoints from HuggingFace Hub."""
        from huggingface_hub import hf_hub_download

        ckpt_dir = os.path.join(self.adit_repo_path, "ckpts")
        os.makedirs(ckpt_dir, exist_ok=True)

        # Download diffusion checkpoint (ldm.ckpt at HF repo root)
        self.diffusion_ckpt_path = os.path.join(ckpt_dir, "ldm.ckpt")
        if not os.path.exists(self.diffusion_ckpt_path):
            logger.info("Downloading diffusion checkpoint from HuggingFace...")
            downloaded_path = hf_hub_download(
                repo_id=HF_REPO_ID,
                filename=HF_DIFFUSION_CKPT,
                local_dir=ckpt_dir,
            )
            self.diffusion_ckpt_path = downloaded_path
            logger.info(f"Downloaded diffusion checkpoint to: {self.diffusion_ckpt_path}")
        else:
            logger.info(f"Using cached diffusion checkpoint: {self.diffusion_ckpt_path}")

        # Download VAE checkpoint (vae.ckpt at HF repo root)
        self.vae_ckpt_path = os.path.join(ckpt_dir, "vae.ckpt")
        if not os.path.exists(self.vae_ckpt_path):
            logger.info("Downloading VAE checkpoint from HuggingFace...")
            downloaded_path = hf_hub_download(
                repo_id=HF_REPO_ID,
                filename=HF_VAE_CKPT,
                local_dir=ckpt_dir,
            )
            self.vae_ckpt_path = downloaded_path
            logger.info(f"Downloaded VAE checkpoint to: {self.vae_ckpt_path}")
        else:
            logger.info(f"Using cached VAE checkpoint: {self.vae_ckpt_path}")

    def _load_model(self) -> None:
        """Load the pretrained VAE + DiT model from checkpoints."""
        from src.models.vae_module import VariationalAutoencoderLitModule

        logger.info("Loading VAE checkpoint...")

        # Load VAE (autoencoder)
        self.autoencoder = VariationalAutoencoderLitModule.load_from_checkpoint(
            self.vae_ckpt_path, map_location=self.device
        )
        self.autoencoder.requires_grad_(False)
        self.autoencoder.eval()
        self.autoencoder.to(self.device)

        logger.info("Loading Diffusion (DiT) checkpoint...")

        # Load the diffusion checkpoint
        # The checkpoint stores denoiser and interpolant as pre-instantiated nn.Module
        # objects in hyper_parameters, while the trained weights are in state_dict.
        ckpt = torch.load(self.diffusion_ckpt_path, map_location="cpu", weights_only=False)
        hparams = ckpt.get("hyper_parameters", {})
        state_dict = ckpt.get("state_dict", {})

        # Extract pre-instantiated denoiser (DiT architecture)
        denoiser = hparams.get("denoiser")
        if denoiser is None:
            from src.models.denoisers.dit import DiT
            denoiser = DiT(d_x=8, d_model=768, nhead=12, num_layers=12, num_datasets=2)
        self.denoiser = denoiser

        # Load trained weights for denoiser from state_dict
        denoiser_state_dict = {
            k.replace("denoiser.", ""): v
            for k, v in state_dict.items()
            if k.startswith("denoiser.")
        }
        if denoiser_state_dict:
            self.denoiser.load_state_dict(denoiser_state_dict)
        self.denoiser.to(self.device)
        self.denoiser.eval()

        # Extract pre-instantiated interpolant (FlowMatchingInterpolant)
        interpolant = hparams.get("interpolant")
        if interpolant is None:
            from src.models.interpolants.flow_matching import FlowMatchingInterpolant
            interpolant = FlowMatchingInterpolant(
                min_t=1e-2, corrupt=True, num_timesteps=100,
                self_condition=True, self_condition_prob=0.5
            )
        self.interpolant = interpolant

        # Store sampling config from hparams
        self.sampling_cfg = hparams.get("sampling", {})
        self.conditioning_cfg = hparams.get("conditioning", {})

        # Build num_nodes_bincount from training data or use defaults
        self._build_num_nodes_distributions()

        logger.info("Model loaded and ready for generation")

    def _build_num_nodes_distributions(self) -> None:
        """
        Build distributions over number of atoms per structure for each dataset.
        These are used to sample random structure sizes during generation.
        """
        # Default distributions based on the training datasets:
        # MP20: materials have 1-200 atoms, peak around 8-20
        # QM9: molecules have ~5-29 atoms (including H)

        # Load from the training data if available
        data_dir = os.path.join(self.adit_repo_path, "data")

        self.num_nodes_bincount = {}
        self.spacegroups_bincount = {}

        # Try to load MP20 distribution
        mp20_path = os.path.join(data_dir, "mp_20", "processed")
        if os.path.isdir(mp20_path):
            logger.info("Loading MP20 atom count distribution from processed data...")
            self._load_distribution_from_data("mp20", mp20_path)
        else:
            # Use a reasonable default distribution for MP20
            # Based on the MP20 dataset: most structures have 4-80 atoms
            logger.info("Using default MP20 atom count distribution")
            probs = torch.zeros(201)
            for n in range(2, 201):
                # Log-normal-like distribution peaking around 12 atoms
                probs[n] = np.exp(-0.5 * ((np.log(n) - np.log(12)) / 0.8) ** 2) / n
            probs = probs / probs.sum()
            self.num_nodes_bincount["mp20"] = probs

        # For QM9: molecules typically have 5-29 atoms (with hydrogens)
        logger.info("Using default QM9 atom count distribution")
        probs = torch.zeros(30)
        for n in range(5, 30):
            # Roughly uniform with peak around 18
            probs[n] = np.exp(-0.5 * ((n - 18) / 4.0) ** 2)
        probs = probs / probs.sum()
        self.num_nodes_bincount["qm9"] = probs

        # No spacegroup conditioning by default
        self.spacegroups_bincount["mp20"] = None
        self.spacegroups_bincount["qm9"] = None

    def _load_distribution_from_data(self, dataset_name: str, data_path: str) -> None:
        """Load atom count distribution from processed PyG dataset files."""
        import glob
        # Try to load from processed .pt files
        pt_files = glob.glob(os.path.join(data_path, "*.pt"))
        if pt_files:
            data = torch.load(pt_files[0], map_location="cpu", weights_only=False)
            if hasattr(data, "num_atoms"):
                counts = torch.bincount(data.num_atoms)
                self.num_nodes_bincount[dataset_name] = counts.float() / counts.sum()
                return

        # Fallback: use the default
        probs = torch.zeros(201)
        for n in range(2, 201):
            probs[n] = np.exp(-0.5 * ((np.log(n) - np.log(12)) / 0.8) ** 2) / n
        probs = probs / probs.sum()
        self.num_nodes_bincount[dataset_name] = probs

    @torch.no_grad()
    def generate_structures(
        self,
        generation_type: str = "crystals",
        num_structures: int = 10,
        batch_size: int = 100,
        cfg_scale: float = 2.0,
        output_dir: str = "outputs",
    ) -> Dict[str, Any]:
        """
        Generate crystal or molecule structures using the pretrained ADiT model.

        Args:
            generation_type: Type of structures to generate ('crystals' or 'molecules').
            num_structures: Total number of structures to generate.
            batch_size: Batch size for generation. Larger batches are more GPU-efficient.
            cfg_scale: Classifier-free guidance scale. Higher values produce more
                      "typical" structures but less diverse.
            output_dir: Directory to save generated structure files.

        Returns:
            Dictionary with:
                - 'num_generated': Number of valid structures generated
                - 'output_dir': Path to output directory
                - 'structures': List of generated structure file paths
                - 'generation_type': Type of generation performed
                - 'metadata_path': Path to metadata JSON file
        """
        if generation_type not in GENERATION_TYPE_TO_DATASET_IDX:
            raise ValueError(
                f"Invalid generation_type: {generation_type}. "
                f"Must be one of: {list(GENERATION_TYPE_TO_DATASET_IDX.keys())}"
            )

        dataset_idx = GENERATION_TYPE_TO_DATASET_IDX[generation_type]
        dataset_name = "mp20" if generation_type == "crystals" else "qm9"

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        logger.info(
            f"Generating {num_structures} {generation_type} "
            f"(dataset={dataset_name}, cfg_scale={cfg_scale})..."
        )

        all_predictions = []
        structures_generated = 0

        for batch_start in range(0, num_structures, batch_size):
            current_batch_size = min(batch_size, num_structures - batch_start)

            # Sample random number of atoms from the training distribution
            num_nodes_bincount = self.num_nodes_bincount[dataset_name].to(self.device)
            sample_lengths = torch.multinomial(
                num_nodes_bincount.float(),
                current_batch_size,
                replacement=True,
            ).to(self.device)

            # Create dataset_idx tensor
            # NOTE: 0 -> null class within DiT, while 0 -> MP20 elsewhere, so +1
            dataset_idx_tensor = torch.full(
                (current_batch_size,), dataset_idx + 1,
                dtype=torch.int64, device=self.device
            )

            # No spacegroup conditioning
            spacegroup = torch.zeros(
                current_batch_size, dtype=torch.int64, device=self.device
            )

            # Create token mask
            max_tokens = max(sample_lengths).item()
            token_mask = torch.zeros(
                current_batch_size, max_tokens,
                dtype=torch.bool, device=self.device
            )
            for idx, length in enumerate(sample_lengths):
                token_mask[idx, :length] = True

            # Generate latent embeddings via flow matching
            samples = self.interpolant.sample_with_classifier_free_guidance(
                batch_size=current_batch_size,
                num_tokens=max_tokens,
                emb_dim=self.denoiser.d_x,
                model=self.denoiser,
                dataset_idx=dataset_idx_tensor,
                spacegroup=spacegroup,
                cfg_scale=cfg_scale,
                token_mask=token_mask,
            )

            # Get final samples and remove padding (convert to PyG format)
            x = samples["clean_traj"][-1][token_mask]

            batch = {
                "x": x,
                "num_atoms": sample_lengths,
                "batch": torch.repeat_interleave(
                    torch.arange(len(sample_lengths), device=self.device),
                    sample_lengths
                ),
                "token_idx": (
                    torch.cumsum(token_mask, dim=-1, dtype=torch.int64) - 1
                )[token_mask],
            }

            # Decode latents to atomic structures using frozen VAE decoder
            out = self.autoencoder.decode(batch)

            # Extract per-structure predictions
            start_idx = 0
            for idx_in_batch, num_atom in enumerate(sample_lengths.tolist()):
                atom_types = out["atom_types"].narrow(0, start_idx, num_atom).argmax(dim=1)
                atom_types[atom_types == 0] = 1  # atom type 0 -> 1 (H) to prevent crash

                pos = out["pos"].narrow(0, start_idx, num_atom) * 10.0  # nm to Angstrom
                frac_coords = out["frac_coords"].narrow(0, start_idx, num_atom)
                lengths = out["lengths"][idx_in_batch] * float(num_atom) ** (1 / 3)  # unscale
                angles = torch.rad2deg(out["angles"][idx_in_batch])

                pred = {
                    "atom_types": atom_types.detach().cpu().numpy(),
                    "pos": pos.detach().cpu().numpy(),
                    "frac_coords": frac_coords.detach().cpu().numpy(),
                    "lengths": lengths.detach().cpu().numpy(),
                    "angles": angles.detach().cpu().numpy(),
                    "sample_idx": batch_start + idx_in_batch,
                }
                all_predictions.append(pred)
                start_idx += num_atom

            structures_generated += current_batch_size
            logger.info(
                f"  Generated batch: {structures_generated}/{num_structures}"
            )

        # Convert predictions to structure files
        structure_paths = []
        if generation_type == "crystals":
            structure_paths = self._save_crystals(all_predictions, output_path)
        else:
            structure_paths = self._save_molecules(all_predictions, output_path)

        # Save metadata
        metadata = {
            "num_generated": len(structure_paths),
            "num_attempted": num_structures,
            "generation_type": generation_type,
            "dataset": dataset_name,
            "cfg_scale": cfg_scale,
            "batch_size": batch_size,
            "device": str(self.device),
        }
        metadata_path = output_path / "generation_metadata.json"
        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=2)

        logger.info(
            f"Generation complete: {len(structure_paths)}/{num_structures} "
            f"valid structures saved to {output_path}"
        )

        return {
            "num_generated": len(structure_paths),
            "output_dir": str(output_path),
            "structures": structure_paths,
            "generation_type": generation_type,
            "metadata_path": str(metadata_path),
        }

    def _save_crystals(
        self,
        predictions: List[Dict[str, np.ndarray]],
        output_path: Path,
    ) -> List[str]:
        """
        Convert crystal predictions to CIF files using pymatgen.

        Args:
            predictions: List of prediction dicts with atom_types, frac_coords, lengths, angles.
            output_path: Directory to save CIF files.

        Returns:
            List of paths to valid CIF files.
        """
        from pymatgen.core import Structure, Lattice

        saved_paths = []
        for pred in predictions:
            # Validate lattice angles
            angles = pred["angles"]
            if not (np.all(angles > 10) and np.all(angles < 170)):
                logger.warning(
                    f"Skipping crystal {pred['sample_idx']}: invalid angles {angles}"
                )
                continue

            lengths = pred["lengths"]
            if np.any(lengths <= 0):
                logger.warning(
                    f"Skipping crystal {pred['sample_idx']}: invalid lengths {lengths}"
                )
                continue

            atom_types = pred["atom_types"]
            frac_coords = pred["frac_coords"]

            lattice = Lattice.from_parameters(
                a=float(lengths[0]),
                b=float(lengths[1]),
                c=float(lengths[2]),
                alpha=float(angles[0]),
                beta=float(angles[1]),
                gamma=float(angles[2]),
            )

            structure = Structure(
                lattice=lattice,
                species=atom_types.tolist(),
                coords=frac_coords.tolist(),
                coords_are_cartesian=False,
            )

            cif_path = output_path / f"crystal_{pred['sample_idx']:04d}.cif"
            structure.to(filename=str(cif_path), fmt="cif")
            saved_paths.append(str(cif_path))

        return saved_paths

    def _save_molecules(
        self,
        predictions: List[Dict[str, np.ndarray]],
        output_path: Path,
    ) -> List[str]:
        """
        Convert molecule predictions to XYZ files.

        Args:
            predictions: List of prediction dicts with atom_types, pos.
            output_path: Directory to save XYZ files.

        Returns:
            List of paths to saved XYZ files.
        """
        from ase import Atoms
        from ase.io import write as ase_write

        saved_paths = []
        # Atomic number to element symbol mapping
        for pred in predictions:
            atom_types = pred["atom_types"]
            positions = pred["pos"]

            # Create ASE Atoms object (no periodicity for molecules)
            atoms = Atoms(
                numbers=atom_types.tolist(),
                positions=positions.tolist(),
                pbc=False,
            )

            xyz_path = output_path / f"molecule_{pred['sample_idx']:04d}.xyz"
            ase_write(str(xyz_path), atoms, format="xyz")
            saved_paths.append(str(xyz_path))

        return saved_paths
