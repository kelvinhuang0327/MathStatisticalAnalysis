from __future__ import annotations

import hashlib
import sqlite3
from datetime import datetime
from pathlib import Path

import pytest
from tests.integration import test_b649_consensus_promotion as consensus_helpers

from lottolab.domain.research_live_forecast import (
    NATIVE_STREAM,
    NATIVE_STREAM_VERSION,
    ORIGINAL_FIELDS,
    LiveForecastInput,
    canonical_json,
    digest,
)
from lottolab.infrastructure.persistence import research_repository
from lottolab.infrastructure.persistence import research_schema as schema
from lottolab.infrastructure.persistence.research_repository import (
    ResearchConflictError,
    ResearchRepositoryError,
    SQLiteResearchRepository,
)

COMMIT_AT = "2026-11-17T12:02:00.000000Z"


def _repository(tmp_path: Path) -> tuple[SQLiteResearchRepository, schema.ResearchDataPaths]:
    data_directory = tmp_path / "research"
    paths = schema.ResearchDataPaths(
        data_directory=data_directory,
        database=data_directory / schema.RESEARCH_DATABASE_FILENAME,
    )
    return SQLiteResearchRepository(paths), paths


def _native_forecast(request_id: str) -> LiveForecastInput:
    schedule_hash = "a" * 64
    history_draws = [
        {
            "lottery_type": "BIG_LOTTO",
            "draw_number": "115000105",
            "draw_date": "2026-11-17",
            "main_numbers": [1, 2, 3, 4, 5, 6],
            "special_number": 7,
        }
    ]
    history_hash = digest(history_draws)
    target = {
        "lottery_type": "BIG_LOTTO",
        "target_draw_number": "115000106",
        "target_draw_date": "2026-11-19",
        "scheduled_at": "2026-11-19T20:30:00+08:00",
        "timezone": "Asia/Taipei",
        "data_cutoff": "115000105",
        "forecast_horizon": 1,
        "history_draw_count": len(history_draws),
        "causal_history_sha256": history_hash,
        "schedule_authority_sha256": schedule_hash,
    }
    rng = {
        "behavior": "DETERMINISTIC",
        "rng_source": "task-local fixture",
        "rng_state_rule": "no random state",
        "configuration": "fixed fixture",
        "prestate_dependency": "none",
        "seed": None,
    }
    strategies = [
        {
            "strategy_id": "task-local-fixture",
            "strategy_version": "1",
            "native_k": 5,
            "parameters": {},
            "rng_semantics": rng,
        }
    ]
    generation_config_sha256 = digest({"fixture_only": False, "strategies": strategies})
    catalog = [{"strategy_id": "task-local-fixture", "version": "1"}]
    catalog_sha256 = digest(catalog)
    producer_without_digest = {
        "schema_version": "native-producer-fixture-v1",
        "producer_id": "task-local-fixture",
        "producer_version": "1",
        "dependencies": [
            {
                "locator": "task-local://fixture-source",
                "source_sha256": "b" * 64,
                "load_bearing_role": "test fixture",
            }
        ],
    }
    producer = {
        **producer_without_digest,
        "digest": digest(producer_without_digest),
    }
    observations = [
        {
            "strategy_id": "task-local-fixture",
            "strategy_version": "1",
            "native_k": 5,
            "draw_number": "115000105",
            "draw_date": "2026-11-17",
            "causal_history_sha256": history_hash,
            "generation_config_sha256": generation_config_sha256,
            "status": "NOT_EXECUTED",
            "producer_fingerprint": producer["digest"],
            "tickets": [],
        }
    ]
    evidence_sha256 = digest(observations)
    buckets = []
    for native_k in (1, 2, 3, 5, 10, 20):
        status = (
            "UNAVAILABLE_NO_CANONICAL_NATIVE_K20_STRATEGY"
            if native_k == 20
            else "UNAVAILABLE_NO_FIXTURE_STRATEGY"
        )
        buckets.append(
            {
                "native_k": native_k,
                "status": status,
                "tickets": [],
                "display_tie_break": "NUMBER_ASC",
                "candidates": [],
            }
        )
    payload = {
        "bundle_id": "task-local-native-fixture",
        "fixture_only": False,
        "catalog": catalog,
        "generation_configs": strategies,
        "evidence_payload_sha256": evidence_sha256,
        "identity": {
            "lottery_type": target["lottery_type"],
            "target_draw_number": target["target_draw_number"],
            "target_draw_date": target["target_draw_date"],
            "schedule_authority_sha256": schedule_hash,
            "history_cutoff": target["data_cutoff"],
            "history_payload_sha256": history_hash,
            "producer_fingerprint": producer["digest"],
            "catalog_universe_sha256": catalog_sha256,
            "generation_config_sha256": generation_config_sha256,
        },
        "buckets": buckets,
    }
    payload_bytes = canonical_json(payload).encode()
    lineage_buckets = [
        {
            "native_k": bucket["native_k"],
            "status": bucket["status"],
            "tickets": bucket["tickets"],
            "selector_status": "EXECUTED",
            "selection_rule": NATIVE_STREAM_VERSION,
            "tie_break": bucket["display_tie_break"],
            "candidate_binding_sha256": digest(bucket["candidates"]),
            "evidence_payload_sha256": evidence_sha256,
            "constructor_status": "NOT_EXECUTED",
        }
        for bucket in buckets
    ]
    effective_rows = [
        {
            "strategy_id": "task-local-fixture",
            "strategy_version": "1",
            "native_k": 5,
            "parameters_json": canonical_json({}),
            "generation_config_sha256": digest(strategies[0]),
            "status": "NOT_EXECUTED",
        }
    ]
    rng_rows = [
        {
            "strategy_id": "task-local-fixture",
            "stage": "NATIVE_GENERATION",
            "status": "NOT_EXECUTED",
            "rng_semantics": rng,
            "seed_status": "NOT_APPLICABLE",
            "invocation_identity": request_id,
            "replicate": 1,
        }
    ]
    runtime_without_sha = {
        "python": {
            "implementation": "fixture-python",
            "version": "3.13",
            "executable": "/fixture/python",
            "executable_sha256": "c" * 64,
        },
        "os": "fixture-os",
        "architecture": "fixture-architecture",
        "dependencies": [
            {
                "name": "fixture-dependency",
                "locator": "task-local://fixture-dependency",
                "versions": {"fixture-dependency": "1"},
                "content_sha256": "d" * 64,
            }
        ],
    }
    original = {
        "producer_json": canonical_json(producer),
        "source_execution_json": canonical_json(
            {
                "repository": "task-local-fixture",
                "commit": "e" * 40,
                "tree": "f" * 40,
                "loaded_code_sha256": "1" * 64,
            }
        ),
        "runtime_manifest_json": canonical_json(
            {**runtime_without_sha, "sha256": digest(runtime_without_sha)}
        ),
        "history_snapshot_json": canonical_json(
            {
                "reference": "task-local://history",
                "draws": history_draws,
                "sha256": history_hash,
            }
        ),
        "catalog_json": canonical_json(
            {"strategies": catalog, "catalog_universe_sha256": catalog_sha256}
        ),
        "generation_configs_json": canonical_json(
            {
                "strategies": strategies,
                "generation_config_sha256": generation_config_sha256,
            }
        ),
        "effective_parameters_json": canonical_json(
            {
                "strategies": effective_rows,
                "sha256": digest({"strategies": effective_rows}),
            }
        ),
        "rng_semantics_json": canonical_json(
            {"stages": rng_rows, "reproducibility_boundary": "TASK_LOCAL_FIXTURE"}
        ),
        "ranking_evidence_json": canonical_json(
            {
                "objective": "OFFICIAL_ANY_PRIZE",
                "ranking_policy_version": NATIVE_STREAM_VERSION,
                "evaluation_window": "FULL",
                "observations": observations,
                "evidence_payload_sha256": evidence_sha256,
            }
        ),
        "ticket_lineage_json": canonical_json(
            {
                "buckets": lineage_buckets,
                "upstream_payload_sha256": hashlib.sha256(payload_bytes).hexdigest(),
            }
        ),
        "generation_started_at": "2026-11-17T12:00:00.000000Z",
        "generation_finished_at": "2026-11-17T12:01:00.000000Z",
    }
    assert set(original) == set(ORIGINAL_FIELDS)
    forecast = LiveForecastInput(
        request_id=request_id,
        request_sha256=digest({"request_id": request_id}),
        provenance_class="NATIVE_GENERATED",
        forecast_stream_id=NATIVE_STREAM,
        forecast_stream_version=NATIVE_STREAM_VERSION,
        target_json=canonical_json(target),
        payload_bytes=payload_bytes,
        source_locator="task-local://native-current-reader-fixture",
        original_execution_json=canonical_json(original),
        missing_provenance_json="{}",
    )
    forecast.validate()
    return forecast


