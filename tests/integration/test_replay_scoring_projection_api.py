"""Real-SQLite HTTP tests for the read-only Replay-scoring projection API."""

# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false
# pyright: reportPrivateUsage=false
# (Starlette TestClient is partially untyped; the reused builder is test-only seed data.)

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from fastapi.testclient import TestClient
from tests.integration.test_replay_scoring_projection_sqlite import (
    _build_two_by_two_artifact,
)

from lottolab.application.use_cases.persist_replay_scoring_artifact import (
    PersistReplayScoringArtifact,
)
from lottolab.evidence.replay_scoring_artifact import ReplayScoringArtifact
from lottolab.infrastructure.persistence.replay_scoring_projection_repository import (
    SQLiteReplayScoringProjectionRepository,
)
from lottolab.infrastructure.persistence.replay_scoring_schema import TABLE_NAMES
from lottolab.interfaces.api.app import create_app


@dataclass(frozen=True, slots=True)
class _DatabaseSnapshot:
    database_bytes: bytes
    tables: tuple[str, ...]
    row_counts: tuple[tuple[str, int], ...]
    schema: tuple[tuple[object, ...], ...]
    records: tuple[tuple[str, tuple[tuple[object, ...], ...]], ...]
    sidecars: tuple[str, ...]


class _Factory:
    def __init__(self, database: Path) -> None:
        self.database = database
        self.calls = 0

    def __call__(self) -> SQLiteReplayScoringProjectionRepository:
        self.calls += 1
        return SQLiteReplayScoringProjectionRepository(self.database)


def _seed(tmp_path: Path) -> tuple[Path, ReplayScoringArtifact]:
    database = tmp_path / "replay_scoring.db"
    artifact = _build_two_by_two_artifact()
    PersistReplayScoringArtifact(
        SQLiteReplayScoringProjectionRepository(database)
    ).execute(artifact)
    return database, artifact


def _snapshot(database: Path) -> _DatabaseSnapshot:
    uri = f"file:{database.as_posix()}?mode=ro"
    with sqlite3.connect(uri, uri=True) as connection:
        tables = tuple(
            cast(
                str,
                row[0],
            )
            for row in connection.execute(
                "SELECT name FROM sqlite_schema WHERE type='table' ORDER BY name"
            )
        )
        row_counts = tuple(
            (table, cast(int, connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]))
            for table in TABLE_NAMES
        )
        schema = tuple(
            tuple(row)
            for row in connection.execute(
                "SELECT type, name, tbl_name, sql FROM sqlite_schema ORDER BY type, name"
            )
        )
        records = tuple(
            (
                table,
                tuple(
                    tuple(row)
                    for row in connection.execute(f'SELECT * FROM "{table}" ORDER BY rowid')
                ),
            )
            for table in TABLE_NAMES
        )
    sidecars = tuple(
        sorted(
            path.name
            for path in database.parent.glob(f"{database.name}-*")
            if path.is_file()
        )
    )
    return _DatabaseSnapshot(
        database_bytes=database.read_bytes(),
        tables=tables,
        row_counts=row_counts,
        schema=schema,
        records=records,
        sidecars=sidecars,
    )


