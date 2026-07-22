"""Dedicated, versioned, idempotent SQLite schema for the Replay-scoring projection.

A standalone schema module, deliberately not sharing anything with
``draw_schema.py`` or ``historical_schema.py``: constructors take an explicit
database path (no ``LOTTOLAB_DATA_DIR`` resolution, no canonical/default
production DB). Mirrors ``historical_schema.py``'s versioned-migration and
semantic-drift-detection pattern (BLHQ R1) at a scope appropriate to a
dedicated, test-owned database, and never reuses the ``historical_*`` tables.
"""

from __future__ import annotations

import hashlib
import re
import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

CURRENT_SCHEMA_VERSION = 1
MIGRATION_NAME = "create_replay_scoring_projection_schema"
BUSY_TIMEOUT_MS = 5_000

TABLE_NAMES = (
    "replay_scoring_schema_migrations",
    "replay_scoring_runs",
    "replay_scored_predictions",
    "replay_scoring_strategy_aggregates",
    "replay_scoring_overall_aggregates",
)


class ReplayScoringSchemaError(RuntimeError):
    """The Replay-scoring database path or schema failed a safety check."""


class ReplayScoringSchemaMigrationError(ReplayScoringSchemaError):
    """The Replay-scoring database schema is absent, corrupt, or drifted."""


class ReplayScoringSchemaChecksumError(ReplayScoringSchemaMigrationError):
    """A recorded migration does not match the code-owned migration."""


@dataclass(frozen=True, slots=True)
class ReplayScoringDatabasePaths:
    """Resolved path only; constructing this value never creates or opens anything."""

    database: Path


