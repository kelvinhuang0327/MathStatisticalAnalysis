"""Operation-scoped SQLite repositories for draw data and ingestion history."""

from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Never, cast

from lottolab.application.draw_data import (
    MAX_INGESTION_ITEM_DETAILS,
    DrawHistoryPage,
    DrawHistoryQuery,
    DrawRecord,
    ExistingDrawConflictError,
    ImportCommitResult,
    IngestionItemRecord,
    IngestionRunDetail,
    IngestionRunPage,
    IngestionRunQuery,
    IngestionRunRecord,
    InvalidDrawImportError,
    RepositoryBusyError,
    RepositoryUnavailableError,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.ingestion import (
    DrawCsvParseResult,
    IngestionItemDisposition,
    IngestionOperationType,
    IngestionRunStatus,
    NormalizedDrawInput,
)
from lottolab.infrastructure.persistence.draw_schema import (
    LocalDataError,
    LocalDataPaths,
    SchemaMigrationError,
    initialize_schema,
    open_database,
    verify_schema_read_only,
)

_DRAW_COLUMNS = """
    id, lottery_type, draw_number, draw_date, main_numbers_json,
    special_numbers_json, normalized_record_hash, source_name,
    source_reference, ingestion_run_id, created_at, updated_at
"""
_RUN_COLUMNS = """
    id, operation_type, status, lottery_type, source_filename,
    source_sha256, parser_version, total_count, inserted_count,
    skipped_count, conflict_count, failed_count, first_draw_number,
    last_draw_number, started_at, completed_at, error_summary
"""


class _StoredDataError(RuntimeError):
    """A database value cannot be represented by the application read model."""


@dataclass(frozen=True, slots=True)
class _ImportDecision:
    row: NormalizedDrawInput
    disposition: IngestionItemDisposition


class SQLiteDrawRepository:
    """Draw-table operations bound to one caller-owned connection."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def find(self, lottery_type: LotteryType, draw_number: str) -> DrawRecord | None:
        row = self._connection.execute(
            f"SELECT {_DRAW_COLUMNS} FROM draws "
            "WHERE lottery_type = ? AND draw_number = ?",
            (lottery_type.value, draw_number),
        ).fetchone()
        return None if row is None else _draw_record(row)

    def insert(
        self,
        row: NormalizedDrawInput,
        *,
        run_id: str,
        source_filename: str,
        timestamp: datetime,
    ) -> None:
        encoded_main = json.dumps(row.main_numbers, separators=(",", ":"))
        encoded_special = json.dumps(row.special_numbers, separators=(",", ":"))
        timestamp_text = _format_utc(timestamp)
        self._connection.execute(
            """
            INSERT INTO draws (
                lottery_type, draw_number, draw_date, main_numbers_json,
                special_numbers_json, normalized_record_hash, source_name,
                source_reference, ingestion_run_id, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row.lottery_type.value,
                row.draw_number,
                row.draw_date.isoformat(),
                encoded_main,
                encoded_special,
                row.normalized_record_hash,
                source_filename,
                row.source,
                run_id,
                timestamp_text,
                timestamp_text,
            ),
        )

    def count(self, query: DrawHistoryQuery) -> int:
        where_sql, parameters = _draw_filters(query)
        row = self._connection.execute(
            f"SELECT COUNT(*) FROM draws{where_sql}", parameters
        ).fetchone()
        if row is None:
            raise _StoredDataError("draw count query returned no row")
        return _nonnegative_integer(row[0], "draw count")

    def query(self, query: DrawHistoryQuery) -> tuple[DrawRecord, ...]:
        where_sql, parameters = _draw_filters(query)
        offset = (query.page - 1) * query.page_size
        rows = self._connection.execute(
            f"""
            SELECT {_DRAW_COLUMNS}
            FROM draws{where_sql}
            ORDER BY draw_date DESC, draw_number DESC, id DESC
            LIMIT ? OFFSET ?
            """,
            (*parameters, query.page_size, offset),
        ).fetchall()
        return tuple(_draw_record(row) for row in rows)


