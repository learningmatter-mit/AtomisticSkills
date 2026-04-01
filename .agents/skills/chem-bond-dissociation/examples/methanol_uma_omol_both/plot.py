"""
Plot BDE comparison for methanol (CO) using FairChem UMA (uma-s-1p1, omol task).
Shows homolytic vs heterolytic BDE for all bonds. Heterolytic is only available
for heavy-atom bonds where both fragments have > 1 atom.

# Env: fairchem-agent
"""
import json
import sys
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.size": 11,
    "axes.labelsize": 12,
    "axes.labelweight": "bold",
    "xtick.labelsize": 10,
    "ytick.labelsize": 10,
    "legend.fontsize": 10,
})

EXAMPLE_DIR = os.path.dirname(__file__)
DATA_FILE = os.path.join(EXAMPLE_DIR, "bde_results.json")
OUT_FILE = os.path.join(EXAMPLE_DIR, "bde_comparison.png")

with open(DATA_FILE) as f:
    data = json.load(f)

# Build per-bond records
bonds = []
for b in data["bonds"]:
    if b.get("skipped"):
        continue
    syms = b["atom_symbols"]
    idxs = b["atom_indices"]
    label = f"{syms[0]}–{syms[1]}\n({idxs[0]}-{idxs[1]})"
    homo = b.get("bde_kcal_mol")
    hetero = b.get("heterolytic_bde_kcal_mol")
    variants = b.get("heterolytic_variants", [])
    bonds.append({
        "label": label,
        "bond_type": f"{syms[0]}-{syms[1]}",
        "homo": homo,
        "hetero": hetero,
        "variant_A_val": variants[0]["bde_kcal_mol"] if len(variants) > 0 else None,
        "variant_B_val": variants[1]["bde_kcal_mol"] if len(variants) > 1 else None,
        "variant_A_lbl": variants[0]["variant"] if len(variants) > 0 else "",
        "variant_B_lbl": variants[1]["variant"] if len(variants) > 1 else "",
        "frag1_formula": b.get("frag1_formula", ""),
        "frag2_formula": b.get("frag2_formula", ""),
        "heterolytic_best_variant": b.get("heterolytic_best_variant"),
    })

labels = [b["label"] for b in bonds]
x = np.arange(len(labels))
width = 0.35

# Separate bonds with and without heterolytic
has_hetero = [b for b in bonds if b["hetero"] is not None]
no_hetero = [b for b in bonds if b["hetero"] is None]

fig, axes = plt.subplots(1, 2, figsize=(13, 5))

# ── Left panel: Homo vs Hetero ─────────────────────────────────────────────
ax = axes[0]

homo_vals = [b["homo"] for b in bonds]
hetero_vals_all = [b["hetero"] if b["hetero"] is not None else 0 for b in bonds]
has_hi = [b["hetero"] is not None for b in bonds]

bars1 = ax.bar(x - width/2, homo_vals, width, label="Homolytic (radical)",
               color="#1565C0", alpha=0.88, zorder=3)
bars2 = ax.bar(x + width/2, hetero_vals_all, width, label="Heterolytic (ionic)",
               color=["#E65100" if h else "#BDBDBD" for h in has_hi],
               alpha=0.88, zorder=3)

for bar, val in zip(bars1, homo_vals):
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 2, f"{val:.0f}",
            ha="center", va="bottom", fontsize=9, fontweight="bold")

for bar, val, h in zip(bars2, hetero_vals_all, has_hi):
    if h:
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 2, f"{val:.0f}",
                ha="center", va="bottom", fontsize=9, color="#BF360C", fontweight="bold")
    else:
        ax.text(bar.get_x() + bar.get_width()/2, 5, "N/A\n(single atom)",
                ha="center", va="bottom", fontsize=7.5, color="#757575", style="italic")

# Annotate delta for bonds that have both
for xi, b in zip(x, bonds):
    if b["hetero"] is not None:
        diff = b["hetero"] - b["homo"]
        ax.annotate(
            f"Δ={diff:+.1f}",
            xy=(xi, max(b["homo"], b["hetero"]) + 13),
            ha="center", fontsize=9, color="#4A148C", fontweight="bold"
        )

