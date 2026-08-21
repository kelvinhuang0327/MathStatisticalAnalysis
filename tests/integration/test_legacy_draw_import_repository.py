"""Transactional integration coverage for the batch draw-import port."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

from lottolab.application.draw_data import DrawHistoryQuery, IngestionRunQuery
from lottolab.domain.batch_imports import ImportFilePayload
from lottolab.domain.draws import LotteryType
from lottolab.domain.ingestion import IngestionRunStatus
from lottolab.infrastructure.imports.batch_files import preview_import_batch
from lottolab.infrastructure.persistence.draw_schema import (
    DATA_DIRECTORY_ENV,
    LocalDataPaths,
    resolve_local_data_paths,
)
from lottolab.infrastructure.persistence.repositories import SQLiteDrawDataRepository

HEADER = "lottery_type,draw_number,draw_date,main_numbers,special_numbers,source"


def task_paths(tmp_path: Path) -> LocalDataPaths:
    return resolve_local_data_paths(environ={DATA_DIRECTORY_ENV: str(tmp_path / "batch-data")})


def canonical(*rows: str) -> bytes:
    return ("\n".join((HEADER, *rows, ""))).encode("utf-8")


def big_row(draw_number: str, *, main: str = "1|3|9|17|24|49") -> str:
    return f"BIG_LOTTO,{draw_number},2026-07-16,{main},7,batch-source"


def test_batch_commit_is_repeat_safe_and_rejects_conflicts_without_rollback(
    tmp_path: Path,
) -> None:
    repository = SQLiteDrawDataRepository(task_paths(tmp_path))
    first_preview = preview_import_batch(
        (ImportFilePayload("first.csv", canonical(big_row("100"))),)
    )
    first = repository.apply_valid_batch_import(first_preview)

    duplicate = repository.apply_valid_batch_import(first_preview)

    assert first.status == IngestionRunStatus.SUCCESS.value
    assert first.summary.imported_rows == 1
    assert duplicate.status == IngestionRunStatus.SUCCESS.value
    assert duplicate.summary.imported_rows == 0
    assert duplicate.summary.duplicate_rows == 1
    assert repository.list_draws(DrawHistoryQuery(page_size=10)).total_count == 1

    conflict_preview = preview_import_batch(
        (
            ImportFilePayload(
                "conflict.csv",
                canonical(
                    big_row("101"),
                    big_row("100", main="1|3|9|17|24|48"),
                ),
            ),
        )
    )
    partial = repository.apply_valid_batch_import(conflict_preview)

    assert partial.status == "PARTIAL_SUCCESS"
    assert partial.summary.imported_rows == 1
    assert partial.summary.conflict_rows == 1
    assert partial.files[0].status.value == "PARTIAL_SUCCESS"
    assert repository.get_draw(LotteryType.BIG_LOTTO, "101") is not None
    assert repository.list_draws(DrawHistoryQuery(page_size=10)).total_count == 2
    runs = repository.list_ingestion_runs(IngestionRunQuery(page_size=10))
    assert runs.records[0].status is IngestionRunStatus.FAILED


def test_batch_commit_imports_a_valid_zip_with_member_provenance(tmp_path: Path) -> None:
    archive_bytes = io.BytesIO()
    member = canonical(big_row("200"))
    with zipfile.ZipFile(archive_bytes, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("nested/draws.csv", member)
    preview = preview_import_batch((ImportFilePayload("draws.zip", archive_bytes.getvalue()),))

    committed = SQLiteDrawDataRepository(task_paths(tmp_path)).apply_valid_batch_import(preview)

    assert committed.status == "SUCCESS"
    assert committed.summary.imported_rows == 1
    assert committed.files[0].source_filename == "nested/draws.csv"
    assert committed.files[0].source_locator.startswith("draws.zip!nested/draws.csv")
    assert committed.files[0].source_sha256 == preview.files[0].source_sha256


def test_batch_commit_accepts_daily_power_and_mixed_lottery_audit(tmp_path: Path) -> None:
    repository = SQLiteDrawDataRepository(task_paths(tmp_path))
    preview = preview_import_batch(
        (
            ImportFilePayload(
                "daily.csv",
                canonical("DAILY_539,96000001,2007-01-01,1|2|3|4|5,,daily"),
            ),
            ImportFilePayload(
                "power.csv",
                canonical("POWER_LOTTO,104000001,2015-01-01,1|3|5|11|17|21,2,power"),
            ),
        )
    )

    committed = repository.apply_valid_batch_import(preview)

    assert committed.status == IngestionRunStatus.SUCCESS.value
    assert committed.summary.imported_rows == 2
    assert repository.get_draw(LotteryType.DAILY_539, "96000001") is not None
    assert repository.get_draw(LotteryType.POWER_LOTTO, "104000001") is not None
    assert committed.files[0].source_filename == "daily.csv"
