"""Bind the archived Three-ticket module for the frozen Four-ticket driver.

The driver keeps its original REPO and early-import behavior. This successor
layer verifies the archived source, loads it under its original qualified
name, updates only the driver's in-memory TTC path, then delegates predicate
loading to the unchanged driver.
"""

from __future__ import annotations

import hashlib
import importlib.util
import os
import stat
import sys
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType

SUCCESSOR_WORKTREE = Path(
    "/Users/kelvin/.codex/worktrees/b649-k20-orbit-source-binding-r1/MathStatisticalAnalysis"
)
CANONICAL_REPOSITORY = Path("/Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis")
TASK_ROOT = (
    CANONICAL_REPOSITORY
    / ".task-data"
    / "B649_K20_313263888_FOUR_TICKET_CYCLE_FULL_FAMILY_R1"
    / "run1"
)
ORIGINAL_DRIVER_PATH = TASK_ROOT / "driver.py"
ORIGINAL_DRIVER_SHA256 = "6348fec9daa839753bf375aa3804a3ca67ed0717fec93c58463d2f01814fd2d7"
FROZEN_PREDICATE_PATH = TASK_ROOT / "predicate-source.snapshot.py"
FROZEN_PREDICATE_SHA256 = "97d73e8b9f81969051a03f6b5744d0d7ca0539ff1f70303ce92ddbb760e7134e"

DEPENDENCY_IMPORT_NAME = "lottolab.research.b649_k20_three_ticket_single_number_cycle_r1"
ARCHIVED_DEPENDENCY_PATH = (
    CANONICAL_REPOSITORY
    / ".task-data"
    / "B649_K20_V7_THREE_TICKET_CYCLE_FULL_FAMILY_R1"
    / "run1"
    / "engine"
    / "src"
    / "lottolab"
    / "research"
    / "b649_k20_three_ticket_single_number_cycle_r1.py"
)
ARCHIVED_DEPENDENCY_SHA256 = "79799744151daa638dd7a8bd372563fcb310c76825efb493415688983a6d5649"

OFFICIAL_IMPORT_NAME = "lottolab.research.b649_official_any_prize_exact"
OFFICIAL_SOURCE_PATH = (
    CANONICAL_REPOSITORY / "src/lottolab/research/b649_official_any_prize_exact.py"
)
OFFICIAL_SOURCE_SHA256 = "92dcb836254cc6dbcd6c2ad907e619a5eb8cf3917197a8f6de3e5f989825cf66"

FOUR_TICKET_IMPORT_NAME = "lottolab.research.b649_k20_four_ticket_cycle_r1"
_DRIVER_IMPORT_NAME = "_b649_k20_four_ticket_frozen_driver_source_binding_r1"
_EXPECTED_DEPENDENCY_HASHES = {
    "b649_k20_three_ticket_single_number_cycle_r1.py": ARCHIVED_DEPENDENCY_SHA256,
    "b649_official_any_prize_exact.py": OFFICIAL_SOURCE_SHA256,
}


class SourceBindingError(RuntimeError):
    """A pinned source, import path, or execution precondition did not match."""


@dataclass(frozen=True)
class SuccessorSourceBinding:
    """Verified identities returned after the unchanged driver loads its predicate."""

    binding_module_path: Path
    binding_module_sha256: str
    driver_module: ModuleType = field(repr=False, compare=False)
    driver_path: Path
    driver_sha256: str
    predicate_module: ModuleType = field(repr=False, compare=False)
    predicate_path: Path
    predicate_sha256: str
    dependency_module: ModuleType = field(repr=False, compare=False)
    dependency_module_name: str
    dependency_path: Path
    dependency_sha256: str
    official_module: ModuleType = field(repr=False, compare=False)
    official_path: Path
    official_sha256: str
    execution_stage: str

    @property
    def binding_identity(self) -> str:
        return f"{self.binding_module_path}#{self.binding_module_sha256}"