class SQLiteIngestionRunRepository:
    """Ingestion-run operations bound to one caller-owned connection."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def create(
        self,
        *,
        run_id: str,
        lottery_type: LotteryType | None,
        result: DrawCsvParseResult,
        total_count: int,
        first_draw_number: str | None,
        last_draw_number: str | None,
        started_at: datetime,
    ) -> None:
        self._connection.execute(
            """
            INSERT INTO ingestion_runs (
                id, operation_type, status, lottery_type, source_filename,
                source_sha256, parser_version, total_count, inserted_count,
                skipped_count, conflict_count, failed_count, first_draw_number,
                last_draw_number, started_at, completed_at, error_summary
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 0, 0, ?, ?, ?, NULL, NULL)
            """,
            (
                run_id,
                IngestionOperationType.DRAW_CSV_IMPORT.value,
                IngestionRunStatus.RUNNING.value,
                lottery_type.value if lottery_type is not None else None,
                result.source_filename,
                result.content_sha256,
                result.parser_version,
                total_count,
                first_draw_number,
                last_draw_number,
                _format_utc(started_at),
            ),
        )

    def complete(
        self,
        *,
        run_id: str,
        status: IngestionRunStatus,
        inserted_count: int,
        skipped_count: int,
        conflict_count: int,
        failed_count: int,
        completed_at: datetime,
        error_summary: str | None,
    ) -> None:
        if status not in (IngestionRunStatus.SUCCESS, IngestionRunStatus.FAILED):
            raise ValueError("an ingestion run can complete only as SUCCESS or FAILED")
        cursor = self._connection.execute(
            """
            UPDATE ingestion_runs
            SET status = ?, inserted_count = ?, skipped_count = ?,
                conflict_count = ?, failed_count = ?, completed_at = ?,
                error_summary = ?
            WHERE id = ? AND status = ? AND completed_at IS NULL
            """,
            (
                status.value,
                inserted_count,
                skipped_count,
                conflict_count,
                failed_count,
                _format_utc(completed_at),
                error_summary,
                run_id,
                IngestionRunStatus.RUNNING.value,
            ),
        )
        if cursor.rowcount != 1:
            raise _StoredDataError("ingestion run completion did not update exactly one row")

    def count(self, query: IngestionRunQuery) -> int:
        where_sql, parameters = _run_filters(query)
        row = self._connection.execute(
            f"SELECT COUNT(*) FROM ingestion_runs{where_sql}", parameters
        ).fetchone()
        if row is None:
            raise _StoredDataError("ingestion run count query returned no row")
        return _nonnegative_integer(row[0], "ingestion run count")

    def query(self, query: IngestionRunQuery) -> tuple[IngestionRunRecord, ...]:
        where_sql, parameters = _run_filters(query)
        offset = (query.page - 1) * query.page_size
        rows = self._connection.execute(
            f"""
            SELECT {_RUN_COLUMNS}
            FROM ingestion_runs{where_sql}
            ORDER BY started_at DESC, id DESC
            LIMIT ? OFFSET ?
            """,
            (*parameters, query.page_size, offset),
        ).fetchall()
        return tuple(_ingestion_run_record(row) for row in rows)

    def get(self, run_id: str) -> IngestionRunRecord | None:
        row = self._connection.execute(
            f"SELECT {_RUN_COLUMNS} FROM ingestion_runs WHERE id = ?",
            (run_id,),
        ).fetchone()
        return None if row is None else _ingestion_run_record(row)


class SQLiteIngestionItemRepository:
    """Ingestion-item operations bound to one caller-owned connection."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def add(
        self,
        *,
        run_id: str,
        row: NormalizedDrawInput,
        disposition: IngestionItemDisposition,
        message: str,
    ) -> None:
        self._connection.execute(
            """
            INSERT INTO ingestion_items (
                ingestion_run_id, source_row_number, lottery_type, draw_number,
                disposition, normalized_record_hash, message
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                row.source_row_number,
                row.lottery_type.value,
                row.draw_number,
                disposition.value,
                row.normalized_record_hash,
                message,
            ),
        )

    def count_for_run(self, run_id: str) -> int:
        row = self._connection.execute(
            "SELECT COUNT(*) FROM ingestion_items WHERE ingestion_run_id = ?",
            (run_id,),
        ).fetchone()
        if row is None:
            raise _StoredDataError("ingestion item count query returned no row")
        return _nonnegative_integer(row[0], "ingestion item count")

    def list_for_run(
        self, run_id: str, *, limit: int = MAX_INGESTION_ITEM_DETAILS
    ) -> tuple[IngestionItemRecord, ...]:
        rows = self._connection.execute(
            """
            SELECT source_row_number, lottery_type, draw_number, disposition,
                   normalized_record_hash, message
            FROM ingestion_items
            WHERE ingestion_run_id = ?
            ORDER BY source_row_number, id
            LIMIT ?
            """,
            (run_id, limit),
        ).fetchall()
        return tuple(_ingestion_item_record(row) for row in rows)


class SQLiteDrawDataRepository:
    """Fresh-connection implementation of the application draw-data ports."""

    def __init__(self, paths: LocalDataPaths) -> None:
        self._paths = paths

    def list_draws(self, query: DrawHistoryQuery) -> DrawHistoryPage:
        try:
            if not verify_schema_read_only(self._paths):
                return DrawHistoryPage((), query.page, query.page_size, 0, 0)
            with open_database(self._paths, read_only=True) as connection:
                connection.execute("BEGIN")
                try:
                    repository = SQLiteDrawRepository(connection)
                    total_count = repository.count(query)
                    records = repository.query(query)
                finally:
                    if connection.in_transaction:
                        connection.rollback()
            return DrawHistoryPage(
                records=records,
                page=query.page,
                page_size=query.page_size,
                total_count=total_count,
                total_pages=_total_pages(total_count, query.page_size),
            )
        except (
            LocalDataError,
            SchemaMigrationError,
            sqlite3.DatabaseError,
            _StoredDataError,
        ) as exc:
            _raise_repository_error(exc)

    def get_draw(self, lottery_type: LotteryType, draw_number: str) -> DrawRecord | None:
        try:
            if not verify_schema_read_only(self._paths):
                return None
            with open_database(self._paths, read_only=True) as connection:
                return SQLiteDrawRepository(connection).find(lottery_type, draw_number)
        except (
            LocalDataError,
            SchemaMigrationError,
            sqlite3.DatabaseError,
            _StoredDataError,
        ) as exc:
            _raise_repository_error(exc)

    def list_ingestion_runs(self, query: IngestionRunQuery) -> IngestionRunPage:
        try:
            if not verify_schema_read_only(self._paths):
                return IngestionRunPage((), query.page, query.page_size, 0, 0)
            with open_database(self._paths, read_only=True) as connection:
                connection.execute("BEGIN")
                try:
                    repository = SQLiteIngestionRunRepository(connection)
                    total_count = repository.count(query)
                    raw_records = repository.query(query)
                finally:
                    if connection.in_transaction:
                        connection.rollback()
            return IngestionRunPage(
                records=raw_records,
                page=query.page,
                page_size=query.page_size,
                total_count=total_count,
                total_pages=_total_pages(total_count, query.page_size),
            )
        except (
            LocalDataError,
            SchemaMigrationError,
            sqlite3.DatabaseError,
            _StoredDataError,
        ) as exc:
            _raise_repository_error(exc)

    def get_ingestion_run(self, run_id: str) -> IngestionRunDetail | None:
        try:
            if not verify_schema_read_only(self._paths):
                return None
            with open_database(self._paths, read_only=True) as connection:
                connection.execute("BEGIN")
                try:
                    run_repository = SQLiteIngestionRunRepository(connection)
                    raw_run = run_repository.get(run_id)
                    if raw_run is None:
                        return None
                    item_repository = SQLiteIngestionItemRepository(connection)
                    item_count = item_repository.count_for_run(run_id)
                    items = item_repository.list_for_run(run_id)
                finally:
                    if connection.in_transaction:
                        connection.rollback()
            return IngestionRunDetail(
                run=raw_run,
                items=items,
                item_count=item_count,
                items_truncated=item_count > len(items),
            )
        except (
            LocalDataError,
            SchemaMigrationError,
            sqlite3.DatabaseError,
            _StoredDataError,
        ) as exc:
            _raise_repository_error(exc)

    def apply_valid_import(self, result: DrawCsvParseResult) -> ImportCommitResult:
        if not result.is_valid:
            raise InvalidDrawImportError(result)

        try:
            schema_existed = verify_schema_read_only(self._paths)
            if not schema_existed:
                initialize_schema(self._paths)
            with open_database(self._paths) as connection:
                return self._apply_transaction(
                    connection,
                    result=result,
                    record_failed_run=schema_existed,
                )
        except (InvalidDrawImportError, ExistingDrawConflictError):
            raise
        except (
            LocalDataError,
            SchemaMigrationError,
            sqlite3.DatabaseError,
            _StoredDataError,
        ) as exc:
            _raise_repository_error(exc)

    def _apply_transaction(
        self,
        connection: sqlite3.Connection,
        *,
        result: DrawCsvParseResult,
        record_failed_run: bool,
    ) -> ImportCommitResult:
        rows = result.normalized_rows
        lottery_type = _single_lottery_type(rows)
        first_draw_number = rows[0].draw_number if rows else None
        last_draw_number = rows[-1].draw_number if rows else None
        run_id = str(uuid.uuid4())
        started_at = _utc_now()
        draw_repository = SQLiteDrawRepository(connection)
        run_repository = SQLiteIngestionRunRepository(connection)
        item_repository = SQLiteIngestionItemRepository(connection)

        connection.execute("BEGIN IMMEDIATE")
        try:
            run_repository.create(
                run_id=run_id,
                lottery_type=lottery_type,
                result=result,
                total_count=len(rows),
                first_draw_number=first_draw_number,
                last_draw_number=last_draw_number,
                started_at=started_at,
            )
            decisions = tuple(
                _classify(draw_repository.find(row.lottery_type, row.draw_number), row)
                for row in rows
            )
            if any(
                decision.disposition is IngestionItemDisposition.CONFLICT
                for decision in decisions
            ):
                connection.rollback()
                conflict_result = self._record_failed_conflict(
                    connection,
                    result=result,
                    run_id=run_id,
                    lottery_type=lottery_type,
                    first_draw_number=first_draw_number,
                    last_draw_number=last_draw_number,
                    record_failed_run=record_failed_run,
                )
                raise ExistingDrawConflictError(conflict_result)

            inserted_count = 0
            skipped_count = 0
            for decision in decisions:
                if decision.disposition is IngestionItemDisposition.INSERTED:
                    draw_repository.insert(
                        decision.row,
                        run_id=run_id,
                        source_filename=result.source_filename,
                        timestamp=started_at,
                    )
                    inserted_count += 1
                    message = "Inserted new draw."
                else:
                    skipped_count += 1
                    message = "Existing draw is semantically identical."
                item_repository.add(
                    run_id=run_id,
                    row=decision.row,
                    disposition=decision.disposition,
                    message=message,
                )

            completed_at = _utc_now()
            run_repository.complete(
                run_id=run_id,
                status=IngestionRunStatus.SUCCESS,
                inserted_count=inserted_count,
                skipped_count=skipped_count,
                conflict_count=0,
                failed_count=0,
                completed_at=completed_at,
                error_summary=None,
            )
            connection.commit()
        except BaseException:
            if connection.in_transaction:
                connection.rollback()
            raise

        committed = ImportCommitResult(
            run_id=run_id,
            status=IngestionRunStatus.SUCCESS,
            lottery_type=lottery_type,
            total_count=len(rows),
            inserted_count=inserted_count,
            skipped_count=skipped_count,
            conflict_count=0,
            failed_count=0,
            first_draw_number=first_draw_number,
            last_draw_number=last_draw_number,
            completed_at=completed_at,
        )
        if not committed.counts_are_consistent:
            raise _StoredDataError("successful ingestion counts are inconsistent")
        return committed

    def _record_failed_conflict(
        self,
        connection: sqlite3.Connection,
        *,
        result: DrawCsvParseResult,
        run_id: str,
        lottery_type: LotteryType | None,
        first_draw_number: str | None,
        last_draw_number: str | None,
        record_failed_run: bool,
    ) -> ImportCommitResult:
        rows = result.normalized_rows
        draw_repository = SQLiteDrawRepository(connection)
        connection.execute("BEGIN IMMEDIATE")
        try:
            decisions = tuple(
                _classify(draw_repository.find(row.lottery_type, row.draw_number), row)
                for row in rows
            )
            skipped_count = sum(
                decision.disposition is IngestionItemDisposition.SKIPPED_DUPLICATE
                for decision in decisions
            )
            conflict_count = sum(
                decision.disposition is IngestionItemDisposition.CONFLICT
                for decision in decisions
            )
            failed_count = len(rows) - skipped_count - conflict_count
            completed_at = _utc_now()

            if record_failed_run:
                run_repository = SQLiteIngestionRunRepository(connection)
                item_repository = SQLiteIngestionItemRepository(connection)
                run_repository.create(
                    run_id=run_id,
                    lottery_type=lottery_type,
                    result=result,
                    total_count=len(rows),
                    first_draw_number=first_draw_number,
                    last_draw_number=last_draw_number,
                    started_at=completed_at,
                )
                for decision in decisions:
                    disposition = decision.disposition
                    if disposition is IngestionItemDisposition.INSERTED:
                        disposition = IngestionItemDisposition.FAILED
                        message = "Not inserted because the batch contains a conflict."
                    elif disposition is IngestionItemDisposition.SKIPPED_DUPLICATE:
                        message = "Existing draw is semantically identical."
                    else:
                        message = "Existing draw differs; batch rejected."
                    item_repository.add(
                        run_id=run_id,
                        row=decision.row,
                        disposition=disposition,
                        message=message,
                    )
                run_repository.complete(
                    run_id=run_id,
                    status=IngestionRunStatus.FAILED,
                    inserted_count=0,
                    skipped_count=skipped_count,
                    conflict_count=conflict_count,
                    failed_count=failed_count,
                    completed_at=completed_at,
                    error_summary="Batch rejected because existing draw data conflicts.",
                )
                connection.commit()
            else:
                connection.rollback()
        except BaseException:
            if connection.in_transaction:
                connection.rollback()
            raise

        failed = ImportCommitResult(
            run_id=run_id if record_failed_run else None,
            status=IngestionRunStatus.FAILED,
            lottery_type=lottery_type,
            total_count=len(rows),
            inserted_count=0,
            skipped_count=skipped_count,
            conflict_count=conflict_count,
            failed_count=failed_count,
            first_draw_number=first_draw_number,
            last_draw_number=last_draw_number,
            completed_at=completed_at,
        )
        if not failed.counts_are_consistent or failed.conflict_count < 1:
            raise _StoredDataError("failed ingestion counts are inconsistent")
        return failed


def _draw_filters(query: DrawHistoryQuery) -> tuple[str, tuple[object, ...]]:
    clauses: list[str] = []
    parameters: list[object] = []
    if query.lottery_type is not None:
        clauses.append("lottery_type = ?")
        parameters.append(query.lottery_type.value)
    if query.draw_number is not None:
        clauses.append("instr(draw_number, ?) > 0")
        parameters.append(query.draw_number)
    if query.date_from is not None:
        clauses.append("draw_date >= ?")
        parameters.append(query.date_from.isoformat())
    if query.date_to is not None:
        clauses.append("draw_date <= ?")
        parameters.append(query.date_to.isoformat())
    where_sql = " WHERE " + " AND ".join(clauses) if clauses else ""
    return where_sql, tuple(parameters)


def _run_filters(query: IngestionRunQuery) -> tuple[str, tuple[object, ...]]:
    clauses: list[str] = []
    parameters: list[object] = []
    if query.status is not None:
        clauses.append("status = ?")
        parameters.append(query.status.value)
    if query.lottery_type is not None:
        clauses.append("lottery_type = ?")
        parameters.append(query.lottery_type.value)
    where_sql = " WHERE " + " AND ".join(clauses) if clauses else ""
    return where_sql, tuple(parameters)


def _classify(existing: DrawRecord | None, row: NormalizedDrawInput) -> _ImportDecision:
    if existing is None:
        disposition = IngestionItemDisposition.INSERTED
    elif _semantically_equal(existing, row):
        disposition = IngestionItemDisposition.SKIPPED_DUPLICATE
    else:
        disposition = IngestionItemDisposition.CONFLICT
    return _ImportDecision(row=row, disposition=disposition)


def _semantically_equal(existing: DrawRecord, row: NormalizedDrawInput) -> bool:
    return (
        existing.normalized_record_hash == row.normalized_record_hash
        and existing.lottery_type is row.lottery_type
        and existing.draw_number == row.draw_number
        and existing.draw_date == row.draw_date
        and existing.main_numbers == row.main_numbers
        and existing.special_numbers == row.special_numbers
    )


def _single_lottery_type(rows: tuple[NormalizedDrawInput, ...]) -> LotteryType | None:
    lottery_types = {row.lottery_type for row in rows}
    if len(lottery_types) > 1:
        raise _StoredDataError("one ingestion run cannot mix lottery types")
    return next(iter(lottery_types), None)


def _draw_record(row: sqlite3.Row | tuple[object, ...]) -> DrawRecord:
    values = tuple(row)
    if len(values) != 12:
        raise _StoredDataError("draw row shape is invalid")
    return DrawRecord(
        internal_id=_positive_integer(values[0], "draw id"),
        lottery_type=_lottery_type(values[1]),
        draw_number=_required_string(values[2], "draw number"),
        draw_date=_date_value(values[3]),
        main_numbers=_number_tuple(values[4], "main numbers"),
        special_numbers=_number_tuple(values[5], "special numbers"),
        normalized_record_hash=_required_string(values[6], "normalized hash"),
        source_name=_optional_string(values[7], "source name"),
        source_reference=_optional_string(values[8], "source reference"),
        ingestion_run_id=_required_string(values[9], "ingestion run id"),
        created_at=_datetime_value(values[10]),
        updated_at=_datetime_value(values[11]),
    )


def _ingestion_run_record(
    row: sqlite3.Row | tuple[object, ...],
) -> IngestionRunRecord:
    values = tuple(row)
    if len(values) != 17:
        raise _StoredDataError("ingestion run row shape is invalid")
    try:
        operation_type = IngestionOperationType(_required_string(values[1], "operation type"))
        status = IngestionRunStatus(_required_string(values[2], "run status"))
    except ValueError as exc:
        raise _StoredDataError("ingestion run enum is invalid") from exc
    return IngestionRunRecord(
        run_id=_required_string(values[0], "run id"),
        operation_type=operation_type,
        status=status,
        lottery_type=_optional_lottery_type(values[3]),
        source_filename=_required_string(values[4], "source filename"),
        source_sha256=_required_string(values[5], "source digest"),
        parser_version=_required_string(values[6], "parser version"),
        total_count=_nonnegative_integer(values[7], "total count"),
        inserted_count=_nonnegative_integer(values[8], "inserted count"),
        skipped_count=_nonnegative_integer(values[9], "skipped count"),
        conflict_count=_nonnegative_integer(values[10], "conflict count"),
        failed_count=_nonnegative_integer(values[11], "failed count"),
        first_draw_number=_optional_string(values[12], "first draw number"),
        last_draw_number=_optional_string(values[13], "last draw number"),
        started_at=_datetime_value(values[14]),
        completed_at=(None if values[15] is None else _datetime_value(values[15])),
        error_summary=_optional_string(values[16], "error summary"),
    )


def _ingestion_item_record(row: sqlite3.Row | tuple[object, ...]) -> IngestionItemRecord:
    values = tuple(row)
    if len(values) != 6:
        raise _StoredDataError("ingestion item row shape is invalid")
    try:
        disposition = IngestionItemDisposition(_required_string(values[3], "disposition"))
    except ValueError as exc:
        raise _StoredDataError("ingestion item disposition is invalid") from exc
    return IngestionItemRecord(
        source_row_number=_positive_integer(values[0], "source row number"),
        lottery_type=_optional_lottery_type(values[1]),
        draw_number=_optional_string(values[2], "draw number"),
        disposition=disposition,
        normalized_record_hash=_optional_string(values[4], "normalized hash"),
        message=_optional_string(values[5], "item message"),
    )


def _lottery_type(value: object) -> LotteryType:
    try:
        return LotteryType(_required_string(value, "lottery type"))
    except ValueError as exc:
        raise _StoredDataError("lottery type is invalid") from exc


def _optional_lottery_type(value: object) -> LotteryType | None:
    return None if value is None else _lottery_type(value)


def _number_tuple(value: object, label: str) -> tuple[int, ...]:
    if not isinstance(value, str):
        raise _StoredDataError(f"{label} is not text")
    try:
        decoded = cast(object, json.loads(value))
    except (json.JSONDecodeError, TypeError) as exc:
        raise _StoredDataError(f"{label} JSON is invalid") from exc
    if not isinstance(decoded, list):
        raise _StoredDataError(f"{label} JSON is invalid")
    items = cast(list[object], decoded)
    if any(type(item) is not int for item in items):
        raise _StoredDataError(f"{label} JSON is invalid")
    return tuple(cast(int, item) for item in items)


def _date_value(value: object) -> date:
    if not isinstance(value, str):
        raise _StoredDataError("draw date is not text")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise _StoredDataError("draw date is invalid") from exc


def _datetime_value(value: object) -> datetime:
    if not isinstance(value, str):
        raise _StoredDataError("timestamp is not text")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise _StoredDataError("timestamp is invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != UTC.utcoffset(parsed):
        raise _StoredDataError("timestamp is not explicit UTC")
    return parsed


def _required_string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise _StoredDataError(f"{label} is invalid")
    return value


def _optional_string(value: object, label: str) -> str | None:
    if value is None:
        return None
    return _required_string(value, label)


def _positive_integer(value: object, label: str) -> int:
    parsed = _nonnegative_integer(value, label)
    if parsed < 1:
        raise _StoredDataError(f"{label} must be positive")
    return parsed


def _nonnegative_integer(value: object, label: str) -> int:
    if type(value) is not int or value < 0:
        raise _StoredDataError(f"{label} must be a nonnegative integer")
    return value


def _total_pages(total_count: int, page_size: int) -> int:
    return 0 if total_count == 0 else (total_count + page_size - 1) // page_size


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _format_utc(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() != UTC.utcoffset(value):
        raise ValueError("timestamp must use UTC")
    return value.isoformat(timespec="microseconds").replace("+00:00", "Z")


def _is_busy_error(error: BaseException) -> bool:
    current: BaseException | None = error
    while current is not None:
        if isinstance(current, sqlite3.OperationalError):
            lowered = str(current).casefold()
            if "locked" in lowered or "busy" in lowered:
                return True
        current = current.__cause__
    return False


def _raise_repository_error(error: BaseException) -> Never:
    if _is_busy_error(error):
        raise RepositoryBusyError("Local draw data is temporarily busy") from None
    raise RepositoryUnavailableError("Local draw data is unavailable") from None
