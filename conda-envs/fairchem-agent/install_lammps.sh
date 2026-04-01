#!/usr/bin/env bash
set -euo pipefail

ENV_NAME="fairchem-agent"
LAMMPS_CONDA_CHANNEL="${LAMMPS_CONDA_CHANNEL:-conda-forge}"

for cmd in conda; do
  command -v "${cmd}" >/dev/null 2>&1 || { echo "Missing: ${cmd}" >&2; exit 1; }
done

conda install -y -n "${ENV_NAME}" -c "${LAMMPS_CONDA_CHANNEL}" lammps
conda run -n "${ENV_NAME}" python -m pip install --upgrade "fairchem-core[extras]" fairchem-lammps

conda run -n "${ENV_NAME}" python -c "import fairchem; print('fairchem import OK')"
conda run -n "${ENV_NAME}" lmp -h >/dev/null
conda run -n "${ENV_NAME}" lmp_fc --help >/dev/null

echo "Done: use 'lmp' and 'lmp_fc' in ${ENV_NAME}"
