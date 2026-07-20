"""Architecture boundary tests scoped to the Replay causal-history modules.

A task-owned counterpart to the shared ``tests/architecture/test_dependency_rules.py``
(protected, not modified by this task; it already scans all of ``src/lottolab``
for cross-layer import violations project-wide, so these new files are also
covered by it). Re-implements a tiny, self-contained AST import walker rather
than importing that protected module, keeping this file fully independent.
"""

from __future__ import annotations

import ast
import dataclasses
from pathlib import Path
from typing import runtime_checkable

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src" / "lottolab"

REPLAY_HISTORY_MODULE_PATHS: dict[str, Path] = {
    "lottolab.domain.replay_history": SRC / "domain" / "replay_history.py",
    "lottolab.application.use_cases.build_causal_history": (
        SRC / "application" / "use_cases" / "build_causal_history.py"
    ),
    "lottolab.infrastructure.persistence.replay_history_reader": (
        SRC / "infrastructure" / "persistence" / "replay_history_reader.py"
    ),
}


def _imported_modules(path: Path) -> set[str]:
    relative_parent = path.parent.relative_to(REPO_ROOT / "src")
    package = ".".join(relative_parent.parts)
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0:
                if node.module:
                    modules.add(node.module)
                continue
            package_parts = package.split(".") if package else []
            parent_count = node.level - 1
            if parent_count > len(package_parts):
                if node.module:
                    modules.add(node.module)
                continue
            resolved = package_parts[: len(package_parts) - parent_count]
            if node.module:
                resolved.extend(node.module.split("."))
                modules.add(".".join(resolved))
            elif resolved:
                for alias in node.names:
                    modules.add(f"{'.'.join(resolved)}.{alias.name}")
            else:
                modules.update(alias.name for alias in node.names)
    return modules


def test_all_three_replay_history_modules_exist() -> None:
    for name, path in REPLAY_HISTORY_MODULE_PATHS.items():
        assert path.is_file(), f"{name} missing at {path}"


def test_domain_replay_history_imports_nothing_from_forbidden_layers() -> None:
    imports = _imported_modules(REPLAY_HISTORY_MODULE_PATHS["lottolab.domain.replay_history"])
    forbidden = ("lottolab.application", "lottolab.infrastructure", "lottolab.interfaces")
    assert not any(module.startswith(forbidden) for module in imports)
    # Only other domain-layer modules (and stdlib) may be imported.
    assert not any(
        module.startswith(("lottolab.strategies", "lottolab.evidence", "lottolab.normalization"))
        for module in imports
    )
    for module in imports:
        if module.startswith("lottolab"):
            assert module.startswith("lottolab.domain"), module


def test_use_case_imports_nothing_from_infrastructure_or_interfaces() -> None:
    path = REPLAY_HISTORY_MODULE_PATHS["lottolab.application.use_cases.build_causal_history"]
    imports = _imported_modules(path)
    assert not any(
        module.startswith(("lottolab.infrastructure", "lottolab.interfaces")) for module in imports
    )


def test_sqlite_draw_history_reader_satisfies_the_draw_history_reader_protocol() -> None:
    from lottolab.application.ports import DrawHistoryReader
    from lottolab.infrastructure.persistence.draw_schema import resolve_local_data_paths
    from lottolab.infrastructure.persistence.replay_history_reader import SQLiteDrawHistoryReader

    # DrawHistoryReader must be declared @runtime_checkable to isinstance-check it below.
    assert runtime_checkable

    paths = resolve_local_data_paths(
        environ={"LOTTOLAB_DATA_DIR": "/nonexistent-replay-history-check"}
    )
    reader = SQLiteDrawHistoryReader(paths)
    assert isinstance(reader, DrawHistoryReader)


def test_causal_draw_row_in_strategies_adapters_base_is_unchanged() -> None:
    """Regression guard: strategies/adapters/base.py's CausalDrawRow must be untouched.

    It is a different, unrelated type from ReplayCausalDrawRow: no special
    number, and fields ``draw: str, date: str, numbers: tuple[int, ...]``.
    """

    from lottolab.strategies.adapters.base import CausalDrawRow

    fields = dataclasses.fields(CausalDrawRow)
    field_names = tuple(field.name for field in fields)
    assert field_names == ("draw", "date", "numbers")

    field_types = {field.name: field.type for field in fields}
    assert field_types["draw"] == "str"
    assert field_types["date"] == "str"
    assert field_types["numbers"] == "tuple[int, ...]"

    assert not hasattr(CausalDrawRow, "special_number")
    assert not hasattr(CausalDrawRow, "special")


def test_replay_causal_draw_row_is_a_distinct_type_from_causal_draw_row() -> None:
    from lottolab.domain.replay_history import ReplayCausalDrawRow
    from lottolab.strategies.adapters.base import CausalDrawRow

    assert ReplayCausalDrawRow is not CausalDrawRow
    replay_field_names = {field.name for field in dataclasses.fields(ReplayCausalDrawRow)}
    assert replay_field_names == {"draw_number", "draw_date", "main_numbers", "special_number"}
