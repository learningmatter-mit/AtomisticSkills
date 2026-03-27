#!/bin/bash
set -e

# Get the directory of the script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

ENV_NAME=$(grep -e '^name:' core_env.yaml | awk '{print $2}')
echo "Creating Conda environment $ENV_NAME without pip dependencies..."

# Create a temporary yaml without the pip section
sed '/^[[:space:]]*- pip:/,$d' core_env.yaml > conda_only_env.yaml

conda env remove -n $ENV_NAME -y || true
conda env create -f conda_only_env.yaml

# Extract pip dependencies, remove quotes
sed -n '/^[[:space:]]*- pip:/,$p' core_env.yaml | grep -v 'pip:' | sed 's/^[[:space:]]*- //' | tr -d '"' | tr -d "'" > uv_requirements.txt

# Ensure uv is installed
if ! command -v uv &> /dev/null; then
    echo "Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.cargo/bin:$HOME/.local/bin:$PATH"
fi

# Activate and use uv
source $(conda info --base)/etc/profile.d/conda.sh
conda activate $ENV_NAME

echo "Installing pip dependencies with uv..."
uv pip install -r uv_requirements.txt

# Cleanup
rm conda_only_env.yaml uv_requirements.txt
echo "Environment $ENV_NAME created successfully!"
