"""Real SQLite migration, rollback and live-version visibility probes."""

from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import replace
from pathlib import Path

import pytest

from lottolab.domain.research_live_forecast import (
    LEGACY_IMPORT_KEY,
    LEGACY_MISSING,
    LEGACY_STREAM,
    ORIGINAL_FIELDS,
    LiveForecastInput,
    canonical_json,
    digest,
)
from lottolab.infrastructure.persistence import research_schema as schema
from lottolab.infrastructure.persistence.research_repository import (
    ResearchConflictError,
    SQLiteResearchRepository,
)


def paths_at(root: Path) -> schema.ResearchDataPaths:
    directory = root / "research"
    return schema.ResearchDataPaths(directory, directory / schema.RESEARCH_DATABASE_FILENAME)


def create_v2(paths: schema.ResearchDataPaths) -> None:
    paths.data_directory.mkdir(mode=0o700)
    paths.database.touch(mode=0o600)
    with sqlite3.connect(paths.database) as connection:
        for statement in schema.MIGRATION_STATEMENTS:
            connection.execute(statement)
        connection.execute(
            "INSERT INTO research_schema_migrations VALUES (2, ?, ?, ?)",
            (schema.MIGRATION_NAME, schema.MIGRATION_CHECKSUM, "original-time"),
        )
        connection.execute(
            "INSERT INTO research_rule_contracts VALUES (?, ?, ?, ?, ?, ?)",
            ("rule", "BIG_LOTTO", "v2", "{}", "a" * 64, "original-time"),
        )
        for name, parent in (("old", None), ("successor", "old")):
            connection.execute(
                "INSERT INTO research_runs VALUES (?, 'LIVE_PREDICTION', 'rule', 'history', ?, "
                "'COMPLETED', NULL, 0, ?, NULL, NULL, 'original-producer', 'v2', "
                "'original-commit', 'original-start', 'original-time')",
                (name, "b" * 64, parent),
            )
        connection.execute(
            "INSERT INTO research_run_current_pointer VALUES (?, ?, ?)",
            ("v2-current", "successor", "original-time"),
        )


def rows_and_schema(
    paths: schema.ResearchDataPaths,
) -> tuple[dict[str, list[tuple[object, ...]]], list[tuple[object, ...]]]:
    with sqlite3.connect(paths.database) as connection:
        rows = {
            table: connection.execute(f"SELECT * FROM {table}").fetchall()
            for table in schema.V2_TABLE_NAMES
        }
        objects = connection.execute("SELECT name,sql FROM sqlite_schema ORDER BY name").fetchall()
    return rows, objects


def test_v2_rows_and_migration_checksum_are_preserved(tmp_path: Path) -> None:
    paths = paths_at(tmp_path)
    create_v2(paths)
    before, _ = rows_and_schema(paths)
    assert schema.MIGRATION_CHECKSUM == (
        "04a5fc31dfb35253964620746e5987d07dd2cf8f5329dd698aad7ef33dc51f16"
    )
    schema.initialize_schema(paths)
    with schema.open_database(paths, read_only=True) as connection:
        for table, expected in before.items():
            actual = connection.execute(f"SELECT * FROM {table}").fetchall()
            if table == "research_runs":
                actual = [row[:-1] for row in actual]
            assert actual[: len(expected)] == expected
        assert connection.execute("SELECT provenance_class FROM research_runs").fetchall() == [
            (None,),
            (None,),
        ]
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        assert connection.execute(
            "SELECT COUNT(*) FROM research_live_forecast_versions"
        ).fetchone() == (0,)
    first_bytes = paths.database.read_bytes()
    schema.initialize_schema(paths)
    assert paths.database.read_bytes() == first_bytes


@pytest.mark.parametrize("failure_after", [1, 3, 7, len(schema.V3_MIGRATION_STATEMENTS)])
def test_migration_failure_rolls_back_schema_rows_and_pointer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure_after: int,
) -> None:
    paths = paths_at(tmp_path)
    create_v2(paths)
    before = rows_and_schema(paths)
    original = schema.V3_MIGRATION_STATEMENTS
    monkeypatch.setattr(
        schema,
        "V3_MIGRATION_STATEMENTS",
        (
            *original[:failure_after],
            "SELECT missing_migration_function()",
            *original[failure_after:],
        ),
    )
    with pytest.raises(schema.ResearchSchemaError):
        schema.initialize_schema(paths)
    assert rows_and_schema(paths) == before
    with sqlite3.connect(paths.database) as connection:
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []


@pytest.fixture
def legacy_input() -> LiveForecastInput:
    # Integration input is supplied explicitly; tests never discover owner files.
    locator = os.environ.get("LOTTOLAB_TEST_LEGACY_PAYLOAD")
    if locator is None:
        pytest.skip("pinned owner-authorized legacy artifact not supplied")
    payload = Path(locator).read_bytes()
    data = json.loads(payload)
    target = {
        "lottery_type": "BIG_LOTTO",
        "target_draw_number": "115000087",
        "target_draw_date": "2026-09-11",
        "scheduled_at": "2026-09-11T20:30:00+08:00",
        "timezone": "Asia/Taipei",
        "data_cutoff": "115000086",
        "forecast_horizon": 1,
        "history_draw_count": 2168,
        "causal_history_sha256": data["causal_history_sha256"],
    }
    return LiveForecastInput(
        LEGACY_IMPORT_KEY,
        digest({"legacy": data["source_task"]}),
        "LEGACY_MATERIALIZED",
        LEGACY_STREAM,
        LEGACY_STREAM,
        canonical_json(target),
        payload,
        locator,
        canonical_json(dict.fromkeys(ORIGINAL_FIELDS)),
        canonical_json(LEGACY_MISSING),
        canonical_json(
            {
                "imported_at": "2026-09-09T01:00:00Z",
                "producer_id": "test-importer",
                "source_execution": {"fixture": True},
                "runtime_manifest": {"fixture": True},
            }
        ),
    )


