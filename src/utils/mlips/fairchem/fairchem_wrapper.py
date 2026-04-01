"""
FAIRCHEM model wrapper for MLIP Agent
"""

import logging
from typing import Dict, Any, Optional, List, Tuple, Union
from pathlib import Path
import numpy as np
import torch
from ase import Atoms
from ase.calculators.calculator import Calculator

from fairchem.core.units.mlip_unit.api.inference import InferenceSettings, guess_inference_settings

from ..base import MLIPModel

logger = logging.getLogger(__name__)



# Available FAIRCHEM models and checkpoints
# Model configurations, default tasks, and supported tasks
MODEL_METADATA = {
    # UMA models (Universal) - Can handle both solid state (omat) and output molecular properties (omol)
    "uma-s-1p1": {
        "default_task": "omat", 
        "supported_tasks": ["omat", "omol", "oc22"],
        "domain": "general"
    },
    "uma-m-1p1": {
        "default_task": "omat", 
        "supported_tasks": ["omat", "omol", "oc22"],
        "domain": "general"
    },
    "uma-s-1": {
        "default_task": "omat", 
        "supported_tasks": ["omat", "omol", "oc22"],
        "domain": "general"
    },
    
    # ESEN models for organic molecules (Molecular only)
    "esen-md-direct-all-omol": {
        "default_task": "omol", 
        "supported_tasks": ["omol"],
        "domain": "molecular"
    },
    "esen-sm-conserving-all-omol": {
        "default_task": "omol", 
        "supported_tasks": ["omol"],
        "domain": "molecular"
    },
    "esen-sm-direct-all-omol": {
        "default_task": "omol", 
        "supported_tasks": ["omol"],
        "domain": "molecular"
    },
    
    # ESEN models for catalysis (OC25/OC22) - Surface science
    "esen-sm-conserving-all-oc25": {
        "default_task": "oc22", 
        "supported_tasks": ["oc22", "omat"],
        "domain": "catalysis"
    }, 
    "esen-md-direct-all-oc25": {
        "default_task": "oc22", 
        "supported_tasks": ["oc22", "omat"],
        "domain": "catalysis"
    },
}

# Try to import FAIRCHEM components with clear error messages
FAIRCHEM_AVAILABLE = False

try:
    from fairchem.core import FAIRChemCalculator, pretrained_mlip
    FAIRCHEM_AVAILABLE = True
except ImportError as e:
    import os
    current_env = os.environ.get('CONDA_DEFAULT_ENV', 'unknown')
    # Only raise the environment error if we're clearly NOT in fairchem environment
    # If we're in fairchem but import fails, it's a dependency issue, not environment issue
    if 'fairchem' not in current_env.lower() and 'fairchem' not in str(e).lower():
        raise ImportError(
            f"FAIRCHEM is not available in the current conda environment '{current_env}'. "
            f"FAIRCHEM models (UMA, ESEN) require the 'fairchem-agent' conda environment. "
            f"Please run this code in the fairchem-agent environment:\n"
            f"  conda activate fairchem-agent\n"
            f"Or use subprocess execution via MLIPModelTool which handles this automatically.\n"
            f"Original error: {e}"
        ) from e
    # If we're in fairchem environment but import fails, it's a dependency issue
    # Allow the error to propagate so subprocess executor can handle it
    FAIRCHEM_AVAILABLE = False
    raise


