"""Persisted exact-SHA Replay-ranking integration over a pytest-owned SQLite DB."""

# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false

from __future__ import annotations

import hashlib
import sqlite3
from datetime import date
from pathlib import Path
from typing import Any, cast

from fastapi.testclient import TestClient

from lottolab.application.use_cases.persist_replay_scoring_artifact import (
    PersistReplayScoringArtifact,
)
from lottolab.application.use_cases.score_replay_artifact import ScoreReplayArtifact
from lottolab.domain.draws import LotteryType
from lottolab.domain.replay_predictions import ReplayTarget
from lottolab.domain.replay_scoring import ReplayTargetOutcome, ReplayTargetOutcomeReadResult
from lottolab.evidence.replay_artifact import (
    build_replay_artifact,
    build_replay_prediction_snapshot,
)
from lottolab.evidence.replay_scoring_artifact import (
    ReplayScoringArtifact,
    build_replay_scoring_artifact,
)
from lottolab.infrastructure.persistence.replay_scoring_projection_repository import (
    SQLiteReplayScoringProjectionRepository,
)
from lottolab.interfaces.api.app import create_app

_WINNING = (1, 2, 3, 4, 5, 6)
_LOSING = (11, 12, 13, 14, 15, 16)
_UNKNOWN_SHA = "f" * 64


class _OutcomeReader:
    def load_target_outcome(
        self, lottery_type: LotteryType, target_draw_number: str
    ) -> ReplayTargetOutcomeReadResult:
        return ReplayTargetOutcomeReadResult.found(
            ReplayTargetOutcome.create(
                lottery_type=lottery_type,
                target_draw_number=target_draw_number,
                target_draw_date=date(2026, 7, 1),
                winning_main_numbers=_WINNING,
                winning_special_number=7,
            )
        )


class _CountingRepository(SQLiteReplayScoringProjectionRepository):
    def __init__(self, database: Path) -> None:
        super().__init__(database)
        self.artifact_reads: list[str] = []

    def get_replay_scoring_artifact(
        self, scoring_artifact_payload_sha256: str
    ) -> ReplayScoringArtifact | None:
        self.artifact_reads.append(scoring_artifact_payload_sha256)
        return super().get_replay_scoring_artifact(scoring_artifact_payload_sha256)


def _build_artifact(*, dataset_version: str, winning_strategy: str) -> ReplayScoringArtifact:
    target = ReplayTarget("700", date(2026, 7, 1))
    strategy_ids = ("alpha", "beta")
    snapshots = tuple(
        build_replay_prediction_snapshot(
            dataset_id="persisted-ranking",
            dataset_version=dataset_version,
            lottery_type=LotteryType.BIG_LOTTO,
            target=target,
            strategy_id=strategy_id,
            strategy_identity=(strategy_id, strategy_id.title(), "1.0.0"),
            history_status="OK",
            history_reason_code=None,
            causal_history=(),
            prediction_status="OK",
            prediction_reason_code=None,
            predicted_main_numbers=(
                _WINNING if strategy_id == winning_strategy else _LOSING
            ),
        )
        for strategy_id in strategy_ids
    )
    source = build_replay_artifact(
        dataset_id="persisted-ranking",
        dataset_version=dataset_version,
        lottery_type=LotteryType.BIG_LOTTO,
        strategy_ids=strategy_ids,
        targets=(target,),
        snapshots=snapshots,
    )
    scored = ScoreReplayArtifact(_OutcomeReader()).execute(source)
    return build_replay_scoring_artifact(
        source_artifact=source,
        scored_predictions=scored.scored_predictions,
        strategy_aggregates=scored.strategy_aggregates,
        overall_aggregate=scored.overall_aggregate,
    )


def _database_snapshot(database: Path) -> tuple[object, ...]:
    connection = sqlite3.connect(f"{database.as_uri()}?mode=ro", uri=True)
    try:
        connection.execute("PRAGMA query_only = ON")
        tables = tuple(
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            )
        )
        schema = tuple(
            connection.execute(
                "SELECT type, name, tbl_name, sql FROM sqlite_master ORDER BY type, name"
            )
        )
        rows = tuple(
            (table, tuple(connection.execute(f'SELECT * FROM "{table}" ORDER BY rowid')))
            for table in tables
        )
        metadata = (
            connection.execute("PRAGMA schema_version").fetchone(),
            connection.execute("PRAGMA user_version").fetchone(),
            tuple(
                (table, tuple(connection.execute(f'PRAGMA table_info("{table}")')))
                for table in tables
            ),
        )
        return tables, schema, rows, metadata
    finally:
        connection.close()


def _database_sha256(database: Path) -> str:
    return hashlib.sha256(database.read_bytes()).hexdigest()


def _sidecars(database: Path) -> tuple[Path, ...]:
    return tuple(
        path
        for suffix in ("-wal", "-shm", "-journal")
        if (path := Path(f"{database}{suffix}")).exists()
    )


def test_exact_persisted_selector_isolated_and_database_unchanged(tmp_path: Path) -> None:
    database = tmp_path / "replay-scoring.db"
    writer = SQLiteReplayScoringProjectionRepository(database)
    artifact_a = _build_artifact(dataset_version="a", winning_strategy="alpha")
    artifact_b = _build_artifact(dataset_version="b", winning_strategy="beta")
    PersistReplayScoringArtifact(writer).execute(artifact_a)
    PersistReplayScoringArtifact(writer).execute(artifact_b)
    before_snapshot = _database_snapshot(database)
    before_digest = _database_sha256(database)
    assert _sidecars(database) == ()

    factory_calls: list[int] = []
    readers: list[_CountingRepository] = []

    def reader_factory() -> _CountingRepository:
        factory_calls.append(1)
        reader = _CountingRepository(database)
        readers.append(reader)
        return reader

    app = create_app(replay_scoring_projection_reader_factory=reader_factory)
    app.openapi()
    assert factory_calls == []
    client = TestClient(app)

    response_a = client.get(
        "/api/v1/replay-rankings/optimal",
        params={"scoring_artifact_payload_sha256": artifact_a.payload_sha256},
    )
    response_b = client.get(
        "/api/v1/replay-rankings/optimal",
        params={"scoring_artifact_payload_sha256": artifact_b.payload_sha256},
    )
    response_unknown = client.get(
        "/api/v1/replay-rankings/optimal",
        params={"scoring_artifact_payload_sha256": _UNKNOWN_SHA},
    )

    assert response_a.status_code == response_b.status_code == 200
    payload_a = cast(dict[str, Any], response_a.json())
    payload_b = cast(dict[str, Any], response_b.json())
    assert payload_a["source_scoring_artifact_payload_sha256"] == artifact_a.payload_sha256
    assert payload_b["source_scoring_artifact_payload_sha256"] == artifact_b.payload_sha256
    assert payload_a["groups"][0]["candidates"][0]["members"][0]["strategy_id"] == "alpha"
    assert payload_b["groups"][0]["candidates"][0]["members"][0]["strategy_id"] == "beta"
    assert response_unknown.status_code == 404
    assert response_unknown.json()["error_code"] == "REPLAY_RANKING_SOURCE_NOT_FOUND"
    assert factory_calls == [1, 1, 1]
    assert [reader.artifact_reads for reader in readers] == [
        [artifact_a.payload_sha256],
        [artifact_b.payload_sha256],
        [_UNKNOWN_SHA],
    ]

    assert _database_snapshot(database) == before_snapshot
    assert _database_sha256(database) == before_digest
    assert _sidecars(database) == ()
