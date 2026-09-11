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

from lottolab.domain.research_live_forecast import (
    CANONICAL_CONSENSUS,
    CONSENSUS_AGGREGATION_UNIT,
    CONSENSUS_AUTHORITY_B_PAYLOAD_SHA256,
    CONSENSUS_CORRELATED_FAMILY_POLICY,
    CONSENSUS_METHOD_ID,
    CONSENSUS_METHOD_VERSION,
    CONSENSUS_MISSING,
    CONSENSUS_PROVENANCE_SCHEMA_VERSION,
    CONSENSUS_STREAM,
    CONSENSUS_STREAM_VERSION,
    CONSENSUS_TARGET_DATA_CUTOFF,
    CONSENSUS_TARGET_DRAW_DATE,
    CONSENSUS_TARGET_DRAW_NUMBER,
    CONSENSUS_TARGET_HISTORY_DRAW_COUNT,
    CONSENSUS_TARGET_HISTORY_SHA256,
    CONSENSUS_TARGET_LOTTERY_TYPE,
    CONSENSUS_TARGET_SCHEDULED_AT,
    CONSENSUS_TARGET_TIMEZONE,
    LEGACY_MISSING,
    LEGACY_SHA256,
    LEGACY_STREAM,
    NATIVE_ARRAY_REQUIRED_PATHS,
    NATIVE_REQUIRED_PATHS,
    NATIVE_STREAM,
    NATIVE_STREAM_VERSION,
    ORIGINAL_FIELDS,
    canonical_json,
)

DATA_DIRECTORY_ENV = "LOTTOLAB_DATA_DIR"
RESEARCH_DATABASE_FILENAME = "lottolab_research.db"
CURRENT_SCHEMA_VERSION = 4
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


