"""
DiffCSP++ wrapper for crystal structure generation.

DiffCSP++ (ICLR 2024) generates crystal structures with space group constraints.
It supports two modes:
1. CSP (Crystal Structure Prediction): Given composition + space group + Wyckoff positions,
   predict the crystal structure (lattice + coordinates).
2. Ab initio generation: Generate structures unconditionally from the training distribution.

Reference: https://github.com/jiaor17/DiffCSP-PP
"""

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)

# DiffCSP++ repo location
DIFFCSP_REPO = Path("/home/bdeng/projects/DiffCSP-PP")
DIFFCSP_CHECKPOINTS = DIFFCSP_REPO / "checkpoints"

# Available pre-trained models
AVAILABLE_MODELS = {
    "mp_csp": "Materials Project CSP model (composition-constrained generation)",
    "mp_gen": "Materials Project ab initio generation model",
    "perov_csp": "Perovskite CSP model",
    "perov_gen": "Perovskite ab initio generation model",
    "carbon_gen": "Carbon ab initio generation model",
    "mpts_csp": "MPTS-52 CSP model",
}

# Chemical symbols table (same as DiffCSP++)
CHEMICAL_SYMBOLS = [
    'X',
    'H', 'He',
    'Li', 'Be', 'B', 'C', 'N', 'O', 'F', 'Ne',
    'Na', 'Mg', 'Al', 'Si', 'P', 'S', 'Cl', 'Ar',
    'K', 'Ca', 'Sc', 'Ti', 'V', 'Cr', 'Mn', 'Fe', 'Co', 'Ni', 'Cu', 'Zn',
    'Ga', 'Ge', 'As', 'Se', 'Br', 'Kr',
    'Rb', 'Sr', 'Y', 'Zr', 'Nb', 'Mo', 'Tc', 'Ru', 'Rh', 'Pd', 'Ag', 'Cd',
    'In', 'Sn', 'Sb', 'Te', 'I', 'Xe',
    'Cs', 'Ba', 'La', 'Ce', 'Pr', 'Nd', 'Pm', 'Sm', 'Eu', 'Gd', 'Tb', 'Dy',
    'Ho', 'Er', 'Tm', 'Yb', 'Lu',
    'Hf', 'Ta', 'W', 'Re', 'Os', 'Ir', 'Pt', 'Au', 'Hg', 'Tl', 'Pb', 'Bi',
    'Po', 'At', 'Rn',
    'Fr', 'Ra', 'Ac', 'Th', 'Pa', 'U', 'Np', 'Pu', 'Am', 'Cm', 'Bk',
    'Cf', 'Es', 'Fm', 'Md', 'No', 'Lr',
    'Rf', 'Db', 'Sg', 'Bh', 'Hs', 'Mt', 'Ds', 'Rg', 'Cn', 'Nh', 'Fl', 'Mc',
    'Lv', 'Ts', 'Og',
]

REV_CHEMICAL_SYMBOLS = {ch: i for i, ch in enumerate(CHEMICAL_SYMBOLS)}


def _ensure_diffcsp_importable() -> None:
    """Ensure DiffCSP++ repo is on the Python path."""
    repo_str = str(DIFFCSP_REPO)
    scripts_str = str(DIFFCSP_REPO / "scripts")
    if repo_str not in sys.path:
        sys.path.insert(0, repo_str)
    if scripts_str not in sys.path:
        sys.path.insert(0, scripts_str)
    # Set PROJECT_ROOT env var needed by Hydra configs
    os.environ.setdefault("PROJECT_ROOT", repo_str)