def _seed_native(
    repository: SQLiteResearchRepository,
    request_id: str,
    *,
    eligible: bool = True,
):
    forecast = _native_forecast(request_id)
    committed = repository.commit_live_forecast(
        forecast,
        expected_current_version=0,
        current_eligible=lambda: eligible,
        clock=lambda: datetime.fromisoformat(COMMIT_AT.replace("Z", "+00:00")),
    )
    return forecast, committed


def _table_counts(paths: schema.ResearchDataPaths) -> dict[str, int]:
    with schema.open_database(paths, read_only=True) as connection:
        return {
            table: int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
            for table in schema.TABLE_NAMES
            if table != "research_schema_migrations"
        }


def _temporarily_disable_table_triggers(connection: sqlite3.Connection, table: str) -> list[str]:
    rows = connection.execute(
        "SELECT name, sql FROM sqlite_master WHERE type='trigger' AND tbl_name=?", (table,)
    ).fetchall()
    definitions: list[str] = []
    for name, sql in rows:
        assert isinstance(sql, str)
        escaped = str(name).replace('"', '""')
        connection.execute(f'DROP TRIGGER "{escaped}"')
        definitions.append(sql)
    connection.execute("PRAGMA ignore_check_constraints=ON")
    return definitions


def _restore_table_triggers(connection: sqlite3.Connection, definitions: list[str]) -> None:
    for definition in definitions:
        connection.execute(definition)


