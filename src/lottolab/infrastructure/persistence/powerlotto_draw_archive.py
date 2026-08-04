"""Task-owned relational archive for POWER_LOTTO draw results."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

POWER_LOTTO = "POWER_LOTTO"
MIGRATION_ID = "P638_OLD_DB_DRAW_MIGRATION_R1"


class PowerLottoDrawArchiveError(RuntimeError):
    """The archive schema or a source draw violates the migration contract."""


class SourceDrawValidationError(PowerLottoDrawArchiveError):
    """A source draw cannot be represented by the archive contract."""


MIGRATION_STATEMENTS = (
    """
    CREATE TABLE migration_run (
        migration_id TEXT PRIMARY KEY,
        source_database TEXT NOT NULL,
        source_run_id TEXT NOT NULL,
        source_sha256 TEXT NOT NULL CHECK (length(source_sha256) = 64),
        status TEXT NOT NULL CHECK (status IN ('IN_PROGRESS', 'COMPLETED')),
        expected_draw_count INTEGER NOT NULL CHECK (expected_draw_count >= 0),
        inserted_draw_count INTEGER NOT NULL CHECK (inserted_draw_count >= 0),
        zone1_number_count INTEGER NOT NULL CHECK (zone1_number_count >= 0),
        zone2_number_count INTEGER NOT NULL CHECK (zone2_number_count >= 0),
        failed_draw_count INTEGER NOT NULL CHECK (failed_draw_count >= 0),
        started_at TEXT NOT NULL,
        completed_at TEXT
    )
    """,
    """
    CREATE TABLE lottery_draw (
        draw_id INTEGER PRIMARY KEY,
        migration_id TEXT NOT NULL,
        lottery_type TEXT NOT NULL CHECK (lottery_type = 'POWER_LOTTO'),
        draw_number TEXT NOT NULL,
        draw_date TEXT NOT NULL,
        source_reference TEXT NOT NULL,
        source_record_sha256 TEXT NOT NULL CHECK (length(source_record_sha256) = 64),
        status TEXT NOT NULL CHECK (status IN ('STAGING', 'COMPLETE')),
        created_at TEXT NOT NULL,
        completed_at TEXT,
        UNIQUE (lottery_type, draw_number),
        FOREIGN KEY (migration_id) REFERENCES migration_run(migration_id)
    )
    """,
    """
    CREATE TABLE lottery_draw_number (
        number_id INTEGER PRIMARY KEY,
        draw_id INTEGER NOT NULL,
        zone INTEGER NOT NULL CHECK (zone IN (1, 2)),
        position INTEGER NOT NULL,
        number INTEGER NOT NULL,
        CHECK (
            (zone = 1 AND position BETWEEN 1 AND 6 AND number BETWEEN 1 AND 38)
            OR (zone = 2 AND position = 1 AND number BETWEEN 1 AND 8)
        ),
        UNIQUE (draw_id, zone, position),
        UNIQUE (draw_id, zone, number),
        FOREIGN KEY (draw_id) REFERENCES lottery_draw(draw_id) ON DELETE CASCADE
    )
    """,
    """
    CREATE INDEX idx_lottery_draw_history
    ON lottery_draw (lottery_type, draw_date, draw_number)
    """,
    """
    CREATE INDEX idx_lottery_draw_migration
    ON lottery_draw (migration_id, status, draw_date, draw_number)
    """,
    """
    CREATE INDEX idx_lottery_draw_number_zone_position
    ON lottery_draw_number (draw_id, zone, position)
    """,
    """
    CREATE TRIGGER lottery_draw_completion_validation
    BEFORE UPDATE OF status ON lottery_draw
    FOR EACH ROW
    WHEN NEW.status = 'COMPLETE'
    BEGIN
        SELECT CASE WHEN OLD.status <> 'STAGING' THEN
            RAISE(ABORT, 'only STAGING draws may become COMPLETE')
        END;
        SELECT CASE WHEN (
            SELECT COUNT(*) FROM lottery_draw_number
            WHERE draw_id = NEW.draw_id AND zone = 1
        ) <> 6 THEN
            RAISE(ABORT, 'a COMPLETE draw requires exactly six zone-1 numbers')
        END;
        SELECT CASE WHEN (
            SELECT COUNT(*) FROM lottery_draw_number
            WHERE draw_id = NEW.draw_id AND zone = 2
        ) <> 1 THEN
            RAISE(ABORT, 'a COMPLETE draw requires exactly one zone-2 number')
        END;
        SELECT CASE WHEN EXISTS (
            SELECT 1
            FROM lottery_draw_number AS current_number
            JOIN lottery_draw_number AS next_number
              ON next_number.draw_id = current_number.draw_id
             AND next_number.zone = 1
             AND next_number.position = current_number.position + 1
            WHERE current_number.draw_id = NEW.draw_id
              AND current_number.zone = 1
              AND current_number.number >= next_number.number
        ) THEN
            RAISE(ABORT, 'zone-1 numbers must be strictly ascending')
        END;
    END
    """,
    """
    CREATE TRIGGER lottery_draw_insert_complete_validation
    BEFORE INSERT ON lottery_draw
    FOR EACH ROW
    WHEN NEW.status = 'COMPLETE'
    BEGIN
        SELECT RAISE(ABORT, 'draws must be inserted as STAGING');
    END
    """,
    """
    CREATE TRIGGER lottery_draw_number_complete_guard
    BEFORE INSERT ON lottery_draw_number
    FOR EACH ROW
    WHEN EXISTS (
        SELECT 1 FROM lottery_draw
        WHERE draw_id = NEW.draw_id AND status = 'COMPLETE'
    )
    BEGIN
        SELECT RAISE(ABORT, 'COMPLETE draw numbers are immutable');
    END
    """,
    """
    CREATE TRIGGER lottery_draw_number_update_complete_guard
    BEFORE UPDATE ON lottery_draw_number
    FOR EACH ROW
    WHEN EXISTS (
        SELECT 1 FROM lottery_draw
        WHERE draw_id = OLD.draw_id AND status = 'COMPLETE'
    )
    BEGIN
        SELECT RAISE(ABORT, 'COMPLETE draw numbers are immutable');
    END
    """,
    """
    CREATE TRIGGER lottery_draw_number_delete_complete_guard
    BEFORE DELETE ON lottery_draw_number
    FOR EACH ROW
    WHEN EXISTS (
        SELECT 1 FROM lottery_draw
        WHERE draw_id = OLD.draw_id AND status = 'COMPLETE'
    )
    BEGIN
        SELECT RAISE(ABORT, 'COMPLETE draw numbers are immutable');
    END
    """,
)

MIGRATION_SQL = ";\n".join(statement.strip() for statement in MIGRATION_STATEMENTS) + ";\n"


@dataclass(frozen=True, slots=True)
class SourceDraw:
    """A validated source row in the target archive's canonical form."""

    draw_number: str
    draw_date: str
    main_numbers: tuple[int, ...]
    second_number: int
    source_reference: str
    source_record_sha256: str


