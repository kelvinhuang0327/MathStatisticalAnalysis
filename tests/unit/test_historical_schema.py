"""Schema creation/verification tests for the historical-results projection (BLHQ R1)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from lottolab.infrastructure.persistence import historical_schema as schema_module
from lottolab.infrastructure.persistence.historical_schema import (
    CURRENT_SCHEMA_VERSION,
    MIGRATION_CHECKSUM,
    MIGRATION_NAME,
    MIGRATION_STATEMENTS,
    TABLE_NAMES,
    HistoricalSchemaChecksumError,
    HistoricalSchemaMigrationError,
    initialize_schema,
    open_database,
    verify_schema_read_only,
)


def _create_populated_v1_database(database: Path) -> None:
    with sqlite3.connect(database) as connection:
        for statement in MIGRATION_STATEMENTS:
            connection.execute(statement)
        connection.execute(
            "INSERT INTO historical_schema_migrations VALUES (1, ?, ?, ?)",
            (MIGRATION_NAME, MIGRATION_CHECKSUM, "2026-07-20T00:00:00.000000Z"),
        )
        connection.execute(
            """
            INSERT INTO historical_result_run VALUES (
                'run-1', ?, ?, '1.0.0', 'SYNTHETIC_TEST_ONLY', 'repo', ?, ?,
                'dataset', ?, NULL, 'BIG_LOTTO', 'COMPLETED', ?, ?, NULL, NULL, ?
            )
            """,
            (
                "1" * 64,
                "2" * 64,
                "3" * 40,
                "4" * 64,
                "5" * 64,
                "2026-01-01T00:00:00.000000Z",
                "2026-01-01T00:01:00.000000Z",
                "2026-01-01T00:00:00.000000Z",
            ),
        )
        for run_id, status, completed_at, error_code in (
            ("run-failed", "FAILED", "2026-01-01T00:02:00.000000Z", "FAILED_CODE"),
            ("run-progress", "IN_PROGRESS", None, None),
        ):
            connection.execute(
                """
                INSERT INTO historical_result_run VALUES (
                    ?, ?, ?, '1.0.0', 'SYNTHETIC_TEST_ONLY', 'repo', ?, ?,
                    ?, ?, NULL, 'BIG_LOTTO', ?, ?, ?, ?, NULL, ?
                )
                """,
                (
                    run_id,
                    run_id.ljust(64, "1")[:64],
                    run_id.ljust(64, "2")[:64],
                    "3" * 40,
                    "4" * 64,
                    f"dataset-{run_id}",
                    "5" * 64,
                    status,
                    "2026-01-01T00:00:00.000000Z",
                    completed_at,
                    error_code,
                    "2026-01-01T00:00:00.000000Z",
                ),
            )
        connection.execute(
            """
            INSERT INTO historical_strategy_snapshot VALUES (
                'strategy-1', 'run-1', 's', 's', 'v1', 1, 'REAL', 'ONLINE',
                NULL, NULL, 1, ?, ?
            )
            """,
            ("6" * 64, "2026-01-01T00:00:00.000000Z"),
        )
        for draw_id, draw_number in ((1, "100"), (2, "105")):
            connection.execute(
                """
                INSERT INTO historical_draw_snapshot VALUES (
                    ?, 'run-1', 'BIG_LOTTO', ?, '2026-01-01', '[1,2,3,4,5,6]',
                    '[7]', ?, ?
                )
                """,
                (
                    draw_id,
                    draw_number,
                    str(draw_id) * 64,
                    "2026-01-01T00:00:00.000000Z",
                ),
            )
        connection.execute(
            """
            INSERT INTO historical_portfolio VALUES (
                'portfolio-1', 'run-1', 'strategy-1', 2, 1, 'constructor',
                ?, ?, ?, NULL, ?
            )
            """,
            (
                "7" * 64,
                "8" * 64,
                "9" * 64,
                "2026-01-01T00:00:00.000000Z",
            ),
        )
        connection.execute(
            """
            INSERT INTO historical_ticket VALUES (
                1, 'portfolio-1', 1, '[1,2,3,4,5,6]', '[7]', 6, 1, ?, NULL, NULL
            )
            """,
            ("a" * 64,),
        )
        connection.execute(
            """
            INSERT INTO historical_count_summary VALUES (
                1, 'run-1', 'strategy-1', 10, 1, 1, 1, ?
            )
            """,
            ("2026-01-01T00:00:00.000000Z",),
        )
        connection.commit()


def _application_rows(database: Path) -> dict[str, list[tuple[object, ...]]]:
    with sqlite3.connect(database) as connection:
        return {
            table: connection.execute(f"SELECT * FROM {table} ORDER BY rowid").fetchall()
            for table in TABLE_NAMES
            if table != "historical_schema_migrations"
        }


def test_verify_schema_read_only_returns_false_for_absent_database(tmp_path: Path) -> None:
    database = tmp_path / "historical.db"
    assert verify_schema_read_only(database) is False
    assert not database.exists()


def test_initialize_schema_creates_all_six_domain_tables_plus_migrations(tmp_path: Path) -> None:
    database = tmp_path / "historical.db"
    initialize_schema(database)
    with open_database(database, read_only=True) as connection:
        names = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
        }
    assert names == set(TABLE_NAMES)
    domain_tables = {
        "historical_result_run",
        "historical_strategy_snapshot",
        "historical_draw_snapshot",
        "historical_portfolio",
        "historical_ticket",
        "historical_count_summary",
    }
    assert domain_tables <= names
    with sqlite3.connect(database) as connection:
        assert connection.execute(
            "SELECT version FROM historical_schema_migrations ORDER BY version"
        ).fetchall() == [(1,), (2,)]


def test_initialize_schema_is_idempotent_and_byte_stable(tmp_path: Path) -> None:
    database = tmp_path / "historical.db"
    initialize_schema(database)
    first_bytes = database.read_bytes()
    initialize_schema(database)
    second_bytes = database.read_bytes()
    assert first_bytes == second_bytes
    assert verify_schema_read_only(database) is True


def test_foreign_keys_are_enforced(tmp_path: Path) -> None:
    database = tmp_path / "historical.db"
    initialize_schema(database)
    with open_database(database) as connection:
        assert connection.execute("PRAGMA foreign_keys").fetchone() == (1,)
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO historical_strategy_snapshot (
                    id, run_id, strategy_id, effective_strategy_id, strategy_version,
                    replicate, identity_kind, governance_status, nested_prefix_supported,
                    descriptor_sha256, created_at
                ) VALUES ('s1', 'missing-run', 'x', 'x', 'v1', 1, 'REAL', 'UNKNOWN', 0, ?, 'now')
                """,
                ("0" * 64,),
            )


