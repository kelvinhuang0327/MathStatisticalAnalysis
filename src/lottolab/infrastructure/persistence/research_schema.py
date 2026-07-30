"""Canonical, versioned SQLite schema for prediction and backtest research.

The research store deliberately lives beside, but never inside, ``lottolab.db``.
It owns a durable default locator, uses rollback-journal mode, rejects WAL
sidecars, and fails closed on migration checksum or semantic schema drift.
"""

from __future__ import annotations

import hashlib
import os
import re
import sqlite3
import stat
from collections.abc import Generator, Mapping
from contextlib import contextmanager, suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

DATA_DIRECTORY_ENV = "LOTTOLAB_DATA_DIR"
RESEARCH_DATABASE_FILENAME = "lottolab_research.db"
CURRENT_SCHEMA_VERSION = 2
MIGRATION_NAME = "create_canonical_research_store_with_legacy_provenance"
BUSY_TIMEOUT_MS = 5_000


class ResearchDataError(RuntimeError):
    """The canonical research path failed a safety check."""


class ResearchSchemaError(RuntimeError):
    """The research database schema is absent, corrupt, or incompatible."""


class NewerSchemaVersionError(ResearchSchemaError):
    """The database belongs to a newer LottoLab version."""


class MigrationChecksumError(ResearchSchemaError):
    """A recorded migration does not match the code-owned migration."""


@dataclass(frozen=True, slots=True)
class ResearchDataPaths:
    """Resolved paths only; constructing this value never opens SQLite."""

    data_directory: Path
    database: Path


TABLE_NAMES = (
    "research_schema_migrations",
    "research_rule_contracts",
    "research_artifacts",
    "research_runs",
    "research_strategy_snapshots",
    "research_draw_bindings",
    "research_prediction_targets",
    "research_prediction_tickets",
    "research_execution_closures",
    "research_ticket_results",
    "research_run_status_events",
    "research_run_summaries",
    "research_artifact_custody_events",
    "research_idempotency_keys",
    "research_run_current_pointer",
)

IMMUTABLE_TABLE_NAMES = tuple(
    table for table in TABLE_NAMES if table != "research_run_current_pointer"
)

