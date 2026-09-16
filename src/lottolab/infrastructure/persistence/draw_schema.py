"""Secure local path resolution and versioned SQLite schema for draw data."""

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
DATABASE_FILENAME = "lottolab.db"
CURRENT_SCHEMA_VERSION = 4
CONTEXT_SCHEMA_VERSION = 2
DRAW_SCHEDULE_SCHEMA_VERSION = 3
MIGRATION_NAME = "create_local_draw_data_schema"
CONTEXT_MIGRATION_NAME = "add_ingestion_run_context"
DRAW_SCHEDULE_MIGRATION_NAME = "add_canonical_draw_schedules"
SCHEDULE_AUTHORITY_MIGRATION_NAME = "add_t539_p638_schedule_authority"
BUSY_TIMEOUT_MS = 5_000


class LocalDataError(RuntimeError):
    """The local data path or database failed a safety check."""


class SchemaMigrationError(RuntimeError):
    """The local database schema is absent, corrupt, or incompatible."""


class NewerSchemaVersionError(SchemaMigrationError):
    """The database belongs to a newer LottoLab version."""


class MigrationChecksumError(SchemaMigrationError):
    """A recorded migration does not match the code-owned migration."""


@dataclass(frozen=True, slots=True)
class LocalDataPaths:
    """Resolved paths only; constructing this value never creates or opens anything."""

    data_directory: Path
    database: Path


MIGRATION_STATEMENTS = (
    """
    CREATE TABLE schema_migrations (
        version INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        checksum TEXT NOT NULL,
        applied_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE ingestion_runs (
        id TEXT PRIMARY KEY,
        operation_type TEXT NOT NULL,
        status TEXT NOT NULL,
        lottery_type TEXT,
        source_filename TEXT NOT NULL,
        source_sha256 TEXT NOT NULL,
        parser_version TEXT NOT NULL,
        total_count INTEGER NOT NULL CHECK (total_count >= 0),
        inserted_count INTEGER NOT NULL CHECK (inserted_count >= 0),
        skipped_count INTEGER NOT NULL CHECK (skipped_count >= 0),
        conflict_count INTEGER NOT NULL CHECK (conflict_count >= 0),
        failed_count INTEGER NOT NULL CHECK (failed_count >= 0),
        first_draw_number TEXT,
        last_draw_number TEXT,
        started_at TEXT NOT NULL,
        completed_at TEXT,
        error_summary TEXT
    )
    """,
    """
    CREATE TABLE draws (
        id INTEGER PRIMARY KEY,
        lottery_type TEXT NOT NULL,
        draw_number TEXT NOT NULL,
        draw_date TEXT NOT NULL,
        main_numbers_json TEXT NOT NULL,
        special_numbers_json TEXT NOT NULL,
        normalized_record_hash TEXT NOT NULL,
        source_name TEXT,
        source_reference TEXT,
        ingestion_run_id TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        UNIQUE (lottery_type, draw_number),
        FOREIGN KEY (ingestion_run_id) REFERENCES ingestion_runs(id) ON DELETE RESTRICT
    )
    """,
    """
    CREATE TABLE ingestion_items (
        id INTEGER PRIMARY KEY,
        ingestion_run_id TEXT NOT NULL,
        source_row_number INTEGER NOT NULL CHECK (source_row_number >= 1),
        lottery_type TEXT,
        draw_number TEXT,
        disposition TEXT NOT NULL,
        normalized_record_hash TEXT,
        message TEXT,
        FOREIGN KEY (ingestion_run_id) REFERENCES ingestion_runs(id) ON DELETE CASCADE
    )
    """,
    """
    CREATE INDEX idx_draws_history
    ON draws (lottery_type, draw_date DESC, draw_number DESC)
    """,
    """
    CREATE INDEX idx_ingestion_runs_history
    ON ingestion_runs (started_at DESC, id DESC)
    """,
    """
    CREATE INDEX idx_ingestion_items_run_row
    ON ingestion_items (ingestion_run_id, source_row_number, id)
    """,
)

