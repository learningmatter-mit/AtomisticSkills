"""
MatGL model wrapper for MLIP Agent
"""

import copy
import logging
import os
from typing import Any, Dict, List, Optional

import matplotlib
import torch
from ase.calculators.calculator import Calculator

from ..base import MLIPModel
from ..device_utils import get_best_device

matplotlib.use("Agg")
os.environ["WANDB_MODE"] = "offline"
os.environ["WANDB_SILENT"] = "true"

logger = logging.getLogger(__name__)

MATGL_AVAILABLE = False

try:
    import matgl
    import numpy as np
    from matgl.data.transformer import Normalizer
    from matgl.ext.ase import PESCalculator, Atoms2Graph
    from matgl.layers import AtomRef

    # torch >= 2.6 loads checkpoints weights-only. MatGL's pretrained models
    # also pickle these (the QET and TensorNet "-m" models numpy arrays, the
    # Eform models a Normalizer), named as numpy 1 wrote them.
    torch.serialization.add_safe_globals(
        [
            AtomRef,
            Normalizer,
            np.ndarray,
            np.dtype,
            (np._core.multiarray._reconstruct, "numpy.core.multiarray._reconstruct"),
        ]
    )

    MATGL_AVAILABLE = True
except ImportError as e:
    logger.error(f"Failed to import matgl: {e}")


# Canonical pretrained model names in matgl 4.x
AVAILABLE_MATGL_MODELS = {
    # M3GNet PES models
    "M3GNet": "M3GNet-PES-MatPES-PBE-2025.2",
    "M3GNet-MP": "M3GNet-PES-MatPES-PBE-2025.2",
    "M3GNet-MP-2021.2.8-PES": "M3GNet-PES-MatPES-PBE-2025.2",
    "M3GNet-MatPES-PBE": "M3GNet-PES-MatPES-PBE-2025.2",
    "M3GNet-MatPES-PBE-v2025.1-PES": "M3GNet-PES-MatPES-PBE-2025.2",
    "M3GNet-PES-MatPES-PBE-2025.2": "M3GNet-PES-MatPES-PBE-2025.2",
    "M3GNet-MatPES-r2SCAN": "M3GNet-PES-MatPES-r2SCAN-2025.2",
    "M3GNet-MatPES-r2SCAN-v2025.1-PES": "M3GNet-PES-MatPES-r2SCAN-2025.2",
    "M3GNet-PES-MatPES-r2SCAN-2025.2": "M3GNet-PES-MatPES-r2SCAN-2025.2",
    "M3GNet-PES-ANI-1x-Subset": "M3GNet-PES-ANI-1x-Subset",
    # CHGNet PES models. The 1M-2026.9 checkpoints (matgl 4.1) are the default
    # CHGNet; versioned 2025 names still load exactly the weights they name.
    "CHGNet": "CHGNet-PES-MatPES-PBE-1M-2026.9",
    "CHGNet-MatPES-PBE": "CHGNet-PES-MatPES-PBE-1M-2026.9",
    "CHGNet-PES-MatPES-PBE-1M-2026.9": "CHGNet-PES-MatPES-PBE-1M-2026.9",
    "CHGNet-MatPES-PBE-2025.2.10-2.7M-PES": "CHGNet-PES-MatPES-PBE-2025.2.10",
    "CHGNet-PES-MatPES-PBE-2025.2.10": "CHGNet-PES-MatPES-PBE-2025.2.10",
    "CHGNet-MatPES-r2SCAN": "CHGNet-PES-MatPES-r2SCAN-1M-2026.9",
    "CHGNet-PES-MatPES-r2SCAN-1M-2026.9": "CHGNet-PES-MatPES-r2SCAN-1M-2026.9",
    "CHGNet-MatPES-r2SCAN-2025.2.10-2.7M-PES": "CHGNet-PES-MatPES-r2SCAN-2025.2.10",
    "CHGNet-PES-MatPES-r2SCAN-2025.2.10": "CHGNet-PES-MatPES-r2SCAN-2025.2.10",
    # TensorNet PES models
    "TensorNet": "TensorNet-PES-MatPES-r2SCAN-2025.2",
    "TensorNet-MatPES-r2SCAN": "TensorNet-PES-MatPES-r2SCAN-2025.2",
    "TensorNet-MatPES-r2SCAN-v2025.1-PES": "TensorNet-PES-MatPES-r2SCAN-2025.2",
    "TensorNet-PES-MatPES-r2SCAN-2025.2": "TensorNet-PES-MatPES-r2SCAN-2025.2",
    "TensorNet-MatPES-PBE": "TensorNet-PES-MatPES-PBE-2025.2",
    "TensorNet-MatPES-PBE-v2025.1-PES": "TensorNet-PES-MatPES-PBE-2025.2",
    "TensorNet-PES-MatPES-PBE-2025.2": "TensorNet-PES-MatPES-PBE-2025.2",
    "TensorNet-PES-ANI-1x-Subset": "TensorNet-PES-ANI-1x-Subset",
    # QET PES models
    "QET": "QET-PES-MatPES-PBE-2025.2",
    "QET-PES-MatPES-PBE-2025.2": "QET-PES-MatPES-PBE-2025.2",
    "QET-PES-MatPES-r2SCAN-2025.2": "QET-PES-MatPES-r2SCAN-2025.2",
    "QET-PES-MatQ": "QET-PES-MatQ",
    # SO3Net PES models
    "SO3Net": "SO3Net-PES-ANI-1x-Subset",
    "SO3Net-PES-ANI-1x-Subset": "SO3Net-PES-ANI-1x-Subset",
    # Property models (MEGNet)
    "MEGNet-BandGap-mfi-MP-2019.4.1": "MEGNet-BandGap-mfi-MP-2019.4.1",
    "MEGNet-MP-2019.4.1-BandGap-mfi": "MEGNet-BandGap-mfi-MP-2019.4.1",
    "MEGNet-BandGap-mfi": "MEGNet-BandGap-mfi-MP-2019.4.1",
    "MEGNet-Eform-MP-2018.6.1": "MEGNet-Eform-MP-2018.6.1",
    "M3GNet-Eform-MP-2018.6.1": "M3GNet-Eform-MP-2018.6.1",
}