MIGRATION_STATEMENTS = (
    """
    CREATE TABLE replay_scoring_schema_migrations (
        version INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        checksum TEXT NOT NULL,
        applied_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE replay_scoring_runs (
        scoring_artifact_payload_sha256 TEXT PRIMARY KEY
            CHECK (length(scoring_artifact_payload_sha256) = 64),
        scoring_artifact_schema_version TEXT NOT NULL,
        source_replay_artifact_payload_sha256 TEXT NOT NULL
            CHECK (length(source_replay_artifact_payload_sha256) = 64),
        dataset_id TEXT NOT NULL,
        dataset_version TEXT NOT NULL,
        lottery_type TEXT NOT NULL CHECK (lottery_type = 'BIG_LOTTO'),
        target_count INTEGER NOT NULL CHECK (target_count >= 0),
        strategy_count INTEGER NOT NULL CHECK (strategy_count >= 0),
        scored_record_count INTEGER NOT NULL CHECK (scored_record_count >= 0),
        overall_aggregate_sha256 TEXT NOT NULL CHECK (length(overall_aggregate_sha256) = 64),
        canonical_bytes BLOB NOT NULL,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE replay_scored_predictions (
        id INTEGER PRIMARY KEY,
        run_sha256 TEXT NOT NULL,
        ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
        source_snapshot_result_sha256 TEXT NOT NULL
            CHECK (length(source_snapshot_result_sha256) = 64),
        scored_result_sha256 TEXT NOT NULL CHECK (length(scored_result_sha256) = 64),
        target_draw_number TEXT NOT NULL,
        target_draw_date TEXT NOT NULL,
        strategy_id TEXT NOT NULL,
        strategy_version TEXT NULL,
        source_history_status TEXT NOT NULL,
        source_history_reason_code TEXT NULL,
        source_prediction_status TEXT NULL,
        source_prediction_reason_code TEXT NULL,
        scoring_status TEXT NOT NULL,
        scoring_reason_code TEXT NULL,
        predicted_main_numbers_json TEXT NULL,
        target_outcome_sha256 TEXT NULL
            CHECK (target_outcome_sha256 IS NULL OR length(target_outcome_sha256) = 64),
        main_number_hit_count INTEGER NULL
            CHECK (main_number_hit_count IS NULL OR main_number_hit_count >= 0),
        special_number_hit INTEGER NULL CHECK (special_number_hit IN (0, 1)),
        prize_tier_id TEXT NULL,
        prize_official_label TEXT NULL,
        no_prize_result TEXT NULL,
        UNIQUE (run_sha256, ordinal),
        UNIQUE (run_sha256, scored_result_sha256),
        FOREIGN KEY (run_sha256)
            REFERENCES replay_scoring_runs(scoring_artifact_payload_sha256) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE replay_scoring_strategy_aggregates (
        id INTEGER PRIMARY KEY,
        run_sha256 TEXT NOT NULL,
        ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
        strategy_id TEXT NOT NULL,
        strategy_version TEXT NULL,
        source_snapshot_count INTEGER NOT NULL CHECK (source_snapshot_count >= 0),
        scored_count INTEGER NOT NULL CHECK (scored_count >= 0),
        history_closed_count INTEGER NOT NULL CHECK (history_closed_count >= 0),
        prediction_closed_count INTEGER NOT NULL CHECK (prediction_closed_count >= 0),
        target_outcome_not_found_count INTEGER NOT NULL
            CHECK (target_outcome_not_found_count >= 0),
        target_identity_mismatch_count INTEGER NOT NULL
            CHECK (target_identity_mismatch_count >= 0),
        first_prize_count INTEGER NOT NULL CHECK (first_prize_count >= 0),
        second_prize_count INTEGER NOT NULL CHECK (second_prize_count >= 0),
        third_prize_count INTEGER NOT NULL CHECK (third_prize_count >= 0),
        fourth_prize_count INTEGER NOT NULL CHECK (fourth_prize_count >= 0),
        fifth_prize_count INTEGER NOT NULL CHECK (fifth_prize_count >= 0),
        sixth_prize_count INTEGER NOT NULL CHECK (sixth_prize_count >= 0),
        seventh_prize_count INTEGER NOT NULL CHECK (seventh_prize_count >= 0),
        general_prize_count INTEGER NOT NULL CHECK (general_prize_count >= 0),
        no_prize_count INTEGER NOT NULL CHECK (no_prize_count >= 0),
        aggregate_sha256 TEXT NOT NULL CHECK (length(aggregate_sha256) = 64),
        UNIQUE (run_sha256, ordinal),
        UNIQUE (run_sha256, strategy_id, strategy_version),
        FOREIGN KEY (run_sha256)
            REFERENCES replay_scoring_runs(scoring_artifact_payload_sha256) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE replay_scoring_overall_aggregates (
        run_sha256 TEXT PRIMARY KEY,
        source_snapshot_count INTEGER NOT NULL CHECK (source_snapshot_count >= 0),
        scored_count INTEGER NOT NULL CHECK (scored_count >= 0),
        history_closed_count INTEGER NOT NULL CHECK (history_closed_count >= 0),
        prediction_closed_count INTEGER NOT NULL CHECK (prediction_closed_count >= 0),
        target_outcome_not_found_count INTEGER NOT NULL
            CHECK (target_outcome_not_found_count >= 0),
        target_identity_mismatch_count INTEGER NOT NULL
            CHECK (target_identity_mismatch_count >= 0),
        first_prize_count INTEGER NOT NULL CHECK (first_prize_count >= 0),
        second_prize_count INTEGER NOT NULL CHECK (second_prize_count >= 0),
        third_prize_count INTEGER NOT NULL CHECK (third_prize_count >= 0),
        fourth_prize_count INTEGER NOT NULL CHECK (fourth_prize_count >= 0),
        fifth_prize_count INTEGER NOT NULL CHECK (fifth_prize_count >= 0),
        sixth_prize_count INTEGER NOT NULL CHECK (sixth_prize_count >= 0),
        seventh_prize_count INTEGER NOT NULL CHECK (seventh_prize_count >= 0),
        general_prize_count INTEGER NOT NULL CHECK (general_prize_count >= 0),
        no_prize_count INTEGER NOT NULL CHECK (no_prize_count >= 0),
        aggregate_sha256 TEXT NOT NULL CHECK (length(aggregate_sha256) = 64),
        FOREIGN KEY (run_sha256)
            REFERENCES replay_scoring_runs(scoring_artifact_payload_sha256) ON DELETE CASCADE
    )
    """,
)

