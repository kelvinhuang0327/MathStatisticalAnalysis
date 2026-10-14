"""Replay fixed B649 results with the pinned source and project interpreter."""

from __future__ import annotations

import importlib
import io
import os
import pickle
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path
from typing import Literal, cast

_ROOT = Path(__file__).resolve().parents[2]
_SNAPSHOT_HEAD = "204f668efe88ab71cb55df3e71cc12948252a450"
_SNAPSHOT_TREE = "9b31b53b79a5ee012055e1c77e486ec05552088a"
_EXPECTED_PYTHON = (3, 13, 8)
_ALLOWED_OPERATIONS = {"compute_result", "verify_result"}
_SNAPSHOT_DIRECTORY = tempfile.TemporaryDirectory(prefix="b649-certificate-source-")
_SNAPSHOT_ROOT = Path(_SNAPSHOT_DIRECTORY.name).resolve()
_GIT_OVERLAY_DIRECTORY = tempfile.TemporaryDirectory(prefix="b649-certificate-git-")
_GIT_OVERLAY = Path(_GIT_OVERLAY_DIRECTORY.name)

_CHILD = """
import importlib
import os
import pickle
import subprocess
import sys
from pathlib import Path

root = Path.cwd().resolve()
project_version = tuple(
    int(part) for part in (root / ".python-version").read_text().strip().split(".")
)
expected_version = (3, 13, 8)
if (
    project_version != expected_version[: len(project_version)]
    or sys.version_info[:3] != expected_version
):
    raise SystemExit(
        f"expected project Python {expected_version}, got {sys.version_info[:3]}"
    )
git_root = Path(
    subprocess.check_output(["git", "rev-parse", "--show-toplevel"], cwd=root, text=True).strip()
).resolve()
if git_root != root:
    raise SystemExit("certificate replay is not bound to the fixed Git worktree")
sys.path.insert(0, str(root))
sys.path.insert(0, str(root / "src"))
module_name, operation = sys.argv[1:3]
if operation not in {"compute_result", "verify_result"}:
    raise SystemExit(f"unsupported certificate operation: {operation}")
certificate = importlib.import_module(module_name)
if Path(certificate.__file__).resolve().parents[3] != root:
    raise SystemExit("certificate did not load from the pinned source snapshot")
arguments = pickle.loads(sys.stdin.buffer.read())
if len(sys.argv) == 5:
    repo = Path(sys.argv[3]).resolve()
    os.environ.pop("GIT_WORK_TREE", None)
    os.environ["GIT_DIR"] = str(repo)
    os.environ["GIT_ALTERNATE_OBJECT_DIRECTORIES"] = sys.argv[4]
try:
    value = getattr(certificate, operation)(*arguments)
except Exception as error:
    outcome = ("error", type(error).__module__, type(error).__name__, str(error))
else:
    outcome = ("ok", value)
response = (
    "b649-certificate-replay-v1",
    sys.executable,
    tuple(sys.version_info[:3]),
    sys.flags.isolated,
    str(Path(certificate.__file__).resolve()),
    outcome,
)
sys.stdout.buffer.write(pickle.dumps(response, protocol=5))
"""


def _git(args: list[str], *, environment: dict[str, str], text: bool = True) -> str | bytes:
    return subprocess.check_output(args, cwd=_ROOT, env=environment, text=text)