V2_TABLE_NAMES = (
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

V2_IMMUTABLE_TABLE_NAMES = tuple(
    table for table in V2_TABLE_NAMES if table != "research_run_current_pointer"
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
    for table in V2_IMMUTABLE_TABLE_NAMES
    for statement in _append_only_trigger_statements(table)
)
MIGRATION_SQL = ";\n".join(statement.strip() for statement in MIGRATION_STATEMENTS) + ";\n"
MIGRATION_CHECKSUM = hashlib.sha256(MIGRATION_SQL.encode("utf-8")).hexdigest()

V2_APPEND_ONLY_TRIGGER_NAMES = tuple(
    trigger
    for table in V2_IMMUTABLE_TABLE_NAMES
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


_V2_EXPECTED_SCHEMA = {_object_name(statement): statement for statement in MIGRATION_STATEMENTS}

# Version 2 statements, name and checksum above are deliberately unchanged.
V3_MIGRATION_NAME = "append_live_forecast_versions_with_class_specific_provenance"
_v3_runs_sql = _BASE_MIGRATION_STATEMENTS[3]
for _nullable_original in (
    "rule_contract_id",
    "producer_identity",
    "execution_code_version",
    "source_commit_oid",
    "started_at",
):
    _v3_runs_sql = _v3_runs_sql.replace(
        f"{_nullable_original} TEXT NOT NULL", f"{_nullable_original} TEXT"
    )
_V3_RUNS_SQL = _v3_runs_sql.replace(
    "        FOREIGN KEY (rule_contract_id)",
    """        provenance_class TEXT CHECK (
            provenance_class IN ('NATIVE_GENERATED', 'LEGACY_MATERIALIZED')
        ),
        CHECK (COALESCE((
            provenance_class = 'LEGACY_MATERIALIZED'
            AND run_kind = 'LIVE_PREDICTION'
            AND imported_from_artifact_id IS NOT NULL
            AND rule_contract_id IS NULL
            AND producer_identity IS NULL AND execution_code_version IS NULL
            AND source_commit_oid IS NULL AND started_at IS NULL
        ) OR (
            (provenance_class IS NULL OR provenance_class = 'NATIVE_GENERATED')
            AND rule_contract_id IS NOT NULL
            AND producer_identity IS NOT NULL AND execution_code_version IS NOT NULL
            AND source_commit_oid IS NOT NULL AND started_at IS NOT NULL
        ), 0)),
        FOREIGN KEY (rule_contract_id)""",
)
_ORIGINAL_COLUMN_SQL = ",\n".join(f"{field} TEXT" for field in ORIGINAL_FIELDS)
_NATIVE_NONNULL_SQL = " AND ".join(f"{field} IS NOT NULL" for field in ORIGINAL_FIELDS)
_LEGACY_NULL_SQL = " AND ".join(f"{field} IS NULL" for field in ORIGINAL_FIELDS)


def _json_contract_sql(expression: str, paths: Mapping[str, str]) -> str:
    clauses: list[str] = []
    for path, kind in paths.items():
        value = f"json_extract({expression}, '$.{path}')"
        clauses.append(f"COALESCE(json_type({expression}, '$.{path}') = '{kind}', 0)")
        if kind == "text":
            clauses.append(f"length(trim({value})) > 0")
            leaf = path.rsplit(".", 1)[-1]
            size = 40 if leaf in ("commit", "tree") else 64
            if leaf in ("commit", "tree", "digest", "producer_fingerprint") or leaf.endswith(
                "sha256"
            ):
                clauses.append(f"length({value}) = {size} AND {value} NOT GLOB '*[^0-9a-f]*'")
    return " AND ".join(clauses)


_NATIVE_JSON_SQL = " AND ".join(
    f"json_valid({field}) AND {_json_contract_sql(field, paths)}"
    for field, paths in NATIVE_REQUIRED_PATHS.items()
)
_NATIVE_TARGET_SQL = _json_contract_sql(
    "target_json",
    {
        "lottery_type": "text",
        "target_draw_number": "text",
        "target_draw_date": "text",
        "scheduled_at": "text",
        "timezone": "text",
        "data_cutoff": "text",
        "forecast_horizon": "integer",
        "history_draw_count": "integer",
        "causal_history_sha256": "text",
        "schedule_authority_sha256": "text",
    },
)
_LIVE_VERSION_SQL = f"""
CREATE TABLE research_live_forecast_versions (
    version INTEGER PRIMARY KEY,
    run_id TEXT NOT NULL UNIQUE,
    request_id TEXT NOT NULL UNIQUE CHECK (length(request_id) > 0),
    request_sha256 TEXT NOT NULL CHECK (length(request_sha256) = 64),
    lottery_type TEXT NOT NULL CHECK (lottery_type = 'BIG_LOTTO'),
    target_draw_number TEXT NOT NULL,
    target_draw_date TEXT NOT NULL,
    forecast_stream_id TEXT NOT NULL,
    forecast_stream_version TEXT NOT NULL,
    target_json TEXT NOT NULL CHECK (json_valid(target_json)),
    provenance_class TEXT NOT NULL CHECK (
        provenance_class IN ('NATIVE_GENERATED', 'LEGACY_MATERIALIZED')
    ),
    original_execution_provenance_status TEXT NOT NULL,
    payload_bytes BLOB NOT NULL CHECK (typeof(payload_bytes) = 'blob'),
    payload_sha256 TEXT NOT NULL CHECK (length(payload_sha256) = 64),
    source_payload_sha256 TEXT NOT NULL CHECK (length(source_payload_sha256) = 64),
    source_locator TEXT NOT NULL CHECK (length(source_locator) > 0),
    bundle_id TEXT,
    {_ORIGINAL_COLUMN_SQL},
    missing_provenance_json TEXT NOT NULL CHECK (json_valid(missing_provenance_json)),
    import_execution_json TEXT,
    committed_at TEXT NOT NULL,
    expected_current_version INTEGER NOT NULL CHECK (expected_current_version >= 0),
    pointer_advanced INTEGER NOT NULL CHECK (pointer_advanced IN (0, 1)),
    provenance_envelope_json TEXT NOT NULL CHECK (json_valid(provenance_envelope_json)),
    provenance_envelope_sha256 TEXT NOT NULL CHECK (length(provenance_envelope_sha256) = 64),
    CHECK (COALESCE((
        provenance_class = 'NATIVE_GENERATED'
        AND forecast_stream_id = '{NATIVE_STREAM}'
        AND forecast_stream_version = '{NATIVE_STREAM_VERSION}'
        AND original_execution_provenance_status = 'COMPLETE'
        AND {_NATIVE_NONNULL_SQL} AND {_NATIVE_JSON_SQL}
        AND {_NATIVE_TARGET_SQL}
        AND json_extract(target_json, '$.lottery_type') = lottery_type
        AND json_extract(target_json, '$.target_draw_number') = target_draw_number
        AND json_extract(target_json, '$.target_draw_date') = target_draw_date
        AND json_extract(target_json, '$.forecast_horizon') = 1
        AND json_extract(target_json, '$.history_draw_count') > 0
        AND CAST(json_extract(target_json, '$.data_cutoff') AS INTEGER)
            < CAST(target_draw_number AS INTEGER)
        AND julianday(json_extract(target_json, '$.scheduled_at')) IS NOT NULL
        AND julianday(generation_finished_at) >= julianday(generation_started_at)
        AND julianday(committed_at) >= julianday(generation_finished_at)
        AND missing_provenance_json = '{{}}' AND import_execution_json IS NULL
        AND bundle_id IS NOT NULL AND length(bundle_id) > 0
    ) OR (
        provenance_class = 'LEGACY_MATERIALIZED'
        AND forecast_stream_id = '{LEGACY_STREAM}'
        AND forecast_stream_version = '{LEGACY_STREAM}'
        AND original_execution_provenance_status = 'UNKNOWN_LEGACY_PROVENANCE'
        AND {_LEGACY_NULL_SQL}
        AND missing_provenance_json = '{canonical_json(LEGACY_MISSING)}'
        AND import_execution_json IS NOT NULL AND json_valid(import_execution_json)
        AND source_payload_sha256 = '{LEGACY_SHA256}'
        AND payload_sha256 = source_payload_sha256 AND bundle_id IS NULL
    ), 0)),
    FOREIGN KEY (run_id) REFERENCES research_runs(id) ON DELETE RESTRICT
)
"""
_V4_RUNS_SQL = _V3_RUNS_SQL.replace(
    "provenance_class IN ('NATIVE_GENERATED', 'LEGACY_MATERIALIZED')",
    "provenance_class IN ('NATIVE_GENERATED', 'LEGACY_MATERIALIZED', 'CANONICAL_CONSENSUS')",
).replace(
    """        ) OR (
            (provenance_class IS NULL OR provenance_class = 'NATIVE_GENERATED')
            AND rule_contract_id IS NOT NULL
            AND producer_identity IS NOT NULL AND execution_code_version IS NOT NULL
            AND source_commit_oid IS NOT NULL AND started_at IS NOT NULL
        ), 0)),""",
    """        ) OR (
            (provenance_class IS NULL OR provenance_class = 'NATIVE_GENERATED')
            AND rule_contract_id IS NOT NULL
            AND producer_identity IS NOT NULL AND execution_code_version IS NOT NULL
            AND source_commit_oid IS NOT NULL AND started_at IS NOT NULL
        ) OR (
            provenance_class = 'CANONICAL_CONSENSUS'
            AND run_kind = 'LIVE_PREDICTION'
            AND imported_from_artifact_id IS NOT NULL
            AND rule_contract_id IS NULL
            AND producer_identity IS NULL AND execution_code_version IS NULL
            AND source_commit_oid IS NULL AND started_at IS NULL
        ), 0)),""",
)
_CONSENSUS_NULL_SQL = " AND ".join(f"{field} IS NULL" for field in ORIGINAL_FIELDS)
_V4_LIVE_VERSION_SQL = (
    _LIVE_VERSION_SQL.replace(
        "provenance_class IN ('NATIVE_GENERATED', 'LEGACY_MATERIALIZED')",
        "provenance_class IN ('NATIVE_GENERATED', 'LEGACY_MATERIALIZED', 'CANONICAL_CONSENSUS')",
    )
    .replace(
        "    import_execution_json TEXT,\n",
        "    import_execution_json TEXT,\n    consensus_provenance_json TEXT,\n",
    )
    .replace(
        "        AND missing_provenance_json = '{}' AND import_execution_json IS NULL\n"
        "        AND bundle_id IS NOT NULL",
        "        AND missing_provenance_json = '{}' AND import_execution_json IS NULL\n"
        "        AND consensus_provenance_json IS NULL\n"
        "        AND bundle_id IS NOT NULL",
    )
    .replace(
        f"        AND import_execution_json IS NOT NULL AND json_valid(import_execution_json)\n"
        f"        AND source_payload_sha256 = '{LEGACY_SHA256}'",
        "        AND import_execution_json IS NOT NULL AND json_valid(import_execution_json)\n"
        "        AND consensus_provenance_json IS NULL\n"
        f"        AND source_payload_sha256 = '{LEGACY_SHA256}'",
    )
    .replace(
        f"        AND source_payload_sha256 = '{LEGACY_SHA256}'\n"
        "        AND payload_sha256 = source_payload_sha256 AND bundle_id IS NULL\n"
        "    ), 0)),",
        f"""        AND source_payload_sha256 = '{LEGACY_SHA256}'
        AND payload_sha256 = source_payload_sha256 AND bundle_id IS NULL
    ) OR (
        provenance_class = '{CANONICAL_CONSENSUS}'
        AND forecast_stream_id = '{CONSENSUS_STREAM}'
        AND forecast_stream_version = '{CONSENSUS_STREAM_VERSION}'
        AND original_execution_provenance_status = 'CONSENSUS_SOURCE_BOUND'
        AND {_CONSENSUS_NULL_SQL}
        AND missing_provenance_json = '{canonical_json(CONSENSUS_MISSING)}'
        AND import_execution_json IS NOT NULL AND json_valid(import_execution_json)
        AND consensus_provenance_json IS NOT NULL
        AND json_valid(consensus_provenance_json)
        AND source_payload_sha256 = payload_sha256
        AND payload_sha256 = '{CONSENSUS_AUTHORITY_B_PAYLOAD_SHA256}'
        AND bundle_id IS NULL
        AND json_extract(target_json, '$.lottery_type') = 'BIG_LOTTO'
        AND json_extract(target_json, '$.target_draw_number') = '115000087'
        AND json_extract(target_json, '$.target_draw_date') = '2026-09-11'
        AND json_extract(target_json, '$.scheduled_at') = '2026-09-11T20:30:00+08:00'
        AND json_extract(target_json, '$.timezone') = 'Asia/Taipei'
        AND json_extract(target_json, '$.data_cutoff') = '115000086'
        AND json_extract(target_json, '$.forecast_horizon') = 1
        AND json_extract(target_json, '$.history_draw_count') = 2168
        AND json_extract(target_json, '$.causal_history_sha256') =
            '{CONSENSUS_TARGET_HISTORY_SHA256}'
        AND json_type(target_json, '$.schedule_authority_sha256') = 'text'
        AND length(json_extract(target_json, '$.schedule_authority_sha256')) = 64
        AND json_extract(target_json, '$.schedule_authority_sha256') NOT GLOB '*[^0-9a-f]*'
    ), 0)),""",
    )
)
_LIVE_POINTER_SQL = """
CREATE TABLE research_live_forecast_current_pointer (
    lottery_type TEXT NOT NULL,
    target_draw_number TEXT NOT NULL,
    target_draw_date TEXT NOT NULL,
    forecast_stream_id TEXT NOT NULL,
    forecast_stream_version TEXT NOT NULL,
    version INTEGER NOT NULL,
    run_id TEXT NOT NULL,
    PRIMARY KEY (lottery_type, target_draw_number, target_draw_date,
                 forecast_stream_id, forecast_stream_version),
    FOREIGN KEY (run_id) REFERENCES research_runs(id) ON DELETE RESTRICT,
    FOREIGN KEY (version) REFERENCES research_live_forecast_versions(version) ON DELETE RESTRICT
)
"""
_POINTER_VERSION_GUARD = (
    "SELECT CASE WHEN NEW.version <= OLD.version THEN RAISE(ABORT, 'stale live pointer') END;"
)


def _inventory_check_sql(inventory: str, paths: Mapping[str, str]) -> str:
    column, array = inventory.split(".")
    source = f"NEW.{column}, '$.{array}'"
    empty = "0" if array == "observations" else f"json_array_length({source}) = 0"
    return f"""
    SELECT CASE WHEN {empty}
        OR EXISTS (
            SELECT 1 FROM json_each({source}) AS item
            WHERE CASE WHEN item.type != 'object' THEN 1
                ELSE NOT COALESCE(({_json_contract_sql("item.value", paths)}), 0) END
        ) THEN RAISE(ABORT, 'incomplete native {inventory}') END;
    """


_NATIVE_INVENTORY_CHECKS = tuple(
    _inventory_check_sql(inventory, paths)
    for inventory, paths in NATIVE_ARRAY_REQUIRED_PATHS.items()
)
_EXECUTED_PARAMETERS_SQL = _json_contract_sql(
    "item.value",
    {
        "constructor_defaults": "object",
        "instance_state": "object",
        "adapter_class": "text",
    },
)
_EXECUTED_CONSTRUCTOR_SQL = _json_contract_sql(
    "item.value",
    {
        "selected_strategy": "text",
        "adapter_locator": "text",
        "adapter_version": "text",
        "adapter_source_sha256": "text",
        "generation_config_sha256": "text",
        "rng_binding_sha256": "text",
    },
)
_NATIVE_STRUCTURE_TRIGGER = f"""
CREATE TRIGGER trg_live_forecast_native_structure
BEFORE INSERT ON research_live_forecast_versions
WHEN NEW.provenance_class = 'NATIVE_GENERATED'
BEGIN
    {"".join(_NATIVE_INVENTORY_CHECKS)}
    SELECT CASE WHEN EXISTS (
        SELECT 1 FROM json_each(NEW.runtime_manifest_json, '$.dependencies') AS item
        WHERE NOT EXISTS (SELECT 1 FROM json_each(item.value, '$.versions'))
           OR EXISTS (SELECT 1 FROM json_each(item.value, '$.versions') AS v
                      WHERE v.type != 'text' OR length(trim(v.value)) = 0)
    ) THEN RAISE(ABORT, 'incomplete native dependency versions') END;
    SELECT CASE WHEN NOT COALESCE((
        json_array_length(NEW.history_snapshot_json, '$.draws')
            = json_extract(NEW.target_json, '$.history_draw_count')
        AND json_extract(NEW.history_snapshot_json, '$.sha256')
            = json_extract(NEW.target_json, '$.causal_history_sha256')
        AND json_extract(NEW.ranking_evidence_json, '$.objective') = 'OFFICIAL_ANY_PRIZE'
        AND json_extract(NEW.ranking_evidence_json, '$.ranking_policy_version')
            = '{NATIVE_STREAM_VERSION}'
        AND json_extract(NEW.ranking_evidence_json, '$.evaluation_window') = 'FULL'
        AND json_array_length(NEW.ticket_lineage_json, '$.buckets') = 6
        AND json_extract(NEW.ticket_lineage_json, '$.upstream_payload_sha256') = NEW.payload_sha256
    ), 0) THEN RAISE(ABORT, 'native target or evidence binding mismatch') END;
    SELECT CASE WHEN EXISTS (
        SELECT 1 FROM json_each(NEW.history_snapshot_json, '$.draws') AS item
        WHERE json_extract(item.value, '$.lottery_type') != 'BIG_LOTTO'
           OR json_array_length(item.value, '$.main_numbers') != 6
           OR CAST(json_extract(item.value, '$.draw_number') AS INTEGER)
              >= CAST(NEW.target_draw_number AS INTEGER)
    ) THEN RAISE(ABORT, 'invalid native history inventory') END;
    SELECT CASE WHEN EXISTS (
        SELECT 1 FROM json_each(NEW.effective_parameters_json, '$.strategies') AS item
        WHERE NOT COALESCE((json_extract(item.value, '$.status') = 'NOT_EXECUTED' OR (
            json_extract(item.value, '$.status') = 'EXECUTED'
            AND {_EXECUTED_PARAMETERS_SQL}
        )), 0)
    ) THEN RAISE(ABORT, 'incomplete executed native parameters') END;
    SELECT CASE WHEN EXISTS (
        SELECT 1 FROM json_each(NEW.rng_semantics_json, '$.stages') AS item
        WHERE NOT COALESCE((
            json_extract(item.value, '$.status') IN ('EXECUTED', 'NOT_EXECUTED')
            AND json_extract(item.value, '$.stage') = 'NATIVE_GENERATION'
            AND json_extract(item.value, '$.replicate') = 1
            AND json_extract(item.value, '$.invocation_identity') = NEW.request_id
            AND ((json_extract(item.value, '$.rng_semantics.behavior') = 'DETERMINISTIC'
                  AND json_type(item.value, '$.rng_semantics.seed') = 'null'
                  AND json_extract(item.value, '$.seed_status') = 'NOT_APPLICABLE')
              OR (json_extract(item.value, '$.rng_semantics.behavior') = 'SEEDED_STOCHASTIC'
                  AND json_type(item.value, '$.rng_semantics.seed') IN ('integer', 'text')
                  AND length(CAST(json_extract(item.value, '$.rng_semantics.seed') AS TEXT)) > 0
                  AND json_extract(item.value, '$.seed_status') = 'EFFECTIVE_SEED_CAPTURED')
              OR (json_extract(item.value, '$.rng_semantics.behavior') = 'UNSEEDED_STOCHASTIC'
                  AND json_type(item.value, '$.rng_semantics.seed') = 'null'
                  AND json_extract(item.value, '$.seed_status')
                      = 'uncaptured_process_global_rng_state'))
        ), 0)
    ) THEN RAISE(ABORT, 'incomplete native RNG execution') END;
    SELECT CASE WHEN EXISTS (
        SELECT 1 FROM json_each(NEW.ticket_lineage_json, '$.buckets') AS item
        WHERE NOT COALESCE((
            json_extract(item.value, '$.selector_status') = 'EXECUTED'
            AND json_extract(item.value, '$.selection_rule') = '{NATIVE_STREAM_VERSION}'
            AND ((json_extract(item.value, '$.constructor_status') = 'NOT_EXECUTED'
                  AND json_extract(item.value, '$.status') != 'AVAILABLE')
              OR (json_extract(item.value, '$.constructor_status') = 'EXECUTED'
                  AND {_EXECUTED_CONSTRUCTOR_SQL}))
        ), 0)
    ) THEN RAISE(ABORT, 'incomplete native constructor lineage') END;
    SELECT CASE WHEN (
        SELECT count(DISTINCT json_extract(value, '$.strategy_id'))
        FROM json_each(NEW.generation_configs_json, '$.strategies')
    ) != json_array_length(NEW.generation_configs_json, '$.strategies')
    OR json_array_length(NEW.generation_configs_json, '$.strategies')
        != json_array_length(NEW.effective_parameters_json, '$.strategies')
    OR json_array_length(NEW.generation_configs_json, '$.strategies')
        != json_array_length(NEW.rng_semantics_json, '$.stages')
    OR EXISTS (
        SELECT 1 FROM json_each(NEW.generation_configs_json, '$.strategies') AS config
        WHERE NOT EXISTS (
            SELECT 1 FROM json_each(NEW.effective_parameters_json, '$.strategies') AS parameters
            WHERE json_extract(config.value, '$.strategy_id')
                = json_extract(parameters.value, '$.strategy_id')
              AND json_extract(config.value, '$.strategy_version')
                = json_extract(parameters.value, '$.strategy_version')
              AND json_extract(config.value, '$.native_k')
                = json_extract(parameters.value, '$.native_k')
              AND json_extract(config.value, '$.parameters')
                = json_extract(parameters.value, '$.parameters_json')
        ) OR NOT EXISTS (
            SELECT 1 FROM json_each(NEW.rng_semantics_json, '$.stages') AS rng
            WHERE json_extract(config.value, '$.strategy_id')
                = json_extract(rng.value, '$.strategy_id')
              AND json_extract(config.value, '$.rng_semantics')
                = json_extract(rng.value, '$.rng_semantics')
        )
    ) THEN RAISE(ABORT, 'native execution inventory mismatch') END;
    SELECT CASE WHEN (
        SELECT count(DISTINCT json_extract(value, '$.native_k'))
        FROM json_each(NEW.ticket_lineage_json, '$.buckets')
        WHERE json_extract(value, '$.native_k') IN (1,2,3,5,10,20)
    ) != 6 OR NOT EXISTS (
        SELECT 1 FROM json_each(NEW.ticket_lineage_json, '$.buckets') AS item
        WHERE json_extract(item.value, '$.native_k') = 20
          AND json_extract(item.value, '$.status') = 'UNAVAILABLE_NO_CANONICAL_NATIVE_K20_STRATEGY'
          AND json_array_length(item.value, '$.tickets') = 0
          AND json_extract(item.value, '$.constructor_status') = 'NOT_EXECUTED'
    ) THEN RAISE(ABORT, 'native K bucket inventory mismatch') END;
END
"""
_CONSENSUS_STRUCTURE_TRIGGER = f"""
CREATE TRIGGER trg_live_forecast_consensus_structure
BEFORE INSERT ON research_live_forecast_versions
WHEN NEW.provenance_class = 'CANONICAL_CONSENSUS'
BEGIN
    SELECT CASE WHEN (
        NEW.lottery_type = '{CONSENSUS_TARGET_LOTTERY_TYPE}'
        AND NEW.target_draw_number = '{CONSENSUS_TARGET_DRAW_NUMBER}'
        AND NEW.target_draw_date = '{CONSENSUS_TARGET_DRAW_DATE}'
        AND NEW.forecast_stream_id = '{CONSENSUS_STREAM}'
        AND NEW.forecast_stream_version = '{CONSENSUS_STREAM_VERSION}'
        AND NEW.payload_sha256 != '{CONSENSUS_AUTHORITY_B_PAYLOAD_SHA256}'
    ) THEN RAISE(ABORT, 'canonical consensus payload is not Authority B') END;
    SELECT CASE WHEN NOT COALESCE((
        json_extract(NEW.consensus_provenance_json, '$.contract_version')
            = '{CONSENSUS_PROVENANCE_SCHEMA_VERSION}'
        AND json_extract(NEW.consensus_provenance_json, '$.candidate.locator')
            = NEW.source_locator
        AND json_extract(NEW.consensus_provenance_json, '$.candidate.sha256')
            = NEW.source_payload_sha256
        AND json_extract(NEW.consensus_provenance_json, '$.source_provenance.locator')
            = NEW.source_locator
        AND json_extract(NEW.consensus_provenance_json, '$.source_provenance.sha256')
            = NEW.source_payload_sha256
        AND json_type(NEW.consensus_provenance_json, '$.source_provenance.document') = 'object'
        AND json_extract(NEW.consensus_provenance_json, '$.source_provenance.document')
            = json_extract(NEW.consensus_provenance_json, '$.production')
        AND json_extract(NEW.consensus_provenance_json, '$.generated_at')
            = json_extract(NEW.consensus_provenance_json, '$.production.created_at')
        AND json_extract(NEW.consensus_provenance_json, '$.production.task_id')
            = 'B649_11_STREAM_CANONICAL_AGGREGATION_IMPLEMENT_AND_MATERIALIZE_115000087_R1'
        AND json_extract(NEW.consensus_provenance_json, '$.production.upstream_task_id')
            = 'B649_OPERATIONAL_PREDICTION_LOOP_R1'
        AND json_extract(
            NEW.consensus_provenance_json,
            '$.production.pre_outcome_temporal_integrity'
        )
            = 'PASS'
        AND json_extract(
            NEW.consensus_provenance_json,
            '$.production.stream_input_manifest_sha256'
        ) = json_extract(
            CAST(NEW.payload_bytes AS TEXT), '$.stream_input_manifest_sha256'
        )
        AND json_extract(NEW.consensus_provenance_json, '$.implementation.commit')
            = json_extract(NEW.consensus_provenance_json, '$.production.implementation.commit')
        AND json_extract(NEW.consensus_provenance_json, '$.implementation.tree')
            = json_extract(NEW.consensus_provenance_json, '$.production.implementation.tree')
        AND json_type(NEW.consensus_provenance_json, '$.implementation.source_hashes') = 'array'
        AND json_extract(NEW.consensus_provenance_json, '$.algorithm.algorithm_id')
            = 'build_canonical_consensus'
        AND json_extract(NEW.consensus_provenance_json, '$.algorithm.method_id')
            = '{CONSENSUS_METHOD_ID}'
        AND json_extract(NEW.consensus_provenance_json, '$.algorithm.method_version')
            = '{CONSENSUS_METHOD_VERSION}'
        AND json_extract(NEW.consensus_provenance_json, '$.algorithm.aggregation_unit')
            = '{CONSENSUS_AGGREGATION_UNIT}'
        AND json_extract(NEW.consensus_provenance_json, '$.algorithm.correlated_family_policy')
            = '{CONSENSUS_CORRELATED_FAMILY_POLICY}'
        AND json_extract(NEW.consensus_provenance_json, '$.algorithm.weight_policy')
            = 'EQUAL_STREAM_WEIGHT'
        AND json_extract(NEW.consensus_provenance_json, '$.algorithm.tie_break')
            = 'SUPPORT_UNITS_DESC_NUMBER_ASC'
        AND json_extract(NEW.consensus_provenance_json, '$.algorithm.score_denominator') = 66
        AND json_extract(NEW.consensus_provenance_json, '$.target.lottery_type')
            = '{CONSENSUS_TARGET_LOTTERY_TYPE}'
        AND json_extract(NEW.consensus_provenance_json, '$.target.draw_number')
            = '{CONSENSUS_TARGET_DRAW_NUMBER}'
        AND json_extract(NEW.consensus_provenance_json, '$.target.draw_date')
            = '{CONSENSUS_TARGET_DRAW_DATE}'
        AND json_extract(NEW.consensus_provenance_json, '$.target.scheduled_at')
            = '{CONSENSUS_TARGET_SCHEDULED_AT}'
        AND json_extract(NEW.consensus_provenance_json, '$.target.timezone')
            = '{CONSENSUS_TARGET_TIMEZONE}'
        AND json_extract(NEW.consensus_provenance_json, '$.target.cutoff')
            = '{CONSENSUS_TARGET_DATA_CUTOFF}'
        AND json_extract(NEW.consensus_provenance_json, '$.target.history_draw_count')
            = {CONSENSUS_TARGET_HISTORY_DRAW_COUNT}
        AND json_extract(NEW.consensus_provenance_json, '$.target.causal_history_sha256')
            = '{CONSENSUS_TARGET_HISTORY_SHA256}'
        AND json_extract(NEW.consensus_provenance_json, '$.target.temporal_class') = 'PRE_DRAW'
        AND json_extract(NEW.consensus_provenance_json, '$.target.target_result_used') = 0
        AND json_extract(NEW.consensus_provenance_json, '$.target.schedule_authority_sha256')
            = json_extract(NEW.target_json, '$.schedule_authority_sha256')
        AND json_extract(NEW.consensus_provenance_json, '$.strategy_reexecution') = 'NO'
        AND json_extract(NEW.consensus_provenance_json, '$.aggregation_reexecution') = 'NO'
        AND json_type(NEW.consensus_provenance_json, '$.streams') = 'array'
        AND json_type(NEW.consensus_provenance_json, '$.final_decision_ranking') = 'array'
        AND json_type(NEW.consensus_provenance_json, '$.final_recommended_output') = 'array'
    ), 0) THEN RAISE(ABORT, 'incomplete canonical consensus provenance') END;
    SELECT CASE WHEN COALESCE(
            json_array_length(NEW.consensus_provenance_json, '$.streams'), -1
        ) != 11
        OR EXISTS (
            SELECT 1 FROM json_each(NEW.consensus_provenance_json, '$.streams') AS item
            WHERE item.type != 'object'
               OR json_type(item.value, '$.strategy_id') != 'text'
               OR json_type(item.value, '$.strategy_version') != 'text'
               OR json_type(item.value, '$.prediction_run_id') != 'text'
               OR json_type(item.value, '$.source_relative_path') != 'text'
               OR json_type(item.value, '$.source_sha256') != 'text'
               OR length(json_extract(item.value, '$.source_sha256')) != 64
               OR json_extract(item.value, '$.source_sha256') GLOB '*[^0-9a-f]*'
               OR json_type(item.value, '$.native_ticket_count') != 'integer'
               OR json_extract(item.value, '$.native_ticket_count') < 1
               OR 6 % json_extract(item.value, '$.native_ticket_count') != 0
        ) THEN RAISE(ABORT, 'invalid canonical consensus stream lineage') END;
    SELECT CASE WHEN NOT COALESCE((
        json_extract(NEW.import_execution_json, '$.activation_event')
            = 'CANONICAL_CONSENSUS_PROMOTION_IMPORT'
        AND json_extract(NEW.import_execution_json, '$.aggregation_execution') = 'NOT_PERFORMED'
        AND json_extract(NEW.import_execution_json, '$.native_generation') = 'NOT_PERFORMED'
        AND json_extract(NEW.import_execution_json, '$.schedule_authority_sha256')
            = json_extract(NEW.target_json, '$.schedule_authority_sha256')
        AND json_type(NEW.import_execution_json, '$.promotion_executor_identity') = 'text'
        AND length(json_extract(NEW.import_execution_json, '$.promotion_executor_identity')) > 0
        AND json_type(NEW.import_execution_json, '$.promotion_attempted_at') = 'text'
        AND json_type(NEW.import_execution_json, '$.authorization_evidence_reference') = 'text'
        AND length(
            json_extract(NEW.import_execution_json, '$.authorization_evidence_reference')
        ) > 0
        AND json_type(NEW.import_execution_json, '$.execution_source.source_id') = 'text'
        AND json_type(NEW.import_execution_json, '$.execution_source.source_version') = 'text'
        AND json_type(NEW.import_execution_json, '$.command_runtime_identity.python') = 'text'
        AND json_type(NEW.import_execution_json, '$.command_runtime_identity.executable') = 'text'
        AND json_type(NEW.import_execution_json, '$.command_runtime_identity.command') = 'array'
    ), 0) THEN RAISE(ABORT, 'incomplete consensus promotion execution') END;
END
"""
_LIVE_TRIGGER_SQL = (
    _NATIVE_STRUCTURE_TRIGGER,
    """
    CREATE TRIGGER trg_live_forecast_run_identity
    BEFORE INSERT ON research_live_forecast_versions
    BEGIN
        SELECT CASE WHEN NOT EXISTS (
            SELECT 1 FROM research_runs
            WHERE id = NEW.run_id AND run_kind = 'LIVE_PREDICTION'
              AND status = 'COMPLETED' AND provenance_class = NEW.provenance_class
        ) THEN RAISE(ABORT, 'live forecast run identity mismatch') END;
    END
    """,
    *tuple(
        f"""
    CREATE TRIGGER trg_live_forecast_pointer_{operation.lower()}
    BEFORE {operation} ON research_live_forecast_current_pointer
    BEGIN
        SELECT CASE WHEN NOT EXISTS (
            SELECT 1 FROM research_live_forecast_versions
            WHERE version = NEW.version AND run_id = NEW.run_id
              AND lottery_type = NEW.lottery_type
              AND target_draw_number = NEW.target_draw_number
              AND target_draw_date = NEW.target_draw_date
              AND forecast_stream_id = NEW.forecast_stream_id
              AND forecast_stream_version = NEW.forecast_stream_version
              AND pointer_advanced = 1
        ) THEN RAISE(ABORT, 'live forecast pointer scope mismatch') END;
        {_POINTER_VERSION_GUARD if operation == "UPDATE" else ""}
    END
    """
        for operation in ("INSERT", "UPDATE")
    ),
    """
    CREATE TRIGGER trg_live_forecast_pointer_no_delete
    BEFORE DELETE ON research_live_forecast_current_pointer
    BEGIN
        SELECT RAISE(ABORT, 'live forecast pointer cannot be deleted');
    END
    """,
)
_V3_ADDED_STATEMENTS = (
    _LIVE_VERSION_SQL,
    _LIVE_POINTER_SQL,
    "CREATE UNIQUE INDEX idx_live_legacy_once ON research_live_forecast_versions "
    "(source_payload_sha256) WHERE provenance_class = 'LEGACY_MATERIALIZED'",
    *_append_only_trigger_statements("research_live_forecast_versions"),
    *_LIVE_TRIGGER_SQL,
)
_V4_LIVE_TRIGGER_SQL = (
    _NATIVE_STRUCTURE_TRIGGER,
    _CONSENSUS_STRUCTURE_TRIGGER,
    *_LIVE_TRIGGER_SQL[1:],
)
_V4_ADDED_STATEMENTS = (
    _V4_LIVE_VERSION_SQL,
    _LIVE_POINTER_SQL,
    "CREATE UNIQUE INDEX idx_live_legacy_once ON research_live_forecast_versions "
    "(source_payload_sha256) WHERE provenance_class = 'LEGACY_MATERIALIZED'",
    *_append_only_trigger_statements("research_live_forecast_versions"),
    *_V4_LIVE_TRIGGER_SQL,
)
_V2_RUN_COLUMNS = (
    "id, run_kind, rule_contract_id, input_dataset_identity, input_dataset_sha256, status, "
    "progress_cursor, expected_target_count, supersedes_run_id, derived_from_run_id, "
    "imported_from_artifact_id, producer_identity, execution_code_version, source_commit_oid, "
    "started_at, created_at"
)
V3_MIGRATION_STATEMENTS = (
    "CREATE TEMP TABLE research_v3_saved_runs AS SELECT * FROM research_runs",
    "DROP TABLE research_runs",
    _V3_RUNS_SQL,
    f"INSERT INTO research_runs ({_V2_RUN_COLUMNS}) SELECT {_V2_RUN_COLUMNS} "
    "FROM research_v3_saved_runs",
    "DROP TABLE research_v3_saved_runs",
    *tuple(
        s for s in MIGRATION_STATEMENTS if "ON research_runs " in s or "ON research_runs\n" in s
    ),
    *_V3_ADDED_STATEMENTS,
)
V3_MIGRATION_CHECKSUM = hashlib.sha256(
    (";\n".join(s.strip() for s in V3_MIGRATION_STATEMENTS) + ";\n").encode()
).hexdigest()
_V3_RUN_COLUMNS = f"{_V2_RUN_COLUMNS}, provenance_class"
_LIVE_VERSION_COLUMNS = ", ".join(
    (
        "version",
        "run_id",
        "request_id",
        "request_sha256",
        "lottery_type",
        "target_draw_number",
        "target_draw_date",
        "forecast_stream_id",
        "forecast_stream_version",
        "target_json",
        "provenance_class",
        "original_execution_provenance_status",
        "payload_bytes",
        "payload_sha256",
        "source_payload_sha256",
        "source_locator",
        "bundle_id",
        *ORIGINAL_FIELDS,
        "missing_provenance_json",
        "import_execution_json",
        "committed_at",
        "expected_current_version",
        "pointer_advanced",
        "provenance_envelope_json",
        "provenance_envelope_sha256",
    )
)
V4_MIGRATION_NAME = "append_canonical_consensus_promotion_contract"
V4_MIGRATION_STATEMENTS = (
    "CREATE TEMP TABLE research_v4_saved_runs AS SELECT * FROM research_runs",
    "CREATE TEMP TABLE research_v4_saved_live_versions AS "
    "SELECT * FROM research_live_forecast_versions",
    "CREATE TEMP TABLE research_v4_saved_pointer AS "
    "SELECT * FROM research_live_forecast_current_pointer",
    "DROP TABLE research_live_forecast_current_pointer",
    "DROP TABLE research_live_forecast_versions",
    "DROP TABLE research_runs",
    _V4_RUNS_SQL,
    f"INSERT INTO research_runs ({_V3_RUN_COLUMNS}) SELECT {_V3_RUN_COLUMNS} "
    "FROM research_v4_saved_runs",
    "DROP TABLE research_v4_saved_runs",
    *tuple(
        s for s in MIGRATION_STATEMENTS if "ON research_runs " in s or "ON research_runs\n" in s
    ),
    _V4_LIVE_VERSION_SQL,
    f"INSERT INTO research_live_forecast_versions ({_LIVE_VERSION_COLUMNS}, "
    "consensus_provenance_json) "
    f"SELECT {_LIVE_VERSION_COLUMNS}, NULL FROM research_v4_saved_live_versions",
    "DROP TABLE research_v4_saved_live_versions",
    _LIVE_POINTER_SQL,
    "INSERT INTO research_live_forecast_current_pointer SELECT * FROM research_v4_saved_pointer",
    "DROP TABLE research_v4_saved_pointer",
    "CREATE UNIQUE INDEX idx_live_legacy_once ON research_live_forecast_versions "
    "(source_payload_sha256) WHERE provenance_class = 'LEGACY_MATERIALIZED'",
    *_append_only_trigger_statements("research_live_forecast_versions"),
    *_V4_LIVE_TRIGGER_SQL,
)
V4_MIGRATION_CHECKSUM = hashlib.sha256(
    (";\n".join(s.strip() for s in V4_MIGRATION_STATEMENTS) + ";\n").encode()
).hexdigest()
TABLE_NAMES = (
    *V2_TABLE_NAMES,
    "research_live_forecast_versions",
    "research_live_forecast_current_pointer",
)
IMMUTABLE_TABLE_NAMES = (*V2_IMMUTABLE_TABLE_NAMES, "research_live_forecast_versions")
APPEND_ONLY_TRIGGER_NAMES = (
    *V2_APPEND_ONLY_TRIGGER_NAMES,
    "trg_research_live_forecast_versions_no_update",
    "trg_research_live_forecast_versions_no_delete",
)
V3_TABLE_NAMES = TABLE_NAMES
V3_IMMUTABLE_TABLE_NAMES = IMMUTABLE_TABLE_NAMES
V3_APPEND_ONLY_TRIGGER_NAMES = APPEND_ONLY_TRIGGER_NAMES
_V3_EXPECTED_SCHEMA_SQL_BY_NAME = {
    **_V2_EXPECTED_SCHEMA,
    "research_runs": _V3_RUNS_SQL,
    **{_object_name(s): s for s in _V3_ADDED_STATEMENTS},
}
_V4_EXPECTED_SCHEMA_SQL_BY_NAME = {
    **_V2_EXPECTED_SCHEMA,
    "research_runs": _V4_RUNS_SQL,
    **{_object_name(s): s for s in _V4_ADDED_STATEMENTS},
}
_EXPECTED_SCHEMA_SQL_BY_NAME = _V4_EXPECTED_SCHEMA_SQL_BY_NAME


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
    """Create, migrate, or verify the canonical research store atomically."""

    _validate_path_definition(paths)
    _validate_existing_paths(paths)
    directory_created = False
    database_created = False
    try:
        directory_created = _ensure_data_directory(paths.data_directory)
        database_created = _ensure_database_file(paths.database)
        with _raw_connection(paths, read_only=False) as connection:
            # SQLite's documented table-rebuild boundary: disable enforcement
            # outside the transaction, then check every FK before commit. No
            # application writer ever receives this migration-only connection.
            connection.execute("PRAGMA foreign_keys = OFF")
            connection.execute("BEGIN IMMEDIATE")
            try:
                if not _verify_migration_state(connection, allow_v2=True):
                    for statement in MIGRATION_STATEMENTS:
                        connection.execute(statement)
                    connection.execute(
                        """
                        INSERT INTO research_schema_migrations
                            (version, name, checksum, applied_at)
                        VALUES (?, ?, ?, ?)
                        """,
                        (
                            2,
                            MIGRATION_NAME,
                            MIGRATION_CHECKSUM,
                            _utc_now(),
                        ),
                    )
                version = connection.execute(
                    "SELECT MAX(version) FROM research_schema_migrations"
                ).fetchone()[0]
                if version == 2:
                    if connection.execute("PRAGMA foreign_key_check").fetchone() is not None:
                        raise ResearchSchemaError("pre-migration foreign-key violation")
                    for statement in V3_MIGRATION_STATEMENTS:
                        connection.execute(statement)
                    connection.execute(
                        "INSERT INTO research_schema_migrations VALUES (?, ?, ?, ?)",
                        (3, V3_MIGRATION_NAME, V3_MIGRATION_CHECKSUM, _utc_now()),
                    )
                    version = 3
                if version == 3:
                    if connection.execute("PRAGMA foreign_key_check").fetchone() is not None:
                        raise ResearchSchemaError("pre-v4-migration foreign-key violation")
                    for statement in V4_MIGRATION_STATEMENTS:
                        connection.execute(statement)
                    connection.execute(
                        "INSERT INTO research_schema_migrations VALUES (?, ?, ?, ?)",
                        (4, V4_MIGRATION_NAME, V4_MIGRATION_CHECKSUM, _utc_now()),
                    )
                if not _verify_migration_state(connection):
                    raise ResearchSchemaError("research schema migration did not reach version 4")
                if connection.execute("PRAGMA foreign_key_check").fetchone() is not None:
                    raise ResearchSchemaError("post-migration foreign-key violation")
            except BaseException:
                connection.rollback()
                raise
            else:
                connection.commit()
            finally:
                connection.execute("PRAGMA foreign_keys = ON")
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
        current_version = connection.execute(
            "SELECT MAX(version) FROM research_schema_migrations"
        ).fetchone()[0]
        if current_version != CURRENT_SCHEMA_VERSION:
            raise ResearchSchemaError("research schema is not at the current version")
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
        current_version = connection.execute(
            "SELECT MAX(version) FROM research_schema_migrations"
        ).fetchone()[0]
        if current_version != CURRENT_SCHEMA_VERSION:
            raise ResearchSchemaError("research schema is not at the current version")
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


def _verify_migration_state(connection: sqlite3.Connection, *, allow_v2: bool = False) -> bool:
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
        raise NewerSchemaVersionError("database schema is newer than this LottoLab build")
    if versions not in ([2], [2, 3], [2, 3, 4]):
        raise ResearchSchemaError("database migration history is incomplete")
    _, name, checksum = rows[0]
    if name != MIGRATION_NAME or checksum != MIGRATION_CHECKSUM:
        raise MigrationChecksumError("database migration checksum does not match")
    if versions == [2]:
        _verify_schema_semantics(connection, table_names, version=2)
        if not allow_v2:
            raise ResearchSchemaError("research schema v2 requires explicit v3 migration")
    elif versions == [2, 3]:
        if rows[1][1:] != (V3_MIGRATION_NAME, V3_MIGRATION_CHECKSUM):
            raise MigrationChecksumError("database v3 migration checksum does not match")
        _verify_schema_semantics(connection, table_names, version=3)
    else:
        if rows[1][1:] != (V3_MIGRATION_NAME, V3_MIGRATION_CHECKSUM):
            raise MigrationChecksumError("database v3 migration checksum does not match")
        if rows[2][1:] != (V4_MIGRATION_NAME, V4_MIGRATION_CHECKSUM):
            raise MigrationChecksumError("database v4 migration checksum does not match")
        _verify_schema_semantics(connection, table_names, version=4)
    return True


def _verify_schema_semantics(
    connection: sqlite3.Connection,
    table_names: set[str],
    *,
    version: int = CURRENT_SCHEMA_VERSION,
) -> None:
    if version == 2:
        expected_tables = V2_TABLE_NAMES
        expected_schema = _V2_EXPECTED_SCHEMA
    elif version == 3:
        expected_tables = V3_TABLE_NAMES
        expected_schema = _V3_EXPECTED_SCHEMA_SQL_BY_NAME
    elif version == 4:
        expected_tables = TABLE_NAMES
        expected_schema = _V4_EXPECTED_SCHEMA_SQL_BY_NAME
    else:
        raise ResearchSchemaError(f"unsupported schema verification version: {version}")
    if table_names != set(expected_tables):
        raise ResearchSchemaError(f"database tables do not match version {version}")
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
        expected_sql = expected_schema.get(name)
        if expected_sql is None or not isinstance(actual_sql, str):
            raise ResearchSchemaError(f"unexpected database schema object: {name}")
        if _canonical_schema_sql(actual_sql) != _canonical_schema_sql(expected_sql):
            raise ResearchSchemaError(
                f"database schema SQL does not match version {version}: {name}"
            )
    if seen_names != set(expected_schema):
        raise ResearchSchemaError(f"database schema objects do not match version {version}")
    for table in expected_tables:
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
    if stat.S_ISREG(metadata.st_mode) and metadata.st_uid == os.getuid() and metadata.st_nlink == 1:
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
    "V3_MIGRATION_CHECKSUM",
    "V3_MIGRATION_NAME",
    "V3_MIGRATION_STATEMENTS",
    "V4_MIGRATION_CHECKSUM",
    "V4_MIGRATION_NAME",
    "V4_MIGRATION_STATEMENTS",
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
