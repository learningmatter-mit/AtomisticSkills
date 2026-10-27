# One AtomisticSkills environment as a container image, built from the same
# venv/<venv>/uv.lock that a host install uses.
#
# A host runs the uv projects natively when it can. This image is the fallback
# for hosts that cannot -- glibc too old, no compiler, macOS, or a cluster that
# prefers containers -- and it is the same environment: same lock, same
# versions, plus Ubuntu 24.04 (glibc 2.39), the build tools source packages
# need, and the compiled programs some skills call (Packmol, fpocket).
# venv/run mounts the host's paths at the same locations, so a command behaves
# identically on either side.
#
# Build one image per uv project:
#   docker buildx build -f docker/Dockerfile --build-arg VENV=mlip \
#     --platform linux/amd64,linux/arm64 -t ghcr.io/learningmatter-mit/atomisticskills-mlip:dev .
FROM ubuntu:24.04

ARG VENV=cpu
ARG IMAGE_NAME=${VENV}
ARG TARGETARCH
# fpocket (drug-pocket-detection) is not packaged by Ubuntu; build it from
# source in the image whose environment runs that skill. It links a prebuilt
# x86-64 molfile plugin, so it exists for amd64 only (as on conda-forge); on
# arm64 the skill uses its P2Rank path. The Makefile is not parallel-safe.
ARG FPOCKET_VERSION=4.2.3

ENV DEBIAN_FRONTEND=noninteractive \
    REPO_DIR=/opt/atomisticskills \
    UV_PYTHON_INSTALL_DIR=/opt/uv/python \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    PYTHONUNBUFFERED=1

# Build tools stay in the image: several packages have no wheel for one of the
# architectures and compile on install (smol, pycalphad, MDAnalysis and
# BoltzTraP2 on arm64; AutoDock Vina needs Boost and SWIG there). util-linux
# provides setpriv for the entrypoint.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates curl git util-linux \
        build-essential cmake pkg-config swig libboost-all-dev libnetcdf-dev \
        packmol \
        # libGL.so.1 for PyMOL (the pymol extra): its wheel bundles libpng,
        # freetype, libxml2, GLEW and netcdf, but not the system OpenGL loader.
        libgl1 \
        # RDKit's drawing code (rdkit.Chem.Draw, via its bundled cairo) links
        # the X11 client and render libraries, which its wheel does not bundle.
        libx11-6 libxext6 libxrender1 \
    && rm -rf /var/lib/apt/lists/*

RUN set -eux; \
    if [ "${VENV}" = "cpu" ] && [ "${TARGETARCH}" = "amd64" ]; then \
        git clone --depth 1 --branch "${FPOCKET_VERSION}" https://github.com/Discngine/fpocket.git /tmp/fpocket; \
        make -C /tmp/fpocket; \
        make -C /tmp/fpocket install; \
        rm -rf /tmp/fpocket; \
    fi

COPY --from=ghcr.io/astral-sh/uv:0.10.9 /uv /uvx /usr/local/bin/

WORKDIR ${REPO_DIR}

# The environment first, so edits to code do not invalidate the multi-GB layer.
# The repository package itself (src/) is installed after the code is copied.
COPY pyproject.toml VERSION ${REPO_DIR}/
COPY venv/${VENV}/pyproject.toml venv/${VENV}/uv.lock ${REPO_DIR}/venv/${VENV}/
# The GPU projects lock two torch builds that exclude each other (cu126, cu130);
# images carry the CUDA 13 one, so a host with a driver older than 580 runs them
# on the CPU (venv/run on the host picks cu126 there instead). The `lammps`
# extras build or run LAMMPS on the host, so images leave them out.
RUN --mount=type=cache,target=/root/.cache/uv \
    extras="--all-extras"; \
    if grep -q '^cu126 = ' venv/${VENV}/pyproject.toml; then extras="${extras} --no-extra cu126"; fi; \
    if grep -q '^lammps = ' venv/${VENV}/pyproject.toml; then extras="${extras} --no-extra lammps"; fi; \
    uv sync --frozen --project venv/${VENV} ${extras} --no-dev \
        --no-install-package atomisticskills

COPY src/ ${REPO_DIR}/src/
COPY skills/ ${REPO_DIR}/skills/
COPY venv/run venv/servers.tsv venv/platforms.tsv ${REPO_DIR}/venv/
COPY docker/entrypoint.sh docker/images.json docker/render.py docker/NOTICE.md ${REPO_DIR}/docker/
RUN --mount=type=cache,target=/root/.cache/uv \
    extras="--all-extras"; \
    if grep -q '^cu126 = ' venv/${VENV}/pyproject.toml; then extras="${extras} --no-extra cu126"; fi; \
    if grep -q '^lammps = ' venv/${VENV}/pyproject.toml; then extras="${extras} --no-extra lammps"; fi; \
    uv sync --frozen --project venv/${VENV} ${extras} --no-dev \
    && venv/${VENV}/.venv/bin/python -c "import rdkit.Chem.Draw" \
    && venv/${VENV}/.venv/bin/python docker/render.py server-map "${IMAGE_NAME}" \
        > docker/server-map.txt \
    && cat docker/server-map.txt \
    && chmod +x docker/entrypoint.sh venv/run

# `python` is the environment's interpreter for every caller: docker run,
# apptainer exec (which skips the entrypoint) and the entrypoint itself.
ENV PATH=${REPO_DIR}/venv/${VENV}/.venv/bin:${PATH} \
    VIRTUAL_ENV=${REPO_DIR}/venv/${VENV}/.venv \
    UV_NO_SYNC=1 \
    ATOMISTIC_VENV=${VENV} \
    HF_HOME=/opt/model-cache/huggingface \
    TORCH_HOME=/opt/model-cache/torch \
    MATGL_CACHE=/opt/model-cache/matgl

RUN mkdir -p /opt/model-cache /work && chmod 777 /opt/model-cache /work
VOLUME ["/opt/model-cache"]
WORKDIR /work

ENTRYPOINT ["/opt/atomisticskills/docker/entrypoint.sh"]