MIGRATION_SQL = ";\n".join(statement.strip() for statement in MIGRATION_STATEMENTS) + ";\n"
MIGRATION_CHECKSUM = hashlib.sha256(MIGRATION_SQL.encode("utf-8")).hexdigest()
CONTEXT_MIGRATION_STATEMENTS = (
    """
    CREATE TABLE ingestion_run_context (
        ingestion_run_id TEXT PRIMARY KEY,
        trigger TEXT NOT NULL,
        provider TEXT,
        provider_version TEXT,
        requested_start TEXT,
        requested_end TEXT,
        resolved_start TEXT,
        resolved_end TEXT,
        fetched_count INTEGER NOT NULL CHECK (fetched_count >= 0),
        FOREIGN KEY (ingestion_run_id) REFERENCES ingestion_runs(id) ON DELETE CASCADE
    )
    """,
    """
    CREATE INDEX idx_ingestion_run_context_trigger
    ON ingestion_run_context (trigger, requested_start, ingestion_run_id)
    """,
)
CONTEXT_MIGRATION_SQL = (
    ";\n".join(statement.strip() for statement in CONTEXT_MIGRATION_STATEMENTS) + ";\n"
)
CONTEXT_MIGRATION_CHECKSUM = hashlib.sha256(
    CONTEXT_MIGRATION_SQL.encode("utf-8")
).hexdigest()
DRAW_SCHEDULE_MIGRATION_STATEMENTS = (
    """
    CREATE TABLE draw_schedules (
        id INTEGER PRIMARY KEY,
        lottery_type TEXT NOT NULL,
        draw_number TEXT NOT NULL,
        draw_date TEXT NOT NULL,
        scheduled_at TEXT NOT NULL,
        schedule_timezone TEXT NOT NULL,
        source_id TEXT NOT NULL,
        source_version TEXT NOT NULL,
        source_locator TEXT NOT NULL,
        source_payload_sha256 TEXT NOT NULL,
        source_observed_at TEXT NOT NULL,
        normalized_announcement_hash TEXT NOT NULL,
        ingestion_run_id TEXT NOT NULL,
        created_at TEXT NOT NULL,
        UNIQUE (lottery_type, draw_number),
        FOREIGN KEY (ingestion_run_id) REFERENCES ingestion_runs(id) ON DELETE RESTRICT
    )
    """,
    """
    CREATE INDEX idx_draw_schedules_earliest
    ON draw_schedules (lottery_type, scheduled_at, draw_date, draw_number)
    """,
    """
    CREATE TRIGGER trg_draw_schedules_reject_existing_draw
    BEFORE INSERT ON draw_schedules
    WHEN EXISTS (
        SELECT 1 FROM draws
        WHERE lottery_type = NEW.lottery_type
          AND draw_number = NEW.draw_number
    )
    BEGIN
        SELECT RAISE(ABORT, 'completed draw already exists for schedule identity');
    END
    """,
    """
    CREATE TRIGGER trg_draws_reject_schedule_date_mismatch_insert
    BEFORE INSERT ON draws
    WHEN EXISTS (
        SELECT 1 FROM draw_schedules
        WHERE lottery_type = NEW.lottery_type
          AND draw_number = NEW.draw_number
          AND draw_date <> NEW.draw_date
    )
    BEGIN
        SELECT RAISE(ABORT, 'completed draw date conflicts with schedule identity');
    END
    """,
    """
    CREATE TRIGGER trg_draws_reject_schedule_date_mismatch_update
    BEFORE UPDATE OF lottery_type, draw_number, draw_date ON draws
    WHEN EXISTS (
        SELECT 1 FROM draw_schedules
        WHERE lottery_type = OLD.lottery_type
          AND draw_number = OLD.draw_number
          AND (
              NEW.lottery_type <> OLD.lottery_type
              OR NEW.draw_number <> OLD.draw_number
              OR draw_date <> NEW.draw_date
          )
    ) OR EXISTS (
        SELECT 1 FROM draw_schedules
        WHERE lottery_type = NEW.lottery_type
          AND draw_number = NEW.draw_number
          AND draw_date <> NEW.draw_date
    )
    BEGIN
        SELECT RAISE(ABORT, 'completed draw date conflicts with schedule identity');
    END
    """,
)
DRAW_SCHEDULE_MIGRATION_SQL = (
    ";\n".join(statement.strip() for statement in DRAW_SCHEDULE_MIGRATION_STATEMENTS)
    + ";\n"
)
DRAW_SCHEDULE_MIGRATION_CHECKSUM = hashlib.sha256(
    DRAW_SCHEDULE_MIGRATION_SQL.encode("utf-8")
).hexdigest()
SCHEDULE_AUTHORITY_MIGRATION_STATEMENTS = (
    """
    CREATE TABLE draw_schedule_facts (
        schedule_id INTEGER PRIMARY KEY,
        official_game_code INTEGER NOT NULL CHECK (official_game_code > 0),
        scheduled_local_time TEXT NOT NULL,
        source_period_identifier TEXT,
        immutable_schedule_hash TEXT NOT NULL,
        authority_origin TEXT NOT NULL
            CHECK (authority_origin IN ('OFFICIAL', 'MANUAL')),
        FOREIGN KEY (schedule_id) REFERENCES draw_schedules(id) ON DELETE RESTRICT
    )
    """,
    """
    CREATE INDEX idx_draw_schedule_facts_game
    ON draw_schedule_facts (official_game_code, schedule_id)
    """,
    """
    CREATE TABLE draw_schedule_authority_evidence (
        id INTEGER PRIMARY KEY,
        schedule_id INTEGER,
        lottery_type TEXT NOT NULL,
        official_game_code INTEGER NOT NULL CHECK (official_game_code > 0),
        draw_number TEXT,
        draw_date TEXT,
        scheduled_local_time TEXT,
        schedule_timezone TEXT,
        scheduled_at TEXT,
        source_period_identifier TEXT,
        event_kind TEXT NOT NULL,
        disposition TEXT NOT NULL,
        detail_code TEXT NOT NULL,
        source_id TEXT NOT NULL,
        source_version TEXT NOT NULL,
        source_locator TEXT NOT NULL,
        source_payload_sha256 TEXT NOT NULL,
        source_observed_at TEXT NOT NULL,
        immutable_schedule_hash TEXT,
        certificate_input_sha256 TEXT,
        certificate_document_sha256 TEXT,
        certified_at TEXT,
        certifying_authority TEXT,
        certification_reason TEXT,
        supporting_artifact_type TEXT,
        run_id TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY (schedule_id) REFERENCES draw_schedules(id) ON DELETE RESTRICT,
        FOREIGN KEY (run_id) REFERENCES ingestion_runs(id) ON DELETE RESTRICT
    )
    """,
    """
    CREATE INDEX idx_draw_schedule_authority_evidence_target
    ON draw_schedule_authority_evidence (lottery_type, draw_number, id)
    """,
    """
    CREATE INDEX idx_draw_schedule_authority_evidence_state
    ON draw_schedule_authority_evidence (
        lottery_type, event_kind, source_observed_at, id
    )
    """,
    """
    CREATE TRIGGER trg_draw_schedules_reject_update
    BEFORE UPDATE ON draw_schedules
    BEGIN
        SELECT RAISE(ABORT, 'canonical schedule facts are immutable');
    END
    """,
    """
    CREATE TRIGGER trg_draw_schedules_reject_delete
    BEFORE DELETE ON draw_schedules
    BEGIN
        SELECT RAISE(ABORT, 'canonical schedule facts cannot be deleted');
    END
    """,
    """
    CREATE TRIGGER trg_draw_schedule_facts_reject_update
    BEFORE UPDATE ON draw_schedule_facts
    BEGIN
        SELECT RAISE(ABORT, 'canonical schedule fact metadata is immutable');
    END
    """,
    """
    CREATE TRIGGER trg_draw_schedule_facts_reject_delete
    BEFORE DELETE ON draw_schedule_facts
    BEGIN
        SELECT RAISE(ABORT, 'canonical schedule fact metadata cannot be deleted');
    END
    """,
    """
    CREATE TRIGGER trg_draw_schedule_authority_evidence_reject_update
    BEFORE UPDATE ON draw_schedule_authority_evidence
    BEGIN
        SELECT RAISE(ABORT, 'schedule authority evidence is append-only');
    END
    """,
    """
    CREATE TRIGGER trg_draw_schedule_authority_evidence_reject_delete
    BEFORE DELETE ON draw_schedule_authority_evidence
    BEGIN
        SELECT RAISE(ABORT, 'schedule authority evidence is append-only');
    END
    """,
)
SCHEDULE_AUTHORITY_MIGRATION_SQL = (
    ";\n".join(statement.strip() for statement in SCHEDULE_AUTHORITY_MIGRATION_STATEMENTS)
    + ";\n"
)
SCHEDULE_AUTHORITY_MIGRATION_CHECKSUM = hashlib.sha256(
    SCHEDULE_AUTHORITY_MIGRATION_SQL.encode("utf-8")
).hexdigest()

