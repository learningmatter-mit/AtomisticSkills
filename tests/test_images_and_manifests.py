"""Everything derived from docker/images.json must agree with it and with reality.

plugin.json, venv/servers.tsv and the in-image server maps are rendered from
images.json; drift between them is silent until a server fails to start on a
user's machine. Image definitions must also point at things that exist: the uv
projects an image installs, and a module for every server.

Requirements:
    - Environment: cpu (run with: venv/run cpu python -m pytest tests/test_images_and_manifests.py)
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SPEC = json.loads((PROJECT_ROOT / "docker" / "images.json").read_text())
PLUGIN = json.loads((PROJECT_ROOT / ".claude-plugin" / "plugin.json").read_text())
VERSION = (PROJECT_ROOT / "VERSION").read_text().strip()

sys.path.insert(0, str(PROJECT_ROOT / "docker"))
import render  # noqa: E402
import publish as image_publish  # noqa: E402


@pytest.mark.parametrize("what", ["servers", "plugin-mcp"])
def test_rendered_files_are_current(what):
    result = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "docker" / "render.py"), what, "--check"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_every_server_has_a_module():
    for image in SPEC["images"]:
        for server, info in render.normalise_servers(image).items():
            module = PROJECT_ROOT / (info["module"].replace(".", "/") + ".py")
            assert module.is_file(), f"{server}: {module} missing"


def test_images_name_real_projects():
    """Every image installs uv projects that exist, one per server or one for all."""
    for image in SPEC["images"]:
        assert image["build"] == "uv", image["name"]
        venvs = image.get("venvs", [image.get("venv")])
        for venv in venvs:
            assert (PROJECT_ROOT / "venv" / venv / "uv.lock").is_file(), (
                image["name"],
                venv,
            )
        envs = {info["env"] for info in render.normalise_servers(image).values()}
        assert envs <= set(venvs), image["name"]


def test_multi_project_images_lock_their_platforms():
    """The generative image syncs its projects there, so each must be locked for
    the image's platforms, even where hosts do not run it natively."""
    arch = {"linux/amd64": "x86_64", "linux/arm64": "aarch64"}
    for image in SPEC["images"]:
        for venv in image.get("venvs", []):
            lock = (PROJECT_ROOT / "venv" / venv / "uv.lock").read_text()
            for platform in image["platforms"]:
                assert f"platform_machine == '{arch[platform]}'" in lock, (
                    venv,
                    platform,
                )


def test_plugin_servers_go_through_the_launcher():
    for server, config in PLUGIN["mcpServers"].items():
        assert config["command"] == "${CLAUDE_PLUGIN_ROOT}/venv/run", server
        assert config["args"] == ["--server", server]
        # The same project the agent's scripts run in, so paths agree.
        assert config["env"]["ATOMISTIC_WORKSPACE"] == "${CLAUDE_PROJECT_DIR}"
        assert config["env"]["ATOMISTIC_RUNTIME"] == "${user_config.runtime}"


def test_plugin_options_are_optional_with_defaults():
    """A non-interactive install must work without --config flags."""
    options = PLUGIN["userConfig"]
    assert set(options) == {"runtime", "image_registry", "image_tag"}
    for name, option in options.items():
        assert option.get("default") not in (None, ""), name
        assert not option.get("required", False), name
    assert options["runtime"]["default"] == "auto"


def test_default_image_tag_matches_the_release():
    """Pairing new plugin code with old images silently drops this release's fixes."""
    assert PLUGIN["userConfig"]["image_tag"]["default"] == VERSION


def test_registry_packages_are_the_built_images():
    """server.json must list the images CI builds, each with the servers it holds."""
    server_json = json.loads((PROJECT_ROOT / "server.json").read_text())
    packages = {}
    for package in server_json["packages"]:
        repo = package["identifier"].rsplit(":", 1)[0]
        packages[repo.rsplit("atomisticskills-", 1)[1]] = sorted(
            package["packageArguments"][0]["choices"]
        )
    assert packages == {
        image["name"]: sorted(image["servers"]) for image in SPEC["images"]
    }


def test_manifest_versions_agree():
    result = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "tools" / "sync_version.py"), "--check"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout


@pytest.mark.parametrize("path", ["venv/run", "docker/entrypoint.sh"])
def test_launchers_are_executable(path):
    """A non-executable launcher means every server fails to start."""
    assert os.access(PROJECT_ROOT / path, os.X_OK)


@pytest.mark.parametrize("dockerfile", ["Dockerfile", "Dockerfile.cuda"])
def test_dockerfile_copies_existing_files(dockerfile):
    text = (PROJECT_ROOT / "docker" / dockerfile).read_text()
    copied = set()
    for line in text.splitlines():
        if line.startswith("COPY ") and "--from" not in line:
            for src in line.split()[1:-1]:
                if "$" in src:
                    continue
                assert (PROJECT_ROOT / src).exists(), f"{dockerfile} copies missing {src}"
                copied.add(src)
    assert {"LICENSE", "docker/NOTICE.md"} <= copied


