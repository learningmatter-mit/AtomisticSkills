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
conda env create -f conda_only_env.yaml -y

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

# Clone VOID library
VOID_DIR="$HOME/projects/AtomisticSkills/VOID"
if [ ! -d "$VOID_DIR" ]; then
    echo "Cloning VOID repository to $VOID_DIR ..."
    git clone https://github.com/learningmatter-mit/VOID.git "$VOID_DIR"
else
    echo "VOID directory already exists at $VOID_DIR"
fi

# Install VOID into the environment
echo "Installing VOID package..."
cd "$VOID_DIR"
# The script uses uv pip install
uv pip install -e .

# Cleanup
cd "$SCRIPT_DIR"
rm conda_only_env.yaml uv_requirements.txt
echo "Environment $ENV_NAME created successfully!"