def test_checksum_drift_is_rejected(tmp_path: Path) -> None:
    database = tmp_path / "historical.db"
    initialize_schema(database)
    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE historical_schema_migrations SET checksum = 'deadbeef' WHERE version = ?",
            (CURRENT_SCHEMA_VERSION,),
        )
        connection.commit()
    with pytest.raises(HistoricalSchemaChecksumError):
        verify_schema_read_only(database)


def test_schema_object_text_drift_is_rejected(tmp_path: Path) -> None:
    database = tmp_path / "historical.db"
    initialize_schema(database)
    with sqlite3.connect(database) as connection:
        connection.execute("DROP INDEX idx_historical_result_run_history")
        connection.commit()
    with pytest.raises(HistoricalSchemaMigrationError):
        verify_schema_read_only(database)


def test_open_database_on_absent_database_fails_closed(tmp_path: Path) -> None:
    database = tmp_path / "missing.db"
    with pytest.raises(HistoricalSchemaMigrationError), open_database(database):
        pass


def test_database_created_only_under_the_pytest_tmp_path(tmp_path: Path) -> None:
    database = tmp_path / "nested" / "historical.db"
    initialize_schema(database)
    assert database.exists()
    assert database.resolve().is_relative_to(tmp_path.resolve())


def test_populated_v1_database_is_readable_then_migrates_with_exact_row_preservation(
    tmp_path: Path,
) -> None:
    database = tmp_path / "historical.db"
    _create_populated_v1_database(database)
    original_bytes = database.read_bytes()
    before = _application_rows(database)

    assert verify_schema_read_only(database) is True
    with open_database(database, read_only=True) as connection:
        assert connection.execute(
            "SELECT id, lottery_type FROM historical_result_run"
        ).fetchall() == [
            ("run-1", "BIG_LOTTO"),
            ("run-failed", "BIG_LOTTO"),
            ("run-progress", "BIG_LOTTO"),
        ]
    assert database.read_bytes() == original_bytes

    initialize_schema(database)

    assert _application_rows(database) == before
    with open_database(database, read_only=True) as connection:
        assert connection.execute(
            "SELECT version FROM historical_schema_migrations ORDER BY version"
        ).fetchall() == [(1,), (2,)]
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        indexes = {row[1] for row in connection.execute("PRAGMA index_list(historical_result_run)")}
        assert "idx_historical_result_run_lottery_completed" in indexes


