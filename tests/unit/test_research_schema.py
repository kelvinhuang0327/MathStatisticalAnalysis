from __future__ import annotations

import sqlite3
import subprocess
from pathlib import Path

import pytest

from lottolab.infrastructure.persistence import project_database_paths as locations
from lottolab.infrastructure.persistence import research_schema as schema
from lottolab.infrastructure.persistence.project_database_paths import project_database_directory
from lottolab.infrastructure.persistence.research_schema import (
    APPEND_ONLY_TRIGGER_NAMES,
    CURRENT_SCHEMA_VERSION,
    DATA_DIRECTORY_ENV,
    RESEARCH_DATABASE_FILENAME,
    TABLE_NAMES,
    V6_MIGRATION_CHECKSUM,
    MigrationChecksumError,
    NewerSchemaVersionError,
    ResearchDataError,
    ResearchDataPaths,
    ResearchSchemaError,
    initialize_schema,
    open_database,
    resolve_research_data_paths,
    verify_schema_read_only,
)


def _paths(tmp_path: Path) -> ResearchDataPaths:
    data_directory = tmp_path.resolve() / "research-data"
    return ResearchDataPaths(
        data_directory=data_directory,
        database=data_directory / RESEARCH_DATABASE_FILENAME,
    )


def _mutable_connection(paths: ResearchDataPaths) -> sqlite3.Connection:
    return sqlite3.connect(str(paths.database))


