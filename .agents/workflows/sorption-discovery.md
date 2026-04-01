---
description: High-throughput screening out of promising porous materials for gas sorption
---

# Sorption Discovery Workflow

This workflow describes how to string together the modular sorption skills (`chem-sorption-relax`, `chem-sorption-widom`, `chem-sorption-gcmc`) to perform a complete computational screening pipeline for gas adsorption (e.g., carbon capture, gas storage) in porous frameworks like MOFs, COFs, or zeolites.

## 1. Structure Preparation & Supercell Generation
Before any sorption calculation, you must ensure your porous framework is properly relaxed and large enough to avoid finite-size effects (i.e., artificial self-interaction of gas molecules across periodic boundaries).
- See: [chem-sorption-relax](../skills/chem-sorption-relax/SKILL.md)
- **Goal**: Check the initial structure (from a database or user input). If the minimum interplanar distance is less than 12 Å (typical threshold for small molecules like CO2/N2), generate a supercell.
- **Next step**: Relax the resulting (super)cell using an MCP tool like `mcp_fairchem_relax_structure` or `mcp_mace_relax_structure`. This yields the geometry-optimized host.

## 2. Initial Affinity Assessment (Widom Insertion)
Running full Monte Carlo simulations on thousands of candidates is computationally expensive. Use Widom insertion on the relaxed structure to rapidly estimate the initial binding affinity at infinite dilution.
- See: [chem-sorption-widom](../skills/chem-sorption-widom/SKILL.md)
- **Goal**: Calculate the Henry coefficient ($K_H$) and isosteric heat of adsorption ($\Delta H_{ads}$) using `run_widom.py`.
- **Decision Point**: Filter out materials with a very low $K_H$ or weak $\Delta H_{ads}$ (e.g., lower than the enthalpy of liquefaction for the target gas). Only proceed to the next step with promising candidates.

## 3. High-Pressure / Mixture Working Capacity (GCMC)
For materials that show strong initial affinity, you need to understand their total capacity at operating pressures and how they behave in mixtures (selectivity).
- See: [chem-sorption-gcmc](../skills/chem-sorption-gcmc/SKILL.md)
- **Goal**: Run Grand Canonical Monte Carlo to get loading isotherms (mmol/g) and partial Qst.
- **Single Component**: Use `run_gcmc.py` to map out the pure adsorption isotherm at various pressure steps (e.g., 0.1 bar, 1 bar, 10 bar) and calculate the working capacity (loading at absorption pressure MINUS loading at desorption pressure).
- **Mixtures**: Use `run_gcmc_multi.py` with realistic flue gas (e.g., 15% CO2 / 85% N2) to compute multi-component selectivities.

## Summary Checklist for the Agent
When tasked with a "sorption screening" or "test this MOF for CO2 capture":
1. [ ] Check structure size and build supercell. (`chem-sorption-relax`)
2. [ ] Relax structure with MCP tool. (`chem-sorption-relax`)
3. [ ] Run Widom insertion for Henry/heat using the desired MLIP. (`chem-sorption-widom`)
4. [ ] If metrics meet target thresholds, run GCMC at operating conditions using the SAME MLIP. (`chem-sorption-gcmc`)
