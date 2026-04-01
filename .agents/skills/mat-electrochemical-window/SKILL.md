---
name: mat-electrochemical-window
description: Calculate the intrinsic electrochemical stability window (ECW) of a material using standard phase diagram thermodynamic methods.
category: [materials]
---

# Electrochemical Stability Window (ECW) Calculation

## Goal
To determine the intrinsic electrochemical stability window (ECW) of a material, specifically bounding the reduction ($V_{\text{red}}$) and oxidation ($V_{\text{ox}}$) potentials against a mobile working ion (e.g., Li/Li+), using a standard zero-Kelvin phase diagram.

This explicitly implements the standard thermodynamic approach for solid electrolytes defined in:
*Zhu, Y., He, X. & Mo, Y. "Origin of Outstanding Stability in the Lithium Solid Electrolyte Materials: Insights from Thermodynamic Analyses Based on First-Principles Calculations". ACS Appl. Mater. Interfaces 7, 23685–23693 (2015).*

> [!TIP]
> **Coupling with Stability**: ECW calculation relies entirely on the same generic computed energies and `PhaseDiagram` used for determining $E_{hull}$. You can uniquely combine this with the [mat-stability](../mat-stability/SKILL.md) skill to calculate both intrinsic thermodynamic stability and electrochemical stability in the same step using the same unified convex hull.

## Methodology

The electrochemical stability window of a phase represents the voltage range over which it is thermodynamically stable against reduction by (e.g., lithiation) or oxidation (e.g., delithiation) of the target ion. 

In `pymatgen`, this exact analytical bounding is extracted using `PhaseDiagram.get_transition_chempots(mobile_element)`. 

1. **Calculate Global Phase Diagram boundaries**: For the composition of the target phase, identifying the critical chemical potentials ($\mu_{\text{Li}}$) where stable facets on the phase diagram intersect.
2. **Identify the stable Region**: Evaluating an intermediary point in each discrete chemical potential band on the `GrandPotentialPhaseDiagram` to check if the exact composition is structurally present on the extended hull. If the material is metastable (E_hull > 0), its intrinsic ECW is always exactly `[0.0 V, 0.0 V]`.
3. **Reference Scale Conversion**: The bounds are translated from absolute chemical potentials into voltages versus the pure standard state metal: $V = -(\mu_{\text{Li}} - \mu_{\text{Li, ref}})$.

## Instructions

To compute the intrinsic ECW of a material, utilize the `calculate_ecw.py` script. The script automatically handles Materials Project thermodynamic entries, phase diagram construction, and calculates the exact analytical grand-potential limits using `.get_transition_chempots()`.

```bash
# Env: base-agent
python .agents/skills/mat-electrochemical-window/scripts/calculate_ecw.py --mp-id mp-1183147 --mobile-ion Li
```

### Script Arguments

- `--mp-id`: The Materials Project ID of the desired structure (e.g., `mp-1183147` for LGPS).
- `--mobile-ion`: The symbol of the mobile ion specifying the redox couple (default: `Li`).

## Examples

### Example 1: Reproducing Solid Electrolyte Literature ECW
You can independently reproduce the exact intrinsic thermodynamic stability windows (Table 1) reported in the original Zhu et al. (2015) manuscript using the script provided in this skill.

```bash
# Env: base-agent
python .agents/skills/mat-electrochemical-window/scripts/reproduce_table1.py
```

> [!NOTE]
> **Explaining Historical Discrepancies**: While the calculated lower boundaries ($V_{\text{red}}$) match Table 1 directly, you will see $V_{\text{ox}}$ values diverge slightly (by 0.1V - 0.3V). This is an expected artifact of Database Evolution. The 2015 calculations relied on legacy GGA parameters; Materials Project released completely new thermodynamic corrections (the `MP2020` schema) specifically adjusting the formation energies of gasses and anions (like $S$ and $O_2$), alongside adding tens of thousands of newly competitive stable phases.

## Constraints

- **Environments**: The analytical scripts here rely strictly on standard `pymatgen` definitions and mp-api interactions, resolving comfortably within the `# Env: base-agent`.
- **Energy Consistency**: The `ComputedEntry` for the candidate phase must share identical calculation parameters (pseudopotentials, U-values, relaxations) with the baseline structures comprising the `PhaseDiagram` object.
- **Reference Accuracy**: Ensure the Phase Diagram holds an accurate ground state reference for the metallic mobile ion.
- **Phase Coverage**: To appropriately predict $V_{\text{red}}$ and $V_{\text{ox}}$, the supplied `pd` must be fully comprehensive of all thermodynamically competing phases occurring within the target generic chemical system (e.g., for `Li10GeP2S12`, the PD must include the entirety of the Li-Ge-P-S quaternary compositional space).
- **Physical Interpretation of Metastability**: If $E_{\text{hull}} > 0$ meV/atom, the script will mathematically return an ECW of `[0.0V, 0.0V]`. This strictly reflects thermodynamic conditions. If you need to force a metastable compound onto the hull to view its artificial "pseudo-stability" limit (as done in Zhu 2015), manually set `entry = ComputedEntry(composition, hull_energy - 1e-5)` before passing into the logic.

## References
- Zhu, Y., He, X. & Mo, Y. "Origin of Outstanding Stability in the Lithium Solid Electrolyte Materials: Insights from Thermodynamic Analyses Based on First-Principles Calculations". *ACS Appl. Mater. Interfaces* 7, 23685–23693 (2015). [DOI: 10.1021/acsami.5b07517](https://doi.org/10.1021/acsami.5b07517)

---

**Author:** Bowen Deng  
**Contact:** [GitHub @bowen-bd](https://github.com/bowen-bd)
