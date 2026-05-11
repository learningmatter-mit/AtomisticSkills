import argparse

import torch
from rdkit import Chem
from rdkit.Chem import AllChem


def generate_conformer(smiles, add_hs=True, optimize=True, random_seed=0):
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        raise ValueError(f"Could not parse SMILES: {smiles}")

    mol = Chem.AddHs(mol) if add_hs else Chem.Mol(mol)

    params = AllChem.ETKDGv3()
    params.randomSeed = int(random_seed)
    params.useSmallRingTorsions = True
    params.useMacrocycleTorsions = True

    status = AllChem.EmbedMolecule(mol, params)
    if status != 0:
        fallback = AllChem.ETKDGv3()
        fallback.randomSeed = int(random_seed)
        fallback.useRandomCoords = True
        fallback.useSmallRingTorsions = True
        fallback.useMacrocycleTorsions = True
        status = AllChem.EmbedMolecule(mol, fallback)

    if status != 0:
        raise ValueError(f"RDKit failed to embed a conformer for: {smiles}")

    if optimize:
        if AllChem.MMFFHasAllMoleculeParams(mol):
            mmff_props = AllChem.MMFFGetMoleculeProperties(mol, mmffVariant="MMFF94s")
            if mmff_props is not None:
                AllChem.MMFFOptimizeMolecule(mol, mmffVariant="MMFF94s")
        else:
            try:
                AllChem.UFFOptimizeMolecule(mol)
            except RuntimeError:
                pass

    conf = mol.GetConformer()
    z = torch.tensor([atom.GetAtomicNum() for atom in mol.GetAtoms()], dtype=torch.long)
    pos = torch.tensor(
        [
            [conf.GetAtomPosition(i).x, conf.GetAtomPosition(i).y, conf.GetAtomPosition(i).z]
            for i in range(mol.GetNumAtoms())
        ],
        dtype=torch.float32,
    )

    return z, pos


def main():
    parser = argparse.ArgumentParser(description="Generate a simple RDKit 3D conformer from SMILES.")
    parser.add_argument("smiles", help="Input SMILES string")
    parser.add_argument("--seed", type=int, default=0, help="Random seed for RDKit embedding")
    parser.add_argument("--no-optimize", action="store_true", help="Skip MMFF/UFF optimization")
    args = parser.parse_args()

    z, pos = generate_conformer(
        args.smiles,
        optimize=not args.no_optimize,
        random_seed=args.seed,
    )

    print(f"num_atoms={len(z)}")
    print(f"z_shape={tuple(z.shape)}")
    print(f"pos_shape={tuple(pos.shape)}")
    print("First five atomic numbers:", z[:5].tolist())
    print("First five coordinates:", pos[:5].tolist())


if __name__ == "__main__":
    main()
