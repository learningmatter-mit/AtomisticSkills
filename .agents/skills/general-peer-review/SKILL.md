---
name: general-peer-review
description: Act as a reviewer to critically review research plans, manuscripts, or task summaries, pointing out missing baselines, statistical flaws, and weak assumptions.
category: [general]
---

# General Peer Review

## Goal
To rigorously evaluate a research plan, manuscript, or simulation workflow prior to execution or publication. This skill acts as an adversarial reviewer, ensuring scientific rigor by identifying methodological gaps, demanding adequate statistical sampling, highlighting weak assumptions, and suggesting necessary baseline comparisons.

## Prerequisites
- A completed or drafted piece of scientific writing (e.g., `research_plan.md`, manuscript draft, or experimental summary).
- Sufficient contextual knowledge regarding the specific simulation or machine-learning methodology being proposed.

## Instructions

1. **Review Initialization**
   The agent initializes the review process by loading the target document into memory. This can be done by standard reading tools like `view_file`.

2. **Literature-Based Validation**
   The agent utilizes skills like `general-query-literature-database` or `general-deep-research` to ground the review in established scientific facts. 
   - Perform a literature search regarding the specific materials, methodologies, or baseline properties stated in the text.
   - Point out discrepancies between the proposed approach and standard practices found in high-impact journals.

3. **Methodological & Reproducibility Critique**
   The agent systematically analyzes the methodology for common theoretical and computational pitfalls:
   - **Ensemble & Sampling**: Verify if MD simulations are long enough to reach equilibration and if the number of samples is statistically significant.
   - **Level of Theory**: Question if the chosen MLIP or DFT functional is adequate for the specific property being computed (e.g., PBE vs. r2SCAN, dispersion corrections for molecular systems).
   - **System Size**: Check if the supercell size is large enough to avoid finite-size effects and self-interaction (e.g., in defect or dopant studies).
   - **Hyperparameters**: Ensure critical hyperparameter choices (e.g., $k$-point grid density, energy cutoffs, learning rates) are justified.
   - **Reproducibility**: Are all protocols, scripts, and model checkpoints adequately specified to allow independent reproduction? Have data availability standards been met?

4. **Baseline & Validation Requirements**
   The agent identifies whether the document includes proper validation checks:
   - Are there missing benchmark/control experiments?
   - Should a preliminary convergence test or standard reference calculation (e.g., bulk defect-free relaxation) be performed first?
   - How does the expected output compare to known literature values?

5. **Constructive Feedback Generation**
   The agent outputs a set of formatted comments, structurally divided into:
   - **Summary Statement**: Brief synopsis of the research, overall recommendation (accept, revisions, reject), and key strengths/weaknesses.
   - **Major Concerns**: Fundamental methodological flaws that could invalidate findings. Number these sequentially. For each concern: state the issue, explain why it's problematic, and suggest actionable solutions.
   - **Minor Concerns**: Suggestions to strengthen clarity, formatting, data presentation, or typographical errors (e.g., "Add error bars on ionic conductivity plots").
   - **Questions for Authors**: Specific points requiring clarification that must be addressed to fully evaluate the work.

## Document-Specific Workflows

### original Research Manuscripts
- Emphasize methodological rigor, proper validation, and significance.
- Evaluate the comprehensiveness of literature coverage and appropriateness of citations.

### Scientific Presentations (PowerPoint / PDF)
> [!WARNING]
> **MANDATORY**: For presentations, NEVER attempt to read the PDF text directly. ALWAYS use visual inspection.

- **Process**: First convert the PDF to images (e.g., via standard Python PDF-to-image libraries) and use a Vision-Language Model (VLM) for visual inspection slide by slide.
- **Evaluation Criteria**: Check for text overflow, overlapping elements, unreadable font sizes (< 18pt), unlabelled axes, and poor color contrast.
- **Reporting**: Note visual formatting issues by specific slide number.

## Examples

To see how the reviewer evaluates a proposed Action Plan for scientific methodology and reproducibility, see the [Workflow Review Discussion](examples/workflow-review/README.md) example.

## Constraints
- **Scope**: Keep feedback strictly focused on scientific rigor, theoretical methodology, and validity of conclusions. Avoid purely stylistic copy-editing unless clarity is severely compromised.
- **Tone**: Critical, objective, and scientifically rigorous (emulating a stringent peer review process).

## See Also
- [general-deep-research](../general-deep-research/SKILL.md)
- [general-presentation](../general-presentation/SKILL.md)

---

**Author:** Bowen Deng  
**Contact:** [GitHub @Bowen-BD](https://github.com/Bowen-BD)