MIGRATION_SQL = ";\n".join(statement.strip() for statement in MIGRATION_STATEMENTS) + ";\n"
MIGRATION_CHECKSUM = hashlib.sha256(MIGRATION_SQL.encode("utf-8")).hexdigest()

_SCHEMA_SQL_TOKEN = re.compile(
    r"'(?:''|[^'])*'|\"(?:\"\"|[^\"])*\"|`(?:``|[^`])*`|\[[^]]*\]|[(),]|[^\s(),]+"
)
_CREATE_NAME_PATTERN = re.compile(r"CREATE\s+(?:UNIQUE\s+)?(?:TABLE|INDEX)\s+(\w+)", re.IGNORECASE)


def _canonical_schema_sql(sql: str) -> tuple[str, ...]:
    return tuple(token.casefold() for token in _SCHEMA_SQL_TOKEN.findall(sql))


def _object_name(sql: str) -> str:
    match = _CREATE_NAME_PATTERN.search(sql)
    if match is None:
        raise ReplayScoringSchemaError("cannot determine schema object name")
    return match.group(1)


_EXPECTED_SCHEMA_SQL_BY_NAME = {
    _object_name(statement): statement for statement in MIGRATION_STATEMENTS
}


def resolve_replay_scoring_database_paths(database: Path) -> ReplayScoringDatabasePaths:
    """Validate an explicit, caller-owned database path. Never creates anything."""

    if "\x00" in str(database):
        raise ReplayScoringSchemaError("database path contains a null byte")
    if not database.is_absolute():
        raise ReplayScoringSchemaError("database path must be absolute")
    if any(part.casefold() == "lotterynew" for part in database.parts):
        raise ReplayScoringSchemaError("LotteryNew paths are forbidden")
    return ReplayScoringDatabasePaths(database=database)


