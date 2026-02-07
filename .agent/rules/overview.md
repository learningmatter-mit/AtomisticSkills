---
trigger: always_on
---

# machine learning interatomic potential (mlip) agent project guide

## Project Overview
In this project, we plan to have a code infrastructure that handles machine learning interatomic potentials (MLIPs) loading, testing and fine-tuning. The Atoms-fine-tuning requires users' natural language input, and through the LLM agent's interpretation of the simulation task, selecting foundation MLIPs and generate material structures for testing and fine-tuning. The fine-tuning process will be conducted automatically, in the fashion of auto-ML.

The MLIP-agent consists of the following parts:

## A large language model agent for determining the computation task and triggers submodules.

This should be a LLM agent implemented through langchain, the users can provide LLM API keys for the response.
The users' request is something like:
*  "I want to calculate the melting temperature of Ag-Li alloy"
*  "Fine-tune a MLIP to calculate the adsorption energy of H2 on Pb-Cu surface"
* "What are the stable phases in the Li-Fe-Cl phase diagram? Can the machine learning potential calculate this?"

The model's decision involves the following steps:

## Step-by-Step Fine-tuning Workflow

The fine-tuning process is broken down into distinct steps that can be run in different conda environments:

### Step 1: Source Structure Generation
**Environment**: Any (LLM agent environment)
**Input**: User's natural language query
**Output**: 1 initial structure
**Description**: 
- Query Materials Project API for inorganic materials
- Use RDKit to generate organic molecules from SMILES strings
- Use materials generative models for hypothetical materials
- Accept user-provided structures directly

### Step 2: Structure Sampling
**Environment**: Any (sampling environment)
**Input**: 1 initial structure
**Output**: List of structures for training
**Description**:
- Use PES sampler to generate structural variations
- Apply different sampling methods (MD, NEB, random displacements, etc.)
- Generate diverse configurations for robust training

### Step 3: Label Acquisition
**Environment**: DFT environment or expensive MLIP environment
**Input**: List of structures
**Output**: List of structures with energy, forces, and stress labels
**Description**:
- Run DFT calculations (VASP, PySCF, etc.) with settings matching foundation potential
- Alternatively, use expensive MLIPs like UMA for rapid labeling
- Parse and format results for MLIP training

### Step 4: MLIP Fine-tuning
**Environment**: Specific MLIP environment (matgl-agent, mace-agent, or fairchem-agent)
**Input**: List of structures with labels
**Output**: Fine-tuned MLIP checkpoint
**Description**:
- Load foundation model
- Fine-tune on labeled data using framework-specific training pipeline
- Save checkpoint for later use
- Generate training history plots

### Workflow Integration
1. Determining what is most relevant foundation MLIPs that should be adopted for this calculation task
2. Depending the simulation task, trigger a sampling function to generate material/molecule configurations that can be calculated to acquire DFT labels for testing and fine-tuning the model's performance.
3. Writes DFT input files for calculating the sampled material/molecule configurations. Note that the DFT softwares (like VASP or pyscf, etc) and corresponding DFT settings need to be set to match the pre-training labels of the foundation potential been selected. Then the user can submit the DFT calculation with their computation resource. Note that the submission script the agent writes should also involve ways to parse and collect the DFT results in to minimal data file.
4. After the DFT is completed, the agent need to transform DFT results into labels that are compatible to the chosen foundation potential. Note the foundation potential typically require very different data formats.
5. Trigger the fine-tuning of the MLIP. We should provided default trainer with standard training parameters from the documentation of corresponding foundation potential. Return the training history in a csv file.

## Foundation Potential Library
The LLM agent should decide which foundation potential to be used based on the users' input task type. This is mostly related to what pretrained chemistry in the foundation potentials are.

### Environment Setup
The main agent is under `conda activate base-agent`
Each foundation potential uses separate conda environments to avoid dependency conflicts:

1. **MatGL Environment**: `conda activate matgl-agent`
   - For MatGL models (M3GNet, CHGNet, TensorNet)
   - Includes PyTorch 2.2.0, DGL, and MatGL dependencies

