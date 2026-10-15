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
_W784_MODULE = "lottolab.research.b649_w784_39_cursor_shared_bound_r1"
_R2_MODULE = "lottolab.research.b649_next_two_resolved_frontier_resume_r2"
_W784_OPERATIONS = {"fixed_input", "upstream_ids_digest"}
_R2_OPERATIONS = {"r2_replay_input"}
_ALLOWED_OPERATIONS = {
    "compute_result",
    "verify_result",
    "source_pins",
    "r2_fixed_input",
    *_W784_OPERATIONS,
    *_R2_OPERATIONS,
}
_ALLOWED_GIT_DAMAGE_CASES = {
    (
        "lottolab.research.b649_three_max_profiles_shared_certificate_r2",
        "lottolab.research.b649_three_max_profiles_shared_certificate_r2",
        "src/lottolab/research/b649_k20_min_s2_route_b_current_owner_refinement_r32.py",
    ),
    (
        "lottolab.research.b649_next_two_max_profiles_exact_bound_r1",
        "lottolab.research.b649_three_max_profiles_shared_certificate_r2",
        "src/lottolab/research/b649_three_max_profiles_shared_certificate_r2.py",
    ),
    (
        "lottolab.research.b649_next_two_max_profiles_exact_bound_r1",
        "lottolab.research.b649_three_max_profiles_shared_certificate_r2",
        "src/lottolab/research/b649_k20_min_s2_route_b_current_owner_refinement_r32.py",
    ),
}
_SNAPSHOT_TEMPORARIES: list[tempfile.TemporaryDirectory[str]] = []
_SNAPSHOT_CACHE: dict[tuple[str, str], tuple[Path, Path, Path]] = {}

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
_W784_MODULE = "lottolab.research.b649_w784_39_cursor_shared_bound_r1"
_R2_MODULE = "lottolab.research.b649_next_two_resolved_frontier_resume_r2"
if (
    project_version != expected_version[: len(project_version)]
    or sys.version_info[:3] != expected_version
):
    raise SystemExit(
        f"expected project Python {expected_version}, got {sys.version_info[:3]}"
    )
(
    module_name,
    operation,
    expected_source_head,
    expected_source_tree,
    expected_operation_head,
    expected_operation_tree,
) = sys.argv[1:7]
if len(sys.argv) not in {7, 9}:
    raise SystemExit("invalid isolated certificate replay arguments")
git_root = Path(
    subprocess.check_output(["git", "rev-parse", "--show-toplevel"], cwd=root, text=True).strip()
).resolve()
if git_root != root:
    raise SystemExit("certificate replay is not bound to the fixed Git worktree")
source_head = expected_source_head
source_tree = subprocess.check_output(
    ["git", "rev-parse", f"{source_head}^{{tree}}"], cwd=root, text=True
).strip()
if source_tree != expected_source_tree:
    raise SystemExit("certificate replay Git source identity mismatch")
operation_head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
operation_tree = subprocess.check_output(
    ["git", "rev-parse", "HEAD^{tree}"], cwd=root, text=True
).strip()
if (operation_head, operation_tree) != (expected_operation_head, expected_operation_tree):
    raise SystemExit("certificate replay Git operation identity mismatch")
sys.path.insert(0, str(root))
sys.path.insert(0, str(root / "src"))
if operation not in {
    "compute_result",
    "verify_result",
    "source_pins",
    "r2_fixed_input",
    "fixed_input",
    "upstream_ids_digest",
    "r2_replay_input",
}:
    raise SystemExit(f"unsupported certificate operation: {operation}")
certificate = importlib.import_module(module_name)
certificate_path = Path(certificate.__file__).resolve()
if not certificate_path.is_relative_to(root):
    raise SystemExit("certificate did not load from the pinned source snapshot")
arguments, git_damage, corrupt_input_tree, profile_floor_override, blob_damage = pickle.loads(
    sys.stdin.buffer.read()
)
if not isinstance(arguments, tuple):
    raise SystemExit("invalid isolated certificate replay arguments")
