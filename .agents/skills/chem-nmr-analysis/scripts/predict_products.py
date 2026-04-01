#!/usr/bin/env python3
"""
Predict reaction products from reactant/reagent SMILES via ReactionT5 (HuggingFace API).

Usage:
    # Env: nmr-agent
    export HF_TOKEN=your_token
    python predict_products.py \
        --reactant_smiles "CC1(C)C2CCC1(C)C(=O)C2" \
        --reagent_smiles "[BH4-].[Na+]" \
        --output predictions.json

Requirements: requests, rdkit (for SMILES validation)
"""

import argparse
import json
import os
import sys

import requests

_HF_API_URL = "https://router.huggingface.co/hf-inference/models/sagawa/ReactionT5v2-forward"


def _valid_smiles(s: str) -> bool:
    try:
        from rdkit import Chem
        return Chem.MolFromSmiles(s) is not None
    except Exception:
        return False


def predict_products(
    reactants_smiles: list[str],
    reagents_smiles: list[str],
    hf_token: str,
    n_best: int = 5,
) -> list[str]:
    """
    Call ReactionT5 via HuggingFace API to predict products.

    Returns list of unique predicted product SMILES.
    """
    reactants_str = " . ".join(reactants_smiles)
    reagents_str = " . ".join(reagents_smiles) if reagents_smiles else ""
    prompt = f"{reactants_str} > {reagents_str} >"

    payload = {
        "inputs": prompt,
        "parameters": {
            "max_new_tokens": 64,
            "num_beams": max(n_best, 10),
            "num_return_sequences": n_best,
            "do_sample": False,
            "early_stopping": True,
        },
    }
    headers = {"Authorization": f"Bearer {hf_token}"}

    try:
        r = requests.post(_HF_API_URL, headers=headers, json=payload, timeout=60)
        r.raise_for_status()
        response = r.json()
    except Exception as e:
        print(f"ERROR: ReactionT5 API call failed: {e}", file=sys.stderr)
        return []

    texts = []
    if isinstance(response, list):
        texts = [item.get("generated_text", "") for item in response]
    elif isinstance(response, dict) and "generated_text" in response:
        texts = [response["generated_text"]]

    seen = set()
    components = []
    for text in texts:
        # ReactionT5 returns the full input prompt + completion; extract the
        # product portion that follows the last ">" delimiter.
        parts_by_arrow = text.split(">")
        product_str = parts_by_arrow[-1].strip() if len(parts_by_arrow) > 1 else text.strip()
        for part in product_str.split("."):
            part = part.strip()
            if part and _valid_smiles(part) and part not in seen:
                seen.add(part)
                components.append(part)

    return components


def main():
    ap = argparse.ArgumentParser(
        description="Predict reaction products via ReactionT5 (HuggingFace API)."
    )
    ap.add_argument("--reactant_smiles", nargs="+", required=True,
                    help="Reactant SMILES (substrates that are transformed)")
    ap.add_argument("--reagent_smiles", nargs="+", default=[],
                    help="Reagent SMILES (facilitate reaction, not transformed)")
    ap.add_argument("--hf_token", default=os.environ.get("HF_TOKEN", ""),
                    help="HuggingFace API token (or set HF_TOKEN env var)")
    ap.add_argument("--n_best", type=int, default=5,
                    help="Number of predictions to return (default: 5)")
    ap.add_argument("--output", default=None,
                    help="Output JSON file path (default: print to stdout)")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    if not args.hf_token:
        print("ERROR: HF_TOKEN not set. Get one at https://huggingface.co/settings/tokens",
              file=sys.stderr)
        sys.exit(1)

    if not args.quiet:
        print(f"Reactants: {args.reactant_smiles}")
        print(f"Reagents:  {args.reagent_smiles}")
        print(f"Predicting products (n_best={args.n_best})...")

    products = predict_products(
        args.reactant_smiles, args.reagent_smiles,
        args.hf_token, n_best=args.n_best,
    )

    result = {
        "reactants": args.reactant_smiles,
        "reagents": args.reagent_smiles,
        "predicted_products": products,
    }

    if not args.quiet:
        print(f"  {len(products)} unique product SMILES predicted:")
        for s in products:
            print(f"    {s}")

    if args.output:
        with open(args.output, "w") as f:
            json.dump(result, f, indent=2)
        if not args.quiet:
            print(f"Output -> {args.output}")
    else:
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
