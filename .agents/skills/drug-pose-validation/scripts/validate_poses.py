"""
Validate docked or generated ligand poses for physical plausibility using PoseBusters.

Reads an SDF of poses (and optionally a receptor PDB), runs PoseBusters checks on
each pose, writes a JSON report and an SDF of valid poses.

Usage:
    python validate_poses.py --poses docked.sdf --receptor protein.pdb --output_dir validation/
    python validate_poses.py --poses docked.sdf --output_dir validation/

Requirements:
    - Conda environment: drugdisc-agent
    - Required packages: posebusters, rdkit
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from rdkit import Chem


def run_validation(
    poses_path: Path,
    receptor_path: Path | None,
    output_dir: Path,
) -> dict:
    """
    Run PoseBusters validation on an SDF of poses.

    Args:
        poses_path: Path to SDF file with ligand poses.
        receptor_path: Optional path to receptor PDB for clash checks.
        output_dir: Directory to write results.

    Returns:
        Dictionary with validation summary and per-pose results.
    """
    from posebusters import PoseBusters

    output_dir.mkdir(parents=True, exist_ok=True)

    if receptor_path is not None:
        buster = PoseBusters(config="dock")
        bust_kwargs = dict(
            mol_pred=str(poses_path),
            mol_true=None,
            mol_cond=str(receptor_path),
        )
    else:
        buster = PoseBusters(config="mol")
        bust_kwargs = dict(mol_pred=str(poses_path))

    # Single bust call with full_report=True (superset of full_report=False).
    # We separate test vs. diagnostic columns using the config.
    df_full = buster.bust(**bust_kwargs, full_report=True)

    # Identify which columns are pass/fail tests (vs. extra diagnostics).
    # Each module in the config lists its test outputs in chosen_binary_test_output,
    # mapped through rename_outputs, then normalized: lower() + replace(" ", "_").
    test_col_set = set()
    for module in buster.config.get("modules", []):
        rename = module.get("rename_outputs", {})
        for key in module.get("chosen_binary_test_output", []):
            display_name = rename.get(key, key)
            test_col_set.add(display_name.lower().replace(" ", "_"))

    per_pose = []
    valid_indices = []

    for i, (_, row) in enumerate(df_full.iterrows()):
        test_results = {}
        diagnostics = {}

        for col in df_full.columns:
            val = row[col]
            if isinstance(val, bool):
                bool_val = val
            elif hasattr(val, "item"):
                bool_val = bool(val.item())
            else:
                continue

            diagnostics[col] = bool_val
            if col in test_col_set:
                test_results[col] = bool_val

        all_passed = all(test_results.values()) if test_results else False

        per_pose.append({
            "pose_index": i,
            "valid": all_passed,
            "tests": test_results,
            "diagnostics": diagnostics,
        })

        if all_passed:
            valid_indices.append(i)

    n_input = len(per_pose)
    n_valid = len(valid_indices)

    # Write valid poses to SDF
    valid_sdf_path = output_dir / "valid_poses.sdf"
    suppl = Chem.SDMolSupplier(str(poses_path), removeHs=False)
    if len(suppl) != n_input:
        raise RuntimeError(
            f"PoseBusters returned {n_input} rows but SDF has {len(suppl)} molecules. "
            f"Index alignment is unreliable; aborting."
        )
    writer = Chem.SDWriter(str(valid_sdf_path))
    for i, mol in enumerate(suppl):
        if mol is not None and i in valid_indices:
            writer.write(mol)
    writer.close()

    report = {
        "n_poses_input": n_input,
        "n_poses_valid": n_valid,
        "pass_rate": round(n_valid / n_input, 4) if n_input > 0 else 0.0,
        "receptor_used": receptor_path is not None,
        "per_pose": per_pose,
    }

    report_path = output_dir / "validation_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=4, default=str)

    # human-readable summary
    summary_path = output_dir / "summary.txt"
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write(f"Pose Validation Summary\n")
        f.write(f"{'='*40}\n")
        f.write(f"Input poses:  {n_input}\n")
        f.write(f"Valid poses:  {n_valid}\n")
        f.write(f"Pass rate:    {report['pass_rate']:.1%}\n")
        f.write(f"Receptor:     {'yes' if receptor_path else 'no'}\n\n")
        for entry in per_pose:
            status = "PASS" if entry["valid"] else "FAIL"
            f.write(f"Pose {entry['pose_index']}: {status}\n")
            failed = [k for k, v in entry["tests"].items() if isinstance(v, bool) and not v]
            if failed:
                f.write(f"  Failed: {', '.join(failed)}\n")

    print(f"Validation complete: {n_valid}/{n_input} poses passed")
    print(f"  Report:      {report_path}")
    print(f"  Valid poses:  {valid_sdf_path}")
    print(f"  Summary:      {summary_path}")

    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate docked poses for physical plausibility using PoseBusters."
    )
    parser.add_argument(
        "--poses",
        required=True,
        help="SDF file containing ligand poses to validate.",
    )
    parser.add_argument(
        "--receptor",
        default=None,
        help="Optional receptor PDB for protein-ligand clash checks.",
    )
    parser.add_argument(
        "--output_dir",
        required=True,
        help="Directory to write validation results.",
    )
    args = parser.parse_args()

    poses_path = Path(args.poses)
    if not poses_path.exists():
        print(f"ERROR: Poses file not found: {poses_path}", file=sys.stderr)
        sys.exit(1)

    receptor_path = None
    if args.receptor:
        receptor_path = Path(args.receptor)
        if not receptor_path.exists():
            print(f"ERROR: Receptor file not found: {receptor_path}", file=sys.stderr)
            sys.exit(1)

    output_dir = Path(args.output_dir)
    run_validation(poses_path, receptor_path, output_dir)

    # Save input configs for reproducibility
    from src.utils.config_utils import save_skill_inputs
    save_skill_inputs(args, args.output_dir)


if __name__ == "__main__":
    main()