if type(corrupt_input_tree) is not bool:
    raise SystemExit("invalid controlled input-tree damage fixture")
if operation in {"fixed_input", "upstream_ids_digest"} and module_name != _W784_MODULE:
    raise SystemExit("unapproved W784-specific certificate operation")
if operation == "r2_replay_input" and module_name != _R2_MODULE:
    raise SystemExit("unapproved R2-specific certificate operation")
if sum(
    (
        git_damage is not None,
        corrupt_input_tree,
        profile_floor_override is not None,
        blob_damage is not None,
    )
) > 1:
    raise SystemExit("controlled certificate damage fixtures cannot be combined")
if profile_floor_override is not None and (
    module_name not in {_W784_MODULE, _R2_MODULE}
    or operation != "compute_result"
    or type(profile_floor_override) is not int
    or profile_floor_override != 113
):
    raise SystemExit("unapproved controlled profile-floor fixture")
allowed_git_damage_cases = {
    (
        "lottolab.research.b649_three_max_profiles_shared_certificate_r2",
        "lottolab.research.b649_three_max_profiles_shared_certificate_r2",
        "src/lottolab/research/b649_k20_min_s2_route_b_current_owner_refinement_r32.py",
    ),
    (
        "lottolab.research.b649_next_two_max_profiles_exact_bound_r1",
        "lottolab.research.b649_three_max_profiles_shared_certificate_r2",
        "src/lottolab/research/b649_three_max_profiles_shared_certificate_r2.py",
    ),
    (
        "lottolab.research.b649_next_two_max_profiles_exact_bound_r1",
        "lottolab.research.b649_three_max_profiles_shared_certificate_r2",
        "src/lottolab/research/b649_k20_min_s2_route_b_current_owner_refinement_r32.py",
    ),
}
if git_damage is not None:
    if isinstance(git_damage, tuple) and len(git_damage) == 2:
        target_module_name, damaged_path = git_damage
        if (module_name, target_module_name, damaged_path) not in allowed_git_damage_cases:
            raise SystemExit("unapproved controlled Git damage fixture")
    else:
        raise SystemExit("invalid controlled Git damage fixture")
    if not isinstance(target_module_name, str) or not isinstance(damaged_path, str):
        raise SystemExit("invalid controlled Git damage fixture")
    target_module = importlib.import_module(target_module_name)
    original_git = target_module.git

    def damaged_git(*args, **kwargs):
        value = original_git(*args, **kwargs)
        if len(args) > 1 and args[0] == "show" and args[1].endswith(damaged_path):
            if not isinstance(value, bytes):
                raise TypeError("controlled Git damage fixture expected bytes")
            return value + b"\\n"
        return value

    target_module.git = damaged_git
if blob_damage is not None:
    w784_blob_cases = {"result_sha", "source_sha"}
    r2_blob_cases = {
        "r2_input_result",
        "r2_direct_source",
        "r2_base_result",
        "r2_r30_result",
    }
    if operation != "compute_result" or (
        module_name == _W784_MODULE and blob_damage not in w784_blob_cases
    ) or (module_name == _R2_MODULE and blob_damage not in r2_blob_cases) or (
        module_name not in {_W784_MODULE, _R2_MODULE}
    ):
        raise SystemExit("unapproved controlled blob damage fixture")
    if module_name == _W784_MODULE:
        damaged_path = (
            certificate.INPUT_RESULT
            if blob_damage == "result_sha"
            else certificate.upstream.SOURCE
        )
    else:
        damaged_path = {
            "r2_input_result": certificate.INPUT_RESULT,
            "r2_direct_source": certificate.direct.SOURCE,
            "r2_base_result": certificate.BASE_RESULT,
            "r2_r30_result": certificate.R30_PATH,
        }[blob_damage]
    original_blob = certificate.blob

    def damaged_blob(*args, **kwargs):
        value = original_blob(*args, **kwargs)
        path = args[1] if len(args) > 1 else kwargs.get("path")
        if path == damaged_path:
            if not isinstance(value, bytes):
                raise TypeError("controlled blob damage fixture expected bytes")
            return value + b"\\n"
        return value

    certificate.blob = damaged_blob