def test_build_matrix_covers_every_image_and_platform():
    import io
    from contextlib import redirect_stdout

    buf = io.StringIO()
    with redirect_stdout(buf):
        render.cmd_matrix(SPEC, None)
    entries = json.loads(buf.getvalue())["include"]
    expected = {(i["name"], p) for i in SPEC["images"] for p in i["platforms"]}
    assert {(e["image"], e["platform"]) for e in entries} == expected
    for e in entries:
        assert (PROJECT_ROOT / e["dockerfile"]).is_file()


class TestPerPlatformSettings:
    """Build settings are scalar where shared, keyed by platform where not."""

    def test_scalar_applies_to_every_platform(self):
        image = {"torch_cuda_arch_list": "12.1"}
        assert (
            render.per_platform(image, "torch_cuda_arch_list", "linux/amd64", "x")
            == "12.1"
        )

    def test_dict_is_looked_up_per_platform(self):
        image = {"torch_cuda_arch_list": {"linux/arm64": "12.1"}}
        assert (
            render.per_platform(image, "torch_cuda_arch_list", "linux/arm64", "x")
            == "12.1"
        )
        assert (
            render.per_platform(image, "torch_cuda_arch_list", "linux/amd64", "x")
            == "x"
        )


def test_research_dir_is_created_under_the_workspace(tmp_path, monkeypatch):
    """Inside a container the repository is read-only; the workspace is not.

    Without ATOMISTIC_WORKSPACE, create_research_dir once failed on Apptainer
    with "[Errno 30] Read-only file system: '/opt/atomisticskills/research'".
    """
    import importlib

    monkeypatch.setenv("ATOMISTIC_WORKSPACE", str(tmp_path))
    research_utils = importlib.import_module("src.utils.research_utils")
    created = research_utils.create_new_research_dir("unit_test_topic")
    assert tmp_path in created.parents and created.is_dir()


class TestImagePublication:
    """Release tags must never combine fresh builds with stale architectures."""

    REGISTRY = "ghcr.io/learningmatter-mit"
    RUN_ID = "123456"

    @pytest.fixture
    def registry(self, monkeypatch):
        images, calls = {}, []

        def docker(args, **kwargs):
            assert args[:3] == ["docker", "buildx", "imagetools"]
            calls.append(args)
            if args[3] == "inspect":
                if args[4] not in images:
                    raise subprocess.CalledProcessError(1, args)
                return subprocess.CompletedProcess(
                    args, 0, stdout=json.dumps({"digest": images[args[4]]})
                )
            assert args[3] == "create"
            return subprocess.CompletedProcess(args, 0)

        monkeypatch.setattr(image_publish.subprocess, "run", docker)
        return images, calls

    def stage(self, images, name="cpu", run_id=RUN_ID):
        base = f"{self.REGISTRY}/atomisticskills-{name}"
        for arch, digest in (("amd64", "a" * 64), ("arm64", "b" * 64)):
            images[f"{base}:build-{run_id}-{arch}"] = f"sha256:{digest}"
        return base

    def matrix(self, *names):
        return {
            "include": [
                {"image": name, "platform": f"linux/{arch}"}
                for name in names
                for arch in ("amd64", "arm64")
            ]
        }

    def test_selected_image_publishes_only_current_digests(self, registry):
        images, calls = registry
        base = self.stage(images)
        self.stage(images, "mlip")
        image_publish.publish(self.matrix("cpu"), self.REGISTRY, self.RUN_ID, VERSION)
        assert [c[3] for c in calls] == [
            "inspect",
            "inspect",
            "create",
            "create",
            "create",
        ]
        creates = [c for c in calls if c[3] == "create"]
        assert creates[0][-2:] == [f"{base}@sha256:{c * 64}" for c in ("a", "b")]
        assert f"{base}:{VERSION}" in creates[0]
        assert f"{base}:latest" in creates[0]
        assert all("atomisticskills-mlip" not in arg for c in calls for arg in c)
        assert all(":build-" not in arg for c in creates for arg in c)

    @pytest.mark.parametrize("stale", ["release", "previous-run"])
    def test_missing_current_architecture_never_uses_old_images(self, registry, stale):
        images, calls = registry
        base = self.stage(images)
        del images[f"{base}:build-{self.RUN_ID}-arm64"]
        if stale == "release":
            for tag in (f"{VERSION}-arm64", "latest-arm64"):
                images[f"{base}:{tag}"] = "sha256:" + "c" * 64
        else:
            self.stage(images, run_id="123455")
        with pytest.raises(subprocess.CalledProcessError):
            image_publish.publish(
                self.matrix("cpu"), self.REGISTRY, self.RUN_ID, VERSION
            )
        assert all(c[3] == "inspect" for c in calls)

    def test_resolves_all_selected_images_before_advancing_any_tags(self, registry):
        images, calls = registry
        self.stage(images)
        with pytest.raises(subprocess.CalledProcessError):
            image_publish.publish(
                self.matrix("cpu", "mlip"), self.REGISTRY, self.RUN_ID, VERSION
            )
        assert all(c[3] == "inspect" for c in calls)

    @pytest.mark.parametrize(
        "matrix",
        [
            {"include": []},
            {"include": [{"image": "cpu", "platform": "linux/amd64"}]},
            {"include": [{"image": "unknown", "platform": "linux/amd64"}]},
        ],
    )
    def test_invalid_selection_does_not_touch_registry(self, registry, matrix):
        _, calls = registry
        with pytest.raises(ValueError):
            image_publish.publish(matrix, self.REGISTRY, self.RUN_ID, VERSION)
        assert not calls

    def test_invalid_digest_is_not_published(self, registry):
        images, calls = registry
        base = self.stage(images)
        images[f"{base}:build-{self.RUN_ID}-arm64"] = ""
        with pytest.raises(ValueError, match="Invalid digest"):
            image_publish.publish(
                self.matrix("cpu"), self.REGISTRY, self.RUN_ID, VERSION
            )
        assert all(c[3] == "inspect" for c in calls)

    def test_publish_failure_fails_the_job(self, registry, monkeypatch):
        images, calls = registry
        self.stage(images)
        inspect = image_publish.subprocess.run

        def fail_create(args, **kwargs):
            if args[3] == "create":
                raise subprocess.CalledProcessError(1, args)
            return inspect(args, **kwargs)

        monkeypatch.setattr(image_publish.subprocess, "run", fail_create)
        with pytest.raises(subprocess.CalledProcessError):
            image_publish.publish(
                self.matrix("cpu"), self.REGISTRY, self.RUN_ID, VERSION
            )


