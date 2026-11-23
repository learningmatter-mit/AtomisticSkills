# NOTICE: third-party software in the container images

The images published under `ghcr.io/learningmatter-mit` contain this repository's
code and the dependencies selected from the `venv/<name>/uv.lock` files. The
repository code is licensed under MIT; its license is shipped at
`/opt/atomisticskills/LICENSE` in every image built with this notice.
Third-party software has its own license terms.

## Model weights are downloaded at run time

The Dockerfiles do not download model checkpoints. The build context excludes
common checkpoint and trajectory formats (`*.pt`, `*.pth`, `*.ckpt`,
`*.safetensors`, `*.model`, `*.traj`, and `*.h5`) and local virtual environments.
The build leaves `/opt/model-cache` empty; the runtime uses that location for
its mounted model cache.

FAIRChem's UMA weights illustrate why this matters. `facebook/UMA` is gated and
uses the FAIR Chemistry license. FAIRChem downloads the checkpoints at run time
using the caller's Hugging Face credentials (`HF_TOKEN` or a cached login) with
access to the repository. The two small `.pt` files in `fairchem-core`, `Jd.pt`
and `wigner_d_coefficients.pt`, are precomputed Wigner-D tables, not checkpoints.
Do not add a build step that downloads weights: shipping them in an image would
be redistribution, not a run-time download by the user.

To spot-check a fresh container, replace the image below with the tag or digest
of interest. Do not bind-mount your existing model cache:

```bash
image=ghcr.io/learningmatter-mit/atomisticskills-fairchem:2.0.0
docker run --rm --entrypoint sh "$image" -ec '
  ls -A /opt/model-cache
  find / -xdev -type f \( -name "*.pt" -o -name "*.pth" -o -name "*.ckpt" \
    -o -name "*.safetensors" -o -name "*.model" -o -name "*.traj" \
    -o -name "*.h5" \) -size +20M -print
'
```

The cache listing should be empty. Review any paths printed by `find`: a large
file with a matching extension is not necessarily a checkpoint. Conversely,
this is only a spot check for large files with common extensions. `find -xdev`
stays on the image filesystem and does not descend into the separate cache
volume; the cache listing above is a separate check. No matches do not prove
that the image contains no checkpoints.

## Selected dependencies with GPL or AGPL licenses

This is not a complete license inventory. The versions and image assignments
below follow the locked environments and the Dockerfiles' selected extras.

| Package           | Version  | License                       | Images                             |
| ----------------- | -------- | ----------------------------- | ---------------------------------- |
| `pymupdf`         | 1.28.2   | AGPL-3.0 or Artifex commercial | cpu, mlip, fairchem                |
| `openbabel-wheel` | 3.1.1.23 | GPL                           | cpu, mlip, fairchem, generative     |
| `python-hostlist` | 2.3.0    | GPL-2.0-or-later              | mlip                               |
| `BoltzTraP2`      | 26.3.1   | GPL-3.0-or-later              | cpu, mlip, fairchem                |

`pymupdf` is used for PDF text extraction, and `openbabel-wheel` provides the
`obabel` command used by the docking skills. In the generative image only the
`adit` environment installs `openbabel-wheel`. `BoltzTraP2` comes in through
AMSET in the `transport` extra. GPU images also carry NVIDIA runtime packages
with their own license terms, separate from the generative image's CUDA base.

## Where to look for source and license terms

- Repository code and build files: use the repository revision that built the
  image. An image tag alone does not identify a Git commit.
- Python dependencies: use the versions and upstream sources recorded in the
  lockfiles at that revision. For example, the PyPI source distribution for
  `pymupdf` can be fetched with
  `pip download --no-binary :all: --no-deps pymupdf==1.28.2`.
- Base images: `ubuntu:24.04` and, for the generative image,
  `nvidia/cuda:13.0.1-devel-ubuntu24.04`. Consult their publishers for source and
  license information.

This notice documents packaging. It does not determine redistribution
obligations or replace the upstream license terms.
