"""Isolated, explicit-path SQLite authority for Next-Draw P4 attribution."""

from __future__ import annotations

import hashlib
import re
import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

NEXT_DRAW_P4_SQLITE_SCHEMA_ID = "LOTTOLAB_NEXT_DRAW_P4_SQLITE_V1"
CURRENT_SCHEMA_VERSION = 1
MIGRATION_NAME = "create_next_draw_p4_attribution_schema"
BUSY_TIMEOUT_MS = 5_000

TABLE_NAMES = (
    "next_draw_p4_schema_migrations",
    "next_draw_p4_attributions",
)


class NextDrawP4SchemaError(RuntimeError):
    """The explicit P4 database path or schema failed a safety check."""


class NextDrawP4SchemaMigrationError(NextDrawP4SchemaError):
    """The P4 schema is absent, incomplete, newer, or semantically drifted."""


class NextDrawP4SchemaChecksumError(NextDrawP4SchemaMigrationError):
    """The recorded P4 migration does not match the code-owned migration."""


@dataclass(frozen=True, slots=True)
class NextDrawP4DatabasePaths:
    """One validated explicit database path; construction performs no I/O."""

    database: Path


MIGRATION_STATEMENTS = (
    """
    CREATE TABLE next_draw_p4_schema_migrations (
        version INTEGER PRIMARY KEY,
        schema_id TEXT NOT NULL,
        name TEXT NOT NULL,
        checksum TEXT NOT NULL,
        applied_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE next_draw_p4_attributions (
        lottery_type TEXT NOT NULL CHECK (lottery_type = 'BIG_LOTTO'),
        target_draw_number TEXT NOT NULL CHECK (length(target_draw_number) BETWEEN 1 AND 32),
        target_draw_date TEXT NOT NULL CHECK (length(target_draw_date) = 10),
        seal_file_sha256 TEXT NOT NULL CHECK (length(seal_file_sha256) = 64),
        seal_digest TEXT NOT NULL CHECK (length(seal_digest) = 64),
        outcome_sha256 TEXT NOT NULL CHECK (length(outcome_sha256) = 64),
        scoring_contract_sha256 TEXT NOT NULL CHECK (length(scoring_contract_sha256) = 64),
        attribution_sha256 TEXT NOT NULL CHECK (length(attribution_sha256) = 64),
        canonical_bytes BLOB NOT NULL,
        created_at TEXT NOT NULL,
        PRIMARY KEY (lottery_type, target_draw_number, target_draw_date)
    )
    """,
    """
    CREATE INDEX idx_next_draw_p4_attributions_history
    ON next_draw_p4_attributions (
        created_at DESC, target_draw_date DESC,
        target_draw_number DESC, lottery_type ASC
    )
    """,
    """
    CREATE TRIGGER trg_next_draw_p4_attributions_no_update
    BEFORE UPDATE ON next_draw_p4_attributions
    BEGIN
        SELECT RAISE(ABORT, 'next_draw_p4_attributions is immutable');
    END
    """,
    """
    CREATE TRIGGER trg_next_draw_p4_attributions_no_delete
    BEFORE DELETE ON next_draw_p4_attributions
    BEGIN
        SELECT RAISE(ABORT, 'next_draw_p4_attributions is immutable');
    END
    """,
)

MIGRATION_SQL = ";\n".join(statement.strip() for statement in MIGRATION_STATEMENTS) + ";\n"
MIGRATION_CHECKSUM = hashlib.sha256(MIGRATION_SQL.encode("utf-8")).hexdigest()

_SCHEMA_SQL_TOKEN = re.compile(
    r"'(?:''|[^'])*'|\"(?:\"\"|[^\"])*\"|`(?:``|[^`])*`|\[[^]]*\]|[(),]|[^\s(),]+"
)
_CREATE_NAME_PATTERN = re.compile(
    r"CREATE\s+(?:UNIQUE\s+)?(?:TABLE|INDEX|TRIGGER)\s+(\w+)", re.IGNORECASE
)


