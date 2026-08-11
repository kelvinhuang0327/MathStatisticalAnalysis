"""BLHQ R1: dedicated, versioned, idempotent SQLite schema for historical results.

A standalone schema module, deliberately not sharing anything with
``draw_schema.py``: R1 constructors take an explicit database path (no
``LOTTOLAB_DATA_DIR`` resolution, no canonical/default production DB). Mirrors
``draw_schema.py``'s versioned-migration and semantic-drift-detection pattern
at a scope appropriate to a dedicated, test-owned database.
"""

from __future__ import annotations

import hashlib
import re
import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

CURRENT_SCHEMA_VERSION = 4
MIGRATION_NAME = "create_historical_results_schema"
V2_MIGRATION_NAME = "expand_historical_lottery_types"
P638_MIGRATION_NAME = "add_powerlotto_replay_extension"
V4_MIGRATION_NAME = "allow_p638_source_native_portfolio_closure"
BUSY_TIMEOUT_MS = 5_000

BASE_TABLE_NAMES = (
    "historical_schema_migrations",
    "historical_result_run",
    "historical_strategy_snapshot",
    "historical_draw_snapshot",
    "historical_portfolio",
    "historical_ticket",
    "historical_count_summary",
)

P638_TABLE_NAMES = (
    "historical_p638_run",
    "historical_p638_strategy_ledger",
    "historical_p638_target",
    "historical_p638_ticket",
)

TABLE_NAMES = BASE_TABLE_NAMES + P638_TABLE_NAMES


class HistoricalSchemaError(RuntimeError):
    """The historical-results database path or schema failed a safety check."""


class HistoricalSchemaMigrationError(HistoricalSchemaError):
    """The historical-results database schema is absent, corrupt, or drifted."""


class HistoricalSchemaChecksumError(HistoricalSchemaMigrationError):
    """A recorded migration does not match the code-owned migration."""


@dataclass(frozen=True, slots=True)
class HistoricalDatabasePaths:
    """Resolved path only; constructing this value never creates or opens anything."""

    database: Path