_EXPECTED_TABLE_XINFO = {
    "schema_migrations": (
        (0, "version", "INTEGER", 0, None, 1, 0),
        (1, "name", "TEXT", 1, None, 0, 0),
        (2, "checksum", "TEXT", 1, None, 0, 0),
        (3, "applied_at", "TEXT", 1, None, 0, 0),
    ),
    "ingestion_runs": (
        (0, "id", "TEXT", 0, None, 1, 0),
        (1, "operation_type", "TEXT", 1, None, 0, 0),
        (2, "status", "TEXT", 1, None, 0, 0),
        (3, "lottery_type", "TEXT", 0, None, 0, 0),
        (4, "source_filename", "TEXT", 1, None, 0, 0),
        (5, "source_sha256", "TEXT", 1, None, 0, 0),
        (6, "parser_version", "TEXT", 1, None, 0, 0),
        (7, "total_count", "INTEGER", 1, None, 0, 0),
        (8, "inserted_count", "INTEGER", 1, None, 0, 0),
        (9, "skipped_count", "INTEGER", 1, None, 0, 0),
        (10, "conflict_count", "INTEGER", 1, None, 0, 0),
        (11, "failed_count", "INTEGER", 1, None, 0, 0),
        (12, "first_draw_number", "TEXT", 0, None, 0, 0),
        (13, "last_draw_number", "TEXT", 0, None, 0, 0),
        (14, "started_at", "TEXT", 1, None, 0, 0),
        (15, "completed_at", "TEXT", 0, None, 0, 0),
        (16, "error_summary", "TEXT", 0, None, 0, 0),
    ),
    "draws": (
        (0, "id", "INTEGER", 0, None, 1, 0),
        (1, "lottery_type", "TEXT", 1, None, 0, 0),
        (2, "draw_number", "TEXT", 1, None, 0, 0),
        (3, "draw_date", "TEXT", 1, None, 0, 0),
        (4, "main_numbers_json", "TEXT", 1, None, 0, 0),
        (5, "special_numbers_json", "TEXT", 1, None, 0, 0),
        (6, "normalized_record_hash", "TEXT", 1, None, 0, 0),
        (7, "source_name", "TEXT", 0, None, 0, 0),
        (8, "source_reference", "TEXT", 0, None, 0, 0),
        (9, "ingestion_run_id", "TEXT", 1, None, 0, 0),
        (10, "created_at", "TEXT", 1, None, 0, 0),
        (11, "updated_at", "TEXT", 1, None, 0, 0),
    ),
    "ingestion_items": (
        (0, "id", "INTEGER", 0, None, 1, 0),
        (1, "ingestion_run_id", "TEXT", 1, None, 0, 0),
        (2, "source_row_number", "INTEGER", 1, None, 0, 0),
        (3, "lottery_type", "TEXT", 0, None, 0, 0),
        (4, "draw_number", "TEXT", 0, None, 0, 0),
        (5, "disposition", "TEXT", 1, None, 0, 0),
        (6, "normalized_record_hash", "TEXT", 0, None, 0, 0),
        (7, "message", "TEXT", 0, None, 0, 0),
    ),
}

_EXPECTED_TABLE_XINFO_V2 = {
    **_EXPECTED_TABLE_XINFO,
    "ingestion_run_context": (
        (0, "ingestion_run_id", "TEXT", 0, None, 1, 0),
        (1, "trigger", "TEXT", 1, None, 0, 0),
        (2, "provider", "TEXT", 0, None, 0, 0),
        (3, "provider_version", "TEXT", 0, None, 0, 0),
        (4, "requested_start", "TEXT", 0, None, 0, 0),
        (5, "requested_end", "TEXT", 0, None, 0, 0),
        (6, "resolved_start", "TEXT", 0, None, 0, 0),
        (7, "resolved_end", "TEXT", 0, None, 0, 0),
        (8, "fetched_count", "INTEGER", 1, None, 0, 0),
    ),
}

_EXPECTED_TABLE_XINFO_V3 = {
    **_EXPECTED_TABLE_XINFO_V2,
    "draw_schedules": (
        (0, "id", "INTEGER", 0, None, 1, 0),
        (1, "lottery_type", "TEXT", 1, None, 0, 0),
        (2, "draw_number", "TEXT", 1, None, 0, 0),
        (3, "draw_date", "TEXT", 1, None, 0, 0),
        (4, "scheduled_at", "TEXT", 1, None, 0, 0),
        (5, "schedule_timezone", "TEXT", 1, None, 0, 0),
        (6, "source_id", "TEXT", 1, None, 0, 0),
        (7, "source_version", "TEXT", 1, None, 0, 0),
        (8, "source_locator", "TEXT", 1, None, 0, 0),
        (9, "source_payload_sha256", "TEXT", 1, None, 0, 0),
        (10, "source_observed_at", "TEXT", 1, None, 0, 0),
        (11, "normalized_announcement_hash", "TEXT", 1, None, 0, 0),
        (12, "ingestion_run_id", "TEXT", 1, None, 0, 0),
        (13, "created_at", "TEXT", 1, None, 0, 0),
    ),
}

_EXPECTED_TABLE_XINFO_V4 = {
    **_EXPECTED_TABLE_XINFO_V3,
    "draw_schedule_facts": (
        (0, "schedule_id", "INTEGER", 0, None, 1, 0),
        (1, "official_game_code", "INTEGER", 1, None, 0, 0),
        (2, "scheduled_local_time", "TEXT", 1, None, 0, 0),
        (3, "source_period_identifier", "TEXT", 0, None, 0, 0),
        (4, "immutable_schedule_hash", "TEXT", 1, None, 0, 0),
        (5, "authority_origin", "TEXT", 1, None, 0, 0),
    ),
    "draw_schedule_authority_evidence": (
        (0, "id", "INTEGER", 0, None, 1, 0),
        (1, "schedule_id", "INTEGER", 0, None, 0, 0),
        (2, "lottery_type", "TEXT", 1, None, 0, 0),
        (3, "official_game_code", "INTEGER", 1, None, 0, 0),
        (4, "draw_number", "TEXT", 0, None, 0, 0),
        (5, "draw_date", "TEXT", 0, None, 0, 0),
        (6, "scheduled_local_time", "TEXT", 0, None, 0, 0),
        (7, "schedule_timezone", "TEXT", 0, None, 0, 0),
        (8, "scheduled_at", "TEXT", 0, None, 0, 0),
        (9, "source_period_identifier", "TEXT", 0, None, 0, 0),
        (10, "event_kind", "TEXT", 1, None, 0, 0),
        (11, "disposition", "TEXT", 1, None, 0, 0),
        (12, "detail_code", "TEXT", 1, None, 0, 0),
        (13, "source_id", "TEXT", 1, None, 0, 0),
        (14, "source_version", "TEXT", 1, None, 0, 0),
        (15, "source_locator", "TEXT", 1, None, 0, 0),
        (16, "source_payload_sha256", "TEXT", 1, None, 0, 0),
        (17, "source_observed_at", "TEXT", 1, None, 0, 0),
        (18, "immutable_schedule_hash", "TEXT", 0, None, 0, 0),
        (19, "certificate_input_sha256", "TEXT", 0, None, 0, 0),
        (20, "certificate_document_sha256", "TEXT", 0, None, 0, 0),
        (21, "certified_at", "TEXT", 0, None, 0, 0),
        (22, "certifying_authority", "TEXT", 0, None, 0, 0),
        (23, "certification_reason", "TEXT", 0, None, 0, 0),
        (24, "supporting_artifact_type", "TEXT", 0, None, 0, 0),
        (25, "run_id", "TEXT", 1, None, 0, 0),
        (26, "created_at", "TEXT", 1, None, 0, 0),
    ),
}

