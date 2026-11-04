"""Block test filesystem operations against production B649 state."""

from __future__ import annotations

import builtins
import io
import os
from pathlib import Path
from typing import Any

import pytest

_FORBIDDEN_ROOTS = (
    Path("/Users/kelvin/VibeCoding-WorkSpace/.task-data/B649_OPERATIONAL_PREDICTION_LOOP_R1/scheduler"),
    Path("/Users/kelvin/VibeCoding-WorkSpace/.worktrees/MathStatisticalAnalysis/B649_PRODUCTION_56c9715ca60bb9af3afe3b5faae83b0dc0471d8f"),
    Path("/Users/kelvin/Library/LaunchAgents"),
    Path("/Users/kelvin/VibeCoding-WorkSpace/MathStatisticalAnalysis/data/databases"),
)


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
    for root in _FORBIDDEN_ROOTS:
        root_value = str(root)
        if selected == root_value or selected.startswith(root_value + os.sep):
            raise RuntimeError(f"test attempted forbidden production-path access: {selected}")


@pytest.fixture(autouse=True)
def refuse_production_path_io(monkeypatch: pytest.MonkeyPatch) -> None:
    """Reject production path resolution, reads, writes, and metadata checks."""

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