MIGRATION_STATEMENTS = (
    """
    CREATE TABLE historical_schema_migrations (
        version INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        checksum TEXT NOT NULL,
        applied_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE historical_result_run (
        id TEXT PRIMARY KEY,
        import_identity_sha256 TEXT NOT NULL CHECK (length(import_identity_sha256) = 64),
        manifest_sha256 TEXT NOT NULL CHECK (length(manifest_sha256) = 64),
        contract_version TEXT NOT NULL,
        source_kind TEXT NOT NULL,
        source_repository TEXT NOT NULL,
        source_commit_oid TEXT NOT NULL CHECK (length(source_commit_oid) = 40),
        source_artifact_sha256 TEXT NOT NULL CHECK (length(source_artifact_sha256) = 64),
        dataset_identity TEXT NOT NULL,
        dataset_sha256 TEXT NOT NULL CHECK (length(dataset_sha256) = 64),
        legacy_run_id TEXT NULL,
        lottery_type TEXT NOT NULL CHECK (lottery_type = 'BIG_LOTTO'),
        status TEXT NOT NULL CHECK (status IN ('IN_PROGRESS', 'COMPLETED', 'FAILED')),
        started_at TEXT NOT NULL,
        completed_at TEXT NULL,
        error_code TEXT NULL,
        error_summary TEXT NULL,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE historical_strategy_snapshot (
        id TEXT PRIMARY KEY,
        run_id TEXT NOT NULL,
        strategy_id TEXT NOT NULL,
        effective_strategy_id TEXT NOT NULL,
        strategy_version TEXT NOT NULL,
        replicate INTEGER NOT NULL CHECK (replicate >= 1),
        identity_kind TEXT NOT NULL CHECK (identity_kind IN ('REAL', 'SYNTHETIC_TEST_ONLY')),
        governance_status TEXT NOT NULL CHECK (
            governance_status IN (
                'ONLINE', 'UNKNOWN', 'REJECTED', 'RETIRED', 'DELETED', 'CANDIDATE'
            )
        ),
        alias_of_strategy_id TEXT NULL,
        equivalence_group TEXT NULL,
        nested_prefix_supported INTEGER NOT NULL CHECK (nested_prefix_supported IN (0, 1)),
        descriptor_sha256 TEXT NOT NULL CHECK (length(descriptor_sha256) = 64),
        created_at TEXT NOT NULL,
        UNIQUE (run_id, strategy_id, strategy_version, replicate),
        FOREIGN KEY (run_id) REFERENCES historical_result_run(id) ON DELETE RESTRICT
    )
    """,
    """
    CREATE TABLE historical_draw_snapshot (
        id INTEGER PRIMARY KEY,
        run_id TEXT NOT NULL,
        lottery_type TEXT NOT NULL CHECK (lottery_type = 'BIG_LOTTO'),
        draw_number TEXT NOT NULL,
        draw_date TEXT NOT NULL,
        main_numbers_json TEXT NOT NULL,
        special_numbers_json TEXT NOT NULL,
        draw_sha256 TEXT NOT NULL CHECK (length(draw_sha256) = 64),
        created_at TEXT NOT NULL,
        UNIQUE (run_id, lottery_type, draw_number),
        FOREIGN KEY (run_id) REFERENCES historical_result_run(id) ON DELETE RESTRICT
    )
    """,
    """
    CREATE TABLE historical_portfolio (
        id TEXT PRIMARY KEY,
        run_id TEXT NOT NULL,
        strategy_snapshot_id TEXT NOT NULL,
        target_draw_snapshot_id INTEGER NOT NULL,
        cutoff_draw_snapshot_id INTEGER NOT NULL,
        constructor_identifier TEXT NOT NULL,
        portfolio_sha256 TEXT NOT NULL CHECK (length(portfolio_sha256) = 64),
        prefix10_sha256 TEXT NOT NULL CHECK (length(prefix10_sha256) = 64),
        prefix15_sha256 TEXT NOT NULL CHECK (length(prefix15_sha256) = 64),
        source_record_locator TEXT NULL,
        created_at TEXT NOT NULL,
        UNIQUE (run_id, strategy_snapshot_id, target_draw_snapshot_id),
        FOREIGN KEY (run_id) REFERENCES historical_result_run(id) ON DELETE RESTRICT,
        FOREIGN KEY (strategy_snapshot_id)
            REFERENCES historical_strategy_snapshot(id) ON DELETE RESTRICT,
        FOREIGN KEY (target_draw_snapshot_id)
            REFERENCES historical_draw_snapshot(id) ON DELETE RESTRICT,
        FOREIGN KEY (cutoff_draw_snapshot_id)
            REFERENCES historical_draw_snapshot(id) ON DELETE RESTRICT
    )
    """,
    """
    CREATE TABLE historical_ticket (
        id INTEGER PRIMARY KEY,
        portfolio_id TEXT NOT NULL,
        portfolio_position INTEGER NOT NULL CHECK (portfolio_position BETWEEN 1 AND 20),
        main_numbers_json TEXT NOT NULL,
        special_numbers_json TEXT NOT NULL,
        main_hit_count INTEGER NOT NULL CHECK (main_hit_count >= 0),
        special_hit INTEGER NOT NULL CHECK (special_hit IN (0, 1)),
        ticket_sha256 TEXT NOT NULL CHECK (length(ticket_sha256) = 64),
        legacy_row_id TEXT NULL,
        legacy_storage_bet_index INTEGER NULL,
        UNIQUE (portfolio_id, portfolio_position),
        FOREIGN KEY (portfolio_id) REFERENCES historical_portfolio(id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE historical_count_summary (
        id INTEGER PRIMARY KEY,
        run_id TEXT NOT NULL,
        strategy_snapshot_id TEXT NOT NULL,
        ticket_count INTEGER NOT NULL CHECK (ticket_count IN (10, 15, 20)),
        evaluated_draws INTEGER NOT NULL CHECK (evaluated_draws >= 0),
        complete_portfolios INTEGER NOT NULL CHECK (complete_portfolios >= 0),
        m4plus_hit_count INTEGER NOT NULL CHECK (m4plus_hit_count >= 0),
        created_at TEXT NOT NULL,
        UNIQUE (run_id, strategy_snapshot_id, ticket_count),
        FOREIGN KEY (run_id) REFERENCES historical_result_run(id) ON DELETE RESTRICT,
        FOREIGN KEY (strategy_snapshot_id)
            REFERENCES historical_strategy_snapshot(id) ON DELETE RESTRICT
    )
    """,
    """
    CREATE UNIQUE INDEX idx_historical_result_run_identity_completed
    ON historical_result_run (import_identity_sha256)
    WHERE status = 'COMPLETED'
    """,
    """
    CREATE INDEX idx_historical_result_run_history
    ON historical_result_run (started_at DESC, id DESC)
    """,
)

MIGRATION_SQL = ";\n".join(statement.strip() for statement in MIGRATION_STATEMENTS) + ";\n"
MIGRATION_CHECKSUM = hashlib.sha256(MIGRATION_SQL.encode("utf-8")).hexdigest()

