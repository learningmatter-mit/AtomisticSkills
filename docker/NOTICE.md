# NOTICE: third-party software in the container images

The images published under `ghcr.io/learningmatter-mit` package this repository's
own code (MIT, see `LICENSE`) together with the software each
`venv/<name>/uv.lock` pins. This file records what that means, and the one thing
the images deliberately do not carry.

## The images carry no model weights

Every MLIP checkpoint is fetched at run time by the code that needs it, into the
mounted model cache (`ATOMISTIC_MODEL_CACHE`, `HF_HOME`, `TORCH_HOME`,
`MATGL_CACHE`), never into an image layer. Three things hold that:

- `.dockerignore` excludes `*.pt`, `*.pth`, `*.ckpt`, `*.model`, `*.traj` and
  `*.h5` from the build context, along with `**/.venv/`;
- the Dockerfiles copy only `src/`, `skills/`, `venv/` and `docker/`, then run
  `uv sync --frozen` from the locks;
- `/opt/model-cache` is a `VOLUME` that is empty at build.

The FAIRChem UMA checkpoints are why this matters. `facebook/UMA` is a gated
repository (`gated: manual`, licence `other` — the FAIR Chemistry licence), and
`fairchem-core` downloads the weights at run time with the **user's own**
`HF_TOKEN`, for a user who has been granted access. An image carrying those
weights would be redistributing them; these do not. Without a token a
`load_model` call fails with 401, which is the intended behaviour, not a bug.

The two `.pt` files inside `fairchem-core` — `models/uma/Jd.pt` (22 KB) and
`models/uma/common/quaternion/wigner_d_coefficients.pt` (30 KB) — are precomputed
Wigner-D constant tables distributed in the MIT-licensed wheel. They are not
model weights.

**Do not add a build step that pre-downloads weights.** It would turn a permitted
run-time download into a redistribution the model licences do not allow, and
would grow every image by gigabytes. Check an image with:

```bash
docker run --rm --entrypoint sh <image> -c \
  'ls -A /opt/model-cache; find / -xdev \( -name "*.ckpt" -o -name "*.safetensors" \) -size +20M'
```

A correct image prints nothing but build-time placeholders.

## Strong-copyleft packages

Most of the pinned software is permissive (MIT, BSD, Apache-2.0). These are the
exceptions, as installed in each image:

| Package           | Version  | Licence                     | Images                              |
| ----------------- | -------- | --------------------------- | ----------------------------------- |
| `pymupdf`         | 1.28.2   | AGPL-3.0 or Artifex commercial | cpu, mlip, fairchem              |
| `openbabel-wheel` | 3.1.1.23 | GPL                         | cpu, mlip, fairchem, generative     |
| `python_hostlist` | 2.3.0    | GPL-2.0+                    | mlip                                |

They arrive as dependencies of the environments in `venv/` — `pymupdf` extracts
PDF text in the paper-download and synthesis-extraction paths, and
`openbabel-wheel` ships the `obabel` converter that the docking skills invoke as
a command — not as modifications of this repository's code, and the images do
not alter them. In the generative image only the `adit` environment pulls one in.

## Corresponding source

For an image tag, the corresponding source is:

- this repository at tag `v<tag>` — `src/`, `skills/`, `docker/` and `venv/run`;
- the exact package versions in `venv/<name>/uv.lock`, for which PyPI serves the
  source distributions. To fetch one:

  ```bash
  pip download --no-binary :all: --no-deps -d /tmp/src pymupdf==1.28.2
  ```

- the base images: `ubuntu:24.04`, and for the generative image
  `nvidia/cuda:13.0.1-devel-ubuntu24.04`, redistributed under NVIDIA's container
  licence.

If you redistribute an image and need a written offer of corresponding source,
open an issue on the repository.

## Scope

This file is an inventory of what the images contain, kept so that whoever
distributes them can make the call knowingly. It is not legal advice, and it
makes no claim about obligations that apply to a given form of distribution.
