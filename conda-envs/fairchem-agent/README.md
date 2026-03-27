# FairChem Agent Environment

Minimal setup for FairChem simulations.

## 1) New Machine Setup

```bash
bash conda-envs/fairchem-agent/install.sh
bash conda-envs/fairchem-agent/install_lammps.sh
```

Creates `fairchem-agent` and installs `lmp` + `lmp_fc`.

## 2) Run FairChem Example

```bash
conda activate fairchem-agent
bash .agents/skills/mat-lammps-md/examples/fairchem/run_fairchem_co_cu111_adsorption.sh
```

## 3) Hugging Face Auth (if model access fails)

```bash
python -c "from huggingface_hub import login; login()"
```

## 4) Optional Verification

```bash
bash conda-envs/fairchem-agent/verify_install.sh
python conda-envs/fairchem-agent/verify_model_loading.py
```