_BASE_MIGRATION_STATEMENTS = (
    """
    CREATE TABLE research_schema_migrations (
        version INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        checksum TEXT NOT NULL CHECK (length(checksum) = 64),
        applied_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE research_rule_contracts (
        id TEXT PRIMARY KEY,
        lottery_type TEXT NOT NULL,
        contract_version TEXT NOT NULL,
        canonical_payload_json TEXT NOT NULL,
        contract_sha256 TEXT NOT NULL CHECK (length(contract_sha256) = 64),
        created_at TEXT NOT NULL,
        UNIQUE (lottery_type, contract_version, contract_sha256)
    )
    """,
    """
    CREATE TABLE research_artifacts (
        id TEXT PRIMARY KEY,
        artifact_kind TEXT NOT NULL,
        source_locator TEXT NOT NULL,
        media_type TEXT NOT NULL,
        byte_length INTEGER NOT NULL CHECK (byte_length >= 0),
        artifact_sha256 TEXT NOT NULL CHECK (length(artifact_sha256) = 64),
        created_at TEXT NOT NULL,
        UNIQUE (artifact_sha256, artifact_kind)
    )
    """,
    """
    CREATE TABLE research_runs (
        id TEXT PRIMARY KEY,
        run_kind TEXT NOT NULL CHECK (
            run_kind IN (
                'LIVE_PREDICTION',
                'HISTORICAL_REPLAY',
                'HISTORICAL_BACKTEST',
                'REGENERATION',
                'IMPORTED_LEGACY_REPORT',
                'REFERENCE_BASELINE'
            )
        ),
        rule_contract_id TEXT NOT NULL,
        input_dataset_identity TEXT NOT NULL,
        input_dataset_sha256 TEXT NOT NULL CHECK (length(input_dataset_sha256) = 64),
        status TEXT NOT NULL CHECK (
            status IN ('PENDING', 'RUNNING', 'PAUSED', 'COMPLETED', 'FAILED', 'CANCELLED')
        ),
        progress_cursor TEXT,
        expected_target_count INTEGER NOT NULL CHECK (expected_target_count >= 0),
        supersedes_run_id TEXT,
        derived_from_run_id TEXT,
        imported_from_artifact_id TEXT,
        producer_identity TEXT NOT NULL,
        execution_code_version TEXT NOT NULL,
        source_commit_oid TEXT NOT NULL,
        started_at TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY (rule_contract_id)
            REFERENCES research_rule_contracts(id) ON DELETE RESTRICT,
        FOREIGN KEY (supersedes_run_id) REFERENCES research_runs(id) ON DELETE RESTRICT,
        FOREIGN KEY (derived_from_run_id) REFERENCES research_runs(id) ON DELETE RESTRICT,
        FOREIGN KEY (imported_from_artifact_id)
            REFERENCES research_artifacts(id) ON DELETE RESTRICT
    )
    """,
    """
    CREATE TABLE research_strategy_snapshots (
        id TEXT PRIMARY KEY,
        run_id TEXT NOT NULL,
        lottery_type TEXT NOT NULL,
        strategy_id TEXT NOT NULL,
        strategy_name TEXT,
        strategy_version TEXT NOT NULL,
        provenance_availability TEXT NOT NULL CHECK (
            provenance_availability IN ('COMPLETE', 'LEGACY_UNAVAILABLE')
        ),
        source_commit_oid TEXT,
        strategy_source_sha256 TEXT CHECK (
            strategy_source_sha256 IS NULL OR length(strategy_source_sha256) = 64
        ),
        producer_identity TEXT NOT NULL,
        producer_version TEXT NOT NULL,
        runtime_fingerprint TEXT,
        parameters_json TEXT,
        parameters_sha256 TEXT CHECK (
            parameters_sha256 IS NULL OR length(parameters_sha256) = 64
        ),
        seed_protocol TEXT,
        replicate INTEGER NOT NULL CHECK (replicate >= 1),
        execution_code_version TEXT NOT NULL,
        governance_status TEXT,
        lifecycle_status TEXT,
        created_at TEXT NOT NULL,
        CHECK (
            (
                provenance_availability = 'COMPLETE'
                AND source_commit_oid IS NOT NULL
                AND strategy_source_sha256 IS NOT NULL
                AND runtime_fingerprint IS NOT NULL
                AND parameters_json IS NOT NULL
                AND parameters_sha256 IS NOT NULL
                AND seed_protocol IS NOT NULL
            )
            OR (
                provenance_availability = 'LEGACY_UNAVAILABLE'
                AND source_commit_oid IS NULL
                AND strategy_source_sha256 IS NULL
                AND runtime_fingerprint IS NULL
                AND parameters_json IS NULL
                AND parameters_sha256 IS NULL
                AND seed_protocol IS NULL
            )
        ),
        UNIQUE (
            run_id,
            lottery_type,
            strategy_id,
            strategy_version,
            replicate,
            parameters_sha256
        ),
        FOREIGN KEY (run_id) REFERENCES research_runs(id) ON DELETE RESTRICT
    )
    """,
    """
    CREATE TABLE research_draw_bindings (
        id TEXT PRIMARY KEY,
        lottery_type TEXT NOT NULL,
        draw_number TEXT NOT NULL,
        draw_date TEXT NOT NULL,
        main_numbers_json TEXT NOT NULL,
        special_numbers_json TEXT NOT NULL,
        draw_sha256 TEXT NOT NULL CHECK (length(draw_sha256) = 64),
        draw_data_version TEXT NOT NULL,
        created_at TEXT NOT NULL,
        UNIQUE (lottery_type, draw_number, draw_sha256, draw_data_version)
    )
    """,
    """
    CREATE TABLE research_prediction_targets (
        id TEXT PRIMARY KEY,
        run_id TEXT NOT NULL,
        strategy_snapshot_id TEXT NOT NULL,
        target_order INTEGER NOT NULL CHECK (target_order >= 0),
        input_dataset_identity TEXT NOT NULL,
        input_dataset_sha256 TEXT NOT NULL CHECK (length(input_dataset_sha256) = 64),
        history_cutoff_binding_id TEXT NOT NULL,
        history_cutoff_lottery_type TEXT NOT NULL,
        history_cutoff_draw_number TEXT NOT NULL,
        history_cutoff_draw_date TEXT NOT NULL,
        history_draw_count INTEGER NOT NULL CHECK (history_draw_count >= 0),
        source_history_order TEXT NOT NULL,
        target_draw_binding_id TEXT NOT NULL,
        target_lottery_type TEXT NOT NULL,
        target_draw_number TEXT NOT NULL,
        target_draw_date TEXT NOT NULL,
        causal_eligible INTEGER NOT NULL CHECK (causal_eligible IN (0, 1)),
        candidate_k INTEGER CHECK (candidate_k IS NULL OR candidate_k >= 0),
        combination_count INTEGER CHECK (
            combination_count IS NULL OR combination_count >= 0
        ),
        ticket_count_prefix INTEGER CHECK (
            ticket_count_prefix IS NULL OR ticket_count_prefix > 0
        ),
        native_ticket_count INTEGER NOT NULL CHECK (native_ticket_count >= 0),
        ordered_portfolio_count INTEGER NOT NULL CHECK (ordered_portfolio_count >= 0),
        execution_status TEXT NOT NULL CHECK (
            execution_status IN (
                'OK',
                'INSUFFICIENT_HISTORY',
                'STRATEGY_UNAVAILABLE',
                'REJECTED',
                'INVALID_OUTPUT',
                'EXECUTION_ERROR',
                'CANCELLED',
                'WAITING_FOR_DRAW'
            )
        ),
        terminal_marker INTEGER NOT NULL CHECK (terminal_marker = 1),
        target_payload_sha256 TEXT NOT NULL CHECK (length(target_payload_sha256) = 64),
        completed_at TEXT NOT NULL,
        created_at TEXT NOT NULL,
        CHECK (history_cutoff_draw_date < target_draw_date),
        CHECK (
            history_cutoff_lottery_type != target_lottery_type
            OR history_cutoff_draw_number != target_draw_number
        ),
        UNIQUE (run_id, strategy_snapshot_id, target_lottery_type, target_draw_number),
        UNIQUE (run_id, target_order, strategy_snapshot_id),
        FOREIGN KEY (run_id) REFERENCES research_runs(id) ON DELETE RESTRICT,
        FOREIGN KEY (strategy_snapshot_id)
            REFERENCES research_strategy_snapshots(id) ON DELETE RESTRICT,
        FOREIGN KEY (history_cutoff_binding_id)
            REFERENCES research_draw_bindings(id) ON DELETE RESTRICT,
        FOREIGN KEY (target_draw_binding_id)
            REFERENCES research_draw_bindings(id) ON DELETE RESTRICT
    )
    """,
    """
    CREATE TABLE research_prediction_tickets (
        id TEXT PRIMARY KEY,
        target_id TEXT NOT NULL,
        native_position INTEGER NOT NULL CHECK (native_position >= 1),
        ordered_portfolio_position INTEGER CHECK (
            ordered_portfolio_position IS NULL OR ordered_portfolio_position >= 1
        ),
        canonical_ticket_json TEXT NOT NULL,
        main_numbers_json TEXT NOT NULL,
        special_numbers_json TEXT NOT NULL,
        ticket_sha256 TEXT NOT NULL CHECK (length(ticket_sha256) = 64),
        native_duplicate_of_position INTEGER CHECK (
            native_duplicate_of_position IS NULL
            OR (
                native_duplicate_of_position >= 1
                AND native_duplicate_of_position < native_position
            )
        ),
        portfolio_duplicate_of_position INTEGER CHECK (
            portfolio_duplicate_of_position IS NULL
            OR (
                portfolio_duplicate_of_position >= 1
                AND portfolio_duplicate_of_position < ordered_portfolio_position
            )
        ),
        legacy_record_json TEXT,
        legacy_record_sha256 TEXT CHECK (
            legacy_record_sha256 IS NULL OR length(legacy_record_sha256) = 64
        ),
        legacy_provenance_hash TEXT,
        legacy_provenance_source TEXT,
        created_at TEXT NOT NULL,
        CHECK (
            (legacy_record_json IS NULL AND legacy_record_sha256 IS NULL)
            OR (legacy_record_json IS NOT NULL AND legacy_record_sha256 IS NOT NULL)
        ),
        UNIQUE (target_id, native_position),
        FOREIGN KEY (target_id)
            REFERENCES research_prediction_targets(id) ON DELETE RESTRICT
    )
    """,
    """
    CREATE TABLE research_execution_closures (
        id TEXT PRIMARY KEY,
        target_id TEXT NOT NULL UNIQUE,
        closure_type TEXT NOT NULL CHECK (
            closure_type IN (
                'INSUFFICIENT_HISTORY',
                'STRATEGY_UNAVAILABLE',
                'REJECTED',
                'INVALID_OUTPUT',
                'EXECUTION_ERROR',
                'CANCELLED',
                'WAITING_FOR_DRAW'
            )
        ),
        reason_code TEXT NOT NULL,
        sanitized_detail TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (target_id)
            REFERENCES research_prediction_targets(id) ON DELETE RESTRICT
    )
    """,
    """
    CREATE TABLE research_ticket_results (
        id TEXT PRIMARY KEY,
        target_id TEXT NOT NULL,
        ticket_id TEXT NOT NULL,
        draw_binding_id TEXT NOT NULL,
        result_version INTEGER NOT NULL CHECK (result_version >= 1),
        draw_sha256 TEXT NOT NULL CHECK (length(draw_sha256) = 64),
        ticket_count_prefix INTEGER NOT NULL CHECK (ticket_count_prefix > 0),
        main_hit_count INTEGER NOT NULL CHECK (main_hit_count >= 0),
        special_hit_count INTEGER NOT NULL CHECK (special_hit_count >= 0),
        hit_numbers_json TEXT,
        legacy_reported_result_json TEXT,
        legacy_reported_result_sha256 TEXT CHECK (
            legacy_reported_result_sha256 IS NULL
            OR length(legacy_reported_result_sha256) = 64
        ),
        prize_tier_id TEXT,
        result_sha256 TEXT NOT NULL CHECK (length(result_sha256) = 64),
        created_at TEXT NOT NULL,
        CHECK (
            (
                legacy_reported_result_json IS NULL
                AND legacy_reported_result_sha256 IS NULL
            )
            OR (
                legacy_reported_result_json IS NOT NULL
                AND legacy_reported_result_sha256 IS NOT NULL
            )
        ),
        UNIQUE (target_id, ticket_id, ticket_count_prefix, result_version),
        UNIQUE (target_id, ticket_id, ticket_count_prefix, draw_sha256),
        FOREIGN KEY (target_id)
            REFERENCES research_prediction_targets(id) ON DELETE RESTRICT,
        FOREIGN KEY (ticket_id)
            REFERENCES research_prediction_tickets(id) ON DELETE RESTRICT,
        FOREIGN KEY (draw_binding_id)
            REFERENCES research_draw_bindings(id) ON DELETE RESTRICT
    )
    """,
    """
    CREATE TABLE research_run_status_events (
        id TEXT PRIMARY KEY,
        run_id TEXT NOT NULL,
        sequence INTEGER NOT NULL CHECK (sequence >= 0),
        status TEXT NOT NULL CHECK (
            status IN ('PENDING', 'RUNNING', 'PAUSED', 'COMPLETED', 'FAILED', 'CANCELLED')
        ),
        progress_cursor TEXT,
        completed_target_count INTEGER NOT NULL CHECK (completed_target_count >= 0),
        observed_at TEXT NOT NULL,
        created_at TEXT NOT NULL,
        UNIQUE (run_id, sequence),
        FOREIGN KEY (run_id) REFERENCES research_runs(id) ON DELETE RESTRICT
    )
    """,
    """
    CREATE TABLE research_run_summaries (
        id TEXT PRIMARY KEY,
        run_id TEXT NOT NULL,
        strategy_snapshot_id TEXT,
        summary_kind TEXT NOT NULL CHECK (
            summary_kind IN ('COVERAGE', 'RANKING', 'DENOMINATOR', 'AUDIT')
        ),
        ticket_count_prefix INTEGER CHECK (
            ticket_count_prefix IS NULL OR ticket_count_prefix > 0
        ),
        summary_version INTEGER NOT NULL CHECK (summary_version >= 1),
        denominator_count INTEGER NOT NULL CHECK (denominator_count >= 0),
        successful_count INTEGER NOT NULL CHECK (successful_count >= 0),
        closed_count INTEGER NOT NULL CHECK (closed_count >= 0),
        rank_value REAL,
        canonical_summary_json TEXT NOT NULL,
        summary_sha256 TEXT NOT NULL CHECK (length(summary_sha256) = 64),
        created_at TEXT NOT NULL,
        UNIQUE (
            run_id,
            strategy_snapshot_id,
            summary_kind,
            ticket_count_prefix,
            summary_version
        ),
        FOREIGN KEY (run_id) REFERENCES research_runs(id) ON DELETE RESTRICT,
        FOREIGN KEY (strategy_snapshot_id)
            REFERENCES research_strategy_snapshots(id) ON DELETE RESTRICT
    )
    """,
    """
    CREATE TABLE research_artifact_custody_events (
        id TEXT PRIMARY KEY,
        artifact_id TEXT NOT NULL,
        sequence INTEGER NOT NULL CHECK (sequence >= 0),
        custody_action TEXT NOT NULL,
        actor_identity TEXT NOT NULL,
        detail_json TEXT NOT NULL,
        created_at TEXT NOT NULL,
        UNIQUE (artifact_id, sequence),
        FOREIGN KEY (artifact_id) REFERENCES research_artifacts(id) ON DELETE RESTRICT
    )
    """,
    """
    CREATE TABLE research_idempotency_keys (
        id TEXT PRIMARY KEY,
        writer_role TEXT NOT NULL,
        operation_name TEXT NOT NULL,
        idempotency_key TEXT NOT NULL,
        request_sha256 TEXT NOT NULL CHECK (length(request_sha256) = 64),
        created_at TEXT NOT NULL,
        UNIQUE (writer_role, idempotency_key)
    )
    """,
    """
    CREATE TABLE research_run_current_pointer (
        pointer_name TEXT PRIMARY KEY,
        run_id TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY (run_id) REFERENCES research_runs(id) ON DELETE RESTRICT
    )
    """,
    """
    CREATE INDEX idx_research_runs_kind_started
    ON research_runs (run_kind, started_at DESC, id DESC)
    """,
    """
    CREATE INDEX idx_research_status_events_latest
    ON research_run_status_events (run_id, sequence DESC, id DESC)
    """,
    """
    CREATE INDEX idx_research_targets_progress
    ON research_prediction_targets (
        run_id,
        terminal_marker,
        target_order,
        strategy_snapshot_id,
        id
    )
    """,
    """
    CREATE INDEX idx_research_targets_denominator
    ON research_prediction_targets (
        run_id,
        strategy_snapshot_id,
        execution_status,
        target_order,
        id
    )
    """,
    """
    CREATE UNIQUE INDEX idx_research_tickets_ordered_position
    ON research_prediction_tickets (target_id, ordered_portfolio_position)
    WHERE ordered_portfolio_position IS NOT NULL
    """,
    """
    CREATE INDEX idx_research_results_draw_version
    ON research_ticket_results (draw_binding_id, draw_sha256, result_version, id)
    """,
    """
    CREATE INDEX idx_research_summaries_query
    ON research_run_summaries (
        summary_kind,
        ticket_count_prefix,
        rank_value DESC,
        run_id,
        id
    )
    """,
    """
    CREATE TRIGGER trg_research_target_binding_identity
    BEFORE INSERT ON research_prediction_targets
    BEGIN
        SELECT CASE WHEN NOT EXISTS (
            SELECT 1
            FROM research_draw_bindings
            WHERE id = NEW.history_cutoff_binding_id
              AND lottery_type = NEW.history_cutoff_lottery_type
              AND draw_number = NEW.history_cutoff_draw_number
              AND draw_date = NEW.history_cutoff_draw_date
        ) THEN RAISE(ABORT, 'history cutoff binding identity mismatch') END;
        SELECT CASE WHEN NOT EXISTS (
            SELECT 1
            FROM research_draw_bindings
            WHERE id = NEW.target_draw_binding_id
              AND lottery_type = NEW.target_lottery_type
              AND draw_number = NEW.target_draw_number
              AND draw_date = NEW.target_draw_date
        ) THEN RAISE(ABORT, 'target draw binding identity mismatch') END;
        SELECT CASE WHEN NOT EXISTS (
            SELECT 1
            FROM research_strategy_snapshots
            WHERE id = NEW.strategy_snapshot_id
              AND run_id = NEW.run_id
              AND lottery_type = NEW.target_lottery_type
        ) THEN RAISE(ABORT, 'strategy target identity mismatch') END;
    END
    """,
    """
    CREATE TRIGGER trg_research_closure_matches_target
    BEFORE INSERT ON research_execution_closures
    BEGIN
        SELECT CASE WHEN NOT EXISTS (
            SELECT 1
            FROM research_prediction_targets
            WHERE id = NEW.target_id
              AND execution_status = NEW.closure_type
              AND execution_status != 'OK'
        ) THEN RAISE(ABORT, 'closure type does not match target status') END;
    END
    """,
    """
    CREATE TRIGGER trg_research_result_identity
    BEFORE INSERT ON research_ticket_results
    BEGIN
        SELECT CASE WHEN NOT EXISTS (
            SELECT 1
            FROM research_prediction_tickets
            WHERE id = NEW.ticket_id AND target_id = NEW.target_id
        ) THEN RAISE(ABORT, 'ticket result target mismatch') END;
        SELECT CASE WHEN NOT EXISTS (
            SELECT 1
            FROM research_draw_bindings
            WHERE id = NEW.draw_binding_id AND draw_sha256 = NEW.draw_sha256
        ) THEN RAISE(ABORT, 'ticket result draw identity mismatch') END;
        SELECT CASE WHEN NOT EXISTS (
            SELECT 1
            FROM research_prediction_targets AS target
            JOIN research_draw_bindings AS binding
              ON binding.id = NEW.draw_binding_id
            WHERE target.id = NEW.target_id
              AND binding.lottery_type = target.target_lottery_type
              AND binding.draw_number = target.target_draw_number
        ) THEN RAISE(ABORT, 'ticket result draw natural key mismatch') END;
    END
    """,
)