class FAIRCHEMWrapper(MLIPModel):
    """
    FAIRCHEM model wrapper implementing the MLIPModel interface.
    
    Supports EquiformerV2 and other FAIRCHEM models.
    """
    
    def __init__(
        self, 
        model_name: str = "EquiformerV2", 
        model_version: str = "latest",
        device: str = "auto",
        task_name: Optional[str] = None,
        inference_settings: Optional[Union[Dict[str, Any], str, InferenceSettings]] = "default"
    ):
        """
        Initialize FAIRCHEM wrapper.
        
        Args:
            model_name: Name of the model ("EquiformerV2", "GemNet", etc.)
            model_version: Version of the model
            device: Device to run the model on ("auto", "cpu", "cuda")
            task_name: Optional task name (e.g. "omat", "omol", "oc22")
        """
        super().__init__(model_name, model_version)
        self.device = device
        self.task_name = task_name
        self.inference_settings = inference_settings
        self.model_class = None
        self.calculator_class = None
        self.trainer = None
        self._calculator = None
        self._current_task = None
        
        # Note: FAIRCHEM_AVAILABLE is False when package is not installed
        # This is expected in testing environments
        
        # Set up model and calculator classes
        self._setup_model_classes()
    
    def _setup_model_classes(self):
        """Set up model and calculator classes based on model name."""
        # Check if the model name is in our available models
        # Normalize model name for lookup (e.g. UMA-S-1P1 -> uma-s-1p1)
        normalized_name = self.model_name.lower()
        
        if normalized_name in MODEL_METADATA:
            self.model_name = normalized_name # Ensure we use the canonical key
            self.model_class = pretrained_mlip
            self.calculator_class = FAIRChemCalculator
            logger.info(f"Successfully set up classes for {self.model_name}")
        elif Path(self.model_name).exists():
             logger.info(f"Model name '{self.model_name}' appears to be a file path. Will infer base model from checkpoint.")
             self.model_class = pretrained_mlip
             self.calculator_class = FAIRChemCalculator
             # Checkpoint loading logic will handle the rest
        else:
             valid_models = list(MODEL_METADATA.keys())
             raise ValueError(f"Model {self.model_name} not found and is not a valid path. Available models: {valid_models}")
    
    def load(self, model_path: Optional[str] = None) -> None:
        """
        Load a FAIRCHEM model.
        
        Supports two modes:
        1. Named pretrained model (e.g., 'uma-s-1p1') — loaded via get_predict_unit
        2. Fine-tuned checkpoint file path — loaded via load_predict_unit (official API)
        
        Args:
            model_path: Path to model checkpoint. If None, uses self.model_name which
                       can be either a named model or a file path to an inference_ckpt.pt.
        """
        from pathlib import Path
        from fairchem.core.units.mlip_unit import load_predict_unit
        
        # Set device first
        if self.device == "auto":
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        
        # Determine if we're loading a file path or a named model
        load_path = model_path or self.model_name
        is_file_path = Path(load_path).exists() and Path(load_path).is_file()
        
        if is_file_path:
            # Load fine-tuned checkpoint using official FairChem API
            logger.info(f"Loading fine-tuned checkpoint from: {load_path}")
            self.model = load_predict_unit(load_path)
            self.is_loaded = True
            self.is_fine_tuned = True
            logger.info(f"Loaded fine-tuned model from {load_path}")
        else:
            # Load pretrained model by name
            model_id = load_path
            
            # Parse inference settings
            if isinstance(self.inference_settings, (str, InferenceSettings)):
                settings = guess_inference_settings(self.inference_settings)
            elif isinstance(self.inference_settings, dict):
                settings = InferenceSettings(**self.inference_settings)
            else:
                settings = self.inference_settings
            
            self.model = self.model_class.get_predict_unit(
                model_name=model_id,
                device=self.device,
                inference_settings=settings
            )
            
            self.is_loaded = True
            logger.info(f"Loaded pretrained {self.model_name} model")
    
    def create_calculator(self, task_name: Optional[str] = None) -> Calculator:
        """
        Create an ASE calculator from the model.
        
        Args:
            task_name: Optional task name to override the default.
            
        Returns:
            ASE Calculator object.
        """
        if not self.is_loaded:
            raise RuntimeError("Model not loaded. Call load() first.")
        
        # Determine target task name
        target_task = task_name or self.task_name
        if target_task is None:
            if "esen" in self.model_name.lower():
                target_task = "omol"
            else:
                target_task = "omat"
        
        # Reuse existing calculator if possible
        if self._calculator is not None and self._current_task == target_task:
            return self._calculator
            
        calculator = self.calculator_class(
            predict_unit=self.model,
            task_name=target_task
        )
        
        # Cache the calculator
        self._calculator = calculator
        self._current_task = target_task
        
        return calculator
    
    def save_checkpoint(self, checkpoint_path: str) -> None:
        """
        Save a model checkpoint.
        
        Args:
            checkpoint_path: Path to save the checkpoint.
        """
        checkpoint_path = Path(checkpoint_path)
        checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Create checkpoint with model state
        if hasattr(self.model, 'state_dict'):
            checkpoint = {
                'model_state_dict': self.model.state_dict(),
                'model_name': self.model_name,
                'model_version': self.model_version,
                'is_fine_tuned': self.is_fine_tuned
            }
        else:
            # Basic checkpoint without model state
            checkpoint = {
                'model_name': self.model_name,
                'model_version': self.model_version,
                'is_fine_tuned': self.is_fine_tuned
            }
        
        if self.training_history:
            checkpoint['training_history'] = self.training_history
        
        torch.save(checkpoint, checkpoint_path)
        logger.info(f"Model checkpoint saved to {checkpoint_path}")
    
    def _safe_load_state_dict(self, state_dict):
        """Load state dict with automatic key prefix and head name remapping.
        
        Handles two common mismatches:
        1. module. prefix: MLIPInferenceCheckpoint uses 'backbone.X' but 
           AveragedModel expects 'module.backbone.X'
        2. Head names: Fine-tuning creates 'shared_efs_head' but base model 
           has 'energyandforcehead.head' or similar
        
        Args:
            state_dict: The state dictionary to load.
        """
        target_model = self.model
        if not hasattr(target_model, "load_state_dict") and hasattr(target_model, "model"):
            target_model = target_model.model
        
        if not hasattr(target_model, "load_state_dict"):
            logging.warning("Model does not support load_state_dict. Skipping state load.")
            return
        
        model_keys = set(target_model.state_dict().keys())
        ckpt_keys = set(state_dict.keys())
        
        # Phase 1: Handle module. prefix mismatch
        model_has_module = any(k.startswith("module.") for k in model_keys)
        ckpt_has_module = any(k.startswith("module.") for k in ckpt_keys)
        
        remapped = dict(state_dict)
        if model_has_module and not ckpt_has_module:
            logging.info("Remapping checkpoint keys: adding 'module.' prefix")
            remapped = {"module." + k: v for k, v in state_dict.items()}
        elif not model_has_module and ckpt_has_module:
            logging.info("Remapping checkpoint keys: stripping 'module.' prefix")
            remapped = {k.replace("module.", "", 1): v for k, v in state_dict.items()}
        
        # Phase 2: Handle output head name mismatch
        # Extract head names from model and checkpoint keys
        model_head_names = set()
        ckpt_head_names = set()
        for k in model_keys:
            if "output_heads." in k:
                # e.g. "module.output_heads.energyandforcehead.head.energy_block.0.weight"
                parts = k.split("output_heads.")[1].split(".")
                model_head_names.add(parts[0])
        for k in remapped.keys():
            if "output_heads." in k:
                parts = k.split("output_heads.")[1].split(".")
                ckpt_head_names.add(parts[0])
        
        if model_head_names and ckpt_head_names and model_head_names != ckpt_head_names:
            # Find weight-name suffix patterns to match heads by structure
            # Simple approach: if there is exactly 1 head on each side, remap directly
            if len(model_head_names) == 1 and len(ckpt_head_names) == 1:
                model_head = next(iter(model_head_names))
                ckpt_head = next(iter(ckpt_head_names))
                
                # Check if the ckpt head weights have a sub-prefix that matches
                # Base model: output_heads.energyandforcehead.head.energy_block.0.weight
                # Checkpoint:  output_heads.shared_efs_head.energy_block.0.weight
                # Need to find what aligns: try mapping ckpt_head -> model_head (with or without .head sub-level)
                ckpt_head_keys = {k for k in remapped if "output_heads." + ckpt_head in k}
                
                # Extract suffixes after the head name
                ckpt_suffixes = set()
                for k in ckpt_head_keys:
                    suffix = k.split("output_heads." + ckpt_head + ".")[1]
                    ckpt_suffixes.add(suffix)
                
                # Find model head suffixes
                model_head_keys = {k for k in model_keys if "output_heads." + model_head in k}
                model_suffixes = set()
                model_head_prefix = None
                for k in model_head_keys:
                    suffix = k.split("output_heads." + model_head + ".")[1]
                    model_suffixes.add(suffix)
                    if model_head_prefix is None:
                        # Detect if model has an extra sub-prefix (e.g., "head.")
                        model_head_prefix = "output_heads." + model_head + "."
                
                # If ckpt suffix "energy_block.0.weight" matches model suffix "head.energy_block.0.weight"
                # then model has an extra "head." sub-prefix
                extra_prefix = ""
                if ckpt_suffixes and model_suffixes and ckpt_suffixes != model_suffixes:
                    # Check if model suffixes all start with a common sub-prefix
                    sample_ckpt = sorted(ckpt_suffixes)[0]
                    for ms in model_suffixes:
                        if ms.endswith(sample_ckpt) and len(ms) > len(sample_ckpt):
                            extra_prefix = ms[: len(ms) - len(sample_ckpt)]
                            break
                
                logging.info("Remapping head keys: '%s' -> '%s' (extra_prefix='%s')", 
                           ckpt_head, model_head, extra_prefix)
                new_remapped = {}
                for k, v in remapped.items():
                    if "output_heads." + ckpt_head + "." in k:
                        old_prefix = "output_heads." + ckpt_head + "."
                        new_prefix = "output_heads." + model_head + "." + extra_prefix
                        new_k = k.replace(old_prefix, new_prefix, 1)
                        new_remapped[new_k] = v
                    else:
                        new_remapped[k] = v
                remapped = new_remapped
        
        msg = target_model.load_state_dict(remapped, strict=False)
        if msg.missing_keys or msg.unexpected_keys:
            logging.warning("State dict load: %d missing, %d unexpected keys", 
                          len(msg.missing_keys), len(msg.unexpected_keys))
            if len(msg.missing_keys) <= 10:
                logging.warning("Missing keys: %s", msg.missing_keys)
            if len(msg.unexpected_keys) <= 10:
                logging.warning("Unexpected keys: %s", msg.unexpected_keys)
        else:
            logging.info("State dict loaded successfully with 0 missing, 0 unexpected keys")

    def load_checkpoint(self, checkpoint_path: str):
        """
        Load a checkpoint for the model.
        
        Args:
            checkpoint_path: Path to the checkpoint file
        """
        import torch
        from pathlib import Path
        
        checkpoint_path = Path(checkpoint_path)
        if not checkpoint_path.exists():
            raise FileNotFoundError(f"Checkpoint not found: {checkpoint_path}")
        
        logging.info(f"Loading checkpoint from {checkpoint_path}")
        try:
            # Try loading with weights_only=False because FAIRCHEM checkpoints contain custom classes
            # The device is not available in this scope, using 'cpu' as a fallback.
            checkpoint = torch.load(checkpoint_path, map_location='cpu', weights_only=False)
            
            # Extract metadata early to setup correct base model
            loaded_model_name = None
            if hasattr(checkpoint, "model_config") and hasattr(checkpoint.model_config, "model_name"):
                 loaded_model_name = checkpoint.model_config.model_name
            elif isinstance(checkpoint, dict):
                 loaded_model_name = checkpoint.get('model_name')
            elif hasattr(checkpoint, 'model_name'):
                 loaded_model_name = getattr(checkpoint, 'model_name')
            
            if loaded_model_name and loaded_model_name in MODEL_METADATA:
                 logging.info(f"Inferred base model from checkpoint: {loaded_model_name}")
                 self.model_name = loaded_model_name
                 self._setup_model_classes()
            
            # Now load base model if needed
            if not self.is_loaded:
                 # If model_name is still a path and we couldn't infer, we default to UMA-S-1P1 as reasonable fallback?
                 # Or we fail. UMA-S-1P1 is a safe bet for most testing.
                 if self.model_name not in MODEL_METADATA and Path(self.model_name).exists():
                     logging.warning(f"Could not infer base model from checkpoint {checkpoint_path}. Defaulting to 'uma-s-1p1'.")
                     self.model_name = "uma-s-1p1"
                     self._setup_model_classes()
                 
                 self.load()
            
            # If it's a fine-tuned model (MLIPInferenceCheckpoint)
            if hasattr(checkpoint, "model_config") and hasattr(checkpoint, "model_state_dict"):
                self.model_config = checkpoint.model_config
                self.model_state_dict = checkpoint.model_state_dict
                self.is_fine_tuned = True
            elif "state_dict" in checkpoint:
                 self.model_state_dict = checkpoint["state_dict"]
            else:
                 # Standard FAIRCHEM checkpoint dict?
                 self.model_state_dict = checkpoint.get("model", checkpoint)
                 
        except Exception as e:
            logging.error(f"Failed to load checkpoint: {e}")
            raise FileNotFoundError(f"Checkpoint not found or invalid: {checkpoint_path} -> {e}")
        
        # Load model metadata first
        # Attributes might be missing on MLIPInferenceCheckpoint or be in model_config
        if isinstance(checkpoint, dict):
            self.model_name = checkpoint.get('model_name', self.model_name)
            self.model_version = checkpoint.get('model_version', self.model_version)
            self.training_history = checkpoint.get('training_history', None)
            self.is_fine_tuned = checkpoint.get('is_fine_tuned', False)
        else:
            # Handle object-based checkpoint (MLIPInferenceCheckpoint)
            self.model_name = getattr(checkpoint, 'model_name', self.model_name)
            self.model_version = getattr(checkpoint, 'model_version', self.model_version)
            self.training_history = getattr(checkpoint, 'training_history', None)
            # Prioritize attribute from checkpoint object, but fallback to what we detected
            self.is_fine_tuned = getattr(checkpoint, 'is_fine_tuned', self.is_fine_tuned)
            
            # MLIPInferenceCheckpoint usually stores config in model_config
            if hasattr(checkpoint, "model_config"):
                 # Try to dig info from config if needed?
                 pass

        if self.model_state_dict is None:
             raise ValueError("Could not extract model state dict from checkpoint")
        
        # Load the model if not already loaded
        # (Already handled above)
        if not self.is_loaded:
             self.load()
        
        # Load model state if available
        if self.model is not None:
            # Handle loading state dict into model
            if self.is_fine_tuned and self.model_state_dict is not None:
                logging.info("Loading fine-tuned state dictionary...")
                self._safe_load_state_dict(self.model_state_dict)
            
            elif isinstance(checkpoint, dict) and 'model_state_dict' in checkpoint:
                 self._safe_load_state_dict(checkpoint['model_state_dict'])
            elif hasattr(checkpoint, 'model_state_dict'):
                 self._safe_load_state_dict(checkpoint.model_state_dict)
            elif isinstance(checkpoint, dict):
                 # Assume checkpoint IS the state dict if keys match params?
                 # Or it contains 'state_dict' key
                 if 'state_dict' in checkpoint:
                      self._safe_load_state_dict(checkpoint['state_dict'])
                 else:
                      # Try loading as is
                      try:
                          self._safe_load_state_dict(checkpoint)
                      except Exception as e:
                          logging.warning(f"Could not load checkpoint directly as state dict: {e}")
        
        self.is_loaded = True
        logging.info(f"Model checkpoint loaded from {checkpoint_path}")
    
    @property
    def supports_charge_spin(self) -> bool:
        """
        Return True when the effective task is ``omol``.

        The FairChem ``FAIRChemCalculator`` reads ``charge`` and ``spin``
        (spin multiplicity) from ``atoms.info`` only when ``task_name="omol"``.
        For all other tasks (omat, oc22, odac, omc) the values are ignored.
        """
        # Determine the resolved task (mirrors create_calculator logic)
        resolved = self.task_name
        if resolved is None:
            resolved = "omol" if "esen" in self.model_name.lower() else "omat"
        return resolved == "omol"

    def get_model_capabilities(self) -> Dict[str, bool]:
        """
        Get model capabilities.
        
        Returns:
            Dictionary of capabilities.
        """
        return {
            "energy": True,
            "forces": True,
            "stress": True,
            "optimization": True,
            "relaxation": True,
            "charge_spin": self.supports_charge_spin,
        }
        


    def predict_atomic_features(self, structure_data: Any) -> Dict[str, Any]:
        """
        Predict atomic latent features (descriptors) for a structure.
        
        Args:
            structure_data: Structure data.
            
        Returns:
            Dictionary containing 'atomic_features'.
        """
        atoms = self.check_structure_data(structure_data)
        if isinstance(atoms, dict) and "error" in atoms:
            return atoms
            
        calc = self.create_calculator()
        atoms.calc = calc
        
        # FairChem models usually don't have a direct latent feature API in the calculator
        # For now, return a placeholder or try to extract from the model if supported
        # Placeholder for consistency with base class
        return {
            "atomic_features": [],
            "note": "Atomic feature extraction not yet implemented for FAIRCHEMWrapper"
        }

    
    @staticmethod
    def get_available_models() -> List[str]:
        """
        Get list of all available FAIRCHEM model names.
        
        Returns:
            List of available model names.
        """
        return list(MODEL_METADATA.keys())
    
    @staticmethod
    def get_standard_models() -> List[str]:
        """
        Get list of standard FAIRCHEM model types.
        
        Returns:
            List of standard model types.
        """
        # Standard models are just keys of MODEL_METADATA now, or we can define a subset if needed.
        # For now, return all available keys as "standard".
        return list(MODEL_METADATA.keys())
    
    def get_supported_elements(self) -> List[str]:
        """
        Get list of chemical elements supported by the loaded model.
        
        Returns:
            List of element symbols supported by the current model.
        """
        if not self.is_loaded or self.model is None:
            raise RuntimeError("Model not loaded. Call load() first.")
        
        from ase.data import chemical_symbols

        # Unwrap the model if necessary (e.g. AveragedModel)
        model = self.model.model
        if hasattr(model, 'module'):
            model = model.module
            
        supported_z = set()
        
        # FairChem models store linear reference energies by task in `atom_refs` on the predict unit. 
        # Elements with `0.0` weights were not present in the original dataset for that task.
        if hasattr(self.model, "atom_refs") and self.model.atom_refs:
            for target, refs in self.model.atom_refs.items():
                if isinstance(refs, (list, tuple)) or type(refs).__name__ == "ListConfig":
                    for z, energy in enumerate(refs):
                        # Some tasks use -1 or 0 index for other purposes
                        if z > 0 and z < len(chemical_symbols) and energy != 0.0:
                            supported_z.add(z)
                elif isinstance(refs, dict) or type(refs).__name__ == "DictConfig":
                    for z_str, charge_dict in refs.items():
                        try:
                            z = int(z_str)
                            if 0 < z < len(chemical_symbols):
                                for charge, energy in charge_dict.items():
                                    if energy != 0.0:
                                        supported_z.add(z)
                        except ValueError:
                            pass

        if supported_z:
            return [chemical_symbols[z] for z in sorted(list(supported_z))]

        # If atom_refs is missing or entirely empty, we cannot reliably guess elements since 
        # max_num_elements acts merely as an embedding dimension ceiling.
        raise RuntimeError(
            f"Could not conclusively determine supported elements for {self.model_name}. "
            f"The `atom_refs` dictionary is missing or empty, meaning no explicit elemental reference "
            f"energies are available to confirm dataset occupancy."
        )


if __name__ == "__main__":
    # Test the wrapper
    wrapper = FAIRCHEMWrapper()
    print(f"FAIRCHEM available: {FAIRCHEM_AVAILABLE}")
    try:
         wrapper.load()
         print(f"Model capabilities: {wrapper.get_model_capabilities()}")
         print(f"Supported elements: {len(wrapper.get_supported_elements())}")
    except Exception as e:
         print(f"Load failed (expected if no GPU or environment): {e}")
