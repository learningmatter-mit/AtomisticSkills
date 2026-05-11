"""
Catalysis Activity Utilities.

A generalized object-oriented framework for thermodynamic modeling of
heterogeneous catalytic reactions (OER, ORR, etc.). Includes empirical
scaling derivation and automated visualization capabilities.
"""

import numpy as np
import matplotlib.pyplot as plt
from abc import ABC, abstractmethod
from typing import Dict, Any, List

# Default Free Energy correction terms (G - E_DFT) = ZPE + CV - TS at T=298.15K.
THERMO_CORRECTIONS = {
    "H2O": {"zpe": 0.560, "cv": 0.103, "ts": 0.675},
    "H2":  {"zpe": 0.268, "cv": 0.0905, "ts": 0.408},
    "O":   {"zpe": 0.065, "cv": 0.038, "ts": 0.080},
    "OH":  {"zpe": 0.344, "cv": 0.051, "ts": 0.080},
    "OOH": {"zpe": 0.443, "cv": 0.068, "ts": 0.116},
    "CO":  {"zpe": 0.140, "cv": 0.087, "ts": 0.613}, 
}

def load_external_corrections(json_path: str) -> None:
    """
    Update the global THERMO_CORRECTIONS with values from a JSON file.
    
    Args:
        json_path: Path to the JSON file containing corrections.
    """
    import json
    import os
    if not os.path.exists(json_path):
        import logging
        logging.warning(f"External corrections file not found: {json_path}")
        return
        
    with open(json_path, 'r') as f:
        new_data = json.load(f)
        THERMO_CORRECTIONS.update(new_data)

def get_thermo_corrections(species: str) -> float:
    """
    Returns the Free Energy correction term (G - E_DFT) = ZPE + CV - TS
    for a given species using the current THERMO_CORRECTIONS dataset.
    """
    mapping = {"HO": "OH", "HOO": "OOH"}
    clean_sp = mapping.get(species, species)
    
    if clean_sp not in THERMO_CORRECTIONS:
        import logging
        logging.warning(f"No thermodynamic corrections for {species}. Assuming 0.0!")
        return 0.0
        
    c = THERMO_CORRECTIONS[clean_sp]
    g_corr = c["zpe"] + c.get("cv", 0.0) - c.get("ts", 0.0)
    return g_corr