V2_RESULT_RUN_TABLE_SQL = """
CREATE TABLE historical_result_run_v2 (
    id TEXT PRIMARY KEY,
    import_identity_sha256 TEXT NOT NULL CHECK (length(import_identity_sha256) = 64),
    manifest_sha256 TEXT NOT NULL CHECK (length(manifest_sha256) = 64),
    contract_version TEXT NOT NULL,
    source_kind TEXT NOT NULL,
    source_repository TEXT NOT NULL,
    source_commit_oid TEXT NOT NULL CHECK (length(source_commit_oid) = 40),
    source_artifact_sha256 TEXT NOT NULL CHECK (length(source_artifact_sha256) = 64),
    dataset_identity TEXT NOT NULL,
    dataset_sha256 TEXT NOT NULL CHECK (length(dataset_sha256) = 64),
    legacy_run_id TEXT NULL,
    lottery_type TEXT NOT NULL CHECK (
        lottery_type IN ('DAILY_539', 'BIG_LOTTO', 'POWER_LOTTO')
    ),
    status TEXT NOT NULL CHECK (status IN ('IN_PROGRESS', 'COMPLETED', 'FAILED')),
    started_at TEXT NOT NULL,
    completed_at TEXT NULL,
    error_code TEXT NULL,
    error_summary TEXT NULL,
    created_at TEXT NOT NULL
)
"""

V2_DRAW_SNAPSHOT_TABLE_SQL = """
CREATE TABLE historical_draw_snapshot_v2 (
    id INTEGER PRIMARY KEY,
    run_id TEXT NOT NULL,
    lottery_type TEXT NOT NULL CHECK (
        lottery_type IN ('DAILY_539', 'BIG_LOTTO', 'POWER_LOTTO')
    ),
    draw_number TEXT NOT NULL,
    draw_date TEXT NOT NULL,
    main_numbers_json TEXT NOT NULL,
    special_numbers_json TEXT NOT NULL,
    draw_sha256 TEXT NOT NULL CHECK (length(draw_sha256) = 64),
    created_at TEXT NOT NULL,
    UNIQUE (run_id, lottery_type, draw_number),
    FOREIGN KEY (run_id) REFERENCES historical_result_run(id) ON DELETE RESTRICT
)
"""

V2_MIGRATION_STATEMENTS = (
    "PRAGMA defer_foreign_keys = ON",
    V2_RESULT_RUN_TABLE_SQL,
    """
    INSERT INTO historical_result_run_v2
    SELECT * FROM historical_result_run
    """,
    V2_DRAW_SNAPSHOT_TABLE_SQL,
    """
    INSERT INTO historical_draw_snapshot_v2
    SELECT * FROM historical_draw_snapshot
    """,
    "DROP TABLE historical_draw_snapshot",
    "ALTER TABLE historical_draw_snapshot_v2 RENAME TO historical_draw_snapshot",
    "DROP TABLE historical_result_run",
    "ALTER TABLE historical_result_run_v2 RENAME TO historical_result_run",
    """
    CREATE UNIQUE INDEX idx_historical_result_run_identity_completed
    ON historical_result_run (import_identity_sha256)
    WHERE status = 'COMPLETED'
    """,
    """
    CREATE INDEX idx_historical_result_run_history
    ON historical_result_run (started_at DESC, id DESC)
    """,
    """
    CREATE INDEX idx_historical_result_run_lottery_completed
    ON historical_result_run (lottery_type, completed_at DESC, id DESC)
    WHERE status = 'COMPLETED'
    """,
)
V2_MIGRATION_SQL = ";\n".join(statement.strip() for statement in V2_MIGRATION_STATEMENTS) + ";\n"
V2_MIGRATION_CHECKSUM = hashlib.sha256(V2_MIGRATION_SQL.encode("utf-8")).hexdigest()

