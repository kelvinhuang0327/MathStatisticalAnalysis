"""Real-SQLite HTTP coverage for persisted Replay-portfolio ranking."""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false
# pyright: reportPrivateUsage=false

from __future__ import annotations

import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient
from tests.integration.test_replay_scoring_projection_api import _snapshot
from tests.integration.test_replay_scoring_projection_sqlite import (
    _build_two_by_two_artifact,
)

from lottolab.application.ports import ReplayScoringProjectionReader
from lottolab.application.use_cases.persist_replay_scoring_artifact import (
    PersistReplayScoringArtifact,
)
from lottolab.evidence.replay_scoring_artifact import ReplayScoringArtifact
from lottolab.infrastructure.persistence.replay_scoring_projection_repository import (
    SQLiteReplayScoringProjectionRepository,
)
from lottolab.interfaces.api.app import create_app


class _Factory:
    def __init__(self, database: Path) -> None:
        self.database = database
        self.calls = 0

    def __call__(self) -> ReplayScoringProjectionReader:
        self.calls += 1
        return SQLiteReplayScoringProjectionRepository(self.database)


def _seed_two(tmp_path: Path) -> tuple[Path, ReplayScoringArtifact, ReplayScoringArtifact]:
    database = tmp_path / "replay_scoring.db"
    repository = SQLiteReplayScoringProjectionRepository(database)
    persist = PersistReplayScoringArtifact(repository)
    first = _build_two_by_two_artifact(
        dataset_version="1", target_draw_numbers=("300", "301")
    )
    second = _build_two_by_two_artifact(
        dataset_version="2", target_draw_numbers=("400", "401")
    )
    persist.execute(first)
    persist.execute(second)
    return database, first, second


def _path(sha: str, *, top_k: int | None = None) -> str:
    suffix = "" if top_k is None else f"&top_k={top_k}"
    return f"/api/v1/replay-rankings/optimal?scoring_artifact_sha256={sha}{suffix}"


def test_exact_persisted_artifact_is_ranked_once_without_storage_mutation(
    tmp_path: Path,
) -> None:
    database, first, second = _seed_two(tmp_path)
    factory = _Factory(database)
    client = TestClient(create_app(replay_scoring_projection_reader_factory=factory))
    before = _snapshot(database)

    response = client.get(_path(second.payload_sha256, top_k=1))

    assert response.status_code == 200
    payload = response.json()
    assert payload["source_scoring_artifact_payload_sha256"] == second.payload_sha256
    assert payload["source_scoring_artifact_payload_sha256"] != first.payload_sha256
    assert payload["dataset_version"] == "2"
    assert payload["top_k"] == 1
    assert payload["groups"][0]["candidates"][0]["members"][0]["strategy_id"] == "alpha"
    assert factory.calls == 1
    assert _snapshot(database) == before
    assert before.sidecars == ()


def test_absent_artifact_and_tampered_storage_map_to_sanitized_errors_read_only(
    tmp_path: Path,
) -> None:
    database, artifact, _ = _seed_two(tmp_path)
    factory = _Factory(database)
    client = TestClient(create_app(replay_scoring_projection_reader_factory=factory))

    missing = client.get(_path("0" * 64))
    assert missing.status_code == 404

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

    unavailable = client.get(_path(artifact.payload_sha256))

    assert unavailable.status_code == 503
    assert unavailable.json() == {
        "error_code": "REPLAY_RANKING_UNAVAILABLE",
        "message": "Replay portfolio ranking is unavailable.",
    }
    assert str(database) not in unavailable.text
    assert _snapshot(database) == before
    assert before.sidecars == ()


def test_mutating_methods_and_malformed_runtime_paths_remain_rejected(tmp_path: Path) -> None:
    database, artifact, _ = _seed_two(tmp_path)
    client = TestClient(
        create_app(replay_scoring_projection_reader_factory=_Factory(database))
    )
    path = _path(artifact.payload_sha256)

    assert client.post(path).status_code == 405
    assert client.put(path).status_code == 405
    assert client.delete(path).status_code == 405
    assert client.get("/api/v1/replay-rankings/latest").status_code == 404
    assert client.get("/api/v1/replay-rankings/optimal/latest").status_code == 404
