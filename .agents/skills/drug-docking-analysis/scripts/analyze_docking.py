"""
Post-docking analysis: score distributions, enrichment metrics, and ligand efficiency.

Takes a docking results CSV (from drug-docking-vina's collect_results.py or equivalent)
and optionally a library CSV with labels (active/inactive) to compute enrichment.

Produces:
  - Score distribution KDE plot
  - Score vs. MW scatter (size bias visualization)
  - Ligand efficiency metrics (LE, BEI, SEI)
  - Enrichment analysis (ROC, AUC, EF) when labels are available
  - Summary JSON with all computed metrics

Usage:
    python analyze_docking.py \
        --docking_csv docking_ranked.csv \
        --output_dir docking_analysis/

    python analyze_docking.py \
        --docking_csv docking_ranked.csv \
        --library_csv library_master.csv \
        --active_label active \
        --inactive_label inactive \
        --output_dir docking_analysis/

Requirements:
    - Conda environment: drugdisc-agent
    - Required packages: rdkit, numpy, scipy, matplotlib
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.stats import gaussian_kde

from rdkit import Chem
from rdkit.Chem import Descriptors, Crippen


def compute_ligand_efficiency(smiles: str, score: float) -> dict:
    """Compute ligand efficiency metrics from a docking score and SMILES.

    Args:
        smiles: canonical SMILES string.
        score: Vina docking score in kcal/mol (negative).

    Returns:
        Dictionary with LE, BEI, SEI, MW, heavy atom count, cLogP.
    """
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return {"valid": False}

    ha = mol.GetNumHeavyAtoms()
    mw = Descriptors.MolWt(mol)
    clogp = Crippen.MolLogP(mol)

    le = -score / ha if ha > 0 else 0.0
    bei = -score * 1000.0 / mw if mw > 0 else 0.0
    sei = -score * 1000.0 / (Descriptors.TPSA(mol) or 1.0)

    return {
        "valid": True,
        "heavy_atoms": ha,
        "mw": round(mw, 2),
        "clogp": round(clogp, 2),
        "tpsa": round(Descriptors.TPSA(mol), 1),
        "le": round(le, 4),
        "bei": round(bei, 2),
        "sei": round(sei, 2),
    }


def compute_enrichment(labels: np.ndarray, scores: np.ndarray) -> dict:
    """Compute ROC AUC and enrichment factors from binary labels and scores.

    Args:
        labels: 1 for active, 0 for inactive.
        scores: higher = better predicted binding (negate Vina scores before calling).

    Returns:
        Dictionary with AUC, EF at various cutoffs, TPR/FPR arrays.
    """
    order = np.argsort(-scores)
    sorted_labels = labels[order]

    n_pos = int(labels.sum())
    n_neg = len(labels) - n_pos

    if n_pos == 0 or n_neg == 0:
        return {"error": "Need at least one active and one inactive for enrichment."}

    tpr = [0.0]
    fpr = [0.0]
    tp = fp = 0
    for lab in sorted_labels:
        if lab == 1:
            tp += 1
        else:
            fp += 1
        tpr.append(tp / n_pos)
        fpr.append(fp / n_neg)

    tpr = np.array(tpr)
    fpr = np.array(fpr)
    auc = float(np.trapezoid(tpr, fpr))

    def ef_at(pct):
        n = max(1, int(len(sorted_labels) * pct))
        top_actives = int(sorted_labels[:n].sum())
        expected = n_pos * pct
        return round(float(top_actives / expected), 3) if expected > 0 else 0.0

    return {
        "n_actives": n_pos,
        "n_inactives": n_neg,
        "auc": round(auc, 4),
        "ef_1pct": ef_at(0.01),
        "ef_2pct": ef_at(0.02),
        "ef_5pct": ef_at(0.05),
        "ef_10pct": ef_at(0.10),
        "ef_20pct": ef_at(0.20),
        "tpr": tpr.tolist(),
        "fpr": fpr.tolist(),
    }


def plot_score_kde(scores: np.ndarray, output_path: Path) -> None:
    """Plot docking score KDE."""
    fig, ax = plt.subplots(figsize=(4, 3.5))
    x_min, x_max = scores.min() - 1, scores.max() + 1
    x_range = np.linspace(x_min, x_max, 300)
    kde = gaussian_kde(scores, bw_method=0.3)

    ax.fill_between(x_range, kde(x_range), alpha=0.35, color="#2166ac")
    ax.plot(x_range, kde(x_range), color="#2166ac", lw=2)
    ax.set_xlabel("Vina docking score (kcal/mol)", fontsize=11)
    ax.set_ylabel("Density", fontsize=11)
    ax.tick_params(labelsize=9)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.set_xlim(x_min, x_max)
    ax.set_ylim(bottom=0)

    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.savefig(output_path.with_suffix(".pdf"), bbox_inches="tight")
    plt.close()


def plot_score_hist_kde(scores: np.ndarray, output_path: Path) -> None:
    """Plot docking score histogram with KDE overlay."""
    fig, ax = plt.subplots(figsize=(4.5, 3.5))
    x_min, x_max = scores.min() - 1, scores.max() + 1

    ax.hist(scores, bins=50, density=True, alpha=0.4, color="#2166ac", edgecolor="none")

    x_range = np.linspace(x_min, x_max, 300)
    kde = gaussian_kde(scores, bw_method=0.3)
    ax.plot(x_range, kde(x_range), color="#2166ac", lw=2)

    ax.set_xlabel("Vina docking score (kcal/mol)", fontsize=11)
    ax.set_ylabel("Density", fontsize=11)
    ax.tick_params(labelsize=9)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.set_xlim(x_min, x_max)
    ax.set_ylim(bottom=0)

    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.savefig(output_path.with_suffix(".pdf"), bbox_inches="tight")
    plt.close()


def plot_score_vs_mw(scores: np.ndarray, mws: np.ndarray, output_path: Path,
                     labels: np.ndarray | None = None) -> None:
    """Plot docking score vs. molecular weight to visualize size bias."""
    fig, ax = plt.subplots(figsize=(5, 4))

    if labels is not None:
        active_mask = labels == 1
        ax.scatter(mws[~active_mask], scores[~active_mask], alpha=0.4, s=20,
                   color="#b2182b", label="Inactive", zorder=2)
        ax.scatter(mws[active_mask], scores[active_mask], alpha=0.7, s=30,
                   color="#2166ac", label="Active", edgecolors="black", linewidths=0.5, zorder=3)
        ax.legend(fontsize=9, frameon=False)
    else:
        ax.scatter(mws, scores, alpha=0.5, s=20, color="#2166ac", zorder=2)

    ax.set_xlabel("Molecular weight (Da)", fontsize=11)
    ax.set_ylabel("Vina docking score (kcal/mol)", fontsize=11)
    ax.tick_params(labelsize=9)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.savefig(output_path.with_suffix(".pdf"), bbox_inches="tight")
    plt.close()


def plot_le_distribution(le_values: np.ndarray, output_path: Path) -> None:
    """Plot ligand efficiency KDE."""
    le_valid = le_values[np.isfinite(le_values) & (le_values > 0)]
    if len(le_valid) < 3:
        return

    fig, ax = plt.subplots(figsize=(4, 3.5))
    x_range = np.linspace(le_valid.min() - 0.05, le_valid.max() + 0.05, 200)
    kde = gaussian_kde(le_valid, bw_method=0.3)

    ax.fill_between(x_range, kde(x_range), alpha=0.35, color="#4393c3")
    ax.plot(x_range, kde(x_range), color="#4393c3", lw=2)
    ax.axvline(x=0.3, color="#999999", ls="--", lw=1, label="LE = 0.3 (rule of thumb)")
    ax.set_xlabel("Ligand efficiency (kcal/mol/HA)", fontsize=11)
    ax.set_ylabel("Density", fontsize=11)
    ax.legend(fontsize=8, frameon=False)
    ax.tick_params(labelsize=9)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.set_ylim(bottom=0)

    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.savefig(output_path.with_suffix(".pdf"), bbox_inches="tight")
    plt.close()


def plot_roc(enrichment: dict, output_path: Path) -> None:
    """Plot ROC curve from enrichment results."""
    tpr = np.array(enrichment["tpr"])
    fpr = np.array(enrichment["fpr"])
    auc = enrichment["auc"]

    fig, ax = plt.subplots(figsize=(4.5, 4.5))
    ax.plot(fpr, tpr, color="#2166ac", lw=2, label=f"Docking (AUC = {auc:.3f})")
    ax.plot([0, 1], [0, 1], "k--", lw=1, label="Random (AUC = 0.500)")
    ax.set_xlabel("False Positive Rate", fontsize=11)
    ax.set_ylabel("True Positive Rate", fontsize=11)
    ax.legend(loc="lower right", fontsize=9, frameon=False)
    ax.tick_params(labelsize=9)
    ax.set_xlim(-0.02, 1.02)
    ax.set_ylim(-0.02, 1.02)
    ax.set_aspect("equal")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.savefig(output_path.with_suffix(".pdf"), bbox_inches="tight")
    plt.close()


def plot_enrichment_factors(enrichment: dict, output_path: Path) -> None:
    """Plot enrichment factor bar chart."""
    cutoffs = ["1%", "2%", "5%", "10%", "20%"]
    efs = [enrichment["ef_1pct"], enrichment["ef_2pct"], enrichment["ef_5pct"],
           enrichment["ef_10pct"], enrichment["ef_20pct"]]

    fig, ax = plt.subplots(figsize=(4, 3.5))
    bars = ax.bar(cutoffs, efs, color="#4393c3", edgecolor="black", linewidth=0.5)
    ax.axhline(y=1.0, color="#999999", ls="--", lw=1, label="Random (EF = 1)")
    ax.set_xlabel("Top % of ranked list", fontsize=11)
    ax.set_ylabel("Enrichment factor", fontsize=11)
    ax.legend(fontsize=8, frameon=False)
    ax.tick_params(labelsize=9)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    for bar, ef in zip(bars, efs):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.1,
                f"{ef:.1f}x", ha="center", va="bottom", fontsize=8)

    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.savefig(output_path.with_suffix(".pdf"), bbox_inches="tight")
    plt.close()


def aggregate_microstates(
    docking_rows: list[dict],
    parent_id_col: str,
) -> list[dict]:
    """Collapse microstates to best-score-per-parent.

    When protomers/tautomers were enumerated during ligand prep, the same
    parent compound appears multiple times in the docking CSV under
    different compound_ids. Ranking or computing enrichment over the raw
    microstates double-counts compounds with more enumerated forms, so
    aggregate to the best (most negative) score per parent before any
    downstream metric.
    """
    best_per_parent: dict[str, dict] = {}
    missing_parent = 0
    for row in docking_rows:
        parent = row.get(parent_id_col) or row.get("compound_id")
        if not row.get(parent_id_col):
            missing_parent += 1
        try:
            score = float(row["best_affinity"])
        except (KeyError, ValueError, TypeError):
            continue
        existing = best_per_parent.get(parent)
        if existing is None or score < float(existing["best_affinity"]):
            best_per_parent[parent] = row
    if missing_parent:
        print(
            f"Warning: {missing_parent} rows had no '{parent_id_col}' value; "
            f"treated as their own parents.",
            file=sys.stderr,
        )
    return list(best_per_parent.values())


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Post-docking analysis: score distributions, enrichment, ligand efficiency."
    )
    parser.add_argument("--docking_csv", required=True, type=Path,
                        help="Docking results CSV with compound_id, best_affinity, smiles columns.")
    parser.add_argument("--library_csv", type=Path, default=None,
                        help="Library CSV with compound_id and label columns (for enrichment).")
    parser.add_argument("--active_label", default="active",
                        help="Label string for actives in library CSV (default: active).")
    parser.add_argument("--inactive_label", default="inactive",
                        help="Label string for inactives in library CSV (default: inactive).")
    parser.add_argument("--parent_id_col", default=None,
                        help="Column name holding the parent compound ID. When set, "
                             "microstates are collapsed to best-score-per-parent before "
                             "computing ligand efficiency, enrichment, and plots. Use this "
                             "when the library contained enumerated protomers/tautomers.")
    parser.add_argument("--output_dir", required=True, type=Path,
                        help="Output directory for plots and results.")
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    plots_dir = args.output_dir / "plots"
    plots_dir.mkdir(exist_ok=True)

    # Load docking results
    docking = []
    with open(args.docking_csv) as f:
        for row in csv.DictReader(f):
            docking.append(row)

    print(f"Loaded {len(docking)} docking results")

    if args.parent_id_col:
        n_before = len(docking)
        docking = aggregate_microstates(docking, args.parent_id_col)
        print(
            f"Aggregated microstates by '{args.parent_id_col}': "
            f"{n_before} rows -> {len(docking)} parent compounds"
        )

    # Load labels if available
    label_map = {}
    if args.library_csv and args.library_csv.exists():
        with open(args.library_csv) as f:
            for row in csv.DictReader(f):
                label_map[row["compound_id"]] = row.get("label", "")

    # Compute ligand efficiency for each compound
    results = []
    for row in docking:
        cid = row["compound_id"]
        score = float(row["best_affinity"])
        smiles = row.get("smiles", "")
        label = row.get("label", "") or label_map.get(cid, "")

        le_data = compute_ligand_efficiency(smiles, score) if smiles else {"valid": False}

        results.append({
            "compound_id": cid,
            "label": label,
            "docking_score": score,
            "smiles": smiles,
            **{k: v for k, v in le_data.items()},
        })

    # Arrays for plotting
    scores = np.array([r["docking_score"] for r in results])
    mws = np.array([r.get("mw", 0) for r in results])
    les = np.array([r.get("le", 0) for r in results])

    # Score distributions
    print("Plotting score distribution...")
    plot_score_kde(scores, plots_dir / "score_kde.png")
    plot_score_hist_kde(scores, plots_dir / "score_hist_kde.png")

    # Score vs MW
    print("Plotting score vs. MW...")
    has_labels = any(r["label"] in (args.active_label, args.inactive_label) for r in results)
    if has_labels:
        plot_labels = np.array([1 if r["label"] == args.active_label else 0
                                for r in results if r["label"] in (args.active_label, args.inactive_label)])
        plot_scores = np.array([r["docking_score"] for r in results
                                if r["label"] in (args.active_label, args.inactive_label)])
        plot_mws = np.array([r.get("mw", 0) for r in results
                             if r["label"] in (args.active_label, args.inactive_label)])
        plot_score_vs_mw(plot_scores, plot_mws, plots_dir / "score_vs_mw.png", labels=plot_labels)
    else:
        plot_score_vs_mw(scores, mws, plots_dir / "score_vs_mw.png")

    # Ligand efficiency distribution
    print("Plotting ligand efficiency...")
    plot_le_distribution(les, plots_dir / "le_distribution.png")

    # Enrichment (only if labels available)
    enrichment = None
    if has_labels:
        print("Computing enrichment...")
        enrich_labels = np.array([1 if r["label"] == args.active_label else 0
                                  for r in results if r["label"] in (args.active_label, args.inactive_label)])
        enrich_scores = np.array([-r["docking_score"] for r in results
                                  if r["label"] in (args.active_label, args.inactive_label)])
        enrichment = compute_enrichment(enrich_labels, enrich_scores)

        if "error" not in enrichment:
            print(f"  AUC: {enrichment['auc']:.3f}")
            print(f"  EF1%: {enrichment['ef_1pct']:.1f}x  EF5%: {enrichment['ef_5pct']:.1f}x  EF10%: {enrichment['ef_10pct']:.1f}x")

            plot_roc(enrichment, plots_dir / "roc_curve.png")
            plot_enrichment_factors(enrichment, plots_dir / "enrichment_factors.png")

    # Write enriched results CSV
    out_fields = ["compound_id", "label", "docking_score", "mw", "clogp", "tpsa",
                  "heavy_atoms", "le", "bei", "sei", "smiles"]
    csv_path = args.output_dir / "docking_analysis.csv"
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=out_fields, extrasaction="ignore")
        writer.writeheader()
        for r in results:
            writer.writerow(r)

    # Summary JSON
    summary = {
        "n_compounds": len(results),
        "microstate_aggregation": {
            "enabled": bool(args.parent_id_col),
            "parent_id_col": args.parent_id_col,
        },
        "score_mean": round(float(scores.mean()), 3),
        "score_std": round(float(scores.std()), 3),
        "score_min": round(float(scores.min()), 3),
        "score_max": round(float(scores.max()), 3),
        "le_mean": round(float(les[les > 0].mean()), 4) if np.any(les > 0) else None,
        "le_median": round(float(np.median(les[les > 0])), 4) if np.any(les > 0) else None,
    }
    if enrichment and "error" not in enrichment:
        summary["enrichment"] = {
            "auc": enrichment["auc"],
            "ef_1pct": enrichment["ef_1pct"],
            "ef_2pct": enrichment["ef_2pct"],
            "ef_5pct": enrichment["ef_5pct"],
            "ef_10pct": enrichment["ef_10pct"],
            "ef_20pct": enrichment["ef_20pct"],
            "n_actives": enrichment["n_actives"],
            "n_inactives": enrichment["n_inactives"],
        }

    summary_path = args.output_dir / "analysis_summary.json"
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=4)

    print(f"\nResults written to {args.output_dir}")
    print(json.dumps(summary, indent=4))

    # Save input configs for reproducibility
    from src.utils.config_utils import save_skill_inputs
    save_skill_inputs(args, args.output_dir)


if __name__ == "__main__":
    main()
