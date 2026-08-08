"""Dedicated, versioned, idempotent SQLite schema for the P638 current-universe ranking.

A standalone schema module, deliberately not sharing anything with
``historical_schema.py``, the ``p638_historical_forwarder.py`` P638
Historical Results V2 contract, ``p638_all10_ranking_schema.py``, or
``p638_all23_ranking_schema.py``: none of those are mutated by this task.

Distinct from the all-10 and all-23 schemas in one deliberate way: this
contract's strategy count is NOT a fixed schema-time constant. As new waves
of P638 strategies are migrated, the "current" universe grows; a fixed
``CHECK (strategy_count = N)`` would need editing on every wave, which is
exactly the count-named-route churn this task's packet forbids ("Do NOT
create count-named future routes such as all37/all42"). Instead this schema
carries a ``strategy_set_fingerprint`` (a SHA-256 of the sorted
``strategy_id@strategy_version`` list) so callers can detect when the active
strategy set has changed without the schema itself naming a count.
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
MIGRATION_NAME = "create_p638_current_ranking_schema"
BUSY_TIMEOUT_MS = 5_000

CONTRACT_VERSION = "P638_HISTORICAL_RESULTS_CURRENT_PRIZE_RANKING_V1"

TABLE_NAMES = (
    "p638_current_schema_migrations",
    "p638_current_run",
    "p638_current_strategy",
    "p638_current_target",
    "p638_current_ticket",
    "p638_current_ranking",
)


class P638CurrentRankingSchemaError(RuntimeError):
    """The P638 current-universe ranking database path or schema failed a safety check."""


class P638CurrentRankingSchemaMigrationError(P638CurrentRankingSchemaError):
    """The P638 current-universe ranking database schema is absent, corrupt, or drifted."""


class P638CurrentRankingSchemaChecksumError(P638CurrentRankingSchemaMigrationError):
    """A recorded migration does not match the code-owned migration."""


@dataclass(frozen=True, slots=True)
class P638CurrentRankingDatabasePaths:
    """Resolved path only; constructing this value never creates or opens anything."""

    database: Path


MIGRATION_STATEMENTS = (
    """
    CREATE TABLE p638_current_schema_migrations (
        version INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        checksum TEXT NOT NULL,
        applied_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE p638_current_run (
        run_id TEXT PRIMARY KEY,
        contract_version TEXT NOT NULL CHECK (
            contract_version = 'P638_HISTORICAL_RESULTS_CURRENT_PRIZE_RANKING_V1'
        ),
        lottery_type TEXT NOT NULL CHECK (lottery_type = 'POWER_LOTTO'),
        strategy_set_fingerprint TEXT NOT NULL CHECK (length(strategy_set_fingerprint) = 64),
        source_replay_db_sha256 TEXT NOT NULL CHECK (length(source_replay_db_sha256) = 64),
        source_draw_db_sha256 TEXT NOT NULL CHECK (length(source_draw_db_sha256) = 64),
        draw_count INTEGER NOT NULL CHECK (draw_count >= 0),
        first_draw_number TEXT NOT NULL,
        last_draw_number TEXT NOT NULL,
        strategy_count INTEGER NOT NULL CHECK (strategy_count >= 1),
        excluded_strategy_count INTEGER NOT NULL CHECK (excluded_strategy_count = 0),
        eligible_target_failure_count INTEGER NOT NULL CHECK (eligible_target_failure_count = 0),
        prize_rule_version TEXT NOT NULL,
        prize_rule_provenance TEXT NOT NULL,
        created_at TEXT NOT NULL,
        completed_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE p638_current_strategy (
        run_id TEXT NOT NULL,
        strategy_id TEXT NOT NULL,
        strategy_version TEXT NOT NULL,
        native_ticket_count INTEGER NOT NULL CHECK (native_ticket_count > 0),
        min_history INTEGER NOT NULL CHECK (min_history >= 0),
        source_paths_json TEXT NOT NULL,
        provenance TEXT NOT NULL,
        PRIMARY KEY (run_id, strategy_id),
        FOREIGN KEY (run_id) REFERENCES p638_current_run(run_id) ON DELETE RESTRICT
    )
    """,
    """
    CREATE TABLE p638_current_target (
        id TEXT PRIMARY KEY,
        run_id TEXT NOT NULL,
        strategy_id TEXT NOT NULL,
        strategy_version TEXT NOT NULL,
        target_draw_number TEXT NOT NULL,
        target_draw_date TEXT NOT NULL,
        cutoff_draw_number TEXT NULL,
        history_length INTEGER NOT NULL CHECK (history_length >= 0),
        expected_ticket_count INTEGER NOT NULL CHECK (expected_ticket_count > 0),
        status TEXT NOT NULL CHECK (status IN (
            'COMPLETE',
            'EXCLUDED_INSUFFICIENT_HISTORY',
            'EXCLUDED_SOURCE_NATIVE_PORTFOLIO_CLOSURE'
        )),
        target_is_winner INTEGER NULL CHECK (target_is_winner IN (0, 1)),
        UNIQUE (run_id, strategy_id, target_draw_number),
        FOREIGN KEY (run_id, strategy_id)
            REFERENCES p638_current_strategy(run_id, strategy_id) ON DELETE RESTRICT
    )
    """,
    """
    CREATE TABLE p638_current_ticket (
        id TEXT PRIMARY KEY,
        target_id TEXT NOT NULL,
        run_id TEXT NOT NULL,
        strategy_id TEXT NOT NULL,
        target_draw_number TEXT NOT NULL,
        ticket_position INTEGER NOT NULL CHECK (ticket_position > 0),
        predicted_zone1_numbers_json TEXT NOT NULL,
        predicted_zone2_number INTEGER NOT NULL CHECK (predicted_zone2_number BETWEEN 1 AND 8),
        actual_zone1_numbers_json TEXT NOT NULL,
        actual_zone2_number INTEGER NOT NULL CHECK (actual_zone2_number BETWEEN 1 AND 8),
        zone1_hit_count INTEGER NOT NULL CHECK (zone1_hit_count BETWEEN 0 AND 6),
        zone2_hit INTEGER NOT NULL CHECK (zone2_hit IN (0, 1)),
        is_winner INTEGER NOT NULL CHECK (is_winner IN (0, 1)),
        prize_tier TEXT NULL,
        prize_tier_order INTEGER NULL CHECK (
            prize_tier_order IS NULL OR prize_tier_order BETWEEN 1 AND 10
        ),
        UNIQUE (target_id, ticket_position),
        FOREIGN KEY (target_id) REFERENCES p638_current_target(id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE p638_current_ranking (
        run_id TEXT NOT NULL,
        strategy_id TEXT NOT NULL,
        rank INTEGER NOT NULL CHECK (rank >= 1),
        strategy_version TEXT NOT NULL,
        native_ticket_count INTEGER NOT NULL CHECK (native_ticket_count > 0),
        eligible_target_count INTEGER NOT NULL CHECK (eligible_target_count >= 0),
        winning_target_count INTEGER NOT NULL CHECK (winning_target_count >= 0),
        winning_target_rate REAL NOT NULL CHECK (
            winning_target_rate >= 0.0 AND winning_target_rate <= 1.0
        ),
        total_complete_ticket_count INTEGER NOT NULL CHECK (total_complete_ticket_count >= 0),
        winning_ticket_count INTEGER NOT NULL CHECK (winning_ticket_count >= 0),
        ticket_winning_rate REAL NOT NULL CHECK (
            ticket_winning_rate >= 0.0 AND ticket_winning_rate <= 1.0
        ),
        prize_tier_counts_json TEXT NOT NULL,
        highest_prize_tier_achieved TEXT NULL,
        first_eligible_draw TEXT NULL,
        last_eligible_draw TEXT NULL,
        prize_rule_version TEXT NOT NULL,
        prize_rule_provenance TEXT NOT NULL,
        provenance TEXT NOT NULL,
        PRIMARY KEY (run_id, strategy_id),
        UNIQUE (run_id, rank),
        FOREIGN KEY (run_id, strategy_id)
            REFERENCES p638_current_strategy(run_id, strategy_id) ON DELETE RESTRICT
    )
    """,
    """
    CREATE INDEX idx_p638_current_target_query
    ON p638_current_target (run_id, strategy_id, target_draw_date, target_draw_number, status)
    """,
    """
    CREATE INDEX idx_p638_current_ticket_query
    ON p638_current_ticket (run_id, strategy_id, target_draw_number, ticket_position)
    """,
    """
    CREATE INDEX idx_p638_current_ranking_rank
    ON p638_current_ranking (run_id, rank)
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
        raise P638CurrentRankingSchemaError("cannot determine schema object name")
    return match.group(1)


_EXPECTED_SCHEMA_SQL_BY_NAME = {
    _object_name(statement): statement for statement in MIGRATION_STATEMENTS
}


def resolve_p638_current_ranking_database_paths(
    database: Path,
) -> P638CurrentRankingDatabasePaths:
    """Validate an explicit, caller-owned database path. Never creates anything."""

    if "\x00" in str(database):
        raise P638CurrentRankingSchemaError("database path contains a null byte")
    if not database.is_absolute():
        raise P638CurrentRankingSchemaError("database path must be absolute")
    if any(part.casefold() == "lotterynew" for part in database.parts):
        raise P638CurrentRankingSchemaError("LotteryNew paths are forbidden")
    return P638CurrentRankingDatabasePaths(database=database)


def initialize_schema(database: Path) -> None:
    """Securely create a P638 current-universe ranking database.

    Idempotent: a call against an already-initialized current database is a
    read-only semantic verification, not a rewrite.
    """

    paths = resolve_p638_current_ranking_database_paths(database)
    paths.database.parent.mkdir(parents=True, exist_ok=True)
    with _raw_connection(paths) as connection:
        try:
            connection.execute("PRAGMA foreign_keys = OFF")
            if connection.execute("PRAGMA foreign_keys").fetchone() != (0,):
                raise P638CurrentRankingSchemaMigrationError(
                    "cannot suspend foreign keys for atomic table rebuild"
                )
            connection.execute("BEGIN IMMEDIATE")
            try:
                version = _verify_migration_state(connection)
                if version is None:
                    for statement in MIGRATION_STATEMENTS:
                        connection.execute(statement)
                    connection.execute(
                        """
                        INSERT INTO p638_current_schema_migrations
                            (version, name, checksum, applied_at)
                        VALUES (?, ?, ?, ?)
                        """,
                        (1, MIGRATION_NAME, MIGRATION_CHECKSUM, _utc_now()),
                    )
                    version = _verify_migration_state(connection)
                if version != CURRENT_SCHEMA_VERSION:
                    raise P638CurrentRankingSchemaMigrationError(
                        f"P638 current-universe ranking schema migration did not reach version "
                        f"{CURRENT_SCHEMA_VERSION}"
                    )
                if connection.execute("PRAGMA foreign_key_check").fetchall():
                    raise P638CurrentRankingSchemaMigrationError(
                        "P638 current-universe ranking schema migration left foreign-key "
                        "violations"
                    )
            except BaseException:
                connection.rollback()
                raise
            else:
                connection.commit()
        finally:
            connection.execute("PRAGMA foreign_keys = ON")
            if connection.execute("PRAGMA foreign_keys").fetchone() != (1,):
                raise P638CurrentRankingSchemaMigrationError(
                    "cannot restore SQLite foreign-key enforcement"
                )


def verify_schema_read_only(database: Path) -> bool:
    """Return False for an absent DB; validate an existing DB without creating it."""

    paths = resolve_p638_current_ranking_database_paths(database)
    if not paths.database.exists():
        return False
    with _raw_connection(paths, read_only=True) as connection:
        initialized = _verify_migration_state(connection)
    if not initialized:
        raise P638CurrentRankingSchemaMigrationError("database exists without a schema migration")
    return True


@contextmanager
def open_database(database: Path, *, read_only: bool = False) -> Generator[sqlite3.Connection]:
    """Open a fresh connection to an existing verified current database."""

    paths = resolve_p638_current_ranking_database_paths(database)
    if not paths.database.exists():
        raise P638CurrentRankingSchemaMigrationError(
            "P638 current-universe ranking database does not exist"
        )
    with _raw_connection(paths, read_only=read_only) as connection:
        if not _verify_migration_state(connection):
            raise P638CurrentRankingSchemaMigrationError(
                "database exists without a schema migration"
            )
        yield connection


@contextmanager
def _raw_connection(
    paths: P638CurrentRankingDatabasePaths, *, read_only: bool = False
) -> Generator[sqlite3.Connection]:
    mode = "ro" if read_only else "rwc"
    uri = f"{paths.database.as_uri()}?mode={mode}"
    try:
        connection = sqlite3.connect(
            uri, uri=True, timeout=BUSY_TIMEOUT_MS / 1_000, isolation_level=None
        )
    except sqlite3.DatabaseError as exc:
        raise P638CurrentRankingSchemaMigrationError(
            "cannot open the P638 current-universe ranking database safely"
        ) from exc
    try:
        try:
            connection.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}")
            connection.execute("PRAGMA foreign_keys = ON")
            if connection.execute("PRAGMA foreign_keys").fetchone() != (1,):
                raise P638CurrentRankingSchemaMigrationError(
                    "SQLite foreign-key enforcement is unavailable"
                )
            if read_only:
                connection.execute("PRAGMA query_only = ON")
        except sqlite3.DatabaseError as exc:
            raise P638CurrentRankingSchemaMigrationError("cannot configure SQLite safely") from exc
        yield connection
    finally:
        connection.close()


def _verify_migration_state(connection: sqlite3.Connection) -> int | None:
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
    if "p638_current_schema_migrations" not in table_names:
        if table_names:
            raise P638CurrentRankingSchemaMigrationError(
                "unversioned database contains application tables"
            )
        return None

    rows = connection.execute(
        "SELECT version, name, checksum FROM p638_current_schema_migrations ORDER BY version"
    ).fetchall()
    try:
        versions = [int(row[0]) for row in rows]
    except (TypeError, ValueError) as exc:
        raise P638CurrentRankingSchemaMigrationError("migration versions are invalid") from exc
    if any(version > CURRENT_SCHEMA_VERSION for version in versions):
        raise P638CurrentRankingSchemaMigrationError(
            "database schema is newer than this LottoLab build"
        )
    if versions != [1]:
        raise P638CurrentRankingSchemaMigrationError("migration history is incomplete")
    _, name, checksum = rows[0]
    if name != MIGRATION_NAME or checksum != MIGRATION_CHECKSUM:
        raise P638CurrentRankingSchemaChecksumError("migration checksum does not match")

    version = versions[-1]
    _verify_schema_semantics(connection, table_names)
    return version


def _verify_schema_semantics(connection: sqlite3.Connection, table_names: set[str]) -> None:
    if table_names != set(TABLE_NAMES):
        raise P638CurrentRankingSchemaMigrationError("database tables do not match the schema")

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
            raise P638CurrentRankingSchemaMigrationError(
                f"unexpected database schema object: {name}"
            )
        if _canonical_schema_sql(actual_sql) != _canonical_schema_sql(expected_sql):
            raise P638CurrentRankingSchemaMigrationError(
                f"database schema SQL does not match the current schema: {name}"
            )
    if seen_names != set(_EXPECTED_SCHEMA_SQL_BY_NAME):
        raise P638CurrentRankingSchemaMigrationError("database schema objects do not match")

    for table in TABLE_NAMES:
        foreign_keys = connection.execute(f"PRAGMA foreign_key_list({table})").fetchall()
        for fk_row in foreign_keys:
            on_delete = str(fk_row[6])
            if on_delete not in ("RESTRICT", "CASCADE"):
                raise P638CurrentRankingSchemaMigrationError(
                    f"unexpected foreign-key action on {table}: {on_delete}"
                )


def _utc_now() -> str:
    from datetime import UTC, datetime

    return datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


__all__ = [
    "CONTRACT_VERSION",
    "CURRENT_SCHEMA_VERSION",
    "TABLE_NAMES",
    "P638CurrentRankingDatabasePaths",
    "P638CurrentRankingSchemaChecksumError",
    "P638CurrentRankingSchemaError",
    "P638CurrentRankingSchemaMigrationError",
    "initialize_schema",
    "open_database",
    "resolve_p638_current_ranking_database_paths",
    "verify_schema_read_only",
]
