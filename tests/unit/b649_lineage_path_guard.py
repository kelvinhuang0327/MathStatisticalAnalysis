"""Path guards shared only by the two lineage successor test modules."""

from __future__ import annotations

import builtins
import io
import os
from pathlib import Path
from typing import Any

from tools import b649_production_cutover as cutover

FORBIDDEN_ROOTS = (
    cutover.scheduler.SCHEDULER_ROOT,
    cutover.CONTROL_ROOT.parent / f"B649_PRODUCTION_{cutover.V5_SOURCE_HEAD}",
    cutover.DEFAULT_PLIST_PATH.parent,
    cutover.CONTROL_ROOT.parents[2] / "MathStatisticalAnalysis" / "data/databases",
)


def forbidden_path_probes() -> tuple[Path, ...]:
    """Return one non-existent child path under each protected root."""
    return tuple(root / "lineage-path-guard-probe" for root in FORBIDDEN_ROOTS)


def _candidate_path(value: object) -> str | None:
    if not isinstance(value, (str, bytes, os.PathLike)):
        return None
    try:
        raw = os.fsdecode(os.fspath(value))
    except (TypeError, ValueError):
        return None
    return os.path.abspath(os.path.normpath(raw))


def _guard_path(value: object) -> None:
    selected = _candidate_path(value)
    if selected is None:
        return
    for root in FORBIDDEN_ROOTS:
        root_value = os.path.abspath(os.path.normpath(str(root)))
        if selected == root_value or selected.startswith(root_value + os.sep):
            raise RuntimeError(f"test attempted forbidden production-path access: {selected}")


def install_path_guard(monkeypatch: Any) -> None:
    """Guard common Python filesystem APIs in a lineage test module only."""
    original_resolve = Path.resolve

    def guarded_resolve(self: Path, strict: bool = False) -> Path:
        _guard_path(self)
        return original_resolve(self, strict=strict)

    monkeypatch.setattr(Path, "resolve", guarded_resolve)

    def wrap(module: object, name: str, path_indexes: tuple[int, ...]) -> None:
        original = getattr(module, name)

        def guarded(*args: Any, **kwargs: Any) -> Any:
            for index in path_indexes:
                if index < len(args):
                    _guard_path(args[index])
            for key in ("path", "src", "dst", "source", "destination"):
                if key in kwargs:
                    _guard_path(kwargs[key])
            return original(*args, **kwargs)

        monkeypatch.setattr(module, name, guarded)

    for module, name, indexes in (
        (builtins, "open", (0,)),
        (io, "open", (0,)),
        (os, "open", (0,)),
        (os, "stat", (0,)),
        (os, "lstat", (0,)),
        (os, "access", (0,)),
        (os, "listdir", (0,)),
        (os, "scandir", (0,)),
        (os, "mkdir", (0,)),
        (os, "makedirs", (0,)),
        (os, "remove", (0,)),
        (os, "unlink", (0,)),
        (os, "rmdir", (0,)),
        (os, "rename", (0, 1)),
        (os, "replace", (0, 1)),
        (os, "chmod", (0,)),
        (os, "chown", (0,)),
        (os, "link", (0, 1)),
        (os, "symlink", (0, 1)),
        (os, "utime", (0,)),
        (os, "truncate", (0,)),
    ):
        wrap(module, name, indexes)