def test_canonical_locator_has_durable_default_and_fixed_sibling_filename(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = tmp_path.resolve() / "owner-home"
    # The candidate lives inside the canonical checkout, so isolate only the
    # host-worktree boundary guard while checking its default path behavior.
    monkeypatch.setattr(schema, "_reject_git_worktree_path", lambda _path: None)

    paths = resolve_research_data_paths(environ={}, home=home)

    assert paths.data_directory == project_database_directory()
    assert paths.database == paths.data_directory / RESEARCH_DATABASE_FILENAME
    assert paths.database.name == "lottolab_research.db"
    assert not home.exists()


def test_schema_initializes_research_database_inside_ignored_project_scratch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = tmp_path / "canonical-checkout"
    project.mkdir()
    subprocess.run(("git", "init", "--quiet", str(project)), check=True)
    (project / ".gitignore").write_text(".task-data/\n", encoding="utf-8")
    monkeypatch.setattr(locations, "PROJECT_ROOT", project)
    scratch_directory = project / ".task-data" / "_scratch" / "unit_research_db_01"

    paths = resolve_research_data_paths(environ={DATA_DIRECTORY_ENV: str(scratch_directory)})
    initialize_schema(paths)

    assert paths.database == scratch_directory / RESEARCH_DATABASE_FILENAME
    assert paths.database.is_file()
    assert verify_schema_read_only(paths) is True
    with open_database(paths, read_only=True) as connection:
        assert connection.execute("SELECT COUNT(*) FROM research_schema_migrations").fetchone() == (
            5,
        )


def test_migration_is_idempotent_and_checksum_verified(tmp_path: Path) -> None:
    paths = _paths(tmp_path)

    initialize_schema(paths)
    with open_database(paths, read_only=True) as connection:
        first_schema = connection.execute(
            """
            SELECT type, name, tbl_name, sql
            FROM sqlite_schema
            ORDER BY type, name
            """
        ).fetchall()
        migration = connection.execute(
            """
            SELECT version, checksum
            FROM research_schema_migrations
            ORDER BY version DESC
            """
        ).fetchone()
    initialize_schema(paths)
    with open_database(paths, read_only=True) as connection:
        second_schema = connection.execute(
            """
            SELECT type, name, tbl_name, sql
            FROM sqlite_schema
            ORDER BY type, name
            """
        ).fetchall()
        migration_count = connection.execute(
            "SELECT COUNT(*) FROM research_schema_migrations"
        ).fetchone()[0]

    assert migration == (CURRENT_SCHEMA_VERSION, V6_MIGRATION_CHECKSUM)
    assert migration_count == 5
    assert first_schema == second_schema
    assert verify_schema_read_only(paths) is True
    assert not Path(f"{paths.database}-wal").exists()
    assert not Path(f"{paths.database}-shm").exists()


def test_migration_checksum_mismatch_fails_closed(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    initialize_schema(paths)
    connection = _mutable_connection(paths)
    try:
        connection.execute("DROP TRIGGER trg_research_schema_migrations_no_update")
        connection.execute(
            "UPDATE research_schema_migrations SET checksum = ?",
            ("0" * 64,),
        )
        connection.commit()
    finally:
        connection.close()

    with pytest.raises(MigrationChecksumError, match="checksum"):
        verify_schema_read_only(paths)


def test_newer_schema_version_fails_closed(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    initialize_schema(paths)
    connection = _mutable_connection(paths)
    try:
        connection.execute("DROP TRIGGER trg_research_schema_migrations_no_update")
        connection.execute(
            "UPDATE research_schema_migrations SET version = ? WHERE version = ?",
            (CURRENT_SCHEMA_VERSION + 1, CURRENT_SCHEMA_VERSION),
        )
        connection.commit()
    finally:
        connection.close()

    with pytest.raises(NewerSchemaVersionError, match="newer"):
        verify_schema_read_only(paths)


def test_semantic_schema_drift_fails_closed(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    initialize_schema(paths)
    connection = _mutable_connection(paths)
    try:
        connection.execute("DROP INDEX idx_research_targets_progress")
        connection.commit()
    finally:
        connection.close()

    with pytest.raises(ResearchSchemaError, match="schema objects"):
        verify_schema_read_only(paths)


def test_wal_or_shm_sidecar_is_rejected_before_open(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    initialize_schema(paths)
    wal = Path(f"{paths.database}-wal")
    wal.write_bytes(b"forbidden")

    with pytest.raises(ResearchDataError, match="WAL and SHM"):
        verify_schema_read_only(paths)


def test_read_only_connection_cannot_write(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    initialize_schema(paths)

    with (
        open_database(paths, read_only=True) as connection,
        pytest.raises(sqlite3.OperationalError, match="readonly"),
    ):
        connection.execute(
            """
            INSERT INTO research_idempotency_keys (
                id, writer_role, operation_name, idempotency_key,
                request_sha256, created_at
            ) VALUES ('x', 'x', 'x', 'x', ?, 'x')
            """,
            ("0" * 64,),
        )


def test_schema_has_exact_table_and_append_only_trigger_inventory(
    tmp_path: Path,
) -> None:
    paths = _paths(tmp_path)
    initialize_schema(paths)

    with open_database(paths, read_only=True) as connection:
        tables = tuple(
            row[0]
            for row in connection.execute(
                """
                SELECT name FROM sqlite_schema
                WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
                ORDER BY name
                """
            )
        )
        triggers = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_schema WHERE type = 'trigger'")
        }

    assert tables == tuple(sorted(TABLE_NAMES))
    assert set(APPEND_ONLY_TRIGGER_NAMES) <= triggers


def test_fresh_v6_native_ticket_evidence_contract_has_constraints_and_triggers(
    tmp_path: Path,
) -> None:
    paths = _paths(tmp_path)
    initialize_schema(paths)

    with open_database(paths, read_only=True) as connection:
        columns = {
            row[1]: {"notnull": row[3], "primary_key": row[5]}
            for row in connection.execute("PRAGMA table_info(research_native_ticket_evidence)")
        }
        foreign_keys = connection.execute(
            "PRAGMA foreign_key_list(research_native_ticket_evidence)"
        ).fetchall()
        triggers = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_schema WHERE type='trigger'")
        }

    assert set(columns) == {
        "ticket_id",
        "emitted_main_numbers_json",
        "rng_evidence_json",
    }
    assert columns["ticket_id"]["primary_key"] == 1
    assert columns["emitted_main_numbers_json"]["notnull"] == 1
    assert columns["rng_evidence_json"]["notnull"] == 1
    assert [(row[2], row[3], row[4], row[6]) for row in foreign_keys] == [
        ("research_prediction_tickets", "ticket_id", "id", "RESTRICT")
    ]
    assert {
        "trg_research_native_ticket_evidence_no_update",
        "trg_research_native_ticket_evidence_no_delete",
    } <= triggers

    with sqlite3.connect(paths.database) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
            connection.execute(
                """
                INSERT INTO research_native_ticket_evidence (
                    ticket_id, emitted_main_numbers_json, rng_evidence_json
                ) VALUES (?, ?, ?)
                """,
                ("missing-ticket", "[]", "{}"),
            )

    assert schema.verify_schema_read_only(paths) is True


def test_v5_to_v6_migration_preserves_existing_data_and_database_file(
    tmp_path: Path,
) -> None:
    paths = _paths(tmp_path)
    initialize_schema(paths)
    artifact = (
        "artifact-v5-fixture",
        "NATIVE_EVIDENCE",
        "fixture://schema-v5-existing-data",
        "application/json",
        7,
        "a" * 64,
        "2030-01-05T10:05:00Z",
    )
    with sqlite3.connect(paths.database) as connection:
        connection.execute(
            """
            INSERT INTO research_artifacts (
                id, artifact_kind, source_locator, media_type, byte_length,
                artifact_sha256, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            artifact,
        )

    database_inode = paths.database.stat().st_ino
    with sqlite3.connect(paths.database) as connection:
        connection.execute("PRAGMA foreign_keys = OFF")
        connection.execute("BEGIN IMMEDIATE")
        for statement in schema.V6_MIGRATION_STATEMENTS[1:]:
            trigger_name = schema._object_name(statement)
            connection.execute(f'DROP TRIGGER "{trigger_name}"')
        connection.execute("DROP TABLE research_native_ticket_evidence")

        migration_triggers = schema._append_only_trigger_statements("research_schema_migrations")
        for statement in migration_triggers:
            trigger_name = schema._object_name(statement)
            connection.execute(f'DROP TRIGGER "{trigger_name}"')
        connection.execute("DELETE FROM research_schema_migrations WHERE version = 6")
        for statement in migration_triggers:
            connection.execute(statement)

    with sqlite3.connect(paths.database) as connection:
        version = connection.execute(
            "SELECT MAX(version) FROM research_schema_migrations"
        ).fetchone()[0]
        preserved_before = connection.execute(
            "SELECT * FROM research_artifacts WHERE id = ?",
            (artifact[0],),
        ).fetchone()
        v6_table_present = connection.execute(
            """
            SELECT 1 FROM sqlite_schema
            WHERE type='table' AND name='research_native_ticket_evidence'
            """
        ).fetchone()

    assert version == 5
    assert preserved_before == artifact
    assert v6_table_present is None
    assert paths.database.stat().st_ino == database_inode

    initialize_schema(paths)

    with open_database(paths, read_only=True) as connection:
        version, migration_name, migration_checksum = connection.execute(
            """
            SELECT version, name, checksum
            FROM research_schema_migrations
            ORDER BY version DESC LIMIT 1
            """
        ).fetchone()
        preserved_after = connection.execute(
            "SELECT * FROM research_artifacts WHERE id = ?",
            (artifact[0],),
        ).fetchone()
        v6_table_present = connection.execute(
            """
            SELECT 1 FROM sqlite_schema
            WHERE type='table' AND name='research_native_ticket_evidence'
            """
        ).fetchone()

    assert (version, migration_name, migration_checksum) == (
        schema.CURRENT_SCHEMA_VERSION,
        schema.V6_MIGRATION_NAME,
        schema.V6_MIGRATION_CHECKSUM,
    )
    assert preserved_after == artifact
    assert v6_table_present == (1,)
    assert paths.database.stat().st_ino == database_inode
    assert verify_schema_read_only(paths) is True
