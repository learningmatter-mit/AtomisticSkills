---
name: drug-retrosynthesis
description: Predict synthetic accessibility and retrosynthetic pathways for novel molecules using the IBM RXN API.
category: drug-discovery
---

# drug-retrosynthesis

## Goal
To predict the retrosynthetic pathways and synthetic accessibility of novel small molecules (such as undocumented fluorinated gases) using the state-of-the-art transformer models provided by IBM RXN for Chemistry.

## Instructions

### 1. Identify Target Molecule
Ensure you have the valid canonical SMILES string for the target material or chemical you wish to synthesize.

### 2. Set Up the IBM RXN Environment
Because IBM RXN is a cloud-hosted API, you must have an API Key.
1. Sign up for a free IBM RXN account at https://rxn.res.ibm.com/
2. Generate an API Key in your user profile.
3. Export the key in your terminal session before running the skill script:

```bash
export RXN_API_KEY="your-api-key-here"
```

### 3. Run Retrosynthesis Evaluation
Use the wrapper script to submit the SMILES string to the IBM RXN API. The script will poll the server and return the predicted pathway and a confidence score for synthetic feasibility.

```bash
# Env: drugdisc-agent
python .agents/skills/drug-retrosynthesis/scripts/evaluate_ibm_rxn.py "target_smiles" --steps 3
```

## Examples

Evaluating the synthetic pathway for a fluorinated gas analog (e.g., 2,3,3,3-tetrafluoropropene: `FC(F)(F)C(F)=C`):
```bash
# Env: drugdisc-agent
export RXN_API_KEY="api-key-here"
python .agents/skills/drug-retrosynthesis/scripts/evaluate_ibm_rxn.py "FC(F)(F)C(F)=C" --steps 3
```

## Constraints
- **Environments**: Requires the `drugdisc-agent` conda environment.
- **Dependencies**: The script relies on the `rxn4chemistry` python library (`pip install rxn4chemistry`). If not installed, the script will gracefully exit with instructions.
- **Rate Limits**: The IBM RXN free tier has API limits. Do not use this in a high-throughput loop for thousands of molecules without a premium tier.
- **Sourcing Constraints**: This tool does not directly check commercial availability of the proposed precursors. You must manually verify if the starting materials proposed by IBM RXN are commercially available.

## References
- Schwaller, P. et al., "Predicting retrosynthetic pathways using a combined linguistic model and hyper-graph exploration strategy," *Chemical Science*, 2020. [DOI:10.1039/C9SC05033H](https://doi.org/10.1039/c9sc05033h)
- IBM RXN for Chemistry: https://rxn.res.ibm.com/

---

**Author:** Sathya Edamadaka  
**Contact:** [GitHub @snme](https://github.com/snme)