P638_MIGRATION_STATEMENTS = (
    """
    CREATE TABLE historical_p638_run (
        run_id TEXT PRIMARY KEY,
        lottery_type TEXT NOT NULL CHECK (lottery_type = 'POWER_LOTTO'),
        source_run_id TEXT NOT NULL,
        source_replay_sha256 TEXT NOT NULL CHECK (length(source_replay_sha256) = 64),
        source_draw_db_sha256 TEXT NOT NULL CHECK (length(source_draw_db_sha256) = 64),
        source_content_sha256 TEXT NOT NULL CHECK (length(source_content_sha256) = 64),
        second_zone_ssot_version TEXT NOT NULL,
        total_source_targets INTEGER NOT NULL CHECK (total_source_targets >= 0),
        selected_strategy_count INTEGER NOT NULL CHECK (selected_strategy_count >= 0),
        draw_count INTEGER NOT NULL CHECK (draw_count >= 0),
        eligible_attempts INTEGER NOT NULL CHECK (eligible_attempts >= 0),
        complete_targets INTEGER NOT NULL CHECK (complete_targets >= 0),
        excluded_targets INTEGER NOT NULL CHECK (excluded_targets >= 0),
        failed_targets INTEGER NOT NULL CHECK (failed_targets >= 0),
        ticket_rows INTEGER NOT NULL CHECK (ticket_rows >= 0),
        provenance_json TEXT NOT NULL,
        created_at TEXT NOT NULL,
        completed_at TEXT NOT NULL,
        FOREIGN KEY (run_id) REFERENCES historical_result_run(id) ON DELETE RESTRICT
    )
    """,
    """
    CREATE TABLE historical_p638_strategy_ledger (
        strategy_snapshot_id TEXT PRIMARY KEY,
        run_id TEXT NOT NULL,
        strategy_id TEXT NOT NULL,
        strategy_version TEXT NOT NULL,
        lottery_type TEXT NOT NULL CHECK (lottery_type = 'POWER_LOTTO'),
        display_label TEXT NOT NULL,
        executable INTEGER NOT NULL CHECK (executable IN (0, 1)),
        adapter_path TEXT NULL,
        native_ticket_count INTEGER NULL CHECK (
            native_ticket_count IS NULL OR native_ticket_count > 0
        ),
        min_history INTEGER NULL CHECK (min_history IS NULL OR min_history >= 0),
        zone1_contract TEXT NOT NULL,
        zone2_contract TEXT NOT NULL,
        lifecycle_status TEXT NOT NULL,
        replay_status TEXT NOT NULL CHECK (
            replay_status IN (
                'R4_RESULT_REUSABLE', 'REPLAY_REQUIRED', 'REPLAY_COMPLETED',
                'EXCLUDED_NON_EXECUTABLE', 'EXCLUDED_DONOR_DEFECT',
                'EXCLUDED_UNRESOLVED_CONTRACT', 'RETIRED', 'IDENTITY_CONFLICT'
            )
        ),
        source_run_id TEXT NULL,
        source_replay_sha256 TEXT NULL CHECK (
            source_replay_sha256 IS NULL OR length(source_replay_sha256) = 64
        ),
        source_paths_json TEXT NOT NULL,
        provenance TEXT NOT NULL,
        exclusion_reason TEXT NULL,
        UNIQUE (run_id, strategy_id, strategy_version),
        FOREIGN KEY (run_id) REFERENCES historical_result_run(id) ON DELETE RESTRICT,
        FOREIGN KEY (strategy_snapshot_id) REFERENCES historical_strategy_snapshot(id)
            ON DELETE RESTRICT
    )
    """,
    """
    CREATE TABLE historical_p638_target (
        id TEXT PRIMARY KEY,
        run_id TEXT NOT NULL,
        strategy_snapshot_id TEXT NOT NULL,
        strategy_id TEXT NOT NULL,
        strategy_version TEXT NOT NULL,
        target_draw_snapshot_id INTEGER NOT NULL,
        cutoff_draw_snapshot_id INTEGER NULL,
        target_draw_number TEXT NOT NULL,
        target_draw_date TEXT NOT NULL,
        history_boundary_draw_number TEXT NULL,
        history_boundary_date TEXT NULL,
        history_length INTEGER NOT NULL CHECK (history_length >= 0),
        expected_ticket_count INTEGER NOT NULL CHECK (expected_ticket_count > 0),
        status TEXT NOT NULL CHECK (
            status IN ('COMPLETE', 'EXCLUDED_INSUFFICIENT_HISTORY', 'FAILED')
        ),
        exclusion_reason TEXT NULL,
        failure_reason TEXT NULL,
        source_target_locator TEXT NULL,
        UNIQUE (run_id, strategy_id, strategy_version, target_draw_number),
        FOREIGN KEY (run_id) REFERENCES historical_result_run(id) ON DELETE RESTRICT,
        FOREIGN KEY (strategy_snapshot_id) REFERENCES historical_p638_strategy_ledger(
            strategy_snapshot_id
        ) ON DELETE RESTRICT,
        FOREIGN KEY (target_draw_snapshot_id) REFERENCES historical_draw_snapshot(id)
            ON DELETE RESTRICT,
        FOREIGN KEY (cutoff_draw_snapshot_id) REFERENCES historical_draw_snapshot(id)
            ON DELETE RESTRICT
    )
    """,
    """
    CREATE TABLE historical_p638_ticket (
        id TEXT PRIMARY KEY,
        target_id TEXT NOT NULL,
        run_id TEXT NOT NULL,
        strategy_id TEXT NOT NULL,
        strategy_version TEXT NOT NULL,
        target_draw_number TEXT NOT NULL,
        ticket_position INTEGER NOT NULL CHECK (ticket_position > 0),
        predicted_zone1_numbers_json TEXT NOT NULL,
        predicted_zone2_number INTEGER NOT NULL CHECK (predicted_zone2_number BETWEEN 1 AND 8),
        actual_zone1_numbers_json TEXT NOT NULL,
        actual_zone2_number INTEGER NOT NULL CHECK (actual_zone2_number BETWEEN 1 AND 8),
        zone1_hit_count INTEGER NOT NULL CHECK (zone1_hit_count BETWEEN 0 AND 6),
        zone2_hit INTEGER NOT NULL CHECK (zone2_hit IN (0, 1)),
        status TEXT NOT NULL CHECK (status = 'COMPLETE'),
        source_run_id TEXT NOT NULL,
        source_replay_sha256 TEXT NOT NULL CHECK (length(source_replay_sha256) = 64),
        source_record_locator TEXT NULL,
        second_zone_ssot_version TEXT NOT NULL,
        provenance TEXT NOT NULL,
        UNIQUE (target_id, ticket_position),
        FOREIGN KEY (target_id) REFERENCES historical_p638_target(id) ON DELETE CASCADE,
        FOREIGN KEY (run_id) REFERENCES historical_result_run(id) ON DELETE RESTRICT
    )
    """,
    """
    CREATE INDEX idx_historical_p638_strategy_run_status
    ON historical_p638_strategy_ledger (run_id, replay_status, strategy_id)
    """,
    """
    CREATE INDEX idx_historical_p638_target_query
    ON historical_p638_target (
        run_id, strategy_id, target_draw_date, target_draw_number, status
    )
    """,
    """
    CREATE INDEX idx_historical_p638_ticket_query
    ON historical_p638_ticket (
        run_id, strategy_id, target_draw_number, ticket_position
    )
    """,
)
P638_MIGRATION_SQL = (
    ";\n".join(statement.strip() for statement in P638_MIGRATION_STATEMENTS) + ";\n"
)
P638_MIGRATION_CHECKSUM = hashlib.sha256(P638_MIGRATION_SQL.encode("utf-8")).hexdigest()