def _resolve_existing_file(path: Path, label: str) -> Path:
    candidate = Path(path)
    if not candidate.is_absolute():
        raise SourceBindingError(f"{label}:PATH_NOT_ABSOLUTE")
    try:
        resolved = candidate.resolve(strict=True)
        metadata = resolved.stat()
    except OSError as error:
        raise SourceBindingError(f"{label}:PATH_UNAVAILABLE {candidate}") from error
    if candidate != resolved or not stat.S_ISREG(metadata.st_mode):
        raise SourceBindingError(f"{label}:PATH_NOT_REGULAR_CANONICAL_FILE {candidate}")
    return resolved


def _require_authorized_path(path: Path, authorized_path: Path, label: str) -> Path:
    actual = _resolve_existing_file(Path(path), label)
    authorized = _resolve_existing_file(Path(authorized_path), f"{label}:AUTHORIZED")
    if actual != authorized:
        raise SourceBindingError(f"{label}:WRONG_MODULE_PATH {actual}")
    return actual


def _stable_bytes(path: Path, label: str) -> bytes:
    resolved = _resolve_existing_file(path, label)
    try:
        before = resolved.stat()
        with resolved.open("rb") as stream:
            data = stream.read()
        after = resolved.stat()
    except OSError as error:
        raise SourceBindingError(f"{label}:READ_FAILED {resolved}") from error
    before_identity = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
    after_identity = (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
    if before_identity != after_identity or len(data) != after.st_size:
        raise SourceBindingError(f"{label}:CHANGED_DURING_READ {resolved}")
    return data


def _verify_sha256(data: bytes, expected_sha256: str, label: str) -> str:
    if len(expected_sha256) != 64 or any(
        char not in "0123456789abcdef" for char in expected_sha256
    ):
        raise SourceBindingError(f"{label}:INVALID_EXPECTED_SHA256")
    actual_sha256 = hashlib.sha256(data).hexdigest()
    if actual_sha256 != expected_sha256:
        raise SourceBindingError(
            f"{label}:SHA256_MISMATCH expected={expected_sha256} actual={actual_sha256}"
        )
    return actual_sha256


def _read_verified_source(
    path: Path, authorized_path: Path, expected_sha256: str, label: str
) -> tuple[Path, bytes, str]:
    resolved = _require_authorized_path(path, authorized_path, label)
    data = _stable_bytes(resolved, label)
    return resolved, data, _verify_sha256(data, expected_sha256, label)


def _module_file(module: ModuleType, authorized_path: Path, label: str) -> Path:
    file_value = getattr(module, "__file__", None)
    spec = getattr(module, "__spec__", None)
    origin = getattr(spec, "origin", None)
    if not isinstance(file_value, str) or not isinstance(origin, str):
        raise SourceBindingError(f"{label}:MODULE_ORIGIN_UNAVAILABLE")
    file_path = _require_authorized_path(Path(file_value), authorized_path, label)
    origin_path = _require_authorized_path(Path(origin), authorized_path, f"{label}:SPEC")
    if file_path != origin_path:
        raise SourceBindingError(f"{label}:MODULE_ORIGIN_MISMATCH")
    return file_path


def _load_verified_module(
    module_name: str,
    path: Path,
    expected_path: Path,
    expected_sha256: str,
    label: str,
) -> tuple[ModuleType, Path, str, bool]:
    resolved, source_bytes, source_sha256 = _read_verified_source(
        path, expected_path, expected_sha256, label
    )
    existing = sys.modules.get(module_name)
    if existing is not None:
        if not isinstance(existing, ModuleType):
            raise SourceBindingError(f"{label}:MODULE_NAME_COLLISION {module_name}")
        existing_path = _module_file(existing, resolved, label)
        existing_sha256 = _verify_sha256(
            _stable_bytes(existing_path, label), expected_sha256, label
        )
        return existing, existing_path, existing_sha256, False

    spec = importlib.util.spec_from_file_location(module_name, str(resolved))
    if spec is None or spec.loader is None or spec.origin is None:
        raise SourceBindingError(f"{label}:MODULE_SPEC_UNAVAILABLE")
    spec_path = _require_authorized_path(Path(spec.origin), resolved, f"{label}:SPEC")
    if spec_path != resolved:
        raise SourceBindingError(f"{label}:SPEC_PATH_MISMATCH")
    module = importlib.util.module_from_spec(spec)
    if _module_file(module, resolved, label) != resolved:
        raise SourceBindingError(f"{label}:MODULE_FILE_MISMATCH_BEFORE_EXEC")
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
        loaded_path = _module_file(module, resolved, label)
        loaded_sha256 = _verify_sha256(_stable_bytes(loaded_path, label), expected_sha256, label)
        if loaded_sha256 != source_sha256 or source_bytes != _stable_bytes(loaded_path, label):
            raise SourceBindingError(f"{label}:SOURCE_CHANGED_DURING_IMPORT")
    except BaseException:
        if sys.modules.get(module_name) is module:
            sys.modules.pop(module_name, None)
        raise
    return module, loaded_path, loaded_sha256, True


def _binding_module_identity() -> tuple[Path, str]:
    expected_path = (
        SUCCESSOR_WORKTREE / "src/lottolab/research/b649_k20_four_ticket_orbit_source_binding_r1.py"
    )
    module_path = _require_authorized_path(
        Path(__file__), expected_path, "SUCCESSOR_BINDING_MODULE"
    )
    spec = globals().get("__spec__")
    origin = getattr(spec, "origin", None)
    if not isinstance(origin, str):
        raise SourceBindingError("SUCCESSOR_BINDING_MODULE:SPEC_ORIGIN_UNAVAILABLE")
    if (
        _require_authorized_path(Path(origin), expected_path, "SUCCESSOR_BINDING_MODULE:SPEC")
        != module_path
    ):
        raise SourceBindingError("SUCCESSOR_BINDING_MODULE:SPEC_PATH_MISMATCH")
    digest = hashlib.sha256(_stable_bytes(module_path, "SUCCESSOR_BINDING_MODULE")).hexdigest()
    return module_path, digest


def _path_value_matches(value: object, expected_path: Path, label: str) -> None:
    if not isinstance(value, (str, Path)):
        raise SourceBindingError(f"{label}:PATH_VALUE_UNAVAILABLE")
    candidate = Path(value)
    if not candidate.is_absolute() or candidate.resolve(strict=False) != expected_path.resolve(
        strict=False
    ):
        raise SourceBindingError(f"{label}:FIXED_DRIVER_PATH_MISMATCH {candidate}")


def _validate_driver_layout(driver: ModuleType) -> None:
    _module_file(driver, ORIGINAL_DRIVER_PATH, "ORIGINAL_DRIVER")
    _verify_sha256(
        _stable_bytes(ORIGINAL_DRIVER_PATH, "ORIGINAL_DRIVER"),
        ORIGINAL_DRIVER_SHA256,
        "ORIGINAL_DRIVER",
    )
    _path_value_matches(driver.REPO, CANONICAL_REPOSITORY, "DRIVER_REPO")
    _path_value_matches(driver.ROOT, TASK_ROOT, "DRIVER_ROOT")
    _path_value_matches(
        driver.SOURCE,
        CANONICAL_REPOSITORY / "src/lottolab/research/b649_k20_four_ticket_cycle_r1.py",
        "DRIVER_SOURCE",
    )
    _path_value_matches(driver.SNAPSHOT, FROZEN_PREDICATE_PATH, "DRIVER_SNAPSHOT")
    _path_value_matches(
        driver.TTC,
        CANONICAL_REPOSITORY
        / "src/lottolab/research/b649_k20_three_ticket_single_number_cycle_r1.py",
        "DRIVER_TTC_ORIGINAL",
    )
    _path_value_matches(driver.OFFICIAL, OFFICIAL_SOURCE_PATH, "DRIVER_OFFICIAL")
    if driver.MODULE_NAME != FOUR_TICKET_IMPORT_NAME:
        raise SourceBindingError("DRIVER_PREDICATE_MODULE_NAME_MISMATCH")
    if driver.SOURCE_SHA256 != FROZEN_PREDICATE_SHA256:
        raise SourceBindingError("DRIVER_PREDICATE_SHA256_CONSTANT_MISMATCH")
    if driver.DEPENDENCY_SHA256 != _EXPECTED_DEPENDENCY_HASHES:
        raise SourceBindingError("DRIVER_DEPENDENCY_SHA256_CONSTANT_MISMATCH")
    if not callable(getattr(driver, "load_predicate_module", None)):
        raise SourceBindingError("DRIVER_PREDICATE_LOADER_UNAVAILABLE")


@dataclass(frozen=True)
class _LoadedModule:
    module: ModuleType = field(repr=False, compare=False)
    path: Path
    sha256: str
    created: bool


def load_original_predicate_for_successor() -> SuccessorSourceBinding:
    """Verify and bind the archived dependency before the unchanged predicate loader runs.

    This imports frozen definitions only. It does not call the driver's solver,
    scoring, move-generation, preflight, or run entrypoints.
    """

    if os.environ.get("PYTHONDONTWRITEBYTECODE") != "1" or not sys.dont_write_bytecode:
        raise SourceBindingError("BYTECODE_OUTPUTS_NOT_DISABLED")

    binding_path, binding_sha256 = _binding_module_identity()
    _read_verified_source(
        ORIGINAL_DRIVER_PATH, ORIGINAL_DRIVER_PATH, ORIGINAL_DRIVER_SHA256, "ORIGINAL_DRIVER"
    )
    _predicate_path, _, predicate_sha256 = _read_verified_source(
        FROZEN_PREDICATE_PATH,
        FROZEN_PREDICATE_PATH,
        FROZEN_PREDICATE_SHA256,
        "FROZEN_PREDICATE",
    )
    official_path, _, _official_sha256 = _read_verified_source(
        OFFICIAL_SOURCE_PATH,
        OFFICIAL_SOURCE_PATH,
        OFFICIAL_SOURCE_SHA256,
        "OFFICIAL_DEPENDENCY",
    )
    dependency_path, _, _dependency_sha256 = _read_verified_source(
        ARCHIVED_DEPENDENCY_PATH,
        ARCHIVED_DEPENDENCY_PATH,
        ARCHIVED_DEPENDENCY_SHA256,
        "ARCHIVED_THREE_TICKET_DEPENDENCY",
    )

    if FOUR_TICKET_IMPORT_NAME in sys.modules:
        raise SourceBindingError("FOUR_TICKET_PREDICATE_PREIMPORTED")

    loaded: list[_LoadedModule] = []
    driver: ModuleType | None = None
    driver_created = False
    original_ttc: object | None = None
    predicate: ModuleType | None = None
    ttc_patched = False
    try:
        driver, driver_path, driver_sha256, driver_created = _load_verified_module(
            _DRIVER_IMPORT_NAME,
            ORIGINAL_DRIVER_PATH,
            ORIGINAL_DRIVER_PATH,
            ORIGINAL_DRIVER_SHA256,
            "ORIGINAL_DRIVER",
        )
        _validate_driver_layout(driver)

        official, loaded_official_path, loaded_official_sha256, official_created = (
            _load_verified_module(
                OFFICIAL_IMPORT_NAME,
                official_path,
                OFFICIAL_SOURCE_PATH,
                OFFICIAL_SOURCE_SHA256,
                "OFFICIAL_DEPENDENCY",
            )
        )
        loaded.append(
            _LoadedModule(official, loaded_official_path, loaded_official_sha256, official_created)
        )

        dependency, loaded_dependency_path, loaded_dependency_sha256, dependency_created = (
            _load_verified_module(
                DEPENDENCY_IMPORT_NAME,
                dependency_path,
                ARCHIVED_DEPENDENCY_PATH,
                ARCHIVED_DEPENDENCY_SHA256,
                "ARCHIVED_THREE_TICKET_DEPENDENCY",
            )
        )
        loaded.append(
            _LoadedModule(
                dependency, loaded_dependency_path, loaded_dependency_sha256, dependency_created
            )
        )

        original_ttc = driver.TTC
        driver.TTC = dependency_path
        ttc_patched = True
        predicate = driver.load_predicate_module()

        predicate_file = _require_authorized_path(
            Path(str(getattr(predicate, "__file__", ""))),
            FROZEN_PREDICATE_PATH,
            "LOADED_FROZEN_PREDICATE",
        )
        if getattr(predicate, "ttc", None) is not dependency:
            raise SourceBindingError("FROZEN_PREDICATE_DEPENDENCY_BINDING_MISMATCH")
        if dependency_path != driver.TTC:
            raise SourceBindingError("DRIVER_TTC_BINDING_DRIFT")

        final_binding_path, final_binding_sha256 = _binding_module_identity()
        if final_binding_path != binding_path or final_binding_sha256 != binding_sha256:
            raise SourceBindingError("SUCCESSOR_BINDING_MODULE_CHANGED_DURING_IMPORT")
        _verify_sha256(
            _stable_bytes(driver_path, "ORIGINAL_DRIVER"), ORIGINAL_DRIVER_SHA256, "ORIGINAL_DRIVER"
        )
        _verify_sha256(
            _stable_bytes(predicate_file, "FROZEN_PREDICATE"),
            FROZEN_PREDICATE_SHA256,
            "FROZEN_PREDICATE",
        )
        _verify_sha256(
            _stable_bytes(loaded_official_path, "OFFICIAL_DEPENDENCY"),
            OFFICIAL_SOURCE_SHA256,
            "OFFICIAL_DEPENDENCY",
        )
        _verify_sha256(
            _stable_bytes(loaded_dependency_path, "ARCHIVED_THREE_TICKET_DEPENDENCY"),
            ARCHIVED_DEPENDENCY_SHA256,
            "ARCHIVED_THREE_TICKET_DEPENDENCY",
        )
        return SuccessorSourceBinding(
            binding_module_path=binding_path,
            binding_module_sha256=binding_sha256,
            driver_module=driver,
            driver_path=driver_path,
            driver_sha256=driver_sha256,
            predicate_module=predicate,
            predicate_path=predicate_file,
            predicate_sha256=predicate_sha256,
            dependency_module=dependency,
            dependency_module_name=DEPENDENCY_IMPORT_NAME,
            dependency_path=loaded_dependency_path,
            dependency_sha256=loaded_dependency_sha256,
            official_module=official,
            official_path=loaded_official_path,
            official_sha256=loaded_official_sha256,
            execution_stage="PREDICATE_IMPORTED_NO_SOLVER",
        )
    except BaseException:
        if predicate is not None and sys.modules.get(FOUR_TICKET_IMPORT_NAME) is predicate:
            sys.modules.pop(FOUR_TICKET_IMPORT_NAME, None)
        if ttc_patched and driver is not None:
            driver.TTC = original_ttc
        for item in reversed(loaded):
            if item.created and sys.modules.get(item.module.__name__) is item.module:
                sys.modules.pop(item.module.__name__, None)
        if driver_created and driver is not None and sys.modules.get(_DRIVER_IMPORT_NAME) is driver:
            sys.modules.pop(_DRIVER_IMPORT_NAME, None)
        raise


__all__ = [
    "ARCHIVED_DEPENDENCY_PATH",
    "ARCHIVED_DEPENDENCY_SHA256",
    "DEPENDENCY_IMPORT_NAME",
    "FROZEN_PREDICATE_PATH",
    "FROZEN_PREDICATE_SHA256",
    "OFFICIAL_SOURCE_PATH",
    "OFFICIAL_SOURCE_SHA256",
    "ORIGINAL_DRIVER_PATH",
    "ORIGINAL_DRIVER_SHA256",
    "SourceBindingError",
    "SuccessorSourceBinding",
    "load_original_predicate_for_successor",
]
