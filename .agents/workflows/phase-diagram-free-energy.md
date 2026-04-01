---
description: construct accurate, first-principles phase diagrams for molecular and elemental systems
---

# 1. The Unified Scientific Goal (Overview)

* **Shared Objective:**  *To determine, with first‑principles‑level accuracy, the temperature–pressure phase behaviour of condensed‑matter systems (molecular ices, elemental metals, molecular crystals, and elemental carbon) and to quantify the microscopic kinetics of phase transformations (melting, solid‑solid transitions, nucleation, and superionic conduction) using a combination of high‑level electronic‑structure methods, machine‑learning interatomic potentials, and rigorous free‑energy/sampling techniques.*

## Overview  
All four studies confront the same fundamental problem: **how to map a complete thermodynamic phase diagram and the associated kinetic pathways for a material whose experimental characterisation is hampered by extreme conditions, kinetic hysteresis, or metastability.**  The underlying physics is the same – a material’s free energy \(G(P,T)\) (or Helmholtz free energy \(F(V,T)\)) determines its equilibrium phases, while the height of the free‑energy barrier \(\Delta G^{\star}\) controls the rate of nucleation.  Because direct first‑principles molecular dynamics (DFT‑MD or QMC‑MD) is far too expensive to sample the long‑time, large‑scale fluctuations that govern phase coexistence and nucleation, each work builds **a surrogate potential that reproduces the electronic‑structure reference** (either a density‑functional functional, a diffusion‑Monte‑Carlo benchmark, or a high‑level DFT+phonon treatment).  Once an accurate potential is in hand, the authors:

1. **Explore the configurational space** (random structure search, metadynamics, multithermal–multibaric sampling, or direct cooling) to locate all relevant polymorphs.  
2. **Compute free energies** either through **thermodynamic integration** (harmonic → anharmonic, QHA, or alchemical pathways) or **two‑phase coexistence** simulations.  
3. **Locate phase boundaries** by equating the Gibbs free energies of competing phases (or by direct coexistence) and, when necessary, refine them with **Gibbs–Duhem integration**.  
4. **Quantify nucleation kinetics** using **enhanced‑sampling methods** (well‑tempered metadynamics, forward‑flux sampling, seeding) combined with **classical nucleation theory (CNT)** to extract interfacial free energies and kinetic prefactors.  
5. **Validate the surrogate** against the electronic‑structure reference (QMC lattice energies, DFT phonon spectra, experimental equations of state) and against experimental observables (melting points, conductivities, Raman/IR spectra).

Thus, despite the diversity of chemical systems (water, gallium, CO₂, carbon), the methodological backbone is identical: **high‑level electronic reference → machine‑learned potential → exhaustive sampling → rigorous free‑energy evaluation → kinetic analysis**.

## Key Concepts  

| Concept | Explanation & Role in the Workflow |
|---|---|
| **Density‑Functional Theory (DFT) / Quantum Monte Carlo (QMC)** | Provides the *ab‑initio* total‑energy and force reference.  QMC is used in the water study to benchmark DFT functionals (revPBE0‑D3), while DFT (LDA, PBE, revPBE0‑D3, OptB88‑vdW) supplies the reference for gallium, CO₂, and carbon. |
| **Machine‑Learning Interatomic Potentials (MLPs)** | Neural‑network models (Behler‑Parrinello, DeePMD, Neuroevolution Potential) trained on the reference data.  They deliver DFT‑quality forces at a cost comparable to classical force fields, enabling nanosecond‑scale, thousand‑atom simulations. |
| **Active‑Learning / Committee‑NN** | Iterative scheme that identifies high‑uncertainty configurations (via disagreement among committee members) and adds them to the training set, guaranteeing coverage of the whole \(P\)–\(T\) region of interest. |
| **Random Structure Search (RSS) / Metadynamics** | Global‑search algorithms that generate candidate crystal polymorphs.  RSS is used for water monolayers; metadynamics drives nucleation events in gallium. |
| **Thermodynamic Integration (TI)** | Computes free‑energy differences by integrating a reversible path (e.g., harmonic → anharmonic, alchemical scaling).  Used for water (Eq. 1), CO₂ (QHA + Birch‑Murnaghan EOS), and carbon (Gibbs–Duhem). |
| **Quasi‑Harmonic Approximation (QHA)** | Adds vibrational free‑energy contributions to static DFT energies, allowing temperature‑dependent Gibbs free energies for CO₂ phases. |
| **Two‑Phase Coexistence Simulations** | Direct MD of solid–liquid interfaces under NPT conditions; the interface motion determines the melting temperature.  Applied to water, gallium, carbon. |
| **Gibbs–Duhem Integration** | Propagates a known coexistence point along a coexistence line by integrating \(\frac{dp}{d\beta}= -\frac{\Delta h}{\beta \Delta v}\).  Used for graphite–diamond and graphite–liquid boundaries. |
| **Collective Variables (CVs) & Order Parameters** | Low‑dimensional descriptors (SOAP kernels, Steinhardt \(q_l\), coordination numbers) that bias sampling toward a target phase (diamond, graphite, α‑Ga, β‑Ga, etc.). |
| **Enhanced‑Sampling Techniques** | *Well‑Tempered Metadynamics* (biases CVs), *Forward Flux Sampling* (splits rare‑event trajectories into interfaces), *Seeding* (inserts critical nuclei).  Enable measurement of nucleation rates otherwise inaccessible to brute‑force MD. |
| **Classical Nucleation Theory (CNT)** | Provides a compact analytical expression for the nucleation rate \(R_{\rm CNT}=A\exp(-\Delta G^{\star}/k_BT)\) with \(\Delta G^{\star}=16\pi\gamma^3/(3\rho^2\Delta\mu^2)\).  Used to fit the numerically obtained rates and extract interfacial tension \(\gamma\) and kinetic prefactor \(A\). |
| **Green–Kubo Transport Formalism** | Computes ionic conductivity from the time‑integrated current autocorrelation function, applied to the superionic water monolayer. |
| **Capillary‑Wave Theory** | Relates interfacial roughness to interfacial free energy (Eq. 4 in the carbon paper), allowing facet‑specific \(\gamma\) values. |

