
"""
Feature Calculators for MLIP models.

This module provides custom ASE calculators and PyTorch modules for extracting
crystal features (embeddings/descriptors) from various MLIP models (MatGL, MACE).
These features are used for clustering and sampling in the OffEquilibriumSampler.
"""

import os
if "MATGL_BACKEND" not in os.environ:
    os.environ["MATGL_BACKEND"] = "DGL"

import logging
import torch
import torch.nn as nn
import numpy as np
from typing import Any, Optional, Dict, List, Union
from ase.calculators.calculator import Calculator, all_changes
from ase import Atoms

logger = logging.getLogger(__name__)

# Try imports
try:
    import matgl
    MATGL_AVAILABLE = True
except ImportError:
    MATGL_AVAILABLE = False


class MatGLCrystalFeaturePotential(nn.Module):
    """
    A custom Potential class that returns crystal features in addition to energy, forces, and stresses.
    """

    def __init__(
        self,
        model,
        data_mean: torch.Tensor | float = 0.0,
        data_std: torch.Tensor | float = 1.0,
        element_refs: torch.Tensor | np.ndarray | None = None,
        calc_forces: bool = True,
        calc_stresses: bool = True,
        calc_hessian: bool = False,
        calc_magmom: bool = False,
        calc_repuls: bool = False,
        zbl_trainable: bool = False,
        debug_mode: bool = False,
    ):
        super().__init__()
        self.model = model
        self.calc_forces = calc_forces
        self.calc_stresses = calc_stresses
        self.calc_hessian = calc_hessian
        self.calc_magmom = calc_magmom
        self.calc_repuls = calc_repuls
        self.data_mean = data_mean
        self.data_std = data_std
        self.element_refs = element_refs
        self.debug_mode = debug_mode
        self.zbl_trainable = zbl_trainable
        # For repuls handling
        if calc_repuls:
             from matgl.layers import PairPot
             self.repuls = PairPot()

    def forward(
        self,
        g: Any,  # dgl.DGLGraph
        lat: torch.Tensor,
        state_attr: torch.Tensor | None = None,
        l_g: Any | None = None,  # dgl.DGLGraph
    ) -> tuple[torch.Tensor, ...]:
        """
        Args:
            g: dgl Graph
            lat: lattice
            lattice: lattice
            state_attr: state attributes
            l_g: line graph

        Returns:
            (energy, forces, stress, hessian, crystal_features)
        """
        # This logic is adapted from matgl.apps._pes_dgl.Potential.forward (DGL)
        # and matgl.apps.pes.Potential.forward (PyG)
        batch_size = g.batch_size if hasattr(g, "batch_size") else (g.num_graphs if hasattr(g, "num_graphs") else 1)
        
        # st (strain) for stress calculations
        st = lat.new_zeros([batch_size, 3, 3])
        if self.calc_stresses:
            st.requires_grad_(True)
            
        lattice = lat @ (torch.eye(3, device=lat.device) + st)
        
        # Check backend (DGL has .ndata, PyG has .pos etc directly)
        is_dgl = hasattr(g, "ndata")
        
        if is_dgl:
            g.edata["lattice"] = torch.repeat_interleave(lattice, g.batch_num_edges(), dim=0)
            g.edata["pbc_offshift"] = (g.edata["pbc_offset"].unsqueeze(dim=-1) * g.edata["lattice"]).sum(dim=1)
            g.ndata["pos"] = (
                g.ndata["frac_coords"].unsqueeze(dim=-1) * torch.repeat_interleave(lattice, g.batch_num_nodes(), dim=0)
            ).sum(dim=1)
            if self.calc_forces:
                g.ndata["pos"].requires_grad_(True)
            inner_g = g
        else:
            # PyG logic
            from torch_geometric.data import Batch
            if isinstance(g, Batch):
                edge_batch = g.batch[g.edge_index[0]]
                node_batch = g.batch
            else:
                edge_batch = torch.zeros(g.edge_index.size(1), dtype=torch.long, device=lat.device)
                node_batch = torch.zeros(g.num_nodes, dtype=torch.long, device=lat.device)
            
            g.lattice = lattice[edge_batch]
            g.pbc_offshift = (g.pbc_offset.unsqueeze(dim=-1) * g.lattice).sum(dim=1)
            lattice_per_node = lattice[node_batch]
            g.pos = (g.frac_coords.unsqueeze(-1) * lattice_per_node).sum(dim=1)
            if self.calc_forces:
                g.pos.requires_grad_(True)
            inner_g = g

        # Call model with return_all_layer_output=True to get energy and features in one go
        # Note: some models might need lattice passed as well
        kwargs = {"g": inner_g, "state_attr": state_attr, "l_g": l_g, "return_all_layer_output": True}
        # Check if the model accepts 'lat' or 'lattice'
        import inspect
        sig = inspect.signature(self.model.forward)
        if "lat" in sig.parameters:
            kwargs["lat"] = lat
        if "lattice" in sig.parameters:
            kwargs["lattice"] = lat
            
        model_output = self.model(**kwargs)
        
        if not isinstance(model_output, dict):
             raise TypeError(f"Model {self.model.__class__.__name__} must return a dict when return_all_layer_output=True, instead got {type(model_output)}")

        # Extract energy
        total_energy = model_output.get("final")
        if total_energy is None:
             raise KeyError(f"Model output dict did not contain 'final' energy key. Available keys: {list(model_output.keys())}")

        # Extract crystal features
        crystal_features = model_output.get("graph_feat")
        if crystal_features is None:
            # Try to find node features to average
            node_features = None
            # Check for various keys used in different versions (M3GNet/CHGNet)
            if "gc_3" in model_output and isinstance(model_output["gc_3"], dict):
                node_features = model_output["gc_3"].get("node_feat")
                if node_features is None:
                    node_features = model_output["gc_3"].get("atom_feat")
            
            if node_features is None:
                node_features = model_output.get("node_feat")
                if node_features is None:
                    node_features = model_output.get("atom_feat")
                
            if node_features is not None:
                # Average node features to get crystal feature
                crystal_features = torch.mean(node_features, dim=0)
        
        if crystal_features is None:
             raise KeyError(f"Could not extract crystal features from model output keys: {list(model_output.keys())}")
        
        # Apply standard Potential post-processing
        if hasattr(self, 'element_refs') and self.element_refs is not None:
             # element_refs in Potential is often an AtomRef module
             if isinstance(self.element_refs, nn.Module):
                 property_offset = torch.squeeze(self.element_refs(g))
             else:
                 # Fallback if it's just raw data
                 node_feat = g.ndata["node_type"]
                 property_offset = torch.sum(self.element_refs[node_feat], dim=0)
             total_energy += property_offset

        total_energy = total_energy * self.data_std + self.data_mean
        
        if self.calc_repuls and hasattr(self.model, "element_types"):
            total_energy += self.repuls(self.model.element_types, g)

        # Calculate derivatives
        forces = torch.zeros(1)
        stress = torch.zeros(1)
        hessian = torch.zeros(1)

        pos_var = inner_g.ndata["pos"] if is_dgl else inner_g.pos
        grad_vars = [pos_var, st] if self.calc_stresses else [pos_var]

        if self.calc_forces:
            from torch.autograd import grad
            grads = grad(
                total_energy,
                grad_vars,
                grad_outputs=torch.ones_like(total_energy),
                create_graph=self.calc_hessian,
                retain_graph=self.calc_hessian,
                allow_unused=True,
            )
            forces = -grads[0]
            
            if self.calc_stresses:
                sts = grads[1]
                # Volume calculation for stress conversion
                # Use det(lattice)
                vol = torch.abs(torch.det(lattice))
                scale = 1.0 / vol # eV/A^3 (standard ASE unit)
                stress = sts * scale
                # Convert to Voigt or keep as tensor
                if stress.dim() == 3:
                     # stress is [batch, 3, 3]
                     # ASE Expects [3, 3] or [6]
                     stress = stress[0] # Assuming batch size 1
                
        return total_energy, forces, stress, hessian, crystal_features