V4_P638_TARGET_TABLE_SQL = """
CREATE TABLE historical_p638_target_v4 (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    strategy_snapshot_id TEXT NOT NULL,
    strategy_id TEXT NOT NULL,
    strategy_version TEXT NOT NULL,
    target_draw_snapshot_id INTEGER NOT NULL,
    cutoff_draw_snapshot_id INTEGER NULL,
    target_draw_number TEXT NOT NULL,
    target_draw_date TEXT NOT NULL,
    history_boundary_draw_number TEXT NULL,
    history_boundary_date TEXT NULL,
    history_length INTEGER NOT NULL CHECK (history_length >= 0),
    expected_ticket_count INTEGER NOT NULL CHECK (expected_ticket_count > 0),
    status TEXT NOT NULL CHECK (
        status IN (
            'COMPLETE', 'EXCLUDED_INSUFFICIENT_HISTORY',
            'EXCLUDED_SOURCE_NATIVE_PORTFOLIO_CLOSURE', 'FAILED'
        )
    ),
    exclusion_reason TEXT NULL,
    failure_reason TEXT NULL,
    source_target_locator TEXT NULL,
    UNIQUE (run_id, strategy_id, strategy_version, target_draw_number),
    FOREIGN KEY (run_id) REFERENCES historical_result_run(id) ON DELETE RESTRICT,
    FOREIGN KEY (strategy_snapshot_id) REFERENCES historical_p638_strategy_ledger(
        strategy_snapshot_id
    ) ON DELETE RESTRICT,
    FOREIGN KEY (target_draw_snapshot_id) REFERENCES historical_draw_snapshot(id)
        ON DELETE RESTRICT,
    FOREIGN KEY (cutoff_draw_snapshot_id) REFERENCES historical_draw_snapshot(id)
        ON DELETE RESTRICT
)
"""

