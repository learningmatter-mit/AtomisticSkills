#!/bin/bash
set -e

# NOTE: Activate environment BEFORE running this script!
# Ensure we are using the correct python
echo "Python: $(which python)"
echo "Torch: $(python -c 'import torch; print(torch.__version__)')"
echo "CUDA: $(nvcc --version | grep release)"

# Clean previous build dir if exists
if [ -d "dgl_source/build" ]; then
    echo "Cleaning build directory..."
    rm -rf dgl_source/build
fi

# Clone DGL if not exists (should exist)
if [ ! -d "dgl_source" ]; then
    echo "Cloning DGL..."
    git clone --recurse-submodules https://github.com/dmlc/dgl.git dgl_source
fi

cd dgl_source
# Ensure we are on master or compatible tag (master usually fine for latest torch)
# git checkout master 

# Create build dir
mkdir -p build
cd build

# CMake with CUDA
# Using the same MATH_LIBS path 
export MATH_LIBS="/opt/nvidia/hpc_sdk/Linux_aarch64/25.9/math_libs/13.0/targets/sbsa-linux"
export CMAKE_PREFIX_PATH=$MATH_LIBS:$CMAKE_PREFIX_PATH
export LD_LIBRARY_PATH=$MATH_LIBS/lib:$LD_LIBRARY_PATH
export CPATH=$MATH_LIBS/include:$CPATH
export CPLUS_INCLUDE_PATH=$MATH_LIBS/include:$CPLUS_INCLUDE_PATH

# Target architectures for GB10 (sm_120/121)
export TORCH_CUDA_ARCH_LIST="8.0 9.0 10.0 12.0"

echo "Configuring CMake..."
# Using Manual arch flags to prevent compute_50
cmake -DUSE_CUDA=ON -DCMAKE_CXX_FLAGS="-fPIC" \
      -DCMAKE_PREFIX_PATH="$MATH_LIBS" \
      -DCUDA_cublas_LIBRARY="$MATH_LIBS/lib/libcublas.so" \
      -DCUDA_cusparse_LIBRARY="$MATH_LIBS/lib/libcusparse.so" \
      -DCUDA_CUDART_LIBRARY="/opt/nvidia/hpc_sdk/Linux_aarch64/25.9/cuda/13.0/lib64/libcudart.so" \
      -DTORCH_CUDA_ARCH_LIST="8.0 9.0 10.0 12.0" \
      -DCUDA_ARCH_NAME=Manual \
      -DCUDA_ARCH_BIN="8.0 9.0 10.0 12.0" \
      -DCUDA_ARCH_PTX="12.0" \
      -DUSE_HUGECTR=OFF \
      -DBUILD_GRAPHBOLT=OFF \
      -DBUILD_SPARSE=OFF \
      ..

# Build
echo "Building libdgl..."
make -j8

# Manual install step
SITE_PACKAGES=$(python -c "import site; print(site.getsitepackages()[0])")
echo "Copying built library to $SITE_PACKAGES/dgl/libdgl.so"

# Ensure dgl python package is installed so usage works
cd ../python
pip install .

# Copy libdgl.so to correct location (pip install . might copy it if built, but we built independently?)
# pip install . usually calls setup.py which calls cmake/make internally OR uses existing?
# If we run pip install ., it might try to rebuild without our specific flags!
# BETTER: build libdgl.so manually (as we did), then copy it over the installed package.
# OR: DGL setup.py accepts cmake args?
# The safest robust method we found:
# 1. pip install . (installs python bindings and likely broken lib or no lib)
# 2. OVERWRITE libdgl.so with our successfully built one.

echo "Re-installing python bindings..."
pip install . 

echo "Overwriting libdgl.so with custom built version..."
cp ../build/libdgl.so "$SITE_PACKAGES/dgl/libdgl.so"

echo "DGL Build/Install for $(which python) Complete!"
