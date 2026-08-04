"""Migrate authorized POWER_LOTTO draw rows into a task-owned SQLite archive."""

from __future__ import annotations

import argparse
import hashlib
import shutil
import sqlite3
import stat
import subprocess
from collections.abc import Iterator
from pathlib import Path
from urllib.parse import quote

from lottolab.infrastructure.persistence.powerlotto_draw_archive import (
    MIGRATION_ID,
    POWER_LOTTO,
    MigrationResult,
    SourceDraw,
    SourceDrawValidationError,
    initialize_schema,
    utc_timestamp,
    validate_source_row,
)

EXPECTED_SOURCE_DRAW_COUNT = 1_933
REQUIRED_SOURCE_TABLES = frozenset({"run_metadata", "draws", "completion"})


class MigrationStop(RuntimeError):
    """A required preflight or migration invariant failed."""

    def __init__(self, stop_token: str, detail: str) -> None:
        super().__init__(f"{stop_token}: {detail}")
        self.stop_token = stop_token
        self.detail = detail


def migrate_powerlotto_draws(
    *,
    source_db: Path,
    target_root: Path,
    expected_draw_count: int = EXPECTED_SOURCE_DRAW_COUNT,
) -> MigrationResult:
    """Perform one atomic migration into an absent target identity."""

    source_db = source_db.resolve()
    target_root = target_root.resolve()
    _verify_source_file(source_db)
    _verify_no_active_source_writer(source_db)
    if target_root.exists():
        raise MigrationStop(
            "STOP_P638_DRAW_TARGET_IDENTITY_COLLISION",
            f"target root already exists: {target_root}",
        )

    source_sha256_before = _sha256_file(source_db)
    source_connection = _open_source(source_db)
    try:
        source_run_id, source_count = _resolve_source_run(
            source_connection, expected_draw_count
        )
        source_rows = source_connection.execute(
            """
            SELECT draw_number, draw_date, main_numbers_json, second_number, source_reference
            FROM draws
            WHERE run_id = ?
            ORDER BY draw_date ASC, draw_number ASC
            """,
            (source_run_id,),
        )

        target_root.mkdir(parents=False, exist_ok=False)
        target_database = target_root / "powerlotto_draws.sqlite3"
        if target_database.exists():
            raise MigrationStop(
                "STOP_P638_DRAW_TARGET_IDENTITY_COLLISION",
                f"target database already exists: {target_database}",
            )
        result = _migrate_rows(
            source_connection=source_connection,
            source_rows=source_rows,
            source_db=source_db,
            source_run_id=source_run_id,
            source_sha256_before=source_sha256_before,
            target_database=target_database,
            expected_draw_count=source_count,
        )
        source_sha256_after = _sha256_file(source_db)
        if source_sha256_after != source_sha256_before:
            raise MigrationStop(
                "STOP_P638_DRAW_SOURCE_CONCURRENT_WRITE",
                "source SHA-256 changed during migration",
            )
        return MigrationResult(
            migration_id=result.migration_id,
            source_run_id=result.source_run_id,
            source_sha256_before=source_sha256_before,
            source_sha256_after=source_sha256_after,
            source_draw_count=result.source_draw_count,
            complete_draw_count=result.complete_draw_count,
            zone1_number_count=result.zone1_number_count,
            zone2_number_count=result.zone2_number_count,
            failed_draw_count=result.failed_draw_count,
            target_database=target_database,
        )
    finally:
        source_connection.close()