def test_legacy_import_preserves_bytes_nulls_and_retry_pointer(
    tmp_path: Path,
    legacy_input: LiveForecastInput,
) -> None:
    repo = SQLiteResearchRepository(paths_at(tmp_path))
    first = repo.commit_live_forecast(
        legacy_input, expected_current_version=0, current_eligible=lambda: True
    )
    assert first.pointer_advanced
    retry = repo.commit_live_forecast(
        legacy_input,
        expected_current_version=0,
        current_eligible=lambda: pytest.fail("retry rechecked validity"),
    )
    assert retry.idempotent and retry.run_id == first.run_id
    assert repo.live_current_version(legacy_input.scope) == first.version
    with schema.open_database(repo.paths, read_only=True) as c:
        assert c.execute("SELECT COUNT(*) FROM research_runs").fetchone() == (1,)
        assert c.execute(
            "SELECT payload_bytes FROM research_live_forecast_versions"
        ).fetchone() == (legacy_input.payload_bytes,)
        assert c.execute(
            f"SELECT {', '.join(ORIGINAL_FIELDS)} FROM research_live_forecast_versions"
        ).fetchone() == ((None,) * len(ORIGINAL_FIELDS))
        assert c.execute(
            "SELECT producer_identity, source_commit_oid, started_at, rule_contract_id "
            "FROM research_runs"
        ).fetchone() == (
            None,
            None,
            None,
            None,
        )
        assert c.execute("SELECT COUNT(*) FROM research_rule_contracts").fetchone() == (0,)


def test_final_gate_failure_rolls_back_every_row_and_is_invisible_before_commit(
    tmp_path: Path,
    legacy_input: LiveForecastInput,
) -> None:
    repo = SQLiteResearchRepository(paths_at(tmp_path))
    calls = 0

    def gate() -> bool:
        nonlocal calls
        calls += 1
        with sqlite3.connect(repo.paths.database.as_uri() + "?mode=ro", uri=True) as reader:
            for table in (
                "research_runs",
                "research_live_forecast_versions",
                "research_live_forecast_current_pointer",
                "research_artifacts",
            ):
                assert reader.execute(f"SELECT COUNT(*) FROM {table}").fetchone() == (0,)
        return calls == 1

    with pytest.raises(ResearchConflictError):
        repo.commit_live_forecast(legacy_input, expected_current_version=0, current_eligible=gate)
    with schema.open_database(repo.paths, read_only=True) as reader:
        for table in schema.TABLE_NAMES:
            if table != "research_schema_migrations":
                assert reader.execute(f"SELECT COUNT(*) FROM {table}").fetchone() == (0,)
    assert calls == 2


def test_expired_legacy_is_history_only_and_retry_does_not_initialize_pointer(
    tmp_path: Path,
    legacy_input: LiveForecastInput,
) -> None:
    repo = SQLiteResearchRepository(paths_at(tmp_path))
    first = repo.commit_live_forecast(
        legacy_input, expected_current_version=0, current_eligible=lambda: False
    )
    retry = repo.commit_live_forecast(
        legacy_input, expected_current_version=0, current_eligible=lambda: True
    )
    assert not first.pointer_advanced and retry.idempotent
    assert repo.live_current_version(legacy_input.scope) == 0


def test_legacy_cannot_claim_native_or_fill_original_commit(
    legacy_input: LiveForecastInput,
) -> None:
    original = legacy_input.original
    original["source_execution_json"] = canonical_json({"commit": "a" * 40})
    with pytest.raises(ValueError, match="NULL provenance"):
        replace(legacy_input, original_execution_json=canonical_json(original)).validate()
    with pytest.raises(ValueError):
        replace(legacy_input, provenance_class="NATIVE_GENERATED").validate()


def test_authorized_canonical_copy_preserves_every_v2_value(tmp_path: Path) -> None:
    locator = os.environ.get("LOTTOLAB_TEST_CANONICAL_RESEARCH_DB")
    if locator is None:
        pytest.skip("canonical copy verification requires an explicit authorized locator")
    source_path = Path(locator)
    paths = paths_at(tmp_path)
    paths.data_directory.mkdir(mode=0o700)
    paths.database.touch(mode=0o600)
    # The original remains read-only. EXCEPT returns only equality booleans;
    # no stored draw outcome values are returned to the test or its output.
    with sqlite3.connect(source_path.as_uri() + "?mode=ro", uri=True) as source:
        source.execute("BEGIN")
        assert source.execute("SELECT MAX(version) FROM research_schema_migrations").fetchone() == (
            2,
        )
        with sqlite3.connect(paths.database) as target:
            source.backup(target)
        schema.initialize_schema(paths)
        with schema.open_database(paths, read_only=True) as migrated:
            migrated.execute("ATTACH DATABASE ? AS prior", (source_path.as_uri() + "?mode=ro",))
            for table in schema.V2_TABLE_NAMES:
                columns = ",".join(
                    '"' + row[1] + '"'
                    for row in migrated.execute(f"PRAGMA prior.table_info({table})")
                )
                predicate = " WHERE version = 2" if table == "research_schema_migrations" else ""
                old = f"SELECT {columns} FROM prior.{table}{predicate}"
                new = f"SELECT {columns} FROM main.{table}{predicate}"
                assert migrated.execute(f"SELECT EXISTS({old} EXCEPT {new})").fetchone() == (0,)
                assert migrated.execute(f"SELECT EXISTS({new} EXCEPT {old})").fetchone() == (0,)
            assert migrated.execute("PRAGMA foreign_key_check").fetchall() == []