## References  

* Paper 1: Kapil V. *et al.* “The first‑principles phase diagram of monolayer nanoconfined water.” *Nature* 609, 512–516 (2022). DOI:10.1038/s41586‑022‑05036‑x  
* Paper 2: Niu H. *et al.* “Ab initio phase diagram and nucleation of gallium.” *Nat Commun* 11, 2654 (2020). DOI:10.1038/s41467‑020‑16372‑9  
* Paper 3: *Authors omitted* “Ab initio determination of the phase diagram of CO₂ at high pressures and temperatures.” *[Journal]* (2023). DOI: [MISSING]  
* Paper 4: Donadio D. *et al.* “Metastability and Ostwald step rule in the crystallisation of diamond and graphite from molten carbon.” *Nat Commun* 16, 6324 (2025). DOI:10.1038/s41467‑025‑61674‑5  

---

# 2. The Canonical Physical Workflow (The Backbone)

Below is the **standard workflow** distilled from the four studies.  Each phase is described in terms of its physical purpose, the typical actions taken, and the expected output.

---

## Phase 1: Reference Data Generation  

**Objective:** Obtain high‑accuracy energies, forces, and stresses for a representative set of atomic configurations spanning the target \(P\)–\(T\) range.

| Action | Physics & Rationale | Typical Constraints |
|---|---|---|
| **1‑a. Choose electronic‑structure method** (QMC, DFT with a specific functional) | Provides a variationally accurate ground‑state energy surface.  The functional is selected by benchmarking (e.g., revPBE0‑D3 for water, LDA for gallium/carbon, PBE for CO₂). | *Functional* chosen by comparison to experimental lattice energies or QMC reference. |
| **1‑b. Sample configurations** (MD at diverse \(P,T\); metadynamics; multithermal–multibaric VES) | Generates configurations that include liquids, solids, transition states, and high‑energy “off‑equilibrium” structures needed for robust ML training. | *Ensembles* cover \(0\le P\le 30\) GPa (water, carbon), \(0\le P\le 2.6\) GPa (gallium), \(10\le P\le 70\) GPa (CO₂). |
| **1‑c. Compute reference observables** (total energy, forces, virial, phonons) | Supplies the supervised learning targets; phonons are needed for QHA in CO₂. | Energy convergence \(<10^{-11}\) a.u., force convergence \(<10^{-6}\) a.u. (gallium DFT). |

**Output:** A database \(\mathcal{D}=\{(\mathbf{R}_i, E_i, \mathbf{F}_i, \mathbf{S}_i)\}\) covering liquids, all solid polymorphs, and intermediate states.

---

## Phase 2: Machine‑Learning Potential Construction  

**Objective:** Build a surrogate interatomic potential that reproduces the reference data within chemical accuracy (≈ 1 kJ mol⁻¹).

| Action | Physics & Rationale | Typical Constraints |
|---|---|---|
| **2‑a. Choose ML architecture** (Behler‑Parrinello NN, DeePMD, Neuroevolution Potential) | High‑dimensional neural networks can represent the many‑body potential energy surface (PES) while respecting symmetries (translation, rotation, permutation). | Hidden layers: (240,120,60,30,10) for DeePMD (Paper 2). |
| **2‑b. Active learning / Committee‑NN** | Iteratively adds the most uncertain configurations (largest committee disagreement) to \(\mathcal{D}\) until the validation RMSE reaches a target. | Target RMSE: ≤ 2.4 meV H₂O (Paper 1), ≤ 2.8 meV atom (Paper 2). |
| **2‑c. Training & validation** | Minimizes a loss function that balances energy, force, and virial errors (weights evolve during training). | Energy RMSE ≈ [2.4 meV H₂O] (Paper 1), 2.8 meV atom (Paper 2). |
| **2‑d. Test on unseen states** (high‑T liquid, strained crystals) | Guarantees transferability across the whole phase diagram. | Validation RMSE ≤ 100 meV Å⁻¹ (Paper 1). |

**Output:** A ready‑to‑use ML potential \(V_{\rm ML}(\mathbf{R})\) that can be called from MD engines (i‑PI, LAMMPS, GPUMD).

---

## Phase 3: Exploration of Polymorphs  

**Objective:** Identify all thermodynamically relevant crystal structures (including potentially unknown phases).

| Action | Physics & Rationale | Typical Constraints |
|---|---|---|
| **3‑a. Random Structure Search (RSS)** (water) | Randomly places molecules in the confinement cell, then locally optimises with \(V_{\rm ML}\) to locate minima. | Unit‑cell sizes: 2–72 H₂O, confinement width 5–8 Å. |
| **3‑b. Metadynamics / Bias‑Enhanced Sampling** (gallium) | Adds a history‑dependent bias on SOAP CVs to drive transitions between liquid and specific solids, revealing nucleation pathways. | Gaussian height 20–300 kJ mol⁻¹, bias factor 100–320. |
| **3‑c. Direct cooling / spontaneous crystallisation** (carbon, water) | Quenches the liquid at a controlled rate; the first crystal that appears is a candidate polymorph. | Cooling rate ≈ 60 K ns⁻¹ (carbon). |
| **3‑d. Structure optimisation** (DFT or ML) | Refines the candidate structures at the target pressure to obtain accurate lattice parameters. | Convergence criteria as in Phase 1. |

