---
name: chem-thermochemistry
description: Compute gas-phase thermodynamic quantities (H, S, G) and reaction thermochemistry (ΔH, ΔS, ΔG) using MLIPs with the ideal-gas/rigid-rotor/harmonic-oscillator approximation.
category: [chemistry]
---

# Gas-Phase Thermochemistry Skill

## Goal

Compute temperature-dependent thermodynamic quantities — enthalpy ($H$), entropy ($S$), and Gibbs free energy ($G$) — for gas-phase molecules, and reaction thermochemistry ($\Delta H$, $\Delta S$, $\Delta G$) for balanced chemical reactions, using Machine Learning Interatomic Potentials (MLIPs) with ASE's ideal-gas / rigid-rotor / harmonic-oscillator (IGRRHO) framework.

> [!IMPORTANT]
> This skill extends [chem-vibration](../chem-vibration/SKILL.md). It reuses the same MLIP-powered Hessian calculation and adds thermodynamic post-processing via `ase.thermochemistry.IdealGasThermo`.

## Background

The IGRRHO partition function decomposes into independent translational, rotational, vibrational, and electronic contributions:

$$q = q_\text{trans} \cdot q_\text{rot} \cdot q_\text{vib} \cdot q_\text{elec}$$

From the partition function, thermodynamic quantities at temperature $T$ and pressure $P$ are:
- **Enthalpy**: $H(T) = E_\text{pot} + E_\text{ZPE} + \sum_i \frac{h\nu_i}{e^{h\nu_i/k_BT}-1} + k_BT$ (+ rotational and translational terms)
- **Entropy**: $S(T,P) = S_\text{trans} + S_\text{rot} + S_\text{vib} + S_\text{elec}$
- **Gibbs free energy**: $G(T,P) = H(T) - TS(T,P)$

For a balanced reaction, $\Delta X = \sum_\text{products} n_i X_i - \sum_\text{reactants} n_j X_j$ where $X = H, S, G$.

## 1. Prerequisites

- An MLIP wrapper must be available (`MACEWrapper`, `MatGLWrapper`, or `FAIRCHEMWrapper`).
- ASE must be installed (provides `ase.thermochemistry.IdealGasThermo`).
- Structures must be **molecules or gas-phase species** (non-periodic).

## 2. Choosing a Foundation Potential

Refer to the [foundation-potentials skill](../ml-foundation-potentials/SKILL.md) for model selection.

> [!IMPORTANT]
> For molecular thermochemistry, use models with good force accuracy (e.g., `MACE-OMAT-0-small`, `MACE-MH-1` with `omol` head). Accurate forces are critical for reliable vibrational frequencies and thus thermodynamic quantities.

## 3. Calculation Workflow

### Single-Molecule Mode

Compute absolute H(T), S(T,P), G(T,P) for one species:

```bash
# Env: mace-agent
python .agents/skills/chem-thermochemistry/scripts/calculate_thermochemistry.py \
    --molecule H2O \
    --temperature 298.15 \
    --pressure 101325 \
    --model_type mace \
    --model_name MACE-OMAT-0-small \
    --output_dir research/my_folder/thermo
```

### Reaction Mode

Compute ΔH, ΔS, ΔG for a balanced gas-phase reaction:

```bash
# Env: mace-agent
python .agents/skills/chem-thermochemistry/scripts/calculate_thermochemistry.py \
    --reaction "2H2 + O2 -> 2H2O" \
    --temperature 298.15 \
    --model_type mace \
    --model_name MACE-OMAT-0-small \
    --output_dir research/my_folder/reaction_thermo
```

### Key Parameters

| Argument | Description |
|:---|:---|
| `--molecule` | ASE built-in molecule name (single species mode) |
| `--structure` | Path to structure file (single species mode) |
| `--reaction` | Balanced reaction string, e.g., `"2H2 + O2 -> 2H2O"` |
| `--temperature` | Temperature in K (default: 298.15) |
| `--pressure` | Pressure in Pa (default: 101325) |
| `--model_type` | MLIP backend: `mace`, `matgl`, `fairchem` |
| `--model_name` | Model name (e.g., `MACE-OMAT-0-small`) |
| `--spin` | Spin multiplicity override as `"name:value"` pairs (e.g., `"O2:1"`) |
| `--symmetry_number` | Symmetry number override as `"name:value"` pairs (e.g., `"H2:2"`) |
| `--fmax` | Force convergence for relaxation (default: 0.01 eV/Å) |
| `--output_dir` | Output directory |

## 4. Output Files

- `thermochemistry_results.json`: Full results including:
  - **Per species**: potential energy, ZPE, vibrational frequencies, H(T), S(T,P), G(T,P)
  - **Reaction** (if applicable): ΔH, ΔS, ΔG in both eV and kJ/mol
  - Metadata: temperature, pressure, model, spin, symmetry numbers

## 5. Examples

### H₂O Formation Reaction

See `examples/H2O_formation/` for the water formation reaction:

```bash
# Env: mace-agent
python .agents/skills/chem-thermochemistry/scripts/calculate_thermochemistry.py \
    --reaction "2H2 + O2 -> 2H2O" \
    --temperature 298.15 \
    --model_type mace \
    --model_name MACE-OMAT-0-small \
    --output_dir .agents/skills/chem-thermochemistry/examples/H2O_formation
```

**NIST reference values** for 2H₂(g) + O₂(g) → 2H₂O(g) at 298.15 K:
| Quantity | NIST Value |
|:---|:---|
| ΔH | −483.65 kJ/mol |
| ΔG | −457.22 kJ/mol |

## 6. Constraints

- **Gas-phase only**: This skill uses the ideal-gas approximation. Not applicable to condensed-phase or surface reactions.
- **Harmonic approximation**: Vibrational contributions assume harmonic potentials. Accuracy degrades for floppy modes and near dissociation.
- **Spin and symmetry**: The script includes a lookup table for common molecules, but exotic species may need manual `--spin` and `--symmetry_number` overrides.
- **Environments**: Scripts require conda environments with MLIP packages:
  - `mace-agent` for MACE models
  - `matgl-agent` for MatGL/CHGNet models
  - `fairchem-agent` for FairChem/UMA models

## References

- ASE Thermochemistry module: [ASE Documentation](https://wiki.fysik.dtu.dk/ase/ase/thermochemistry/thermochemistry.html)
- NIST-JANAF Thermochemical Tables: [NIST](https://janaf.nist.gov/)
- McQuarrie, D.A. "Statistical Mechanics", University Science Books, 2000.

---

**Author:** Bowen Deng  
**Contact:** [GitHub @bowen-bd](https://github.com/bowen-bd)