def test_native_current_roundtrip_timestamps_repeatability_and_read_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository, paths = _repository(tmp_path)
    assert schema.CURRENT_SCHEMA_VERSION == 5
    with schema.open_database(paths, read_only=True) as connection:
        assert connection.execute(
            "SELECT version, checksum FROM research_schema_migrations ORDER BY version DESC LIMIT 1"
        ).fetchone() == (5, schema.V5_MIGRATION_CHECKSUM)
        table_names = {
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
        }
        assert table_names == set(schema.V5_TABLE_NAMES)
        assert "research_live_forecast_versions" in table_names
        assert "research_live_forecast_current_pointer" in table_names
    forecast, committed = _seed_native(repository, "native-roundtrip")
    before = _table_counts(paths)
    observed_read_modes: list[bool] = []
    real_open_database = research_repository.open_database

    def observe_open(database_paths: schema.ResearchDataPaths, *, read_only: bool = False):
        observed_read_modes.append(read_only)
        return real_open_database(database_paths, read_only=read_only)

    monkeypatch.setattr(research_repository, "open_database", observe_open)
    first = repository.read_current_native(forecast.scope)
    second = repository.read_current_native(forecast.scope)
    after = _table_counts(paths)

    assert first is not None
    assert first == second
    assert first.version == committed.version
    assert first.run_id == committed.run_id
    assert first.scope == forecast.scope
    assert first.request_id == forecast.request_id
    assert first.request_sha256 == forecast.request_sha256
    assert first.forecast_stream_id == NATIVE_STREAM
    assert first.forecast_stream_version == NATIVE_STREAM_VERSION
    assert first.payload_bytes == forecast.payload_bytes
    assert first.payload_sha256 == forecast.payload_sha256
    assert first.committed_at == COMMIT_AT
    assert first.forecast.original["generation_started_at"] == "2026-11-17T12:00:00.000000Z"
    assert first.forecast.original["generation_finished_at"] == "2026-11-17T12:01:00.000000Z"
    assert before == after
    assert observed_read_modes == [True, True]