def _canonical_schema_sql(sql: str) -> tuple[str, ...]:
    return tuple(token.casefold() for token in _SCHEMA_SQL_TOKEN.findall(sql))


def _object_name(sql: str) -> str:
    match = _CREATE_NAME_PATTERN.search(sql)
    if match is None:
        raise NextDrawP4SchemaError("cannot determine P4 schema object name")
    return match.group(1)


_EXPECTED_SCHEMA_SQL_BY_NAME = {
    _object_name(statement): statement for statement in MIGRATION_STATEMENTS
}


def resolve_next_draw_p4_database_paths(database: Path) -> NextDrawP4DatabasePaths:
    """Validate one caller-supplied path with no scan, fallback, or creation."""

    if not isinstance(cast(object, database), Path):
        raise NextDrawP4SchemaError("P4 database must be a Path")
    if "\x00" in str(database):
        raise NextDrawP4SchemaError("P4 database path contains a null byte")
    if not database.is_absolute():
        raise NextDrawP4SchemaError("P4 database path must be explicit and absolute")
    if database == Path(database.anchor) or database.parent == Path(database.anchor):
        raise NextDrawP4SchemaError("P4 database cannot be placed at the filesystem root")
    if any(part.casefold() == "lotterynew" for part in database.parts):
        raise NextDrawP4SchemaError("LotteryNew paths are forbidden")
    return NextDrawP4DatabasePaths(database=database)


