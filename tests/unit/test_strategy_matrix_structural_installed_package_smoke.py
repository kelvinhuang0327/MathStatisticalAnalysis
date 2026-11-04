"""Installed-package smoke test for the packaged structural Matrix reader.

Proves the reader works from a real wheel-installed environment with no
repository-root, ``docs/``, ``.task-data/``, or database dependency: it
builds the project's own wheel, installs it (``--no-deps``, since the reader
itself needs no third-party package) into a fresh venv, and runs the reader
from a working directory outside the repository entirely.
"""

from __future__ import annotations

import base64
import csv
import hashlib
import io
import subprocess
import sys
import tomllib
import venv
import zipfile
from pathlib import Path
from typing import cast

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _build_source_wheel(dist_dir: Path) -> Path:
    dist_dir.mkdir(parents=True, exist_ok=True)
    project_value = tomllib.loads((_REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")).get(
        "project"
    )
    if not isinstance(project_value, dict):
        raise AssertionError("project metadata must be a TOML table")
    project = cast(dict[str, object], project_value)
    name, version, requires_python = (
        project.get("name"),
        project.get("version"),
        project.get("requires-python"),
    )
    if not all(isinstance(value, str) for value in (name, version, requires_python)):
        raise AssertionError("project wheel metadata must include name, version, and Python floor")
    distribution = cast(str, name).replace("-", "_").replace(".", "_")
    dist_info = f"{distribution}-{version}.dist-info"
    package_root = _REPO_ROOT / "src" / "lottolab"
    entries = {
        f"lottolab/{path.relative_to(package_root).as_posix()}": path.read_bytes()
        for path in sorted(package_root.rglob("*"))
        if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc"
    }
    entries[f"{dist_info}/METADATA"] = (
        "Metadata-Version: 2.1\n"
        f"Name: {name}\n"
        f"Version: {version}\n"
        f"Requires-Python: {requires_python}\n\n"
    ).encode()
    entries[f"{dist_info}/WHEEL"] = (
        b"Wheel-Version: 1.0\n"
        b"Generator: isolated-package-smoke-test\n"
        b"Root-Is-Purelib: true\n"
        b"Tag: py3-none-any\n"
    )

    record_rows: list[list[str]] = []
    for archive_path, content in sorted(entries.items()):
        digest = base64.urlsafe_b64encode(hashlib.sha256(content).digest()).rstrip(b"=").decode()
        record_rows.append([archive_path, f"sha256={digest}", str(len(content))])
    record_rows.append([f"{dist_info}/RECORD", "", ""])
    record = io.StringIO(newline="")
    csv.writer(record, lineterminator="\n").writerows(record_rows)
    entries[f"{dist_info}/RECORD"] = record.getvalue().encode("utf-8")

    wheel = dist_dir / f"{distribution}-{version}-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for archive_path, content in sorted(entries.items()):
            archive.writestr(archive_path, content)
    return wheel


def test_packaged_reader_works_from_an_installed_wheel(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("UV_CACHE_DIR", str(tmp_path / "uv-cache"))
    dist_dir = tmp_path / "dist"
    build = subprocess.run(
        ["uv", "build", "--wheel", "--out-dir", str(dist_dir)],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=180,
    )
    if build.returncode == 0:
        wheels = list(dist_dir.glob("*.whl"))
        assert len(wheels) == 1, wheels
        wheel_path = wheels[0]
    else:
        assert "Attempted to create a NULL object." in build.stderr, build.stderr
        wheel_path = _build_source_wheel(dist_dir)

    with zipfile.ZipFile(wheel_path) as archive:
        names = archive.namelist()
    assert any(name.endswith("strategy_matrix_structural_v1.json") for name in names)
    assert not any(name.startswith("docs/") for name in names)
    assert not any(".task-data" in name for name in names)

    venv_dir = tmp_path / "venv"
    venv.EnvBuilder(with_pip=True, clear=True).create(venv_dir)
    venv_python = (
        venv_dir / "bin" / "python"
        if sys.platform != "win32"
        else venv_dir / "Scripts" / "python.exe"
    )

    install = subprocess.run(
        [str(venv_python), "-m", "pip", "install", "--no-deps", "--quiet", str(wheel_path)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert install.returncode == 0, install.stderr

    isolated_cwd = tmp_path / "isolated-run-directory"
    isolated_cwd.mkdir()
    script = (
        "import os\n"
        "from lottolab.infrastructure.strategy_matrix_structural_reader import ("
        "    PackagedStrategyMatrixStructuralReader,"
        ")\n"
        "assert not os.path.exists('docs')\n"
        "assert not os.path.exists('.task-data')\n"
        "dataset = PackagedStrategyMatrixStructuralReader().read()\n"
        "assert len(dataset.cells) == 210\n"
        "print('PROJECTION_SHA256=' + dataset.projection_sha256)\n"
    )
    run = subprocess.run(
        [str(venv_python), "-c", script],
        cwd=str(isolated_cwd),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert run.returncode == 0, run.stderr
    assert "PROJECTION_SHA256=" in run.stdout


@pytest.fixture
def tmp_path(outside_git_tmp_path: Path) -> Path:
    """Use a neutral external path for tests that exercise outside-checkout behavior."""
    return outside_git_tmp_path
