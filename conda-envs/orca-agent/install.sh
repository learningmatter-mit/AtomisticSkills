#!/bin/bash
set -e

# SCINE packages (scine-utilities-python, scine-readuct-python) are only
# available as pre-built binaries for x86_64 (linux-64, osx-64).
# There are no aarch64 builds on conda-forge or PyPI.
ARCH=$(uname -m)
if [[ "$ARCH" == "aarch64" || "$ARCH" == "arm64" ]]; then
    echo "ERROR: orca-agent environment requires x86_64 architecture."
    echo "       Current architecture: $ARCH"
    echo "       SCINE packages do not provide aarch64 binaries."
    echo "       To run on ARM, build SCINE from source: https://github.com/qcscine/utilities"
    exit 1
fi

conda env create -f core_env.yaml