class MatGLCrystalFeatureCalculator(Calculator):
    """
    Custom MatGL calculator that stores crystal features in results during calculation.
    wraps a MatGL model and uses MatGLCrystalFeaturePotential.
    """
    
    implemented_properties = ("energy", "free_energy", "forces", "stress", "hessian", "magmoms", "crystal_fea")
    
    def __init__(self, potential, state_attr=None, stress_unit="eV/Å³", stress_weight=1.0, use_voigt=False, device="auto", **kwargs):
        """
        Args:
            potential: matgl.apps.pes.Potential or matgl.models.*
            state_attr: State attributes
            stress_unit: Unit for stress (default eV/Å³)
            stress_weight: Weight for stress
            use_voigt: Use Voigt notation for stress
            device: Device to run on
        """
        Calculator.__init__(self, **kwargs)
        
        # If potential is a PESCalculator, unwrap it
        if hasattr(potential, "potential") and not hasattr(potential, "model"):
             # Case of PESCalculator
             potential = potential.potential
             
        # If potential is a Potential module, unwrap the base model
        if hasattr(potential, "model"):
            model = potential.model
            # Copy other attributes if needed
            data_mean = getattr(potential, "data_mean", 0.0)
            data_std = getattr(potential, "data_std", 1.0)
            element_refs = getattr(potential, "element_refs", None)
            calc_repuls = getattr(potential, "calc_repuls", False)
        else:
            model = potential
            data_mean = 0.0
            data_std = 1.0
            element_refs = None
            calc_repuls = False
            
        self.potential = MatGLCrystalFeaturePotential(
            model=model,
            data_mean=data_mean,
            data_std=data_std,
            element_refs=element_refs,
            calc_forces=True,
            calc_stresses=True, # Always calculate stress for MD
            calc_repuls=calc_repuls
        )
        
        self.converter = None
        self.struct_adaptor = None
        
        self.state_attr = state_attr
        
        if device == "auto":
            import torch
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device
            
        self.potential.to(self.device)

    def calculate(self, atoms=None, properties=None, system_changes=all_changes):
        """Calculate properties."""
        Calculator.calculate(self, atoms, properties, system_changes)
        
        # Convert atoms to graph
        import matgl
        from matgl.ext.pymatgen import get_element_list, Structure2Graph
        if self.struct_adaptor is None:
            from pymatgen.io.ase import AseAtomsAdaptor
            self.struct_adaptor = AseAtomsAdaptor()
            
        struct = self.struct_adaptor.get_structure(atoms)
        
        if self.converter is None:
            from matgl.ext.pymatgen import get_element_list, Structure2Graph
            # determine elements and cutoff (simplified)
            elements = self.potential.model.element_types if hasattr(self.potential.model, "element_types") else get_element_list([struct])
            cutoff = getattr(self.potential.model, "cutoff", 5.0)
            self.converter = Structure2Graph(element_types=elements, cutoff=cutoff)
            
        # get_graph returns graph, state_attr, (optional) other info depending on MatGL version
        graph_data = self.converter.get_graph(struct)
        if len(graph_data) == 3:
             graph, state_attr, _ = graph_data
        else:
             graph, state_attr = graph_data
        
        if self.state_attr is not None:
             state_attr = self.state_attr
             
        # Prepare inputs
        is_dgl = hasattr(graph, "ndata")
        
        if is_dgl:
            if "pos" not in graph.ndata:
                 pass
            try:
                graph.ndata["pos"].requires_grad_(True)
            except Exception:
                pass
            import dgl
            g_batch = dgl.batch([graph]).to(self.device)
        else:
            if not hasattr(graph, "pos"):
                pass
            try:
                graph.pos.requires_grad_(True)
            except Exception:
                pass
            from torch_geometric.data import Batch
            g_batch = Batch.from_data_list([graph]).to(self.device)

        lattice = torch.tensor(struct.lattice.matrix, dtype=matgl.float_th, device=self.device).unsqueeze(0)
        lattice.requires_grad_(True)
        
        state_attr = torch.tensor(state_attr, dtype=matgl.float_th, device=self.device).unsqueeze(0) if state_attr is not None else None
        
        # Run model
        energy, forces, stress, hessian, crystal_features = self.potential(g_batch, lattice, state_attr)
        
        # Store results
        self.results["energy"] = energy.detach().cpu().numpy().item()
        self.results["free_energy"] = self.results["energy"]
        # Remove squeeze(0) which was incorrect for multiple atoms
        self.results["forces"] = forces.detach().cpu().numpy()
        
        # Stress handling
        self.results["stress"] = stress.detach().cpu().numpy()
        s = self.results["stress"]
        
        # Convert to Voigt [xx, yy, zz, yz, xz, xy]
        if s.shape == (3, 3):
             s_voigt = np.array([s[0,0], s[1,1], s[2,2], s[1,2], s[0,2], s[0,1]])
             self.results["stress"] = s_voigt
        else:
             self.results["stress"] = s
        
        # Ensure forces are 2D (N, 3)
        if self.results["forces"].ndim == 1:
             self.results["forces"] = self.results["forces"].reshape(-1, 3)
             
        # Store crystal features
        self.results["crystal_fea"] = crystal_features.detach().cpu().numpy().flatten()


