---
name: drug-pocket-detection
description: >
  Identify and rank ligandable pockets on a protein structure or model using
  geometry (fpocket) or an ML predictor (P2Rank). Returns ranked pockets with
  lining residues, geometric center, volume, and a druggability score per
  pocket. Excludes docking; pair with drug-binding-site-definition or
  drug-docking-vina downstream. Use whenever the user has a protein but no
  binding-site information, asks about cryptic / allosteric / orphan pockets,
  needs to assess druggability, or wants to choose where to dock.
category: [drug-discovery]
---

# drug-pocket-detection

## Goal

Take a protein structure (experimental or predicted) and produce a ranked list
of candidate ligandable pockets, each described by:

- A unique pocket id and rank
- A geometric center (x, y, z in Angstroms)
- An estimated volume (A^3)
- A druggability score (fpocket: logistic-regression model from Schmidtke & Barril 2010, layered on top of fpocket's own PLS-derived pocket score from Le Guilloux et al. 2009; P2Rank: a calibrated per-pocket ligandability probability)
- The lining residues (chain, resnum, resname, one-letter)
- Backend-specific raw metrics (hydrophobicity, polarity, alpha-sphere counts,
  etc.) preserved for provenance

This skill **does not** perform docking. Once you have selected a pocket, feed its center into [drug-binding-site-definition](../drug-binding-site-definition/SKILL.md) to produce a docking box, then run [drug-docking-vina](../drug-docking-vina/SKILL.md).

## Choosing a Backend

| Backend | When to use | Strengths | Weaknesses |
|---|---|---|---|
| **fpocket** (default) | First pass on any structure; lightweight (no Java, no large model file) | Fast; well-cited logistic-regression druggability score (Schmidtke & Barril 2010) layered on the underlying PLS pocket score (Le Guilloux et al. 2009); deterministic given the same parameters but slightly sensitive to floating-point details across builds | Pure geometry; misses cryptic pockets that lack a clear cavity in the input conformation |
| **P2Rank** | Independent ML pocket prediction, especially when geometry alone is ambiguous (shallow / surface pockets) or for predicted structures via the `alphafold` profile | Often higher Top-1 accuracy on benchmarks (Krivak & Hoksza 2018); residue-aware ML; reports adjacent residues directly | Heavier install (separate Java runtime + downloaded model); does not report pocket volume |

Run **both** if a decision is load-bearing (e.g., you only get one shot at MD). Compare the top-3 of each; consensus picks are stronger.

## Instructions

### 1. Prepare the protein

Prepare inputs explicitly: strip unwanted waters, buffer ions, and ligands; keep cofactors / metals only when biologically required. The
[drug-protein-prep](../drug-protein-prep/SKILL.md) skill produces a suitable input. Do not rely on backend HETATM handling as a substitute for careful preparation becuase fpocket strips many non-cofactor HETATMs but keeps a fixed cofactor set, and P2Rank's HETATM behavior should be re-validated for the installed version. Crystallographic waters / buffer ions left in the input will bias the geometry and produce decoy pockets.

### 2. Detect pockets with fpocket (default)

```bash
# Env: drugdisc-agent
python .agents/skills/drug-pocket-detection/scripts/detect_pockets.py \
  --protein receptor_prepared.pdb \
  --backend fpocket \
  --top_n 10 \
  --output_json pockets.json
```

Optional fpocket knobs (passed through to the underlying CLI; unset means fpocket's compiled-in default applies):

- `--fp_min_radius`, `--fp_max_radius`: bounds on alpha-sphere radii. Lower
  the minimum (e.g., 2.8) to detect tighter pockets; raise the maximum
  (e.g., 7.0) for shallow / surface pockets.
- `--fp_min_clust_radius`: clustering distance for alpha spheres. Lowering
  it splits one large pocket into several smaller ones.
- `--residue_cutoff` (default 5.0 A): radius around alpha-sphere centers
  used to define lining residues.

The defaults have drifted across releases and you should not assume they match what you read anywhere. Concretely, three sources can disagree at once:

- The **published 2009 paper** (Le Guilloux et al.) lists `-m 3.0`, `-M 6.0`, `-i 35`.
- The **current master-branch source** (`headers/fparams.h`) defines `M_MIN_ASHAPE_SIZE_DEFAULT 3.4`, `M_MAX_ASHAPE_SIZE_DEFAULT 6.2`, `M_MIN_POCK_NB_ASPH 15`.
- The **`fpocket -h` text** in fpocket 4.x typically shows yet another set (e.g., `(3.0)`, `(6.0)`, `(30)` for `-i`).

`-D 2.4` for the clustering distance is the consistent value in modern
4.x source and help. Because of this drift, the script never assumes a
default and always records the exact command line in the output JSON
(`backend_command`); reproducing a result requires keeping that line.

### 3. Detect pockets with P2Rank (optional ML backend)

```bash
# Env: drugdisc-agent
python .agents/skills/drug-pocket-detection/scripts/detect_pockets.py \
  --protein receptor_prepared.pdb \
  --backend p2rank \
  --top_n 10 \
  --output_json pockets_p2rank.json
```

For predicted structures (AlphaFold, NMR, cryo-EM) use the dedicated profile, which avoids relying on B-factor as a feature:

```bash
python .agents/skills/drug-pocket-detection/scripts/detect_pockets.py \
  --protein af_model.pdb \
  --backend p2rank \
  --p2rank_config alphafold \
  --output_json pockets_p2rank.json
```

P2Rank is not a Python package: install the `prank` CLI separately (see **Constraints**) and ensure it is on `PATH`. Visualization files are disabled by default (`-visualizations 0`) to keep runs fast; pass `--p2rank_visualizations` if you want them written.

### 4. Inspect and pick a pocket

The output JSON has this schema:

```json
{
  "protein": "/abs/path/receptor_prepared.pdb",
  "backend": "fpocket",
  "backend_version": "4.0",
  "backend_command": ["/abs/path/fpocket", "-f", "..."],
  "n_pockets": 5,
  "residue_cutoff_a": 5.0,
  "pockets": [
    {
      "rank": 1,
      "id": "pocket_1",
      "fpocket_index": 1,
      "druggability_score": 0.93,
      "fpocket_score": 38.2,
      "volume_a3": 612.3,
      "n_alpha_spheres": 78,
      "hydrophobicity_score": 32.4,
      "polarity_score": 13,
      "center": {"x": 14.2, "y": 24.3, "z": 5.9},
      "bounding_box": {"min": [4.0, 16.0, -3.0], "max": [24.0, 32.0, 15.0]},
      "residues": [
        {"chain": "A", "resnum": 25, "resname": "ASP", "icode": "",
         "one_letter": "D", "label": "A:ASP25"},
        "..."
      ],
      "n_residues": 24,
      "raw_metrics": { "...all fpocket info fields...": null }
    }
  ]
}
```

Schema differences by backend:

- `bounding_box`: only fpocket reports one (computed from alpha-sphere positions). `null` for P2Rank.
- `volume_a3`: only fpocket reports volume; `null` for P2Rank.
- `residue_source`: P2Rank pockets carry this extra field, set to `"p2rank"` when residues come from the predictions CSV `residue_ids` column or `"geometric_shell"` when the script falls back to a distance shell around the reported center.
- `druggability_score`: for fpocket, the logistic-regression druggability score from Schmidtke & Barril (2010); for P2Rank, the calibrated per-pocket ligandability probability. The two are *not* numerically comparable across backends. fpocket's separate underlying pocket score (PLS-derived, Le Guilloux et al. 2009) is exposed as `fpocket_score`.

**Druggability score: practical rule of thumb (fpocket logistic regression):**

| Score | Action |
|---|---|
| > 0.5 | Worth prioritizing; fpocket docs flag this as the threshold for "chance to find drug-like molecules" |
| 0.2 - 0.5 | Gray zone: inspect manually and cross-check against biology |
| < 0.2 | Lower priority for drug-like small molecules |

The broad qualitative interpretation (>0.5 promising, ~0 unlikely) is from fpocket's own documentation, building on Schmidtke & Barril (2010). The 0.2 intermediate cutoff is a workflow heuristic and not a calibrated decision boundary. The logistic-regression model has been retrained since the original publication, and performance is structure- and pocket-shape-dependent.

**Sanity checks before committing to a pocket:**

- The pocket center should lie inside the protein, not on the surface or in bulk solvent. Use `visualize_pockets.py` (next step).
- For known targets, cross-reference the lining residues against literature (catalytic residues, mutagenesis hits, conserved motifs). If none of those appear in the top pocket's residue list, you are probably looking at a decoy pocket.
- If the top fpocket pocket has a very small volume (< 200 A^3), it may be too small for typical drug-like ligands. Check the second-ranked pocket too.

### 5. Visualize the top pockets

```bash
# Env: drugdisc-agent
python .agents/skills/drug-pocket-detection/scripts/visualize_pockets.py \
  --protein receptor_prepared.pdb \
  --pockets pockets.json \
  --top_n 3 \
  --output pockets_vis.png
```

Renders the protein as a transparent cartoon, draws a colored sphere at each pocket center labeled `P1`, `P2`, `P3`, and shows the lining residues as sticks colored to match their pocket. Always inspect the image before moving on; the highest-ranked pocket geometrically is not always the biologically relevant one.

### 6. Hand off to docking

Convert the chosen pocket into a docking-box JSON consumable by the downstream skills:

```bash
# Env: drugdisc-agent
python .agents/skills/drug-pocket-detection/scripts/pocket_to_box.py \
  --pockets pockets.json \
  --rank 1 \
  --padding 6.0 \
  --min_size 20.0 \
  --output_json binding_site.json
```

The resulting `binding_site.json` matches the schema produced by [drug-binding-site-definition](../drug-binding-site-definition/SKILL.md) and can be passed directly to [drug-docking-vina](../drug-docking-vina/SKILL.md). The recorded `sizing_strategy` field tells you which heuristic was used:

- `bounding_box`: per-axis min/max from fpocket alpha-sphere positions plus padding. Most faithful for elongated / clefted pockets - they keep their shape rather than being forced into a cube.
- `volume_sphere`: equivalent-sphere radius from `volume_a3`, then a cubic box. Used when no bounding box is available.
- `default_size`: fixed cubic edge (`--default_size`, default 22 A). Used for P2Rank pockets, which report neither a bounding box nor a volume.

If you instead prefer to define the box from the pocket's residue list (rather than from its center + extent), grab the `residues[*].label` strings from the JSON and feed them into binding-site-definition Mode B. This is often the right choice for long grooves and interface pockets.

## Special Considerations

- **AlphaFold / predicted structures**: pLDDT < 70 in the pocket region means loop conformations are unreliable; the resulting pocket may be artifactual. For predicted structures, prefer P2Rank (less geometry-sensitive) or run fpocket on multiple predicted conformers (e.g., an AlphaFold MSA ensemble) and keep only pockets that appear in most conformers.
- **Cryptic pockets**: Both backends operate on a single static conformation. Cryptic pockets (which only form upon ligand binding or a conformational change) are systematically missed. To detect them, run pocket detection on trajectory snapshots from MD (e.g., every 1 ns from a 50 ns apo simulation) and union the pockets across frames.
- **Multimers and interfaces**: Both tools treat the input as one entity. For oligomeric proteins, run on the biological assembly so interface pockets are detected. fpocket will happily merge alpha spheres across chains.
- **Membrane proteins**: Pockets predicted in the transmembrane region are usually lipid-facing artifacts unless the target is genuinely intramembrane (some GPCR allosteric sites). Cross-reference the pocket center against the membrane plane.
- **Rescoring with multiple backends**: A pocket that is top-3 in both fpocket and P2Rank is much more likely to be relevant than one that is top-1 in only one backend. The two methods make different mistakes.
- **Conservation overlay**: Conservation is not computed here. If you have a ConSurf score or similar per-residue conservation, intersect it with the pocket residues post-hoc; conserved + pocket-lining residues are strong evidence of a functional site.

## Examples

See [examples/hiv1-protease/README.md](examples/hiv1-protease/README.md) for a full walkthrough on the apo HIV-1 protease (PDB 1HSG with the MK1 inhibitor removed), comparing fpocket and P2Rank rankings against the known catalytic site (Asp25/Asp25').

## Troubleshooting

- **`fpocket: command not found`**: Install via `conda install -c conda-forge fpocket` (or `mamba install`). Verify with `fpocket -h`.
- **`prank: command not found`**: Download the latest P2Rank release from https://github.com/rdk/p2rank/releases, unpack it, and either add the unpacked directory to `PATH` or symlink `prank` into a directory on `PATH`. Current P2Rank requires Java 17+ (tested up to Java 25). Run `prank --version` to confirm the install.
- **fpocket reports zero pockets**: The input is likely missing heavy atoms (only CA traces) or has badly fragmented chains. Run protein-prep first.
- **fpocket returns one giant pocket covering the whole surface**: The alpha-sphere clustering distance is too large for your structure. Lower `--fp_min_clust_radius` (try 1.4 A).
- **P2Rank predictions CSV not found**: Some prank versions write to a `predict_<stem>/` subdirectory; the script searches recursively, but make sure prank actually completed successfully (look for `*.pdb_predictions.csv` somewhere under your `--work_dir`).
- **All pockets sit on the surface, none in the active site**: Likely cause: a co-crystal ligand or cofactor was removed but its space is now empty and geometrically unfavored. Either keep the cofactor in (if it is a permanent partner), or run on a holo conformation if available.

## Constraints

- **Environment**: `drugdisc-agent`.
- **Python deps**: numpy, MDAnalysis (already in `drugdisc-agent`).
- **External CLI tools** (one of):
  - `fpocket` 4.x via conda-forge. Add to `drugdisc-agent` with `mamba install -n drugdisc-agent -c conda-forge fpocket`.
  - `prank` (P2Rank) from https://github.com/rdk/p2rank/releases. Current P2Rank requires **Java 17+** (tested up to Java 25). Very old releases (2.3 and earlier) supported Java 11+; only relevant if you are pinning to a legacy version.
- **Input**: PDB (preferred) or any format MDAnalysis can read for residue extraction. fpocket itself accepts PDB and mmCIF.
- **Pure geometry / ML on a single conformer**: cryptic pockets are missed by design. Use trajectory ensembles to detect those.
- **No conservation, no template-based detection**: the description mentions templates and conservation as conceptual inputs, but those signals are not computed here; they should be layered on post-hoc by intersecting with the reported residue lists.

## References

- Le Guilloux, V.; Schmidtke, P.; Tuffery, P. Fpocket: An Open Source Platform for Ligand Pocket Detection. *BMC Bioinformatics* **2009**, *10*, 168. https://doi.org/10.1186/1471-2105-10-168
- Schmidtke, P.; Barril, X. Understanding and Predicting Druggability. A High-Throughput Method for Detection of Drug Binding Sites. *J. Med. Chem.* **2010**, *53*, 5858-5867. https://doi.org/10.1021/jm100574m
- Krivak, R.; Hoksza, D. P2Rank: Machine Learning Based Tool for Rapid and Accurate Prediction of Ligand Binding Sites from Protein Structure. *J. Cheminform.* **2018**, *10*, 39. https://doi.org/10.1186/s13321-018-0285-8
- Cimermancic, P.; et al. CryptoSite: Expanding the Druggable Proteome by Characterization and Prediction of Cryptic Binding Sites. *J. Mol. Biol.* **2016**, *428*, 709-719. https://doi.org/10.1016/j.jmb.2016.01.029

---

**Author:** Matthew Cox
**Contact:** [GitHub @mcox3406](https://github.com/mcox3406)