_EXPECTED_INDEX_LIST = {
    "schema_migrations": {},
    "ingestion_runs": {
        "idx_ingestion_runs_history": (0, "c", 0),
        "sqlite_autoindex_ingestion_runs_1": (1, "pk", 0),
    },
    "draws": {
        "idx_draws_history": (0, "c", 0),
        "sqlite_autoindex_draws_1": (1, "u", 0),
    },
    "ingestion_items": {
        "idx_ingestion_items_run_row": (0, "c", 0),
    },
}

_EXPECTED_INDEX_LIST_V2 = {
    **_EXPECTED_INDEX_LIST,
    "ingestion_run_context": {
        "idx_ingestion_run_context_trigger": (0, "c", 0),
        "sqlite_autoindex_ingestion_run_context_1": (1, "pk", 0),
    },
}

_EXPECTED_INDEX_LIST_V3 = {
    **_EXPECTED_INDEX_LIST_V2,
    "draw_schedules": {
        "idx_draw_schedules_earliest": (0, "c", 0),
        "sqlite_autoindex_draw_schedules_1": (1, "u", 0),
    },
}

_EXPECTED_INDEX_LIST_V4 = {
    **_EXPECTED_INDEX_LIST_V3,
    "draw_schedule_facts": {
        "idx_draw_schedule_facts_game": (0, "c", 0),
    },
    "draw_schedule_authority_evidence": {
        "idx_draw_schedule_authority_evidence_state": (0, "c", 0),
        "idx_draw_schedule_authority_evidence_target": (0, "c", 0),
    },
}

_EXPECTED_INDEX_XINFO = {
    "sqlite_autoindex_ingestion_runs_1": (
        (0, 0, "id", 0, "BINARY", 1),
        (1, -1, None, 0, "BINARY", 0),
    ),
    "sqlite_autoindex_draws_1": (
        (0, 1, "lottery_type", 0, "BINARY", 1),
        (1, 2, "draw_number", 0, "BINARY", 1),
        (2, -1, None, 0, "BINARY", 0),
    ),
    "idx_draws_history": (
        (0, 1, "lottery_type", 0, "BINARY", 1),
        (1, 3, "draw_date", 1, "BINARY", 1),
        (2, 2, "draw_number", 1, "BINARY", 1),
        (3, -1, None, 0, "BINARY", 0),
    ),
    "idx_ingestion_runs_history": (
        (0, 14, "started_at", 1, "BINARY", 1),
        (1, 0, "id", 1, "BINARY", 1),
        (2, -1, None, 0, "BINARY", 0),
    ),
    "idx_ingestion_items_run_row": (
        (0, 1, "ingestion_run_id", 0, "BINARY", 1),
        (1, 2, "source_row_number", 0, "BINARY", 1),
        (2, 0, "id", 0, "BINARY", 1),
        (3, -1, None, 0, "BINARY", 0),
    ),
}

_EXPECTED_INDEX_XINFO_V2 = {
    **_EXPECTED_INDEX_XINFO,
    "sqlite_autoindex_ingestion_run_context_1": (
        (0, 0, "ingestion_run_id", 0, "BINARY", 1),
        (1, -1, None, 0, "BINARY", 0),
    ),
    "idx_ingestion_run_context_trigger": (
        (0, 1, "trigger", 0, "BINARY", 1),
        (1, 4, "requested_start", 0, "BINARY", 1),
        (2, 0, "ingestion_run_id", 0, "BINARY", 1),
        (3, -1, None, 0, "BINARY", 0),
    ),
}

_EXPECTED_INDEX_XINFO_V3 = {
    **_EXPECTED_INDEX_XINFO_V2,
    "sqlite_autoindex_draw_schedules_1": (
        (0, 1, "lottery_type", 0, "BINARY", 1),
        (1, 2, "draw_number", 0, "BINARY", 1),
        (2, -1, None, 0, "BINARY", 0),
    ),
    "idx_draw_schedules_earliest": (
        (0, 1, "lottery_type", 0, "BINARY", 1),
        (1, 4, "scheduled_at", 0, "BINARY", 1),
        (2, 3, "draw_date", 0, "BINARY", 1),
        (3, 2, "draw_number", 0, "BINARY", 1),
        (4, -1, None, 0, "BINARY", 0),
    ),
}

_EXPECTED_INDEX_XINFO_V4 = {
    **_EXPECTED_INDEX_XINFO_V3,
    "idx_draw_schedule_facts_game": (
        (0, 1, "official_game_code", 0, "BINARY", 1),
        (1, 0, "schedule_id", 0, "BINARY", 1),
        (2, -1, None, 0, "BINARY", 0),
    ),
    "idx_draw_schedule_authority_evidence_target": (
        (0, 2, "lottery_type", 0, "BINARY", 1),
        (1, 4, "draw_number", 0, "BINARY", 1),
        (2, 0, "id", 0, "BINARY", 1),
        (3, -1, None, 0, "BINARY", 0),
    ),
    "idx_draw_schedule_authority_evidence_state": (
        (0, 2, "lottery_type", 0, "BINARY", 1),
        (1, 10, "event_kind", 0, "BINARY", 1),
        (2, 17, "source_observed_at", 0, "BINARY", 1),
        (3, 0, "id", 0, "BINARY", 1),
        (4, -1, None, 0, "BINARY", 0),
    ),
}

_EXPECTED_FOREIGN_KEYS = {
    "schema_migrations": (),
    "ingestion_runs": (),
    "draws": ((0, 0, "ingestion_runs", "ingestion_run_id", "id", "NO ACTION", "RESTRICT", "NONE"),),
    "ingestion_items": (
        (0, 0, "ingestion_runs", "ingestion_run_id", "id", "NO ACTION", "CASCADE", "NONE"),
    ),
}