@dataclass(frozen=True, slots=True)
class MigrationResult:
    """Reconciliation facts returned after a committed migration."""

    migration_id: str
    source_run_id: str
    source_sha256_before: str
    source_sha256_after: str
    source_draw_count: int
    complete_draw_count: int
    zone1_number_count: int
    zone2_number_count: int
    failed_draw_count: int
    target_database: Path


def utc_timestamp() -> str:
    """Return a stable, timezone-explicit timestamp for audit rows."""

    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def canonical_source_record_sha256(
    *,
    draw_number: str,
    draw_date: str,
    main_numbers: Sequence[int],
    second_number: int,
    source_reference: str,
) -> str:
    """Hash one normalized source record, independent of source JSON spacing."""

    canonical_record = {
        "draw_date": draw_date,
        "draw_number": draw_number,
        "main_numbers": list(main_numbers),
        "second_number": second_number,
        "source_reference": source_reference,
    }
    serialized = json.dumps(
        canonical_record,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def validate_source_row(row: sqlite3.Row, row_number: int) -> SourceDraw:
    """Validate one source row against the POWER_LOTTO two-zone contract."""

    draw_number = _required_text(row["draw_number"], "draw_number", row_number)
    draw_date = _required_text(row["draw_date"], "draw_date", row_number)
    source_reference = _required_text(row["source_reference"], "source_reference", row_number)

    raw_main_numbers = row["main_numbers_json"]
    if type(raw_main_numbers) is not str:
        raise SourceDrawValidationError(
            f"source row {row_number} main_numbers_json must be text"
        )
    try:
        decoded_main_numbers: Any = json.loads(raw_main_numbers)
    except json.JSONDecodeError as exc:
        raise SourceDrawValidationError(
            f"source row {row_number} main_numbers_json is not valid JSON"
        ) from exc
    if not isinstance(decoded_main_numbers, list):
        raise SourceDrawValidationError(
            f"source row {row_number} must contain exactly six zone-1 numbers"
        )
    raw_main_numbers = cast(list[object], decoded_main_numbers)
    if len(raw_main_numbers) != 6:
        raise SourceDrawValidationError(
            f"source row {row_number} must contain exactly six zone-1 numbers"
        )
    if any(type(number) is not int for number in raw_main_numbers):
        raise SourceDrawValidationError(
            f"source row {row_number} zone-1 numbers must be built-in integers"
        )
    main_numbers = tuple(number for number in raw_main_numbers if type(number) is int)
    if any(number < 1 or number > 38 for number in main_numbers):
        raise SourceDrawValidationError(
            f"source row {row_number} zone-1 numbers must be in range 1..38"
        )
    if len(set(main_numbers)) != 6:
        raise SourceDrawValidationError(
            f"source row {row_number} zone-1 numbers must be unique"
        )
    if main_numbers != tuple(sorted(main_numbers)):
        raise SourceDrawValidationError(
            f"source row {row_number} zone-1 numbers must be ascending"
        )

    raw_second_number = row["second_number"]
    if type(raw_second_number) is not int:
        raise SourceDrawValidationError(
            f"source row {row_number} second_number must be a built-in integer"
        )
    second_number = raw_second_number
    if not 1 <= second_number <= 8:
        raise SourceDrawValidationError(
            f"source row {row_number} second_number must be in range 1..8"
        )

    return SourceDraw(
        draw_number=draw_number,
        draw_date=draw_date,
        main_numbers=main_numbers,
        second_number=second_number,
        source_reference=source_reference,
        source_record_sha256=canonical_source_record_sha256(
            draw_number=draw_number,
            draw_date=draw_date,
            main_numbers=main_numbers,
            second_number=second_number,
            source_reference=source_reference,
        ),
    )


def initialize_schema(connection: sqlite3.Connection) -> None:
    """Create the archive schema in the caller's current transaction."""

    for statement in MIGRATION_STATEMENTS:
        connection.execute(statement)


def _required_text(value: object, field: str, row_number: int) -> str:
    if type(value) is not str or not value:
        raise SourceDrawValidationError(f"source row {row_number} {field} must be non-empty text")
    return value
