"""Focused real-SQLite acceptance for local Replay execution composition."""

# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false
# (Starlette TestClient and sqlite row values are partially untyped.)

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Never, cast

from fastapi.testclient import TestClient
from pytest import MonkeyPatch

from lottolab.domain.draws import LotteryType
from lottolab.infrastructure.imports.csv_draws import parse_draw_csv
from lottolab.infrastructure.persistence.draw_schema import (
    DATA_DIRECTORY_ENV,
    LocalDataPaths,
    open_database,
    resolve_local_data_paths,
)
from lottolab.infrastructure.persistence.repositories import SQLiteDrawDataRepository
from lottolab.interfaces.api.local_app import create_local_app

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = (
    REPO_ROOT / "tests" / "fixtures" / "replay" / "synthetic_biglotto_causal_history.json"
)

_HEADER = "lottery_type,draw_number,draw_date,main_numbers,special_numbers,source"
_PATH = "/api/v1/replay-execution"
_DATASET_ID = "SYNTHETIC_BIG_LOTTO_REPLAY_EXECUTION_LOCAL_APP_R2"
_DATASET_VERSION = "1"
_KNOWN_STRATEGY_ID = "biglotto_social_wisdom_anti_popularity"
_OTHER_STRATEGY_ID = "biglotto_zone_split_3bet_bet1"
_SNAPSHOT_FIELDS = {
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
}


def _task_paths(tmp_path: Path, name: str = "replay-execution-local-app") -> LocalDataPaths:
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
                "synthetic-replay-execution-local-app",
            )
        )
        for row in _fixture_rows()
    ]
    document = parse_draw_csv(
        "\n".join((_HEADER, *rows, "")),
        filename="synthetic-replay-execution-local-app.csv",
    )
    assert document.is_valid, document.errors

    result = SQLiteDrawDataRepository(paths).apply_valid_import(document)

    assert result.inserted_count == len(rows) == 110
    assert result.skipped_count == result.conflict_count == result.failed_count == 0


def _draw_date_for(draw_number: str) -> str:
    for row in _fixture_rows():
        if row["draw_number"] == draw_number:
            return cast(str, row["draw_date"])
    raise AssertionError(f"fixture has no row for {draw_number}")


def _database_inventory(
    paths: LocalDataPaths,
) -> tuple[tuple[str, ...], tuple[tuple[str, int], ...], int, str, tuple[str, ...]]:
    with open_database(paths, read_only=True) as connection:
        tables = tuple(
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
            )
            if not str(row[0]).startswith("sqlite_")
        )
        counts: list[tuple[str, int]] = []
        for table in tables:
            row = connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()
            assert row is not None
            counts.append((table, int(row[0])))

    database = paths.database
    sidecars = tuple(sorted(path.name for path in database.parent.glob(f"{database.name}-*")))
    return (
        tables,
        tuple(counts),
        database.stat().st_size,
        hashlib.sha256(database.read_bytes()).hexdigest(),
        sidecars,
    )


def _client(monkeypatch: MonkeyPatch, paths: LocalDataPaths) -> TestClient:
    monkeypatch.setenv(DATA_DIRECTORY_ENV, str(paths.data_directory))
    return TestClient(create_local_app())


def _payload(
    *,
    targets: list[tuple[str, str]],
    strategy_ids: list[str],
    maximum_history_draws: int | None = None,
    minimum_history_draws: int | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "lottery_type": LotteryType.BIG_LOTTO.value,
        "dataset_id": _DATASET_ID,
        "dataset_version": _DATASET_VERSION,
        "targets": [
            {"draw_number": draw_number, "draw_date": draw_date}
            for draw_number, draw_date in targets
        ],
        "strategy_ids": strategy_ids,
    }
    if maximum_history_draws is not None:
        payload["maximum_history_draws"] = maximum_history_draws
    if minimum_history_draws is not None:
        payload["minimum_history_draws"] = minimum_history_draws
    return payload


