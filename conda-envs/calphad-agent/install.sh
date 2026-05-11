#!/bin/bash
# install.sh for calphad-agent

ENV_NAME="calphad-agent"

# Try mamba first, fallback to conda
if command -v mamba &> /dev/null; then
    CONDA_EXE="mamba"
else
    CONDA_EXE="conda"
fi

echo "Creating Conda environment $ENV_NAME using $CONDA_EXE..."

$CONDA_EXE env remove -n $ENV_NAME -y || true
$CONDA_EXE env create -f core_env.yaml

echo "Environment $ENV_NAME successfully created!"
echo "To activate, run: conda activate $ENV_NAME"
