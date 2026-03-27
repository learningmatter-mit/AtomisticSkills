#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../../../../.." && pwd)"

# Env: mace-agent
# Thermal quench example for Na2Si3O7.

OUT_DIR="${OUT_DIR:-./out-mace-na2si3o7-quench}"
LMP_BIN="${LMP_BIN:-${PROJECT_ROOT}/lammps/mace-agent/lmp}"
INPUT_STRUCTURE="${INPUT_STRUCTURE:-}"
MODEL_FILE="${MODEL_FILE:-}"
MODEL_CHECKPOINT="${MODEL_CHECKPOINT:-}"
MACE_MODEL_NAME="${MACE_MODEL_NAME:-MACE-MP-medium}"
MACE_HEAD="${MACE_HEAD:-}"

mkdir -p "${OUT_DIR}"

if [[ -z "${INPUT_STRUCTURE}" ]]; then
  INPUT_STRUCTURE="${OUT_DIR}/na2si3o7_initial.cif"
  python "${SCRIPT_DIR}/generate_na2si3o7_structure.py" --out "${INPUT_STRUCTURE}"
fi

if [[ -z "${MODEL_FILE}" ]]; then
    MODEL_FILE="${OUT_DIR}/mace_auto-lammps.pt"
fi

if [[ ! -f "${MODEL_FILE}" ]]; then
  MODEL_FILE="${MODEL_FILE}" \
  MODEL_CHECKPOINT="${MODEL_CHECKPOINT}" \
  MACE_MODEL_NAME="${MACE_MODEL_NAME}" \
  MACE_HEAD="${MACE_HEAD}" \
  python - <<'PY'
import os
from pathlib import Path

import torch
from e3nn.util import jit
from mace.calculators import LAMMPS_MACE
from mace.calculators.foundations_models import download_mace_mp_checkpoint

model_file = Path(os.environ["MODEL_FILE"])
model_checkpoint = os.environ.get("MODEL_CHECKPOINT", "").strip()
model_name = os.environ.get("MACE_MODEL_NAME", "MACE-MP-medium").strip()
head_override = os.environ.get("MACE_HEAD", "").strip()

# Keep this mapping local so the script works outside repo PYTHONPATH.
model_aliases = {
    "MACE-MP-small": "small",
    "MACE-MP-medium": "medium",
    "MACE-MP-large": "large",
    "MACE-MP-small-0b": "small-0b",
    "MACE-MP-medium-0b": "medium-0b",
    "MACE-MP-small-0b2": "small-0b2",
    "MACE-MP-medium-0b2": "medium-0b2",
    "MACE-MP-large-0b2": "large-0b2",
    "MACE-MP-medium-0b3": "medium-0b3",
    "MACE-MPA-0": "medium-mpa-0",
    "MACE-OMAT-0-small": "small-omat-0",
    "MACE-OMAT-0-medium": "medium-omat-0",
    "MACE-MATPES-PBE-0": "mace-matpes-pbe-0",
    "MACE-MATPES-R2SCAN-0": "mace-matpes-r2scan-0",
    "MACE-MH-1": "https://huggingface.co/mace-foundations/mace-mh-1/resolve/main/mace-mh-1.model",
    "MACE-MH-0": "https://huggingface.co/mace-foundations/mace-mh-0/resolve/main/mace-mh-0.model",
}

if not model_checkpoint:
    model_key = model_name
    if Path(model_key).exists():
        model_checkpoint = model_key
    else:
        mapped = model_aliases.get(model_key, model_key)
        try:
            model_checkpoint = download_mace_mp_checkpoint(mapped)
        except Exception as exc:
            raise SystemExit(
                f"Could not resolve MODEL_CHECKPOINT from MACE_MODEL_NAME='{model_name}'. "
                "Set MODEL_CHECKPOINT or MODEL_FILE explicitly."
            ) from exc

checkpoint_path = Path(model_checkpoint)
if not checkpoint_path.exists():
    raise SystemExit(f"Resolved checkpoint does not exist: {checkpoint_path}")

model = torch.load(checkpoint_path, map_location=torch.device("cpu"))
model = model.double().to("cpu")

heads = list(getattr(model, "heads", [None]))
if head_override:
    selected_head = head_override
elif len(heads) <= 1:
    selected_head = heads[0] if heads else None
elif "omat_pbe" in heads:
    selected_head = "omat_pbe"
else:
    selected_head = heads[-1]

lammps_model = (
    LAMMPS_MACE(model, head=selected_head)
    if selected_head is not None
    else LAMMPS_MACE(model)
)
compiled = jit.compile(lammps_model)
model_file.parent.mkdir(parents=True, exist_ok=True)
compiled.save(model_file)
print(f"Wrote {model_file} from {checkpoint_path} (head={selected_head})")
PY
fi

python - <<PY
from ase.io import read
from ase.io.lammpsdata import write_lammps_data

atoms = read("${INPUT_STRUCTURE}")
write_lammps_data("${OUT_DIR}/na2si3o7_initial.data", atoms, atom_style="atomic", masses=True)
PY

cp "${SCRIPT_DIR}/in.na2si3o7_quench_mace" \
   "${OUT_DIR}/in.na2si3o7_quench_mace"

"${LMP_BIN}" \
  -in "${OUT_DIR}/in.na2si3o7_quench_mace" \
  -var datafile "${OUT_DIR}/na2si3o7_initial.data" \
  -var outdir "${OUT_DIR}" \
  -var model_file "${MODEL_FILE}" \
  -log "${OUT_DIR}/log.lammps"

echo "Finished. Inspect:"
echo "  ${OUT_DIR}/log.lammps"
echo "  ${OUT_DIR}/na2si3o7_quench.lammpstrj"
echo "  ${OUT_DIR}/na2si3o7_glass_final.data"