if corrupt_input_tree:
    if module_name not in {_W784_MODULE, _R2_MODULE} or operation != "compute_result":
        raise SystemExit("unapproved controlled input-tree damage fixture")
    original_git = certificate.git
    pinned_head = (
        certificate.INPUT_HEAD if module_name == _W784_MODULE else certificate.BASE_HEAD
    )
    damaged_tree_ref = f"{pinned_head}^{{tree}}"

    def damaged_input_tree_git(*args, **kwargs):
        value = original_git(*args, **kwargs)
        if args == ("rev-parse", damaged_tree_ref):
            return "0" * 40
        return value

    certificate.git = damaged_input_tree_git
if profile_floor_override is not None:
    def damaged_profile_s4_floor(_: tuple[int, ...]) -> int:
        return profile_floor_override

    certificate.route.r28.profile_s4_floor = damaged_profile_s4_floor
if len(sys.argv) == 9:
    repo = Path(sys.argv[7]).resolve()
    os.environ.pop("GIT_WORK_TREE", None)
    os.environ["GIT_DIR"] = str(repo)
    os.environ["GIT_ALTERNATE_OBJECT_DIRECTORIES"] = sys.argv[8]
operation_ref = (
    arguments[0]
    if len(sys.argv) == 9
    and operation in {"compute_result", "verify_result"}
    and arguments
    and isinstance(arguments[0], str)
    else "HEAD"
)
operation_head = subprocess.check_output(
    ["git", "rev-parse", operation_ref], cwd=root, text=True
).strip()
operation_tree = subprocess.check_output(
    ["git", "rev-parse", f"{operation_ref}^{{tree}}"], cwd=root, text=True
).strip()
try:
    if operation == "upstream_ids_digest":
        if (
            module_name != _W784_MODULE
            or len(arguments) != 1
            or type(arguments[0]) is not list
            or any(type(value) is not str for value in arguments[0])
        ):
            raise SystemExit("invalid W784 upstream digest arguments")
        operation_function = certificate.upstream.ids_digest
    elif operation == "r2_replay_input":
        if module_name != _R2_MODULE or arguments:
            raise SystemExit("invalid R2 replay input arguments")
        operation_function = certificate.replay_input
    else:
        operation_function = getattr(certificate, operation)
    value = operation_function(*arguments)
except Exception as error:
    outcome = ("error", type(error).__module__, type(error).__name__, str(error))
else:
    outcome = ("ok", value)