**Output:** A set of candidate crystal structures \(\{\mathcal{C}_j\}\) with optimized geometries and energies.

---

## Phase 4: Free‑Energy Evaluation  

**Objective:** Compute the Gibbs (or Helmholtz) free energy of each phase as a function of \(P\) and \(T\).

| Action | Physics & Rationale | Typical Constraints |
|---|---|---|
| **4‑a. Harmonic lattice dynamics** (water, CO₂) | Calculates phonon frequencies at 0 K; yields the harmonic Helmholtz free energy \(A_{\rm harm}(T)\). | Supercell size sufficient for phonon convergence (e.g., 144 H₂O). |
| **4‑b. Quasi‑Harmonic Approximation (QHA)** (CO₂) | Allows the cell volume to relax with temperature, giving \(F(V,T)\) and thus \(G(P,T)\) via Eq. (1). | Birch‑Murnaghan EOS fitted to 3rd order. |
| **4‑c. Thermodynamic Integration (TI)** (water) | Performs a reversible path from the harmonic reference at 20 K to the fully anharmonic state at the target temperature (Eq. 1 in Paper 1). | Integration over \(\lambda\) (coupling) or temperature steps. |
| **4‑d. Two‑phase coexistence MD** (water, gallium, carbon) | Directly observes interface motion under NPT; the temperature where the interface does not move is the melting point. | System size ≈ 10 000 atoms (carbon) to suppress finite‑size effects. |
| **4‑e. Gibbs‑Duhem integration** (carbon) | Propagates a known coexistence point along a line using \(\frac{dp}{d\beta} = -\frac{\Delta h}{\beta \Delta v}\). | Step \(\Delta\beta = 0.05\) eV⁻¹. |

**Output:** For each phase \(\mathcal{C}_j\), a continuous function \(G_j(P,T)\) (or \(F_j(V,T)\)).

---

## Phase 5: Construction of Phase Boundaries  

**Objective:** Locate the set of \((P,T)\) where two phases have equal Gibbs free energy.

| Action | Physics & Rationale | Typical Constraints |
|---|---|---|
| **5‑a. Equality of Gibbs free energies** \(\,G_i(P,T)=G_k(P,T)\) | Directly yields coexistence curves (e.g., water monolayer II ↔ III, gallium liquid ↔ α‑Ga). | Interpolation between tabulated \(G\) values. |
| **5‑b. Verification by direct coexistence** | Runs a two‑phase simulation at selected points to confirm the predicted coexistence temperature. | Same protocol as 4‑d. |
| **5‑c. Triple points** | Intersection of three coexistence lines; used to benchmark against experiment (e.g., water hexatic‑liquid‑hexagonal, carbon graphite‑diamond‑liquid). | Numerical intersection of three curves. |

**Output:** Complete pressure–temperature phase diagram with stable, metastable, and triple‑point loci.

---

## Phase 6: Kinetic Analysis (Nucleation)  

**Objective:** Quantify the rate at which a metastable phase transforms into a more stable one, and identify the microscopic pathway.

| Action | Physics & Rationale | Typical Constraints |
|---|---|---|
| **6‑a. Define CVs / order parameters** (SOAP, Steinhardt \(q_l\), coordination) | Distinguish liquid, solid‑like, and polymorph‑specific environments; essential for biasing rare events. | For diamond \(q_6>0.5\) & coordination = 4; for graphite \(q_3<-0.85\) & coordination = 3. |
| **6‑b. Enhanced‑sampling runs** (WTMetaD, FFS, seeding) | Accelerates crossing of the free‑energy barrier, yielding the nucleation free‑energy profile and the critical nucleus size \(N_c\). | WTMetaD bias factor 100–320, Gaussian heights 20–300 kJ mol⁻¹. |
| **6‑c. Forward Flux Sampling (FFS)** (carbon) | Decomposes the rare event into a product of conditional probabilities across a set of interfaces \(\{\lambda_i\}\). | Initial flux measured from \(N_0=120\) crossings; each subsequent stage uses \(M_i\approx\) several hundred trials. |
| **6‑d. Seeding** (gallium) | Inserts pre‑equilibrated crystalline clusters of known size and monitors growth/shrinkage to locate the critical temperature. | Five seed sizes per phase, each equilibrated for ≈ 0.2 ns. |
| **6‑e. CNT fitting** | Fits the numerically obtained rates \(R\) to the CNT expression \(R=A\exp(-\Delta G^{\star}/k_BT)\) to extract \(\gamma_{LS}\) and kinetic prefactor \(A\). | Uses Eq. (2) from Paper 4; assumes spherical nuclei for diamond, anisotropic for graphite. |
| **6‑f. Transport calculations** (water superionic) | Green–Kubo integration of charge currents to obtain ionic conductivity. | Conductivity threshold 0.1 S cm⁻¹ defines the superionic regime. |

**Output:** Nucleation rates \(R(P,T)\), critical nucleus sizes \(N_c\), interfacial free energies \(\gamma_{LS}\), and mechanistic insight (one‑step vs. two‑step pathways, Ostwald step rule).

---