class ReactionMechanism(ABC):
    
    @property
    @abstractmethod
    def name(self) -> str:
        pass
        
    @property
    @abstractmethod
    def required_intermediates(self) -> List[str]:
        pass
        
    @property
    @abstractmethod
    def equilibrium_potential(self) -> float:
        pass

    @property
    @abstractmethod
    def starting_free_energy(self) -> float:
        """Starting free energy level relative to standard (e.g. 0 for OER, 4.92 for ORR)."""
        pass

    def calculate_steps(self, binding_energies: Dict[str, float]) -> Dict[str, Any]:
        """
        Evaluate steps, overpotential, and descriptor for a single catalyst surface.
        binding_energies MUST be relative to standard H2/H2O references!
        
        Must return Dict with at least:
        "steps": [dG1, dG2, ...], 
        "eta": overpotential (V), 
        "pds": int (1-indexed), 
        "descriptor": float
        """
        pass
        
    @abstractmethod
    def get_step_labels(self) -> List[str]:
        """Labels for the X-axis of the Free Energy diagram."""
        pass
        
    @abstractmethod
    def get_descriptor_name(self) -> str:
        """Name of the descriptor for the Volcano plot X-axis."""
        pass

    def __init__(self):
        self.step_colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b', '#e377c2']
    
    def acquire_empirical_scaling(self, results_dict: Dict[str, Dict[str, Any]], desc_range: np.ndarray) -> np.ndarray:
        """
        Calculates theoretical overpotential curves empirically derived from the 
        dataset linear regression of all operational steps against the descriptor.
        """
        names = list(results_dict.keys())
        if not names:
            return np.zeros_like(desc_range)
            
        num_steps = len(results_dict[names[0]]["steps"])
        descriptors = [res["descriptor"] for res in results_dict.values()]
        
        step_fits = []
        for step_idx in range(num_steps):
            step_energies = [res["steps"][step_idx] for res in results_dict.values()]
            if len(descriptors) > 1:
                coefs = np.polyfit(descriptors, step_energies, 1)
            else:
                coefs = [0.0, step_energies[0]]
            step_fits.append(coefs)
            
        eta_empirical = []
        for x in desc_range:
            step_theoretics = [coefs[0] * x + coefs[1] for coefs in step_fits]
            
            # Use max(steps) for OER. For reductions (ORR downhill steps), 
            # U_lim = - max(step). eta = V_eq - U_lim = V_eq + max(step).
            # Wait, if ORR steps are downhill (e.g. -1.0, -1.5, -1.0, -1.42). 
            # Max step is -1.0. Overpotential = 1.23 + (-1.0) = 0.23 V.
            # So `eta = max(steps) - V_eq` for OER OR `eta = V_eq + max(steps)` for ORR!
            # Since self.equilibrium_potential might be used differently, let's just 
            # calculate eta identically to the subclass evaluate mechanism!
            # Let's abstract a function `calculate_eta(steps)` so we can reuse!
            try:
                eta = self.calculate_eta(step_theoretics)
            except Exception:
                eta = max(step_theoretics) - self.equilibrium_potential
            eta_empirical.append(eta)
            
        return np.array(eta_empirical)

    @abstractmethod
    def calculate_eta(self, steps: List[float]) -> float:
        """Formula converting mechanism steps into empirical overpotential."""
        pass

    def plot_free_energy(self, results_dict: Dict[str, Dict[str, Any]], output_path: str):
        plt.figure(figsize=(8, 6))
        
        x_labels = self.get_step_labels()
        x_positions = np.arange(len(x_labels))
        
        n_steps = len(x_labels) - 1
        # For ideal background:
        if self.starting_free_energy > 0:
            ideal_levels = [self.starting_free_energy] + [self.starting_free_energy - self.equilibrium_potential * i for i in range(1, n_steps + 1)]
        else:
            ideal_levels = [self.starting_free_energy] + [self.starting_free_energy + self.equilibrium_potential * i for i in range(1, n_steps + 1)]
        
        step_width = 0.6
        
        for name, res in results_dict.items():
            levels = [self.starting_free_energy]
            current_energy = self.starting_free_energy
            for step_dg in res["steps"]:
                current_energy += step_dg
                levels.append(current_energy)
                
            for i in range(len(levels)):
                plt.hlines(levels[i], x_positions[i] - step_width/2, x_positions[i] + step_width/2, 
                           linewidth=3, label=name if i == 0 else "")
                
            for i in range(len(levels)-1):
                plt.plot([x_positions[i] + step_width/2, x_positions[i+1] - step_width/2], 
                         [levels[i], levels[i+1]], 'k--', alpha=0.3)
                 
        for i in range(len(ideal_levels)):
            plt.hlines(ideal_levels[i], x_positions[i] - step_width/2, x_positions[i] + step_width/2, 
                       linewidth=2, color='gray', linestyle=':')
            if i == 0:
                plt.plot([], [], color='gray', linestyle=':', label='Ideal')
                
        for i in range(len(ideal_levels)-1):
            plt.plot([x_positions[i] + step_width/2, x_positions[i+1] - step_width/2], 
                     [ideal_levels[i], ideal_levels[i+1]], 'k--', alpha=0.1)

        plt.xticks(x_positions, x_labels, fontsize=12)
        plt.yticks(fontsize=12)
        plt.ylabel('Free Energy (eV)', fontsize=14)
        plt.title(f'{self.name} Free Energy Diagram (U = 0 V vs RHE)', fontsize=14)
        plt.legend(frameon=False, loc="upper right" if self.starting_free_energy > 0 else "upper left")
        plt.tight_layout()
        plt.savefig(output_path, dpi=300)
        plt.close()

    def plot_volcano(self, results_dict: Dict[str, Dict[str, Any]], output_path: str):
        plt.figure(figsize=(7, 6))
        
        # Determine plot bounds dynamically based on data
        if results_dict:
            descriptors = [r["descriptor"] for r in results_dict.values()]
            desc_min = min(descriptors)
            desc_max = max(descriptors)
        else:
            desc_min, desc_max = 0, 3.0
            
        x_desc = np.linspace(desc_min - 0.5, desc_max + 0.5, 100)
        
        # Acquire empirical scaling model
        eta_empirical = self.acquire_empirical_scaling(results_dict, x_desc)
        
        # Plot -eta for proper volcano shape
        plt.plot(x_desc, -eta_empirical, 'k--', alpha=0.5, label='Empirical Scaling Fit')
        
        # Sort results to find top 3 (lowest eta)
        sorted_results = sorted(results_dict.items(), key=lambda x: x[1]["eta"])
        top_names = [x[0] for x in sorted_results[:3]]
        
        # Plot data points
        top_colors = ['#d62728', '#ff7f0e', '#2ca02c'] # Red, Orange, Green
        for idx, (name, res) in enumerate(results_dict.items()):
            if name in top_names:
                color = top_colors[top_names.index(name)]
                size = 100
                zorder = 10
                alpha = 1.0
            else:
                color = '#bcbcbc' # Grey
                size = 60
                zorder = 5
                alpha = 0.6
                
            plt.scatter([res["descriptor"]], [-res["eta"]], s=size, color=color, 
                        marker='o', edgecolors='k', zorder=zorder, alpha=alpha)

        # Plot Peak if present within range
        if len(x_desc) > 0:
            peak_idx = np.argmin(eta_empirical)
            plt.axvline(x_desc[peak_idx], color='r', linestyle=':', label='Empirical Optimal Activity')

        plt.xlabel(self.get_descriptor_name(), fontsize=14)
        plt.ylabel(r'$-\eta$ (V)', fontsize=14)
        plt.title('MLIP prediction', fontsize=14)
        plt.grid(alpha=0.3)
        plt.tight_layout()
        plt.savefig(output_path, dpi=300)
        plt.close()


