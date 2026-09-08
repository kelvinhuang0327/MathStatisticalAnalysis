"""Installed-package smoke test for the packaged structural Matrix reader.

Proves the reader works from a real wheel-installed environment with no
repository-root, ``docs/``, ``.task-data/``, or database dependency: it
builds the project's own wheel, installs it (``--no-deps``, since the reader
itself needs no third-party package) into a fresh venv, and runs the reader
from a working directory outside the repository entirely.
"""

from __future__ import annotations

import subprocess
import sys
import venv
import zipfile
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]


def test_packaged_reader_works_from_an_installed_wheel(tmp_path: Path) -> None:
    dist_dir = tmp_path / "dist"
    build = subprocess.run(
        ["uv", "build", "--wheel", "--out-dir", str(dist_dir)],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert build.returncode == 0, build.stderr

    wheels = list(dist_dir.glob("*.whl"))
    assert len(wheels) == 1, wheels
    wheel_path = wheels[0]

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
