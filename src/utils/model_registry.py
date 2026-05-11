"""
MLIP Model Registry — persistent store of fine-tuned model checkpoints.

The registry lives at ~/.config/atomistic_skills/model_registry.yaml and is
shared across all projects on the same machine.  Every fine-tuned MLIP should
be registered here so future research tasks can discover and reuse it instead
of retraining from scratch.

Registry entry schema
---------------------
id              : str   — unique human-readable key, e.g. "mace-LiFePO4-v1"
backend         : str   — "mace" | "matgl" | "fairchem"
base_model      : str   — foundation checkpoint name (e.g. "MACE-MH-1")
chemical_system : str   — sorted, hyphen-joined elements (e.g. "Fe-Li-O-P")
description     : str   — free-text summary of training data / purpose
training_date   : str   — ISO date "YYYY-MM-DD"
checkpoint_path : str   — absolute path to the saved model file
performance     : dict  — {energy_mae: float [meV/atom], force_mae: float [meV/Å]}
research_dir    : str   — relative path to the research directory where it was trained
tags            : list  — optional keyword tags
notes           : str   — optional free-text notes
"""

from __future__ import annotations

import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

# Registry file location — follows the same config-dir convention as config_utils.py
REGISTRY_PATH = Path.home() / ".config" / "atomistic_skills" / "model_registry.yaml"


# ---------------------------------------------------------------------------
# Low-level I/O
# ---------------------------------------------------------------------------

def _load_raw() -> Dict[str, Any]:
    """Load raw registry dict from disk; return empty structure if missing."""
    if not REGISTRY_PATH.exists():
        return {"models": []}
    with open(REGISTRY_PATH, "r") as f:
        data = yaml.safe_load(f) or {}
    if "models" not in data:
        data["models"] = []
    return data


def _save_raw(data: Dict[str, Any]) -> None:
    """Persist registry dict to disk."""
    REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(REGISTRY_PATH, "w") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalise_chemsys(chemsys: str) -> str:
    """Sort and deduplicate elements in a hyphen-separated chemical system string.

    Examples
    --------
    >>> _normalise_chemsys("Li-Fe-P-O")
    'Fe-Li-O-P'
    >>> _normalise_chemsys("O-Li")
    'Li-O'
    """
    elements = [e.strip() for e in chemsys.split("-") if e.strip()]
    return "-".join(sorted(set(elements)))


def _chemsys_elements(chemsys: str) -> set:
    return set(e.strip() for e in chemsys.split("-") if e.strip())


def _generate_id(backend: str, chemical_system: str, existing_ids: List[str]) -> str:
    """Auto-generate a unique model id like 'mace-FeLiOP-v1'."""
    elements_compact = "".join(sorted(_chemsys_elements(chemical_system)))
    base = f"{backend}-{elements_compact}"
    version = 1
    candidate = f"{base}-v{version}"
    while candidate in existing_ids:
        version += 1
        candidate = f"{base}-v{version}"
    return candidate


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def register_model(
    checkpoint_path: str,
    chemical_system: str,
    backend: str,
    base_model: str,
    description: str = "",
    energy_mae: Optional[float] = None,
    force_mae: Optional[float] = None,
    research_dir: str = "",
    tags: Optional[List[str]] = None,
    notes: str = "",
    model_id: Optional[str] = None,
) -> str:
    """Add a fine-tuned model to the registry.

    Parameters
    ----------
    checkpoint_path : absolute path to the model checkpoint file.
    chemical_system : elements covered, e.g. "Li-Fe-P-O" (order does not matter).
    backend         : "mace", "matgl", or "fairchem".
    base_model      : name of the foundation model that was fine-tuned.
    description     : short human-readable summary.
    energy_mae      : validation energy MAE in meV/atom (optional).
    force_mae       : validation force  MAE in meV/Å  (optional).
    research_dir    : path to the research directory where training was run.
    tags            : list of keyword tags for filtering (optional).
    notes           : any additional free-text notes.
    model_id        : explicit id; auto-generated if omitted.

    Returns
    -------
    The id of the registered model.
    """
    backend = backend.lower().strip()
    if backend not in {"mace", "matgl", "fairchem"}:
        raise ValueError(f"backend must be 'mace', 'matgl', or 'fairchem'; got '{backend}'")

    norm_chemsys = _normalise_chemsys(chemical_system)

    data = _load_raw()
    existing_ids = [m.get("id", "") for m in data["models"]]

    if model_id is None:
        model_id = _generate_id(backend, norm_chemsys, existing_ids)
    elif model_id in existing_ids:
        raise ValueError(
            f"Model id '{model_id}' already exists in the registry. "
            "Choose a different id or omit it for auto-generation."
        )

    entry: Dict[str, Any] = {
        "id": model_id,
        "backend": backend,
        "base_model": base_model,
        "chemical_system": norm_chemsys,
        "description": description,
        "training_date": datetime.now().strftime("%Y-%m-%d"),
        "checkpoint_path": str(Path(checkpoint_path).expanduser().resolve()),
        "performance": {},
        "research_dir": research_dir,
        "tags": tags or [],
        "notes": notes,
    }

    if energy_mae is not None:
        entry["performance"]["energy_mae"] = round(float(energy_mae), 4)
    if force_mae is not None:
        entry["performance"]["force_mae"] = round(float(force_mae), 4)

    data["models"].append(entry)
    _save_raw(data)
    return model_id