class TestMatrixSelection:
    """A change only rebuilds the images it can affect.

    The build matrix is narrowed by diffing, because the generative image
    compiles the PyG extensions from source on arm64 and takes about two hours;
    rebuilding it for a change to `venv/mlip/uv.lock` is pure cost. Anything the
    filter cannot attribute to exactly one image must select every image, since
    building too much only wastes time while building too little ships a broken
    image.
    """

    ALL = [image["name"] for image in SPEC["images"]]

    def test_no_information_builds_everything(self):
        assert render.select_images(SPEC, set()) == self.ALL

    def test_a_project_lock_selects_only_its_image(self):
        assert render.select_images(SPEC, {"venv/mlip/uv.lock"}) == ["mlip"]
        assert render.select_images(SPEC, {"venv/fairchem/pyproject.toml"}) == [
            "fairchem"
        ]

    def test_a_multi_project_image_is_selected_by_either_project(self):
        for project in ("adit", "diffcsp", "mattergen"):
            assert render.select_images(SPEC, {f"venv/{project}/uv.lock"}) == [
                "generative"
            ]

    def test_the_build_itself_selects_everything(self):
        for path in (
            "docker/Dockerfile",
            "docker/Dockerfile.cuda",
            "docker/images.json",
        ):
            assert render.select_images(SPEC, {path}) == self.ALL, path

    def test_the_sources_images_copy_select_everything(self):
        # Images install the repository itself, so a source change can alter any
        # of them; nothing in the filter narrows that.
        for path in ("src/mcp_server/mace_server.py", "pyproject.toml", "README.md"):
            assert render.select_images(SPEC, {path}) == self.ALL, path

    def test_one_unattributable_path_selects_everything(self):
        mixed = {"venv/mlip/uv.lock", "src/utils/mlips/base.py"}
        assert render.select_images(SPEC, mixed) == self.ALL

    def test_the_real_change_this_rule_exists_for(self):
        """Both FairChem and MatGL bumps touch locks the generative image does
        not use; that image must drop out of the matrix."""
        changed = {"venv/mlip/uv.lock", "venv/fairchem/uv.lock"}
        assert render.select_images(SPEC, changed) == ["mlip", "fairchem"]

    def test_matrix_emits_only_the_selected_images(self):
        for changed, expected in (
            ([], self.ALL),
            (["venv/mlip/uv.lock"], ["mlip"]),
            (["venv/adit/uv.lock"], ["generative"]),
        ):
            argv = [
                sys.executable,
                str(PROJECT_ROOT / "docker" / "render.py"),
                "matrix",
            ]
            for path in changed:
                argv += ["--changed", path]
            result = subprocess.run(argv, capture_output=True, text=True)
            assert result.returncode == 0, result.stderr
            images = sorted({e["image"] for e in json.loads(result.stdout)["include"]})
            assert images == sorted(expected), changed