class MatGLWrapper(MLIPModel):
    """MatGL model wrapper implementing the MLIPModel interface."""

    # Functional indices for MEGNet-BandGap-mfi (ntypes_state=4)
    BANDGAP_FUNCTIONALS: Dict[str, int] = {"PBE": 0, "GLLB-SC": 1, "HSE": 2, "SCAN": 3}

    def __init__(
        self,
        model_name: str = "M3GNet",
        model_version: str = "latest",
        device: str = "auto",
        task_name: Optional[str] = None,
    ):
        super().__init__(model_name, model_version)
        self.device = get_best_device(device)
        self.task_name = task_name
        self.model = None
        self.is_loaded = False

    def load(self, model_path: Optional[str] = None) -> None:
        """Load a MatGL pretrained model."""
        if not MATGL_AVAILABLE:
            raise ImportError("MatGL is not available in the current environment.")

        name = model_path or self.model_name

        # Resolve aliases
        if model_path is None:
            for key, val in AVAILABLE_MATGL_MODELS.items():
                if name.upper() == key.upper():
                    name = val
                    break

        logger.info(f"Loading MatGL model {name} on {self.device}")
        self.model = matgl.load_model(name)
        self.model.to(self.device)
        self.is_loaded = True
        logger.info(f"Successfully loaded {self.model_name} on {self.device}")

    def create_calculator(self) -> Calculator:
        """Create an ASE PESCalculator from the loaded model."""
        if not self.is_loaded:
            raise RuntimeError("Model not loaded. Call load() first.")
        self.model.to(self.device)
        return PESCalculator(
            potential=self.model, device=self.device, stress_unit="eV/A3"
        )

    def static_calculation(
        self, structure_data: Any, use_nvalchemi: bool = False
    ) -> Dict[str, Any]:
        """Run a static single-point calculation.

        For MEGNet-BandGap models the DFT functional is selected via ``task_name``
        set at construction time (default "PBE"). Supported values: "PBE", "GLLB-SC",
        "HSE", "SCAN".
        """
        if not self.is_loaded:
            return {"error": "Model not loaded. Please call load() first."}

        # Batch input: pass structure_data directly so base.py can dispatch to
        # NValchemi or sequential.  check_structure_data() does not handle lists.
        is_batch = isinstance(structure_data, list) or (
            isinstance(structure_data, str) and os.path.isdir(structure_data)
        )
        if is_batch and "Potential" in type(self.model).__name__:
            return super().static_calculation(
                structure_data, use_nvalchemi=use_nvalchemi
            )

        atoms = self.check_structure_data(structure_data)
        if isinstance(atoms, dict) and "error" in atoms:
            return atoms

        model_class = type(self.model).__name__
        if "Potential" in model_class:
            return super().static_calculation(atoms)

        # Property predictor (MEGNet bandgap / Eform)
        try:
            from pymatgen.io.ase import AseAtomsAdaptor

            structure = AseAtomsAdaptor.get_structure(atoms)
            # MEGNet-BandGap uses ntypes_state=4; predict_structure requires an explicit
            # functional index passed as state_attr. Resolve from task_name (default PBE=0).
            state_attr = None
            if "BandGap" in self.model_name:
                functional = self.BANDGAP_FUNCTIONALS.get(self.task_name or "PBE", 0)
                state_attr = torch.tensor([functional], dtype=torch.float32)
            prediction = self._predict_structure(structure, state_attr)
            val = float(
                prediction.item() if hasattr(prediction, "item") else prediction
            )

            prop_name = "property_prediction"
            if "BandGap" in self.model_name or "band_gap" in self.model_name.lower():
                prop_name = "bandgap"
            elif "Eform" in self.model_name or "formation" in self.model_name.lower():
                prop_name = "formation_energy"

            return {prop_name: val, "unit": "eV"}
        except Exception as e:
            import traceback

            logger.error(f"Property prediction failed: {e}\n{traceback.format_exc()}")
            return {"error": f"Property prediction failed: {str(e)}"}

    def _predict_structure(self, structure, state_attr: Optional[torch.Tensor]):
        """A property model's prediction, as ``model.predict_structure`` makes it.

        MatGL builds the graph where its neighbor-list backend runs (the default
        CUDA device whenever one is visible) and the default state on the CPU,
        then calls the model wherever it is: with the model on the CPU or on
        another GPU that fails ("Expected all tensors to be on the same device").
        Here graph, lattice and state go to the model's device.
        """
        from matgl.ext.pymatgen import Structure2Graph

        device = next(self.model.parameters()).device
        # The Eform models wrap the network in a TransformedTargetModel, whose
        # forward un-normalizes the output; the graph settings are the network's.
        network = getattr(self.model, "model", self.model)
        converter = Structure2Graph(
            element_types=network.element_types, cutoff=network.cutoff
        )
        g, lat, state_default = converter.get_graph(structure)
        g, lat = g.to(device), lat.to(device)
        g.pbc_offshift = torch.matmul(g.pbc_offset, lat[0])
        g.pos = g.frac_coords @ lat[0]
        if state_attr is None:
            state_attr = torch.tensor(state_default, dtype=matgl.float_th)
        return self.model(g=g, state_attr=state_attr.to(device)).detach()

    def predict_atomic_features(self, structure_data: Any) -> Dict[str, Any]:
        """Predict per-atom latent features for a structure."""
        if not self.is_loaded:
            return {"error": "Model not loaded. Please call load() first."}

        atoms = self.check_structure_data(structure_data)
        if isinstance(atoms, dict) and "error" in atoms:
            return atoms

        try:
            potential = self.model
            if not hasattr(potential, "model"):
                return {
                    "error": "Loaded model does not expose an inner model for feature extraction."
                }
            inner = potential.model

            converter = Atoms2Graph(
                element_types=inner.element_types, cutoff=inner.cutoff
            )
            graph, lat, _state_attr = converter.get_graph(atoms)

            # Mirror how Potential.forward sets pos / pbc_offshift
            g = copy.copy(graph)
            g = g.to(self.device)
            if lat.dim() == 2:
                lat = lat.unsqueeze(0)
            lat = lat.to(self.device)

            node_batch = torch.zeros(g.num_nodes, dtype=torch.long, device=self.device)
            edge_batch = node_batch[g.edge_index[0]]
            g.lattice = lat[edge_batch]
            g.pbc_offshift = (g.pbc_offset.unsqueeze(-1) * g.lattice).sum(dim=1)
            g.pos = (g.frac_coords.unsqueeze(-1) * lat[node_batch]).sum(dim=1)

            with torch.no_grad():
                inner(g=g, state_attr=None)

            fd = inner.feature_dict
            features = None
            for k in reversed(list(fd.keys())):
                if k.startswith("gc_") and isinstance(fd[k], dict):
                    features = fd[k].get("node_feat")
                    if features is None:
                        features = fd[k].get("atom_feat")
                    if features is not None:
                        logger.info(f"Extracted features from layer: {k}")
                        break

            if features is None:
                return {
                    "error": f"Could not find node features in feature_dict. Keys: {list(fd.keys())}"
                }

            features = features.detach().cpu().numpy()
            return {
                "atomic_features": features.tolist(),
                "feature_dim": features.shape[1],
                "num_atoms": features.shape[0],
            }
        except Exception as e:
            import traceback

            logger.error(
                f"Failed to predict atomic features: {e}\n{traceback.format_exc()}"
            )
            return {"error": f"Failed to predict atomic features: {str(e)}"}

    def save_checkpoint(self, checkpoint_path: str) -> None:
        """Save model state checkpoint."""
        if not self.is_loaded:
            raise RuntimeError("Model not loaded")
        data = {
            "model_state_dict": self.model.state_dict(),
            "model_name": self.model_name,
            "is_fine_tuned": self.is_fine_tuned,
            "training_history": getattr(self, "_training_history", None),
        }
        torch.save(data, checkpoint_path)

    def load_checkpoint(self, checkpoint_path: str) -> None:
        """Load model weights from checkpoint."""
        if not self.is_loaded:
            self.load()
        checkpoint = torch.load(checkpoint_path, map_location=self.device)
        self.model.load_state_dict(checkpoint["model_state_dict"])
        self.is_fine_tuned = checkpoint.get("is_fine_tuned", True)
        self._training_history = checkpoint.get("training_history")
        self.is_loaded = True

    def get_supported_elements(self) -> List[str]:
        """Get supported elements from the loaded model."""
        if not self.is_loaded:
            raise RuntimeError("Model not loaded. Call load() first.")
        if hasattr(self.model, "model") and hasattr(self.model.model, "element_types"):
            return list(self.model.model.element_types)
        raise RuntimeError(
            f"Could not determine supported elements for {self.model_name}."
        )

    @property
    def supports_charge_spin(self) -> bool:
        return False

    def get_model_capabilities(self) -> Dict[str, bool]:
        return {
            "energy": True,
            "forces": True,
            "stress": True,
            "charges": self.model_name.startswith("CHGNet")
            if self.is_loaded
            else False,
            "dipole": False,
            "charge_spin": False,
        }

    def _get_nvalchemi_model(self):
        """Return a NValchemi-compatible wrapper for the loaded MatGL model, or None."""
        from src.utils.mlips.nvalchemi.matgl_nv import get_nvalchemi_matgl_model

        return get_nvalchemi_matgl_model(self)