# 3. Comparative Implementation Matrix (The Variants)

| Backbone Step | Parameter / Method | Paper 1 (Water) | Paper 2 (Gallium) | Paper 3 (CO₂) | Paper 4 (Carbon) |
|---|---|---|---|---|---|
| **Reference electronic method** | Functional / QMC | revPBE0‑D3 (DFT) – benchmarked vs QMC | LDA (DFT) for training; OptB88‑vdW for validation | PBE (GGA) PAW | LDA (DFT) & OptB88‑vdW (GGA) |
| **Plane‑wave cutoff** | Energy cutoff (Ry) | [MISSING] | 600 Ry (DFT) | 200 Ry (DFT) | [MISSING] |
| **k‑point sampling** | Grid | 2 × 2 × 2 (DFT) for water | 2 × 2 × 2 (DFT) | Monkhorst‑Pack (density not specified) | [MISSING] |
| **ML architecture** | NN type | Behler‑Parrinello (committee of 8) | DeePMD (5 hidden layers) | N/A (no ML) | NEP (neuroevolution) – 3‑parameter sets |
| **Training set size** | Number of configs | ~[MISSING] (active learning ~1 k) | 28 000 (gallium) | N/A | 28 000 (carbon) |
| **Force RMSE** | meV Å⁻¹ | ≤ 100 meV Å⁻¹ (validation) | 60 meV Å⁻¹ (training) | N/A | ≤ 75 meV Å⁻¹ (water) – for carbon ≈ 75 meV Å⁻¹ |
| **Energy RMSE** | meV per atom | 2.4 meV H₂O (≈ 0.2 kJ mol⁻¹) | 2.8 meV atom | N/A | 2.8 meV atom (carbon) |
| **Structure search** | Method | Random Structure Search (RSS) with ML | Metadynamics (WTMetaD) + multithermal‑multibaric sampling | Variable‑cell DFT optimisation | Direct cooling + two‑phase simulations |
| **Free‑energy method** | TI / QHA / coexistence | Thermodynamic integration (harmonic→anharmonic) + direct coexistence | Multithermal‑multibaric free‑energy differences (ΔG) + coexistence | Quasi‑Harmonic Approximation + Birch‑Murnaghan EOS | Two‑phase coexistence + Gibbs–Duhem integration |
| **Phase‑boundary extraction** | Equality of G or interface motion | G(P,T) equality; direct coexistence | ΔG\(l\to s\) = 0; Gibbs–Duhem | G(P,T) equality (Eq. 1) | Direct coexistence + Gibbs–Duhem |
| **Nucleation sampling** | Enhanced method | Direct MD (spontaneous) + analysis of hexatic → liquid | WTMetaD (bias on SOAP) + seeding + CNT analysis | N/A | Forward Flux Sampling (FFS) + CNT fit |
| **Order parameters** | CV definition | Six‑fold orientational order (hexatic) + translational order | SOAP kernels with σ = 0.35–0.5; coordination‑based | N/A | Steinhardt \(q_l\) (l = 6 for diamond, l = 3 for graphite) + coordination |
| **Thermostat** | Algorithm | Stochastic velocity rescaling (Paper 2) / NVT (water MD) | Stochastic velocity rescaling (2 fs) | Not specified (likely NVT) | Stochastic rescaling (GPUMD) |
| **Barostat** | Algorithm | Parrinello‑Rahman (isotropic) | Isotropic Parrinello‑Rahman (τ = 1 ps) | Not specified | Stochastic cell rescaling (τ = 5 ps) |
| **Time step** | fs | 2 fs (gallium) | 2 fs (gallium) | [MISSING] | 0.5 fs (carbon) |
| **System size** | Number of atoms | 144 H₂O (water) | 144–2560 Ga (varies) | 1–2 × unit cell (DFT) | 4096 C (phase diagram) |
| **Transport property** | Conductivity calculation | Green–Kubo (ionic) | N/A | N/A | N/A |
| **Phase‑diagram validation** | Comparison to experiment | Dielectric constant, melting T, superionic conductivity | Triple point, melting T, lattice parameters | EOS vs. experimental P–V‑T data | Melting slopes, triple point, density crossover |
| **Software** | MD engine | i‑PI + LAMMPS (n2p2) | LAMMPS + PLUMED + VES | Quantum ESPRESSO | GPUMD (NEP) |

*All entries marked **[MISSING]** are not reported in the source text.*

---

# 4. Deep‑Dive Methodological Modules  

Below each module is presented as a self‑contained textbook‑style exposition, strictly derived from the supplied papers.

---

## Module A: **Active‑Learning Committee Neural‑Network Potentials**  
*Primary Source: Paper 1 (Water) – “Active learning workflow of the machine learning potential across the full phase diagram.”*

### 1. Context & Motivation  
Standard supervised training of a neural‑network potential (NNP) requires a representative dataset.  For complex phase‑space coverage (wide \(P\)–\(T\) range, polymorphic transitions) a *static* dataset often misses high‑energy or transition‑state configurations, leading to uncontrolled extrapolation errors.  An *active‑learning* loop iteratively enriches the training set with configurations that the current model finds most ambiguous.

### 2. Theoretical Formulation  

