#!/usr/bin/env bash
set -euo pipefail

ENV_NAME="matgl-agent"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
LAMMPS_ROOT="${PROJECT_ROOT}/lammps"
LAMMPS_SRC_DIR="${LAMMPS_ROOT}/lammps-src"
LAMMPS_BUILD_DIR="${LAMMPS_ROOT}/${ENV_NAME}"
LAMMPS_GIT_URL="https://github.com/lammps/lammps.git"

KOKKOS_ARCH_FLAG="${KOKKOS_ARCH_FLAG:-Kokkos_ARCH_AMPERE86}"
LAMMPS_REF="${LAMMPS_REF:-}"
LAMMPS_BUILD_JOBS="${LAMMPS_BUILD_JOBS:-16}"

for cmd in git cmake g++ mpicxx nvcc conda nvidia-smi; do
  command -v "${cmd}" >/dev/null 2>&1 || { echo "Missing: ${cmd}" >&2; exit 1; }
done

mkdir -p "${LAMMPS_ROOT}" "${LAMMPS_BUILD_DIR}"
if [[ ! -d "${LAMMPS_SRC_DIR}/.git" ]]; then
  git clone "${LAMMPS_GIT_URL}" "${LAMMPS_SRC_DIR}"
fi

if [[ -n "${LAMMPS_REF}" ]]; then
  git -C "${LAMMPS_SRC_DIR}" fetch --tags
  git -C "${LAMMPS_SRC_DIR}" checkout "${LAMMPS_REF}"
fi

PYTHON_EXECUTABLE="$(conda run -n "${ENV_NAME}" python -c 'import sys; print(sys.executable)')"
CYTHONIZE_EXECUTABLE="$(conda run -n "${ENV_NAME}" python -c 'import shutil; print(shutil.which("cythonize") or "")')"

if [[ -z "${CYTHONIZE_EXECUTABLE}" ]]; then
  echo "Missing cythonize in ${ENV_NAME}. Run: conda run -n ${ENV_NAME} python -m pip install cython" >&2
  exit 1
fi

cmake -S "${LAMMPS_SRC_DIR}/cmake" \
  -B "${LAMMPS_BUILD_DIR}" \
  -C "${LAMMPS_SRC_DIR}/cmake/presets/all_off.cmake" \
  -D BUILD_MPI=ON \
  -D BUILD_OMP=ON \
  -D PKG_KOKKOS=ON \
  -D Kokkos_ENABLE_CUDA=ON \
  -D "${KOKKOS_ARCH_FLAG}=ON" \
  -D PKG_ML-IAP=ON \
  -D PKG_ML-SNAP=ON \
  -D PKG_PYTHON=ON \
  -D MLIAP_ENABLE_PYTHON=ON \
  -D CMAKE_CXX_STANDARD=17 \
  -D CMAKE_CXX_COMPILER=mpicxx \
  -D CMAKE_CUDA_COMPILER=/usr/bin/nvcc \
  -D Cythonize_EXECUTABLE="${CYTHONIZE_EXECUTABLE}" \
  -D Python_EXECUTABLE="${PYTHON_EXECUTABLE}"

cmake --build "${LAMMPS_BUILD_DIR}" -j "${LAMMPS_BUILD_JOBS}"

echo "Done: ${LAMMPS_BUILD_DIR}/lmp"