class OERMechanism(ReactionMechanism):
    @property
    def name(self) -> str: return "OER"
    @property
    def required_intermediates(self) -> List[str]: return ["OH", "O", "OOH"]
    @property
    def equilibrium_potential(self) -> float: return 1.23
    @property
    def starting_free_energy(self) -> float: return 0.0
    
    def get_step_labels(self) -> List[str]:
        return ['*', 'OH*', 'O*', 'OOH*', 'O2']
        
    def get_descriptor_name(self) -> str:
        return r'$\Delta G_O - \Delta G_{OH}$ (eV)'
        
    def calculate_eta(self, steps: List[float]) -> float:
        return max(steps) - self.equilibrium_potential

    def calculate_steps(self, binding_energies: Dict[str, float]) -> Dict[str, Any]:
        dG_corr_OH = get_thermo_corrections("OH") + 0.5 * get_thermo_corrections("H2") - get_thermo_corrections("H2O")
        dG_corr_O = get_thermo_corrections("O") + get_thermo_corrections("H2") - get_thermo_corrections("H2O")
        dG_corr_OOH = get_thermo_corrections("OOH") + 1.5 * get_thermo_corrections("H2") - 2 * get_thermo_corrections("H2O")

        dG_OH = binding_energies["OH"] + dG_corr_OH
        dG_O = binding_energies["O"] + dG_corr_O
        dG_OOH = binding_energies["OOH"] + dG_corr_OOH

        dG1 = dG_OH
        dG2 = dG_O - dG_OH
        dG3 = dG_OOH - dG_O
        dG4 = 4.92 - dG_OOH

        steps = [dG1, dG2, dG3, dG4]
        eta = self.calculate_eta(steps)
        pds = steps.index(max(steps)) + 1
        
        return {
            "dG_OH": dG_OH, "dG_O": dG_O, "dG_OOH": dG_OOH,
            "steps": steps, "eta": eta, "pds": pds, "descriptor": dG_O - dG_OH
        }

class ORRMechanism(ReactionMechanism):
    @property
    def name(self) -> str: return "ORR"
    @property
    def required_intermediates(self) -> List[str]: return ["OOH", "O", "OH"]
    @property
    def equilibrium_potential(self) -> float: return 1.23
    @property
    def starting_free_energy(self) -> float: return 4.92
    
    def get_step_labels(self) -> List[str]:
        return ['O2', 'OOH*', 'O*', 'OH*', '*']
        
    def get_descriptor_name(self) -> str:
        return r'$\Delta G_{OH}$ (eV)'
        
    def calculate_eta(self, steps: List[float]) -> float:
        # Steps are theoretically downhill (negative)
        # Reduction overpotential = U_ideal - U_onset
        # U_lim = - max(steps). Therefore, eta = 1.23 - U_lim = 1.23 + max(steps).
        return 1.23 + max(steps)

    def calculate_steps(self, binding_energies: Dict[str, float]) -> Dict[str, Any]:
        dG_corr_OH = get_thermo_corrections("OH") + 0.5 * get_thermo_corrections("H2") - get_thermo_corrections("H2O")
        dG_corr_O = get_thermo_corrections("O") + get_thermo_corrections("H2") - get_thermo_corrections("H2O")
        dG_corr_OOH = get_thermo_corrections("OOH") + 1.5 * get_thermo_corrections("H2") - 2 * get_thermo_corrections("H2O")

        dG_OH = binding_energies["OH"] + dG_corr_OH
        dG_O = binding_energies["O"] + dG_corr_O
        dG_OOH = binding_energies["OOH"] + dG_corr_OOH

        dG1 = dG_OOH - 4.92
        dG2 = dG_O - dG_OOH
        dG3 = dG_OH - dG_O
        dG4 = -dG_OH

        steps = [dG1, dG2, dG3, dG4]
        eta = self.calculate_eta(steps)
        pds = steps.index(max(steps)) + 1
        
        return {
            "dG_OH": dG_OH, "dG_O": dG_O, "dG_OOH": dG_OOH,
            "steps": steps, "eta": eta, "pds": pds, "descriptor": dG_OH
        }