def _append_only_trigger_statements(table: str) -> tuple[str, str]:
    return (
        f"""
        CREATE TRIGGER trg_{table}_no_update
        BEFORE UPDATE ON {table}
        BEGIN
            SELECT RAISE(ABORT, 'append-only table: {table}');
        END
        """,
        f"""
        CREATE TRIGGER trg_{table}_no_delete
        BEFORE DELETE ON {table}
        BEGIN
            SELECT RAISE(ABORT, 'append-only table: {table}');
        END
        """,
    )


MIGRATION_STATEMENTS = _BASE_MIGRATION_STATEMENTS + tuple(
    statement
    for table in IMMUTABLE_TABLE_NAMES
    for statement in _append_only_trigger_statements(table)
)
MIGRATION_SQL = ";\n".join(statement.strip() for statement in MIGRATION_STATEMENTS) + ";\n"
MIGRATION_CHECKSUM = hashlib.sha256(MIGRATION_SQL.encode("utf-8")).hexdigest()

APPEND_ONLY_TRIGGER_NAMES = tuple(
    trigger
    for table in IMMUTABLE_TABLE_NAMES
    for trigger in (f"trg_{table}_no_update", f"trg_{table}_no_delete")
)

_SCHEMA_SQL_TOKEN = re.compile(
    r"'(?:''|[^'])*'|\"(?:\"\"|[^\"])*\"|`(?:``|[^`])*`|\[[^]]*\]|[(),]|[^\s(),]+"
)
_CREATE_NAME_PATTERN = re.compile(
    r"CREATE\s+(?:UNIQUE\s+)?(?:TABLE|INDEX|TRIGGER)\s+(\w+)",
    re.IGNORECASE,
)