class DiffCSPWrapper:
    """DiffCSP++ wrapper for crystal structure generation.

    Attributes:
        model_name: Name of the loaded model checkpoint.
        device: Device the model is running on.
        model: The loaded PyTorch Lightning model.
    """

    def __init__(
        self,
        model_name: str = "mp_csp",
        device: str = "auto",
    ) -> None:
        """Initialize DiffCSP++ wrapper and load the model.

        Args:
            model_name: Name of the pre-trained model (e.g., 'mp_csp', 'mp_gen').
            device: Device to run on ('auto', 'cpu', 'cuda').
        """
        import torch

        _ensure_diffcsp_importable()

        self.model_name = model_name
        if device == "auto":
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device

        model_path = DIFFCSP_CHECKPOINTS / model_name
        if not model_path.exists():
            raise FileNotFoundError(
                f"Model checkpoint not found at {model_path}. "
                f"Available models: {list(AVAILABLE_MODELS.keys())}"
            )

        self.model, self._cfg = self._load_model(model_path)
        self.model.to(self.device)
        self.model.eval()
        self._is_gen_model = "gen" in model_name
        logger.info(
            "Loaded DiffCSP++ model: %s (type=%s, device=%s)",
            model_name,
            "ab_initio" if self._is_gen_model else "csp",
            self.device,
        )

    def _load_model(self, model_path: Path):
        """Load a DiffCSP++ model from checkpoint using Hydra config.

        Args:
            model_path: Path to the model directory containing hparams.yaml and *.ckpt.

        Returns:
            Tuple of (model, config).
        """
        import hydra
        import numpy as np
        import torch
        from hydra import initialize_config_dir
        from hydra.core.global_hydra import GlobalHydra
        from omegaconf import OmegaConf

        # Clear any existing Hydra state
        GlobalHydra.instance().clear()

        with initialize_config_dir(str(model_path)):
            from hydra import compose
            cfg = compose(config_name="hparams")

            model = hydra.utils.instantiate(
                cfg.model,
                optim=cfg.optim,
                data=cfg.data,
                logging=cfg.logging,
                _recursive_=False,
            )

            # Find the best checkpoint
            ckpts = list(model_path.glob("*.ckpt"))
            ckpt = None
            for ck in ckpts:
                if "last" in ck.name:
                    ckpt = str(ck)
                    break
            if ckpt is None and ckpts:
                ckpt_epochs = np.array([
                    int(ck.name.split("-")[0].split("=")[1])
                    for ck in ckpts
                    if "last" not in ck.name
                ])
                ckpt = str(ckpts[ckpt_epochs.argsort()[-1]])

            if ckpt is None:
                raise FileNotFoundError(f"No checkpoint found in {model_path}")

            hparams_file = str(model_path / "hparams.yaml")
            model = model.load_from_checkpoint(ckpt, hparams_file=hparams_file, strict=True)

            # Try to load scalers
            lattice_scaler_path = model_path / "lattice_scaler.pt"
            prop_scaler_path = model_path / "prop_scaler.pt"
            if lattice_scaler_path.exists():
                model.lattice_scaler = torch.load(lattice_scaler_path, weights_only=False)
            if prop_scaler_path.exists():
                model.scaler = torch.load(prop_scaler_path, weights_only=False)

        return model, cfg

    def generate_with_symmetry(
        self,
        spacegroup: int,
        wyckoff_letters: Union[str, List[str]],
        atom_types: Union[str, List[str]],
        num_samples: int = 1,
        step_lr: float = 1e-5,
        batch_size: int = 128,
        output_dir: str = "outputs",
    ) -> Dict[str, Any]:
        """Generate structures constrained by space group + Wyckoff positions + atom types.

        This provides exact composition control. For example, to generate Li2ZrCl6
        in space group 12 with Wyckoff positions 2a, 4g, 4h, 4i, 4i:
            spacegroup=12, wyckoff_letters=['2a','4g','4h','4i','4i'],
            atom_types=['Zr','Li','Cl','Cl','Cl']

        Args:
            spacegroup: Space group number (1-230).
            wyckoff_letters: Wyckoff position labels (e.g., ['2a', '2d', '4g'] or 'adg').
            atom_types: Element for each Wyckoff position (e.g., ['Mn', 'Li', 'O']).
            num_samples: Number of structure samples to generate for this composition.
            step_lr: Langevin step size for the corrector.
            batch_size: Batch size for parallel generation.
            output_dir: Directory to save CIF files and metadata.

        Returns:
            Dictionary with num_generated, output_dir, structures, metadata_path.
        """
        import torch
        from pymatgen.io.cif import CifWriter

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # Parse wyckoff_letters
        if isinstance(wyckoff_letters, str):
            if "," in wyckoff_letters:
                wyckoff_letters = wyckoff_letters.split(",")
            # else: single-char shorthand like 'adg' — each char is one letter
            else:
                wyckoff_letters = list(wyckoff_letters)

        # Parse atom_types
        if isinstance(atom_types, str):
            atom_types = atom_types.split(",")

        if len(wyckoff_letters) != len(atom_types):
            raise ValueError(
                f"Length mismatch: {len(wyckoff_letters)} Wyckoff positions vs "
                f"{len(atom_types)} atom types"
            )

        # Build data objects for all samples
        data_list = []
        for _ in range(num_samples):
            data = self._build_syminfo_data(spacegroup, wyckoff_letters, atom_types)
            data_list.append(data)

        structures = self._run_diffusion(data_list, step_lr, batch_size)

        # Save structures
        structure_paths = []
        for i, struct in enumerate(structures):
            if struct is not None:
                cif_path = output_path / f"structure_{i:04d}.cif"
                writer = CifWriter(struct)
                writer.write_file(str(cif_path))
                structure_paths.append(str(cif_path))

        # Save metadata
        metadata = {
            "model_name": self.model_name,
            "generation_mode": "symmetry_constrained",
            "spacegroup": spacegroup,
            "wyckoff_letters": wyckoff_letters,
            "atom_types": atom_types,
            "num_samples_requested": num_samples,
            "num_generated": len(structure_paths),
            "step_lr": step_lr,
        }
        metadata_path = output_path / "generation_metadata.json"
        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=2)

        return {
            "num_generated": len(structure_paths),
            "output_dir": str(output_path),
            "structures": structure_paths,
            "metadata_path": str(metadata_path),
        }

    def generate_from_json(
        self,
        json_specs: List[Dict[str, Any]],
        step_lr: float = 1e-5,
        batch_size: int = 128,
        output_dir: str = "outputs",
    ) -> Dict[str, Any]:
        """Generate structures from a list of symmetry specifications.

        Each spec is a dict with keys:
            - spacegroup_number: int
            - wyckoff_letters: list of str or str
            - atom_types: list of str (optional for gen models)

        Args:
            json_specs: List of symmetry specification dicts.
            step_lr: Langevin step size for the corrector.
            batch_size: Batch size for parallel generation.
            output_dir: Directory to save CIF files and metadata.

        Returns:
            Dictionary with num_generated, output_dir, structures, metadata_path.
        """
        from pymatgen.io.cif import CifWriter

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        data_list = []
        for spec in json_specs:
            sg = spec["spacegroup_number"]
            wl = spec["wyckoff_letters"]
            at = spec.get("atom_types", None)
            data = self._build_syminfo_data(sg, wl, at)
            data_list.append(data)

        structures = self._run_diffusion(data_list, step_lr, batch_size)

        structure_paths = []
        for i, struct in enumerate(structures):
            if struct is not None:
                cif_path = output_path / f"structure_{i:04d}.cif"
                writer = CifWriter(struct)
                writer.write_file(str(cif_path))
                structure_paths.append(str(cif_path))

        metadata = {
            "model_name": self.model_name,
            "generation_mode": "batch_symmetry",
            "num_specs": len(json_specs),
            "num_generated": len(structure_paths),
            "step_lr": step_lr,
        }
        metadata_path = output_path / "generation_metadata.json"
        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=2)

        return {
            "num_generated": len(structure_paths),
            "output_dir": str(output_path),
            "structures": structure_paths,
            "metadata_path": str(metadata_path),
        }

    def generate_unconditional(
        self,
        num_structures: int = 10,
        step_lr: float = 5e-6,
        batch_size: int = 128,
        output_dir: str = "outputs",
    ) -> Dict[str, Any]:
        """Generate structures unconditionally (ab initio generation).

        This requires a generation model (e.g., 'mp_gen', 'perov_gen').
        Structures are sampled from the training distribution.

        Args:
            num_structures: Number of structures to generate.
            step_lr: Langevin step size for the corrector.
            batch_size: Batch size for parallel generation.
            output_dir: Directory to save CIF files and metadata.

        Returns:
            Dictionary with num_generated, output_dir, structures, metadata_path.
        """
        if not self._is_gen_model:
            raise ValueError(
                f"Unconditional generation requires a 'gen' model. "
                f"Current model '{self.model_name}' is a CSP model. "
                f"Use 'mp_gen', 'perov_gen', or 'carbon_gen' instead."
            )

        import numpy as np
        import torch
        from torch.utils.data import Dataset
        from torch_geometric.data import DataLoader

        from pymatgen.io.cif import CifWriter

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # Load training data for sampling template structures
        from hydra.core.global_hydra import GlobalHydra
        import hydra

        GlobalHydra.instance().clear()

        model_path = DIFFCSP_CHECKPOINTS / self.model_name
        from hydra import initialize_config_dir, compose

        with initialize_config_dir(str(model_path)):
            cfg = compose(config_name="hparams")
            datamodule = hydra.utils.instantiate(
                cfg.data.datamodule, _recursive_=False, scaler_path=model_path
            )
            datamodule.setup()
            train_loader = datamodule.train_dataloader(shuffle=False)

        train_set = train_loader.dataset

        # Create sampling dataset that selects random templates
        rng = np.random.RandomState(9999)
        indices = rng.choice(len(train_set), num_structures, replace=True)

        class _SampleDataset(Dataset):
            def __init__(self, dataset, idxs):
                self.dataset = dataset
                self.idxs = idxs

            def __len__(self):
                return len(self.idxs)

            def __getitem__(self, index):
                return self.dataset[self.idxs[index]]

        sample_set = _SampleDataset(train_set, indices)
        loader = DataLoader(sample_set, batch_size=min(batch_size, len(sample_set)))

        # Run diffusion
        frac_coords_all = []
        num_atoms_all = []
        atom_types_all = []
        lattices_all = []

        for batch in loader:
            if torch.cuda.is_available():
                batch.cuda()
            outputs, _ = self.model.sample(batch, step_lr=step_lr)
            frac_coords_all.append(outputs["frac_coords"].detach().cpu())
            num_atoms_all.append(outputs["num_atoms"].detach().cpu())
            atom_types_all.append(outputs["atom_types"].detach().cpu())
            lattices_all.append(outputs["lattices"].detach().cpu())

        frac_coords = torch.cat(frac_coords_all, dim=0)
        num_atoms = torch.cat(num_atoms_all, dim=0)
        atom_types = torch.cat(atom_types_all, dim=0)
        lattices = torch.cat(lattices_all, dim=0)

        lengths, angles = self._lattices_to_params(lattices)

        crystal_list = self._get_crystals_list(frac_coords, atom_types, lengths, angles, num_atoms)
        structures = self._crystals_to_pymatgen(crystal_list)

        # Save structures
        structure_paths = []
        for i, struct in enumerate(structures):
            if struct is not None:
                cif_path = output_path / f"structure_{i:04d}.cif"
                writer = CifWriter(struct)
                writer.write_file(str(cif_path))
                structure_paths.append(str(cif_path))

        metadata = {
            "model_name": self.model_name,
            "generation_mode": "unconditional",
            "num_structures_requested": num_structures,
            "num_generated": len(structure_paths),
            "step_lr": step_lr,
        }
        metadata_path = output_path / "generation_metadata.json"
        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=2)

        return {
            "num_generated": len(structure_paths),
            "output_dir": str(output_path),
            "structures": structure_paths,
            "metadata_path": str(metadata_path),
        }

    def _build_syminfo_data(
        self,
        spacegroup: int,
        wyckoff_letters: Union[str, List[str]],
        atom_types: Optional[List[str]] = None,
    ):
        """Build a PyG Data object from symmetry information.

        Args:
            spacegroup: Space group number (1-230).
            wyckoff_letters: Wyckoff position labels.
            atom_types: Element for each Wyckoff position.

        Returns:
            torch_geometric.data.Data object for the model.
        """
        import torch
        from pyxtal.symmetry import Group
        from torch_geometric.data import Data

        if isinstance(wyckoff_letters, str):
            if "," in wyckoff_letters:
                wyckoff_letters = wyckoff_letters.split(",")
            else:
                wyckoff_letters = list(wyckoff_letters)

        g = Group(spacegroup)
        ops_tot = []
        anchor_index = []
        num_atoms = 0
        atom_numbers = [] if atom_types is not None else None

        for idx in range(len(wyckoff_letters)):
            letter = wyckoff_letters[idx][-1]  # 'a' for '2a', or just 'a'
            ops = g[letter].ops
            for op in ops:
                ops_tot.append(op.affine_matrix)
                anchor_index.append(num_atoms)
                if atom_types is not None:
                    atom_numbers.append(REV_CHEMICAL_SYMBOLS[atom_types[idx]])
            num_atoms += len(ops)

        data = Data(
            spacegroup=torch.LongTensor([spacegroup]),
            ops=torch.FloatTensor(ops_tot),
            anchor_index=torch.LongTensor(anchor_index),
            num_nodes=num_atoms,
            num_atoms=num_atoms,
        )
        data.ops_inv = torch.linalg.pinv(data.ops[:, :3, :3])

        if atom_types is not None:
            data.atom_types = torch.LongTensor(atom_numbers)
        else:
            data.atom_types = torch.zeros(num_atoms, dtype=torch.long)

        return data

    def _run_diffusion(
        self,
        data_list: list,
        step_lr: float,
        batch_size: int,
    ) -> list:
        """Run the diffusion model on a list of data objects and return pymatgen Structures.

        Args:
            data_list: List of PyG Data objects.
            step_lr: Langevin step size.
            batch_size: Batch size for inference.

        Returns:
            List of pymatgen Structure objects (or None for failures).
        """
        import torch
        from torch.utils.data import Dataset
        from torch_geometric.data import DataLoader

        class _ListDataset(Dataset):
            def __init__(self, items):
                self.items = items

            def __len__(self):
                return len(self.items)

            def __getitem__(self, idx):
                return self.items[idx]

        dataset = _ListDataset(data_list)
        loader = DataLoader(dataset, batch_size=min(batch_size, len(dataset)))

        frac_coords_all = []
        num_atoms_all = []
        atom_types_all = []
        lattices_all = []

        for batch in loader:
            if self.device == "cuda":
                batch.cuda()
            outputs, _ = self.model.sample(batch, step_lr=step_lr)
            frac_coords_all.append(outputs["frac_coords"].detach().cpu())
            num_atoms_all.append(outputs["num_atoms"].detach().cpu())
            atom_types_all.append(outputs["atom_types"].detach().cpu())
            lattices_all.append(outputs["lattices"].detach().cpu())

        frac_coords = torch.cat(frac_coords_all, dim=0)
        num_atoms = torch.cat(num_atoms_all, dim=0)
        atom_types = torch.cat(atom_types_all, dim=0)
        lattices = torch.cat(lattices_all, dim=0)

        lengths, angles = self._lattices_to_params(lattices)
        crystal_list = self._get_crystals_list(frac_coords, atom_types, lengths, angles, num_atoms)
        return self._crystals_to_pymatgen(crystal_list)

    @staticmethod
    def _lattices_to_params(lattices):
        """Convert lattice matrices to lengths and angles.

        Args:
            lattices: Tensor of shape (N, 3, 3).

        Returns:
            Tuple of (lengths, angles) tensors.
        """
        import numpy as np
        import torch

        lengths = torch.sqrt(torch.sum(lattices ** 2, dim=-1))
        angles = torch.zeros_like(lengths)
        for i in range(3):
            j = (i + 1) % 3
            k = (i + 2) % 3
            angles[..., i] = torch.clamp(
                torch.sum(lattices[..., j, :] * lattices[..., k, :], dim=-1)
                / (lengths[..., j] * lengths[..., k]),
                -1.0,
                1.0,
            )
        angles = torch.arccos(angles) * 180.0 / np.pi
        return lengths, angles

    @staticmethod
    def _get_crystals_list(frac_coords, atom_types, lengths, angles, num_atoms):
        """Split batched tensors into per-crystal dicts.

        Args:
            frac_coords: Batched fractional coordinates.
            atom_types: Batched atom type indices.
            lengths: Lattice lengths per crystal.
            angles: Lattice angles per crystal.
            num_atoms: Number of atoms per crystal.

        Returns:
            List of crystal dicts.
        """
        start_idx = 0
        crystal_list = []
        for batch_idx, num_atom in enumerate(num_atoms.tolist()):
            crystal_list.append({
                "frac_coords": frac_coords.narrow(0, start_idx, num_atom).detach().cpu().numpy(),
                "atom_types": atom_types.narrow(0, start_idx, num_atom).detach().cpu().numpy(),
                "lengths": lengths[batch_idx].detach().cpu().numpy(),
                "angles": angles[batch_idx].detach().cpu().numpy(),
            })
            start_idx += num_atom
        return crystal_list

    @staticmethod
    def _crystals_to_pymatgen(crystal_list: list) -> list:
        """Convert crystal dicts to pymatgen Structure objects.

        Args:
            crystal_list: List of crystal dicts from _get_crystals_list.

        Returns:
            List of pymatgen Structure objects (or None for invalid structures).
        """
        from pymatgen.core.lattice import Lattice
        from pymatgen.core.structure import Structure

        structures = []
        for crystal in crystal_list:
            frac_coords = crystal["frac_coords"]
            atom_types = crystal["atom_types"]
            lengths = crystal["lengths"]
            angles = crystal["angles"]
            try:
                structure = Structure(
                    lattice=Lattice.from_parameters(
                        *(lengths.tolist() + angles.tolist())
                    ),
                    species=atom_types,
                    coords=frac_coords,
                    coords_are_cartesian=False,
                )
                structures.append(structure)
            except Exception:
                structures.append(None)
        return structures