@pytest.mark.parametrize("lottery_type", ["DAILY_539", "BIG_LOTTO", "POWER_LOTTO"])
def test_v2_schema_accepts_exactly_the_three_internal_lottery_values(
    tmp_path: Path, lottery_type: str
) -> None:
    database = tmp_path / f"{lottery_type}.db"
    initialize_schema(database)
    with open_database(database) as connection:
        values = (
            "run",
            "1" * 64,
            "2" * 64,
            "2.0.0",
            "SYNTHETIC_TEST_ONLY",
            "repo",
            "3" * 40,
            "4" * 64,
            "dataset",
            "5" * 64,
            lottery_type,
            "COMPLETED",
            "now",
            "now",
            "now",
        )
        connection.execute(
            """
            INSERT INTO historical_result_run (
                id, import_identity_sha256, manifest_sha256, contract_version, source_kind,
                source_repository, source_commit_oid, source_artifact_sha256, dataset_identity,
                dataset_sha256, lottery_type, status, started_at, completed_at, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            values,
        )


def test_v2_schema_rejects_arbitrary_lottery_text(tmp_path: Path) -> None:
    database = tmp_path / "historical.db"
    initialize_schema(database)
    with open_database(database) as connection, pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            """
            INSERT INTO historical_result_run (
                id, import_identity_sha256, manifest_sha256, contract_version, source_kind,
                source_repository, source_commit_oid, source_artifact_sha256, dataset_identity,
                dataset_sha256, lottery_type, status, started_at, completed_at, created_at
            ) VALUES ('run', ?, ?, '2.0.0', 'SYNTHETIC_TEST_ONLY', 'repo', ?, ?,
                      'dataset', ?, 'L649', 'COMPLETED', 'now', 'now', 'now')
            """,
            ("1" * 64, "2" * 64, "3" * 40, "4" * 64, "5" * 64),
        )
    with open_database(database) as connection:
        connection.execute(
            """
            INSERT INTO historical_result_run (
                id, import_identity_sha256, manifest_sha256, contract_version, source_kind,
                source_repository, source_commit_oid, source_artifact_sha256, dataset_identity,
                dataset_sha256, lottery_type, status, started_at, completed_at, created_at
            ) VALUES ('run', ?, ?, '2.0.0', 'SYNTHETIC_TEST_ONLY', 'repo', ?, ?,
                      'dataset', ?, 'BIG_LOTTO', 'COMPLETED', 'now', 'now', 'now')
            """,
            ("1" * 64, "2" * 64, "3" * 40, "4" * 64, "5" * 64),
        )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO historical_draw_snapshot (
                    run_id, lottery_type, draw_number, draw_date, main_numbers_json,
                    special_numbers_json, draw_sha256, created_at
                ) VALUES ('run', 'P638', '1', 'now', '[]', '[]', ?, 'now')
                """,
                ("6" * 64,),
            )


def test_v1_to_v2_failure_rolls_back_every_rebuild_step(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = tmp_path / "historical.db"
    _create_populated_v1_database(database)
    before = _application_rows(database)
    monkeypatch.setattr(
        schema_module,
        "V2_MIGRATION_STATEMENTS",
        (
            *schema_module.V2_MIGRATION_STATEMENTS[:8],
            "INVALID SQL",
        ),
    )

    with pytest.raises(sqlite3.OperationalError):
        initialize_schema(database)

    assert _application_rows(database) == before
    with sqlite3.connect(database) as connection:
        assert connection.execute(
            "SELECT version FROM historical_schema_migrations ORDER BY version"
        ).fetchall() == [(1,)]
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        names = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        assert "historical_result_run_v2" not in names
        assert "historical_draw_snapshot_v2" not in names
    assert verify_schema_read_only(database) is True


def test_v1_migration_sql_and_checksum_are_frozen() -> None:
    assert MIGRATION_CHECKSUM == (
        "b8bce2f97403523812117550cb7b575bd22eb3d39d43b76a8a8f0b88e9233837"
    )
    assert len(schema_module.MIGRATION_SQL.encode()) == 5580


def test_newer_unknown_schema_version_fails_closed(tmp_path: Path) -> None:
    database = tmp_path / "historical.db"
    initialize_schema(database)
    with sqlite3.connect(database) as connection:
        connection.execute(
            "INSERT INTO historical_schema_migrations VALUES (3, 'future', 'future', 'future')"
        )
        connection.commit()
    with pytest.raises(HistoricalSchemaMigrationError):
        verify_schema_read_only(database)
