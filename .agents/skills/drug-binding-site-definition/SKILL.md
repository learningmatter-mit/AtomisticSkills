---
name: drug-binding-site-definition
description: >
  Define a docking search box (center coordinates + box dimensions in Angstroms) from a co-crystal
  ligand, binding-site residues, or a saved JSON specification. Use this skill whenever the user
  mentions binding site, docking box, search box, grid box, active site definition, or pocket
  definition, or needs to specify where to dock ligands on a protein. Also use when the user has a
  protein target but needs help figuring out where to dock before running a docking skill.
category: [drug-discovery]
---

# drug-binding-site-definition

## Goal

To produce a standardized **docking / simulation box definition** (center coordinates + box dimensions in Angstroms) that downstream skills such as [drug-docking-vina](../drug-docking-vina/SKILL.md) and [drug-complex-system-builder](../drug-complex-system-builder/SKILL.md) can consume directly.

## Choosing the Right Mode

Use this decision tree to pick the appropriate approach:

```
Do you have a reference ligand positioned in the binding site?
  |-- YES --> Mode A (co-crystal ligand)
  |-- NO
       Do you know the key binding-site residues (from literature, mutagenesis, etc.)?
         |-- YES --> Mode B (residue list)
         |-- NO
              Do you have a closely related protein with a known binding site?
                |-- YES --> Superimpose structures, transfer the ligand,
                |           then use Mode A on the transferred ligand.
                |           (See "When You Have No Binding-Site Information" below.)
                |-- NO  --> Run computational pocket prediction first
                            (see "When You Have No Binding-Site Information" below),
                            then feed results into Mode A or B.
```

If you already have a saved box JSON from a prior run, use Mode C to reload it.

## Instructions

### 1. Mode A: Box from a co-crystal ligand (most common)

If you have a reference ligand already positioned in the binding site (PDB, SDF, MOL2, or PDBQT), compute the box automatically:

```bash
# Env: drugdisc-agent
python .agents/skills/drug-binding-site-definition/scripts/define_binding_site.py \
  --mode ligand \
  --ligand_file docking/inputs/reference_ligand.sdf \
  --padding 6.0 \
  --min_size 20.0 \
  --output_json docking/inputs/binding_site.json
```

Key parameters:
- `--padding`: buffer added to the ligand bounding box on each side (default 6.0 A). Use 4-5 A for tight/buried pockets, 8-10 A for shallow or allosteric sites.
- `--min_size`: minimum box edge length per axis (default 20.0 A).

The ligand **must** be in the same coordinate frame as the receptor. If it comes from a different crystal structure, superimpose first.

### 2. Mode B: Box from binding-site residues

When no co-crystal ligand is available but you know the key binding-site residues (e.g., from literature or mutagenesis data):

```bash
# Env: drugdisc-agent
python .agents/skills/drug-binding-site-definition/scripts/define_binding_site.py \
  --mode residues \
  --protein_file protein_prepared.pdb \
  --residues "A:ASP25,A:THR26,A:GLY27,A:ILE50,A:ASP124,A:THR125,A:GLY126" \
  --padding 8.0 \
  --min_size 20.0 \
  --output_json docking/inputs/binding_site.json
```

Residue format: comma-separated `chain:resname+resid` (e.g., `A:ASP25`). You can omit the chain prefix (e.g., `25,26,27,50`) only if the protein contains a **single chain**; for multi-chain structures always include the chain ID to avoid ambiguity.

### 3. Mode C: Load a saved box definition

Re-use a previously computed box:

```bash
# Env: drugdisc-agent
python .agents/skills/drug-binding-site-definition/scripts/define_binding_site.py \
  --mode json \
  --input_json docking/inputs/binding_site.json
```

This validates the JSON and prints the box to stdout for inspection.

### 4. Interpret and validate the output

The output JSON has the following schema:

```json
{
  "center_x": 16.0,
  "center_y": 25.0,
  "center_z": 2.0,
  "size_x": 22.0,
  "size_y": 24.0,
  "size_z": 20.0,
  "padding": 6.0,
  "min_size": 20.0,
  "mode": "ligand",
  "source": "reference_ligand.sdf"
}
```

All coordinates and dimensions are in Angstroms.

Always verify that the box covers the expected pocket before docking. If PyMOL is available, use the included visualization script to render the box as a wireframe overlay:

```bash
# Env: drugdisc-agent
python .agents/skills/drug-binding-site-definition/scripts/visualize_box.py \
  --protein docking/inputs/protein_prepared.pdb \
  --box docking/inputs/binding_site.json \
  --ligand_resname MK1 \
  --output docking/inputs/box_visualization.png
```

This produces a ray-traced PNG showing the protein (cartoon), ligand (yellow sticks), and docking box (red wireframe). The `--ligand_resname` flag is optional; omit it if no ligand is present.

If no viewer is available, at minimum sanity-check that the box center falls near the expected pocket by comparing coordinates to known active-site residues in the PDB.

## When You Have No Binding-Site Information

If you have a protein structure but no co-crystal ligand and no literature on binding-site residues, you need to identify candidate pockets before defining a docking box.

### Homology-based site transfer

If a homologous protein (>30% sequence identity) has a co-crystal structure, superimpose your target onto the template and extract the ligand coordinates in your target's reference frame. Then use Mode A on the transferred ligand. This is often the most reliable approach when a good template exists.

### Computational pocket prediction

Open-source tools can identify probable binding pockets from protein geometry alone:

- **fpocket** (recommended, lightweight): identifies pockets via Voronoi tessellation and alpha spheres. Run it, pick the top-ranked pocket, extract its residues, and feed them into Mode B.
- **P2Rank**: ML-based pocket predictor, often more accurate than fpocket on benchmarks.
- **DoGSiteScorer**: web-based alternative if local tools are not available.

