"""Real-SQLite acceptance for create_app()'s default local Replay execution.

Mirrors tests/integration/test_replay_research_session_sqlite.py's own
fixture-seeding pattern (same committed synthetic fixture, same task-owned
temp database). The HTTP adapter's own translation/serialization contract is
covered by tests/unit/test_replay_execution_api.py using fakes; this file
only proves LocalReplayExecutor's real-database composition: a seeded target
resolves, a caller-supplied draw_date is never trusted over the stored
canonical one, target/strategy order survives, a missing target and
unavailable storage both fail safely, no write ever reaches the database, and
an explicitly injected executor still wins over a real local database.
"""

# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false
# (Starlette TestClient is partially untyped under the httpx v1 compatibility shim.)

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any, cast

from fastapi.testclient import TestClient

from lottolab.application.use_cases.replay_historical_predictions import (
    ReplayHistoricalPredictionsInput,
    ReplayHistoricalPredictionsResult,
)
from lottolab.domain.draws import LotteryType
from lottolab.evidence.replay_artifact import build_replay_prediction_snapshot
from lottolab.infrastructure.imports.csv_draws import parse_draw_csv
from lottolab.infrastructure.persistence.draw_schema import (
    DATA_DIRECTORY_ENV,
    LocalDataPaths,
    open_database,
    resolve_local_data_paths,
)
from lottolab.infrastructure.persistence.repositories import SQLiteDrawDataRepository
from lottolab.interfaces.api.app import create_app

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = (
    REPO_ROOT / "tests" / "fixtures" / "replay" / "synthetic_biglotto_causal_history.json"
)

_HEADER = "lottery_type,draw_number,draw_date,main_numbers,special_numbers,source"
_PATH = "/api/v1/replay-execution"
_DATASET_ID = "SYNTHETIC_BIG_LOTTO_REPLAY_EXECUTION_API_SQLITE_R1"
_DATASET_VERSION = "1"
_KNOWN_STRATEGY_ID = "biglotto_social_wisdom_anti_popularity"
_OTHER_STRATEGY_ID = "biglotto_zone_split_3bet_bet1"
_TABLES = ("draws", "schema_migrations", "ingestion_runs", "ingestion_items")


def _task_paths(tmp_path: Path, name: str = "replay-execution-api-sqlite") -> LocalDataPaths:
    return resolve_local_data_paths(environ={DATA_DIRECTORY_ENV: str(tmp_path / name)})


def _fixture_rows() -> list[dict[str, Any]]:
    fixture: dict[str, Any] = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    return cast("list[dict[str, Any]]", fixture["history_rows"])


def _seed_canonical_draws(paths: LocalDataPaths) -> None:
    rows = [
        ",".join(
            (
                LotteryType.BIG_LOTTO.value,
                row["draw_number"],
                row["draw_date"],
                "|".join(str(number) for number in row["main_numbers"]),
                str(row["special_number"]),
                "synthetic-replay-execution-api-sqlite",
            )
        )
        for row in _fixture_rows()
    ]
    document = parse_draw_csv(
        "\n".join((_HEADER, *rows, "")),
        filename="synthetic-replay-execution-api-sqlite.csv",
    )
    assert document.is_valid, document.errors

    result = SQLiteDrawDataRepository(paths).apply_valid_import(document)

    assert result.inserted_count == len(rows) == 110
    assert result.skipped_count == result.conflict_count == result.failed_count == 0


def _draw_date_for(draw_number: str) -> date:
    for row in _fixture_rows():
        if row["draw_number"] == draw_number:
            return date.fromisoformat(row["draw_date"])
    raise AssertionError(f"fixture has no row for {draw_number}")


def _table_snapshot(paths: LocalDataPaths) -> dict[str, tuple[tuple[object, ...], ...]]:
    with open_database(paths, read_only=True) as connection:
        return {
            table: tuple(
                tuple(row) for row in connection.execute(f"SELECT * FROM {table} ORDER BY rowid")
            )
            for table in _TABLES
        }


def _payload(
    *,
    targets: list[tuple[str, str]],
    strategy_ids: list[str],
    lottery_type: str = "BIG_LOTTO",
    dataset_id: str = _DATASET_ID,
    dataset_version: str = _DATASET_VERSION,
) -> dict[str, Any]:
    return {
        "lottery_type": lottery_type,
        "dataset_id": dataset_id,
        "dataset_version": dataset_version,
        "targets": [
            {"draw_number": draw_number, "draw_date": draw_date}
            for draw_number, draw_date in targets
        ],
        "strategy_ids": strategy_ids,
    }


def test_default_composition_resolves_a_real_seeded_target(tmp_path: Path) -> None:
    paths = _task_paths(tmp_path)
    _seed_canonical_draws(paths)
    client = TestClient(create_app(data_paths_provider=lambda: paths))

    response = client.post(
        _PATH,
        json=_payload(targets=[("1000104", "2020-04-14")], strategy_ids=[_KNOWN_STRATEGY_ID]),
    )

    assert response.status_code == 200
    body = cast(dict[str, Any], response.json())
    assert len(body["snapshots"]) == 1
    snapshot = body["snapshots"][0]
    assert snapshot["target_draw_number"] == "1000104"
    assert snapshot["history_status"] == "OK"
    assert snapshot["prediction_status"] is not None