class MaceCrystalFeatureCalculator(Calculator):
    """
    Wrapper for MACE calculator that adds crystal feature extraction.
    Uses 'get_descriptors' from MACE to get atomic features and averages them.
    """
    
    implemented_properties = ("energy", "free_energy", "forces", "stress", "magmoms", "crystal_fea")
    
    def __init__(self, mace_calculator: Calculator, **kwargs):
        """
        Args:
            mace_calculator: An initialized mace.calculators.mace.MACECalculator
        """
        self.mace_calc = mace_calculator
        Calculator.__init__(self, **kwargs)
        
        # Copy settings from wrapped calculator
        self.parameters = self.mace_calc.parameters
        
    def calculate(self, atoms=None, properties=None, system_changes=all_changes):
        """Calculate properties using MACE and extract descriptors with a single forward pass."""
        # Standard ASE calculator setup
        Calculator.calculate(self, atoms, properties, system_changes)
        
        # Captured features from hooks
        captured_feats = []

        def hook_fn(module, input, output):
            if isinstance(output, dict) and "node_feats" in output:
                captured_feats.append(output["node_feats"])

        # Register hooks on all models in the ensemble
        # MACE calculators can be ensembles of multiple models
        hooks = []
        if hasattr(self.mace_calc, "models"):
            for model in self.mace_calc.models:
                hooks.append(model.register_forward_hook(hook_fn))
        
        try:
            # We want energy and forces mostly
            # If properties is None, ASE defaults to 'energy', 'forces' usually
            req_props = properties if properties else ['energy', 'forces']
            
            # The standard calculate() call on mace_calc will trigger the forward pass
            # This handles energy, forces, stress, etc.
            self.mace_calc.calculate(atoms, properties=req_props, system_changes=system_changes)
            
            # Copy standard results to this calculator
            self.results.update(self.mace_calc.results)
            
            # Process captured features
            if captured_feats:
                # If it's an ensemble, captured_feats will have len > 1
                # MACE's get_descriptors averages over models if num_models > 1
                # For sampling features, we follow the same pattern
                
                # Each feat in captured_feats is (num_atoms, num_features) or (num_atoms, num_layers, num_feat)
                # MACE descriptors usually average over atoms
                all_atom_features = []
                for feat in captured_feats:
                    # Detach and move to cpu/numpy
                    f_np = feat.detach().cpu().numpy()
                    # MACE descriptors can have multiple layers, we flatten/average as needed
                    # By default, we average over atoms (axis 0)
                    # If it has 3 dims (atoms, layers, features), we might need to handle layers
                    if f_np.ndim == 3:
                        # Average over layers first or just take last layer? 
                        # MACE get_descriptors usually returns all requested layers.
                        # We'll average over EVERYTHING but atoms to get a descriptor per atom if not careful.
                        # Let's keep it consistent with MACE's own descriptor extraction logic if possible.
                        # For simplicity in clustering, we average over atoms to get (crystal_feature_dim,)
                        
                        # Average over atoms
                        avg_feat = np.mean(f_np, axis=0)
                        # Then flatten features/layers
                        all_atom_features.append(avg_feat.flatten())
                    else:
                        all_atom_features.append(np.mean(f_np, axis=0))
                
                # Average over models in ensemble
                crystal_features = np.mean(all_atom_features, axis=0)
                self.results["crystal_fea"] = crystal_features
            else:
                # Fallback to get_descriptors if hook failed (e.g. non-standard MACE version)
                descriptors = self.mace_calc.get_descriptors(atoms)
                if descriptors is not None:
                    self.results["crystal_fea"] = np.mean(descriptors, axis=0)
                else:
                    raise RuntimeError("MACE descriptor extraction failed (both hook and fallback)")
        finally:
            # Always remove hooks
            for h in hooks:
                h.remove()

    def get_property(self, name, atoms=None, allow_calculation=True):
        if name == "crystal_fea":
             if name not in self.results:
                  if allow_calculation:
                       self.calculate(atoms=atoms, properties=[name])
                  else:
                       return None
             return self.results[name]
             return self.results[name]
        
        # For structural properties, use standard Calculator mechanism
        # This ensures self.calculate is called, populating self.results and crystal_fea
        return Calculator.get_property(self, name, atoms, allow_calculation)