ax.set_xticks(x)
ax.set_xticklabels(labels)
ax.set_ylabel("BDE (kcal/mol)", fontweight="bold")
ax.set_title("Methanol: Homolytic vs Heterolytic BDE\n(FairChem UMA uma-s-1p1, omol task)", fontweight="bold")
# Custom legend
from matplotlib.patches import Patch
legend_elements = [
    Patch(color="#1565C0", alpha=0.88, label="Homolytic (radical)"),
    Patch(color="#E65100", alpha=0.88, label="Heterolytic (ionic, best variant)"),
    Patch(color="#BDBDBD", alpha=0.88, label="Heterolytic N/A (single-atom fragment)"),
]
ax.legend(handles=legend_elements, framealpha=0.8, fontsize=9)
ax.set_ylim(0, max(homo_vals + [v for v in hetero_vals_all if v > 0]) * 1.22)
ax.yaxis.grid(True, alpha=0.3, zorder=0)
ax.set_axisbelow(True)

# ── Right panel: C-O bond both polarity variants ───────────────────────────
ax2 = axes[1]
co_bond = next((b for b in bonds if "C" in b["bond_type"] and "O" in b["bond_type"] and b["hetero"] is not None), None)

if co_bond:
    categories = ["Neutral radical\n(homolytic)", "Best ionic\n(heterolytic)", 
                  f"Variant A\n{co_bond['variant_A_lbl']}", f"Variant B\n{co_bond['variant_B_lbl']}"]
    vals = [co_bond["homo"], co_bond["hetero"],
            co_bond["variant_A_val"], co_bond["variant_B_val"]]
    colors = ["#1565C0", "#E65100", "#AD1457", "#6A1B9A"]

    xi = np.arange(len(categories))
    bars = ax2.bar(xi, vals, color=colors, alpha=0.88, width=0.55, zorder=3)

    for bar, val in zip(bars, vals):
        ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1.5, f"{val:.1f}",
                 ha="center", va="bottom", fontsize=11, fontweight="bold")

    # Highlight the best variant
    best_idx = 2 if co_bond["heterolytic_best_variant"] == co_bond["variant_A_lbl"] else 3
    bars[best_idx].set_edgecolor("gold")
    bars[best_idx].set_linewidth(2.5)

    ax2.set_xticks(xi)
    ax2.set_xticklabels(categories, fontsize=9)
    ax2.set_ylabel("BDE (kcal/mol)", fontweight="bold")
    ax2.set_title(f"C–O Bond: All Cleavage Modes\n({co_bond['frag1_formula']} / {co_bond['frag2_formula']})", fontweight="bold")
    ax2.set_ylim(0, max(vals) * 1.2)
    ax2.yaxis.grid(True, alpha=0.3, zorder=0)
    ax2.set_axisbelow(True)

    # Annotate key delta
    ax2.annotate(
        f"Δ = {co_bond['hetero'] - co_bond['homo']:+.1f} kcal/mol\n(vs homolytic)",
        xy=(1, co_bond["hetero"]), xytext=(0.8, co_bond["hetero"] + 12),
        fontsize=9, color="#4A148C", fontweight="bold",
        arrowprops=dict(arrowstyle="->", color="#4A148C"),
    )
    
    # Note about best variant (gold border)
    ax2.text(0.97, 0.03, "★ gold border = best heterolytic variant",
             transform=ax2.transAxes, ha="right", fontsize=8.5, color="#8B7500", style="italic")

fig.suptitle("Methanol BDE: FairChem UMA omol (uma-s-1p1)\nDemonstrating charge/spin-aware heterolytic cleavage",
             fontsize=12, fontweight="bold", y=1.01)
plt.tight_layout()
plt.savefig(OUT_FILE, dpi=150, bbox_inches="tight")
print(f"Saved: {OUT_FILE}")
