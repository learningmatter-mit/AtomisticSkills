"""
Build charged defect formation energy diagram for O vacancy in MgO.
Uses PBE DFT results from atomate2 local execution.

For charged defects, formation energy:
  E_f(q) = E_def(q) - E_bulk + mu_O + q * (E_VBM + E_Fermi)

Where:
  - E_def(q): energy of defect supercell with charge q
  - E_bulk: energy of pristine supercell 
  - mu_O: O chemical potential (from O2 molecule or O-poor/O-rich limits)
  - E_VBM: VBM eigenvalue from bulk calculation
  - E_Fermi: Fermi level measured from VBM (0 to band gap)
"""
import json
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path

BASE = Path("/home/bdeng/projects/AtomisticSkills/research/2026-02-17_MgO_charged_vacancy/dft_atomate2")

# Load DFT energies
with open(BASE / "dft_energies.json") as f:
    data = json.load(f)

E_pristine = data["pristine"]["energy"]  # -320.668 eV
E_vac_q0 = data["vac_O_q0"]["energy"]     # -309.061 eV  
E_vac_q1 = data["vac_O_q+1"]["energy"]    # -313.712 eV
E_vac_q2 = data["vac_O_q+2"]["energy"]    # -316.803 eV

# PBE band gap of MgO (experimental ~7.7 eV, PBE ~4.7 eV)
E_gap_PBE = 4.7  

# O chemical potential: O-rich limit approximation
# For PBE: E(O2) ~ -9.85 eV total, so mu_O(O-rich) = -9.85/2 = -4.925 eV
# MP PBE value: -4.948 eV/atom (includes corrections)
mu_O_rich = -4.948  

# O-poor limit: mu_O = mu_O(MgO) - mu_Mg(bulk)
# PBE: E_form(MgO) ~ -6.0 eV/f.u.
# mu_O(O-poor) = mu_O(O-rich) + E_form(MgO) 
# MgO formation enthalpy PBE ~ -5.7 eV
E_form_MgO = -5.7
mu_O_poor = mu_O_rich + E_form_MgO

print("=" * 60)
print("MgO O-vacancy DFT Results (PBE, MatPES preset)")
print("=" * 60)

print(f"\nRaw DFT energies:")
print(f"  E_pristine (Mg27O27) = {E_pristine:.6f} eV")
print(f"  E_vac_q0   (Mg27O26) = {E_vac_q0:.6f} eV")
print(f"  E_vac_q+1  (Mg27O26) = {E_vac_q1:.6f} eV")
print(f"  E_vac_q+2  (Mg27O26) = {E_vac_q2:.6f} eV")

print(f"\nChemical potential of O:")
print(f"  mu_O (O-rich)  = {mu_O_rich:.3f} eV")
print(f"  mu_O (O-poor)  = {mu_O_poor:.3f} eV")

# Formation energies as a function of Fermi level
# E_f(q, E_F) = E_def(q) - E_bulk + mu_O + q * E_F
# where E_F is measured from VBM (0 to E_gap)

def formation_energy(E_def, E_bulk, mu_O, charge, E_fermi):
    """Calculate formation energy."""
    return E_def - E_bulk + mu_O + charge * E_fermi

E_F = np.linspace(0, E_gap_PBE, 200)

# O-rich conditions
ef_q0_rich = np.full_like(E_F, formation_energy(E_vac_q0, E_pristine, mu_O_rich, 0, 0))
ef_q1_rich = formation_energy(E_vac_q1, E_pristine, mu_O_rich, 1, E_F)
ef_q2_rich = formation_energy(E_vac_q2, E_pristine, mu_O_rich, 2, E_F)

# O-poor conditions
ef_q0_poor = np.full_like(E_F, formation_energy(E_vac_q0, E_pristine, mu_O_poor, 0, 0))
ef_q1_poor = formation_energy(E_vac_q1, E_pristine, mu_O_poor, 1, E_F)
ef_q2_poor = formation_energy(E_vac_q2, E_pristine, mu_O_poor, 2, E_F)

# Minimum envelope
env_rich = np.minimum(ef_q0_rich, np.minimum(ef_q1_rich, ef_q2_rich))
env_poor = np.minimum(ef_q0_poor, np.minimum(ef_q1_poor, ef_q2_poor))

# Print formation energies at key points
print(f"\nFormation energies (O-rich, no Freysoldt correction):")
print(f"  V_O^0 (E_F=0)   = {formation_energy(E_vac_q0, E_pristine, mu_O_rich, 0, 0):.4f} eV")
print(f"  V_O^+1 (E_F=0)  = {formation_energy(E_vac_q1, E_pristine, mu_O_rich, 1, 0):.4f} eV")
print(f"  V_O^+2 (E_F=0)  = {formation_energy(E_vac_q2, E_pristine, mu_O_rich, 2, 0):.4f} eV")