def _migrate_rows(
    *,
    source_connection: sqlite3.Connection,
    source_rows: Iterator[sqlite3.Row],
    source_db: Path,
    source_run_id: str,
    source_sha256_before: str,
    target_database: Path,
    expected_draw_count: int,
) -> MigrationResult:
    del source_connection
    connection = sqlite3.connect(target_database)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("BEGIN")
    try:
        initialize_schema(connection)
        started_at = utc_timestamp()
        connection.execute(
            """
            INSERT INTO migration_run (
                migration_id, source_database, source_run_id, source_sha256, status,
                expected_draw_count, inserted_draw_count, zone1_number_count,
                zone2_number_count, failed_draw_count, started_at, completed_at
            ) VALUES (?, ?, ?, ?, 'IN_PROGRESS', ?, 0, 0, 0, 0, ?, NULL)
            """,
            (
                MIGRATION_ID,
                str(source_db),
                source_run_id,
                source_sha256_before,
                expected_draw_count,
                started_at,
            ),
        )

        inserted_draw_count = 0
        zone1_number_count = 0
        zone2_number_count = 0
        for row_number, row in enumerate(source_rows, start=1):
            try:
                draw = validate_source_row(row, row_number)
            except SourceDrawValidationError as exc:
                raise MigrationStop("STOP_P638_DRAW_SOURCE_SCHEMA_UNEXPECTED", str(exc)) from exc
            _insert_draw(connection, draw)
            inserted_draw_count += 1
            zone1_number_count += 6
            zone2_number_count += 1

        if inserted_draw_count != expected_draw_count:
            raise MigrationStop(
                "STOP_P638_DRAW_SOURCE_COUNT_UNEXPECTED",
                f"validated {inserted_draw_count} rows, expected {expected_draw_count}",
            )

        completed_at = utc_timestamp()
        connection.execute(
            """
            UPDATE migration_run
            SET status = 'COMPLETED', inserted_draw_count = ?, zone1_number_count = ?,
                zone2_number_count = ?, completed_at = ?
            WHERE migration_id = ? AND status = 'IN_PROGRESS'
            """,
            (
                inserted_draw_count,
                zone1_number_count,
                zone2_number_count,
                completed_at,
                MIGRATION_ID,
            ),
        )
        _verify_target_counts(
            connection,
            expected_draw_count=expected_draw_count,
            expected_zone1_count=zone1_number_count,
            expected_zone2_count=zone2_number_count,
        )
        source_sha256_before_commit = _sha256_file(source_db)
        source_sha256_at_start = connection.execute(
            "SELECT source_sha256 FROM migration_run WHERE migration_id = ?",
            (MIGRATION_ID,),
        ).fetchone()
        if source_sha256_at_start is None or (
            source_sha256_before_commit != source_sha256_at_start[0]
        ):
            raise MigrationStop(
                "STOP_P638_DRAW_SOURCE_CONCURRENT_WRITE",
                "source SHA-256 changed before target commit",
            )
        connection.commit()
        return MigrationResult(
            migration_id=MIGRATION_ID,
            source_run_id=source_run_id,
            source_sha256_before=source_sha256_before_commit,
            source_sha256_after=source_sha256_before_commit,
            source_draw_count=expected_draw_count,
            complete_draw_count=expected_draw_count,
            zone1_number_count=zone1_number_count,
            zone2_number_count=zone2_number_count,
            failed_draw_count=0,
            target_database=target_database,
        )
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _insert_draw(connection: sqlite3.Connection, draw: SourceDraw) -> None:
    connection.execute(
        """
        INSERT INTO lottery_draw (
            migration_id, lottery_type, draw_number, draw_date, source_reference,
            source_record_sha256, status, created_at, completed_at
        ) VALUES (?, ?, ?, ?, ?, ?, 'STAGING', ?, NULL)
        """,
        (
            MIGRATION_ID,
            POWER_LOTTO,
            draw.draw_number,
            draw.draw_date,
            draw.source_reference,
            draw.source_record_sha256,
            utc_timestamp(),
        ),
    )
    draw_id = connection.execute("SELECT last_insert_rowid()").fetchone()[0]
    connection.executemany(
        """
        INSERT INTO lottery_draw_number (draw_id, zone, position, number)
        VALUES (?, 1, ?, ?)
        """,
        ((draw_id, position, number) for position, number in enumerate(draw.main_numbers, start=1)),
    )
    connection.execute(
        """
        INSERT INTO lottery_draw_number (draw_id, zone, position, number)
        VALUES (?, 2, 1, ?)
        """,
        (draw_id, draw.second_number),
    )
    connection.execute(
        """
        UPDATE lottery_draw
        SET status = 'COMPLETE', completed_at = ?
        WHERE draw_id = ? AND status = 'STAGING'
        """,
        (utc_timestamp(), draw_id),
    )