V4_MIGRATION_STATEMENTS = (
    "PRAGMA defer_foreign_keys = ON",
    V4_P638_TARGET_TABLE_SQL,
    """
    INSERT INTO historical_p638_target_v4 (
        id, run_id, strategy_snapshot_id, strategy_id, strategy_version,
        target_draw_snapshot_id, cutoff_draw_snapshot_id, target_draw_number,
        target_draw_date, history_boundary_draw_number, history_boundary_date,
        history_length, expected_ticket_count, status, exclusion_reason,
        failure_reason, source_target_locator
    )
    SELECT
        id, run_id, strategy_snapshot_id, strategy_id, strategy_version,
        target_draw_snapshot_id, cutoff_draw_snapshot_id, target_draw_number,
        target_draw_date, history_boundary_draw_number, history_boundary_date,
        history_length, expected_ticket_count, status, exclusion_reason,
        failure_reason, source_target_locator
    FROM historical_p638_target
    """,
    "DROP TABLE historical_p638_target",
    "ALTER TABLE historical_p638_target_v4 RENAME TO historical_p638_target",
    """
    CREATE INDEX idx_historical_p638_target_query
    ON historical_p638_target (
        run_id, strategy_id, target_draw_date, target_draw_number, status
    )
    """,
)
V4_MIGRATION_SQL = (
    ";\n".join(statement.strip() for statement in V4_MIGRATION_STATEMENTS) + ";\n"
)
V4_MIGRATION_CHECKSUM = hashlib.sha256(V4_MIGRATION_SQL.encode("utf-8")).hexdigest()

_SCHEMA_SQL_TOKEN = re.compile(
    r"'(?:''|[^'])*'|\"(?:\"\"|[^\"])*\"|`(?:``|[^`])*`|\[[^]]*\]|[(),]|[^\s(),]+"
)
_CREATE_NAME_PATTERN = re.compile(r"CREATE\s+(?:UNIQUE\s+)?(?:TABLE|INDEX)\s+(\w+)", re.IGNORECASE)


def _canonical_schema_sql(sql: str) -> tuple[str, ...]:
    return tuple(token.casefold() for token in _SCHEMA_SQL_TOKEN.findall(sql))


def _object_name(sql: str) -> str:
    match = _CREATE_NAME_PATTERN.search(sql)
    if match is None:
        raise HistoricalSchemaError("cannot determine schema object name")
    return match.group(1)


_EXPECTED_SCHEMA_SQL_BY_NAME = {
    _object_name(statement): statement for statement in MIGRATION_STATEMENTS
}
_EXPECTED_SCHEMA_SQL_BY_NAME_V2 = {
    **_EXPECTED_SCHEMA_SQL_BY_NAME,
    "historical_result_run": V2_RESULT_RUN_TABLE_SQL.replace(
        "historical_result_run_v2", '"historical_result_run"', 1
    ),
    "historical_draw_snapshot": V2_DRAW_SNAPSHOT_TABLE_SQL.replace(
        "historical_draw_snapshot_v2", '"historical_draw_snapshot"', 1
    ),
    "idx_historical_result_run_identity_completed": V2_MIGRATION_STATEMENTS[9],
    "idx_historical_result_run_history": V2_MIGRATION_STATEMENTS[10],
    "idx_historical_result_run_lottery_completed": V2_MIGRATION_STATEMENTS[11],
}
_EXPECTED_SCHEMA_SQL_BY_NAME_V3 = {
    **_EXPECTED_SCHEMA_SQL_BY_NAME_V2,
    **{_object_name(statement): statement for statement in P638_MIGRATION_STATEMENTS},
}
_EXPECTED_SCHEMA_SQL_BY_NAME_V4 = {
    **_EXPECTED_SCHEMA_SQL_BY_NAME_V3,
    "historical_p638_target": V4_P638_TARGET_TABLE_SQL.replace(
        "historical_p638_target_v4", '"historical_p638_target"', 1
    ),
}


def resolve_historical_database_paths(database: Path) -> HistoricalDatabasePaths:
    """Validate an explicit, caller-owned database path. Never creates anything."""

    if "\x00" in str(database):
        raise HistoricalSchemaError("database path contains a null byte")
    if not database.is_absolute():
        raise HistoricalSchemaError("database path must be absolute")
    if any(part.casefold() == "lotterynew" for part in database.parts):
        raise HistoricalSchemaError("LotteryNew paths are forbidden")
    return HistoricalDatabasePaths(database=database)


