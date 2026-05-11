window.SKILLS_DATA = [
  {
    "id": "chem-bond-dissociation",
    "name": "chem-bond-dissociation",
    "description": "Calculate homolytic and heterolytic bond dissociation energies (BDEs) for all single bonds in a molecule using MLIPs with RDKit fragmentation.",
    "category": [
      "chemistry"
    ],
    "has_examples": true,
    "num_examples": 4
  },
  {
    "id": "chem-conformer-search",
    "name": "chem-conformer-search",
    "description": "Generate molecular conformers with RDKit ETKDG, relax with MLIPs, and rank by energy with Boltzmann weighting.",
    "category": [
      "chemistry"
    ],
    "has_examples": true,
    "num_examples": 2
  },
  {
    "id": "chem-db-mof",
    "name": "chem-db-mof",
    "description": "Query multiple MOF databases (QMOF via MPContribs; ARC-MOF DB7/Majumdar et al. via Zenodo) and download CIF structures with optional element or identifier filters.",
    "category": "chemistry",
    "has_examples": false,
    "num_examples": 0
  },
  {
    "id": "chem-db-qmof",
    "name": "chem-db-qmof",
    "description": "Query the Quantum MOF (QMOF) database via Materials Project's MPContribs platform for DFT-computed properties (bandgap) and optimized crystal structures of Metal-Organic Frameworks.",
    "category": [
      "materials",
      "chemistry"
    ],
    "has_examples": false,
    "num_examples": 0
  },
  {
    "id": "chem-db-spectra",
    "name": "chem-db-spectra",
    "description": "Search and download experimental InfraRed (IR), Mass spectra, and UV-Vis spectra data (JCAMP-DX format) for molecules.",
    "category": "chemistry",
    "has_examples": true,
    "num_examples": 1
  },
  {
    "id": "chem-dft-orca-advanced-calculation",
    "name": "chem-dft-orca-advanced-calculation",
    "description": "Write and run custom ORCA input files for advanced electronic structure methods or settings not available through the SCINE wrapper, including multi-reference methods, excited states, relativistic effects, advanced SCF, NMR/EPR, and more.",
    "category": [
      "chemistry"
    ],
    "has_examples": false,
    "num_examples": 0
  },
  {
    "id": "chem-dft-orca-optimization",
    "name": "chem-dft-orca-optimization",
    "description": "Run DFT geometry optimization (minimization or TS search) on a molecular structure using ORCA via SCINE/ReaDuct wrapper.",
    "category": [
      "chemistry"
    ],
    "has_examples": false,
    "num_examples": 0
  },
  {
    "id": "chem-dft-orca-singlepoint",
    "name": "chem-dft-orca-singlepoint",
    "description": "Run a DFT or Coupled Cluster single-point energy calculation (with optional gradients/Hessian) on a molecular structure with ORCA through SCINE wrapper.",
    "category": [
      "chemistry"
    ],
    "has_examples": false,
    "num_examples": 0
  },
  {
    "id": "chem-docking-void",
    "name": "chem-docking-void",
    "description": "Dock small-molecule guests into a porous host material using the VOID library (Voronoi Clustering), generating multiple 3D conformers with RDKit and ranking generated complexes.",
    "category": [
      "materials",
      "chemistry"
    ],
    "has_examples": true,
    "num_examples": 1
  },
  {
    "id": "chem-hazard-toxicity",
    "name": "chem-hazard-toxicity",
    "description": "Extract explicit safety warnings, GHS classifications, and LD50 profiles from PubChem PUG VIEW.",
    "category": [
      "chemistry",
      "drug-discovery"
    ],
    "has_examples": true,
    "num_examples": 1
  },
  {
    "id": "chem-irc-verification",
    "name": "chem-irc-verification",
    "description": "Verify non-periodic molecular TS connectivity with forward/reverse IRC using endpoint connectivity and RMSD checks.",
    "category": [
      "chemistry"
    ],
    "has_examples": true,
    "num_examples": 1
  },
  {
    "id": "chem-neb-barrier",
    "name": "chem-neb-barrier",
    "description": "Calculate activation barrier using Nudged Elastic Band (NEB) method with MLIPs.",
    "category": [
      "chemistry",
      "materials"
    ],
    "has_examples": true,
    "num_examples": 2
  },
  {
    "id": "chem-nmr-analysis",
    "name": "chem-nmr-analysis",
    "description": "Scripts for Wasserstein deconvolution of 1H NMR mixture spectra against reference spectra, reaction product prediction, time-series kinetics, and spectral plotting.",
    "category": "chemistry",
    "has_examples": false,
    "num_examples": 0
  },
  {
    "id": "chem-nmr-predict",
    "name": "chem-nmr-predict",
    "description": "Predict 1H NMR spectra from SMILES strings via NMRdb.org SPINUS neural network prediction and nmrsim quantum mechanical spin simulation.",
    "category": "chemistry",
    "has_examples": false,
    "num_examples": 0
  },
  {
    "id": "chem-react-ot",
    "name": "chem-react-ot",
    "description": "Generate transition state structures for chemical reactions using React-OT.",
    "category": [
      "chemistry"
    ],
    "has_examples": true,
    "num_examples": 1
  },
  {
    "id": "chem-similarity-search",
    "name": "chem-similarity-search",
    "description": "Find structurally similar chemical compounds using PubChem's 2D fast similarity engine via the PUG-REST API.",
    "category": [
      "chemistry",
      "drug-discovery"
    ],
    "has_examples": true,
    "num_examples": 1
  },
  {
    "id": "chem-solution-md",
    "name": "chem-solution-md",
    "description": "Set up and run molecular dynamics simulations of molecules in explicit solvent boxes using Packmol for box construction and MLIPs for dynamics.",
    "category": [
      "chemistry"
    ],
    "has_examples": true,
    "num_examples": 2
  },
  {
    "id": "chem-sorption-gcmc",
    "name": "chem-sorption-gcmc",
    "description": "Calculates gas adsorption isotherms via BVT/GCMC Monte Carlo simulations in a porous framework using MLIP.",
    "category": [
      "materials",
      "chemistry"
    ],
    "has_examples": true,
    "num_examples": 1
  },
  {
    "id": "chem-sorption-relax",
    "name": "chem-sorption-relax",
    "description": "Prepares supercells for porous frameworks based on minimum interplanar distance and relaxes them using standard MLIP relaxation tools.",
    "category": [
      "materials",
      "chemistry"
    ],
    "has_examples": true,
    "num_examples": 1
  },
  {
    "id": "chem-sorption-widom",
    "name": "chem-sorption-widom",
    "description": "Calculates Henry coefficient and heat of adsorption for a gas in a porous framework using Widom insertion with any supported MLIP.",
    "category": [
      "materials",
      "chemistry"
    ],
    "has_examples": true,
    "num_examples": 1
  },
  {
    "id": "chem-thermochemistry",
    "name": "chem-thermochemistry",
    "description": "Compute gas-phase thermodynamic quantities (H, S, G) and reaction thermochemistry (ΔH, ΔS, ΔG) using MLIPs with the ideal-gas/rigid-rotor/harmonic-oscillator approximation.",
    "category": [
      "chemistry"
    ],
    "has_examples": true,
    "num_examples": 2
  },
  {
    "id": "chem-ts-optimization",
    "name": "chem-ts-optimization",
    "description": "Optimize non-periodic molecular TS guesses and verify first-order saddle point from vibrational modes.",
    "category": [
      "chemistry"
    ],
    "has_examples": true,
    "num_examples": 1
  },
  {
    "id": "chem-vibration",
    "name": "chem-vibration",
    "description": "Calculate vibrational frequencies, normal modes, zero-point energy, and IR spectra of molecules and clusters using MLIPs.",
    "category": [
      "chemistry"
    ],
    "has_examples": true,
    "num_examples": 1
  },
  {
    "id": "drug-admet-prediction",
    "name": "drug-admet-prediction",
    "description": "Compute RDKit physicochemical descriptors and rule-based drug-likeness heuristics (Ro5, Veber, QED) from SMILES.",
    "category": [
      "drug-discovery"
    ],
    "has_examples": true,
    "num_examples": 1
  },
  {
    "id": "drug-binding-site-definition",
    "name": "drug-binding-site-definition",
    "description": "Define a docking search box (center coordinates + box dimensions in Angstroms) from a co-crystal ligand, binding-site residues, or a saved JSON specification. Use this skill whenever the user mentions binding site, docking box, search box, grid box, active site definition, or pocket definition, or needs to specify where to dock ligands on a protein. Also use when the user has a protein target but needs help figuring out where to dock before running a docking skill.\n",
    "category": [
      "drug-discovery"
    ],
    "has_examples": true,
    "num_examples": 1
  },
  {
    "id": "drug-bioactivity-assay",
    "name": "drug-bioactivity-assay",
    "description": "Fetch biological assays and target proteins a chemical has been tested against via PubChem.",
    "category": [
      "drug-discovery"
    ],
    "has_examples": true,
    "num_examples": 1
  },
  {
    "id": "drug-complex-system-builder",
    "name": "drug-complex-system-builder",
    "description": "Build a solvated, charge-neutralized protein-ligand complex for OpenMM molecular dynamics simulation. Combines a prepared receptor PDB and ligand SDF, parameterizes the ligand with OpenFF Sage or GAFF (AM1-BCC charges), applies Amber ff14SB to the protein, solvates with explicit water, and adds counterions. Use this skill when the user wants to solvate a complex, set up a system for MD, prepare for simulation, add water and ions, or build a simulation box from a protein-ligand structure.\n",
    "category": [
      "drug-discovery"
    ],
    "has_examples": true,
    "num_examples": 1
  },
  {
    "id": "drug-db-chembl",
    "name": "drug-db-chembl",
    "description": "Query ChEMBL web services for targets, molecules, and curated bioactivity measurements (IC50, Ki, EC50, etc.).",
    "category": [
      "drug-discovery"
    ],
    "has_examples": true,
    "num_examples": 1
  },
  {
    "id": "drug-db-pdb",
    "name": "drug-db-pdb",
    "description": "Search, filter, and retrieve macromolecular structures from the RCSB Protein Data Bank (PDB), including metadata, bound ligands, and optional coordinate/validation downloads.",
    "category": [
      "drug-discovery"
    ],
    "has_examples": true,
    "num_examples": 1
  },
  {
    "id": "drug-db-pubchem",
    "name": "drug-db-pubchem",
    "description": "Query PubChem via PUG-REST to retrieve CIDs, computed properties, synonyms, and 2D/3D SDF structures.",
    "category": [
      "drug-discovery"
    ],
    "has_examples": true,
    "num_examples": 1
  },
  {
    "id": "drug-docking-analysis",
    "name": "drug-docking-analysis",
    "description": "Post-docking analysis of virtual screening results including score distributions, enrichment metrics (ROC AUC, enrichment factors), and ligand efficiency calculations.",
    "category": [
      "drug-discovery"
    ],
    "has_examples": true,
    "num_examples": 1
  },
  {
    "id": "drug-docking-vina",
    "name": "drug-docking-vina",
    "description": "Dock small-molecule ligands into a protein receptor using AutoDock Vina (Python API) and save ranked poses + docking metadata for reproducible virtual screening.",
    "category": [
      "drug-discovery"
    ],
    "has_examples": true,
    "num_examples": 1
  },
  {
    "id": "drug-ligand-prep",
    "name": "drug-ligand-prep",
    "description": "",
    "category": [],
    "has_examples": true,
    "num_examples": 1
  },
  {
    "id": "drug-mmpbsa-gbsa",
    "name": "drug-mmpbsa-gbsa",
    "description": "Compute single-trajectory MM-GBSA and / or MM-PBSA binding free energy estimates from a protein-ligand MD trajectory. Two backends: a fast OpenMM GBn2 path (no extra dependencies) and an AmberTools MMPBSA.py path that supports both GB (multiple igb models) and Poisson-Boltzmann PB on the same trajectory.\n",
    "category": [
      "drug-discovery"
    ],
    "has_examples": true,
    "num_examples": 2
  },
  {
    "id": "drug-molecular-fingerprints",
    "name": "drug-molecular-fingerprints",
    "description": "Compute Morgan/ECFP fingerprints, Tanimoto similarity, and optional Butina clusters/heatmaps for small-molecule comparison.",
    "category": [
      "drug-discovery"
    ],
    "has_examples": true,
    "num_examples": 1
  },
  {
    "id": "drug-pocket-detection",
    "name": "drug-pocket-detection",
    "description": "Identify and rank ligandable pockets on a protein structure or model using geometry (fpocket) or an ML predictor (P2Rank). Returns ranked pockets with lining residues, geometric center, volume, and a druggability score per pocket. Excludes docking; pair with drug-binding-site-definition or drug-docking-vina downstream. Use whenever the user has a protein but no binding-site information, asks about cryptic / allosteric / orphan pockets, needs to assess druggability, or wants to choose where to dock.\n",
    "category": [
      "drug-discovery"
    ],
    "has_examples": true,
    "num_examples": 1
  },
  {
    "id": "drug-pose-validation",
    "name": "drug-pose-validation",
    "description": "Validate docked or generated ligand poses for physical plausibility using PoseBusters, filtering out chemically invalid or clashing poses before downstream refinement.",
    "category": [
      "drug-discovery"
    ],
    "has_examples": true,
    "num_examples": 1
  },
  {
    "id": "drug-protein-ligand-md",
    "name": "drug-protein-ligand-md",
    "description": "Run a protein-ligand MD simulation in OpenMM with energy minimization, restrained equilibration, and production NPT, producing trajectory and checkpoint files for downstream analysis.",
    "category": [
      "drug-discovery"
    ],
    "has_examples": true,
    "num_examples": 1
  },
  {
    "id": "drug-protein-prep",
    "name": "drug-protein-prep",
    "description": "Prepare macromolecular receptor structures (PDB/mmCIF or RCSB PDB ID) for docking or simulation by fixing common structure issues and adding hydrogens.",
    "category": [
      "drug-discovery"
    ],
    "has_examples": true,
    "num_examples": 1
  },
  {
    "id": "drug-redocking-rmsd",
    "name": "drug-redocking-rmsd",
    "description": "Compute symmetry-corrected heavy-atom RMSD between docked poses and a reference crystal ligand to validate docking protocols.",
    "category": [
      "drug-discovery"
    ],
    "has_examples": true,
    "num_examples": 1
  },
  {
    "id": "drug-retrosynthesis",
    "name": "drug-retrosynthesis",
    "description": "Predict synthetic accessibility and retrosynthetic pathways for novel molecules using the IBM RXN API.",
    "category": "drug-discovery",
    "has_examples": true,
    "num_examples": 1
  },
  {
    "id": "drug-trajectory-analysis",
    "name": "drug-trajectory-analysis",
    "description": "Analyze a protein-ligand MD trajectory to compute ligand RMSD, pocket RMSF, hydrogen bonds, contact occupancy, and protein-ligand interaction fingerprints over time.",
    "category": [
      "drug-discovery"
    ],
    "has_examples": true,
    "num_examples": 1
  },
  {
    "id": "general-arxiv-search",
    "name": "general-arxiv-search",
    "description": "Search and retrieve research papers from ArXiv API for scientific research.",
    "category": "general",
    "has_examples": false,
    "num_examples": 0
  },
  {
    "id": "general-chemical-literature",
    "name": "general-chemical-literature",
    "description": "Retrieve extensive literature (PubMed) and patent associated with a specific chemical compound via PubChem.",
    "category": [
      "general",
      "chemistry",
      "drug-discovery",
      "materials"
    ],
    "has_examples": true,
    "num_examples": 1
  },
  {
    "id": "general-chemical-pricing",
    "name": "general-chemical-pricing",
    "description": "Retrieves averaged elemental prices and provides direct vendor purchase links for elements and precursor compounds.",
    "category": [
      "general",
      "materials",
      "chemistry"
    ],
    "has_examples": true,
    "num_examples": 1
  },
  {
    "id": "general-deep-research",
    "name": "general-deep-research",
    "description": "Perform iterative, deep, and comprehensive literature research on a specific materials/chemistry topic.",
    "category": "general",
    "has_examples": false,
    "num_examples": 0
  },
  {
    "id": "general-patent-search",
    "name": "general-patent-search",
    "description": "Search for patents by keyword, material name, or assignee using free data sources (Google Patents).",
    "category": "general",
    "has_examples": true,
    "num_examples": 1
  },
  {
    "id": "general-peer-review",
    "name": "general-peer-review",
    "description": "Act as a reviewer to critically review research plans, manuscripts, or task summaries, pointing out missing baselines, statistical flaws, and weak assumptions.",
    "category": [
      "general"
    ],
    "has_examples": true,
    "num_examples": 1
  },
  {
    "id": "general-plot-digitizer",
    "name": "general-plot-digitizer",
    "description": "Extract continuous X-Y data from experimental spectrum images (Raman, XRD, UV-Vis, IR, etc.) via hybrid VLM + CV pipeline and agent-in-the-loop workflow.",
    "category": [
      "general",
      "machine-learning"
    ],
    "has_examples": true,
    "num_examples": 4
  },
  {
    "id": "general-presentation",
    "name": "general-presentation",
    "description": "Generate and iteratively refine PowerPoint presentations from simulation results using python-pptx.",
    "category": [
      "general"
    ],
    "has_examples": true,
    "num_examples": 1
  },
  {
    "id": "general-property-units",
    "name": "general-property-units",
    "description": "Reference guide for energy, force, and stress units across MLIPs, DFT codes, and ASE, including conversion factors.",
    "category": [
      "general",
      "machine-learning"
    ],
    "has_examples": false,
    "num_examples": 0
  },
  {
    "id": "general-query-literature-database",
    "name": "general-query-literature-database",
    "description": "Find relevant simulation workflows in the in-house literature database.",
    "category": "general",
    "has_examples": false,
    "num_examples": 0
  },
  {
    "id": "general-workflow-planner",
    "name": "general-workflow-planner",
    "description": "Hierarchically decompose high-level scientific workflows (from literature or user-proposed) into executable sequences of existing SKILLs and MCP tools for the research plan.",
    "category": [
      "general"
    ],
    "has_examples": true,
    "num_examples": 1
  },
  {
    "id": "mat-amorphization",
    "name": "mat-amorphization",
    "description": "Generate amorphorized structures from crystalline starting points using a melt-quench MD protocol.",
    "category": [
      "materials"
    ],
    "has_examples": true,
    "num_examples": 1
  },
  {
    "id": "mat-calphad-phase-diagram",
    "name": "mat-calphad-phase-diagram",
    "description": "Calculate and plot multi-component temperature-composition phase diagrams from Thermodynamic Database (.tdb) files using CALPHAD methods.",
    "category": "materials",
    "has_examples": true,
    "num_examples": 1
  },
  {
    "id": "mat-calphad-property-diagram",
    "name": "mat-calphad-property-diagram",
    "description": "Calculate temperature-dependent thermodynamic properties like Equilibrium Phase Fractions for a specific alloy composition using CALPHAD models.",
    "category": "materials",
    "has_examples": true,
    "num_examples": 1
  },
  {
    "id": "mat-db-mp",
    "name": "mat-db-mp",
    "description": "Query Materials Project database for crystal structures, computed properties, elastic/magnetic data, and structurally similar materials using the MP API.",
    "category": [
      "materials"
    ],
    "has_examples": true,
    "num_examples": 1
  },
  {
    "id": "mat-db-nist-janaf",
    "name": "mat-db-nist-janaf",
    "description": "Query the NIST Chemistry WebBook (which includes JANAF thermochemical tables) for standard experimental thermochemistry properties.",
    "category": "materials",
    "has_examples": true,
    "num_examples": 1
  },
  {
    "id": "mat-db-optimade",
    "name": "mat-db-optimade",
    "description": "Query the Crystallography Open Database (COD) and other OPTIMADE-compliant databases for experimental crystal structures.",
    "category": "materials",
    "has_examples": true,
    "num_examples": 3
  },
  {
    "id": "mat-defect-energy",
    "name": "mat-defect-energy",
    "description": "Calculate point-defect formation energies (vacancies, substitutions, interstitials) using MLIPs.",
    "category": [
      "materials"
    ],
    "has_examples": true,
    "num_examples": 1
  },
  {
    "id": "mat-defect-energy-dft",
    "name": "mat-defect-energy-dft",
    "description": "Calculate charged defect formation energies and transition level diagrams using pymatgen-analysis-defects and atomate2 VASP workflows.",
    "category": [
      "materials"
    ],
    "has_examples": true,
    "num_examples": 1
  },
  {
    "id": "mat-dft-electron-phonon",
    "name": "mat-dft-electron-phonon",
    "description": "Computes electron-phonon coupling to calculate temperature-dependent bandgap renormalization using atomate2.",
    "category": "materials",
    "has_examples": true,
    "num_examples": 1
  },
  {
    "id": "mat-dft-electronic-transport",
    "name": "mat-dft-electronic-transport",
    "description": "Compute electronic transport properties (mobility, conductivity, Seebeck coefficient) using DFT and AMSET via atomate2.",
    "category": "materials",
    "has_examples": true,
    "num_examples": 1
  },
  {
    "id": "mat-dft-ferroelectric",
    "name": "mat-dft-ferroelectric",
    "description": "Calculate the spontaneous ferroelectric polarization across a non-polar to polar structure transition using the Berry Phase method.",
    "category": "materials",
    "has_examples": true,
    "num_examples": 1
  },
  {
    "id": "mat-dft-lobster",
    "name": "mat-dft-lobster",
    "description": "Construct computational flows for VASP electronic structure projection via LOBSTER to calculate chemical bonding insights (COHP, atomic charges, DOS).",
    "category": "materials",
    "has_examples": true,
    "num_examples": 1
  },
  {
    "id": "mat-dft-mixing-functionals",
    "name": "mat-dft-mixing-functionals",
    "description": "Energy corrections needed when using certain MLIPs for phase diagram construction / formation energy calculations.",
    "category": [
      "materials"
    ],
    "has_examples": false,
    "num_examples": 0
  },
  {
    "id": "mat-dft-vasp",
    "name": "mat-dft-vasp",
    "description": "Prepare VASP input files, run DFT calculations (locally or remotely via atomate2), and parse VASP output results.",
    "category": "materials",
    "has_examples": true,
    "num_examples": 1
  },
  {
    "id": "mat-dielectric-response",
    "name": "mat-dielectric-response",
    "description": "Calculate frequency-dependent dielectric response using atomate2 OpticsMaker and VASP.",
    "category": [
      "materials"
    ],
    "has_examples": true,
    "num_examples": 1
  },
  {
    "id": "mat-diffusion-analysis",
    "name": "mat-diffusion-analysis",
    "description": "Calculate ionic diffusion coefficients and activation energy from MD trajectories using pymatgen.",
    "category": [
      "materials"
    ],
    "has_examples": true,
    "num_examples": 1
  },
  {
    "id": "mat-disorder",
    "name": "mat-disorder",
    "description": "Generate ordered structures from disordered starting points with partial occupancies.",
    "category": [
      "materials"
    ],
    "has_examples": true,
    "num_examples": 1
  },
  {
    "id": "mat-elasticity",
    "name": "mat-elasticity",
    "description": "Calculate the full elastic tensor and mechanical properties (bulk modulus, shear modulus, Young's modulus, Poisson's ratio) using MLIPs.",
    "category": [
      "materials"
    ],
    "has_examples": true,
    "num_examples": 1
  },
  {
    "id": "mat-electrochemical-window",
    "name": "mat-electrochemical-window",
    "description": "Calculate the intrinsic electrochemical stability window (ECW) of a material using standard phase diagram thermodynamic methods.",
    "category": [
      "materials"
    ],
    "has_examples": true,
    "num_examples": 1
  },
  {
    "id": "mat-electronic-structure",
    "name": "mat-electronic-structure",
    "description": "Calculate electronic band structure and density of states using atomate2 and VASP.",
    "category": [
      "materials"
    ],
    "has_examples": true,
    "num_examples": 1
  },
  {
    "id": "mat-elemental-energies",
    "name": "mat-elemental-energies",
    "description": "A library of ground-state element structures and their energies calculated from MLIPs. Used to calculate formation energies of compounds.",
    "category": [
      "materials"
    ],
    "has_examples": false,
    "num_examples": 0
  },
  {
    "id": "mat-equation-of-state",
    "name": "mat-equation-of-state",
    "description": "Calculate equation of state (bulk modulus, equilibrium volume) using MLIPs.",
    "category": [
      "materials"
    ],
    "has_examples": true,
    "num_examples": 1
  },
  {
    "id": "mat-grain-boundary",
    "name": "mat-grain-boundary",
    "description": "Calculate grain boundary energies for tilt/twist grain boundaries (Σ-CSL boundaries) using MLIPs; output γ_GB vs. misorientation angle curves and identify low-energy special boundaries.",
    "category": [
      "materials"
    ],
    "has_examples": true,
    "num_examples": 1
  },
  {
    "id": "mat-grand-canonical-mc",
    "name": "mat-grand-canonical-mc",
    "description": "Run Grand Canonical Monte Carlo (GCMC) simulations with cluster expansion models to map composition-temperature phase diagrams via chemical potential sweeps.",
    "category": [
      "materials"
    ],
    "has_examples": true,
    "num_examples": 2
  },
  {
    "id": "mat-intercalation-voltage",
    "name": "mat-intercalation-voltage",
    "description": "Calculate the average intercalation voltage of cathode materials using MLIPs.",
    "category": [
      "materials"
    ],
    "has_examples": true,
    "num_examples": 1
  },
  {
    "id": "mat-ionic-substitution",
    "name": "mat-ionic-substitution",
    "description": "Discover new crystal structures by data-mined ionic substitution — propose candidates from existing structures (forward) or find potential structures for a target composition (reverse).",
    "category": [
      "materials"
    ],
    "has_examples": true,
    "num_examples": 2
  },
  {
    "id": "mat-kinetic-monte-carlo",
    "name": "mat-kinetic-monte-carlo",
    "description": "",
    "category": [],
    "has_examples": true,
    "num_examples": 2
  },
  {
    "id": "mat-lammps-md",
    "name": "mat-lammps-md",
    "description": "Build and run LAMMPS molecular dynamics with isolated MLIP-specific binaries (MACE, MatGL/CHGNet, FairChem) to avoid Python and Torch stack conflicts.",
    "category": [
      "materials"
    ],
    "has_examples": true,
    "num_examples": 3
  },
  {
    "id": "mat-lattice-thermal-conductivity",
    "name": "mat-lattice-thermal-conductivity",
    "description": "Calculate lattice thermal conductivity of materials with MLIPs.",
    "category": [
      "materials"
    ],
    "has_examples": true,
    "num_examples": 1
  },
  {
    "id": "mat-magnetic-density",
    "name": "mat-magnetic-density",
    "description": "Calculate magnetic moments and spin density from spin-polarized DFT calculations using VASP.",
    "category": [
      "materials"
    ],
    "has_examples": true,
    "num_examples": 1
  },
  {
    "id": "mat-md-monitors",
    "name": "mat-md-monitors",
    "description": "Real-time monitoring tools for stability, equilibration, and diffusion during ASE molecular dynamics simulations.",
    "category": [
      "materials",
      "chemistry"
    ],
    "has_examples": false,
    "num_examples": 0
  },
  {
    "id": "mat-md-probability-density",
    "name": "mat-md-probability-density",
    "description": "Calculate and visualize the probability density of diffusing ions from a Molecular Dynamics (MD) trajectory.",
    "category": [
      "materials"
    ],
    "has_examples": true,
    "num_examples": 1
  },
  {
    "id": "mat-melting-point",
    "name": "mat-melting-point",
    "description": "Calculate the melting temperature of a material using the solid-liquid interface (coexistence) method.",
    "category": [
      "materials"
    ],
    "has_examples": true,
    "num_examples": 1
  },
  {
    "id": "mat-phase-diagram",
    "name": "mat-phase-diagram",
    "description": "Retrieve and visualize pre-computed phase diagrams from Materials Project for thermodynamic stability analysis.",
    "category": [
      "materials"
    ],
    "has_examples": true,
    "num_examples": 1
  },
  {
    "id": "mat-phase-field-conservative",
    "name": "mat-phase-field-conservative",
    "description": "Simulate conservative phase-fields (spinodal decomposition and phase separation) using the Cahn-Hilliard equation.",
    "category": "materials",
    "has_examples": true,
    "num_examples": 1
  },
  {
    "id": "mat-phase-field-non-conservative",
    "name": "mat-phase-field-non-conservative",
    "description": "Simulate non-conservative phase-fields (grain growth and phase transformations) using the Allen-Cahn equation.",
    "category": "materials",
    "has_examples": true,
    "num_examples": 2
  },
  {
    "id": "mat-phonon",
    "name": "mat-phonon",
    "description": "Calculate vibrational properties (phonon dispersions, density of states, thermal properties) using MLIPs.",
    "category": [
      "materials"
    ],
    "has_examples": true,
    "num_examples": 1
  },
  {
    "id": "mat-pourbaix-diagram",
    "name": "mat-pourbaix-diagram",
    "description": "Calculate Pourbaix (pH-voltage) diagrams for aqueous electrochemical stability using water-corrected MLIP energies and pymatgen.",
    "category": [
      "materials"
    ],
    "has_examples": true,
    "num_examples": 1
  },
  {
    "id": "mat-qha-thermal-expansion",
    "name": "mat-qha-thermal-expansion",
    "description": "Calculate Quasi-Harmonic Approximation (QHA) thermal properties using MLIPs.",
    "category": [
      "materials"
    ],
    "has_examples": true,
    "num_examples": 1
  },
  {
    "id": "mat-raman-spectra",
    "name": "mat-raman-spectra",
    "description": "Calculate Raman-active phonon mode frequencies and simulate Raman spectra from MLIP phonon calculations; optionally compute full Raman intensities with DFT Born charges via atomate2.",
    "category": [
      "materials"
    ],
    "has_examples": true,
    "num_examples": 1
  },
  {
    "id": "mat-random-structure-search",
    "name": "mat-random-structure-search",
    "description": "Generate random crystal structures for a given composition (AIRSS-style) and relax with MLIPs to find low-energy candidates.",
    "category": [
      "materials"
    ],
    "has_examples": true,
    "num_examples": 1
  },
  {
    "id": "mat-reaction-network",
    "name": "mat-reaction-network",
    "description": "Predict thermodynamically optimal solid-state inorganic synthesis pathways and tabulates basic reactions.",
    "category": [
      "materials"
    ],
    "has_examples": true,
    "num_examples": 2
  },
  {
    "id": "mat-sample-pes-by-md",
    "name": "mat-sample-pes-by-md",
    "description": "Sample off-equilibrium potential energy surface (PES), used for benchmarking and fine-tuning MLIPs.",
    "category": [
      "materials",
      "chemistry",
      "machine-learning"
    ],
    "has_examples": false,
    "num_examples": 0
  },
  {
    "id": "mat-solid-free-energy",
    "name": "mat-solid-free-energy",
    "description": "Calculate absolute solid Helmholtz free energy, and optional Gibbs free energy, with Frenkel-Ladd switching using portable MLIP wrappers on a pre-equilibrated periodic structure.",
    "category": [
      "materials"
    ],
    "has_examples": true,
    "num_examples": 1
  },
  {
    "id": "mat-stability",
    "name": "mat-stability",
    "description": "Calculate the thermodynamic stability and energy above the convex hull (E_hull) of a material at 0K.",
    "category": [
      "materials"
    ],
    "has_examples": true,
    "num_examples": 1
  },
  {
    "id": "mat-structure-novelty",
    "name": "mat-structure-novelty",
    "description": "Determine if a given structure matches known experimental or theoretical structures, or compare two user-provided structures.",
    "category": "materials",
    "has_examples": true,
    "num_examples": 2
  },
  {
    "id": "mat-surface-adsorption",
    "name": "mat-surface-adsorption",
    "description": "Calculate surface adsorption energies for adsorbate-surface combinations using MLIPs.",
    "category": [
      "materials",
      "chemistry"
    ],
    "has_examples": true,
    "num_examples": 1
  },
  {
    "id": "mat-surface-energy",
    "name": "mat-surface-energy",
    "description": "Calculate surface energy of various (hkl) planes and generate the equilibrium crystal shape (Wulff shape).",
    "category": [
      "materials"
    ],
    "has_examples": true,
    "num_examples": 1
  },
  {
    "id": "mat-synthesis-recommendation",
    "name": "mat-synthesis-recommendation",
    "description": "Query and rank synthesis recipes from Materials Project's text-mined literature database with precursors, procedures, and journal references.",
    "category": [
      "materials"
    ],
    "has_examples": true,
    "num_examples": 2
  },
  {
    "id": "mat-xrd-calculator",
    "name": "mat-xrd-calculator",
    "description": "Calculate the X-ray Diffraction (XRD) spectrum of a material using pymatgen.",
    "category": [
      "materials"
    ],
    "has_examples": true,
    "num_examples": 1
  },
  {
    "id": "mat-xrd-digitizer",
    "name": "mat-xrd-digitizer",
    "description": "Digitize an image of an XRD plot into a numeric .xy data file by extracting visual peaks.",
    "category": [
      "materials"
    ],
    "has_examples": true,
    "num_examples": 1
  },
  {
    "id": "mat-xrd-phase-analysis",
    "name": "mat-xrd-phase-analysis",
    "description": "Phase identification from experimental XRD using DARA's tree search (Ray-based).",
    "category": [
      "materials"
    ],
    "has_examples": true,
    "num_examples": 1
  },
  {
    "id": "mat-xrd-refinement",
    "name": "mat-xrd-refinement",
    "description": "Perform Rietveld refinement from experimental XRD patterns using DARA (BGMN).",
    "category": [
      "materials"
    ],
    "has_examples": true,
    "num_examples": 2
  },
  {
    "id": "ml-cluster-expansion",
    "name": "ml-cluster-expansion",
    "description": "train a Cluster Expansion (CE) for lattice-based Monte Carlo simulation of disordered materials.",
    "category": [
      "machine-learning",
      "materials"
    ],
    "has_examples": true,
    "num_examples": 3
  },
  {
    "id": "ml-committee-uncertainty",
    "name": "ml-committee-uncertainty",
    "description": "Quantify prediction uncertainty of MACE MLIPs using committee (ensemble) models; flag high-uncertainty structures for DFT verification.",
    "category": [
      "machine-learning",
      "materials",
      "chemistry"
    ],
    "has_examples": true,
    "num_examples": 1
  },
  {
    "id": "ml-fairchem-finetune",
    "name": "ml-fairchem-finetune",
    "description": "Fine-tune Fairchem machine learning interatomic potentials (UMA, ESEN) on custom datasets.",
    "category": [
      "machine-learning"
    ],
    "has_examples": true,
    "num_examples": 1
  },
  {
    "id": "ml-foundation-potentials",
    "name": "ml-foundation-potentials",
    "description": "Guide for selecting the most appropriate foundation MLIP model based on simulation requirements.",
    "category": [
      "machine-learning",
      "materials",
      "chemistry",
      "drug-discovery"
    ],
    "has_examples": false,
    "num_examples": 0
  },
  {
    "id": "ml-generative-adit",
    "name": "ml-generative-adit",
    "description": "Generate novel crystal structures and molecules using ADiT (All-atom Diffusion Transformer), a unified latent diffusion model.",
    "category": [
      "machine-learning",
      "materials",
      "chemistry"
    ],
    "has_examples": true,
    "num_examples": 1
  },
  {
    "id": "ml-generative-diffcsp",
    "name": "ml-generative-diffcsp",
    "description": "Generate crystal structures with exact composition control using DiffCSP++ (space group + Wyckoff positions), or unconditionally from trained distributions.",
    "category": [
      "machine-learning",
      "materials"
    ],
    "has_examples": true,
    "num_examples": 3
  },
  {
    "id": "ml-generative-mattergen",
    "name": "ml-generative-mattergen",
    "description": "Generate inorganic material structures using MatterGen, a diffusion-based generative model.",
    "category": [
      "machine-learning",
      "materials"
    ],
    "has_examples": true,
    "num_examples": 1
  },
  {
    "id": "ml-mace-finetune",
    "name": "ml-mace-finetune",
    "description": "Fine-tune MACE machine learning interatomic potentials on custom datasets.",
    "category": [
      "machine-learning"
    ],
    "has_examples": true,
    "num_examples": 1
  },
  {
    "id": "ml-matgl-finetune",
    "name": "ml-matgl-finetune",
    "description": "Fine-tune MatGL machine learning interatomic potentials on custom datasets.",
    "category": [
      "machine-learning"
    ],
    "has_examples": true,
    "num_examples": 1
  },
  {
    "id": "ml-mlip-automl",
    "name": "ml-mlip-automl",
    "description": "Automate hyperparameter tuning for MLIPs (MACE, MatGL, FairChem) using an LLM-driven search framework.",
    "category": [
      "machine-learning"
    ],
    "has_examples": false,
    "num_examples": 0
  },
  {
    "id": "ml-mlip-benchmark",
    "name": "ml-mlip-benchmark",
    "description": "Benchmark MLIP accuracy against a labeled dataset — compute MAE/RMSE for energy/atom and forces, and generate parity plots.",
    "category": [
      "machine-learning",
      "materials",
      "chemistry"
    ],
    "has_examples": true,
    "num_examples": 1
  },
  {
    "id": "ml-mlip-speed",
    "name": "ml-mlip-speed",
    "description": "Benchmark of inference speed of Machine Learning Interatomic Potentials (MLIPs).",
    "category": [
      "machine-learning"
    ],
    "has_examples": false,
    "num_examples": 0
  },
  {
    "id": "ml-property-predict-scd",
    "name": "ml-property-predict-scd",
    "description": "Train a model to predict custom properties of molecules or periodic materials using pretrained SelfConditionedDenoisingAtoms (SCD) foundation models.",
    "category": [
      "machine-learning",
      "materials",
      "chemistry"
    ],
    "has_examples": true,
    "num_examples": 2
  },
  {
    "id": "ml-property-predictor",
    "name": "ml-property-predictor",
    "description": "Train a property predictor head on top of a Machine Learning Interatomic Potential (MLIP) backbone (MACE or MatGL) to predict custom intensive or extensive properties from crystal or molecular structures.",
    "category": [
      "machine-learning",
      "materials",
      "chemistry"
    ],
    "has_examples": true,
    "num_examples": 2
  }
];
window.WORKFLOWS_DATA = [
  {
    "id": "drug-hit-finding-htvs",
    "title": "Drug Hit Finding Htvs",
    "description": "An end-to-end workflow for noncovalent, small-molecule structure-based virtual screening, from target retrieval through docking, pose validation, MD refinement, and ADMET filtering to identify drug-like hits."
  },
  {
    "id": "generative-halide-discovery",
    "title": "Generative Halide Discovery",
    "description": "An end-to-end generative AI workflow for discovering novel high-conductivity solid-state electrolytes (SSEs), specifically mapped for halide lithium-ion conductors."
  },
  {
    "id": "image-to-xrd-phase",
    "title": "Image To Xrd Phase",
    "description": "End-to-end workflow for digitizing an XRD plot image and identifying its crystalline phases."
  },
  {
    "id": "materials-discovery",
    "title": "Materials Discovery",
    "description": "An end-to-end workflow for high-throughput materials discovery, screening, and synthesizability assessment."
  },
  {
    "id": "mlip-benchmark-finetune",
    "title": "Mlip Benchmark Finetune",
    "description": "Workflow for benchmarking, fine-tuning, and distilling Machine Learning Interatomic Potentials (MLIPs)"
  },
  {
    "id": "mof-co2-dac-screening",
    "title": "Mof Co2 Dac Screening",
    "description": "End-to-end high-throughput screening of MOF databases for CO2 direct air capture (DAC), from database query through Widom insertion ranking to GCMC isotherm validation of top candidates."
  },
  {
    "id": "nmr-reaction-kinetics",
    "title": "Nmr Reaction Kinetics",
    "description": "End-to-end workflow for extracting reaction kinetics (mole fraction vs time) from time-series crude 1H NMR spectra via Wasserstein deconvolution."
  },
  {
    "id": "reaction-to-nmr-quantification",
    "title": "Reaction To Nmr Quantification",
    "description": "End-to-end workflow for predicting reaction products and quantifying them via Wasserstein deconvolution of a crude 1H NMR spectrum."
  },
  {
    "id": "sorption-discovery",
    "title": "Sorption Discovery",
    "description": "High-throughput screening out of promising porous materials for gas sorption"
  }
];
window.ATOMISTIC_STATS = {
  "skills": 120,
  "tools": 50,
  "servers": 19
};
window.SERVER_TOOLS_COUNT = {
  "drugdisc": 5,
  "diffcsp": 1,
  "fairchem": 5,
  "adit": 1,
  "mace": 6,
  "smol": 7,
  "mattergen": 1,
  "base": 11,
  "atomate2": 6,
  "matgl": 7
};