"""Architecture and protected-shape guards for Replay prize scoring."""

from __future__ import annotations

import ast
import dataclasses
import inspect
from pathlib import Path

from lottolab.application.ports import ReplayTargetOutcomeReader
from lottolab.infrastructure.persistence.draw_schema import resolve_local_data_paths
from lottolab.infrastructure.persistence.replay_target_outcome_reader import (
    SQLiteReplayTargetOutcomeReader,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src" / "lottolab"
PATHS = {
    "domain": SRC / "domain" / "replay_scoring.py",
    "use_case": SRC / "application" / "use_cases" / "score_replay_artifact.py",
    "adapter": SRC / "infrastructure" / "persistence" / "replay_target_outcome_reader.py",
    "artifact": SRC / "evidence" / "replay_scoring_artifact.py",
}


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def test_scoring_modules_exist_in_the_declared_layers() -> None:
    assert all(path.is_file() for path in PATHS.values())


def test_scoring_domain_imports_no_upper_layer() -> None:
    imports = _imports(PATHS["domain"])
    assert not any(
        module.startswith(
            (
                "lottolab.application",
                "lottolab.infrastructure",
                "lottolab.interfaces",
                "lottolab.evidence",
                "lottolab.strategies",
            )
        )
        for module in imports
    )


def test_scoring_use_case_imports_no_infrastructure_or_interfaces() -> None:
    imports = _imports(PATHS["use_case"])
    assert not any(
        module.startswith(("lottolab.infrastructure", "lottolab.interfaces"))
        for module in imports
    )


def test_scoring_artifact_imports_no_database_or_transport() -> None:
    imports = _imports(PATHS["artifact"])
    assert "sqlite3" not in imports
    assert not any(
        module.startswith(
            (
                "lottolab.application",
                "lottolab.infrastructure",
                "lottolab.interfaces",
                "httpx",
                "urllib",
            )
        )
        for module in imports
    )


def test_sqlite_adapter_implements_only_the_narrow_reader_port() -> None:
    paths = resolve_local_data_paths(
        environ={"LOTTOLAB_DATA_DIR": "/nonexistent-replay-scoring-check"}
    )
    reader = SQLiteReplayTargetOutcomeReader(paths)
    assert isinstance(reader, ReplayTargetOutcomeReader)
    public_methods = {
        name
        for name, member in inspect.getmembers(SQLiteReplayTargetOutcomeReader)
        if inspect.isfunction(member) and not name.startswith("_")
    }
    assert public_methods == {"load_target_outcome"}


def test_scoring_sources_do_not_import_the_historical_query_domain() -> None:
    forbidden = (
        "HistoricalResultQueryRepository",
        "historical_queries",
        "historical_repositories",
        "historical_results",
    )
    for path in PATHS.values():
        source = path.read_text(encoding="utf-8")
        assert not any(token in source for token in forbidden), path


def test_protected_replay_source_shapes_are_unchanged() -> None:
    from lottolab.domain.replay_predictions import ReplayPredictionSnapshot
    from lottolab.evidence.replay_artifact import ReplayArtifact

    assert tuple(field.name for field in dataclasses.fields(ReplayPredictionSnapshot)) == (
        "snapshot_schema_version",
        "dataset_id",
        "dataset_version",
        "lottery_type",
        "source_mode",
        "target_draw_number",
        "target_draw_date",
        "cutoff_draw_number",
        "cutoff_draw_date",
        "strategy_id",
        "strategy_version",
        "adapter_strategy_id",
        "adapter_strategy_name",
        "adapter_strategy_version",
        "history_status",
        "history_reason_code",
        "causal_history_count",
        "causal_history_sha256",
        "prediction_status",
        "prediction_reason_code",
        "predicted_main_numbers",
        "result_sha256",
    )
    assert tuple(field.name for field in dataclasses.fields(ReplayArtifact)) == (
        "artifact_schema_version",
        "dataset_id",
        "dataset_version",
        "lottery_type",
        "strategy_ids",
        "targets",
        "snapshots",
        "snapshot_count",
        "payload_sha256",
    )


def test_scoring_contains_no_duplicate_prize_signature_mapping() -> None:
    use_case_source = PATHS["use_case"].read_text(encoding="utf-8")
    domain_source = PATHS["domain"].read_text(encoding="utf-8")
    assert use_case_source.count("resolve_big_lotto_prize_tier") == 1
    assert "BigLottoPrizeTier(" not in use_case_source
    assert "BigLottoPrizeTier(" not in domain_source
    for signature in ("(6, False)", "(5, True)", "(5, False)", "(4, True)"):
        assert signature not in use_case_source
        assert signature not in domain_source


def test_no_cli_router_or_frontend_path_references_scoring() -> None:
    scanned = (
        *(SRC / "interfaces").rglob("*.py"),
        *(REPO_ROOT / "frontend").rglob("*"),
    )
    for path in scanned:
        if path.is_file():
            assert "replay_scoring" not in path.read_text(encoding="utf-8", errors="ignore")
