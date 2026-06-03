#!/usr/bin/env python3
"""
Si doping & point-defect test project pipeline.

Env: mace-agent (relaxation), base-agent (defect generation & energy calc)
Run from repo root or this directory.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

# Repo root (AtomisticSkills)
PROJECT_DIR = Path(__file__).resolve().parent
REPO_ROOT = PROJECT_DIR.parents[1]
sys.path.insert(0, str(REPO_ROOT))

STRUCTURES = PROJECT_DIR / "structures"
RESULTS = PROJECT_DIR / "results"
DEFECT_STRUCTS = STRUCTURES / "defect_structures"
BULK_RELAX = RESULTS / "bulk_relaxation"
PRISTINE_RELAX = RESULTS / "pristine_relaxation"
DEFECT_RELAX = RESULTS / "defect_relaxations"
ENERGIES_JSON = RESULTS / "defect_energies.json"
ANALYSIS_MD = RESULTS / "ANALYSIS.md"

SUPERCELL = [3, 3, 3]
MODEL_NAME = "MACE-MH-1"
TASK_NAME = "matpes_r2scan"
ELEM_ENERGIES = (
    REPO_ROOT
    / ".agents/skills/mat-elemental-energies/resources/MACE-MH-1_matpes_r2scan_energies.json"
)

GENERATE_DEFECTS_SIMPLE = PROJECT_DIR / "generate_defects_simple.py"
CALC_ENERGY = (
    REPO_ROOT / ".agents/skills/mat-defect-energy/scripts/calculate_defect_energy.py"
)


def _conda_python(env: str) -> str:
    base = os.environ.get("CONDA_PREFIX", "")
    if Path(base).name == env:
        return sys.executable
    for root in (
        Path.home() / "mambaforge",
        Path.home() / "miniforge3",
        Path.home() / "miniconda3",
    ):
        py = root / "envs" / env / "bin" / "python"
        if py.is_file():
            return str(py)
    return "python"


def step_fetch() -> Path:
    """Fetch lowest-energy Si structure from Materials Project (base-agent)."""
    STRUCTURES.mkdir(parents=True, exist_ok=True)
    out_cif = STRUCTURES / "Si_mp.cif"
    print("=== Step: fetch Si from Materials Project ===")

    fetch_script = PROJECT_DIR / "_fetch_si.py"
    fetch_script.write_text(
        f'''import json, os, sys
sys.path.insert(0, {repr(str(REPO_ROOT))})
from src.utils.config_utils import inject_config_into_env
inject_config_into_env()
from mp_api.client import MPRester
api_key = os.environ["MP_API_KEY"]
out_cif = {repr(str(out_cif))}
meta_path = {repr(str(STRUCTURES / "Si_mp_metadata.json"))}
with MPRester(api_key) as mpr:
    docs = mpr.materials.summary.search(
        formula="Si",
        fields=["material_id", "formula_pretty", "energy_above_hull", "structure"],
    )
docs = sorted(docs, key=lambda d: d.energy_above_hull or 0.0)
best = docs[0]
best.structure.to(filename=out_cif)
meta = {{"material_id": str(best.material_id), "formula": best.formula_pretty,
         "energy_above_hull": best.energy_above_hull}}
with open(meta_path, "w") as f:
    json.dump(meta, f, indent=2)
print(f"Saved {{out_cif}} ({{meta['material_id']}})")
'''
    )
    py = _conda_python("base-agent")
    subprocess.run([py, str(fetch_script)], check=True, cwd=str(REPO_ROOT))
    fetch_script.unlink(missing_ok=True)
    with open(STRUCTURES / "Si_mp_metadata.json") as f:
        meta = json.load(f)
    print(f"  {out_cif} ({meta['material_id']}, Ehull={meta['energy_above_hull']})")
    return out_cif


def step_relax_bulk(device: str = "cpu") -> Path:
    """Relax bulk primitive Si."""
    print("=== Step: relax bulk Si ===")
    si_cif = STRUCTURES / "Si_mp.cif"
    if not si_cif.exists():
        step_fetch()

    from src.utils.mlips.mace.mace_wrapper import MACEWrapper

    BULK_RELAX.mkdir(parents=True, exist_ok=True)
    wrapper = MACEWrapper(model_name=MODEL_NAME, device=device, head=TASK_NAME)
    wrapper.load()
    res = wrapper.relax_structure(
        structure_data=str(si_cif),
        fmax=0.01,
        relax_cell=True,
        output_dir=str(BULK_RELAX),
    )
    if res.get("error"):
        raise RuntimeError(res["error"])
    print(f"  Bulk relaxed → {BULK_RELAX}")
    return BULK_RELAX / "relaxed_structure.cif"


def step_generate_defects() -> None:
    """Generate P@Si, B@Si, vacancy, and Si interstitial supercells."""
    print("=== Step: generate defect supercells ===")
    bulk_cif = BULK_RELAX / "relaxed_structure.cif"
    if not bulk_cif.exists():
        step_relax_bulk()

    py = _conda_python("base-agent")
    subprocess.run(
        [
            py,
            str(GENERATE_DEFECTS_SIMPLE),
            "--bulk",
            str(bulk_cif),
            "--supercell_size",
            *[str(x) for x in SUPERCELL],
            "--output",
            str(DEFECT_STRUCTS),
        ],
        check=True,
        cwd=str(REPO_ROOT),
    )
    print(f"  Defect CIFs → {DEFECT_STRUCTS}")
    for p in sorted(DEFECT_STRUCTS.glob("*.cif")):
        print(f"    {p.name}")


def step_relax_defects(device: str = "cpu") -> None:
    """Relax pristine supercell and all defect structures (fixed cell)."""
    print("=== Step: relax pristine + defects ===")
    pristine = DEFECT_STRUCTS / "pristine_supercell.cif"
    if not pristine.exists():
        step_generate_defects()

    from src.utils.mlips.mace.mace_wrapper import MACEWrapper

    wrapper = MACEWrapper(model_name=MODEL_NAME, device=device, head=TASK_NAME)
    wrapper.load()

    PRISTINE_RELAX.mkdir(parents=True, exist_ok=True)
    wrapper.relax_structure(
        structure_data=str(pristine),
        fmax=0.02,
        relax_cell=False,
        output_dir=str(PRISTINE_RELAX),
    )
    print(f"  Pristine → {PRISTINE_RELAX}")

    DEFECT_RELAX.mkdir(parents=True, exist_ok=True)
    defect_cifs = [
        p
        for p in DEFECT_STRUCTS.glob("*.cif")
        if p.name != "pristine_supercell.cif"
    ]
    for cif in defect_cifs:
        out = DEFECT_RELAX / cif.stem
        wrapper.relax_structure(
            structure_data=str(cif),
            fmax=0.02,
            relax_cell=False,
            output_dir=str(out),
        )
        print(f"  Relaxed {cif.name} → {out}")


def step_energies() -> None:
    """Compute formation energies."""
    print("=== Step: formation energies ===")
    py = _conda_python("base-agent")
    cmd = [
        py,
        str(CALC_ENERGY),
        "--bulk_dir",
        str(PRISTINE_RELAX),
        "--defect_dir",
        str(DEFECT_RELAX),
        "--supercell_size",
        *[str(x) for x in SUPERCELL],
        "--elemental_energies",
        str(ELEM_ENERGIES),
        "--output",
        str(ENERGIES_JSON),
    ]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    subprocess.run(cmd, check=True, cwd=str(REPO_ROOT), env=env)
    print(f"  Saved {ENERGIES_JSON}")


def step_summary() -> None:
    """Write ANALYSIS.md from defect_energies.json."""
    print("=== Step: summary ===")
    if not ENERGIES_JSON.exists():
        step_energies()

    with open(ENERGIES_JSON) as f:
        data = json.load(f)

    defects = data.get("defects", [])
    if not defects:
        raise RuntimeError("No defects in energies file")

    lines = [
        "# Si Point-Defect Analysis (MLIP)",
        "",
        f"**Model:** {MODEL_NAME} (`{TASK_NAME}`)  ",
        f"**Supercell:** {SUPERCELL[0]}×{SUPERCELL[1]}×{SUPERCELL[2]}  ",
        f"**Chemical potentials:** elemental reservoir (`MACE-MH-1_matpes_r2scan_energies.json`)",
        "",
        "## Formation energies (neutral)",
        "",
        "| Rank | Defect | E_f (eV) | Δn (species change) |",
        "|------|--------|----------|---------------------|",
    ]
    for i, d in enumerate(defects, 1):
        dn = ", ".join(f"{k}:{v}" for k, v in d.get("delta_n", {}).items()) or "—"
        lines.append(
            f"| {i} | `{d['name']}` | {d['formation_energy_eV']:.3f} | {dn} |"
        )

    lowest = defects[0]
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            f"**Lowest formation energy:** `{lowest['name']}` "
            f"({lowest['formation_energy_eV']:.3f} eV) under the elemental chemical-potential "
            "reference used here.",
            "",
            "### Doping (substitutional)",
            "- **P@Si** — n-type donor (extra electron in band-gap engineering picture).",
            "- **B@Si** — p-type acceptor.",
            "",
            "Compare their E_f to decide which substitutional dopant is more "
            "favorable to incorporate at neutral charge state in this MLIP model.",
            "",
            "### Implant damage (native defects)",
            "- **Si vacancy (V_Si)** — common displacement damage product.",
            "- **Si self-interstitial (Si_i)** — Frenkel partner to vacancies.",
            "",
            "After implantation, the crystal often contains both V and Si_i. "
            "If E_f(V) + E_f(Si_i) is large compared to pristine Si, "
            "annealing provides thermodynamic driving force for **Frenkel recombination** "
            "(V + Si_i → bulk Si), reducing defect density.",
            "",
            "Substitutional dopants that remain after anneal are those with **low E_f** "
            "relative to competing native defects, and sufficient kinetic access during RTA.",
            "",
            "### Caveats",
            "- Neutral defects only; real dopants are charged (use DFT for transition levels).",
            "- MLIP E_f are **trends**, not experimental formation enthalpies.",
            "- No implant cascade — this is equilibrium defect thermodynamics on a fixed supercell.",
            "",
            "## Raw data",
            "",
            f"See `{ENERGIES_JSON.relative_to(PROJECT_DIR)}`.",
            "",
        ]
    )

    ANALYSIS_MD.parent.mkdir(parents=True, exist_ok=True)
    ANALYSIS_MD.write_text("\n".join(lines))
    print(f"  Wrote {ANALYSIS_MD}")


STEPS = {
    "fetch": lambda **kw: step_fetch(),
    "relax_bulk": step_relax_bulk,
    "generate_defects": lambda **kw: step_generate_defects(),
    "relax_defects": step_relax_defects,
    "energies": lambda **kw: step_energies(),
    "summary": lambda **kw: step_summary(),
    "all": None,
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Si doping defect project pipeline")
    parser.add_argument(
        "--step",
        default="all",
        choices=list(STEPS.keys()),
        help="Pipeline step to run",
    )
    parser.add_argument(
        "--device",
        default="cpu",
        help="MACE device (cpu recommended on Mac)",
    )
    args = parser.parse_args()

    os.chdir(PROJECT_DIR)
    STRUCTURES.mkdir(parents=True, exist_ok=True)
    RESULTS.mkdir(parents=True, exist_ok=True)

    if args.step == "all":
        step_fetch()
        step_relax_bulk(device=args.device)
        step_generate_defects()
        step_relax_defects(device=args.device)
        step_energies()
        step_summary()
        print("\n=== Pipeline complete ===")
        print(f"Results: {RESULTS}")
        print(f"Report:  {ANALYSIS_MD}")
        return

    fn = STEPS[args.step]
    if args.step in ("relax_bulk", "relax_defects"):
        fn(device=args.device)
    else:
        fn()


if __name__ == "__main__":
    main()
