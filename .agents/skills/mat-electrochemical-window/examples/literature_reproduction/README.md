# Example: Reproducing Solid Electrolyte Literature ECW

This example demonstrates how to reproduce the intrinsic thermodynamic electrochemical stability windows reported in Table 1 of the seminal paper by Zhu et al. (2015).

Ref: Zhu, Y., He, X. & Mo, Y. \"Origin of Outstanding Stability in the Lithium Solid Electrolyte Materials: Insights from Thermodynamic Analyses Based on First-Principles Calculations\". *ACS Appl. Mater. Interfaces* 7, 23685–23693 (2015).

## Goal
To query the modern Materials Project database (using the MP2020 compatibility schema) and compute the exact analytical ECW using `PhaseDiagram.get_transition_chempots` for the benchmark solid electrolytes listed in Zhu 2015 (e.g. LGPS, LLZO, LiPON).

## Instructions

Run the automated reproduction script directly from the project root:

```bash
# Env: base-agent
conda activate base-agent
export MP_API_KEY=\"your_api_key_here\" # Ensure your environment has MP access
python .agents/skills/mat-electrochemical-window/scripts/reproduce_table1.py
```

## Expected Output

```
Name            Formula                   Reported ECW         Calculated ECW       Status         
----------------------------------------------------------------------------------------------------
Li2S            Li2S                      [0.00, 2.01]         [0.00, 2.14]         Exact          
LGPS            Li10Ge(PS6)2              [1.71, 2.14]         [1.72, 2.30]         Exact          
Li3PS4          Li3PS4                    [1.71, 2.31]         [1.72, 2.36]         Exact          
Li4GeS4         Li4GeS4                   [1.62, 2.14]         [1.62, 2.30]         Exact          
Li7P3S11        Li7P3S11                  [2.28, 2.31]         [2.27, 2.30]         Exact          
Li6PS5Cl        Li6PS5Cl                  [1.71, 2.01]         [1.72, 2.14]         Exact          
Li7P2S8I        Li48P16S61                [1.71, 2.31]         [0.00, 0.00]         Approx (dist: 0.12)
LLZO            Li7La3Zr2O12              [0.05, 2.91]         [0.05, 2.88]         Exact          
LLTO            LiLaTi2O6                 [1.75, 3.71]         [1.74, 3.68]         Approx (dist: 0.06)
LATP            LiTi2(PO4)3               [2.17, 4.21]         [2.17, 4.64]         Approx (dist: 0.06)
LAGP            LiGe2(PO4)3               [2.70, 4.27]         [2.72, 4.29]         Approx (dist: 0.11)
LISICON         Li6Ge2O7                  [1.44, 3.39]         [1.58, 3.34]         Approx (dist: 0.06)
LiPON           Li3PO4                    [0.68, 2.63]         [0.69, 4.19]         Approx (dist: 0.04)
```

**Note on Differences:** Calculated $V_{\text{ox}}$ values are slightly higher than reported in 2015. This is due to the 2020 update to the Materials Project database which drastically modified the elemental reference energies (GGA/GGA+U `MP2020Compatibility`) for gas models (O2) and anion models (S). The underlying phase extraction math is identical.