_EXPECTED_FOREIGN_KEYS_V2 = {
    **_EXPECTED_FOREIGN_KEYS,
    "ingestion_run_context": (
        (
            0,
            0,
            "ingestion_runs",
            "ingestion_run_id",
            "id",
            "NO ACTION",
            "CASCADE",
            "NONE",
        ),
    ),
}

_EXPECTED_FOREIGN_KEYS_V3 = {
    **_EXPECTED_FOREIGN_KEYS_V2,
    "draw_schedules": (
        (
            0,
            0,
            "ingestion_runs",
            "ingestion_run_id",
            "id",
            "NO ACTION",
            "RESTRICT",
            "NONE",
        ),
    ),
}

_EXPECTED_FOREIGN_KEYS_V4 = {
    **_EXPECTED_FOREIGN_KEYS_V3,
    "draw_schedule_facts": (
        (
            0,
            0,
            "draw_schedules",
            "schedule_id",
            "id",
            "NO ACTION",
            "RESTRICT",
            "NONE",
        ),
    ),
    "draw_schedule_authority_evidence": (
        (
            0,
            0,
            "ingestion_runs",
            "run_id",
            "id",
            "NO ACTION",
            "RESTRICT",
            "NONE",
        ),
        (
            1,
            0,
            "draw_schedules",
            "schedule_id",
            "id",
            "NO ACTION",
            "RESTRICT",
            "NONE",
        ),
    ),
}

_EXPECTED_SCHEMA_SQL = {
    "schema_migrations": MIGRATION_STATEMENTS[0],
    "ingestion_runs": MIGRATION_STATEMENTS[1],
    "draws": MIGRATION_STATEMENTS[2],
    "ingestion_items": MIGRATION_STATEMENTS[3],
    "idx_draws_history": MIGRATION_STATEMENTS[4],
    "idx_ingestion_runs_history": MIGRATION_STATEMENTS[5],
    "idx_ingestion_items_run_row": MIGRATION_STATEMENTS[6],
    "sqlite_autoindex_draws_1": None,
    "sqlite_autoindex_ingestion_runs_1": None,
}

_EXPECTED_SCHEMA_SQL_V2 = {
    **_EXPECTED_SCHEMA_SQL,
    "ingestion_run_context": CONTEXT_MIGRATION_STATEMENTS[0],
    "idx_ingestion_run_context_trigger": CONTEXT_MIGRATION_STATEMENTS[1],
    "sqlite_autoindex_ingestion_run_context_1": None,
}

_EXPECTED_SCHEMA_SQL_V3 = {
    **_EXPECTED_SCHEMA_SQL_V2,
    "draw_schedules": DRAW_SCHEDULE_MIGRATION_STATEMENTS[0],
    "idx_draw_schedules_earliest": DRAW_SCHEDULE_MIGRATION_STATEMENTS[1],
    "trg_draw_schedules_reject_existing_draw": DRAW_SCHEDULE_MIGRATION_STATEMENTS[2],
    "trg_draws_reject_schedule_date_mismatch_insert": DRAW_SCHEDULE_MIGRATION_STATEMENTS[3],
    "trg_draws_reject_schedule_date_mismatch_update": DRAW_SCHEDULE_MIGRATION_STATEMENTS[4],
    "sqlite_autoindex_draw_schedules_1": None,
}

_EXPECTED_SCHEMA_SQL_V4 = {
    **_EXPECTED_SCHEMA_SQL_V3,
    "draw_schedule_facts": SCHEDULE_AUTHORITY_MIGRATION_STATEMENTS[0],
    "idx_draw_schedule_facts_game": SCHEDULE_AUTHORITY_MIGRATION_STATEMENTS[1],
    "draw_schedule_authority_evidence": SCHEDULE_AUTHORITY_MIGRATION_STATEMENTS[2],
    "idx_draw_schedule_authority_evidence_target": (
        SCHEDULE_AUTHORITY_MIGRATION_STATEMENTS[3]
    ),
    "idx_draw_schedule_authority_evidence_state": (
        SCHEDULE_AUTHORITY_MIGRATION_STATEMENTS[4]
    ),
    "trg_draw_schedules_reject_update": SCHEDULE_AUTHORITY_MIGRATION_STATEMENTS[5],
    "trg_draw_schedules_reject_delete": SCHEDULE_AUTHORITY_MIGRATION_STATEMENTS[6],
    "trg_draw_schedule_facts_reject_update": SCHEDULE_AUTHORITY_MIGRATION_STATEMENTS[7],
    "trg_draw_schedule_facts_reject_delete": SCHEDULE_AUTHORITY_MIGRATION_STATEMENTS[8],
    "trg_draw_schedule_authority_evidence_reject_update": (
        SCHEDULE_AUTHORITY_MIGRATION_STATEMENTS[9]
    ),
    "trg_draw_schedule_authority_evidence_reject_delete": (
        SCHEDULE_AUTHORITY_MIGRATION_STATEMENTS[10]
    ),
}

_EXPECTED_SCHEMA_OBJECTS = {("table", name, name) for name in _EXPECTED_TABLE_XINFO} | {
    ("index", "idx_draws_history", "draws"),
    ("index", "idx_ingestion_runs_history", "ingestion_runs"),
    ("index", "idx_ingestion_items_run_row", "ingestion_items"),
    ("index", "sqlite_autoindex_draws_1", "draws"),
    ("index", "sqlite_autoindex_ingestion_runs_1", "ingestion_runs"),
}

_EXPECTED_SCHEMA_OBJECTS_V2 = {
    ("table", name, name) for name in _EXPECTED_TABLE_XINFO_V2
} | {
    (object_type, name, table)
    for object_type, name, table in _EXPECTED_SCHEMA_OBJECTS
    if object_type == "index"
} | {
    ("index", "idx_ingestion_run_context_trigger", "ingestion_run_context"),
    ("index", "sqlite_autoindex_ingestion_run_context_1", "ingestion_run_context"),
}

_EXPECTED_SCHEMA_OBJECTS_V3 = {
    ("table", name, name) for name in _EXPECTED_TABLE_XINFO_V3
} | {
    (object_type, name, table)
    for object_type, name, table in _EXPECTED_SCHEMA_OBJECTS_V2
    if object_type == "index"
} | {
    ("index", "idx_draw_schedules_earliest", "draw_schedules"),
    ("index", "sqlite_autoindex_draw_schedules_1", "draw_schedules"),
    (
        "trigger",
        "trg_draw_schedules_reject_existing_draw",
        "draw_schedules",
    ),
    (
        "trigger",
        "trg_draws_reject_schedule_date_mismatch_insert",
        "draws",
    ),
    (
        "trigger",
        "trg_draws_reject_schedule_date_mismatch_update",
        "draws",
    ),
}