def _canonical_schema_sql(sql: str) -> tuple[str, ...]:
    return tuple(token.casefold() for token in _SCHEMA_SQL_TOKEN.findall(sql))


def _object_name(sql: str) -> str:
    match = _CREATE_NAME_PATTERN.search(sql)
    if match is None:
        raise ResearchSchemaError("cannot determine schema object name")
    return match.group(1)


_EXPECTED_SCHEMA_SQL_BY_NAME = {
    _object_name(statement): statement for statement in MIGRATION_STATEMENTS
}


def resolve_research_data_paths(
    *,
    environ: Mapping[str, str] | None = None,
    home: Path | None = None,
) -> ResearchDataPaths:
    """Resolve the canonical research-store location without creating it."""

    selected_environment = os.environ if environ is None else environ
    if DATA_DIRECTORY_ENV in selected_environment:
        configured = selected_environment[DATA_DIRECTORY_ENV]
        if not configured.strip():
            raise ResearchDataError(f"{DATA_DIRECTORY_ENV} must not be empty")
        data_directory = Path(configured)
    else:
        selected_home = Path.home() if home is None else home
        data_directory = selected_home / "Library" / "Application Support" / "LottoLab"
    paths = ResearchDataPaths(
        data_directory=data_directory,
        database=data_directory / RESEARCH_DATABASE_FILENAME,
    )
    _validate_path_definition(paths)
    _validate_existing_paths(paths)
    return paths


