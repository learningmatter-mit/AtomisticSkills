# Container Images for AtomisticSkills

These container images serve as the automatic fallback runtime for the `venv/run` launcher and the Claude Code plugin. If a host cannot run the `uv` environments natively (due to older glibc, missing build compilers, macOS, or cluster policies), `venv/run` automatically executes commands and MCP servers inside the corresponding container image.

`docker/images.json` is the single source of truth for container images, their build strategies, platforms, and the MCP servers they carry. All derived manifests and configuration files are generated via `docker/render.py`.

## Image Inventory

| Image | Build Strategy | Servers Carried | Platforms | GPU |
| :--- | :--- | :--- | :--- | :--- |
| `atomisticskills-cpu` | `uv` (from `venv/cpu/uv.lock`) | `atomate2`, `base`, `drugdisc`, `smol` | linux/amd64, linux/arm64 | No |
| `atomisticskills-mlip` | `uv` (from `venv/mlip/uv.lock`) | `mace`, `matgl` | linux/amd64, linux/arm64 | Yes |
| `atomisticskills-fairchem` | `uv` (from `venv/fairchem/uv.lock`) | `fairchem` | linux/amd64, linux/arm64 | Yes |
| `atomisticskills-generative` | `uv` (from `venv/{adit,diffcsp,mattergen}/uv.lock`) | `adit`, `diffcsp`, `mattergen` | linux/amd64, linux/arm64 | Yes |

### Build Strategies

Every image is built from committed `venv/<name>/uv.lock` files, so a container runs the same pinned environment as a native host install.

1. **One project (`cpu`, `mlip`, `fairchem`)**: `docker/Dockerfile`, on Ubuntu 24.04 with the build tools and system programs some skills call (Boost, Packmol, fpocket).

2. **Several projects (`generative`)**: `docker/Dockerfile.cuda` installs `adit`, `diffcsp` and `mattergen` side by side on a CUDA toolkit image, for linux/amd64 and linux/arm64. On amd64 it installs PyG's wheels (they need glibc 2.32, so EL8-era hosts use this image). PyG publishes no aarch64 wheels for `torch-scatter`, `torch-sparse` and `torch-cluster`, so on arm64 the image compiles them against each environment's torch with `FORCE_CUDA=1` for `TORCH_CUDA_ARCH_LIST` (default `12.1`, GB10 / DGX Spark). Either way the build fails if they lack their CUDA kernels. Each server runs in its own environment; a command runs in the one `ATOMISTIC_VENV` names (`venv/run` passes it). The ADiT, DiffCSP++ and MatterGen source checkouts are not in the image: `venv/run` mounts them from the host (see `docs/environment_variables.md`).

## Building Images Locally

### 1. Build uv-based Images (`cpu`, `mlip`, `fairchem`)

Use `docker/Dockerfile` with build arguments `VENV` and `IMAGE_NAME`:

```bash
# CPU image
docker build -f docker/Dockerfile \
  --build-arg VENV=cpu --build-arg IMAGE_NAME=cpu \
  -t ghcr.io/learningmatter-mit/atomisticskills-cpu:dev .

# MLIP image
docker build -f docker/Dockerfile \
  --build-arg VENV=mlip --build-arg IMAGE_NAME=mlip \
  -t ghcr.io/learningmatter-mit/atomisticskills-mlip:dev .

# FairChem image
docker build -f docker/Dockerfile \
  --build-arg VENV=fairchem --build-arg IMAGE_NAME=fairchem \
  -t ghcr.io/learningmatter-mit/atomisticskills-fairchem:dev .
```

To build multi-arch images with Buildx:
```bash
docker buildx build -f docker/Dockerfile \
  --platform linux/amd64,linux/arm64 \
  --build-arg VENV=cpu --build-arg IMAGE_NAME=cpu \
  -t ghcr.io/learningmatter-mit/atomisticskills-cpu:dev .
```

### 2. Build the Generative Image

