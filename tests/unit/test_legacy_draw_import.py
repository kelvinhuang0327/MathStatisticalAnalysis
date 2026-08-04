"""Unit coverage for the owner-authorized legacy draw-file adapters."""

from __future__ import annotations

import io
import zipfile

from lottolab.domain.batch_imports import ImportFilePayload, ImportFileStatus
from lottolab.domain.draws import LotteryType
from lottolab.infrastructure.imports.batch_files import preview_import_batch
from lottolab.infrastructure.imports.legacy_files import (
    parse_legacy_csv,
    parse_legacy_daily539_txt,
)

LEGACY_HEADER = (
    "遊戲名稱,期別,開獎日期,銷售總額,銷售注數,總獎金,"
    "獎號1,獎號2,獎號3,獎號4,獎號5,獎號6,特別號,\n"
)


def legacy_csv(row: str, *, header: str = LEGACY_HEADER) -> bytes:
    return (header + row + "\n").encode("utf-8-sig")


def zip_bytes(*members: tuple[str, bytes]) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in members:
            archive.writestr(name, content)
    return output.getvalue()


def test_legacy_csv_adapters_preserve_three_lottery_shapes() -> None:
    big = parse_legacy_csv(
        legacy_csv("大樂透,96000001,2007/01/02,0,0,0,13,21,23,27,31,49,19,,"),
        filename="big.csv",
        source_locator="big.csv",
        expected_lottery_type=LotteryType.BIG_LOTTO,
    )
    power = parse_legacy_csv(
        legacy_csv(
            "威力彩,104000001,2015/01/01,0,0,0,01,03,05,11,17,21,02,,",
            header=LEGACY_HEADER.replace("特別號", "第二區"),
        ),
        filename="power.csv",
        source_locator="power.csv",
        expected_lottery_type=LotteryType.POWER_LOTTO,
    )
    daily = parse_legacy_csv(
        legacy_csv("今彩539,96000001,2007/01/01,0,0,0,09,11,27,28,38,,"),
        filename="daily.csv",
        source_locator="daily.csv",
        expected_lottery_type=LotteryType.DAILY_539,
    )

    assert big.is_valid and big.normalized_rows[0].special_numbers == (19,)
    assert power.is_valid and power.normalized_rows[0].special_numbers == (2,)
    assert daily.is_valid and daily.normalized_rows[0].special_numbers == ()
    assert big.normalized_rows[0].draw_date.isoformat() == "2007-01-02"


def test_daily539_txt_adapter_accepts_roc_year_and_compact_numbers() -> None:
    result = parse_legacy_daily539_txt(
        "第112000001期\n開獎日期:111/01/02\n0102030405\n".encode("big5"),
        filename="今彩539.txt",
        source_locator="今彩539.txt",
    )

    assert result.is_valid
    row = result.normalized_rows[0]
    assert row.lottery_type is LotteryType.DAILY_539
    assert row.draw_number == "112000001"
    assert row.draw_date.isoformat() == "2022-01-02"
    assert row.main_numbers == (1, 2, 3, 4, 5)


def test_batch_expansion_is_deterministic_and_reports_exclusions() -> None:
    valid_archive = zip_bytes(
        ("nested/valid.csv", legacy_csv("大樂透,96000001,2007/01/02,0,0,0,13,21,23,27,31,49,19,,")),
        ("nested/readme.pdf", b"ignored"),
    )
    unsafe_archive = io.BytesIO()
    with zipfile.ZipFile(unsafe_archive, "w") as archive:
        archive.writestr(
            "../escape.csv",
            legacy_csv("大樂透,96000002,2007/01/04,0,0,0,13,21,23,27,31,49,19,,"),
        )

    preview = preview_import_batch(
        (
            ImportFilePayload("valid.zip", valid_archive),
            ImportFilePayload("bingo.csv", legacy_csv("賓果賓果,1,2026/01/01,0,0,0,1,")),
            ImportFilePayload(
                "bonus.csv",
                legacy_csv("大樂透加開,1,2026/01/01,0,0,0,1,2,3,4,5,6,7,"),
            ),
            ImportFilePayload("other.csv", legacy_csv("38樂合彩,1,2026/01/01,0,0,0,1,")),
            ImportFilePayload("unsafe.zip", unsafe_archive.getvalue()),
            ImportFilePayload("notes.json", b"{}"),
            ImportFilePayload("broken.zip", b"not a zip"),
        )
    )

    assert preview.normalized_rows[0].lottery_type is LotteryType.BIG_LOTTO
    assert preview.normalized_rows[0].source is not None
    assert preview.normalized_rows[0].source.startswith("valid.zip!nested/valid.csv")
    assert preview.normalized_rows[0].source_name == "nested/valid.csv"
    statuses = {file.source_filename: file.status for file in preview.files}
    assert statuses["nested/valid.csv"] is ImportFileStatus.ACCEPTED
    assert statuses["bingo.csv"] is ImportFileStatus.EXCLUDED
    assert statuses["bonus.csv"] is ImportFileStatus.EXCLUDED
    assert statuses["other.csv"] is ImportFileStatus.EXCLUDED
    assert statuses["notes.json"] is ImportFileStatus.EXCLUDED
    assert statuses["broken.zip"] is ImportFileStatus.FAILED
    assert any(file.issues[0].code == "UNSAFE_ARCHIVE_MEMBER" for file in preview.files)