def initialize_schema(paths: ResearchDataPaths) -> None:
    """Securely create or verify the canonical version-2 research store."""

    _validate_path_definition(paths)
    _validate_existing_paths(paths)
    directory_created = False
    database_created = False
    try:
        directory_created = _ensure_data_directory(paths.data_directory)
        database_created = _ensure_database_file(paths.database)
        with _raw_connection(paths, read_only=False) as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                if not _verify_migration_state(connection):
                    for statement in MIGRATION_STATEMENTS:
                        connection.execute(statement)
                    connection.execute(
                        """
                        INSERT INTO research_schema_migrations
                            (version, name, checksum, applied_at)
                        VALUES (?, ?, ?, ?)
                        """,
                        (
                            CURRENT_SCHEMA_VERSION,
                            MIGRATION_NAME,
                            MIGRATION_CHECKSUM,
                            _utc_now(),
                        ),
                    )
                    if not _verify_migration_state(connection):
                        raise ResearchSchemaError(
                            "research schema migration did not reach version 2"
                        )
            except BaseException:
                connection.rollback()
                raise
            else:
                connection.commit()
        _validate_existing_paths(paths)
        _reject_wal_sidecars(paths.database)
    except (ResearchDataError, ResearchSchemaError):
        if database_created:
            _remove_new_database(paths.database)
        if directory_created:
            _remove_empty_directory(paths.data_directory)
        raise
    except sqlite3.DatabaseError as exc:
        if database_created:
            _remove_new_database(paths.database)
        if directory_created:
            _remove_empty_directory(paths.data_directory)
        raise ResearchSchemaError("SQLite research schema migration failed") from exc


