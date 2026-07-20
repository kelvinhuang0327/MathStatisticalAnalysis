"""Schema creation/verification tests for the historical-results projection (BLHQ R1)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from lottolab.infrastructure.persistence.historical_schema import (
    CURRENT_SCHEMA_VERSION,
    TABLE_NAMES,
    HistoricalSchemaChecksumError,
    HistoricalSchemaMigrationError,
    initialize_schema,
    open_database,
    verify_schema_read_only,
)


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
