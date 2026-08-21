"""Temporary-DB integration tests for transactional draw persistence."""

from __future__ import annotations

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from threading import Barrier

import pytest
from pytest import MonkeyPatch

import lottolab.infrastructure.persistence.draw_schema as draw_schema
import lottolab.infrastructure.persistence.repositories as repositories
from lottolab.application.draw_data import (
    DrawHistoryQuery,
    ExistingDrawConflictError,
    ImportCommitResult,
    IngestionRunQuery,
    InvalidDrawImportError,
    RepositoryBusyError,
    RepositoryUnavailableError,
)
from lottolab.domain.batch_imports import (
    BatchDrawImportPreview,
    ImportFilePayload,
    ImportFileStatus,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.ingestion import (
    DrawCsvParseResult,
    IngestionItemDisposition,
    IngestionRunStatus,
    NormalizedDrawInput,
)
from lottolab.infrastructure.imports.batch_files import preview_import_batch
from lottolab.infrastructure.imports.csv_draws import parse_draw_csv
from lottolab.infrastructure.persistence.draw_schema import (
    DATA_DIRECTORY_ENV,
    LocalDataPaths,
    initialize_schema,
    open_database,
    resolve_local_data_paths,
)
from lottolab.infrastructure.persistence.repositories import (
    SQLiteDrawDataRepository,
    SQLiteDrawRepository,
    SQLiteIngestionItemRepository,
)

HEADER = "lottery_type,draw_number,draw_date,main_numbers,special_numbers,source"


def csv_document(*rows: str) -> str:
    return "\n".join((HEADER, *rows, ""))


def task_paths(tmp_path: Path) -> LocalDataPaths:
    return resolve_local_data_paths(environ={DATA_DIRECTORY_ENV: str(tmp_path / "task-draw-data")})


def parsed(
    *rows: str,
    filename: str = "synthetic.csv",
) -> DrawCsvParseResult:
    result = parse_draw_csv("\n".join((HEADER, *rows, "")), filename=filename)
    assert result.is_valid, result.errors
    return result


def row(
    draw_number: str,
    draw_date: str,
    main_numbers: str = "1|3|9|17|24|49",
    special_number: str = "7",
    source: str = "synthetic-reference",
) -> str:
    return f"BIG_LOTTO,{draw_number},{draw_date},{main_numbers},{special_number},{source}"


def test_empty_history_reads_do_not_create_directory_or_database(tmp_path: Path) -> None:
    paths = task_paths(tmp_path)
    repository = SQLiteDrawDataRepository(paths)

    draws = repository.list_draws(DrawHistoryQuery())
    runs = repository.list_ingestion_runs(IngestionRunQuery())

    assert draws.records == ()
    assert draws.total_count == draws.total_pages == 0
    assert runs.records == ()
    assert runs.total_count == runs.total_pages == 0
    assert repository.get_draw(LotteryType.BIG_LOTTO, "1") is None
    assert repository.get_ingestion_run("unknown") is None
    assert not paths.data_directory.exists()
    assert not paths.database.exists()


def test_success_duplicate_history_and_ingestion_item_integrity(tmp_path: Path) -> None:
    paths = task_paths(tmp_path)
    repository = SQLiteDrawDataRepository(paths)
    document = parsed(
        row("0001", "2026-07-15"),
        row("0002", "2026-07-16", source="second-reference"),
        filename="../../display-only.csv",
    )

    first = repository.apply_valid_import(document)
    second = repository.apply_valid_import(document)

    assert first.status is IngestionRunStatus.SUCCESS
    assert first.inserted_count == 2
    assert first.skipped_count == first.conflict_count == first.failed_count == 0
    assert first.counts_are_consistent
    assert second.status is IngestionRunStatus.SUCCESS
    assert second.inserted_count == 0
    assert second.skipped_count == 2
    assert second.counts_are_consistent
    assert first.run_id is not None
    assert second.run_id is not None

    history = repository.list_draws(
        DrawHistoryQuery(lottery_type=LotteryType.BIG_LOTTO, page=1, page_size=1)
    )
    assert history.total_count == 2
    assert history.total_pages == 2
    assert history.sort == (
        "draw_date:desc",
        "draw_number:string_desc",
        "id:desc",
    )
    assert [record.draw_number for record in history.records] == ["0002"]
    stored = history.records[0]
    assert stored.main_numbers == (1, 3, 9, 17, 24, 49)
    assert stored.special_numbers == (7,)
    assert stored.source_name == "../../display-only.csv"
    assert stored.source_reference == "second-reference"
    assert stored.ingestion_run_id == first.run_id
    assert stored.created_at == stored.updated_at

    run_page = repository.list_ingestion_runs(IngestionRunQuery(page_size=10))
    assert run_page.total_count == 2
    assert [run.status for run in run_page.records] == [
        IngestionRunStatus.SUCCESS,
        IngestionRunStatus.SUCCESS,
    ]
    duplicate_detail = repository.get_ingestion_run(second.run_id)
    assert duplicate_detail is not None
    assert duplicate_detail.item_count == 2
    assert duplicate_detail.items_truncated is False
    assert [item.source_row_number for item in duplicate_detail.items] == [2, 3]
    assert {item.disposition for item in duplicate_detail.items} == {
        IngestionItemDisposition.SKIPPED_DUPLICATE
    }

    assert not Path(f"{paths.database}-wal").exists()
    assert not Path(f"{paths.database}-shm").exists()


def test_batch_repeat_safety_and_existing_conflict_are_classified_before_inserts(
    tmp_path: Path,
) -> None:
    repository = SQLiteDrawDataRepository(task_paths(tmp_path))
    repository.apply_valid_import(parsed(row("100", "2026-07-16")))
    existing_before = repository.get_draw(LotteryType.BIG_LOTTO, "100")
    assert existing_before is not None

    duplicate_preview = preview_import_batch(
        (
            ImportFilePayload(
                "duplicate.csv",
                csv_document(row("100", "2026-07-16")).encode(),
            ),
        )
    )
    duplicate = repository.apply_valid_batch_import(duplicate_preview)

    assert duplicate.status == "SUCCESS"
    assert duplicate.summary.accepted_rows == duplicate.summary.imported_rows == 0
    assert duplicate.summary.duplicate_rows == 1
    assert duplicate.files[0].status is ImportFileStatus.DUPLICATE
    assert duplicate.run_id is not None
    duplicate_audit = repository.get_ingestion_run(duplicate.run_id)
    assert duplicate_audit is not None
    assert duplicate_audit.run.status is IngestionRunStatus.SUCCESS
    assert duplicate_audit.run.skipped_count == 1
    assert repository.list_draws(DrawHistoryQuery()).total_count == 1

    conflict_preview = preview_import_batch(
        (
            ImportFilePayload(
                "a-conflict.csv",
                csv_document(row("100", "2026-07-16", main_numbers="1|3|9|17|24|48")).encode(),
            ),
            ImportFilePayload(
                "b-safe.csv",
                csv_document(row("101", "2026-07-17")).encode(),
            ),
        )
    )
    committed = repository.apply_valid_batch_import(conflict_preview)

    assert committed.status == "PARTIAL_SUCCESS"
    assert committed.summary.imported_rows == 1
    assert committed.summary.conflict_rows == 1
    results = {result.source_filename: result for result in committed.files}
    assert results["a-conflict.csv"].status is ImportFileStatus.CONFLICTED
    assert results["b-safe.csv"].status is ImportFileStatus.IMPORTED
    assert repository.get_draw(LotteryType.BIG_LOTTO, "100") == existing_before
    safe = repository.get_draw(LotteryType.BIG_LOTTO, "101")
    assert safe is not None
    assert safe.source_name == "b-safe.csv"
    assert safe.source_reference == "b-safe.csv|source=synthetic-reference"
    assert committed.run_id is not None
    conflict_audit = repository.get_ingestion_run(committed.run_id)
    assert conflict_audit is not None
    assert conflict_audit.run.status is IngestionRunStatus.FAILED
    assert conflict_audit.run.inserted_count == 1
    assert conflict_audit.run.conflict_count == 1

    failed_preview = preview_import_batch(
        (
            ImportFilePayload(
                "only-conflict.csv",
                csv_document(row("100", "2026-07-16", main_numbers="1|3|9|17|24|47")).encode(),
            ),
        )
    )
    failed = repository.apply_valid_batch_import(failed_preview)

    assert failed.status == "FAILED"
    assert failed.summary.imported_rows == 0
    assert failed.summary.conflict_rows == 1
    assert failed.files[0].status is ImportFileStatus.CONFLICTED
    assert repository.get_draw(LotteryType.BIG_LOTTO, "100") == existing_before


def test_batch_cross_file_duplicates_and_conflicts_have_distinct_outcomes(
    tmp_path: Path,
) -> None:
    original = csv_document(row("200", "2026-07-16")).encode()
    preview = preview_import_batch(
        (
            ImportFilePayload("c-conflict.csv", csv_document(row("200", "2026-07-17")).encode()),
            ImportFilePayload("b-duplicate.csv", original),
            ImportFilePayload("a-original.csv", original),
        )
    )

    repository = SQLiteDrawDataRepository(task_paths(tmp_path))
    committed = repository.apply_valid_batch_import(preview)

    assert committed.status == "PARTIAL_SUCCESS"
    assert committed.summary.imported_rows == 1
    assert committed.summary.duplicate_rows == 1
    assert committed.summary.conflict_rows == 1
    results = {result.source_filename: result for result in committed.files}
    assert results["a-original.csv"].status is ImportFileStatus.IMPORTED
    assert results["b-duplicate.csv"].status is ImportFileStatus.DUPLICATE
    assert results["c-conflict.csv"].status is ImportFileStatus.CONFLICTED
    assert repository.list_draws(DrawHistoryQuery()).total_count == 1
    stored = repository.get_draw(LotteryType.BIG_LOTTO, "200")
    assert stored is not None
    assert stored.draw_date.isoformat() == "2026-07-16"


def test_batch_chunk_failure_preserves_earlier_rows_and_continues_later_chunks(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    repository = SQLiteDrawDataRepository(task_paths(tmp_path))
    preview = preview_import_batch(
        (
            ImportFilePayload(
                "a-first.csv",
                csv_document(*(row(str(index), "2026-07-16") for index in range(1, 501))).encode(),
            ),
            ImportFilePayload(
                "b-failing.csv",
                csv_document(
                    *(row(str(index), "2026-07-17") for index in range(501, 1001))
                ).encode(),
            ),
            ImportFilePayload(
                "c-later.csv",
                csv_document(row("1001", "2026-07-18")).encode(),
            ),
        )
    )
    observed_chunk_sizes: list[int] = []
    original_apply_chunk = (
        SQLiteDrawDataRepository._apply_batch_chunk  # pyright: ignore[reportPrivateUsage]
    )
    original_insert = SQLiteDrawRepository.insert

    def observe_chunk(
        self: SQLiteDrawDataRepository,
        *,
        preview: BatchDrawImportPreview,
        chunk_index: int,
        rows: tuple[NormalizedDrawInput, ...],
    ) -> object:
        observed_chunk_sizes.append(len(rows))
        return original_apply_chunk(
            self,
            preview=preview,
            chunk_index=chunk_index,
            rows=rows,
        )

    def fail_midway_through_second_chunk(
        self: SQLiteDrawRepository,
        candidate: NormalizedDrawInput,
        *,
        run_id: str,
        source_filename: str,
        timestamp: datetime,
    ) -> None:
        if candidate.draw_number == "750":
            raise sqlite3.OperationalError("synthetic mid-chunk insert failure")
        original_insert(
            self,
            candidate,
            run_id=run_id,
            source_filename=source_filename,
            timestamp=timestamp,
        )

    monkeypatch.setattr(SQLiteDrawDataRepository, "_apply_batch_chunk", observe_chunk)
    monkeypatch.setattr(SQLiteDrawRepository, "insert", fail_midway_through_second_chunk)
    committed = repository.apply_valid_batch_import(preview)

    assert observed_chunk_sizes == [500, 500, 1]
    assert all(size <= 500 for size in observed_chunk_sizes)
    assert committed.status == "PARTIAL_SUCCESS"
    assert committed.committed_chunks == 2
    assert committed.failed_chunks == 1
    assert committed.summary.imported_rows == 501
    assert committed.summary.failed_rows == 500
    assert len(committed.run_ids) == 3
    failed_audit = repository.get_ingestion_run(committed.run_ids[1])
    assert failed_audit is not None
    assert failed_audit.run.status is IngestionRunStatus.FAILED
    assert failed_audit.run.failed_count == 500
    assert failed_audit.item_count == 500
    results = {result.source_filename: result for result in committed.files}
    assert results["a-first.csv"].status is ImportFileStatus.IMPORTED
    assert results["b-failing.csv"].status is ImportFileStatus.FAILED
    assert results["c-later.csv"].status is ImportFileStatus.IMPORTED
    preview_results = {result.source_filename: result for result in preview.files}
    for filename, result in results.items():
        assert result.source_locator == preview_results[filename].source_locator
        assert result.source_sha256 == preview_results[filename].source_sha256
    assert repository.list_draws(DrawHistoryQuery()).total_count == 501
    assert repository.get_draw(LotteryType.BIG_LOTTO, "1") is not None
    assert repository.get_draw(LotteryType.BIG_LOTTO, "501") is None
    assert repository.get_draw(LotteryType.BIG_LOTTO, "749") is None
    assert repository.get_draw(LotteryType.BIG_LOTTO, "750") is None
    assert repository.get_draw(LotteryType.BIG_LOTTO, "1000") is None
    later = repository.get_draw(LotteryType.BIG_LOTTO, "1001")
    assert later is not None
    assert later.source_name == "c-later.csv"
    assert later.source_reference == "c-later.csv|source=synthetic-reference"


def test_history_filters_and_string_order_are_deterministic(tmp_path: Path) -> None:
    repository = SQLiteDrawDataRepository(task_paths(tmp_path))
    repository.apply_valid_import(
        parsed(
            row("09", "2026-07-15"),
            row("10", "2026-07-16"),
            row("2", "2026-07-16"),
        )
    )

    ordered = repository.list_draws(DrawHistoryQuery(page_size=10))
    assert [record.draw_number for record in ordered.records] == ["2", "10", "09"]

    substring = repository.list_draws(
        DrawHistoryQuery(
            lottery_type=LotteryType.BIG_LOTTO,
            draw_number="0",
            date_from=ordered.records[-1].draw_date,
            date_to=ordered.records[0].draw_date,
            page_size=10,
        )
    )
    assert [record.draw_number for record in substring.records] == ["10", "09"]


def test_ingestion_run_item_details_are_ordered_and_bounded(tmp_path: Path) -> None:
    paths = task_paths(tmp_path)
    repository = SQLiteDrawDataRepository(paths)
    document = parsed(*(row(str(index), "2026-07-16") for index in range(1, 502)))

    committed = repository.apply_valid_import(document)
    assert committed.run_id is not None
    detail = repository.get_ingestion_run(committed.run_id)

    assert detail is not None
    assert detail.item_count == 501
    assert len(detail.items) == 500
    assert detail.items_truncated is True
    assert [item.source_row_number for item in detail.items[:3]] == [2, 3, 4]
    assert [item.source_row_number for item in detail.items[-3:]] == [499, 500, 501]
    assert document.source_filename.encode() in paths.database.read_bytes()
    assert (HEADER + "\n").encode() not in paths.database.read_bytes()


def test_conflict_records_failed_run_and_rolls_back_every_new_draw(tmp_path: Path) -> None:
    repository = SQLiteDrawDataRepository(task_paths(tmp_path))
    initial = parsed(row("100", "2026-07-16"))
    inserted = repository.apply_valid_import(initial)
    before = repository.get_draw(LotteryType.BIG_LOTTO, "100")
    assert before is not None

    conflict = parsed(
        row("101", "2026-07-17"),
        row("100", "2026-07-16", main_numbers="1|3|9|17|24|48"),
    )
    with pytest.raises(ExistingDrawConflictError) as captured:
        repository.apply_valid_import(conflict)

    failed = captured.value.result
    assert failed.status is IngestionRunStatus.FAILED
    assert failed.run_id is not None
    assert failed.inserted_count == 0
    assert failed.skipped_count == 0
    assert failed.conflict_count == 1
    assert failed.failed_count == 1
    assert failed.counts_are_consistent
    assert repository.get_draw(LotteryType.BIG_LOTTO, "101") is None
    assert repository.get_draw(LotteryType.BIG_LOTTO, "100") == before

    detail = repository.get_ingestion_run(failed.run_id)
    assert detail is not None
    assert detail.run.status is IngestionRunStatus.FAILED
    assert detail.run.error_summary == "Batch rejected because existing draw data conflicts."
    assert detail.run.inserted_count == 0
    assert [item.disposition for item in detail.items] == [
        IngestionItemDisposition.FAILED,
        IngestionItemDisposition.CONFLICT,
    ]
    assert detail.run.total_count == detail.item_count == 2

    original_detail = repository.get_ingestion_run(inserted.run_id or "")
    assert original_detail is not None
    assert original_detail.run.status is IngestionRunStatus.SUCCESS


def test_invalid_parse_result_is_refused_before_schema_creation(tmp_path: Path) -> None:
    paths = task_paths(tmp_path)
    repository = SQLiteDrawDataRepository(paths)
    invalid = parse_draw_csv(
        "\n".join(
            (
                HEADER,
                row("1", "2026-07-16"),
                row("1", "2026-07-16"),
                "",
            )
        )
    )
    assert not invalid.is_valid
    assert invalid.normalized_rows

    with pytest.raises(InvalidDrawImportError):
        repository.apply_valid_import(invalid)

    assert not paths.data_directory.exists()
    assert not paths.database.exists()


def test_unexpected_item_failure_rolls_back_draws_runs_and_items(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    paths = task_paths(tmp_path)
    initialize_schema(paths)
    repository = SQLiteDrawDataRepository(paths)

    def fail_item(*args: object, **kwargs: object) -> None:
        del args, kwargs
        raise sqlite3.OperationalError("synthetic repository failure")

    monkeypatch.setattr(SQLiteIngestionItemRepository, "add", fail_item)
    with pytest.raises(RepositoryUnavailableError, match="unavailable"):
        repository.apply_valid_import(parsed(row("1", "2026-07-16")))

    assert repository.list_draws(DrawHistoryQuery()).total_count == 0
    assert repository.list_ingestion_runs(IngestionRunQuery()).total_count == 0
    with open_database(paths, read_only=True) as connection:
        assert connection.execute("SELECT COUNT(*) FROM ingestion_items").fetchone() == (0,)


def test_concurrent_equivalent_commits_insert_once_then_skip(tmp_path: Path) -> None:
    paths = task_paths(tmp_path)
    barrier = Barrier(2)
    document = parsed(row("500", "2026-07-16"))

    def commit() -> ImportCommitResult:
        barrier.wait(timeout=5)
        return SQLiteDrawDataRepository(paths).apply_valid_import(document)

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = (executor.submit(commit), executor.submit(commit))
        results = [future.result(timeout=10) for future in futures]

    assert sorted((result.inserted_count, result.skipped_count) for result in results) == [
        (0, 1),
        (1, 0),
    ]
    repository = SQLiteDrawDataRepository(paths)
    assert repository.list_draws(DrawHistoryQuery()).total_count == 1
    assert repository.list_ingestion_runs(IngestionRunQuery()).total_count == 2


def test_concurrent_fresh_database_conflict_commits_failed_audit(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    paths = task_paths(tmp_path)
    assert not paths.data_directory.exists()
    assert not paths.database.exists()
    start_barrier = Barrier(2)
    fresh_path_barrier = Barrier(2)
    original_initialize = repositories.initialize_schema

    def synchronized_fresh_path(candidate: LocalDataPaths) -> None:
        fresh_path_barrier.wait(timeout=5)
        original_initialize(candidate)

    monkeypatch.setattr(repositories, "initialize_schema", synchronized_fresh_path)
    documents = (
        parsed(row("600", "2026-07-16", main_numbers="1|3|9|17|24|49")),
        parsed(row("600", "2026-07-16", main_numbers="1|3|9|17|24|48")),
    )

    def commit(document: DrawCsvParseResult) -> ImportCommitResult | ExistingDrawConflictError:
        start_barrier.wait(timeout=5)
        try:
            return SQLiteDrawDataRepository(paths).apply_valid_import(document)
        except ExistingDrawConflictError as exc:
            return exc

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = (
            executor.submit(commit, documents[0]),
            executor.submit(commit, documents[1]),
        )
        results = [future.result(timeout=10) for future in futures]

    assert sum(isinstance(result, ExistingDrawConflictError) for result in results) == 1
    failed = next(
        result.result for result in results if isinstance(result, ExistingDrawConflictError)
    )
    assert failed.run_id is not None
    assert failed.status is IngestionRunStatus.FAILED
    assert failed.inserted_count == 0
    assert failed.conflict_count == 1
    assert failed.counts_are_consistent
    repository = SQLiteDrawDataRepository(paths)
    stored = repository.get_draw(LotteryType.BIG_LOTTO, "600")
    assert stored is not None
    assert stored.main_numbers in {
        (1, 3, 9, 17, 24, 48),
        (1, 3, 9, 17, 24, 49),
    }
    assert repository.list_draws(DrawHistoryQuery()).total_count == 1
    runs = repository.list_ingestion_runs(IngestionRunQuery(page_size=10)).records
    assert len(runs) == 2
    assert {run.status for run in runs} == {
        IngestionRunStatus.SUCCESS,
        IngestionRunStatus.FAILED,
    }
    detail = repository.get_ingestion_run(failed.run_id)
    assert detail is not None
    assert detail.run.status is IngestionRunStatus.FAILED
    assert detail.run.total_count == detail.item_count == 1
    assert [item.disposition for item in detail.items] == [IngestionItemDisposition.CONFLICT]


def test_busy_failed_audit_returns_service_busy_without_false_conflict(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    paths = task_paths(tmp_path)
    repository = SQLiteDrawDataRepository(paths)
    successful = repository.apply_valid_import(parsed(row("650", "2026-07-16")))
    stored_before = repository.get_draw(LotteryType.BIG_LOTTO, "650")
    original_record_failed = (
        SQLiteDrawDataRepository._record_failed_conflict  # pyright: ignore[reportPrivateUsage]
    )
    monkeypatch.setattr(draw_schema, "BUSY_TIMEOUT_MS", 10)

    def hold_audit_writer_lock(
        self: SQLiteDrawDataRepository,
        connection: sqlite3.Connection,
        *,
        result: DrawCsvParseResult,
        run_id: str,
        lottery_type: LotteryType | None,
        first_draw_number: str | None,
        last_draw_number: str | None,
    ) -> ImportCommitResult:
        lock = sqlite3.connect(paths.database, isolation_level=None)
        lock.execute("BEGIN IMMEDIATE")
        try:
            return original_record_failed(
                self,
                connection,
                result=result,
                run_id=run_id,
                lottery_type=lottery_type,
                first_draw_number=first_draw_number,
                last_draw_number=last_draw_number,
            )
        finally:
            lock.rollback()
            lock.close()

    monkeypatch.setattr(SQLiteDrawDataRepository, "_record_failed_conflict", hold_audit_writer_lock)
    conflict = parsed(row("650", "2026-07-16", main_numbers="1|3|9|17|24|48"))
    with pytest.raises(RepositoryBusyError, match="temporarily busy"):
        repository.apply_valid_import(conflict)

    assert repository.get_draw(LotteryType.BIG_LOTTO, "650") == stored_before
    runs = repository.list_ingestion_runs(IngestionRunQuery(page_size=10)).records
    assert [run.run_id for run in runs] == [successful.run_id]


def test_busy_timeout_is_bounded_and_error_is_sanitized(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    paths = task_paths(tmp_path)
    initialize_schema(paths)
    monkeypatch.setattr(draw_schema, "BUSY_TIMEOUT_MS", 10)

    lock = sqlite3.connect(paths.database, isolation_level=None)
    lock.execute("BEGIN IMMEDIATE")
    try:
        with pytest.raises(RepositoryBusyError, match="temporarily busy") as captured:
            SQLiteDrawDataRepository(paths).apply_valid_import(parsed(row("700", "2026-07-16")))
    finally:
        lock.rollback()
        lock.close()

    message = str(captured.value)
    assert str(paths.database) not in message
    assert "locked" not in message.casefold()