def verify_schema_read_only(paths: ResearchDataPaths) -> bool:
    """Return False for an absent store; verify an existing store read-only."""

    _validate_path_definition(paths)
    _validate_existing_paths(paths)
    if not paths.database.exists():
        return False
    with _raw_connection(paths, read_only=True) as connection:
        try:
            initialized = _verify_migration_state(connection)
        except sqlite3.DatabaseError as exc:
            raise ResearchSchemaError("SQLite research schema verification failed") from exc
        if not initialized:
            raise ResearchSchemaError("database exists without a research migration")
    _validate_existing_paths(paths)
    return True


@contextmanager
def open_database(
    paths: ResearchDataPaths,
    *,
    read_only: bool = False,
) -> Generator[sqlite3.Connection]:
    """Open an existing store after checksum and semantic precondition checks."""

    _validate_path_definition(paths)
    _validate_existing_paths(paths)
    if not paths.database.exists():
        raise ResearchSchemaError("research database does not exist")
    with _raw_connection(paths, read_only=read_only) as connection:
        try:
            initialized = _verify_migration_state(connection)
        except sqlite3.DatabaseError as exc:
            raise ResearchSchemaError("SQLite research schema verification failed") from exc
        if not initialized:
            raise ResearchSchemaError("database exists without a research migration")
        yield connection


