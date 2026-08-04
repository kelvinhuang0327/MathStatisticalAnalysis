from __future__ import annotations

import io
import zipfile
from pathlib import Path
from typing import Any

from lottolab.application.use_cases.historical_draw_import import HistoricalDrawImportService
from lottolab.domain.historical_draw_import import (
    HistoricalImportDisposition,
    HistoricalImportFilter,
    HistoricalImportInput,
    HistoricalImportReason,
)
from lottolab.infrastructure.downloaded_draw_archive import DownloadedDrawArchiveParser
from lottolab.infrastructure.persistence.historical_draw_import_repository import (
    SQLiteHistoricalDrawImportRepository,
)


def _power_csv(start: int, count: int) -> bytes:
    rows = [
        "遊戲名稱,期別,開獎日期,獎號1,獎號2,獎號3,獎號4,獎號5,獎號6,第二區"
    ]
    for draw_number in range(start, start + count):
        base = (draw_number % 30) + 1
        numbers = tuple(sorted(((base + index) % 38 + 1) for index in range(6)))
        rows.append(
            f"威力彩,{draw_number},2024/01/01,{numbers[0]},{numbers[1]},"
            f"{numbers[2]},{numbers[3]},{numbers[4]},{numbers[5]},1"
        )
    return ("\n".join(rows) + "\n").encode("utf-8")


def _zip_bytes(members: dict[str, bytes]) -> bytes:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in members.items():
            archive.writestr(name, content)
    return stream.getvalue()


def test_preview_commit_and_duplicate_conflict_resolution(tmp_path: Path) -> None:
    repository = SQLiteHistoricalDrawImportRepository(tmp_path / "historical.db")
    service = HistoricalDrawImportService(repository, DownloadedDrawArchiveParser())
    original = _power_csv(1, 1)

    preview = service.preview([HistoricalImportInput("draws.csv", original)])
    assert preview.status.value == "PREVIEW"
    assert preview.summary.imported_rows == 0
    assert preview.summary.valid_rows == 1

    committed = service.import_inputs([HistoricalImportInput("draws.csv", original)])
    assert committed.status.value == "COMPLETED"
    assert committed.summary.imported_rows == 1
    assert committed.chunks[0].candidate_rows == 1
    assert committed.row_results[0].disposition is HistoricalImportDisposition.ACCEPTED

    duplicate = service.preview([HistoricalImportInput("again.csv", original)])
    assert duplicate.summary.duplicate_rows == 1
    assert duplicate.row_results[0].reason_code is HistoricalImportReason.DUPLICATE_SKIPPED

    conflict_csv = original.replace(b",1,2024/01/01,", b",1,2024/01/02,")
    conflict = service.preview([HistoricalImportInput("conflict.csv", conflict_csv)])
    assert conflict.summary.conflict_rows == 1
    assert conflict.row_results[0].reason_code is HistoricalImportReason.CONFLICT_REJECTED


def test_zip_filter_bingo_and_bonus_exclusions(tmp_path: Path) -> None:
    repository = SQLiteHistoricalDrawImportRepository(tmp_path / "historical.db")
    service = HistoricalDrawImportService(repository, DownloadedDrawArchiveParser())
    archive = _zip_bytes(
        {
            "power.csv": _power_csv(1, 1),
            "賓果.csv": _power_csv(2, 1),
            "bonus.csv": _power_csv(3, 1),
        }
    )

    result = service.preview(
        [HistoricalImportInput("legacy.zip", archive)],
        lottery_filter=HistoricalImportFilter.POWER_LOTTO,
    )

    assert result.summary.parsed_rows == 3
    assert result.summary.valid_rows == 1
    assert result.summary.excluded_rows == 2
    reasons = {row.reason_code for row in result.row_results}
    assert HistoricalImportReason.BINGO_EXCLUDED in reasons
    assert HistoricalImportReason.UNSUPPORTED_BONUS_DRAW in reasons


def test_chunk_boundary_and_partial_success_preserve_earlier_chunks(tmp_path: Path) -> None:
    class FailingSecondChunkRepository:
        def __init__(self, database: Path) -> None:
            self.delegate = SQLiteHistoricalDrawImportRepository(database)

        def ensure_schema(self) -> None:
            self.delegate.ensure_schema()

        def load_existing_draws(self) -> Any:
            return self.delegate.load_existing_draws()

        def create_run(self, **kwargs: Any) -> Any:
            return self.delegate.create_run(**kwargs)

        def commit_chunk(self, **kwargs: Any) -> Any:
            if kwargs["chunk_index"] == 1:
                raise RuntimeError("synthetic chunk failure")
            return self.delegate.commit_chunk(**kwargs)

        def record_failed_chunk(self, **kwargs: Any) -> Any:
            return self.delegate.record_failed_chunk(**kwargs)

        def update_files(self, **kwargs: Any) -> None:
            self.delegate.update_files(**kwargs)

        def complete_run(self, **kwargs: Any) -> None:
            self.delegate.complete_run(**kwargs)

        def get_run(self, run_id: str) -> Any:
            return self.delegate.get_run(run_id)

    repository = FailingSecondChunkRepository(tmp_path / "historical.db")
    service = HistoricalDrawImportService(repository, DownloadedDrawArchiveParser())
    result = service.import_inputs(
        [HistoricalImportInput("large.csv", _power_csv(1, 1001))]
    )

    assert result.status.value == "PARTIAL_SUCCESS"
    assert [chunk.candidate_rows for chunk in result.chunks] == [500, 500, 1]
    assert [chunk.status.value for chunk in result.chunks] == [
        "COMMITTED",
        "FAILED",
        "COMMITTED",
    ]
    assert result.summary.imported_rows == 501
    assert result.summary.failed_rows == 500
    assert all(chunk.candidate_rows <= 500 for chunk in result.chunks)


def test_parse_failure_is_reflected_in_file_and_batch_status(tmp_path: Path) -> None:
    repository = SQLiteHistoricalDrawImportRepository(tmp_path / "historical.db")
    service = HistoricalDrawImportService(repository, DownloadedDrawArchiveParser())
    inputs = [
        HistoricalImportInput("valid.csv", _power_csv(1, 1)),
        HistoricalImportInput("invalid.csv", b""),
    ]

    preview = service.preview(inputs)
    assert preview.status.value == "PREVIEW"
    preview_files = {item.filename: item for item in preview.files}
    assert preview_files["valid.csv"].status.value == "ACCEPTED"
    assert preview_files["invalid.csv"].status.value == "FAILED"

    result = service.import_inputs(inputs)
    assert result.status.value == "PARTIAL_SUCCESS"
    assert result.summary.imported_rows == 1
    assert result.summary.failed_rows == 0
    result_files = {item.filename: item for item in result.files}
    assert result_files["invalid.csv"].status.value == "FAILED"