def search_models(
    chemical_system: Optional[str] = None,
    backend: Optional[str] = None,
    max_energy_mae: Optional[float] = None,
    max_force_mae: Optional[float] = None,
    tags: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """Search the registry and return matching model entries.

    Matching logic
    --------------
    chemical_system : the model must cover **all** requested elements (subset match).
                      E.g. searching "Li-O" will match a model trained on "Fe-Li-O-P".
    backend         : exact match (case-insensitive).
    max_energy_mae  : model's energy_mae must be ≤ this value (meV/atom).
    max_force_mae   : model's force_mae  must be ≤ this value (meV/Å).
    tags            : model must have **all** requested tags.
    """
    data = _load_raw()
    results = []

    requested_elements = _chemsys_elements(chemical_system) if chemical_system else None
    requested_tags = set(tags) if tags else None
    norm_backend = backend.lower().strip() if backend else None

    for entry in data.get("models", []):
        # --- element filter ---
        if requested_elements is not None:
            model_elements = _chemsys_elements(entry.get("chemical_system", ""))
            if not requested_elements.issubset(model_elements):
                continue

        # --- backend filter ---
        if norm_backend is not None:
            if entry.get("backend", "").lower() != norm_backend:
                continue

        # --- performance filter ---
        perf = entry.get("performance", {})
        if max_energy_mae is not None and perf.get("energy_mae") is not None:
            if perf["energy_mae"] > max_energy_mae:
                continue
        if max_force_mae is not None and perf.get("force_mae") is not None:
            if perf["force_mae"] > max_force_mae:
                continue

        # --- tag filter ---
        if requested_tags is not None:
            model_tags = set(entry.get("tags", []))
            if not requested_tags.issubset(model_tags):
                continue

        # Verify checkpoint still exists on disk
        ckpt = entry.get("checkpoint_path", "")
        entry_copy = dict(entry)
        entry_copy["checkpoint_exists"] = Path(ckpt).exists() if ckpt else False
        results.append(entry_copy)

    return results


def get_model(model_id: str) -> Optional[Dict[str, Any]]:
    """Return a single registry entry by id, or None if not found."""
    data = _load_raw()
    for entry in data.get("models", []):
        if entry.get("id") == model_id:
            entry_copy = dict(entry)
            ckpt = entry.get("checkpoint_path", "")
            entry_copy["checkpoint_exists"] = Path(ckpt).exists() if ckpt else False
            return entry_copy
    return None


def list_models() -> List[Dict[str, Any]]:
    """Return all registry entries."""
    return search_models()


def delete_model(model_id: str) -> bool:
    """Remove a model from the registry by id. Returns True if found and removed."""
    data = _load_raw()
    before = len(data["models"])
    data["models"] = [m for m in data["models"] if m.get("id") != model_id]
    if len(data["models"]) < before:
        _save_raw(data)
        return True
    return False


# ---------------------------------------------------------------------------
# Formatting helpers (used by MCP tools)
# ---------------------------------------------------------------------------

def _format_entry(entry: Dict[str, Any]) -> str:
    """Render a single registry entry as a human-readable markdown block."""
    perf = entry.get("performance", {})
    e_mae = f"{perf['energy_mae']} meV/atom" if "energy_mae" in perf else "N/A"
    f_mae = f"{perf['force_mae']} meV/Å"    if "force_mae"  in perf else "N/A"
    ckpt_status = "✓ exists" if entry.get("checkpoint_exists") else "✗ missing"
    tags = ", ".join(entry.get("tags", [])) or "—"

    return (
        f"### {entry['id']}\n"
        f"- **Backend / Base model**: {entry.get('backend','?')} / {entry.get('base_model','?')}\n"
        f"- **Chemical system**: {entry.get('chemical_system','?')}\n"
        f"- **Description**: {entry.get('description','—')}\n"
        f"- **Training date**: {entry.get('training_date','?')}\n"
        f"- **Checkpoint**: `{entry.get('checkpoint_path','?')}` ({ckpt_status})\n"
        f"- **Performance**: energy MAE = {e_mae}, force MAE = {f_mae}\n"
        f"- **Research dir**: {entry.get('research_dir','—')}\n"
        f"- **Tags**: {tags}\n"
        f"- **Notes**: {entry.get('notes','—')}\n"
    )