def _prepare_source_snapshot() -> tuple[str, Path]:
    environment = os.environ.copy()
    for name in tuple(environment):
        if name.startswith("GIT_"):
            environment.pop(name)

    source_tree = cast(
        str,
        _git(
            ["git", "rev-parse", f"{_SNAPSHOT_HEAD}^{{tree}}"],
            environment=environment,
        ),
    ).strip()
    if source_tree != _SNAPSHOT_TREE:
        raise ValueError("fixed source TREE does not match the B649 certificate input")

    git_dir = cast(
        str,
        _git(["git", "rev-parse", "--absolute-git-dir"], environment=environment),
    ).strip()
    common_dir = cast(
        str,
        _git(["git", "rev-parse", "--git-common-dir"], environment=environment),
    ).strip()
    common_path = Path(common_dir)
    if not common_path.is_absolute():
        common_path = (_ROOT / common_path).resolve()

    archive = cast(
        bytes,
        _git(
            ["git", "archive", "--format=tar", _SNAPSHOT_HEAD],
            environment=environment,
            text=False,
        ),
    )
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as source:
        source.extractall(_SNAPSHOT_ROOT, filter="data")
    (_SNAPSHOT_ROOT / ".git").write_text(f"gitdir: {git_dir}\n", encoding="utf-8")
    (_GIT_OVERLAY / "HEAD").write_text(f"{_SNAPSHOT_HEAD}\n", encoding="utf-8")
    (_GIT_OVERLAY / "commondir").write_text(f"{common_path}\n", encoding="utf-8")
    return git_dir, common_path


_GIT_DIR, _COMMON_DIR = _prepare_source_snapshot()
sys.path.insert(0, str(_SNAPSHOT_ROOT / "src"))


def _prepend_package_path(module_name: str, package_path: Path) -> None:
    package = importlib.import_module(module_name)
    paths = getattr(package, "__path__", None)
    if paths is None:
        raise RuntimeError(f"{module_name} is not an import package")
    package.__path__ = [
        str(package_path),
        *(str(path) for path in paths if Path(path).resolve() != package_path.resolve()),
    ]


_prepend_package_path("lottolab", _SNAPSHOT_ROOT / "src" / "lottolab")
if "lottolab.research" in sys.modules:
    _prepend_package_path("lottolab.research", _SNAPSHOT_ROOT / "src" / "lottolab" / "research")


def _replay_head(module_name: str) -> tuple[str, str]:
    module = sys.modules.get(module_name)
    if module is None:
        return _SNAPSHOT_HEAD, _SNAPSHOT_TREE
    head = getattr(module, "INPUT_HEAD", _SNAPSHOT_HEAD)
    tree = getattr(module, "INPUT_TREE", _SNAPSHOT_TREE)
    if not isinstance(head, str) or not isinstance(tree, str):
        raise TypeError("certificate replay identity must contain fixed Git HEAD and TREE strings")
    return head, tree