def test_caller_supplied_draw_date_is_never_trusted_over_the_stored_canonical_date(
    tmp_path: Path,
) -> None:
    paths = _task_paths(tmp_path)
    _seed_canonical_draws(paths)
    client = TestClient(create_app(data_paths_provider=lambda: paths))
    stored_date = _draw_date_for("1000104")
    wrong_date = "1999-01-01"
    assert wrong_date != stored_date.isoformat()

    response = client.post(
        _PATH,
        json=_payload(targets=[("1000104", wrong_date)], strategy_ids=[_KNOWN_STRATEGY_ID]),
    )

    assert response.status_code == 200
    snapshot = cast(dict[str, Any], response.json())["snapshots"][0]
    assert snapshot["target_draw_date"] == stored_date.isoformat()
    assert snapshot["target_draw_date"] != wrong_date


def test_target_and_strategy_order_are_preserved_through_the_default_composition(
    tmp_path: Path,
) -> None:
    paths = _task_paths(tmp_path)
    _seed_canonical_draws(paths)
    client = TestClient(create_app(data_paths_provider=lambda: paths))
    strategy_ids = [_KNOWN_STRATEGY_ID, _OTHER_STRATEGY_ID]

    response = client.post(
        _PATH,
        json=_payload(
            targets=[("1000106", "2020-04-16"), ("1000104", "2020-04-14")],
            strategy_ids=strategy_ids,
        ),
    )

    assert response.status_code == 200
    body = cast(dict[str, Any], response.json())
    pairs = [
        (snapshot["target_draw_number"], snapshot["strategy_id"]) for snapshot in body["snapshots"]
    ]
    assert pairs == [
        ("1000106", strategy_ids[0]),
        ("1000106", strategy_ids[1]),
        ("1000104", strategy_ids[0]),
        ("1000104", strategy_ids[1]),
    ]


def test_missing_target_in_a_real_database_retains_the_existing_closed_semantics(
    tmp_path: Path,
) -> None:
    paths = _task_paths(tmp_path)
    _seed_canonical_draws(paths)
    client = TestClient(create_app(data_paths_provider=lambda: paths))

    response = client.post(
        _PATH,
        json=_payload(targets=[("9999999", "2020-01-01")], strategy_ids=[_KNOWN_STRATEGY_ID]),
    )

    assert response.status_code == 200
    snapshot = cast(dict[str, Any], response.json())["snapshots"][0]
    assert snapshot["history_status"] == "TARGET_NOT_FOUND"
    assert snapshot["history_reason_code"] == "TARGET_DRAW_NOT_FOUND"


def test_unavailable_storage_fails_safely_without_leaking_internal_detail(tmp_path: Path) -> None:
    del tmp_path
    broken_paths = LocalDataPaths(
        data_directory=Path("relative-broken-replay-execution-path"),
        database=Path("relative-broken-replay-execution-path/lottolab.db"),
    )
    client = TestClient(create_app(data_paths_provider=lambda: broken_paths))

    response = client.post(
        _PATH,
        json=_payload(targets=[("1000104", "2020-04-14")], strategy_ids=[_KNOWN_STRATEGY_ID]),
    )

    assert response.status_code == 503
    assert response.json() == {
        "error_code": "REPLAY_EXECUTION_UNAVAILABLE",
        "message": "Replay execution is unavailable.",
    }
    assert "relative-broken-replay-execution-path" not in response.text
    assert "Traceback" not in response.text


def test_default_composition_never_writes_to_the_local_database(tmp_path: Path) -> None:
    paths = _task_paths(tmp_path)
    _seed_canonical_draws(paths)
    before = _table_snapshot(paths)
    client = TestClient(create_app(data_paths_provider=lambda: paths))

    response = client.post(
        _PATH,
        json=_payload(
            targets=[("1000104", "2020-04-14"), ("9999999", "2020-01-01")],
            strategy_ids=[_KNOWN_STRATEGY_ID],
        ),
    )
    after = _table_snapshot(paths)

    assert response.status_code == 200
    assert after == before, "default replay execution composition must never write"


def test_injected_executor_wins_even_when_a_real_local_database_is_present(
    tmp_path: Path,
) -> None:
    """Acceptance A: an injected executor is authoritative, and the default
    local composition must not even be constructed/used -- proven here by
    handing create_app() a paths_provider that raises if LocalReplayExecutor
    ever calls it, alongside a real seeded database an accidental fallback
    to the default composition would otherwise successfully read from."""

    paths = _task_paths(tmp_path)
    _seed_canonical_draws(paths)

    def _exploding_paths_provider() -> LocalDataPaths:
        raise AssertionError("default local composition must not be used when injected")

    class _StubExecutor:
        def execute(
            self, request: ReplayHistoricalPredictionsInput
        ) -> ReplayHistoricalPredictionsResult:
            target = request.targets[0]
            return ReplayHistoricalPredictionsResult(
                snapshots=(
                    build_replay_prediction_snapshot(
                        dataset_id=request.dataset_id,
                        dataset_version=request.dataset_version,
                        lottery_type=request.lottery_type,
                        target=target,
                        strategy_id=request.strategy_ids[0],
                        strategy_identity=None,
                        history_status="TARGET_NOT_FOUND",
                        history_reason_code="TARGET_DRAW_NOT_FOUND",
                        causal_history=None,
                        prediction_status=None,
                        prediction_reason_code=None,
                        predicted_main_numbers=None,
                    ),
                )
            )

    client = TestClient(
        create_app(
            replay_executor=_StubExecutor(),
            data_paths_provider=_exploding_paths_provider,
        )
    )

    response = client.post(
        _PATH,
        json=_payload(targets=[("1000104", "2020-04-14")], strategy_ids=[_KNOWN_STRATEGY_ID]),
    )

    assert response.status_code == 200
    snapshot = cast(dict[str, Any], response.json())["snapshots"][0]
    # The stub's fixed placeholder, not a real OK prediction from the seeded
    # database -- proves the real local database was never consulted.
    assert snapshot["history_status"] == "TARGET_NOT_FOUND"
