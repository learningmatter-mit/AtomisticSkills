---
name: mat-structure-novelty
description: Determine if a given structure matches known experimental or theoretical structures, or compare two user-provided structures.
category: materials
---

# mat-structure-novelty

## Goal
To determine whether a user-provided structure (or list of structures) has been previously reported. This is done by matching the target structure against:
1. Known polymorphs in the Materials Project (MP). MP entries contain `theoretical` tags, and experimental structures will overlap with the Inorganic Crystal Structure Database (ICSD).
2. Any arbitrary candidate structure(s) provided by the user.

## Instructions

### Step 1: Execute Direct Novelty Check
Use the `match_structure.py` script to perform a symmetry-aware structural comparison. The script accepts a single target CIF or an entire **directory** of targets to run in bulk.

**Option A: Automatic Materials Project Matching (Default)**
If you do not pass a second argument, the script will automatically query the Materials Project API for all theoretical and experimental polymorphs corresponding to the target formulas, and match your structures against them:

```bash
# Env: base-agent
python .agents/skills/mat-structure-novelty/scripts/match_structure.py generated_cifs/ --output batch_results.json
```

**Option B: Local Candidate Matching**
If you want to match against a specific subset of structures (like a local ICSD dump) or just compare two specific structures, pass the explicitly downloaded candidates directory or file:

```bash
# Env: base-agent
python .agents/skills/mat-structure-novelty/scripts/match_structure.py target_structure_1.cif target_structure_2.xyz --output match_results.json
```

**Literature Fallback (Novel/Unmatched Structures):** 
If the script fails to find any *structural* match among the candidates in the Materials Project, you should perform a literature search to see if the material has been synthesized. 
When searching the literature for the structure, **ONLY use the composition as input** (for example, `"Li3ZrCl6"` or `"Li3InCl6"`). Do not include the space group or crystal system in the search query, as papers often do not index those exact terms in searchable abstracts.
After finding papers that report the composition, you must read the paper and **compare the structure** described in the literature with your candidate polymorph to determine if they match.
> [!IMPORTANT]
> If a literature match is reported but the **full text is not available (Open Access = False)** and you are unable to definitively read the paper to confirm the exact reported structure matches yours, you MUST explicitly tell the user that "literature full text is not available and the structure cannot be conclusively confirmed".

### Step 2: Literature Search (Mandatory)
If the structure is entirely novel, or just to know if the *composition* itself has been heavily studied or synthesized in particular conditions, you **MUST** perform a literature search using the `search_literature` MCP tool. 

```bash
mcp_search_literature(
    query="synthesis of Li10GeP2S12",
    limit=5,
    download=False
)
```

## Examples

Checking if a generated structure has been experimentally reported:
```bash
# Env: base-agent
# This automatically searches MP for LiFePO4 structures and compares against generated_LFP.cif
python .agents/skills/mat-structure-novelty/scripts/match_structure.py generated_LFP.cif --output match_results.json
```

## Constraints
- **Environments**: The script uses the standard `StructureMatcher` from `pymatgen`. It MUST be run in the `base-agent` environment.
- **Match Tolerances**: The structural matching relies on fractional length tolerance (`--ltol`), site tolerance (`--stol`), and angle tolerance (`--angle_tol`). The defaults (0.2, 0.3, 5.0) are typically suitable for DFT-relaxed comparison against MP structures, but can be tweaked if the test structure is highly distorted or unrelaxed.

---

**Author:** Bowen Deng  
**Contact:** [GitHub @bowen-bd](https://github.com/bowen-bd)
