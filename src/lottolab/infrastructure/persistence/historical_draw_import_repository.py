"""Historical V2 persistence for uploaded draw-import runs and chunks."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from collections.abc import Callable, Mapping, Sequence
from contextlib import suppress
from datetime import UTC, date, datetime
from pathlib import Path

from lottolab.domain.historical_draw_import import (
    ExistingHistoricalDraw,
    HistoricalDrawCandidate,
    HistoricalImportBatchStatus,
    HistoricalImportChunkResult,
    HistoricalImportChunkStatus,
    HistoricalImportDisposition,
    HistoricalImportFileResult,
    HistoricalImportFileStatus,
    HistoricalImportFilter,
    HistoricalImportReason,
    HistoricalImportRowResult,
    ImportRunStorage,
    StoredImportRun,
)
from lottolab.domain.historical_results import HistoricalLotteryType
from lottolab.infrastructure.persistence.historical_schema import (
    HistoricalSchemaError,
    initialize_schema,
    open_database,
    resolve_historical_database_paths,
    verify_schema_read_only,
)


class HistoricalDrawImportRepositoryError(HistoricalSchemaError):
    """An import metadata or Historical V2 persistence operation failed."""


def _default_clock() -> datetime:
    return datetime.now(UTC)


def _default_id_factory() -> str:
    return str(uuid.uuid4())


def _format_utc(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() != UTC.utcoffset(value):
        raise ValueError("timestamp must use UTC")
    return value.isoformat(timespec="microseconds").replace("+00:00", "Z")


def _sha256_canonical(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class SQLiteHistoricalDrawImportRepository:
    """Explicit-path repository that writes only the configured Historical V2 DB."""

    def __init__(
        self,
        database: Path,
        *,
        clock: Callable[[], datetime] = _default_clock,
        id_factory: Callable[[], str] = _default_id_factory,
    ) -> None:
        self._database = database
        self._clock = clock
        self._id_factory = id_factory

    @property
    def database(self) -> Path:
        return self._database

    def ensure_schema(self) -> None:
        try:
            paths = resolve_historical_database_paths(self._database)
            with sqlite3.connect(paths.database) as connection:
                journal_mode = str(connection.execute("PRAGMA journal_mode = WAL").fetchone()[0])
                if journal_mode.casefold() != "wal":
                    raise HistoricalDrawImportRepositoryError(
                        "historical import storage could not enable its writer journal"
                    )
            initialize_schema(paths.database)
        except HistoricalDrawImportRepositoryError:
            raise
        except Exception as exc:
            raise HistoricalDrawImportRepositoryError(
                "historical import schema could not be initialized"
            ) from exc

    def load_existing_draws(
        self,
    ) -> Mapping[tuple[HistoricalLotteryType, str], ExistingHistoricalDraw]:
        if not self._database.exists():
            return {}
        try:
            if not verify_schema_read_only(self._database):
                return {}
            with open_database(self._database, read_only=True) as connection:
                rows = connection.execute(
                    """
                    SELECT d.lottery_type, d.draw_number, d.draw_date,
                           d.main_numbers_json, d.special_numbers_json,
                           d.draw_sha256, d.run_id
                    FROM historical_draw_snapshot d
                    JOIN historical_result_run r ON r.id = d.run_id
                    WHERE r.status = 'COMPLETED'
                    ORDER BY r.completed_at ASC, d.id ASC
                    """
                ).fetchall()
        except Exception as exc:
            raise HistoricalDrawImportRepositoryError(
                "historical results storage is unavailable for import preview"
            ) from exc

        existing: dict[tuple[HistoricalLotteryType, str], ExistingHistoricalDraw] = {}
        for row in rows:
            lottery_type = HistoricalLotteryType(str(row[0]))
            draw_number = str(row[1])
            key = (lottery_type, draw_number)
            existing.setdefault(
                key,
                ExistingHistoricalDraw(
                    lottery_type=lottery_type,
                    draw_number=draw_number,
                    draw_date=date.fromisoformat(str(row[2])),
                    main_numbers=tuple(int(value) for value in json.loads(str(row[3]))),
                    special_numbers=tuple(int(value) for value in json.loads(str(row[4]))),
                    normalized_record_hash=str(row[5]),
                    historical_run_id=str(row[6]),
                ),
            )
        return existing

    def create_run(
        self,
        *,
        lottery_filter: HistoricalImportFilter,
        import_identity_sha256: str,
        files: Sequence[HistoricalImportFileResult],
        rows: Sequence[HistoricalImportRowResult],
    ) -> ImportRunStorage:
        self.ensure_schema()
        run_id = self._id_factory()
        timestamp = _format_utc(self._clock())
        file_ids = tuple(self._id_factory() for _ in files)
        row_ids: list[int] = []
        try:
            with open_database(self._database) as connection:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute(
                    """
                    INSERT INTO historical_import_run (
                        id, status, lottery_filter, import_identity_sha256,
                        started_at, completed_at, error_code, error_summary, created_at
                    ) VALUES (?, 'PREVIEW', ?, ?, ?, NULL, NULL, NULL, ?)
                    """,
                    (run_id, lottery_filter.value, import_identity_sha256, timestamp, timestamp),
                )
                for sequence, (file_id, file_result) in enumerate(
                    zip(file_ids, files, strict=True)
                ):
                    connection.execute(
                        """
                        INSERT INTO historical_import_file (
                            id, run_id, sequence, filename, source_sha256, status,
                            discovered_members, accepted_files, excluded_files, parsed_rows,
                            valid_rows, excluded_rows, duplicate_rows, conflict_rows,
                            imported_rows, failed_rows, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            file_id,
                            run_id,
                            sequence,
                            file_result.filename,
                            file_result.source_sha256,
                            file_result.status.value,
                            file_result.discovered_members,
                            file_result.accepted_files,
                            file_result.excluded_files,
                            file_result.parsed_rows,
                            file_result.valid_rows,
                            file_result.excluded_rows,
                            file_result.duplicate_rows,
                            file_result.conflict_rows,
                            file_result.imported_rows,
                            file_result.failed_rows,
                            timestamp,
                        ),
                    )
                    for row_result in file_result.rows:
                        row_id = connection.execute(
                            """
                            INSERT INTO historical_import_row (
                                run_id, file_id, chunk_id, member_path, member_sha256,
                                source_row_number, lottery_type, draw_number, draw_date,
                                main_numbers_json, special_numbers_json, normalized_record_hash,
                                disposition, reason_code, message, historical_run_id, created_at
                            ) VALUES (?, ?, NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?)
                            """,
                            (
                                run_id,
                                file_id,
                                row_result.member_path,
                                row_result.member_sha256,
                                row_result.source_row_number,
                                None
                                if row_result.lottery_type is None
                                else row_result.lottery_type.value,
                                row_result.draw_number,
                                None
                                if row_result.draw_date is None
                                else row_result.draw_date.isoformat(),
                                json.dumps(list(row_result.main_numbers), separators=(",", ":")),
                                json.dumps(list(row_result.special_numbers), separators=(",", ":")),
                                row_result.normalized_record_hash,
                                row_result.disposition.value,
                                None
                                if row_result.reason_code is None
                                else row_result.reason_code.value,
                                row_result.message,
                                timestamp,
                            ),
                        ).lastrowid
                        if row_id is None:
                            raise HistoricalDrawImportRepositoryError(
                                "historical import row insert returned no row id"
                            )
                        row_ids.append(int(row_id))
                connection.commit()
        except Exception as exc:
            raise HistoricalDrawImportRepositoryError(
                "historical import run metadata could not be persisted"
            ) from exc
        return ImportRunStorage(run_id=run_id, file_ids=file_ids, row_ids=tuple(row_ids))

    def commit_chunk(
        self,
        *,
        run_id: str,
        chunk_index: int,
        batch_identity_sha256: str,
        candidates: Sequence[HistoricalDrawCandidate],
        row_ids: Sequence[int],
    ) -> HistoricalImportChunkResult:
        if len(candidates) != len(row_ids):
            raise ValueError("candidate and row-id counts must match")
        timestamp = _format_utc(self._clock())
        chunk_id = self._id_factory()
        historical_run_ids: list[str] = []
        try:
            with open_database(self._database) as connection:
                connection.execute("BEGIN IMMEDIATE")
                grouped: dict[HistoricalLotteryType, list[HistoricalDrawCandidate]] = {}
                for candidate in candidates:
                    grouped.setdefault(candidate.lottery_type, []).append(candidate)
                row_to_historical_run: dict[int, str] = {}
                for lottery_type in sorted(grouped, key=lambda value: value.value):
                    group = grouped[lottery_type]
                    group_digest = _sha256_canonical(
                        [candidate.normalized_record_hash for candidate in group]
                    )
                    historical_run_id = self._id_factory()
                    historical_run_ids.append(historical_run_id)
                    connection.execute(
                        """
                        INSERT INTO historical_result_run (
                            id, import_identity_sha256, manifest_sha256, contract_version,
                            source_kind, source_repository, source_commit_oid,
                            source_artifact_sha256, dataset_identity, dataset_sha256,
                            legacy_run_id, lottery_type, status, started_at, completed_at,
                            error_code, error_summary, created_at
                        ) VALUES (?, ?, ?, 'LEGACY_IMPORT_V1', 'UPLOADED_DRAW_ARCHIVE',
                                  'uploaded-web-input', ?, ?, ?, ?, ?, ?, 'COMPLETED', ?, ?, NULL,
                                  NULL, ?)
                        """,
                        (
                            historical_run_id,
                            _sha256_canonical(
                                [batch_identity_sha256, chunk_index, lottery_type.value]
                            ),
                            group_digest,
                            "0" * 40,
                            batch_identity_sha256,
                            f"{run_id}:{chunk_index}:{lottery_type.value}",
                            group_digest,
                            run_id,
                            lottery_type.value,
                            timestamp,
                            timestamp,
                            timestamp,
                        ),
                    )
                    for candidate in group:
                        cursor = connection.execute(
                            """
                            INSERT INTO historical_draw_snapshot (
                                run_id, lottery_type, draw_number, draw_date,
                                main_numbers_json, special_numbers_json, draw_sha256, created_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                historical_run_id,
                                candidate.lottery_type.value,
                                candidate.draw_number,
                                candidate.draw_date.isoformat(),
                                json.dumps(list(candidate.main_numbers), separators=(",", ":")),
                                json.dumps(list(candidate.special_numbers), separators=(",", ":")),
                                candidate.normalized_record_hash,
                                timestamp,
                            ),
                        )
                        if cursor.rowcount != 1:
                            raise HistoricalDrawImportRepositoryError(
                                "historical draw snapshot insert did not affect one row"
                            )
                        row_to_historical_run[id(candidate)] = historical_run_id

                connection.execute(
                    """
                    INSERT INTO historical_import_chunk (
                        id, run_id, chunk_index, candidate_rows, imported_rows, failed_rows,
                        status, historical_run_ids_json, error_code, error_message,
                        started_at, completed_at
                    ) VALUES (?, ?, ?, ?, ?, 0, 'COMMITTED', ?, NULL, NULL, ?, ?)
                    """,
                    (
                        chunk_id,
                        run_id,
                        chunk_index,
                        len(candidates),
                        len(candidates),
                        json.dumps(historical_run_ids, separators=(",", ":")),
                        timestamp,
                        timestamp,
                    ),
                )
                for row_id, candidate in zip(row_ids, candidates, strict=True):
                    connection.execute(
                        """
                        UPDATE historical_import_row
                        SET chunk_id = ?, disposition = 'ACCEPTED', reason_code = NULL,
                            message = NULL, historical_run_id = ?
                        WHERE id = ?
                        """,
                        (chunk_id, row_to_historical_run[id(candidate)], row_id),
                    )
                connection.commit()
        except Exception as exc:
            with suppress(Exception):
                self.record_failed_chunk(
                    run_id=run_id,
                    chunk_index=chunk_index,
                    candidate_rows=len(candidates),
                    row_ids=row_ids,
                    error_message=str(exc),
                )
            raise HistoricalDrawImportRepositoryError(
                f"historical import chunk {chunk_index} failed"
            ) from exc
        return HistoricalImportChunkResult(
            chunk_index=chunk_index,
            candidate_rows=len(candidates),
            imported_rows=len(candidates),
            failed_rows=0,
            status=HistoricalImportChunkStatus.COMMITTED,
            historical_run_ids=tuple(historical_run_ids),
        )

    def record_failed_chunk(
        self,
        *,
        run_id: str,
        chunk_index: int,
        candidate_rows: int,
        row_ids: Sequence[int],
        error_message: str,
    ) -> HistoricalImportChunkResult:
        timestamp = _format_utc(self._clock())
        chunk_id = self._id_factory()
        message = error_message[:500]
        try:
            with open_database(self._database) as connection:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute(
                    """
                    INSERT INTO historical_import_chunk (
                        id, run_id, chunk_index, candidate_rows, imported_rows, failed_rows,
                        status, historical_run_ids_json, error_code, error_message,
                        started_at, completed_at
                    ) VALUES (?, ?, ?, ?, 0, ?, 'FAILED', '[]', ?, ?, ?, ?)
                    """,
                    (
                        chunk_id,
                        run_id,
                        chunk_index,
                        candidate_rows,
                        candidate_rows,
                        HistoricalImportReason.PERSISTENCE_FAILURE.value,
                        message,
                        timestamp,
                        timestamp,
                    ),
                )
                for row_id in row_ids:
                    connection.execute(
                        """
                        UPDATE historical_import_row
                        SET chunk_id = ?, disposition = 'FAILED',
                            reason_code = ?, message = ?
                        WHERE id = ?
                        """,
                        (
                            chunk_id,
                            HistoricalImportReason.PERSISTENCE_FAILURE.value,
                            message,
                            row_id,
                        ),
                    )
                connection.commit()
        except Exception as exc:
            raise HistoricalDrawImportRepositoryError(
                "failed chunk audit could not be recorded"
            ) from exc
        return HistoricalImportChunkResult(
            chunk_index=chunk_index,
            candidate_rows=candidate_rows,
            imported_rows=0,
            failed_rows=candidate_rows,
            status=HistoricalImportChunkStatus.FAILED,
            historical_run_ids=(),
            error_code=HistoricalImportReason.PERSISTENCE_FAILURE,
            error_message=message,
        )

    def complete_run(
        self,
        *,
        run_id: str,
        status: HistoricalImportBatchStatus,
        error_message: str | None = None,
    ) -> None:
        timestamp = _format_utc(self._clock())
        with open_database(self._database) as connection:
            cursor = connection.execute(
                """
                UPDATE historical_import_run
                SET status = ?, completed_at = ?, error_code = ?, error_summary = ?
                WHERE id = ? AND status IN ('IN_PROGRESS', 'PREVIEW')
                """,
                (
                    status.value,
                    timestamp,
                    None
                    if error_message is None
                    else HistoricalImportReason.PERSISTENCE_FAILURE.value,
                    None if error_message is None else error_message[:500],
                    run_id,
                ),
            )
            if cursor.rowcount != 1:
                raise HistoricalDrawImportRepositoryError(
                    "historical import run completion did not update one row"
                )
            connection.commit()

    def update_files(
        self,
        *,
        run_id: str,
        files: Sequence[HistoricalImportFileResult],
    ) -> None:
        """Persist final file counters after all chunk outcomes are known."""

        try:
            with open_database(self._database) as connection:
                connection.execute("BEGIN IMMEDIATE")
                for sequence, file_result in enumerate(files):
                    cursor = connection.execute(
                        """
                        UPDATE historical_import_file
                        SET status = ?, discovered_members = ?, accepted_files = ?,
                            excluded_files = ?, parsed_rows = ?, valid_rows = ?,
                            excluded_rows = ?, duplicate_rows = ?, conflict_rows = ?,
                            imported_rows = ?, failed_rows = ?
                        WHERE run_id = ? AND sequence = ?
                        """,
                        (
                            file_result.status.value,
                            file_result.discovered_members,
                            file_result.accepted_files,
                            file_result.excluded_files,
                            file_result.parsed_rows,
                            file_result.valid_rows,
                            file_result.excluded_rows,
                            file_result.duplicate_rows,
                            file_result.conflict_rows,
                            file_result.imported_rows,
                            file_result.failed_rows,
                            run_id,
                            sequence,
                        ),
                    )
                    if cursor.rowcount != 1:
                        raise HistoricalDrawImportRepositoryError(
                            "historical import file update did not affect one row"
                        )
                connection.commit()
        except Exception as exc:
            raise HistoricalDrawImportRepositoryError(
                "historical import file counters could not be persisted"
            ) from exc

    def get_run(self, run_id: str) -> StoredImportRun | None:
        if not self._database.exists() or not verify_schema_read_only(self._database):
            return None
        with open_database(self._database, read_only=True) as connection:
            run = connection.execute(
                """
                SELECT id, status, lottery_filter, import_identity_sha256
                FROM historical_import_run WHERE id = ?
                """,
                (run_id,),
            ).fetchone()
            if run is None:
                return None
            file_rows = connection.execute(
                """
                SELECT id, filename, source_sha256, status, discovered_members,
                       accepted_files, excluded_files, parsed_rows, valid_rows,
                       excluded_rows, duplicate_rows, conflict_rows, imported_rows,
                       failed_rows
                FROM historical_import_file WHERE run_id = ? ORDER BY sequence
                """,
                (run_id,),
            ).fetchall()
            files: list[HistoricalImportFileResult] = []
            rows_by_file: dict[str, list[HistoricalImportRowResult]] = {}
            raw_rows = connection.execute(
                """
                SELECT f.id, f.filename, f.source_sha256, ir.member_path, ir.member_sha256,
                       ir.source_row_number, ir.lottery_type, ir.draw_number, ir.draw_date,
                       ir.main_numbers_json, ir.special_numbers_json, ir.disposition,
                       ir.reason_code, ir.normalized_record_hash, ir.message,
                       ir.historical_run_id
                FROM historical_import_row ir
                JOIN historical_import_file f ON f.id = ir.file_id
                WHERE ir.run_id = ? ORDER BY f.sequence, ir.id
                """,
                (run_id,),
            ).fetchall()
            for raw in raw_rows:
                rows_by_file.setdefault(str(raw[0]), []).append(_row_result_from_db(raw[1:]))
            for file_row in file_rows:
                files.append(
                    HistoricalImportFileResult(
                        filename=str(file_row[1]),
                        source_sha256=str(file_row[2]),
                        status=HistoricalImportFileStatus(str(file_row[3])),
                        discovered_members=int(file_row[4]),
                        accepted_files=int(file_row[5]),
                        excluded_files=int(file_row[6]),
                        parsed_rows=int(file_row[7]),
                        valid_rows=int(file_row[8]),
                        excluded_rows=int(file_row[9]),
                        duplicate_rows=int(file_row[10]),
                        conflict_rows=int(file_row[11]),
                        imported_rows=int(file_row[12]),
                        failed_rows=int(file_row[13]),
                        rows=tuple(rows_by_file.get(str(file_row[0]), ())),
                    )
                )
            chunks = tuple(
                _chunk_result_from_db(row)
                for row in connection.execute(
                    """
                    SELECT chunk_index, candidate_rows, imported_rows, failed_rows, status,
                           historical_run_ids_json, error_code, error_message
                    FROM historical_import_chunk WHERE run_id = ? ORDER BY chunk_index
                    """,
                    (run_id,),
                ).fetchall()
            )
        rows = tuple(row for file_result in files for row in file_result.rows)
        return StoredImportRun(
            run_id=str(run[0]),
            status=HistoricalImportBatchStatus(str(run[1])),
            lottery_filter=HistoricalImportFilter(str(run[2])),
            import_identity_sha256=str(run[3]),
            files=tuple(files),
            chunks=chunks,
            rows=rows,
        )


def _row_result_from_db(row: Sequence[object]) -> HistoricalImportRowResult:
    (
        source_filename,
        source_sha256,
        member_path,
        member_sha256,
        source_row_number,
        lottery_type,
        draw_number,
        draw_date,
        main_numbers_json,
        special_numbers_json,
        disposition,
        reason_code,
        normalized_record_hash,
        message,
        historical_run_id,
    ) = row
    return HistoricalImportRowResult(
        source_filename=str(source_filename),
        source_sha256=str(source_sha256),
        member_path=str(member_path),
        member_sha256=None if member_sha256 is None else str(member_sha256),
        source_row_number=None if source_row_number is None else int(str(source_row_number)),
        lottery_type=None if lottery_type is None else HistoricalLotteryType(str(lottery_type)),
        draw_number=None if draw_number is None else str(draw_number),
        disposition=HistoricalImportDisposition(str(disposition)),
        reason_code=None if reason_code is None else HistoricalImportReason(str(reason_code)),
        normalized_record_hash=(
            None if normalized_record_hash is None else str(normalized_record_hash)
        ),
        message=None if message is None else str(message),
        historical_run_id=None if historical_run_id is None else str(historical_run_id),
        draw_date=None if draw_date is None else date.fromisoformat(str(draw_date)),
        main_numbers=tuple(
            int(value) for value in json.loads(str(main_numbers_json or "[]"))
        ),
        special_numbers=tuple(
            int(value) for value in json.loads(str(special_numbers_json or "[]"))
        ),
    )


def _chunk_result_from_db(row: Sequence[object]) -> HistoricalImportChunkResult:
    return HistoricalImportChunkResult(
        chunk_index=int(str(row[0])),
        candidate_rows=int(str(row[1])),
        imported_rows=int(str(row[2])),
        failed_rows=int(str(row[3])),
        status=HistoricalImportChunkStatus(str(row[4])),
        historical_run_ids=tuple(str(value) for value in json.loads(str(row[5]))),
        error_code=None if row[6] is None else HistoricalImportReason(str(row[6])),
        error_message=None if row[7] is None else str(row[7]),
    )


__all__ = [
    "HistoricalDrawImportRepositoryError",
    "ImportRunStorage",
    "SQLiteHistoricalDrawImportRepository",
    "StoredImportRun",
]