class HERMechanism(ReactionMechanism):
    @property
    def name(self) -> str: return "HER"
    @property
    def required_intermediates(self) -> List[str]: return ["H"]
    @property
    def equilibrium_potential(self) -> float: return 0.0
    @property
    def starting_free_energy(self) -> float: return 0.0
    
    def get_step_labels(self) -> List[str]:
        return ['H+', 'H*', 'H2']
        
    def get_descriptor_name(self) -> str:
        return r'$\Delta G_{H}$ (eV)'
        
    def calculate_eta(self, steps: List[float]) -> float:
        return abs(steps[0])

    def calculate_steps(self, binding_energies: Dict[str, float]) -> Dict[str, Any]:
        # Simplify H correction 
        dG_H = binding_energies["H"] + get_thermo_corrections("H") if "H" in binding_energies else 0.0
        
        steps = [dG_H, -dG_H]
        eta = self.calculate_eta(steps)
        pds = 1 if steps[0] > steps[1] else 2
        
        return {
            "dG_H": dG_H,
            "steps": steps, "eta": eta, "pds": pds, "descriptor": dG_H
        }

class CO2RR_COMechanism(ReactionMechanism):
    @property
    def name(self) -> str: return "CO2RR-CO"
    @property
    def required_intermediates(self) -> List[str]: return ["COOH", "CO"]
    @property
    def equilibrium_potential(self) -> float: return -0.11
    @property
    def starting_free_energy(self) -> float: return 0.0
    
    def get_step_labels(self) -> List[str]:
        return ['CO2', 'COOH*', 'CO*', 'CO']
        
    def get_descriptor_name(self) -> str:
        return r'$\Delta G_{CO}$ (eV)'
        
    def calculate_eta(self, steps: List[float]) -> float:
        return max(steps) - self.equilibrium_potential

    def calculate_steps(self, binding_energies: Dict[str, float]) -> Dict[str, Any]:
        dG_COOH = binding_energies["COOH"] + get_thermo_corrections("COOH") if "COOH" in binding_energies else 0.0
        dG_CO = binding_energies["CO"] + get_thermo_corrections("CO") if "CO" in binding_energies else 0.0
        
        dG1 = dG_COOH        # CO2 -> COOH*
        dG2 = dG_CO - dG_COOH # COOH* -> CO*
        dG3 = -dG_CO # Desorption approx depending on mechanism
        
        steps = [dG1, dG2, dG3]
        eta = self.calculate_eta(steps)
        pds = steps.index(max(steps)) + 1
        
        return {
            "dG_COOH": dG_COOH, "dG_CO": dG_CO,
            "steps": steps, "eta": eta, "pds": pds, "descriptor": dG_CO
        }


class NRRMechanism(ReactionMechanism):
    """Skeleton for 6-e NRR"""
    @property
    def name(self) -> str: return "NRR"
    @property
    def required_intermediates(self) -> List[str]: return ["NNH", "NNH2", "N", "NH", "NH2", "NH3"]
    @property
    def equilibrium_potential(self) -> float: return 0.05
    @property
    def starting_free_energy(self) -> float: return 0.0
    
    def get_step_labels(self) -> List[str]:
        return ['N2', 'NNH*', 'NNH2*', 'N*', 'NH*', 'NH2*', 'NH3*', 'NH3']
        
    def get_descriptor_name(self) -> str:
        return r'$\Delta G_{N} - \Delta G_{NH}$ (eV)'
        
    def calculate_eta(self, steps: List[float]) -> float:
        return max(steps) - self.equilibrium_potential

    def calculate_steps(self, binding_energies: Dict[str, float]) -> Dict[str, Any]:
        # PLACEHOLDER: Insert rigorous thermodynamics when executing NRR
        steps = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        return {
            "steps": steps, "eta": 0.0, "pds": 1, "descriptor": 0.0
        }

# Factory registration
REACTIONS = {
    "OER": OERMechanism,
    "ORR": ORRMechanism,
    "HER": HERMechanism,
    "CO2RR-CO": CO2RR_COMechanism,
    "NRR": NRRMechanism
}