@contextmanager
def _raw_connection(
    paths: ResearchDataPaths,
    *,
    read_only: bool,
) -> Generator[sqlite3.Connection]:
    _validate_existing_paths(paths)
    _reject_wal_sidecars(paths.database)
    mode = "ro" if read_only else "rw"
    uri = f"{paths.database.as_uri()}?mode={mode}"
    try:
        connection = sqlite3.connect(
            uri,
            uri=True,
            timeout=BUSY_TIMEOUT_MS / 1_000,
            isolation_level=None,
        )
    except sqlite3.DatabaseError as exc:
        raise ResearchSchemaError("cannot open the research database safely") from exc
    try:
        try:
            connection.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}")
            connection.execute("PRAGMA foreign_keys = ON")
            if connection.execute("PRAGMA foreign_keys").fetchone() != (1,):
                raise ResearchSchemaError("SQLite foreign-key enforcement is unavailable")
            if read_only:
                connection.execute("PRAGMA query_only = ON")
                journal_mode = connection.execute("PRAGMA journal_mode").fetchone()
            else:
                journal_mode = connection.execute("PRAGMA journal_mode = DELETE").fetchone()
            if journal_mode is None or str(journal_mode[0]).lower() != "delete":
                raise ResearchSchemaError("SQLite must use DELETE journal mode")
        except sqlite3.DatabaseError as exc:
            raise ResearchSchemaError("cannot configure SQLite safely") from exc
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
    if "research_schema_migrations" not in table_names:
        if table_names:
            raise ResearchSchemaError("unversioned database contains application tables")
        return False

    rows = connection.execute(
        """
        SELECT version, name, checksum
        FROM research_schema_migrations
        ORDER BY version
        """
    ).fetchall()
    try:
        versions = [int(row[0]) for row in rows]
    except (TypeError, ValueError) as exc:
        raise ResearchSchemaError("database migration versions are invalid") from exc
    if any(version > CURRENT_SCHEMA_VERSION for version in versions):
        raise NewerSchemaVersionError(
            "database schema is newer than this LottoLab build"
        )
    if versions != [CURRENT_SCHEMA_VERSION]:
        raise ResearchSchemaError("database migration history is incomplete")
    _, name, checksum = rows[0]
    if name != MIGRATION_NAME or checksum != MIGRATION_CHECKSUM:
        raise MigrationChecksumError("database migration checksum does not match")
    _verify_schema_semantics(connection, table_names)
    return True