- **Committee Model:**  
  A set of \(M\) independent NNPs \(\{V^{(k)}(\mathbf{R})\}_{k=1}^{M}\) are trained on the same data but with different random seeds or data resampling.  For any configuration \(\mathbf{R}\) the **committee mean**  
  \[
  \overline{V}(\mathbf{R}) = \frac{1}{M}\sum_{k=1}^{M} V^{(k)}(\mathbf{R})
  \]
  is taken as the prediction, while the **committee standard deviation**  
  \[
  \sigma_{\rm com}(\mathbf{R}) = \sqrt{\frac{1}{M}\sum_{k=1}^{M}\bigl(V^{(k)}(\mathbf{R})-\overline{V}(\mathbf{R})\bigr)^2}
  \]
  serves as an *error estimator*.

- **Query‑by‑Committee (QbC):**  
  During a production MD run with the current committee, the *most uncertain* configurations are those with the largest \(\sigma_{\rm com}\).  A threshold \(\sigma_{\rm th}\) is defined (e.g. a few meV/atom); any frame with \(\sigma_{\rm com} > \sigma_{\rm th}\) is **selected for labeling**.

- **Iterative Loop (Generation \(g\) → \(g+1\))**  
  1. Run unbiased MD with the current committee at a set of thermodynamic points (different \(P,T\)).  
  2. Identify frames exceeding \(\sigma_{\rm th}\).  
  3. Compute reference DFT/QMC energies and forces for those frames.  
  4. Augment the training set \(\mathcal{D}^{(g)}\) → \(\mathcal{D}^{(g+1)}\).  
  5. Retrain all committee members on \(\mathcal{D}^{(g+1)}\).  
  6. Repeat until \(\sigma_{\rm com}\) is below the target for all sampled regions.

- **Error Metrics:**  
  Validation RMSEs are reported for *energy* (meV/H₂O) and *force* (meV Å⁻¹).  Convergence is declared when the validation RMSE stops decreasing significantly over successive generations.

### 3. Algorithmic Implementation  

| Step | Action |
|---|---|
| **S1** | Initialise a committee of \(M=8\) Behler‑Parrinello NNPs with random weights. |
| **S2** | Generate an *initial* training set (e.g. bulk water, known ice polymorphs). |
| **S3** | Train each NNP on the set, minimising a loss \(\mathcal{L}=w_E\Delta E^2+w_F\Delta F^2+w_S\Delta S^2\). |
| **S4** | Run MD (i‑PI + n2p2) at a *grid* of \(P,T\) points covering the target phase diagram. |
| **S5** | For every MD snapshot compute \(\sigma_{\rm com}\).  If \(\sigma_{\rm com}> \sigma_{\rm th}\), store the geometry. |
| **S6** | Perform DFT (revPBE0‑D3) single‑point calculations on the stored geometries. |
| **S7** | Append the new data to the training pool; go to **S3** (next generation). |
| **S8** | Stop when the validation RMSE is ≤ 2.4 meV H₂O (energy) and ≤ 75 meV Å⁻¹ (forces). |

The resulting **final committee** provides both a highly accurate surrogate PES and an intrinsic estimate of its own uncertainty, which can be used on‑the‑fly to flag configurations that lie outside the training domain.

---

## Module B: **Multithermal–Multibaric Variational Enhanced Sampling (VES)**  
*Primary Source: Paper 2 (Gallium) – “Multithermal–multibaric simulation” and “Collective variables”.*

### 1. Context & Motivation  
Sampling the full \(P\)–\(T\) landscape in a single simulation is impossible with a standard canonical ensemble because each \((P,T)\) requires a separate run.  VES provides a *variational* framework to construct a bias potential \(V(\mathbf{s})\) that forces the system to sample a *target distribution* \(p(\mathbf{s})\) over a set of collective variables (CVs) \(\mathbf{s}\).  By choosing \(\mathbf{s}=(E,V,\chi)\) (energy, volume, structural order) and a *flat* target distribution in a prescribed \((\beta,P)\) window, the simulation simultaneously explores many thermodynamic states.

### 2. Theoretical Formulation  

- **VES Functional:**  
  \[
  \Omega[V]=\frac{1}{\beta}\ln\!\left[\int d\mathbf{s}\, e^{-\beta\bigl(F(\mathbf{s})+V(\mathbf{s})\bigr)}\right]
  -\frac{1}{\beta}\ln\!\left[\int d\mathbf{s}\, e^{-\beta F(\mathbf{s})}\right]
  +\int d\mathbf{s}\, p(\mathbf{s})V(\mathbf{s})
  \tag{1}
  \]
  where \(F(\mathbf{s})\) is the *unbiased* free energy as a function of the CVs, and \(p(\mathbf{s})\) is the *desired* probability density (flat in the chosen energy–volume window).

- **Stationary Condition:**  
  Variation \(\delta\Omega[V]=0\) yields
  \[
  F(\mathbf{s}) = -V(\mathbf{s}) -\frac{1}{\beta}\ln p(\mathbf{s}) .
  \tag{2}
  \]
  Hence, when the bias converges, the biased simulation samples exactly \(p(\mathbf{s})\).

