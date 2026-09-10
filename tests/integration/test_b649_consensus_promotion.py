"""Integration tests for atomic Authority B promotion and exact current reads."""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import subprocess
import sys
from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import pytest

from lottolab.domain.research_live_forecast import (
    CONSENSUS_MISSING,
    LEGACY_MISSING,
    LEGACY_SHA256,
    LEGACY_STREAM,
    ORIGINAL_FIELDS,
    canonical_json,
    object_json,
)
from lottolab.infrastructure.b649_consensus_promotion import (
    CONSENSUS_SCOPE,
    EXPECTED_CANDIDATE_LOCATOR,
    EXPECTED_CANDIDATE_SHA256,
    CanonicalConsensusEligibilityGate,
    CanonicalEligibilityResult,
    PromotionRequest,
    load_consensus_candidate,
    promote_consensus_candidate,
)
from lottolab.infrastructure.persistence import research_schema as schema
from lottolab.infrastructure.persistence.research_repository import (
    ResearchConflictError,
    SQLiteResearchRepository,
)

_SCHEDULE_HASH = "a" * 64
_CLOCK = datetime(2026, 9, 11, 12, 29, 59, tzinfo=UTC)


def _candidate():
    return load_consensus_candidate(EXPECTED_CANDIDATE_LOCATOR)


def _paths(tmp_path: Path) -> schema.ResearchDataPaths:
    directory = tmp_path / "research"
    return schema.ResearchDataPaths(directory, directory / schema.RESEARCH_DATABASE_FILENAME)


def _request(request_id: str, *, expected_current_version: int = 0) -> PromotionRequest:
    return PromotionRequest(
        request_id=request_id,
        request_sha256=hashlib.sha256(request_id.encode()).hexdigest(),
        expected_current_version=expected_current_version,
        schedule_authority_sha256=_SCHEDULE_HASH,
        authorization_evidence_reference="test://authorized-b649-promotion",
        promotion_executor_identity="integration-test-executor",
        execution_source_id="test://b649-promote-cli",
        execution_source_version="integration-v1",
        promotion_attempted_at=datetime(2026, 9, 10, 12, tzinfo=UTC),
        command_runtime_identity={
            "python": "fixture-python",
            "executable": "/fixture/python",
            "command": ["b649-promote", request_id],
        },
    )


class _CountingEligibleGate(CanonicalConsensusEligibilityGate):
    def __init__(self) -> None:
        self.calls = 0

    def check(
        self,
        candidate_target: Mapping[str, object] | None = None,
        *,
        now: datetime | None = None,
    ) -> CanonicalEligibilityResult:
        assert candidate_target is not None
        assert candidate_target.get("schedule_authority_sha256") == _SCHEDULE_HASH
        self.calls += 1
        checked_at = _CLOCK if now is None else now
        return CanonicalEligibilityResult(True, (), checked_at, _SCHEDULE_HASH, "ABSENT")


class _DriftingEligibleGate(CanonicalConsensusEligibilityGate):
    def __init__(self) -> None:
        self.calls = 0

    def check(
        self,
        candidate_target: Mapping[str, object] | None = None,
        *,
        now: datetime | None = None,
    ) -> CanonicalEligibilityResult:
        del candidate_target
        self.calls += 1
        return CanonicalEligibilityResult(
            True,
            (),
            _CLOCK if now is None else now,
            _SCHEDULE_HASH if self.calls == 1 else "b" * 64,
            "ABSENT",
        )


def _count_rows(repository: SQLiteResearchRepository) -> dict[str, int]:
    with schema.open_database(repository.paths, read_only=True) as connection:
        return {
            table: int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
            for table in schema.TABLE_NAMES
            if table != "research_schema_migrations"
        }