def initialize_schema(database: Path) -> None:
    """Securely create/verify a version-1 Replay-scoring database.

    Idempotent: a call against an already-initialized version-1 database is a
    read-only semantic verification, not a rewrite.
    """

    paths = resolve_replay_scoring_database_paths(database)
    paths.database.parent.mkdir(parents=True, exist_ok=True)
    with _raw_connection(paths) as connection:
        connection.execute("BEGIN IMMEDIATE")
        try:
            if not _verify_migration_state(connection):
                for statement in MIGRATION_STATEMENTS:
                    connection.execute(statement)
                connection.execute(
                    """
                    INSERT INTO replay_scoring_schema_migrations
                        (version, name, checksum, applied_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (CURRENT_SCHEMA_VERSION, MIGRATION_NAME, MIGRATION_CHECKSUM, _utc_now()),
                )
                if not _verify_migration_state(connection):
                    raise ReplayScoringSchemaMigrationError(
                        "replay-scoring schema migration did not reach version 1"
                    )
        except BaseException:
            connection.rollback()
            raise
        else:
            connection.commit()


def verify_schema_read_only(database: Path) -> bool:
    """Return False for an absent DB; validate an existing DB without creating it."""

    paths = resolve_replay_scoring_database_paths(database)
    if not paths.database.exists():
        return False
    with _raw_connection(paths, read_only=True) as connection:
        initialized = _verify_migration_state(connection)
    if not initialized:
        raise ReplayScoringSchemaMigrationError("database exists without a schema migration")
    return True


@contextmanager
def open_database(database: Path, *, read_only: bool = False) -> Generator[sqlite3.Connection]:
    """Open a fresh, configured connection to an existing verified version-1 DB."""

    paths = resolve_replay_scoring_database_paths(database)
    if not paths.database.exists():
        raise ReplayScoringSchemaMigrationError("replay-scoring database does not exist")
    with _raw_connection(paths, read_only=read_only) as connection:
        if not _verify_migration_state(connection):
            raise ReplayScoringSchemaMigrationError("database exists without a schema migration")
        yield connection


@contextmanager
def _raw_connection(
    paths: ReplayScoringDatabasePaths, *, read_only: bool = False
) -> Generator[sqlite3.Connection]:
    mode = "ro" if read_only else "rwc"
    uri = f"{paths.database.as_uri()}?mode={mode}"
    try:
        connection = sqlite3.connect(
            uri, uri=True, timeout=BUSY_TIMEOUT_MS / 1_000, isolation_level=None
        )
    except sqlite3.DatabaseError as exc:
        raise ReplayScoringSchemaMigrationError(
            "cannot open the replay-scoring database safely"
        ) from exc
    try:
        try:
            connection.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}")
            connection.execute("PRAGMA foreign_keys = ON")
            if connection.execute("PRAGMA foreign_keys").fetchone() != (1,):
                raise ReplayScoringSchemaMigrationError(
                    "SQLite foreign-key enforcement is unavailable"
                )
            if read_only:
                connection.execute("PRAGMA query_only = ON")
        except sqlite3.DatabaseError as exc:
            raise ReplayScoringSchemaMigrationError("cannot configure SQLite safely") from exc
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
    if "replay_scoring_schema_migrations" not in table_names:
        if table_names:
            raise ReplayScoringSchemaMigrationError(
                "unversioned database contains application tables"
            )
        return False

    rows = connection.execute(
        "SELECT version, name, checksum FROM replay_scoring_schema_migrations ORDER BY version"
    ).fetchall()
    try:
        versions = [int(row[0]) for row in rows]
    except (TypeError, ValueError) as exc:
        raise ReplayScoringSchemaMigrationError("migration versions are invalid") from exc
    if any(version > CURRENT_SCHEMA_VERSION for version in versions):
        raise ReplayScoringSchemaMigrationError(
            "database schema is newer than this LottoLab build"
        )
    if versions != [CURRENT_SCHEMA_VERSION]:
        raise ReplayScoringSchemaMigrationError("migration history is incomplete")
    _, name, checksum = rows[0]
    if name != MIGRATION_NAME or checksum != MIGRATION_CHECKSUM:
        raise ReplayScoringSchemaChecksumError("migration checksum does not match")

    _verify_schema_semantics(connection, table_names)
    return True


def _verify_schema_semantics(connection: sqlite3.Connection, table_names: set[str]) -> None:
    if table_names != set(TABLE_NAMES):
        raise ReplayScoringSchemaMigrationError("database tables do not match version 1")

    schema_rows = connection.execute(
        """
        SELECT type, name, tbl_name, sql FROM sqlite_schema
        WHERE sql IS NOT NULL AND name NOT LIKE 'sqlite_%'
        ORDER BY type, name
        """
    ).fetchall()
    seen_names: set[str] = set()
    for row in schema_rows:
        name = str(row[1])
        actual_sql = row[3]
        seen_names.add(name)
        expected_sql = _EXPECTED_SCHEMA_SQL_BY_NAME.get(name)
        if expected_sql is None or not isinstance(actual_sql, str):
            raise ReplayScoringSchemaMigrationError(f"unexpected database schema object: {name}")
        if _canonical_schema_sql(actual_sql) != _canonical_schema_sql(expected_sql):
            raise ReplayScoringSchemaMigrationError(
                f"database schema SQL does not match version 1: {name}"
            )
    if seen_names != set(_EXPECTED_SCHEMA_SQL_BY_NAME):
        raise ReplayScoringSchemaMigrationError("database schema objects do not match version 1")

    for table in TABLE_NAMES:
        foreign_keys = connection.execute(f"PRAGMA foreign_key_list({table})").fetchall()
        for fk_row in foreign_keys:
            on_delete = str(fk_row[6])
            if on_delete not in ("RESTRICT", "CASCADE"):
                raise ReplayScoringSchemaMigrationError(
                    f"unexpected foreign-key action on {table}: {on_delete}"
                )


def _utc_now() -> str:
    from datetime import UTC, datetime

    return datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


__all__ = [
    "BUSY_TIMEOUT_MS",
    "CURRENT_SCHEMA_VERSION",
    "MIGRATION_CHECKSUM",
    "MIGRATION_NAME",
    "TABLE_NAMES",
    "ReplayScoringDatabasePaths",
    "ReplayScoringSchemaChecksumError",
    "ReplayScoringSchemaError",
    "ReplayScoringSchemaMigrationError",
    "initialize_schema",
    "open_database",
    "resolve_replay_scoring_database_paths",
    "verify_schema_read_only",
]
