"""Architecture boundary tests scoped to the Replay PORTFOLIO execution path.

A task-owned counterpart to the shared ``tests/architecture/test_dependency_rules.py``
(protected, not modified by this task; it already scans all of ``src/lottolab``
for cross-layer import violations project-wide, so this new module is also
covered by it) and to ``tests/architecture/test_replay_execution_dependency_rules.py``
(protected -- not modified here; it already re-verifies the shared
``lottolab.domain.replay_predictions`` and ``lottolab.application.use_cases.
replay_historical_predictions`` modules this task edited). Re-implements a
tiny, self-contained AST import walker rather than importing either protected
module, keeping this file fully independent -- mirroring the existing
pattern.
"""

from __future__ import annotations

import ast
import dataclasses
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src" / "lottolab"

PORTFOLIO_USE_CASE_PATH = (
    SRC / "application" / "use_cases" / "replay_historical_portfolio_predictions.py"
)
RESEARCH_SESSION_PATH = SRC / "interfaces" / "research" / "replay_research_session.py"


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


def test_portfolio_use_case_module_exists() -> None:
    assert PORTFOLIO_USE_CASE_PATH.is_file()


def test_portfolio_use_case_imports_nothing_from_infrastructure_or_interfaces() -> None:
    imports = _imported_modules(PORTFOLIO_USE_CASE_PATH)
    assert not any(
        module.startswith(("lottolab.infrastructure", "lottolab.interfaces")) for module in imports
    )


def test_portfolio_use_case_imports_no_sqlite_cli_or_network_dependency() -> None:
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
    imports = _imported_modules(PORTFOLIO_USE_CASE_PATH)
    assert imports.isdisjoint(forbidden_exact)


def test_portfolio_use_case_reuses_the_single_ticket_causal_row_converter() -> None:
    """``to_causal_draw_rows`` must stay the one place Replay narrows
    ``ReplayCausalDrawRow`` down to the strategy adapter's ``CausalDrawRow``
    shape -- the PORTFOLIO path must import it, never redefine it."""

    source = PORTFOLIO_USE_CASE_PATH.read_text(encoding="utf-8")
    assert "from lottolab.application.use_cases.replay_historical_predictions import" in source
    assert "to_causal_draw_rows" in source
    assert "def to_causal_draw_rows(" not in source
    assert "def _to_causal_draw_rows(" not in source


def test_replay_portfolio_prediction_snapshot_has_the_declared_field_shape() -> None:
    from lottolab.domain.replay_predictions import ReplayPortfolioPredictionSnapshot

    field_names = {field.name for field in dataclasses.fields(ReplayPortfolioPredictionSnapshot)}
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
        "predicted_tickets",
    }
    assert required_minimum <= field_names
    forbidden_fields = {
        "predicted_main_numbers",
        "special_number",
        "confidence",
        "candidate_rank",
        "prize",
        "produced_at",
        "timestamp",
        "result_sha256",
    }
    assert field_names.isdisjoint(forbidden_fields)


def test_research_session_exposes_a_portfolio_replay_method() -> None:
    source = RESEARCH_SESSION_PATH.read_text(encoding="utf-8")
    assert "def replay_portfolio_targets(" in source
    assert "def replay_targets(" in source  # SINGLE_TICKET path still present, unremoved
