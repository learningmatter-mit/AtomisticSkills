#!/usr/bin/env bash
set -euo pipefail

ENV_NAME="mace-agent"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
LAMMPS_ROOT="${PROJECT_ROOT}/lammps"
LAMMPS_SRC_DIR="${LAMMPS_ROOT}/lammps-src-mace"
LAMMPS_BUILD_DIR="${LAMMPS_ROOT}/${ENV_NAME}"
LAMMPS_GIT_URL="${LAMMPS_GIT_URL:-https://github.com/ACEsuit/lammps.git}"
LAMMPS_REF="${LAMMPS_REF:-mace}"
LAMMPS_BUILD_JOBS="${LAMMPS_BUILD_JOBS:-16}"
CLEAN_BUILD="${CLEAN_BUILD:-1}"

for cmd in git cmake g++ mpicxx conda; do
  command -v "${cmd}" >/dev/null 2>&1 || { echo "Missing: ${cmd}" >&2; exit 1; }
done

mkdir -p "${LAMMPS_ROOT}" "${LAMMPS_BUILD_DIR}"
if [[ ! -d "${LAMMPS_SRC_DIR}/.git" ]]; then
  git clone --branch "${LAMMPS_REF}" --depth 1 "${LAMMPS_GIT_URL}" "${LAMMPS_SRC_DIR}"
fi

git -C "${LAMMPS_SRC_DIR}" fetch --tags
git -C "${LAMMPS_SRC_DIR}" checkout "${LAMMPS_REF}"

PYTHON_EXECUTABLE="$(conda run -n "${ENV_NAME}" python -c 'import sys; print(sys.executable)')"
TORCH_CMAKE_PREFIX="$(conda run -n "${ENV_NAME}" python -c 'import torch; print(torch.utils.cmake_prefix_path)')"
ENV_PREFIX="$(conda run -n "${ENV_NAME}" python -c 'import sys; print(sys.prefix)')"

if [[ -z "${TORCH_CMAKE_PREFIX}" ]]; then
  echo "Torch CMake prefix not found in ${ENV_NAME}" >&2
  exit 1
fi

conda install -y -n "${ENV_NAME}" -c conda-forge mkl-devel

if [[ "${CLEAN_BUILD}" == "1" ]]; then
  rm -rf "${LAMMPS_BUILD_DIR}"
  mkdir -p "${LAMMPS_BUILD_DIR}"
fi

cmake -S "${LAMMPS_SRC_DIR}/cmake" \
  -B "${LAMMPS_BUILD_DIR}" \
  -D CMAKE_BUILD_TYPE=Release \
  -D BUILD_MPI=ON \
  -D BUILD_OMP=ON \
  -D PKG_OPENMP=ON \
  -D PKG_ML-MACE=ON \
  -D CMAKE_CXX_STANDARD=17 \
  -D CMAKE_CXX_COMPILER=mpicxx \
  -D Python_EXECUTABLE="${PYTHON_EXECUTABLE}" \
  -D CMAKE_PREFIX_PATH="${TORCH_CMAKE_PREFIX};${ENV_PREFIX}" \
  -D MKL_ROOT="${ENV_PREFIX}"

cmake --build "${LAMMPS_BUILD_DIR}" -j "${LAMMPS_BUILD_JOBS}"

LMP_HELP_OUTPUT="$("${LAMMPS_BUILD_DIR}/lmp" -h 2>&1 || true)"
if [[ "${LMP_HELP_OUTPUT}" != *"ML-MACE"* ]]; then
  echo "ML-MACE not detected in lmp -h output." >&2
  exit 1
fi

echo "Done: ${LAMMPS_BUILD_DIR}/lmp"