def replay_certificate_call(
    module_name: str,
    operation: Literal["compute_result", "verify_result"],
    *arguments: object,
    repo: Path | None = None,
) -> object:
    """Call a fixed-result verifier in a fresh process with its exact input HEAD/TREE."""
    project_version = tuple(
        int(part) for part in (_ROOT / ".python-version").read_text().strip().split(".")
    )
    if (
        project_version != _EXPECTED_PYTHON[: len(project_version)]
        or sys.version_info[:3] != _EXPECTED_PYTHON
    ):
        raise RuntimeError(
            f"expected project Python {_EXPECTED_PYTHON}, got {sys.version_info[:3]}"
        )
    if operation not in _ALLOWED_OPERATIONS:
        raise ValueError(f"unsupported certificate operation: {operation}")
    _validate_local_pickle_value(arguments)

    head, expected_tree = _replay_head(module_name)
    environment = os.environ.copy()
    for name in tuple(environment):
        if name.startswith("GIT_"):
            environment.pop(name)
    actual_tree = cast(
        str,
        _git(["git", "rev-parse", f"{head}^{{tree}}"], environment=environment),
    ).strip()
    if actual_tree != expected_tree:
        raise ValueError(f"fixed replay TREE mismatch for {head}")

    (_GIT_OVERLAY / "HEAD").write_text(f"{head}\n", encoding="utf-8")
    child_environment = environment.copy()
    child_environment["GIT_CONFIG_COUNT"] = "1"
    child_environment["GIT_CONFIG_KEY_0"] = "core.fsmonitor"
    child_environment["GIT_CONFIG_VALUE_0"] = "false"
    child_environment["GIT_DIR"] = str(_GIT_OVERLAY)
    child_environment["GIT_WORK_TREE"] = str(_SNAPSHOT_ROOT)
    command = [sys.executable, "-I", "-c", _CHILD, module_name, operation]
    if repo is not None:
        repo_path = repo.resolve()
        temporary_root = Path(tempfile.gettempdir()).resolve()
        if not repo_path.is_relative_to(temporary_root) or not (repo_path / "HEAD").is_file():
            raise ValueError(
                "candidate replay repository must be a task-local temporary bare Git repo"
            )
        command.extend((str(repo_path), str(_COMMON_DIR / "objects")))
    completed = subprocess.run(
        command,
        cwd=_SNAPSHOT_ROOT,
        env=child_environment,
        input=pickle.dumps(arguments, protocol=5),
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        message = completed.stderr.decode(errors="replace")
        raise RuntimeError(f"isolated certificate replay exited {completed.returncode}:\n{message}")

    decoded = pickle.loads(completed.stdout)
    if not isinstance(decoded, tuple):
        raise TypeError("isolated certificate replay returned an invalid response")
    response = cast(tuple[object, ...], decoded)
    if len(response) != 6:
        raise TypeError("isolated certificate replay returned an invalid response")
    magic, executable, child_version, isolated, module_path, outcome = response
    if magic != "b649-certificate-replay-v1":
        raise TypeError("isolated certificate replay returned an invalid response identity")
    if not isinstance(executable, str) or Path(executable).resolve() != Path(
        sys.executable
    ).resolve():
        raise RuntimeError("isolated certificate replay used a different Python executable")
    if child_version != _EXPECTED_PYTHON or isolated != 1:
        raise RuntimeError("isolated certificate replay interpreter identity mismatch")
    if not isinstance(module_path, str) or not Path(module_path).resolve().is_relative_to(
        _SNAPSHOT_ROOT
    ):
        raise RuntimeError("isolated certificate replay loaded source outside its fixed snapshot")
    if not isinstance(outcome, tuple):
        raise TypeError("isolated certificate replay returned an invalid operation outcome")
    operation_outcome = cast(tuple[object, ...], outcome)
    if not operation_outcome:
        raise TypeError("isolated certificate replay returned an invalid operation outcome")
    if operation_outcome[0] == "error":
        if len(operation_outcome) != 4:
            raise TypeError("isolated certificate replay returned an invalid error response")
        _, error_module, error_name, message = operation_outcome
        if (error_module, error_name) == ("builtins", "ValueError"):
            raise ValueError(str(message))
        raise RuntimeError(f"{error_module}.{error_name}: {message}")
    if operation_outcome[0] != "ok" or len(operation_outcome) != 2:
        raise TypeError("isolated certificate replay returned an invalid success response")
    return operation_outcome[1]


def _validate_local_pickle_value(value: object) -> None:
    """Allow only builtin test values into pickle; no external or custom objects."""
    if value is None or type(value) in (bool, int, float, str, bytes):
        return
    if type(value) is tuple:
        for item in cast(tuple[object, ...], value):
            _validate_local_pickle_value(item)
        return
    if type(value) is list:
        for item in cast(list[object], value):
            _validate_local_pickle_value(item)
        return
    if type(value) is set:
        for item in cast(set[object], value):
            _validate_local_pickle_value(item)
        return
    if type(value) is frozenset:
        for item in cast(frozenset[object], value):
            _validate_local_pickle_value(item)
        return
    if type(value) is dict:
        mapping = cast(dict[object, object], value)
        for key, item in mapping.items():
            _validate_local_pickle_value(key)
            _validate_local_pickle_value(item)
        return
    raise TypeError(f"isolated certificate replay rejects pickle input type {type(value).__name__}")


def replay_fixed_result(module_name: str) -> dict[str, object]:
    """Replay the certificate and preserve its exact Python result types."""
    result = replay_certificate_call(module_name, "compute_result")
    if not isinstance(result, dict):
        raise TypeError("certificate replay did not return a mapping with string keys")
    result_map = cast(dict[object, object], result)
    if not all(isinstance(key, str) for key in result_map):
        raise TypeError("certificate replay did not return a mapping with string keys")
    return cast(dict[str, object], result)