- **Target Distribution for Multithermal–Multibaric Sampling:**  
  Define a rectangular domain \(\{E_1<E<E_2\}\times\{V_1<V<V_2\}\times\{ \chi_{\min}<\chi<\chi_{\max}\}\).  The target is uniform:
  \[
  p(E,V,\chi)=\begin{cases}
  \frac{1}{\Omega_{E,V,\chi}} & \text{if } (E,V,\chi) \in \text{domain}\\
  0 & \text{otherwise}
  \end{cases}.
  \tag{3}
  \]
  The domain is chosen such that for any \((\beta',P')\) within the desired interval \([\beta_1,\beta_2]\times[P_1,P_2]\) there exists at least one configuration whose biased free energy satisfies  
  \(\beta' F_{\beta',P'}(E,V) < \varepsilon\) (energy cutoff).

- **Bias Representation:**  
  The bias is expanded on a basis of Legendre polynomials \(L_n\) in each CV:
  \[
  V(E,V,\chi)=\sum_{i,j,k} c_{ijk}\,L_i(E)\,L_j(V)\,L_k(\chi) .
  \]
  The coefficients \(\{c_{ijk}\}\) are updated by stochastic gradient descent to minimise \(\Omega[V]\).

### 3. Algorithmic Implementation  

| Step | Action |
|---|---|
| **B1** | Choose CVs: total potential energy \(E\), instantaneous volume \(V\), and a structural order parameter \(\chi\) (e.g. SOAP‑based kernel). |
| **B2** | Define the admissible \((E,V,\chi)\) windows (bounds in Table of Paper 2). |
| **B3** | Initialise bias coefficients \(\{c_{ijk}=0\}\). |
| **B4** | Run MD (LAMMPS + PLUMED) while accumulating the instantaneous CV values. |
| **B5** | Every *bias‑update* interval (e.g. 500 steps) compute the gradient \(\partial\Omega/\partial c_{ijk}\) and update coefficients using averaged stochastic gradient descent with step size \(\mu\) (see paper: \(\mu=5\) kJ mol⁻¹ for α‑Ga). |
| **B6** | Continue until the histogram of sampled \((E,V,\chi)\) becomes flat within statistical noise (convergence criterion). |
| **B7** | Reweight the biased trajectory to obtain unbiased estimates of observables at any \((\beta,P)\) inside the predefined window using the relation \(\langle O\rangle_{\beta,P}= \langle O\,e^{\beta V}\rangle_{\rm bias}/\langle e^{\beta V}\rangle_{\rm bias}\). |
| **B8** | Extract free‑energy differences \(\Delta G_{l\to s}(\beta,P)\) by thermodynamic integration over the reweighted ensemble. |

The VES‑biased simulation thus yields *one* trajectory from which the free energies of *all* temperatures and pressures in the chosen window can be reconstructed, dramatically reducing the total computational cost.

---

## Module C: **Quasi‑Harmonic Approximation (QHA) for Molecular Crystals**  
*Primary Source: Paper 3 (CO₂) – “Quasi‑harmonic approximation” and Eq. (1).*

### 1. Context & Motivation  
At finite temperature the vibrational contribution to the free energy can be significant, especially for light‑atom molecular crystals such as CO₂.  The QHA treats phonons as harmonic oscillators whose frequencies \(\{\omega_{\mathbf{q}\nu}(V)\}\) depend parametrically on the crystal volume \(V\).  By minimizing the Helmholtz free energy with respect to \(V\) at each temperature, thermal expansion and the temperature dependence of the equation of state are captured.

### 2. Theoretical Formulation  

- **Helmholtz Free Energy at Fixed Volume:**  
  \[
  F(V,T)=E_{\rm static}(V)+F_{\rm vib}(V,T),
  \]
  where \(E_{\rm static}(V)\) is the DFT total energy of the static lattice, and
  \[
  F_{\rm vib}(V,T)=k_B T\sum_{\mathbf{q},\nu}\ln\!\Bigl[2\sinh\!\bigl(\tfrac{\hbar\omega_{\mathbf{q}\nu}(V)}{2k_B T}\bigr)\Bigr]
  \]
  includes zero‑point energy (the \(T\to0\) limit of the logarithm).

- **Volume Optimisation at Fixed \(T\):**  
  For each temperature, solve
  \[
  \frac{\partial F(V,T)}{\partial V}=0 \quad\Rightarrow\quad P(V,T) = -\frac{\partial F}{\partial V}.
  \]
  This yields the equilibrium volume \(V_{\rm eq}(T)\) and the corresponding pressure \(P\).

- **Birch‑Murnaghan Equation of State (EOS):**  
  The computed \((V,T)\) points are fitted to a third‑order Birch‑Murnaghan EOS:
  \[
  P(V)=\frac{3B_0}{2}\Bigl[\bigl(V_0/V\bigr)^{7/3}-\bigl(V_0/V\bigr)^{5/3}\Bigr]\Bigl\{1+\frac{3}{4}(B'_0-4)\bigl[(V_0/V)^{2/3}-1\bigr]\Bigr\},
  \]
  where \(B_0\) is the bulk modulus and \(B'_0\) its pressure derivative.

- **Gibbs Free Energy:**  
  Using the EOS, the pressure is expressed as a function of volume and temperature, allowing the Gibbs free energy:
  \[
  G(P,T)=F\bigl[V(P,T),T\bigr]+P\,V(P,T) .
  \tag{1}
  \]

### 3. Algorithmic Implementation  

| Step | Action |
|---|---|
| **C1** | Perform static DFT geometry optimisation at several trial volumes (e.g. ± 5 %). |
| **C2** | Compute phonon spectra at each volume using DFPT (density‑functional perturbation theory). |
| **C3** | Evaluate \(F_{\rm vib}(V,T)\) on a temperature grid (0 K → 2000 K). |
| **C4** | Add the static energy to obtain \(F(V,T)\). |
| **C5** | For each \(T\), minimise \(F(V,T)\) with respect to \(V\) (e.g. cubic spline + Newton‑Raphson). |
| **C6** | Fit the resulting \((V,T)\) data to the Birch‑Murnaghan EOS to obtain a continuous \(P(V,T)\). |
| **C7** | Compute \(G(P,T)\) via Eq. (1); construct phase boundaries by locating pressure where \(G\) of two phases intersect. |

The QHA thereby bridges static DFT lattice energies and finite‑temperature thermodynamics without resorting to costly anharmonic MD.

---

## Module D: **Classical Nucleation Theory (CNT) with Anisotropic Interfacial Free Energies**  
*Primary Source: Paper 4 (Carbon) – Eqs. (1)–(2) and facet‑specific \(\gamma\) from capillary‑wave analysis.*

### 1. Context & Motivation  
CNT provides a simple analytic framework to relate the nucleation rate to the thermodynamic driving force \(\Delta\mu\) and the solid–liquid interfacial tension \(\gamma\).  For highly anisotropic crystals (graphite) the *shape* of the critical nucleus deviates from a sphere, but an *effective* \(\gamma\) can still be extracted by fitting the observed rate to the spherical CNT expression.

### 2. Theoretical Formulation  

- **Nucleation Rate:**  
  \[
  R_{\rm CNT}(T)=A\exp\!\Bigl[-\frac{\Delta G^{\star}}{k_B T}\Bigr],
  \tag{1}
  \]
  where \(A\) is a kinetic prefactor (often approximated as \(A\approx \rho_l Z f^+\)).

- **Barrier Height for a Spherical Nucleus:**  
  \[
  \Delta G^{\star}= \frac{16\pi\gamma_{LS}^3}{3\rho_s^2\Delta\mu^2},
  \tag{2}
  \]
  with \(\rho_s\) the number density of the solid, \(\Delta\mu = \mu_{\rm solid} - \mu_{\rm liquid}<0\).

- **Chemical Potential Approximation:**  
  Assuming the enthalpy of melting \(\Delta H_m\) is weakly temperature dependent,
  \[
  \Delta\mu \approx \Delta H_m\Bigl(1-\frac{T}{T_m}\Bigr),
  \]
  where \(T_m\) is the melting temperature at the given pressure.

- **Anisotropic Interfacial Tension (Capillary‑Wave Theory):**  
  The roughness \(\langle\sigma^2\rangle\) of a planar interface is related to \(\gamma\) by
  \[
  \gamma = \frac{k_B T}{2\pi \langle\sigma^2\rangle}\,\ln\!\Bigl(\frac{L}{\xi}\Bigr),
  \tag{4}
  \]
  where \(L\) is the lateral size of the simulation cell and \(\xi\) the bulk correlation length (first minimum of the liquid RDF).  By measuring \(\langle\sigma^2\rangle\) for different crystal facets (basal vs. prismatic graphite) one obtains facet‑specific \(\gamma\).

### 3. Algorithmic Implementation  

| Step | Action |
|---|---|
| **D1** | Compute \(\Delta H_m\) and \(T_m\) from two‑phase coexistence simulations at the pressure of interest. |
| **D2** | Estimate \(\Delta\mu(T)\) using the linear approximation above. |
| **D3** | Perform Forward‑Flux Sampling (or metadynamics) to obtain nucleation rates \(R(T)\) for the phase of interest. |
| **D4** | Fit \(R(T)\) to Eq. (1) with \(\Delta G^{\star}\) from Eq. (2); treat \(A\) and \(\gamma_{LS}\) as fitting parameters. |
| **D5** | Validate \(\gamma_{LS}\) by an independent capillary‑wave calculation (Eq. 4) on a planar solid–liquid interface. |
| **D6** | For anisotropic crystals, repeat D5 for each low‑energy facet to obtain \(\gamma_{LS}^{\rm facet}\). |
| **D7** | Use the facet‑specific \(\gamma\) to rationalise observed nucleus shapes (e.g., elongated graphite patches). |

The combined use of kinetic sampling and independent thermodynamic measurements yields a self‑consistent picture of nucleation barriers and interfacial anisotropy.

---

## Module E: **Green–Kubo Conductivity for Superionic Phases**  
*Primary Source: Paper 1 (Water) – “Electrical conductivities are estimated using Green–Kubo theory on the basis of atomistic velocities and fixed atomistic oxidation numbers.”*

### 1. Context & Motivation  
In a superionic conductor, mobile ions (protons) carry charge while the heavy lattice (oxygen) remains essentially static.  The ionic conductivity \(\sigma\) can be obtained from equilibrium MD by integrating the autocorrelation of the total charge current.

### 2. Theoretical Formulation  

- **Microscopic Charge Current:**  
  \[
  \mathbf{J}(t)=\frac{1}{V}\sum_{i} q_i \mathbf{v}_i(t),
  \]
  where \(q_i\) is the fixed oxidation number (e.g., \(+1\) for H, \(-2\) for O) and \(\mathbf{v}_i\) the velocity of atom \(i\).

- **Green–Kubo Relation:**  
  \[
  \sigma = \frac{1}{3k_B T V}\int_0^{\infty}\! \langle \mathbf{J}(t)\cdot \mathbf{J}(0)\rangle \, dt .
  \tag{G}
  \]
  The angular brackets denote an equilibrium ensemble average.

- **Practical Evaluation:**  
  The integral is approximated by a finite-time numerical integration (e.g., trapezoidal rule) up to a decorrelation time \(\tau_c\) where the autocorrelation decays to noise level.

### 3. Algorithmic Implementation  

| Step | Action |
|---|---|
| **E1** | Run a long NVT MD trajectory of the superionic water monolayer at the target \(P,T\) using the ML potential. |
| **E2** | Record atomic velocities at every MD step (timestep = 2 fs). |
| **E3** | Compute \(\mathbf{J}(t)\) on‑the‑fly using the fixed oxidation numbers. |
| **E4** | Evaluate the autocorrelation function \(C(t)=\langle \mathbf{J}(t)\cdot \mathbf{J}(0)\rangle\) via time‑averaging over the trajectory. |
| **E5** | Integrate \(C(t)\) up to the plateau region to obtain \(\sigma\) via Eq. (G). |
| **E6** | Compare \(\sigma\) to the empirical threshold \(0.1\;\text{S cm}^{-1}\) to decide whether the phase is “superionic”. |

The method yields a quantitative transport property directly comparable with experimental impedance spectroscopy.

---

# 5. Methodology Selection Guide  

| Aspect | Trade‑off Considerations | Consensus Recommendation |
|---|---|---|
| **Reference Accuracy vs. Cost** | QMC provides benchmark lattice energies (water) but is limited to a handful of points; DFT (LDA/GGA) is cheaper but functional‑dependent. | Use **DFT** as the primary reference; validate critical points with **QMC** if feasible (as in the water study). |
| **Machine‑Learning Potential Type** | Behler‑Parrinello (high‑dimensional NN) offers excellent transferability but requires careful symmetry enforcement; DeePMD and NEP are more scalable to >10 000 atoms. | For **large‑scale phase‑diagram** work (carbon, gallium) adopt **Neuroevolution/NEP** or **DeePMD**; for **smaller, highly accurate polymorph searches** (water monolayer) the **committee Behler‑Parrinello** approach is appropriate. |
| **Active‑Learning vs. Fixed Training Set** | Fixed sets risk missing transition‑state regions; active‑learning ensures coverage but adds iterative DFT calculations. | **Active‑learning with committee disagreement** is strongly recommended for any study spanning wide \(P\)–\(T\) windows. |
| **Free‑Energy Evaluation** | QHA is inexpensive but neglects anharmonicity (CO₂). Thermodynamic integration captures anharmonic effects but requires many MD windows (water). Two‑phase coexistence is robust but can be size‑sensitive. | Combine **QHA** for *rigid molecular crystals* (CO₂) with **thermodynamic integration** for *flexible or strongly anharmonic* systems (water, gallium). Validate with **two‑phase coexistence** at a few points. |
| **Nucleation Sampling** | Metadynamics yields the free‑energy surface but can bias pathways; FFS provides unbiased rate estimates but needs a good order parameter; seeding is cheap but assumes CNT validity. | **Hybrid approach**: use **metadynamics** to discover plausible CVs, then **FFS** or **seeding** for quantitative rates, finally **fit to CNT** for interfacial properties. |
| **Order Parameter Choice** | Simple coordination‑based descriptors may miss subtle structural motifs; SOAP kernels capture full local environment but are costly. | For **elemental systems** (gallium, carbon) use **SOAP‑based kernels**; for **molecular systems** (water, CO₂) combine **orientational order** (hexatic \(C_6\)) with **coordination**. |
| **Thermostat/Barostat** | Stochastic velocity rescaling and Parrinello–Rahman are robust for NPT; Nose–Hoover can produce resonance artifacts. | Adopt **stochastic velocity rescaling** for temperature and **Parrinello–Rahman** (or stochastic cell rescaling) for pressure, as done in the majority of the papers. |
| **System Size** | Small cells (< 200 atoms) suffer from finite‑size melting; > 4000 atoms needed for accurate interfacial tension (carbon). | Use **≥ 1000 atoms** for coexistence and nucleation studies; for **structure search** smaller cells (≤ 200) are acceptable. |
| **Software Stack** | i‑PI + LAMMPS + PLUMED (water, gallium) vs. GPUMD (carbon) vs. Quantum ESPRESSO (CO₂). | Choose the **MD engine that natively supports the trained ML potential** (e.g., LAMMPS with n2p2 for Behler‑Parrinello, GPUMD for NEP).  Coupling to **PLUMED** provides the needed CV infrastructure. |

**Overall Recommendation for a New Researcher**  
1. **Select a DFT functional** that reproduces known lattice energies for the system of interest (benchmark against QMC if possible).  
2. **Generate an initial training set** covering liquids, all known solid polymorphs, and a few high‑energy configurations.  
3. **Train a committee NN** (Behler‑Parrinello) or a NEP/DeePMD model using **active‑learning**; stop when validation RMSE ≤ 3 meV/atom and committee disagreement is low.  
4. **Explore polymorphs** with **random structure search** (for molecular crystals) or **metadynamics** (for metals).  
5. **Compute free energies**:  
   - Use **QHA** for rigid molecular crystals (CO₂).  
   - Use **thermodynamic integration** (harmonic → anharmonic) for flexible systems (water, gallium).  
   - Cross‑check with **two‑phase coexistence** at selected points.  
6. **Map phase boundaries** by equating Gibbs free energies; refine with **Gibbs–Duhem integration**.  
7. **Quantify nucleation**:  
   - Define robust CVs (SOAP, Steinhardt \(q_l\), coordination).  
   - Run **WTMetaD** to locate the transition state; extract bias‑free free‑energy profile.  
   - Perform **FFS** (or seeding) to obtain rates; fit to **CNT** to extract \(\gamma_{LS}\) and \(A\).  
8. **Validate** against experimental melting lines, triple points, and transport measurements (e.g., ionic conductivity).  

Following this protocol yields a **reproducible, high‑accuracy phase diagram** together with **quantitative nucleation kinetics**, exactly as demonstrated across the four exemplary studies.