```bash
docker buildx build -f docker/Dockerfile.cuda \
  --platform linux/arm64 \
  --build-arg VENVS="adit diffcsp mattergen" --build-arg IMAGE_NAME=generative \
  --build-arg TORCH_CUDA_ARCH_LIST="12.1" --build-arg MAX_JOBS=4 \
  -t ghcr.io/learningmatter-mit/atomisticskills-generative:dev .
```

Compiling the extensions with CUDA takes a while; `MAX_JOBS` bounds the parallel `nvcc` jobs (a few GB of memory each).

## Manifest Rendering (`docker/render.py`)

Never manually edit derived configuration files. Re-render them from `docker/images.json`:

```bash
# Render venv/servers.tsv (read by venv/run)
python docker/render.py servers

# Render mcpServers block in .claude-plugin/plugin.json
python docker/render.py plugin-mcp

# Render GitHub Actions build matrix for build-images.yml
python docker/render.py matrix

# Check that rendered files are up to date (used by CI)
python docker/render.py servers --check
python docker/render.py plugin-mcp --check
```

## CI Publication

Build jobs push staging tags named `build-<run-id>-<arch>`. The publication job
runs only after every selected architecture builds successfully and the CPU
smoke tests pass. `docker/publish.py` checks that each selected image has all its
platforms, resolves this run's staging tags to digests, and only then updates
`VERSION`, `latest` and their architecture tags. A missing staging image stops
publication; older release tags are never used as substitute inputs. Manual
image filters apply to publication as well as builds. Retrying failed jobs can
reuse successful builds from the same workflow run.

## Running Servers and Commands Through Containers

The unified launcher `venv/run` mounts the repository, the workspace and the current directory at their own paths inside the container, runs as the calling user, and passes the GPU through:

```bash
# Run via Docker backend
ATOMISTIC_RUNTIME=docker venv/run cpu python skills/mat-xrd-calculator/scripts/calculate_xrd.py ...

# Start an MCP server via Docker
ATOMISTIC_RUNTIME=docker venv/run --server base
```

### Apptainer / HPC Clusters

On HPC clusters without a Docker daemon, set `ATOMISTIC_RUNTIME: apptainer` in `~/.config/atomistic_skills.yaml` (or via environment variable).

`venv/run` converts the OCI images into SIF format under `<model-cache>/sif/` with proper locking. To pre-build SIF containers ahead of time so MCP servers do not time out on first launch:
```bash
venv/run --setup
```

## Licences: What the Images Contain

An image ships this repository's MIT code plus the software its
`venv/<name>/uv.lock` pins. It carries **no model weights**: every checkpoint is
fetched at run time into the mounted model cache under the caller's own
credentials. FAIRChem's UMA is the case that makes this a rule rather than a
convenience — `facebook/UMA` is a gated repository (manual approval, the FAIR
Chemistry licence), so weights are downloaded by `fairchem-core` with the user's
`HF_TOKEN` after access is granted. An image without a token cannot obtain them,
and an image that shipped them would be redistributing them.

Never add a build step that pre-downloads weights. Verify an image with:

```bash
docker run --rm --entrypoint sh <image> -c 'ls -A /opt/model-cache; \
  find / -xdev \( -name "*.ckpt" -o -name "*.safetensors" \) -size +20M'
```

A few dependencies are strongly copyleft — `pymupdf` (AGPL-3.0 or commercial) and
`openbabel-wheel` (GPL) in `cpu`, `mlip` and `fairchem`, plus `python_hostlist`
(GPL-2.0+) in `mlip`. `docker/NOTICE.md` lists them per image and says where the
corresponding source is; it is copied into every image.

## Known Limitations

- **Generative servers on x86_64** run natively where glibc ≥ 2.32 (PyG's wheels) and from the amd64 `generative` image elsewhere.
- **GPU Driver Requirements**: On aarch64, CUDA 13 wheels require NVIDIA driver ≥ 580.
- **Model Checkpoints**: Model weights are downloaded on first use into the mounted cache directory (`ATOMISTIC_MODEL_CACHE` or `~/.cache/atomisticskills`), so they persist across container restarts and updates.