_EXPECTED_SCHEMA_OBJECTS_V4 = {
    ("table", name, name) for name in _EXPECTED_TABLE_XINFO_V4
} | {
    (object_type, name, table)
    for object_type, name, table in _EXPECTED_SCHEMA_OBJECTS_V3
    if object_type != "table"
} | {
    ("index", "idx_draw_schedule_facts_game", "draw_schedule_facts"),
    (
        "index",
        "idx_draw_schedule_authority_evidence_target",
        "draw_schedule_authority_evidence",
    ),
    (
        "index",
        "idx_draw_schedule_authority_evidence_state",
        "draw_schedule_authority_evidence",
    ),
    ("trigger", "trg_draw_schedules_reject_update", "draw_schedules"),
    ("trigger", "trg_draw_schedules_reject_delete", "draw_schedules"),
    (
        "trigger",
        "trg_draw_schedule_facts_reject_update",
        "draw_schedule_facts",
    ),
    (
        "trigger",
        "trg_draw_schedule_facts_reject_delete",
        "draw_schedule_facts",
    ),
    (
        "trigger",
        "trg_draw_schedule_authority_evidence_reject_update",
        "draw_schedule_authority_evidence",
    ),
    (
        "trigger",
        "trg_draw_schedule_authority_evidence_reject_delete",
        "draw_schedule_authority_evidence",
    ),
}

_SCHEMA_SQL_TOKEN = re.compile(
    r"'(?:''|[^'])*'|\"(?:\"\"|[^\"])*\"|`(?:``|[^`])*`|\[[^]]*\]|[(),]|[^\s(),]+"
)


def resolve_local_data_paths(
    *,
    environ: Mapping[str, str] | None = None,
    home: Path | None = None,
) -> LocalDataPaths:
    """Resolve the configured location without creating directories or opening SQLite."""

    selected_environment = os.environ if environ is None else environ
    if DATA_DIRECTORY_ENV in selected_environment:
        configured = selected_environment[DATA_DIRECTORY_ENV]
        if not configured.strip():
            raise LocalDataError(f"{DATA_DIRECTORY_ENV} must not be empty")
        data_directory = Path(configured)
    else:
        selected_home = Path.home() if home is None else home
        data_directory = selected_home / "Library" / "Application Support" / "LottoLab"

    paths = LocalDataPaths(
        data_directory=data_directory,
        database=data_directory / DATABASE_FILENAME,
    )
    _validate_path_definition(paths)
    _validate_existing_paths(paths)
    return paths


def initialize_schema(paths: LocalDataPaths) -> None:
    """Securely create or upgrade the local draw database in one transaction."""

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
                version = _verify_migration_state(connection)
                if version is None:
                    for statement in MIGRATION_STATEMENTS:
                        connection.execute(statement)
                    connection.execute(
                        """
                        INSERT INTO schema_migrations (version, name, checksum, applied_at)
                        VALUES (?, ?, ?, ?)
                        """,
                        (
                            1,
                            MIGRATION_NAME,
                            MIGRATION_CHECKSUM,
                            _utc_now(),
                        ),
                    )
                    version = _verify_migration_state(connection)
                if version == 1:
                    for statement in CONTEXT_MIGRATION_STATEMENTS:
                        connection.execute(statement)
                    connection.execute(
                        """
                        INSERT INTO schema_migrations (version, name, checksum, applied_at)
                        VALUES (?, ?, ?, ?)
                        """,
                        (
                            CONTEXT_SCHEMA_VERSION,
                            CONTEXT_MIGRATION_NAME,
                            CONTEXT_MIGRATION_CHECKSUM,
                            _utc_now(),
                        ),
                    )
                    version = _verify_migration_state(connection)
                if version == CONTEXT_SCHEMA_VERSION:
                    for statement in DRAW_SCHEDULE_MIGRATION_STATEMENTS:
                        connection.execute(statement)
                    connection.execute(
                        """
                        INSERT INTO schema_migrations (version, name, checksum, applied_at)
                        VALUES (?, ?, ?, ?)
                        """,
                        (
                            DRAW_SCHEDULE_SCHEMA_VERSION,
                            DRAW_SCHEDULE_MIGRATION_NAME,
                            DRAW_SCHEDULE_MIGRATION_CHECKSUM,
                            _utc_now(),
                        ),
                    )
                    version = _verify_migration_state(connection)
                if version == DRAW_SCHEDULE_SCHEMA_VERSION:
                    for statement in SCHEDULE_AUTHORITY_MIGRATION_STATEMENTS:
                        connection.execute(statement)
                    connection.execute(
                        """
                        INSERT INTO schema_migrations (version, name, checksum, applied_at)
                        VALUES (?, ?, ?, ?)
                        """,
                        (
                            CURRENT_SCHEMA_VERSION,
                            SCHEDULE_AUTHORITY_MIGRATION_NAME,
                            SCHEDULE_AUTHORITY_MIGRATION_CHECKSUM,
                            _utc_now(),
                        ),
                    )
                    version = _verify_migration_state(connection)
                if version != CURRENT_SCHEMA_VERSION:
                    raise SchemaMigrationError(
                        f"schema migration did not reach version {CURRENT_SCHEMA_VERSION}"
                    )
            except BaseException:
                connection.rollback()
                raise
            else:
                connection.commit()
        _validate_existing_paths(paths)
        _reject_wal_sidecars(paths.database)
    except (LocalDataError, SchemaMigrationError):
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
        raise SchemaMigrationError("SQLite schema migration failed") from exc


def verify_schema_read_only(paths: LocalDataPaths) -> bool:
    """Return False for an absent DB; validate an existing DB without creating it."""

    _validate_path_definition(paths)
    _validate_existing_paths(paths)
    if not paths.database.exists():
        return False
    with _raw_connection(paths, read_only=True) as connection:
        try:
            version = _verify_migration_state(connection)
        except sqlite3.DatabaseError as exc:
            raise SchemaMigrationError("SQLite schema verification failed") from exc
        if version is None:
            raise SchemaMigrationError("database exists without a schema migration")
    _validate_existing_paths(paths)
    return True