def initialize_schema(database: Path) -> None:
    """Securely create or atomically upgrade a historical-results database.

    Idempotent: a call against an already-initialized current database is a
    read-only semantic verification, not a rewrite.
    """

    paths = resolve_historical_database_paths(database)
    paths.database.parent.mkdir(parents=True, exist_ok=True)
    with _raw_connection(paths) as connection:
        try:
            connection.execute("PRAGMA foreign_keys = OFF")
            if connection.execute("PRAGMA foreign_keys").fetchone() != (0,):
                raise HistoricalSchemaMigrationError(
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
                        INSERT INTO historical_schema_migrations
                            (version, name, checksum, applied_at)
                        VALUES (?, ?, ?, ?)
                        """,
                        (1, MIGRATION_NAME, MIGRATION_CHECKSUM, _utc_now()),
                    )
                    version = _verify_migration_state(connection)
                if version == 1:
                    for statement in V2_MIGRATION_STATEMENTS:
                        connection.execute(statement)
                    connection.execute(
                        """
                        INSERT INTO historical_schema_migrations
                            (version, name, checksum, applied_at)
                        VALUES (?, ?, ?, ?)
                        """,
                        (
                            2,
                            V2_MIGRATION_NAME,
                            V2_MIGRATION_CHECKSUM,
                            _utc_now(),
                        ),
                    )
                    version = _verify_migration_state(connection)
                if version == 2:
                    for statement in P638_MIGRATION_STATEMENTS:
                        connection.execute(statement)
                    connection.execute(
                        """
                        INSERT INTO historical_schema_migrations
                            (version, name, checksum, applied_at)
                        VALUES (?, ?, ?, ?)
                        """,
                        (
                            3,
                            P638_MIGRATION_NAME,
                            P638_MIGRATION_CHECKSUM,
                            _utc_now(),
                        ),
                    )
                    version = _verify_migration_state(connection)
                if version == 3:
                    for statement in V4_MIGRATION_STATEMENTS:
                        connection.execute(statement)
                    connection.execute(
                        """
                        INSERT INTO historical_schema_migrations
                            (version, name, checksum, applied_at)
                        VALUES (?, ?, ?, ?)
                        """,
                        (
                            CURRENT_SCHEMA_VERSION,
                            V4_MIGRATION_NAME,
                            V4_MIGRATION_CHECKSUM,
                            _utc_now(),
                        ),
                    )
                    version = _verify_migration_state(connection)
                if version != CURRENT_SCHEMA_VERSION:
                    raise HistoricalSchemaMigrationError(
                        f"historical schema migration did not reach version "
                        f"{CURRENT_SCHEMA_VERSION}"
                    )
                if connection.execute("PRAGMA foreign_key_check").fetchall():
                    raise HistoricalSchemaMigrationError(
                        "historical schema migration left foreign-key violations"
                    )
            except BaseException:
                connection.rollback()
                raise
            else:
                connection.commit()
        finally:
            connection.execute("PRAGMA foreign_keys = ON")
            if connection.execute("PRAGMA foreign_keys").fetchone() != (1,):
                raise HistoricalSchemaMigrationError(
                    "cannot restore SQLite foreign-key enforcement"
                )


def verify_schema_read_only(database: Path) -> bool:
    """Return False for an absent DB; validate an existing DB without creating it."""

    paths = resolve_historical_database_paths(database)
    if not paths.database.exists():
        return False
    with _raw_connection(paths, read_only=True) as connection:
        initialized = _verify_migration_state(connection)
    if not initialized:
        raise HistoricalSchemaMigrationError("database exists without a schema migration")
    return True


@contextmanager
def open_database(database: Path, *, read_only: bool = False) -> Generator[sqlite3.Connection]:
    """Open a fresh connection to an existing verified V1 or current database."""

    paths = resolve_historical_database_paths(database)
    if not paths.database.exists():
        raise HistoricalSchemaMigrationError("historical results database does not exist")
    with _raw_connection(paths, read_only=read_only) as connection:
        if not _verify_migration_state(connection):
            raise HistoricalSchemaMigrationError("database exists without a schema migration")
        yield connection


@contextmanager
def _raw_connection(
    paths: HistoricalDatabasePaths, *, read_only: bool = False
) -> Generator[sqlite3.Connection]:
    mode = "ro" if read_only else "rwc"
    uri = f"{paths.database.as_uri()}?mode={mode}"
    try:
        connection = sqlite3.connect(
            uri, uri=True, timeout=BUSY_TIMEOUT_MS / 1_000, isolation_level=None
        )
    except sqlite3.DatabaseError as exc:
        raise HistoricalSchemaMigrationError(
            "cannot open the historical results database safely"
        ) from exc
    try:
        try:
            connection.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}")
            connection.execute("PRAGMA foreign_keys = ON")
            if connection.execute("PRAGMA foreign_keys").fetchone() != (1,):
                raise HistoricalSchemaMigrationError(
                    "SQLite foreign-key enforcement is unavailable"
                )
            if read_only:
                connection.execute("PRAGMA query_only = ON")
        except sqlite3.DatabaseError as exc:
            raise HistoricalSchemaMigrationError("cannot configure SQLite safely") from exc
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
    if "historical_schema_migrations" not in table_names:
        if table_names:
            raise HistoricalSchemaMigrationError("unversioned database contains application tables")
        return None

    rows = connection.execute(
        "SELECT version, name, checksum FROM historical_schema_migrations ORDER BY version"
    ).fetchall()
    try:
        versions = [int(row[0]) for row in rows]
    except (TypeError, ValueError) as exc:
        raise HistoricalSchemaMigrationError("migration versions are invalid") from exc
    if any(version > CURRENT_SCHEMA_VERSION for version in versions):
        raise HistoricalSchemaMigrationError("database schema is newer than this LottoLab build")
    if versions not in ([1], [1, 2], [1, 2, 3], [1, 2, 3, CURRENT_SCHEMA_VERSION]):
        raise HistoricalSchemaMigrationError("migration history is incomplete")
    _, initial_name, initial_checksum = rows[0]
    if initial_name != MIGRATION_NAME or initial_checksum != MIGRATION_CHECKSUM:
        raise HistoricalSchemaChecksumError("migration checksum does not match")
    if len(versions) >= 2:
        _, current_name, current_checksum = rows[1]
        if current_name != V2_MIGRATION_NAME or current_checksum != V2_MIGRATION_CHECKSUM:
            raise HistoricalSchemaChecksumError("migration checksum does not match")
    if len(versions) >= 3:
        _, current_name, current_checksum = rows[2]
        if current_name != P638_MIGRATION_NAME or current_checksum != P638_MIGRATION_CHECKSUM:
            raise HistoricalSchemaChecksumError("migration checksum does not match")
    if versions == [1, 2, 3, CURRENT_SCHEMA_VERSION]:
        _, current_name, current_checksum = rows[3]
        if current_name != V4_MIGRATION_NAME or current_checksum != V4_MIGRATION_CHECKSUM:
            raise HistoricalSchemaChecksumError("migration checksum does not match")

    version = versions[-1]
    _verify_schema_semantics(connection, table_names, version=version)
    return version


def _verify_schema_semantics(
    connection: sqlite3.Connection, table_names: set[str], *, version: int
) -> None:
    expected_table_names = set(TABLE_NAMES) if version >= 3 else set(BASE_TABLE_NAMES)
    if table_names != expected_table_names:
        raise HistoricalSchemaMigrationError(f"database tables do not match version {version}")

    schema_rows = connection.execute(
        """
        SELECT type, name, tbl_name, sql FROM sqlite_schema
        WHERE sql IS NOT NULL AND name NOT LIKE 'sqlite_%'
        ORDER BY type, name
        """
    ).fetchall()
    seen_names: set[str] = set()
    expected_sql_by_name = _EXPECTED_SCHEMA_SQL_BY_NAME
    if version >= 2:
        expected_sql_by_name = {**expected_sql_by_name, **_EXPECTED_SCHEMA_SQL_BY_NAME_V2}
    if version == 3:
        expected_sql_by_name = {**expected_sql_by_name, **_EXPECTED_SCHEMA_SQL_BY_NAME_V3}
    if version >= CURRENT_SCHEMA_VERSION:
        expected_sql_by_name = {**expected_sql_by_name, **_EXPECTED_SCHEMA_SQL_BY_NAME_V4}
    for row in schema_rows:
        name = str(row[1])
        actual_sql = row[3]
        seen_names.add(name)
        expected_sql = expected_sql_by_name.get(name)
        if expected_sql is None or not isinstance(actual_sql, str):
            raise HistoricalSchemaMigrationError(f"unexpected database schema object: {name}")
        if _canonical_schema_sql(actual_sql) != _canonical_schema_sql(expected_sql):
            raise HistoricalSchemaMigrationError(
                f"database schema SQL does not match version {version}: {name}"
            )
    if seen_names != set(expected_sql_by_name):
        raise HistoricalSchemaMigrationError(
            f"database schema objects do not match version {version}"
        )

    tables_to_check = TABLE_NAMES if version >= 3 else BASE_TABLE_NAMES
    for table in tables_to_check:
        foreign_keys = connection.execute(f"PRAGMA foreign_key_list({table})").fetchall()
        for fk_row in foreign_keys:
            on_delete = str(fk_row[6])
            if on_delete not in ("RESTRICT", "CASCADE"):
                raise HistoricalSchemaMigrationError(
                    f"unexpected foreign-key action on {table}: {on_delete}"
                )


def _utc_now() -> str:
    from datetime import UTC, datetime

    return datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")
