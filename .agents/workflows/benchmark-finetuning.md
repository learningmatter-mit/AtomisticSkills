---
description: Workflow for benchmarking, fine-tuning, and distilling Machine Learning Interatomic Potentials (MLIPs)
---

This workflow guides you through the process of selecting, evaluating, and improving a Machine Learning Interatomic Potential (MLIP) for a specific target simulation task.

1. **Choose a relevant foundation potential**
   - Review the requirements of your target simulation (e.g., elements involved, accuracy versus speed constraints).
   - Refer to the `ml-foundation-potentials` skill (`.agents/skills/ml-foundation-potentials/SKILL.md`) to select an appropriate foundation potential.

2. **Sample the Potential Energy Surface (PES)**
   - Carefully sample the PES based on the problem of interest to capture relevant configurations, including off-equilibrium and transition states.
   - For solid-state materials, refer to the `mat-sample-pes-by-md` skill (`.agents/skills/mat-sample-pes-by-md/SKILL.md`).
   - Alternative sampling methods exist depending on the system (e.g., `chem-conformer-search`, `mat-amorphorization`, `mat-random-structure-search`).

3. **Acquire labels for the sampled structures**
   - Calculate high-fidelity energies, forces, and stresses for the sampled structures.
   - *Ab initio labels*: Use Density Functional Theory (DFT) via `atomate2` VASP workflows.
   - *Distillation*: Use a significantly more expensive but accurate foundation potential to label the structures for a faster, lighter potential.

4. **Benchmark the foundation potential's accuracy**
   - Evaluate the baseline accuracy of the chosen foundation potential against the newly acquired labels.
   - Refer to the `ml-mlip-training` skill (`.agents/skills/ml-mlip-training/SKILL.md`) for benchmarking procedures to determine if fine-tuning is necessary.

5. **Perform fine-tuning (or distillation)**
   - If the baseline potential's accuracy is insufficient on your sampled PES, fine-tune the model using the labeled dataset.
   - Refer to the `ml-mlip-training` skill (`.agents/skills/ml-mlip-training/SKILL.md`) for instructions on setting up and executing the fine-tuning process.

6. **Deploy the MLIP for the target simulation task**
   - Deploy the benchmarked or fine-tuned MLIP to run your primary simulation tasks (e.g., production molecular dynamics, phase diagrams).

7. **Monitor simulated metrics and iterate (Active Learning)**
   - During the simulation, continuously monitor relevant physical metrics to ensure the MLIP's structural and thermodynamic stability (e.g., system density, Radial Distribution Function (RDF), transition temperature, diffusivity).
   - If the accuracy of these computed macroscopic properties is unsatisfied or unphysical behavior is observed, repeat the process: further sample the PES from the problematic configurations, acquire new labels, and iteratively fine-tune the MLIP.