@contextmanager
def open_database(
    paths: LocalDataPaths, *, read_only: bool = False
) -> Generator[sqlite3.Connection]:
    """Open a fresh configured connection to an existing verified draw DB."""

    _validate_path_definition(paths)
    _validate_existing_paths(paths)
    if not paths.database.exists():
        raise SchemaMigrationError("local draw database does not exist")
    with _raw_connection(paths, read_only=read_only) as connection:
        try:
            version = _verify_migration_state(connection)
        except sqlite3.DatabaseError as exc:
            raise SchemaMigrationError("SQLite schema verification failed") from exc
        if version is None:
            raise SchemaMigrationError("database exists without a schema migration")
        yield connection


@contextmanager
def _raw_connection(paths: LocalDataPaths, *, read_only: bool) -> Generator[sqlite3.Connection]:
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
        raise SchemaMigrationError("cannot open the local draw database safely") from exc
    try:
        try:
            connection.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}")
            connection.execute("PRAGMA foreign_keys = ON")
            if connection.execute("PRAGMA foreign_keys").fetchone() != (1,):
                raise SchemaMigrationError("SQLite foreign-key enforcement is unavailable")
            if read_only:
                connection.execute("PRAGMA query_only = ON")
                journal_mode = connection.execute("PRAGMA journal_mode").fetchone()
            else:
                journal_mode = connection.execute("PRAGMA journal_mode = DELETE").fetchone()
            if journal_mode is None or str(journal_mode[0]).lower() != "delete":
                raise SchemaMigrationError("SQLite must use DELETE journal mode")
        except sqlite3.DatabaseError as exc:
            raise SchemaMigrationError("cannot configure SQLite safely") from exc
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
    if "schema_migrations" not in table_names:
        if table_names:
            raise SchemaMigrationError("unversioned database contains application tables")
        return None

    rows = connection.execute(
        "SELECT version, name, checksum FROM schema_migrations ORDER BY version"
    ).fetchall()
    try:
        versions = [int(row[0]) for row in rows]
    except (TypeError, ValueError) as exc:
        raise SchemaMigrationError("database migration versions are invalid") from exc
    if any(version > CURRENT_SCHEMA_VERSION for version in versions):
        raise NewerSchemaVersionError("database schema is newer than this LottoLab build")
    if versions not in (
        [1],
        [1, CONTEXT_SCHEMA_VERSION],
        [1, CONTEXT_SCHEMA_VERSION, DRAW_SCHEDULE_SCHEMA_VERSION],
        [
            1,
            CONTEXT_SCHEMA_VERSION,
            DRAW_SCHEDULE_SCHEMA_VERSION,
            CURRENT_SCHEMA_VERSION,
        ],
    ):
        raise SchemaMigrationError("database migration history is incomplete")
    _, initial_name, initial_checksum = rows[0]
    if initial_name != MIGRATION_NAME or initial_checksum != MIGRATION_CHECKSUM:
        raise MigrationChecksumError("database migration checksum does not match")
    if len(versions) >= 2:
        _, context_name, context_checksum = rows[1]
        if (
            context_name != CONTEXT_MIGRATION_NAME
            or context_checksum != CONTEXT_MIGRATION_CHECKSUM
        ):
            raise MigrationChecksumError("database migration checksum does not match")
    if len(versions) >= 3:
        _, schedule_name, schedule_checksum = rows[2]
        if (
            schedule_name != DRAW_SCHEDULE_MIGRATION_NAME
            or schedule_checksum != DRAW_SCHEDULE_MIGRATION_CHECKSUM
        ):
            raise MigrationChecksumError("database migration checksum does not match")
    if len(versions) == 4:
        _, authority_name, authority_checksum = rows[3]
        if (
            authority_name != SCHEDULE_AUTHORITY_MIGRATION_NAME
            or authority_checksum != SCHEDULE_AUTHORITY_MIGRATION_CHECKSUM
        ):
            raise MigrationChecksumError("database migration checksum does not match")

    version = versions[-1]
    _verify_schema_semantics(connection, table_names, version=version)
    return version