def test_promotion_is_byte_exact_append_only_idempotent_and_readable(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    repository = SQLiteResearchRepository(paths)
    candidate = _candidate()
    request = _request("promotion-one")
    gate = _CountingEligibleGate()

    first = promote_consensus_candidate(
        paths.database,
        candidate,
        request,
        eligibility_gate=gate,
        clock=lambda: _CLOCK,
    )
    current = repository.read_current_consensus()
    retry = promote_consensus_candidate(
        paths.database,
        candidate,
        request,
        eligibility_gate=gate,
        clock=lambda: _CLOCK,
    )

    assert first.pointer_advanced and not first.idempotent
    assert retry.idempotent and retry.run_id == first.run_id
    assert gate.calls == 2
    assert current is not None
    assert current.scope == CONSENSUS_SCOPE
    assert current.version == first.version
    assert current.run_id == first.run_id
    assert current.payload_bytes == candidate.candidate_bytes
    assert current.payload_sha256 == EXPECTED_CANDIDATE_SHA256
    assert current.forecast.source_locator == str(EXPECTED_CANDIDATE_LOCATOR)
    assert current.schedule_authority_sha256 == _SCHEDULE_HASH
    assert current.forecast.original == dict.fromkeys(ORIGINAL_FIELDS)
    assert current.forecast.missing_provenance_json == canonical_json(CONSENSUS_MISSING)
    imported = object_json(current.forecast.import_execution_json or "")
    assert imported["schedule_authority_sha256"] == _SCHEDULE_HASH
    assert imported["aggregation_execution"] == "NOT_PERFORMED"
    assert imported["native_generation"] == "NOT_PERFORMED"
    provenance = current.forecast.consensus_provenance
    assert provenance is not None
    assert provenance["candidate"] == {
        "locator": str(EXPECTED_CANDIDATE_LOCATOR),
        "sha256": EXPECTED_CANDIDATE_SHA256,
    }
    implementation = cast(dict[str, object], provenance["implementation"])
    assert implementation["commit"] == "573eb1aa519ccf4eb0c688bff0ca2b6c28183558"
    assert "canonical_aggregation" not in provenance
    assert "supersession" not in provenance
    assert _count_rows(repository)["research_live_forecast_versions"] == 1
    assert _count_rows(repository)["research_runs"] == 1
    assert _count_rows(repository)["research_artifacts"] == 1
    assert _count_rows(repository)["research_idempotency_keys"] == 1


def test_failed_consensus_attempt_rolls_back_and_same_request_is_reusable(
    tmp_path: Path,
) -> None:
    repository = SQLiteResearchRepository(_paths(tmp_path))
    forecast = _candidate().build_forecast(_request("reusable"))
    calls = 0

    def failing_gate() -> bool:
        nonlocal calls
        calls += 1
        return calls == 1

    with pytest.raises(ResearchConflictError):
        repository.commit_consensus_promotion(
            forecast,
            expected_current_version=0,
            current_eligible=failing_gate,
            clock=lambda: _CLOCK,
        )
    assert calls == 2
    assert all(value == 0 for value in _count_rows(repository).values())

    result = repository.commit_consensus_promotion(
        forecast,
        expected_current_version=0,
        current_eligible=lambda: True,
        clock=lambda: _CLOCK,
    )
    assert result.pointer_advanced and not result.idempotent
    assert _count_rows(repository)["research_idempotency_keys"] == 1


def test_schedule_hash_drift_between_gate_checks_rolls_back(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    repository = SQLiteResearchRepository(paths)
    candidate = _candidate()
    request = _request("schedule-drift")
    gate = _DriftingEligibleGate()

    with pytest.raises(ResearchConflictError):
        promote_consensus_candidate(
            paths.database,
            candidate,
            request,
            eligibility_gate=gate,
            clock=lambda: _CLOCK,
        )
    assert gate.calls == 2
    assert all(value == 0 for value in _count_rows(repository).values())

    stable = _CountingEligibleGate()
    result = promote_consensus_candidate(
        paths.database,
        candidate,
        request,
        eligibility_gate=stable,
        clock=lambda: _CLOCK,
    )
    assert result.pointer_advanced and not result.idempotent


def test_cas_loser_and_reused_request_conflicts_leave_no_residue(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    first_repository = SQLiteResearchRepository(paths)
    candidate = _candidate()
    first_forecast = candidate.build_forecast(_request("cas-first"))
    second_forecast = candidate.build_forecast(_request("cas-second"))

    def commit(repo: SQLiteResearchRepository, forecast: object) -> object:
        assert hasattr(forecast, "request_id")
        return repo.commit_consensus_promotion(
            forecast,  # type: ignore[arg-type]
            expected_current_version=0,
            current_eligible=lambda: True,
            clock=lambda: _CLOCK,
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = (
            executor.submit(
                commit,
                SQLiteResearchRepository(paths, initialize=False),
                first_forecast,
            ),
            executor.submit(
                commit,
                SQLiteResearchRepository(paths, initialize=False),
                second_forecast,
            ),
        )
        outcomes: list[object] = []
        for future in futures:
            try:
                outcomes.append(future.result())
            except Exception as exc:
                outcomes.append(exc)

    assert sum(not isinstance(value, Exception) for value in outcomes) == 1
    assert sum(isinstance(value, ResearchConflictError) for value in outcomes) == 1
    counts = _count_rows(first_repository)
    assert counts["research_live_forecast_versions"] == 1
    assert counts["research_runs"] == 1
    assert counts["research_artifacts"] == 1
    assert counts["research_idempotency_keys"] == 1

    with schema.open_database(first_repository.paths, read_only=True) as connection:
        winner_request_id = str(
            connection.execute("SELECT request_id FROM research_live_forecast_versions").fetchone()[
                0
            ]
        )
    winner_forecast = (
        first_forecast if winner_request_id == first_forecast.request_id else second_forecast
    )
    reused = replace(winner_forecast, request_sha256="f" * 64)
    with pytest.raises(ResearchConflictError):
        first_repository.commit_consensus_promotion(
            reused,
            expected_current_version=1,
            current_eligible=lambda: pytest.fail("request conflict must fail before gate"),
            clock=lambda: _CLOCK,
        )
    assert _count_rows(first_repository)["research_live_forecast_versions"] == 1


def test_schema_v3_to_v4_preserves_live_payload_and_current_pointer(tmp_path: Path) -> None:
    paths = _create_v3_with_legacy_live_row(tmp_path)
    with sqlite3.connect(paths.database) as connection:
        before_run = connection.execute(
            "SELECT id, imported_from_artifact_id, provenance_class FROM research_runs"
        ).fetchall()
        before_version = connection.execute(
            "SELECT version, run_id, request_id, payload_bytes, payload_sha256, "
            "source_payload_sha256 FROM research_live_forecast_versions"
        ).fetchall()
        before_pointer = connection.execute(
            "SELECT * FROM research_live_forecast_current_pointer"
        ).fetchall()

    schema.initialize_schema(paths)

    with schema.open_database(paths, read_only=True) as connection:
        assert (
            connection.execute(
                "SELECT id, imported_from_artifact_id, provenance_class FROM research_runs"
            ).fetchall()
            == before_run
        )
        assert connection.execute(
            "SELECT version, run_id, request_id, payload_bytes, payload_sha256, "
            "source_payload_sha256, consensus_provenance_json FROM "
            "research_live_forecast_versions"
        ).fetchall() == [(*before_version[0], None)]
        assert (
            connection.execute("SELECT * FROM research_live_forecast_current_pointer").fetchall()
            == before_pointer
        )
        assert connection.execute(
            "SELECT version, name, checksum FROM research_schema_migrations ORDER BY version"
        ).fetchall() == [
            (2, schema.MIGRATION_NAME, schema.MIGRATION_CHECKSUM),
            (3, schema.V3_MIGRATION_NAME, schema.V3_MIGRATION_CHECKSUM),
            (4, schema.V4_MIGRATION_NAME, schema.V4_MIGRATION_CHECKSUM),
        ]


def test_schema_v3_to_v4_failure_rolls_back_every_legacy_row(tmp_path: Path) -> None:
    paths = _create_v3_with_legacy_live_row(tmp_path)
    before = _v3_rows(paths)
    original = schema.V4_MIGRATION_STATEMENTS
    bad_statement = "SELECT missing_b649_v4_migration_function()"
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(
        schema,
        "V4_MIGRATION_STATEMENTS",
        (*original[:4], bad_statement, *original[4:]),
    )
    try:
        with pytest.raises(schema.ResearchSchemaError):
            schema.initialize_schema(paths)
    finally:
        monkeypatch.undo()
    assert _v3_rows(paths) == before
    with sqlite3.connect(paths.database) as connection:
        assert connection.execute(
            "SELECT version FROM research_schema_migrations ORDER BY version"
        ).fetchall() == [(2,), (3,)]
        assert (
            connection.execute(
                "SELECT name FROM sqlite_schema WHERE type='table' AND name LIKE 'research_v4_%'"
            ).fetchall()
            == []
        )


def test_cli_preflight_and_blocked_promote_are_read_only_and_current_is_exact(
    tmp_path: Path,
) -> None:
    paths = _paths(tmp_path)
    SQLiteResearchRepository(paths)
    draw_database = tmp_path / "draw" / "lottolab.db"
    common = [
        "--database",
        str(paths.database),
        "--draw-database",
        str(draw_database),
        "--candidate",
        str(EXPECTED_CANDIDATE_LOCATOR),
        "--candidate-sha256",
        EXPECTED_CANDIDATE_SHA256,
        "--expected-current-version",
        "0",
        "--request-id",
        "cli-request",
        "--request-sha256",
        "1" * 64,
        "--execution-source-id",
        "test://cli",
        "--execution-source-version",
        "cli-v1",
    ]
    before_bytes = paths.database.read_bytes()
    before_mtime = paths.database.stat().st_mtime_ns
    preflight = _run_cli("preflight", *common)
    assert preflight.returncode == 1
    preflight_payload = json.loads(preflight.stdout)
    assert preflight_payload["status"] == "NOT_READY"
    assert "SCHEDULE_HASH_NOT_BOUND" in preflight_payload["blockers"]
    assert paths.database.read_bytes() == before_bytes
    assert paths.database.stat().st_mtime_ns == before_mtime

    promote = _run_cli(
        "promote",
        *common,
        "--schedule-authority-sha256",
        _SCHEDULE_HASH,
        "--authorization-reference",
        "test://authorization",
        "--executor-identity",
        "cli-test-executor",
    )
    assert promote.returncode == 1
    assert json.loads(promote.stdout)["status"] == "NOT_READY"
    assert (
        _count_rows(SQLiteResearchRepository(paths, initialize=False))[
            "research_live_forecast_versions"
        ]
        == 0
    )

    current = _run_cli(
        "current",
        "--database",
        str(paths.database),
        "--draw-database",
        str(draw_database),
    )
    assert current.returncode == 0
    current_payload = json.loads(current.stdout)
    assert current_payload["status"] == "EMPTY"
    assert current_payload["current"] is None


def test_cli_rejects_descriptive_candidate_without_touching_research_store(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    SQLiteResearchRepository(paths)
    old_candidate = Path(
        "/Users/kelvin/VibeCoding-WorkSpace/.task-data/"
        "B649_115000087_PR283_CANONICAL_SUCCESSOR_CANDIDATE_R1/candidate/"
        "successor_candidate_payload.json"
    )
    before = paths.database.read_bytes()
    result = _run_cli(
        "preflight",
        "--database",
        str(paths.database),
        "--candidate",
        str(old_candidate),
        "--candidate-sha256",
        "d21444820905d49aefb84bfb405709cfd95b95a9484ef525244f9e1c1d40ea3e",
        "--expected-current-version",
        "0",
        "--request-id",
        "old-candidate",
        "--request-sha256",
        "2" * 64,
        "--execution-source-id",
        "test://cli",
        "--execution-source-version",
        "cli-v1",
    )
    assert result.returncode == 1
    assert "Authority B artifact" in json.loads(result.stdout)["blockers"][0]
    assert paths.database.read_bytes() == before


def _create_v3_with_legacy_live_row(tmp_path: Path) -> schema.ResearchDataPaths:
    paths = _paths(tmp_path)
    paths.data_directory.mkdir(mode=0o700)
    paths.data_directory.chmod(0o700)
    descriptor = os.open(paths.database, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.close(descriptor)
    paths.database.chmod(0o600)
    payload = b"preserved-v3-payload-bytes"
    target = canonical_json(
        {
            "lottery_type": "BIG_LOTTO",
            "target_draw_number": "115000087",
            "target_draw_date": "2026-09-11",
            "scheduled_at": "2026-09-11T20:30:00+08:00",
            "timezone": "Asia/Taipei",
            "data_cutoff": "115000086",
            "forecast_horizon": 1,
            "history_draw_count": 2168,
            "causal_history_sha256": "2" * 64,
        }
    )
    missing = canonical_json(LEGACY_MISSING)
    envelope = canonical_json({"fixture": "v3"})
    live_columns = (
        "version, run_id, request_id, request_sha256, lottery_type, target_draw_number, "
        "target_draw_date, forecast_stream_id, forecast_stream_version, target_json, "
        "provenance_class, original_execution_provenance_status, payload_bytes, payload_sha256, "
        "source_payload_sha256, source_locator, bundle_id, "
        + ", ".join(ORIGINAL_FIELDS)
        + ", missing_provenance_json, import_execution_json, committed_at, "
        "expected_current_version, pointer_advanced, provenance_envelope_json, "
        "provenance_envelope_sha256"
    )
    live_values = (
        1,
        "v3-live-run",
        "v3-live-request",
        "3" * 64,
        "BIG_LOTTO",
        "115000087",
        "2026-09-11",
        LEGACY_STREAM,
        LEGACY_STREAM,
        target,
        "LEGACY_MATERIALIZED",
        "UNKNOWN_LEGACY_PROVENANCE",
        payload,
        LEGACY_SHA256,
        LEGACY_SHA256,
        "fixture://v3-payload",
        None,
        *([None] * len(ORIGINAL_FIELDS)),
        missing,
        canonical_json(
            {
                "imported_at": "2026-09-10T00:00:00Z",
                "producer_id": "v3-importer",
                "source_execution": {},
                "runtime_manifest": {},
            }
        ),
        "2026-09-10T00:00:01Z",
        0,
        1,
        envelope,
        "4" * 64,
    )
    with sqlite3.connect(paths.database) as connection:
        for statement in schema.MIGRATION_STATEMENTS:
            connection.execute(statement)
        connection.execute(
            "INSERT INTO research_schema_migrations VALUES (?, ?, ?, ?)",
            (2, schema.MIGRATION_NAME, schema.MIGRATION_CHECKSUM, "2026-09-10T00:00:00Z"),
        )
        for statement in schema.V3_MIGRATION_STATEMENTS:
            connection.execute(statement)
        connection.execute(
            "INSERT INTO research_schema_migrations VALUES (?, ?, ?, ?)",
            (3, schema.V3_MIGRATION_NAME, schema.V3_MIGRATION_CHECKSUM, "2026-09-10T00:00:01Z"),
        )
        connection.execute(
            "INSERT INTO research_artifacts VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                "v3-artifact",
                "LIVE_FORECAST_PAYLOAD",
                "fixture://v3-payload",
                "application/octet-stream",
                len(payload),
                LEGACY_SHA256,
                "2026-09-10T00:00:00Z",
            ),
        )
        connection.execute(
            "INSERT INTO research_runs (id, run_kind, rule_contract_id, input_dataset_identity, "
            "input_dataset_sha256, status, progress_cursor, expected_target_count, "
            "supersedes_run_id, derived_from_run_id, imported_from_artifact_id, producer_identity, "
            "execution_code_version, source_commit_oid, started_at, created_at, provenance_class) "
            "VALUES (?, 'LIVE_PREDICTION', NULL, ?, ?, 'COMPLETED', NULL, 1, NULL, NULL, ?, "
            "NULL, NULL, NULL, NULL, ?, 'LEGACY_MATERIALIZED')",
            (
                "v3-live-run",
                "causal-history:" + "2" * 64,
                "1" * 64,
                "v3-artifact",
                "2026-09-10T00:00:00Z",
            ),
        )
        connection.execute(
            f"INSERT INTO research_live_forecast_versions ({live_columns}) VALUES "
            f"({','.join('?' for _ in live_values)})",
            live_values,
        )
        connection.execute(
            "INSERT INTO research_live_forecast_current_pointer VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                "BIG_LOTTO",
                "115000087",
                "2026-09-11",
                LEGACY_STREAM,
                LEGACY_STREAM,
                1,
                "v3-live-run",
            ),
        )
    return paths


def _v3_rows(paths: schema.ResearchDataPaths) -> tuple[object, ...]:
    with sqlite3.connect(paths.database) as connection:
        return (
            tuple(connection.execute("SELECT * FROM research_runs").fetchone()),
            tuple(connection.execute("SELECT * FROM research_live_forecast_versions").fetchone()),
            tuple(
                connection.execute(
                    "SELECT * FROM research_live_forecast_current_pointer"
                ).fetchone()
            ),
            tuple(connection.execute("SELECT * FROM research_schema_migrations").fetchone()),
        )


def _run_cli(*arguments: str) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["PYTHONPATH"] = "src"
    return subprocess.run(
        [sys.executable, "tools/b649_promote_consensus_candidate.py", *arguments],
        cwd=Path(__file__).resolve().parents[2],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
