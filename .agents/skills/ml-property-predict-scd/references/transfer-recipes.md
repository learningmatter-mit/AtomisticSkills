# Transfer Recipes

Use the checkpoint that matches the domain first:

- molecules: `ct-scd-pcq`
- materials: `ct-scd-amp`

## Frozen backbone embeddings

The upstream notebook demonstrates the core pattern:

1. download `last.ckpt` with `hf_hub_download()`
2. load the model with `models.model_helper.load_model()`
3. call the model on a PyG batch and read `out["mol_emb"]`

Recommended outputs:

- `out["mol_emb"]`: graph-level feature vector for downstream ML
- `out["atom_embs"]`: atom- or site-level feature tensor when `return_atom_embs=True`

Recommended runtime choices:

- keep the checkpoint frozen
- set `model.eval()`
- set `model.denoise = False` when the denoising head is not needed
- only pass `graph_batch=batch` when `allow_periodic` or `noise_in_loader` is active
- configure graph mode to match the task: molecules can use the compiled path, materials require loader-side graphs

Use `templates/extract_embeddings.py` as the starting point.

## Lightweight frozen-backbone training

Use `templates/train_lightweight_head.py` with one of three modes. All three keep the SCD backbone live in the forward pass.

### 1. `scalar_head`

- trains only the native `scalar_head`
- most appropriate for invariant scalar regression targets
- can use `reset_head()` when switching to a new target
- supports `set_head_agg` so the scalar-head reduction can be changed between `sum` and `mean`
- resets the checkpoint's `mean/std` output buffers to identity before downstream training

Important implementation detail:

- `scd_model.finetune()` does not by itself freeze the rest of the network, so head-only training should explicitly freeze non-`scalar_head` parameters

### 2. `atom_emb_mlp`

- obtains `atom_embs` from the frozen backbone
- pools them with `sum` or `mean`
- trains only a 1- or 2-layer MLP head
- computes features on the fly rather than relying on an offline feature cache

This is often useful when atomwise information matters but full-model finetuning is too expensive.

### 3. `mol_emb_mlp`

- obtains `mol_emb` from the frozen backbone
- trains only a 1- or 2-layer MLP head
- computes features on the fly rather than relying on an offline feature cache

This is the cleanest external-head baseline on the pretrained graph representation.

## Full-model finetuning

Use the native training path when you want the full pretrained checkpoint updated:

```bash
python train.py --conf configs/my_finetune.yaml --load-hf ct-scd-pcq --job-id my_run
```

or

```bash
python train.py --conf configs/my_finetune.yaml --load-hf ct-scd-amp --job-id my_run
```

Useful switches:

- `reset_head: true`
  reasonable default when switching from SCD pretraining to a new scalar property
- `reset_embeddings: false`
  keep pretrained atomic embeddings unless you have a strong reason to reinitialize
- `reset_norms: null`
  leave norms alone unless transfer is unstable

The recommendation on `reset_head: true` is an inference from the code: the pretraining path freezes `scalar_head`, so the public checkpoint head is not a trained downstream property head.

## Choosing between the lightweight and full-model paths

- use `scalar_head` when the target is a standard invariant scalar regression property and you want the lightest native-head adaptation
- use `atom_emb_mlp` when pooled atomwise information is likely more expressive than the native scalar head
- use `mol_emb_mlp` when you want a simple external graph-level head
- use full-model finetuning when you want the best downstream accuracy and can afford more GPU memory and training time