def _verify_schema_semantics(
    connection: sqlite3.Connection,
    table_names: set[str],
    *,
    version: int,
) -> None:
    expected_table_xinfo = {
        1: _EXPECTED_TABLE_XINFO,
        CONTEXT_SCHEMA_VERSION: _EXPECTED_TABLE_XINFO_V2,
        DRAW_SCHEDULE_SCHEMA_VERSION: _EXPECTED_TABLE_XINFO_V3,
        CURRENT_SCHEMA_VERSION: _EXPECTED_TABLE_XINFO_V4,
    }[version]
    expected_schema_objects = {
        1: _EXPECTED_SCHEMA_OBJECTS,
        CONTEXT_SCHEMA_VERSION: _EXPECTED_SCHEMA_OBJECTS_V2,
        DRAW_SCHEDULE_SCHEMA_VERSION: _EXPECTED_SCHEMA_OBJECTS_V3,
        CURRENT_SCHEMA_VERSION: _EXPECTED_SCHEMA_OBJECTS_V4,
    }[version]
    expected_schema_sql = {
        1: _EXPECTED_SCHEMA_SQL,
        CONTEXT_SCHEMA_VERSION: _EXPECTED_SCHEMA_SQL_V2,
        DRAW_SCHEDULE_SCHEMA_VERSION: _EXPECTED_SCHEMA_SQL_V3,
        CURRENT_SCHEMA_VERSION: _EXPECTED_SCHEMA_SQL_V4,
    }[version]
    expected_index_list = {
        1: _EXPECTED_INDEX_LIST,
        CONTEXT_SCHEMA_VERSION: _EXPECTED_INDEX_LIST_V2,
        DRAW_SCHEDULE_SCHEMA_VERSION: _EXPECTED_INDEX_LIST_V3,
        CURRENT_SCHEMA_VERSION: _EXPECTED_INDEX_LIST_V4,
    }[version]
    expected_foreign_keys = {
        1: _EXPECTED_FOREIGN_KEYS,
        CONTEXT_SCHEMA_VERSION: _EXPECTED_FOREIGN_KEYS_V2,
        DRAW_SCHEDULE_SCHEMA_VERSION: _EXPECTED_FOREIGN_KEYS_V3,
        CURRENT_SCHEMA_VERSION: _EXPECTED_FOREIGN_KEYS_V4,
    }[version]
    expected_index_xinfo = {
        1: _EXPECTED_INDEX_XINFO,
        CONTEXT_SCHEMA_VERSION: _EXPECTED_INDEX_XINFO_V2,
        DRAW_SCHEDULE_SCHEMA_VERSION: _EXPECTED_INDEX_XINFO_V3,
        CURRENT_SCHEMA_VERSION: _EXPECTED_INDEX_XINFO_V4,
    }[version]
    if table_names != set(expected_table_xinfo):
        raise SchemaMigrationError(f"database schema tables do not match version {version}")

    schema_rows = connection.execute(
        "SELECT type, name, tbl_name, sql FROM sqlite_schema ORDER BY type, name"
    ).fetchall()
    schema_objects = {(str(row[0]), str(row[1]), str(row[2])) for row in schema_rows}
    if schema_objects != expected_schema_objects:
        raise SchemaMigrationError(f"database schema objects do not match version {version}")
    for row in schema_rows:
        name = str(row[1])
        expected_sql = expected_schema_sql[name]
        actual_sql = row[3]
        if expected_sql is None:
            if actual_sql is not None:
                raise SchemaMigrationError(
                    f"database schema SQL does not match version {version}: {name}"
                )
        elif not isinstance(actual_sql, str) or _canonical_schema_sql(
            actual_sql
        ) != _canonical_schema_sql(expected_sql):
            raise SchemaMigrationError(
                f"database schema SQL does not match version {version}: {name}"
            )

    for table, expected_columns in expected_table_xinfo.items():
        columns = tuple(
            (
                int(row[0]),
                str(row[1]),
                str(row[2]),
                int(row[3]),
                None if row[4] is None else str(row[4]),
                int(row[5]),
                int(row[6]),
            )
            for row in connection.execute(f"PRAGMA table_xinfo({table})")
        )
        if columns != expected_columns:
            raise SchemaMigrationError(
                f"database table semantics do not match version {version}: {table}"
            )

        indexes = {
            str(row[1]): (int(row[2]), str(row[3]), int(row[4]))
            for row in connection.execute(f"PRAGMA index_list({table})")
        }
        if indexes != expected_index_list[table]:
            raise SchemaMigrationError(
                f"database index inventory does not match version {version}: {table}"
            )

        foreign_keys = tuple(
            (
                int(row[0]),
                int(row[1]),
                str(row[2]),
                str(row[3]),
                str(row[4]),
                str(row[5]),
                str(row[6]),
                str(row[7]),
            )
            for row in connection.execute(f"PRAGMA foreign_key_list({table})")
        )
        if foreign_keys != expected_foreign_keys[table]:
            raise SchemaMigrationError(
                f"database foreign-key semantics do not match version {version}: {table}"
            )

    for index, expected_index_columns in expected_index_xinfo.items():
        index_columns = tuple(
            (
                int(row[0]),
                int(row[1]),
                None if row[2] is None else str(row[2]),
                int(row[3]),
                None if row[4] is None else str(row[4]),
                int(row[5]),
            )
            for row in connection.execute(f"PRAGMA index_xinfo({index})")
        )
        if index_columns != expected_index_columns:
            raise SchemaMigrationError(
                f"database index semantics do not match version {version}: {index}"
            )


def _canonical_schema_sql(sql: str) -> tuple[str, ...]:
    return tuple(token.casefold() for token in _SCHEMA_SQL_TOKEN.findall(sql))


def _validate_path_definition(paths: LocalDataPaths) -> None:
    data_directory = paths.data_directory
    if "\x00" in str(data_directory):
        raise LocalDataError("local data path contains a null byte")
    if not data_directory.is_absolute():
        raise LocalDataError("local data path must be absolute")
    if ".." in data_directory.parts:
        raise LocalDataError("local data path traversal is not allowed")
    if data_directory == Path(data_directory.anchor):
        raise LocalDataError("local data path cannot be the filesystem root")
    if any(part.casefold() == "lotterynew" for part in data_directory.parts):
        raise LocalDataError("LotteryNew paths are forbidden")
    if paths.database != data_directory / DATABASE_FILENAME:
        raise LocalDataError("local database filename is fixed")
    _reject_git_worktree_path(data_directory)
    _reject_symlink_components(data_directory)


def _validate_existing_paths(paths: LocalDataPaths) -> None:
    _validate_path_definition(paths)
    try:
        directory_metadata = os.lstat(paths.data_directory)
    except FileNotFoundError:
        return
    if not stat.S_ISDIR(directory_metadata.st_mode):
        raise LocalDataError("local data path is not a directory")
    if directory_metadata.st_uid != os.getuid():
        raise LocalDataError("local data directory has a foreign owner")
    if stat.S_IMODE(directory_metadata.st_mode) != 0o700:
        raise LocalDataError("local data directory mode must be exactly 0700")

    try:
        database_metadata = os.lstat(paths.database)
    except FileNotFoundError:
        return
    if not stat.S_ISREG(database_metadata.st_mode):
        raise LocalDataError("local database must be a regular file")
    if database_metadata.st_uid != os.getuid():
        raise LocalDataError("local database has a foreign owner")
    if stat.S_IMODE(database_metadata.st_mode) != 0o600:
        raise LocalDataError("local database mode must be exactly 0600")
    if database_metadata.st_nlink != 1:
        raise LocalDataError("local database must have exactly one hard link")


def _ensure_data_directory(data_directory: Path) -> bool:
    existed = data_directory.exists()
    try:
        data_directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    except OSError as exc:
        raise LocalDataError("cannot create the local data directory safely") from exc
    _reject_symlink_components(data_directory)
    paths = LocalDataPaths(data_directory, data_directory / DATABASE_FILENAME)
    _validate_existing_paths(paths)
    return not existed


def _ensure_database_file(database: Path) -> bool:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(database, flags, 0o600)
    except FileExistsError:
        paths = LocalDataPaths(database.parent, database)
        _validate_existing_paths(paths)
        return False
    except OSError as exc:
        raise LocalDataError("cannot create the local database safely") from exc
    try:
        os.fchmod(descriptor, 0o600)
    finally:
        os.close(descriptor)
    paths = LocalDataPaths(database.parent, database)
    _validate_existing_paths(paths)
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
            raise LocalDataError("cannot inspect the local data path safely") from exc
        if stat.S_ISLNK(metadata.st_mode):
            raise LocalDataError("local data path cannot contain symlinks")


def _reject_git_worktree_path(path: Path) -> None:
    for ancestor in (path, *path.parents):
        try:
            os.lstat(ancestor / ".git")
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise LocalDataError("cannot inspect Git-worktree boundaries safely") from exc
        raise LocalDataError("local data path must be outside Git worktrees")


def _reject_wal_sidecars(database: Path) -> None:
    for suffix in ("-wal", "-shm"):
        try:
            os.lstat(Path(f"{database}{suffix}"))
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise LocalDataError("cannot inspect SQLite sidecar files safely") from exc
        raise LocalDataError("WAL and SHM files are forbidden")


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