def initialize_schema(database: Path) -> None:
    """Create or verify the isolated V1 schema inside one write transaction."""

    paths = resolve_next_draw_p4_database_paths(database)
    paths.database.parent.mkdir(parents=True, exist_ok=True)
    with _raw_connection(paths) as connection:
        connection.execute("BEGIN IMMEDIATE")
        try:
            if not _verify_migration_state(connection):
                for statement in MIGRATION_STATEMENTS:
                    connection.execute(statement)
                connection.execute(
                    """
                    INSERT INTO next_draw_p4_schema_migrations
                        (version, schema_id, name, checksum, applied_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        CURRENT_SCHEMA_VERSION,
                        NEXT_DRAW_P4_SQLITE_SCHEMA_ID,
                        MIGRATION_NAME,
                        MIGRATION_CHECKSUM,
                        _utc_now(),
                    ),
                )
                if not _verify_migration_state(connection):
                    raise NextDrawP4SchemaMigrationError(
                        "P4 schema migration did not reach version 1"
                    )
        except BaseException:
            connection.rollback()
            raise
        else:
            connection.commit()


def verify_schema_read_only(database: Path) -> bool:
    """Return False for an absent DB; verify an existing DB without writing."""

    paths = resolve_next_draw_p4_database_paths(database)
    if not paths.database.exists():
        return False
    with _raw_connection(paths, read_only=True) as connection:
        initialized = _verify_migration_state(connection)
    if not initialized:
        raise NextDrawP4SchemaMigrationError("P4 database has no migration authority")
    return True


@contextmanager
def open_database(database: Path, *, read_only: bool = False) -> Generator[sqlite3.Connection]:
    """Open an existing, semantically verified P4 database."""

    paths = resolve_next_draw_p4_database_paths(database)
    if not paths.database.exists():
        raise NextDrawP4SchemaMigrationError("P4 database does not exist")
    with _raw_connection(paths, read_only=read_only) as connection:
        if not _verify_migration_state(connection):
            raise NextDrawP4SchemaMigrationError("P4 database has no migration authority")
        yield connection


@contextmanager
def _raw_connection(
    paths: NextDrawP4DatabasePaths, *, read_only: bool = False
) -> Generator[sqlite3.Connection]:
    mode = "ro" if read_only else "rwc"
    uri = f"{paths.database.as_uri()}?mode={mode}"
    try:
        connection = sqlite3.connect(
            uri,
            uri=True,
            timeout=BUSY_TIMEOUT_MS / 1_000,
            isolation_level=None,
        )
    except sqlite3.DatabaseError as exc:
        raise NextDrawP4SchemaMigrationError("cannot open P4 database safely") from exc
    try:
        try:
            connection.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}")
            connection.execute("PRAGMA foreign_keys = ON")
            if connection.execute("PRAGMA foreign_keys").fetchone() != (1,):
                raise NextDrawP4SchemaMigrationError(
                    "SQLite foreign-key enforcement is unavailable"
                )
            if read_only:
                connection.execute("PRAGMA query_only = ON")
        except sqlite3.DatabaseError as exc:
            raise NextDrawP4SchemaMigrationError("cannot configure P4 SQLite safely") from exc
        yield connection
    finally:
        connection.close()


def _verify_migration_state(connection: sqlite3.Connection) -> bool:
    table_names = {
        str(row[0])
        for row in connection.execute(
            """
            SELECT name FROM sqlite_master
            WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
            ORDER BY name
            """
        )
    }
    if "next_draw_p4_schema_migrations" not in table_names:
        if table_names:
            raise NextDrawP4SchemaMigrationError(
                "unversioned P4 database contains application tables"
            )
        return False
    rows = connection.execute(
        """
        SELECT version, schema_id, name, checksum
        FROM next_draw_p4_schema_migrations ORDER BY version
        """
    ).fetchall()
    if rows != [
        (
            CURRENT_SCHEMA_VERSION,
            NEXT_DRAW_P4_SQLITE_SCHEMA_ID,
            MIGRATION_NAME,
            MIGRATION_CHECKSUM,
        )
    ]:
        versions = [row[0] for row in rows]
        if any(
            isinstance(version, int) and version > CURRENT_SCHEMA_VERSION
            for version in versions
        ):
            raise NextDrawP4SchemaMigrationError("P4 schema is newer than this build")
        if rows and rows[0][3] != MIGRATION_CHECKSUM:
            raise NextDrawP4SchemaChecksumError("P4 migration checksum does not match")
        raise NextDrawP4SchemaMigrationError("P4 migration history is invalid")
    _verify_schema_semantics(connection, table_names)
    return True


def _verify_schema_semantics(connection: sqlite3.Connection, table_names: set[str]) -> None:
    if table_names != set(TABLE_NAMES):
        raise NextDrawP4SchemaMigrationError("P4 database tables do not match V1")
    rows = connection.execute(
        """
        SELECT type, name, sql FROM sqlite_schema
        WHERE sql IS NOT NULL AND name NOT LIKE 'sqlite_%'
        ORDER BY type, name
        """
    ).fetchall()
    seen: set[str] = set()
    for _object_type, name_raw, actual_sql in rows:
        name = str(name_raw)
        seen.add(name)
        expected_sql = _EXPECTED_SCHEMA_SQL_BY_NAME.get(name)
        if expected_sql is None or not isinstance(actual_sql, str):
            raise NextDrawP4SchemaMigrationError(f"unexpected P4 schema object: {name}")
        if _canonical_schema_sql(actual_sql) != _canonical_schema_sql(expected_sql):
            raise NextDrawP4SchemaMigrationError(
                f"P4 schema SQL does not match V1: {name}"
            )
    if seen != set(_EXPECTED_SCHEMA_SQL_BY_NAME):
        raise NextDrawP4SchemaMigrationError("P4 schema objects do not match V1")


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


__all__ = [
    "BUSY_TIMEOUT_MS",
    "CURRENT_SCHEMA_VERSION",
    "MIGRATION_CHECKSUM",
    "MIGRATION_NAME",
    "NEXT_DRAW_P4_SQLITE_SCHEMA_ID",
    "NextDrawP4DatabasePaths",
    "NextDrawP4SchemaChecksumError",
    "NextDrawP4SchemaError",
    "NextDrawP4SchemaMigrationError",
    "initialize_schema",
    "open_database",
    "resolve_next_draw_p4_database_paths",
    "verify_schema_read_only",
]