Pocket prediction is a starting point, not ground truth. Always cross-reference predicted sites against any available functional data (conservation scores, mutagenesis, known mechanism) before committing to a docking box.

### Blind docking (last resort)

If no structural or functional clues exist, you can define a box that covers the entire protein surface. This is computationally expensive and less reliable. To generate a whole-protein box, use Mode B with all surface residues, or manually set a large box (40-60 A per side) centered on the protein centroid. Treat blind docking results as hypothesis-generating, not definitive.

## Special Considerations

- **AlphaFold / predicted structures**: These lack experimental ligand density and may have unreliable loop conformations near potential pockets. Use wider padding (8-10 A), cross-reference with pocket prediction tools, and check pLDDT confidence scores (regions with pLDDT < 70 near the pocket boundary are a red flag).
- **Multiple binding sites**: Many targets (kinases, GPCRs, allosteric enzymes) have more than one druggable pocket. Run the skill separately for each site, producing one JSON per pocket (e.g., `binding_site_orthosteric.json`, `binding_site_allosteric.json`).
- **Covalent binding sites**: Center the box on the reactive residue (e.g., a catalytic cysteine) using Mode B with that residue as the anchor, plus neighboring pocket residues. Use tighter padding (4-5 A).
- **Oligomeric interface sites**: Some binding sites span the interface between protein chains (e.g., the HIV-1 protease active site spans a homodimer interface). Make sure the input structure contains the full biological assembly, not just a single chain.
- **Membrane proteins**: For GPCRs, ion channels, and other membrane-embedded targets, the docking box may extend into the lipid bilayer region. Constrain the box to avoid the transmembrane region unless the binding site is intramembrane (e.g., some GPCR orthosteric sites).
- **Flexible / cryptic pockets**: Some pockets only form upon ligand binding or conformational change. A static docking box cannot capture these. Consider ensemble docking across multiple conformations (e.g., from MD snapshots) with separate box definitions for each conformer.

## Examples

### Example: HIV-1 protease (PDB 1HSG), box from co-crystal ligand

This target is a homodimer; make sure you use the biological assembly containing both chains.

```bash
# Env: drugdisc-agent
python .agents/skills/drug-binding-site-definition/scripts/define_binding_site.py \
  --mode ligand \
  --ligand_file hiv_docking/inputs/indinavir_ref.sdf \
  --padding 6.0 \
  --output_json hiv_docking/inputs/binding_site.json
```

### Example: Box from known active-site residues

```bash
# Env: drugdisc-agent
python .agents/skills/drug-binding-site-definition/scripts/define_binding_site.py \
  --mode residues \
  --protein_file hiv_docking/inputs/1HSG_prepared.pdb \
  --residues "A:ASP25,A:THR26,A:GLY27,A:ALA28,A:ILE50" \
  --padding 8.0 \
  --output_json hiv_docking/inputs/binding_site.json
```

## Troubleshooting

- **"No atom coordinates found in \<file\>"**: The ligand file is empty or in an unsupported format. Verify the file has atoms (`grep "^HETATM" ligand.pdb | wc -l` for PDB, or open in a viewer). Convert to SDF using Open Babel if needed: `obabel ligand.mol2 -O ligand.sdf`.
- **"No atoms found for residues: ..."**: The residue ID does not match the PDB numbering. Check for insertion codes (e.g., `27A`), non-standard numbering, or mismatched chain IDs. Run `grep "^ATOM" protein.pdb | awk '{print $5, $6}' | sort -u` to see available chain + residue ID combinations.
- **Box is unexpectedly large or offset**: Common causes include alternate conformations (altlocs) inflating the bounding box, or the ligand file containing multiple poses/conformers. Keep only the relevant conformer (altloc A) and a single ligand pose before defining the box.
- **Box extends outside the protein**: Usually means the padding is too large relative to the pocket. Reduce `--padding` or verify that the ligand/residues are actually in the pocket you intended.

## Constraints

- **Environment**: Requires `drugdisc-agent`.
- **Ligand mode**: Accepts PDB, SDF, MOL2, and PDBQT formats. The ligand must already be positioned in the receptor coordinate frame.
- **Residue mode**: The protein file must be a PDB with standard residue numbering. Non-standard residue IDs or insertion codes may require explicit `chain:resid` specification.
- **Box sizing**: For standard docking, 20-25 A per axis is typical. Boxes larger than 30 A significantly increase Vina runtime and reduce pose accuracy (Feinstein & Brylinski, 2015). Blind docking with boxes of 40-60 A is possible but should be treated as exploratory.

## References

- Feinstein, W. P.; Brylinski, M. Calculating an Optimal Box Size for Ligand Docking and Virtual Screening against Experimental and Predicted Binding Pockets. *J. Cheminform.* **2015**, *7*, 18. https://doi.org/10.1186/s13321-015-0067-5
- Le Guilloux, V.; Schmidtke, P.; Tuffery, P. Fpocket: An Open Source Platform for Ligand Pocket Detection. *BMC Bioinformatics* **2009**, *10*, 168. https://doi.org/10.1186/1471-2105-10-168
- Krivak, R.; Hoksza, D. P2Rank: Machine Learning Based Tool for Rapid and Accurate Prediction of Ligand Binding Sites from Protein Structure. *J. Cheminform.* **2018**, *10*, 39. https://doi.org/10.1186/s13321-018-0285-8

---

**Author:** Matthew Cox
**Contact:** [GitHub @mcox3406](https://github.com/mcox3406)
