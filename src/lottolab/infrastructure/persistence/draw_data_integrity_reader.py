"""Read-only SQLite reader for the draw-data integrity inspection core.

Every inspection runs inside one read-only transaction over a connection
opened through the existing ``draw_schema`` safety contract (``query_only``
enforced, no schema initialization, no migration). The transaction is always
rolled back and the connection always closed, on every path.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from lottolab.domain.draw_data_integrity import (
    REQUIRED_TABLE_NAMES,
    DrawDataIntegrityFinding,
    DrawDataIntegrityFindingCode,
    DrawDataIntegrityReport,
    DrawDataIntegrityStatus,
    DrawDataLotterySummary,
    DrawDataTableCount,
)
from lottolab.infrastructure.persistence.draw_schema import (
    LocalDataPaths,
    SchemaMigrationError,
    open_database,
    verify_schema_read_only,
)

_ABSENT_REPORT = DrawDataIntegrityReport(
    status=DrawDataIntegrityStatus.ABSENT,
    schema_version=None,
    table_counts=(),
    lottery_summaries=(),
    findings=(),
)


class SQLiteDrawDataIntegrityReader:
    """Inspects one explicitly supplied draw database, read-only, once per call."""

    def inspect(self, database: Path) -> DrawDataIntegrityReport:
        paths = LocalDataPaths(data_directory=database.parent, database=database)
        if not verify_schema_read_only(paths):
            return _ABSENT_REPORT

        with open_database(paths, read_only=True) as connection:
            connection.execute("BEGIN")
            try:
                schema_version = _read_schema_version(connection)
                findings = _run_integrity_checks(connection)
                table_counts = _read_table_counts(connection)
                lottery_summaries = _read_lottery_summaries(connection)
            finally:
                connection.rollback()

        status = (
            DrawDataIntegrityStatus.HEALTHY
            if all(finding.count == 0 for finding in findings)
            else DrawDataIntegrityStatus.UNHEALTHY
        )
        return DrawDataIntegrityReport(
            status=status,
            schema_version=schema_version,
            table_counts=table_counts,
            lottery_summaries=lottery_summaries,
            findings=findings,
        )


def _read_schema_version(connection: sqlite3.Connection) -> int:
    row = connection.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
    if row is None or len(row) != 1 or type(row[0]) is not int:
        raise SchemaMigrationError("canonical draw database schema version is invalid")
    return row[0]


def _run_integrity_checks(
    connection: sqlite3.Connection,
) -> tuple[DrawDataIntegrityFinding, ...]:
    return (
        DrawDataIntegrityFinding(
            code=DrawDataIntegrityFindingCode.SQLITE_QUICK_CHECK_FAILED,
            count=_quick_check_failure_count(connection),
        ),
        DrawDataIntegrityFinding(
            code=DrawDataIntegrityFindingCode.FOREIGN_KEY_VIOLATION,
            count=len(connection.execute("PRAGMA foreign_key_check").fetchall()),
        ),
        DrawDataIntegrityFinding(
            code=DrawDataIntegrityFindingCode.DUPLICATE_DRAW_IDENTITY,
            count=_scalar_count(
                connection,
                """
                SELECT COUNT(*) FROM (
                    SELECT 1 FROM draws
                    GROUP BY lottery_type, draw_number
                    HAVING COUNT(*) > 1
                )
                """,
            ),
        ),
        DrawDataIntegrityFinding(
            code=DrawDataIntegrityFindingCode.INVALID_DRAW_NUMBER,
            count=_scalar_count(
                connection,
                """
                SELECT COUNT(*) FROM draws
                WHERE TRIM(draw_number) = ''
                   OR draw_number GLOB '*[^0-9]*'
                """,
            ),
        ),
        DrawDataIntegrityFinding(
            code=DrawDataIntegrityFindingCode.INVALID_NORMALIZED_RECORD_HASH,
            count=_scalar_count(
                connection,
                """
                SELECT COUNT(*) FROM draws
                WHERE LENGTH(normalized_record_hash) != 64
                   OR normalized_record_hash GLOB '*[^0-9a-f]*'
                """,
            ),
        ),
        DrawDataIntegrityFinding(
            code=DrawDataIntegrityFindingCode.INVALID_NUMBERS_JSON,
            count=_scalar_count(
                connection,
                """
                SELECT COUNT(*) FROM draws
                WHERE json_valid(main_numbers_json) = 0
                   OR json_valid(special_numbers_json) = 0
                """,
            ),
        ),
    )


def _quick_check_failure_count(connection: sqlite3.Connection) -> int:
    rows = connection.execute("PRAGMA quick_check").fetchall()
    if len(rows) == 1 and str(rows[0][0]) == "ok":
        return 0
    return len(rows)


def _scalar_count(connection: sqlite3.Connection, sql: str) -> int:
    row = connection.execute(sql).fetchone()
    return int(row[0])


def _read_table_counts(connection: sqlite3.Connection) -> tuple[DrawDataTableCount, ...]:
    return tuple(
        DrawDataTableCount(
            table_name=table_name,
            row_count=_scalar_count(connection, f"SELECT COUNT(*) FROM {table_name}"),
        )
        for table_name in REQUIRED_TABLE_NAMES
    )


def _read_lottery_summaries(
    connection: sqlite3.Connection,
) -> tuple[DrawDataLotterySummary, ...]:
    rows = connection.execute(
        """
        SELECT
            lottery_type,
            draw_number,
            draw_date,
            ROW_NUMBER() OVER (
                PARTITION BY lottery_type
                ORDER BY draw_date ASC, CAST(draw_number AS INTEGER) ASC
            ) AS rank_first,
            ROW_NUMBER() OVER (
                PARTITION BY lottery_type
                ORDER BY draw_date DESC, CAST(draw_number AS INTEGER) DESC
            ) AS rank_last
        FROM draws
        """
    ).fetchall()

    draw_counts: dict[str, int] = {}
    first_by_type: dict[str, tuple[str, str]] = {}
    last_by_type: dict[str, tuple[str, str]] = {}
    for lottery_type, draw_number, draw_date, rank_first, rank_last in rows:
        lottery_type = str(lottery_type)
        draw_counts[lottery_type] = draw_counts.get(lottery_type, 0) + 1
        if rank_first == 1:
            first_by_type[lottery_type] = (str(draw_number), str(draw_date))
        if rank_last == 1:
            last_by_type[lottery_type] = (str(draw_number), str(draw_date))

    summaries: list[DrawDataLotterySummary] = []
    for lottery_type in sorted(draw_counts):
        first_draw_number, first_draw_date = first_by_type[lottery_type]
        last_draw_number, last_draw_date = last_by_type[lottery_type]
        summaries.append(
            DrawDataLotterySummary(
                lottery_type=lottery_type,
                draw_count=draw_counts[lottery_type],
                first_draw_number=first_draw_number,
                first_draw_date=first_draw_date,
                last_draw_number=last_draw_number,
                last_draw_date=last_draw_date,
            )
        )
    return tuple(summaries)