def _resolve_source_run(
    connection: sqlite3.Connection, expected_draw_count: int
) -> tuple[str, int]:
    actual_tables = {
        str(row[0])
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    }
    if not REQUIRED_SOURCE_TABLES.issubset(actual_tables):
        missing = sorted(REQUIRED_SOURCE_TABLES - actual_tables)
        raise MigrationStop(
            "STOP_P638_DRAW_SOURCE_SCHEMA_UNEXPECTED",
            f"missing source tables: {', '.join(missing)}",
        )
    candidates = connection.execute(
        """
        SELECT rm.run_id, rm.source_count, COUNT(d.draw_number) AS draw_count,
               COUNT(DISTINCT d.draw_number) AS distinct_draw_count
        FROM run_metadata AS rm
        JOIN completion AS c ON c.run_id = rm.run_id
        JOIN draws AS d ON d.run_id = rm.run_id
        WHERE rm.lottery_type = ?
          AND rm.status IN ('COMPLETE', 'COMPLETED')
          AND c.status IN ('COMPLETE', 'COMPLETED')
        GROUP BY rm.run_id, rm.source_count
        ORDER BY rm.run_id
        """,
        (POWER_LOTTO,),
    ).fetchall()
    if len(candidates) != 1:
        raise MigrationStop(
            "STOP_P638_DRAW_SOURCE_RUN_AMBIGUOUS",
            f"expected exactly one completed POWER_LOTTO run, found {len(candidates)}",
        )
    candidate = candidates[0]
    source_count = int(candidate[1])
    draw_count = int(candidate[2])
    distinct_draw_count = int(candidate[3])
    if (
        source_count != expected_draw_count
        or draw_count != expected_draw_count
        or distinct_draw_count != expected_draw_count
    ):
        raise MigrationStop(
            "STOP_P638_DRAW_SOURCE_COUNT_UNEXPECTED",
            "source_count, draw count, and distinct draw count must all equal "
            f"{expected_draw_count}; got {source_count}, {draw_count}, {distinct_draw_count}",
        )
    return str(candidate[0]), source_count


def _open_source(source_db: Path) -> sqlite3.Connection:
    uri = f"file:{quote(str(source_db), safe='/')}?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only = ON")
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def _verify_source_file(source_db: Path) -> None:
    if not source_db.exists() or not source_db.is_file():
        raise MigrationStop("STOP_P638_DRAW_SOURCE_DB_MISSING", str(source_db))
    if not stat.S_ISREG(source_db.stat().st_mode):
        raise MigrationStop("STOP_P638_DRAW_SOURCE_DB_MISSING", f"not a regular file: {source_db}")
    try:
        with _open_source(source_db) as connection:
            connection.execute("SELECT 1").fetchone()
    except sqlite3.DatabaseError as exc:
        raise MigrationStop(
            "STOP_P638_DRAW_SOURCE_SCHEMA_UNEXPECTED",
            f"source is not readable SQLite: {exc}",
        ) from exc


def _verify_no_active_source_writer(source_db: Path) -> None:
    lsof = shutil.which("lsof")
    if lsof is None:
        raise MigrationStop(
            "STOP_P638_DRAW_SOURCE_CONCURRENT_WRITE",
            "lsof is required to verify source writer absence",
        )
    result = subprocess.run(
        [lsof, "-F", "fn", "--", str(source_db)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode not in (0, 1):
        raise MigrationStop(
            "STOP_P638_DRAW_SOURCE_CONCURRENT_WRITE",
            f"lsof failed with exit code {result.returncode}",
        )
    pids: list[str] = []
    current_pid = ""
    for line in result.stdout.splitlines():
        if line.startswith("p"):
            current_pid = line[1:]
        elif line.startswith("f") and any(mode in line[1:] for mode in ("w", "u")):
            pids.append(current_pid or "unknown")
    if pids:
        raise MigrationStop(
            "STOP_P638_DRAW_SOURCE_CONCURRENT_WRITE",
            f"source has active openers: {', '.join(pids)}",
        )


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verify_target_counts(
    connection: sqlite3.Connection,
    *,
    expected_draw_count: int,
    expected_zone1_count: int,
    expected_zone2_count: int,
) -> None:
    complete_draw_count = int(
        connection.execute(
            "SELECT COUNT(*) FROM lottery_draw WHERE lottery_type = ? AND status = 'COMPLETE'",
            (POWER_LOTTO,),
        ).fetchone()[0]
    )
    zone1_count = int(
        connection.execute(
            "SELECT COUNT(*) FROM lottery_draw_number WHERE zone = 1"
        ).fetchone()[0]
    )
    zone2_count = int(
        connection.execute(
            "SELECT COUNT(*) FROM lottery_draw_number WHERE zone = 2"
        ).fetchone()[0]
    )
    if (complete_draw_count, zone1_count, zone2_count) != (
        expected_draw_count,
        expected_zone1_count,
        expected_zone2_count,
    ):
        raise MigrationStop(
            "STOP_P638_DRAW_SOURCE_COUNT_UNEXPECTED",
            "target reconciliation failed: "
            f"{complete_draw_count}, {zone1_count}, {zone2_count}",
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-db", type=Path, required=True)
    parser.add_argument("--target-root", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = migrate_powerlotto_draws(source_db=args.source_db, target_root=args.target_root)
    except MigrationStop as exc:
        print(str(exc))
        return 2
    print(
        "migration complete: "
        f"draws={result.complete_draw_count} zone1={result.zone1_number_count} "
        f"zone2={result.zone2_number_count} source_sha256={result.source_sha256_after}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