def test_four_get_operations_and_filters_forward_stored_semantics_read_only(
    tmp_path: Path,
) -> None:
    database, artifact = _seed(tmp_path)
    factory = _Factory(database)
    app = create_app(replay_scoring_projection_reader_factory=factory)
    client = TestClient(app)
    sha = artifact.payload_sha256
    before = _snapshot(database)

    openapi = client.get("/openapi.json")
    assert openapi.status_code == 200
    assert factory.calls == 0

    run = client.get(f"/api/v1/replay-scoring/{sha}")
    assert run.status_code == 200
    assert run.json() == {
        "scoring_artifact_schema_version": artifact.artifact_schema_version,
        "scoring_artifact_payload_sha256": sha,
        "source_replay_artifact_payload_sha256": artifact.source_replay_artifact_payload_sha256,
        "dataset_id": artifact.dataset_id,
        "dataset_version": artifact.dataset_version,
        "lottery_type": artifact.lottery_type.value,
        "target_count": 2,
        "strategy_count": 2,
        "scored_record_count": 4,
        "overall_aggregate_sha256": artifact.overall_aggregate.aggregation_sha256,
    }
    assert factory.calls == 1

    predictions = client.get(f"/api/v1/replay-scoring/{sha}/predictions")
    assert predictions.status_code == 200
    prediction_payload = predictions.json()
    assert [item["ordinal"] for item in prediction_payload] == [0, 1, 2, 3]
    assert [item["scoring_status"] for item in prediction_payload] == [
        "SCORED",
        "SCORED",
        "NOT_SCORED_HISTORY_CLOSED",
        "NOT_SCORED_PREDICTION_CLOSED",
    ]
    assert prediction_payload[0]["prize_tier_id"] == "FIRST"
    assert prediction_payload[1]["no_prize_result"] == "NO_PRIZE"
    assert prediction_payload[2]["predicted_main_numbers"] is None
    assert factory.calls == 2

    expected_filters = [
        ("target_draw=300", [0, 1]),
        ("strategy_id=beta", [1, 3]),
        ("status=SCORED", [0, 1]),
        ("tier=FIRST", [0]),
        ("tier=NO_PRIZE", [1]),
        ("target_draw=301&strategy_id=beta", [3]),
    ]
    for query, expected_ordinals in expected_filters:
        before_call = factory.calls
        response = client.get(f"/api/v1/replay-scoring/{sha}/predictions?{query}")
        assert response.status_code == 200
        assert [item["ordinal"] for item in response.json()] == expected_ordinals
        assert factory.calls == before_call + 1

    strategy_aggregates = client.get(
        f"/api/v1/replay-scoring/{sha}/strategy-aggregates"
    )
    assert strategy_aggregates.status_code == 200
    assert [item["ordinal"] for item in strategy_aggregates.json()] == [0, 1]
    assert [item["strategy_id"] for item in strategy_aggregates.json()] == [
        "alpha",
        "beta",
    ]

    overall = client.get(f"/api/v1/replay-scoring/{sha}/overall-aggregate")
    assert overall.status_code == 200
    assert overall.json()["aggregate_sha256"] == artifact.overall_aggregate.aggregation_sha256
    assert overall.json()["source_snapshot_count"] == 4

    repeated = client.get(f"/api/v1/replay-scoring/{sha}/predictions")
    assert repeated.status_code == 200
    assert repeated.json() == prediction_payload

    after = _snapshot(database)
    assert after == before
    assert before.tables == tuple(sorted(TABLE_NAMES))
    assert before.sidecars == ()
    assert after.sidecars == ()


def test_validation_not_configured_not_found_and_storage_errors_are_sanitized(
    tmp_path: Path,
) -> None:
    database, artifact = _seed(tmp_path)
    factory = _Factory(database)
    client = TestClient(create_app(replay_scoring_projection_reader_factory=factory))

    invalid_sha = client.get("/api/v1/replay-scoring/" + "A" * 64)
    assert invalid_sha.status_code == 422
    assert invalid_sha.json()["error_code"] == "REQUEST_VALIDATION_FAILED"
    assert factory.calls == 0

    invalid_filter = client.get(
        f"/api/v1/replay-scoring/{artifact.payload_sha256}/predictions?status=UNKNOWN"
    )
    assert invalid_filter.status_code == 422
    assert invalid_filter.json() == {
        "error_code": "REQUEST_VALIDATION_FAILED",
        "message": "Request validation failed.",
        "fields": [],
        "preview": None,
    }
    assert factory.calls == 0

    missing = client.get("/api/v1/replay-scoring/" + "0" * 64)
    assert missing.status_code == 404
    assert missing.json()["error_code"] == "REPLAY_SCORING_RUN_NOT_FOUND"
    assert factory.calls == 1

    not_configured = TestClient(create_app()).get(
        f"/api/v1/replay-scoring/{artifact.payload_sha256}"
    )
    assert not_configured.status_code == 503
    assert not_configured.json()["error_code"] == "REPLAY_SCORING_QUERY_NOT_CONFIGURED"

    def unavailable_factory():
        raise RuntimeError(f"private database path: {database}")

    unavailable = TestClient(
        create_app(replay_scoring_projection_reader_factory=unavailable_factory)
    ).get(f"/api/v1/replay-scoring/{artifact.payload_sha256}")
    assert unavailable.status_code == 503
    assert unavailable.json() == {
        "error_code": "REPLAY_SCORING_QUERY_UNAVAILABLE",
        "message": "Replay scoring query is unavailable.",
    }
    assert str(database) not in unavailable.text


def test_authoritative_payload_tamper_returns_503_without_get_side_effects(
    tmp_path: Path,
) -> None:
    database, artifact = _seed(tmp_path)
    with sqlite3.connect(database) as connection:
        connection.execute(
            """
            UPDATE replay_scoring_runs SET canonical_bytes = canonical_bytes || X'20'
            WHERE scoring_artifact_payload_sha256 = ?
            """,
            (artifact.payload_sha256,),
        )
        connection.commit()
    before = _snapshot(database)

    response = TestClient(
        create_app(
            replay_scoring_projection_reader_factory=lambda: (
                SQLiteReplayScoringProjectionRepository(database)
            )
        )
    ).get(f"/api/v1/replay-scoring/{artifact.payload_sha256}")

    assert response.status_code == 503
    assert response.json() == {
        "error_code": "REPLAY_SCORING_QUERY_UNAVAILABLE",
        "message": "Replay scoring query is unavailable.",
    }
    assert _snapshot(database) == before
    assert before.sidecars == ()