# Transition levels
# epsilon(q1/q2) = (E_def(q1) - E_def(q2)) / (q2 - q1) 
# For (+2/+1): E_F where E_f(+2) = E_f(+1)
# E_def(q2) - E_bulk + mu + 2*E_F = E_def(q1) - E_bulk + mu + 1*E_F
# E_F = E_def(q1) - E_def(q2)
eps_2_1 = E_vac_q1 - E_vac_q2  # (+2/+1) transition
eps_1_0 = E_vac_q0 - E_vac_q1  # (+1/0) transition
eps_2_0 = (E_vac_q0 - E_vac_q2) / 2  # (+2/0) thermodynamic transition

print(f"\nTransition levels (from VBM):")
print(f"  epsilon(+2/+1) = {eps_2_1:.4f} eV")
print(f"  epsilon(+1/0)  = {eps_1_0:.4f} eV")
print(f"  epsilon(+2/0)  = {eps_2_0:.4f} eV")

# --- Plot ---
fig, axes = plt.subplots(1, 2, figsize=(14, 7))

colors = {"q=0": "#2196F3", "q=+1": "#FF9800", "q=+2": "#F44336"}

for ax, label, ef_q0, ef_q1, ef_q2, env in [
    (axes[0], "O-rich", ef_q0_rich, ef_q1_rich, ef_q2_rich, env_rich),
    (axes[1], "O-poor", ef_q0_poor, ef_q1_poor, ef_q2_poor, env_poor),
]:
    ax.plot(E_F, ef_q0, "--", color=colors["q=0"], alpha=0.4, linewidth=1)
    ax.plot(E_F, ef_q1, "--", color=colors["q=+1"], alpha=0.4, linewidth=1)
    ax.plot(E_F, ef_q2, "--", color=colors["q=+2"], alpha=0.4, linewidth=1)
    
    # Plot envelope with colored segments
    for i in range(len(E_F) - 1):
        val = env[i]
        if abs(val - ef_q0[i]) < 0.01:
            c = colors["q=0"]
        elif abs(val - ef_q1[i]) < 0.01:
            c = colors["q=+1"]
        else:
            c = colors["q=+2"]
        ax.plot(E_F[i:i+2], env[i:i+2], color=c, linewidth=2.5)
    
    ax.set_xlabel("Fermi level (eV from VBM)", fontsize=13)
    ax.set_ylabel("Formation energy (eV)", fontsize=13)
    ax.set_title(f"V$_O$ in MgO ({label}, PBE)", fontsize=14)
    ax.set_xlim(0, E_gap_PBE)
    ax.axhline(y=0, color="gray", linewidth=0.5, linestyle="-")
    ax.grid(True, alpha=0.3)
    
    # Legend
    from matplotlib.lines import Line2D
    legend_elements = [
        Line2D([0], [0], color=colors["q=0"], linewidth=2, label="V$_O^{0}$"),
        Line2D([0], [0], color=colors["q=+1"], linewidth=2, label="V$_O^{+1}$"),
        Line2D([0], [0], color=colors["q=+2"], linewidth=2, label="V$_O^{+2}$"),
    ]
    ax.legend(handles=legend_elements, fontsize=11)

plt.tight_layout()
plt.savefig(BASE / "formation_energy_diagram_PBE.png", dpi=200, bbox_inches="tight")
print(f"\nFigure saved to {BASE / 'formation_energy_diagram_PBE.png'}")

# Save full results
full_results = {
    "method": "PBE (MatPES preset via atomate2)",
    "supercell": "3x3x3 rocksalt MgO (54 atoms)",
    "energies": {
        "pristine": E_pristine,
        "vac_O_q0": E_vac_q0,
        "vac_O_q+1": E_vac_q1,
        "vac_O_q+2": E_vac_q2,
    },
    "formation_energies_O_rich_EF0": {
        "V_O_q0": formation_energy(E_vac_q0, E_pristine, mu_O_rich, 0, 0),
        "V_O_q+1": formation_energy(E_vac_q1, E_pristine, mu_O_rich, 1, 0),
        "V_O_q+2": formation_energy(E_vac_q2, E_pristine, mu_O_rich, 2, 0),
    },
    "formation_energies_O_poor_EF0": {
        "V_O_q0": formation_energy(E_vac_q0, E_pristine, mu_O_poor, 0, 0),
        "V_O_q+1": formation_energy(E_vac_q1, E_pristine, mu_O_poor, 1, 0),
        "V_O_q+2": formation_energy(E_vac_q2, E_pristine, mu_O_poor, 2, 0),
    },
    "transition_levels": {
        "+2/+1": eps_2_1,
        "+1/0": eps_1_0,
        "+2/0_thermodynamic": eps_2_0,
    },
    "band_gap_PBE": E_gap_PBE,
    "chemical_potentials": {
        "mu_O_rich": mu_O_rich,
        "mu_O_poor": mu_O_poor,
    },
    "notes": "No Freysoldt or other finite-size corrections applied. PBE underestimates band gap.",
}

with open(BASE / "full_results.json", "w") as f:
    json.dump(full_results, f, indent=2)
print(f"Full results saved to {BASE / 'full_results.json'}")