def _verify_schema_semantics(
    connection: sqlite3.Connection,
    table_names: set[str],
) -> None:
    if table_names != set(TABLE_NAMES):
        raise ResearchSchemaError("database tables do not match version 2")
    schema_rows = connection.execute(
        """
        SELECT type, name, tbl_name, sql
        FROM sqlite_schema
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
            raise ResearchSchemaError(f"unexpected database schema object: {name}")
        if _canonical_schema_sql(actual_sql) != _canonical_schema_sql(expected_sql):
            raise ResearchSchemaError(f"database schema SQL does not match version 2: {name}")
    if seen_names != set(_EXPECTED_SCHEMA_SQL_BY_NAME):
        raise ResearchSchemaError("database schema objects do not match version 2")
    for table in TABLE_NAMES:
        for foreign_key in connection.execute(f"PRAGMA foreign_key_list({table})"):
            if str(foreign_key[6]) != "RESTRICT":
                raise ResearchSchemaError(
                    f"unexpected foreign-key action on {table}: {foreign_key[6]}"
                )


def _validate_path_definition(paths: ResearchDataPaths) -> None:
    data_directory = paths.data_directory
    if "\x00" in str(data_directory):
        raise ResearchDataError("research data path contains a null byte")
    if not data_directory.is_absolute():
        raise ResearchDataError("research data path must be absolute")
    if ".." in data_directory.parts:
        raise ResearchDataError("research data path traversal is not allowed")
    if data_directory == Path(data_directory.anchor):
        raise ResearchDataError("research data path cannot be the filesystem root")
    if any(part.casefold() == "lotterynew" for part in data_directory.parts):
        raise ResearchDataError("LotteryNew paths are forbidden")
    if paths.database != data_directory / RESEARCH_DATABASE_FILENAME:
        raise ResearchDataError("research database filename is fixed")
    _reject_git_worktree_path(data_directory)
    _reject_symlink_components(data_directory)


def _validate_existing_paths(paths: ResearchDataPaths) -> None:
    _validate_path_definition(paths)
    try:
        directory_metadata = os.lstat(paths.data_directory)
    except FileNotFoundError:
        return
    if not stat.S_ISDIR(directory_metadata.st_mode):
        raise ResearchDataError("research data path is not a directory")
    if directory_metadata.st_uid != os.getuid():
        raise ResearchDataError("research data directory has a foreign owner")
    if stat.S_IMODE(directory_metadata.st_mode) != 0o700:
        raise ResearchDataError("research data directory mode must be exactly 0700")
    try:
        database_metadata = os.lstat(paths.database)
    except FileNotFoundError:
        return
    if not stat.S_ISREG(database_metadata.st_mode):
        raise ResearchDataError("research database must be a regular file")
    if database_metadata.st_uid != os.getuid():
        raise ResearchDataError("research database has a foreign owner")
    if stat.S_IMODE(database_metadata.st_mode) != 0o600:
        raise ResearchDataError("research database mode must be exactly 0600")
    if database_metadata.st_nlink != 1:
        raise ResearchDataError("research database must have exactly one hard link")


def _ensure_data_directory(data_directory: Path) -> bool:
    existed = data_directory.exists()
    try:
        data_directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    except OSError as exc:
        raise ResearchDataError("cannot create the research data directory safely") from exc
    _reject_symlink_components(data_directory)
    paths = ResearchDataPaths(
        data_directory,
        data_directory / RESEARCH_DATABASE_FILENAME,
    )
    _validate_existing_paths(paths)
    return not existed


def _ensure_database_file(database: Path) -> bool:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(database, flags, 0o600)
    except FileExistsError:
        _validate_existing_paths(ResearchDataPaths(database.parent, database))
        return False
    except OSError as exc:
        raise ResearchDataError("cannot create the research database safely") from exc
    try:
        os.fchmod(descriptor, 0o600)
    finally:
        os.close(descriptor)
    _validate_existing_paths(ResearchDataPaths(database.parent, database))
    return True


def _reject_symlink_components(path: Path) -> None:
    current = Path(path.anchor)
    for component in path.parts[1:]:
        current /= component
        try:
            metadata = os.lstat(current)
        except FileNotFoundError:
            break
        except OSError as exc:
            raise ResearchDataError("cannot inspect the research path safely") from exc
        if stat.S_ISLNK(metadata.st_mode):
            raise ResearchDataError("research data path cannot contain symlinks")


def _reject_git_worktree_path(path: Path) -> None:
    for ancestor in (path, *path.parents):
        try:
            os.lstat(ancestor / ".git")
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise ResearchDataError("cannot inspect Git-worktree boundaries safely") from exc
        raise ResearchDataError("research data path must be outside Git worktrees")


def _reject_wal_sidecars(database: Path) -> None:
    for suffix in ("-wal", "-shm"):
        try:
            os.lstat(Path(f"{database}{suffix}"))
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise ResearchDataError("cannot inspect SQLite sidecar files safely") from exc
        raise ResearchDataError("WAL and SHM files are forbidden")


def _remove_new_database(database: Path) -> None:
    try:
        metadata = os.lstat(database)
    except OSError:
        return
    if (
        stat.S_ISREG(metadata.st_mode)
        and metadata.st_uid == os.getuid()
        and metadata.st_nlink == 1
    ):
        with suppress(OSError):
            database.unlink()


def _remove_empty_directory(data_directory: Path) -> None:
    with suppress(OSError):
        data_directory.rmdir()


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


__all__ = [
    "APPEND_ONLY_TRIGGER_NAMES",
    "BUSY_TIMEOUT_MS",
    "CURRENT_SCHEMA_VERSION",
    "DATA_DIRECTORY_ENV",
    "IMMUTABLE_TABLE_NAMES",
    "MIGRATION_CHECKSUM",
    "MIGRATION_NAME",
    "MIGRATION_SQL",
    "MIGRATION_STATEMENTS",
    "RESEARCH_DATABASE_FILENAME",
    "TABLE_NAMES",
    "MigrationChecksumError",
    "NewerSchemaVersionError",
    "ResearchDataError",
    "ResearchDataPaths",
    "ResearchSchemaError",
    "initialize_schema",
    "open_database",
    "resolve_research_data_paths",
    "verify_schema_read_only",
]
