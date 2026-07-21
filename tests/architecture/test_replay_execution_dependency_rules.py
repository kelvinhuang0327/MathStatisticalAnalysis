"""Architecture boundary tests scoped to the Replay execution modules.

A task-owned counterpart to the shared ``tests/architecture/test_dependency_rules.py``
(protected, not modified by this task; it already scans all of ``src/lottolab``
for cross-layer import violations project-wide, so these new files are also
covered by it). Re-implements a tiny, self-contained AST import walker rather
than importing that protected module, keeping this file fully independent —
mirroring ``tests/architecture/test_replay_history_dependency_rules.py``.
"""

from __future__ import annotations

import ast
import dataclasses
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src" / "lottolab"

REPLAY_EXECUTION_MODULE_PATHS: dict[str, Path] = {
    "lottolab.domain.replay_predictions": SRC / "domain" / "replay_predictions.py",
    "lottolab.application.use_cases.replay_historical_predictions": (
        SRC / "application" / "use_cases" / "replay_historical_predictions.py"
    ),
    "lottolab.evidence.replay_artifact": SRC / "evidence" / "replay_artifact.py",
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


def test_all_three_replay_execution_modules_exist() -> None:
    for name, path in REPLAY_EXECUTION_MODULE_PATHS.items():
        assert path.is_file(), f"{name} missing at {path}"


def test_domain_replay_predictions_imports_nothing_from_forbidden_layers() -> None:
    imports = _imported_modules(REPLAY_EXECUTION_MODULE_PATHS["lottolab.domain.replay_predictions"])
    forbidden = (
        "lottolab.application",
        "lottolab.infrastructure",
        "lottolab.interfaces",
        "lottolab.evidence",
        "lottolab.strategies",
        "lottolab.normalization",
    )
    assert not any(module.startswith(forbidden) for module in imports)
    for module in imports:
        if module.startswith("lottolab"):
            assert module.startswith("lottolab.domain"), module


def test_use_case_imports_nothing_from_infrastructure_or_interfaces() -> None:
    path = REPLAY_EXECUTION_MODULE_PATHS[
        "lottolab.application.use_cases.replay_historical_predictions"
    ]
    imports = _imported_modules(path)
    assert not any(
        module.startswith(("lottolab.infrastructure", "lottolab.interfaces")) for module in imports
    )


def test_evidence_replay_artifact_imports_nothing_from_forbidden_layers() -> None:
    path = REPLAY_EXECUTION_MODULE_PATHS["lottolab.evidence.replay_artifact"]
    imports = _imported_modules(path)
    forbidden = (
        "lottolab.application",
        "lottolab.infrastructure",
        "lottolab.interfaces",
        "lottolab.strategies",
        "lottolab.normalization",
    )
    assert not any(module.startswith(forbidden) for module in imports)
    for module in imports:
        if module.startswith("lottolab"):
            assert module.startswith(("lottolab.domain", "lottolab.evidence")), module


def test_replay_execution_modules_import_no_sqlite_cli_or_network_dependency() -> None:
    forbidden_exact = {
        "sqlite3",
        "subprocess",
        "socket",
        "urllib",
        "urllib.request",
        "http.client",
        "httpx",
        "importlib",
    }
    for path in REPLAY_EXECUTION_MODULE_PATHS.values():
        imports = _imported_modules(path)
        assert imports.isdisjoint(forbidden_exact), path


def test_causal_draw_row_in_strategies_adapters_base_is_unchanged() -> None:
    """Regression guard: strategies/adapters/base.py's CausalDrawRow must stay untouched.

    Replay must never widen it to add ``special_number`` — see
    ``lottolab.domain.replay_history`` and this task's own History Provenance
    requirement (special number lives only in Replay's own provenance hash).
    """

    from lottolab.strategies.adapters.base import CausalDrawRow

    fields = dataclasses.fields(CausalDrawRow)
    field_names = tuple(field.name for field in fields)
    assert field_names == ("draw", "date", "numbers")
    assert not hasattr(CausalDrawRow, "special_number")
    assert not hasattr(CausalDrawRow, "special")


def test_replay_prediction_snapshot_has_the_declared_field_shape() -> None:
    from lottolab.domain.replay_predictions import ReplayPredictionSnapshot

    field_names = {field.name for field in dataclasses.fields(ReplayPredictionSnapshot)}
    required_minimum = {
        "snapshot_schema_version",
        "dataset_id",
        "dataset_version",
        "lottery_type",
        "target_draw_number",
        "target_draw_date",
        "cutoff_draw_number",
        "cutoff_draw_date",
        "causal_history_count",
        "causal_history_sha256",
        "strategy_id",
        "strategy_version",
        "adapter_strategy_id",
        "source_mode",
        "prediction_status",
        "prediction_reason_code",
        "predicted_main_numbers",
        "result_sha256",
    }
    assert required_minimum <= field_names
    forbidden_fields = {
        "special_number",
        "confidence",
        "candidate_rank",
        "prize",
        "produced_at",
        "timestamp",
    }
    assert field_names.isdisjoint(forbidden_fields)