2. **MACE Environment**: `conda activate mace-agent` 
   - For MACE models (MACE-MP, MACE-MATPES, MACE-MPA series)
   - Includes PyTorch 2.4.1, e3nn, and MACE dependencies

3. **FAIRCHEM Environment**: `conda activate fairchem-agent`
   - For FAIRCHEM models (UMA, ESEN series)
   - Includes FAIRCHEM-core and related dependencies

### Environment Creation
```bash
# Create MatGL environment
conda env create -f conda-envs/matgl-environment.yml

# Create MACE environment  
conda env create -f conda-envs/mace-environment.yml

# Create FAIRCHEM environment
conda env create -f conda-envs/fairchem-environment.yml
```

### Testing Requirements
Write tests for the following tasks:
1. The pretrained checkpoints of these foundation potentials can be loaded.
2. ASE Calculator can be created from the pretrained checkpoints, and can be used to calculate energy of a toy material/molecule.
3. The pretrained model can be fine-tuned for a toy dataset, and the resulted checkpoints are saved properly.
4. The fine-tuned model can be loaded into a ASECalculator

## Data Augmenter
The data augmenter function involves functions to sample the desired region of the potential energy surface (PES) described by the MLIP. This can be done by by several sub-components:

### Getting the initial material
Based on the user's input text, the LLM should first query or generate the target material for further sampling.

There are a few cases:
* If the user is interested in an inorganic material, try to search the material from the materials project API. If the material does not exist in the Materials Project, the agent can call a materials generative model to generate a hypothetical material.
* If the user is interested in an organic material, the agent should search for the organic molecule/proteins or create the smile strings and then use RDKit to convert the smile string to 3-dimensional ASE atoms.
* If the target system is even more complex, i.e. a electrode interface with organic molecule on one side and solid material on the other side, the agent to return a warning, and provide the option to test solely on a simpler subset of the simulation, i.e. only the solid material in the simulation setup. The combined simulation and data augmentation is prohibited at the moment because most pretrained MLIPs are not good enough to handle a mixture of inorganic and organic materials.
* Alternatively, the user can directly provide the 3-dimensional structure of the material in the prompt, and the agent can use this to construct the initial material data object.

### Perform sampling

## MLIP Label Preparation

### Prepare DFT inputs
After collecting the list of structures from the sampling step, the agent should prepare the structures into DFT-ready formats for the submission of DFT calculations. This involves determining the compatible calculation type of the foundation potential and writing the job script. At this stage we can pass the DFT calculation to users.

### Collect the DFT labels
This step involves parsing the raw DFT outputs to the formats that are supported by the foundation potential been used.

## Quick Start

### Installation
1. Clone the repository
2. Create the required conda environments:
   ```bash
   conda env create -f conda-envs/matgl-environment.yml
   conda env create -f conda-envs/mace-environment.yml
   conda env create -f conda-envs/fairchem-environment.yml
   ```
3. Activate the appropriate environment for your task:
   ```bash
   conda activate matgl-agent  # For MatGL models
   conda activate mace-agent  # For MACE models
   conda activate fairchem-agent  # For FAIRCHEM models
   ```

### Basic Usage
```python
from mlip_agent.models.matgl_wrapper import MatGLWrapper
from mlip_agent.models.mace_wrapper import MACEWrapper
from mlip_agent.models.fairchem_wrapper import FAIRCHEMWrapper

# Example: Load a MatGL model
wrapper = MatGLWrapper(model_name="M3GNet")
wrapper.load_pretrained()
calculator = wrapper.create_calculator()
```

## Main Features

- **Multi-Framework Support**: MACE, MatGL, and FAIRCHEM foundation models
- **Automatic Model Selection**: LLM-based selection of appropriate models for specific tasks
- **Fine-tuning Capabilities**: Automated fine-tuning with proper data format conversion
- **DFT Integration**: Seamless integration with DFT calculations for training data generation

## Development Guide

### Testing
Run tests for each environment:
```bash
# Test MatGL
conda activate matgl-agent
python -m pytest tests/test_matgl_wrapper.py -v

# Test MACE
conda activate mace-agent
python -m pytest tests/test_mace_wrapper.py -v

# Test FAIRCHEM
conda activate fairchem-agent
python -m pytest tests/test_fairchem_wrapper.py -v
```