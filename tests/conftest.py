from __future__ import annotations

import os
import shutil
import sys
import uuid
from collections.abc import Generator, Iterator
from contextlib import contextmanager
from pathlib import Path
from stat import S_ISDIR, S_ISLNK
from types import ModuleType
from typing import cast

import pytest

_RESEARCH_MODULE_PREFIX = "lottolab.research."
_CERTIFICATE_TEST_MODULES = frozenset(
    {
        "test_b649_min_s2_bonf5_tied_owners_cert_r1.py",
        "test_b649_min_s2_bonferroni5_target_cert_r1.py",
        "test_b649_min_s2_owner_a_exact_bound_r1.py",
        "test_b649_min_s2_owner_b_exact_bound_r1.py",
        "test_b649_min_s2_t249_bonf5_single_row_composition_r1.py",
        "test_b649_min_s2_t249_dual_profile_composition_r1.py",
        "test_b649_min_s2_two_bonf5_owners_exact_composition_r1.py",
        "test_b649_min_s2_two_tied_owner_exact_cert_r1.py",
        "test_b649_three_max_profiles_shared_certificate_r2.py",
    }
)


def _imported_research_dependencies(targets: tuple[ModuleType, ...]) -> set[str]:
    required: set[str] = set()
    pending = list(targets)
    while pending:
        module = pending.pop()
        name = module.__name__
        if not name.startswith(_RESEARCH_MODULE_PREFIX) or name in required:
            continue
        required.add(name)
        for value in vars(module).values():
            dependency = value if isinstance(value, ModuleType) else None
            if dependency is None:
                dependency_name = getattr(value, "__module__", None)
                dependency = (
                    sys.modules.get(dependency_name) if isinstance(dependency_name, str) else None
                )
            if isinstance(dependency, ModuleType) and dependency.__name__.startswith(
                _RESEARCH_MODULE_PREFIX
            ):
                pending.append(dependency)
    return required


def _is_research_or_solver_module(name: str) -> bool:
    return (
        name.startswith(_RESEARCH_MODULE_PREFIX) or name == "ortools" or name.startswith("ortools.")
    )


@contextmanager
def _isolated_research_import_state(targets: tuple[ModuleType, ...]) -> Generator[None]:
    required = _imported_research_dependencies(targets)
    before = {
        name: module
        for name, module in tuple(sys.modules.items())
        if _is_research_or_solver_module(name)
    }
    removed = {
        name: module
        for name, module in before.items()
        if (name.startswith(_RESEARCH_MODULE_PREFIX) and name not in required)
        or name == "ortools"
        or name.startswith("ortools.")
    }
    missing = object()
    parent_attributes: list[tuple[ModuleType, str, object]] = []
    helper_attributes: list[tuple[ModuleType, object]] = []
    for name, module in removed.items():
        parent_name, _, child_name = name.rpartition(".")
        parent = before.get(parent_name) or sys.modules.get(parent_name)
        if isinstance(parent, ModuleType):
            parent_attributes.append((parent, child_name, vars(parent).get(child_name, missing)))
            if vars(parent).get(child_name) is module:
                vars(parent).pop(child_name)
        sys.modules.pop(name, None)

    for target in targets:
        if isinstance(vars(target).get("HELPERS"), tuple):
            helper_attributes.append((target, vars(target)["HELPERS"]))
            vars(target)["HELPERS"] = tuple(
                Path(module_file).resolve()
                for name, module in sorted(before.items())
                if name in required
                and name != target.__name__
                and isinstance(module_file := getattr(module, "__file__", None), str)
            )

    try:
        yield
    finally:
        for name, module in tuple(sys.modules.items()):
            if _is_research_or_solver_module(name) and name not in before:
                parent_name, _, child_name = name.rpartition(".")
                parent = sys.modules.get(parent_name) or before.get(parent_name)
                if isinstance(parent, ModuleType) and vars(parent).get(child_name) is module:
                    vars(parent).pop(child_name)
                sys.modules.pop(name, None)
        sys.modules.update(before)
        for module, helpers in helper_attributes:
            vars(module)["HELPERS"] = helpers
        for parent, child_name, value in parent_attributes:
            if value is missing:
                vars(parent).pop(child_name, None)
            else:
                vars(parent)[child_name] = value


@pytest.fixture
def outside_git_tmp_path(
    tmp_path_factory: pytest.TempPathFactory,
) -> Iterator[Path]:
    configured_root = os.environ.get("MSA_TEST_EXTERNAL_TMP_ROOT")
    root = Path(configured_root) if configured_root else tmp_path_factory.getbasetemp()
    root = root.resolve(strict=True)
    if not root.is_dir():
        pytest.fail(f"external test scratch is not a directory: {root}")
    if "b649" in str(root).casefold() or any(
        part.casefold() == "lotterynew" for part in root.parts
    ):
        pytest.fail(f"external test scratch contains a protected path token: {root}")
    for ancestor in (root, *root.parents):
        try:
            (ancestor / ".git").lstat()
        except FileNotFoundError:
            continue
        pytest.fail(f"external test scratch is inside a Git worktree: {root}")

    digest = uuid.uuid4().hex.replace("b649", "safe")
    scratch = root / f"case-{digest}"
    if "b649" in str(scratch).casefold() or any(
        part.casefold() == "lotterynew" for part in scratch.parts
    ):
        pytest.fail(f"generated test scratch contains a protected path token: {scratch}")
    scratch.mkdir()
    try:
        yield scratch
    finally:
        if scratch.parent != root or scratch.name != f"case-{digest}":
            pytest.fail(f"refusing to remove unexpected test scratch: {scratch}")
        try:
            scratch_mode = os.lstat(scratch).st_mode
        except FileNotFoundError:
            return
        if not S_ISDIR(scratch_mode) or S_ISLNK(scratch_mode):
            pytest.fail(f"refusing to remove non-directory test scratch: {scratch}")
        shutil.rmtree(scratch)


@pytest.fixture(autouse=True)
def isolate_lottolab_database_environment(
    monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest, tmp_path: Path
) -> None:
    if request.node.get_closest_marker("real_draw_authority_db") is not None:  # pyright: ignore[reportUnknownMemberType]
        monkeypatch.delenv("LOTTOLAB_DATA_DIR", raising=False)
    else:
        monkeypatch.setenv("LOTTOLAB_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("LOTTOLAB_DATABASE_CONFIG", "")


@pytest.fixture(scope="module", autouse=True)
def isolate_b649_certificate_collection_imports(
    request: pytest.FixtureRequest,
) -> Iterator[None]:
    test_module = cast(ModuleType, request.module)  # pyright: ignore[reportUnknownMemberType]
    module_path = getattr(test_module, "__file__", None)
    if not isinstance(module_path, str) or Path(module_path).name not in _CERTIFICATE_TEST_MODULES:
        yield
        return
    targets = tuple(
        value
        for value in vars(test_module).values()
        if isinstance(value, ModuleType) and value.__name__.startswith(_RESEARCH_MODULE_PREFIX)
    )
    if not targets:
        pytest.fail(f"certificate test module has no loaded research target: {module_path}")
    with _isolated_research_import_state(targets):
        yield