def test_missing_native_current_returns_none_without_history_fallback(tmp_path: Path) -> None:
    repository, _paths = _repository(tmp_path)
    forecast = _native_forecast("native-missing")
    assert repository.read_current_native(forecast.scope) is None


def test_history_version_without_current_pointer_returns_none(tmp_path: Path) -> None:
    repository, paths = _repository(tmp_path)
    forecast, committed = _seed_native(repository, "native-history-only", eligible=False)
    assert committed.pointer_advanced is False
    counts = _table_counts(paths)
    assert counts["research_live_forecast_versions"] == 1
    assert counts["research_live_forecast_current_pointer"] == 0
    assert repository.read_current_native(forecast.scope) is None


def test_consensus_rows_cannot_be_read_as_native_or_change_consensus_reader(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        consensus_helpers.promotion_module,
        "EXPECTED_OPERATION_ROOT",
        consensus_helpers._HERMETIC_OPERATION_ROOT,
    )
    monkeypatch.setattr(
        consensus_helpers.promotion_module,
        "EXPECTED_CANDIDATE_LOCATOR",
        consensus_helpers._HERMETIC_CANDIDATE_LOCATOR,
    )
    repository, _paths = _repository(tmp_path)
    candidate = consensus_helpers._candidate()
    request = consensus_helpers._request("native-reader-consensus-separation")
    forecast = candidate.build_forecast(request)
    committed = repository.commit_consensus_promotion(
        forecast,
        expected_current_version=0,
        current_eligible=lambda: True,
        clock=lambda: consensus_helpers._CLOCK,
    )
    current = repository.read_current_consensus(scope=forecast.scope)
    assert current is not None
    assert current.scope == forecast.scope
    assert current.version == committed.version
    assert current.run_id == committed.run_id
    assert current.payload_bytes == forecast.payload_bytes
    assert current.forecast.request_id == forecast.request_id
    assert current.committed_at is None
    with pytest.raises(ResearchRepositoryError, match="Native stream"):
        repository.read_current_native(forecast.scope)
    native_scope = (
        forecast.scope[0],
        forecast.scope[1],
        forecast.scope[2],
        NATIVE_STREAM,
        NATIVE_STREAM_VERSION,
    )
    assert repository.read_current_native(native_scope) is None


def test_wrong_native_stream_version_is_rejected(tmp_path: Path) -> None:
    repository, _paths = _repository(tmp_path)
    forecast = _native_forecast("native-wrong-version")
    wrong_scope = (*forecast.scope[:4], "B649_FULL_OFFICIAL_ANY_PRIZE_R0")
    with pytest.raises(ResearchRepositoryError, match="Native stream"):
        repository.read_current_native(wrong_scope)


def test_pointer_and_version_scope_mismatch_is_rejected(tmp_path: Path) -> None:
    repository, paths = _repository(tmp_path)
    forecast, committed = _seed_native(repository, "native-scope-mismatch")
    with sqlite3.connect(paths.database) as connection:
        triggers = _temporarily_disable_table_triggers(
            connection, "research_live_forecast_versions"
        )
        connection.execute(
            "UPDATE research_live_forecast_versions SET target_draw_date=? WHERE version=?",
            ("2026-11-20", committed.version),
        )
        _restore_table_triggers(connection, triggers)
    with pytest.raises(ResearchConflictError, match="no matching version"):
        repository.read_current_native(forecast.scope)


def test_payload_sha_mismatch_is_rejected(tmp_path: Path) -> None:
    repository, paths = _repository(tmp_path)
    forecast, committed = _seed_native(repository, "native-payload-mismatch")
    with sqlite3.connect(paths.database) as connection:
        triggers = _temporarily_disable_table_triggers(
            connection, "research_live_forecast_versions"
        )
        connection.execute(
            "UPDATE research_live_forecast_versions SET payload_bytes=? WHERE version=?",
            (b"{}", committed.version),
        )
        _restore_table_triggers(connection, triggers)
    with pytest.raises(ResearchConflictError, match="payload"):
        repository.read_current_native(forecast.scope)