def test_local_app_executes_seeded_replay_without_changing_database(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    paths = _task_paths(tmp_path)
    _seed_canonical_draws(paths)
    before = _database_inventory(paths)
    client = _client(monkeypatch, paths)
    strategy_ids = [_KNOWN_STRATEGY_ID, _OTHER_STRATEGY_ID]

    response = client.post(
        _PATH,
        json=_payload(
            targets=[("1000106", "1999-01-02"), ("1000104", "1999-01-01")],
            strategy_ids=strategy_ids,
        ),
    )

    after = _database_inventory(paths)
    assert response.status_code == 200
    snapshots = cast("list[dict[str, Any]]", response.json()["snapshots"])
    assert [
        (snapshot["target_draw_number"], snapshot["strategy_id"]) for snapshot in snapshots
    ] == [
        ("1000106", strategy_ids[0]),
        ("1000106", strategy_ids[1]),
        ("1000104", strategy_ids[0]),
        ("1000104", strategy_ids[1]),
    ]
    assert {snapshot["target_draw_date"] for snapshot in snapshots[:2]} == {
        _draw_date_for("1000106")
    }
    assert {snapshot["target_draw_date"] for snapshot in snapshots[2:]} == {
        _draw_date_for("1000104")
    }
    assert all(set(snapshot) == _SNAPSHOT_FIELDS for snapshot in snapshots)
    assert all(snapshot["history_status"] == "OK" for snapshot in snapshots)
    assert before == after
    assert after[4] == ()


def test_unknown_strategy_and_invalid_bounds_reuse_existing_closed_results(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    paths = _task_paths(tmp_path)
    _seed_canonical_draws(paths)
    client = _client(monkeypatch, paths)

    unknown = client.post(
        _PATH,
        json=_payload(
            targets=[("1000104", _draw_date_for("1000104"))],
            strategy_ids=["unknown_strategy"],
        ),
    )
    invalid_bounds = client.post(
        _PATH,
        json=_payload(
            targets=[("1000104", _draw_date_for("1000104"))],
            strategy_ids=[_KNOWN_STRATEGY_ID],
            maximum_history_draws=0,
        ),
    )

    assert unknown.status_code == 200
    unknown_snapshot = cast("dict[str, Any]", unknown.json()["snapshots"][0])
    assert unknown_snapshot["history_status"] == "OK"
    assert unknown_snapshot["prediction_status"] == "STRATEGY_UNAVAILABLE"
    assert unknown_snapshot["prediction_reason_code"] == "UNKNOWN_STRATEGY"

    assert invalid_bounds.status_code == 200
    invalid_snapshot = cast("dict[str, Any]", invalid_bounds.json()["snapshots"][0])
    assert invalid_snapshot["history_status"] == "INVALID_BOUNDS"
    assert invalid_snapshot["prediction_status"] is None
    assert invalid_snapshot["predicted_main_numbers"] is None


def test_missing_database_is_sanitized_and_creates_no_files(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    paths = _task_paths(tmp_path, "missing-replay-execution-database")
    assert not paths.data_directory.exists()
    monkeypatch.setenv(DATA_DIRECTORY_ENV, str(paths.data_directory))
    app = create_local_app()
    app.openapi()
    assert not paths.data_directory.exists(), "app construction and OpenAPI wiring must stay lazy"
    client = TestClient(app)

    response = client.post(
        _PATH,
        json=_payload(
            targets=[("1000104", "2020-04-14")],
            strategy_ids=[_KNOWN_STRATEGY_ID],
        ),
    )

    assert response.status_code == 503
    assert response.json() == {
        "error_code": "REPLAY_EXECUTION_UNAVAILABLE",
        "message": "Replay execution is unavailable.",
    }
    assert not paths.data_directory.exists()
    for suffix in ("", "-wal", "-shm", "-journal"):
        assert not Path(f"{paths.database}{suffix}").exists()


def test_local_internal_failure_is_sanitized(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    paths = _task_paths(tmp_path)
    _seed_canonical_draws(paths)
    private_detail = "private local replay stack failed at /secret/lottolab.db"

    def _fail_get_draw(
        repository: SQLiteDrawDataRepository,
        lottery_type: LotteryType,
        draw_number: str,
    ) -> Never:
        del repository, lottery_type, draw_number
        raise RuntimeError(private_detail)

    monkeypatch.setattr(SQLiteDrawDataRepository, "get_draw", _fail_get_draw)
    client = _client(monkeypatch, paths)

    response = client.post(
        _PATH,
        json=_payload(
            targets=[("1000104", "2020-04-14")],
            strategy_ids=[_KNOWN_STRATEGY_ID],
        ),
    )

    assert response.status_code == 503
    assert response.json() == {
        "error_code": "REPLAY_EXECUTION_UNAVAILABLE",
        "message": "Replay execution is unavailable.",
    }
    assert private_detail not in response.text
    assert "Traceback" not in response.text