response = (
    "b649-certificate-replay-v2",
    sys.executable,
    tuple(sys.version_info[:3]),
    sys.flags.isolated,
    str(certificate_path),
    (source_head, source_tree),
    (operation_head, operation_tree),
    outcome,
)
sys.stdout.buffer.write(pickle.dumps(response, protocol=5))
"""


def _git(args: list[str], *, environment: dict[str, str], text: bool = True) -> str | bytes:
    return subprocess.check_output(args, cwd=_ROOT, env=environment, text=text)


def _prepare_source_snapshot(
    head: str, expected_tree: str
) -> tuple[Path, Path, Path]:
    key = (head, expected_tree)
    cached = _SNAPSHOT_CACHE.get(key)
    if cached is not None:
        return cached

    environment = os.environ.copy()
    for name in tuple(environment):
        if name.startswith("GIT_"):
            environment.pop(name)

    actual_tree = cast(
        str,
        _git(
            ["git", "rev-parse", f"{head}^{{tree}}"],
            environment=environment,
        ),
    ).strip()
    if actual_tree != expected_tree:
        raise ValueError(f"fixed source TREE does not match B649 replay HEAD {head}")

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
            ["git", "archive", "--format=tar", head],
            environment=environment,
            text=False,
        ),
    )
    snapshot_directory = tempfile.TemporaryDirectory(
        prefix=f"b649-certificate-source-{head[:12]}-"
    )
    _SNAPSHOT_TEMPORARIES.append(snapshot_directory)
    snapshot_root = Path(snapshot_directory.name).resolve()
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as source:
        source.extractall(snapshot_root, filter="data")
    (snapshot_root / ".git").write_text(f"gitdir: {git_dir}\n", encoding="utf-8")
    result = (snapshot_root, common_path, Path(git_dir))
    _SNAPSHOT_CACHE[key] = result
    return result


_SNAPSHOT_ROOT, _COMMON_DIR, _GIT_DIR = _prepare_source_snapshot(_SNAPSHOT_HEAD, _SNAPSHOT_TREE)
sys.path.insert(0, str(_SNAPSHOT_ROOT / "src"))


def _prepend_package_paths(module_name: str, *package_paths: Path) -> None:
    package = importlib.import_module(module_name)
    paths = getattr(package, "__path__", None)
    if paths is None:
        raise RuntimeError(f"{module_name} is not an import package")
    selected = [path.resolve() for path in package_paths]
    existing = [Path(path).resolve() for path in paths]
    package.__path__ = [str(path) for path in dict.fromkeys((*selected, *existing))]


_prepend_package_paths(
    "lottolab",
    _SNAPSHOT_ROOT / "src" / "lottolab",
    _ROOT / "src" / "lottolab",
)
_prepend_package_paths(
    "lottolab.research",
    _SNAPSHOT_ROOT / "src" / "lottolab" / "research",
    _ROOT / "src" / "lottolab" / "research",
)


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
    operation: Literal[
        "compute_result",
        "verify_result",
        "source_pins",
        "r2_fixed_input",
        "fixed_input",
        "upstream_ids_digest",
        "r2_replay_input",
    ],
    *arguments: object,
    repo: Path | None = None,
    source_head: str | None = None,
    source_tree: str | None = None,
    operation_head: str | None = None,
    operation_tree: str | None = None,
    git_damage: tuple[str, str] | None = None,
    corrupt_input_tree: bool = False,
    profile_floor_override: int | None = None,
    blob_damage: Literal[
        "result_sha",
        "source_sha",
        "r2_input_result",
        "r2_direct_source",
        "r2_base_result",
        "r2_r30_result",
    ]
    | None = None,
) -> object:
    """Call a fixed certificate operation in a fresh pinned-source process."""
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
    if type(corrupt_input_tree) is not bool:
        raise ValueError("invalid controlled input-tree damage fixture")
    _validate_local_pickle_value(
        (arguments, git_damage, corrupt_input_tree, profile_floor_override, blob_damage)
    )

    if git_damage is not None and (module_name, *git_damage) not in _ALLOWED_GIT_DAMAGE_CASES:
        raise ValueError("unapproved controlled Git damage fixture")
    if operation in _W784_OPERATIONS and module_name != _W784_MODULE:
        raise ValueError("unapproved W784-specific certificate operation")
    if operation in _R2_OPERATIONS and module_name != _R2_MODULE:
        raise ValueError("unapproved R2-specific certificate operation")
    if corrupt_input_tree and module_name not in {_W784_MODULE, _R2_MODULE}:
        raise ValueError("unapproved controlled input-tree damage fixture")
    if (corrupt_input_tree or profile_floor_override is not None) and operation != "compute_result":
        raise ValueError("controlled computation fixtures require compute_result")
    if profile_floor_override is not None and (
        module_name not in {_W784_MODULE, _R2_MODULE}
        or type(profile_floor_override) is not int
        or profile_floor_override != 113
    ):
        raise ValueError("unapproved controlled profile-floor fixture")
    if blob_damage is not None and (
        operation != "compute_result"
        or (
            module_name == _W784_MODULE
            and blob_damage not in {"result_sha", "source_sha"}
        )
        or (
            module_name == _R2_MODULE
            and blob_damage
            not in {
                "r2_input_result",
                "r2_direct_source",
                "r2_base_result",
                "r2_r30_result",
            }
        )
        or module_name not in {_W784_MODULE, _R2_MODULE}
    ):
        raise ValueError("unapproved controlled blob damage fixture")
    if sum(
        (
            git_damage is not None,
            corrupt_input_tree,
            profile_floor_override is not None,
            blob_damage is not None,
        )
    ) > 1:
        raise ValueError("controlled certificate damage fixtures cannot be combined")
    if (
        (
            git_damage is not None
            or corrupt_input_tree
            or profile_floor_override is not None
            or blob_damage is not None
        )
        and repo is not None
    ):
        raise ValueError("controlled certificate damage cannot be combined with a candidate repo")
    if (source_head is None) != (source_tree is None):
        raise ValueError("replay source HEAD and TREE must be supplied together")
    if source_head is None or source_tree is None:
        source_head, source_tree = _SNAPSHOT_HEAD, _SNAPSHOT_TREE
    if (operation_head is None) != (operation_tree is None):
        raise ValueError("replay operation HEAD and TREE must be supplied together")
    if operation_head is None or operation_tree is None:
        operation_head, operation_tree = _replay_head(module_name)
    snapshot_root, common_dir, _ = _prepare_source_snapshot(source_head, source_tree)
    environment = os.environ.copy()
    for name in tuple(environment):
        if name.startswith("GIT_"):
            environment.pop(name)
    actual_source_tree = cast(
        str,
        _git(["git", "rev-parse", f"{source_head}^{{tree}}"], environment=environment),
    ).strip()
    if actual_source_tree != source_tree:
        raise ValueError(f"fixed replay TREE mismatch for {source_head}")
    actual_operation_tree = cast(
        str,
        _git(["git", "rev-parse", f"{operation_head}^{{tree}}"], environment=environment),
    ).strip()
    if actual_operation_tree != operation_tree:
        raise ValueError(f"fixed replay operation TREE mismatch for {operation_head}")

    overlay_directory = tempfile.TemporaryDirectory(prefix="b649-certificate-git-")
    git_overlay = Path(overlay_directory.name).resolve()
    (git_overlay / "HEAD").write_text(f"{operation_head}\n", encoding="utf-8")
    (git_overlay / "commondir").write_text(f"{common_dir}\n", encoding="utf-8")

    child_environment = environment.copy()
    child_environment["GIT_CONFIG_COUNT"] = "1"
    child_environment["GIT_CONFIG_KEY_0"] = "core.fsmonitor"
    child_environment["GIT_CONFIG_VALUE_0"] = "false"
    child_environment["GIT_DIR"] = str(git_overlay)
    child_environment["GIT_WORK_TREE"] = str(snapshot_root)
    command = [
        sys.executable,
        "-I",
        "-c",
        _CHILD,
        module_name,
        operation,
        source_head,
        source_tree,
        operation_head,
        operation_tree,
    ]
    operation_identity = (operation_head, operation_tree)
    if repo is not None:
        if (
            operation not in {"compute_result", "verify_result"}
            or not arguments
            or not isinstance(arguments[0], str)
        ):
            raise ValueError("candidate replay requires an explicit certificate candidate ref")
        repo_path = repo.resolve()
        temporary_root = Path(tempfile.gettempdir()).resolve()
        if not repo_path.is_relative_to(temporary_root) or not (repo_path / "HEAD").is_file():
            raise ValueError(
                "candidate replay repository must be a task-local temporary bare Git repo"
            )
        candidate_environment = environment.copy()
        candidate_environment["GIT_ALTERNATE_OBJECT_DIRECTORIES"] = str(common_dir / "objects")
        candidate_ref = arguments[0]
        candidate_head = cast(
            str,
            _git(
                ["git", "--git-dir", str(repo_path), "rev-parse", candidate_ref],
                environment=candidate_environment,
            ),
        ).strip()
        candidate_tree = cast(
            str,
            _git(
                ["git", "--git-dir", str(repo_path), "rev-parse", f"{candidate_ref}^{{tree}}"],
                environment=candidate_environment,
            ),
        ).strip()
        operation_identity = (candidate_head, candidate_tree)
        command.extend((str(repo_path), str(common_dir / "objects")))
    completed = subprocess.run(
        command,
        cwd=snapshot_root,
        env=child_environment,
        input=pickle.dumps(
            (
                arguments,
                git_damage,
                corrupt_input_tree,
                profile_floor_override,
                blob_damage,
            ),
            protocol=5,
        ),
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
    if len(response) != 8:
        raise TypeError("isolated certificate replay returned an invalid response")
    (
        magic,
        executable,
        child_version,
        isolated,
        module_path,
        child_source_identity,
        child_operation_identity,
        outcome,
    ) = response
    if magic != "b649-certificate-replay-v2":
        raise TypeError("isolated certificate replay returned an invalid response identity")
    if not isinstance(executable, str) or Path(executable).resolve() != Path(
        sys.executable
    ).resolve():
        raise RuntimeError("isolated certificate replay used a different Python executable")
    if child_version != _EXPECTED_PYTHON or isolated != 1:
        raise RuntimeError("isolated certificate replay interpreter identity mismatch")
    expected_module_path = snapshot_root / "src" / Path(*module_name.split(".")).with_suffix(
        ".py"
    )
    if (
        not isinstance(module_path, str)
        or Path(module_path).resolve() != expected_module_path.resolve()
    ):
        raise RuntimeError("isolated certificate replay loaded source outside its fixed snapshot")
    if child_source_identity != (source_head, source_tree):
        raise RuntimeError("isolated certificate replay used a different fixed source Git identity")
    if child_operation_identity != operation_identity:
        raise RuntimeError("isolated certificate replay used a different operation Git identity")
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


def replay_fixed_result(
    module_name: str,
    *,
    source_head: str | None = None,
    source_tree: str | None = None,
    operation_head: str | None = None,
    operation_tree: str | None = None,
) -> dict[str, object]:
    """Replay the certificate and preserve its exact Python result types."""
    result = replay_certificate_call(
        module_name,
        "compute_result",
        source_head=source_head,
        source_tree=source_tree,
        operation_head=operation_head,
        operation_tree=operation_tree,
    )
    if not isinstance(result, dict):
        raise TypeError("certificate replay did not return a mapping with string keys")
    result_map = cast(dict[object, object], result)
    if not all(isinstance(key, str) for key in result_map):
        raise TypeError("certificate replay did not return a mapping with string keys")
    return cast(dict[str, object], result)


def replay_fixed_inputs(
    module_name: str,
    *,
    source_head: str,
    source_tree: str,
    operation_head: str,
    operation_tree: str,
) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    """Replay R2's pinned input, base, and R30 payloads in its source snapshot."""
    inputs = replay_certificate_call(
        module_name,
        "r2_replay_input",
        source_head=source_head,
        source_tree=source_tree,
        operation_head=operation_head,
        operation_tree=operation_tree,
    )
    if type(inputs) is not tuple:
        raise TypeError("R2 replay did not return its three pinned input mappings")
    input_items = cast(tuple[object, ...], inputs)
    if len(input_items) != 3:
        raise TypeError("R2 replay did not return its three pinned input mappings")
    fixed, base, r30 = input_items
    results = (fixed, base, r30)
    if any(type(result) is not dict for result in results):
        raise TypeError("R2 replay returned a non-dictionary pinned input")
    mappings = cast(tuple[dict[object, object], ...], results)
    if any(not all(isinstance(key, str) for key in result) for result in mappings):
        raise TypeError("R2 replay returned a pinned input with non-string keys")
    return cast(
        tuple[dict[str, object], dict[str, object], dict[str, object]],
        mappings,
    )
