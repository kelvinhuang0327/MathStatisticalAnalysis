"""Focused parser and validation tests for the downloaded archive auditor."""

from __future__ import annotations

import json

from lottolab.infrastructure.downloaded_draw_archive import (
    BIG_LOTTO,
    DAILY_539,
    ArchiveMember,
    DatasetClassification,
    ParsedDraw,
    StructuralIssue,
    parse_csv_bytes,
)

POWER_HEADER = (
    "遊戲名稱,期別,開獎日期,銷售總額,銷售注數,總獎金,獎號1,獎號2,獎號3,獎號4,獎號5,獎號6,第二區"
)
DAILY_HEADER = "遊戲名稱,期別,開獎日期,銷售總額,銷售注數,總獎金,獎號1,獎號2,獎號3,獎號4,獎號5"
BIG_HEADER = (
    "遊戲名稱,期別,開獎日期,銷售總額,銷售注數,總獎金,獎號1,獎號2,獎號3,獎號4,獎號5,獎號6,特別號"
)


def _row(game: str, identity: str, date_text: str, numbers: str, special: str = "") -> str:
    values = [game, identity, date_text, "0", "0", "0", *numbers.split(",")]
    if special:
        values.append(special)
    return ",".join(values)


def _parse(
    document: str,
    *,
    bom: bool = False,
) -> tuple[ArchiveMember, tuple[ParsedDraw, ...], tuple[StructuralIssue, ...]]:
    content = document.encode("utf-8")
    if bom:
        content = b"\xef\xbb\xbf" + content
    return parse_csv_bytes(content)


def test_utf8_bom_powerlotto_happy_path_preserves_raw_order() -> None:
    member, draws, issues = _parse(
        "\n".join(
            [
                POWER_HEADER,
                _row("威力彩", "115000001", "2026/01/01", "01,02,03,04,05,06", "08"),
            ]
        ),
        bom=True,
    )

    assert member.classification is DatasetClassification.POWER_LOTTO
    assert member.detected_encoding == "UTF-8 with BOM"
    assert member.row_count == 1
    assert len(draws) == 1
    draw = draws[0]
    assert draw.raw_draw_identity == "115000001"
    assert draw.raw_date_text == "2026/01/01"
    assert draw.draw_date == "2026-01-01"
    assert draw.raw_zone1 == ("01", "02", "03", "04", "05", "06")
    assert draw.zone1 == (1, 2, 3, 4, 5, 6)
    assert draw.zone2 == 8
    assert issues == ()


def test_powerlotto_validation_covers_range_duplicates_missing_zone2_overlap_and_order() -> None:
    invalid_range = _parse(
        "\n".join(
            [
                POWER_HEADER,
                _row("威力彩", "1", "2026/01/01", "01,02,03,04,05,39", "08"),
            ]
        )
    )[2]
    assert any(issue.code == "ZONE1_OUT_OF_RANGE" for issue in invalid_range)

    duplicate = _parse(
        "\n".join(
            [
                POWER_HEADER,
                _row("威力彩", "2", "2026/01/01", "01,02,02,04,05,06", "08"),
            ]
        )
    )[2]
    assert any(issue.code == "DUPLICATE_ZONE1_VALUE" for issue in duplicate)

    missing_zone2 = _parse(
        "\n".join(
            [
                POWER_HEADER,
                _row("威力彩", "3", "2026/01/01", "01,02,03,04,05,06"),
            ]
        )
    )[2]
    assert any(issue.code == "MISSING_ZONE2" for issue in missing_zone2)

    overlap = _parse(
        "\n".join(
            [
                POWER_HEADER,
                _row("威力彩", "4", "2026/01/01", "01,02,03,04,05,06", "06"),
            ]
        )
    )[2]
    assert not any(issue.code == "SPECIAL_NUMBER_OVERLAP" for issue in overlap)

    out_of_order = _parse(
        "\n".join(
            [
                POWER_HEADER,
                _row("威力彩", "5", "2026/01/01", "06,05,04,03,02,01", "08"),
            ]
        )
    )[2]
    assert any(issue.code == "SOURCE_ORDER_VIOLATION" for issue in out_of_order)


def test_daily539_and_biglotto_are_classified_from_content_and_validated() -> None:
    daily_member, daily_draws, daily_issues = _parse(
        "\n".join(
            [
                DAILY_HEADER,
                _row("今彩539", "1", "2026/01/01", "01,02,03,04,05"),
            ]
        )
    )
    assert daily_member.classification.value == DAILY_539
    assert len(daily_draws) == 1
    assert daily_issues == ()

    big_member, big_draws, big_issues = _parse(
        "\n".join(
            [
                BIG_HEADER,
                _row("大樂透", "1", "2026/01/01", "01,02,03,04,05,06", "07"),
            ]
        )
    )
    assert big_member.classification.value == BIG_LOTTO
    assert len(big_draws) == 1
    assert big_issues == ()

    overlap = _parse(
        "\n".join(
            [
                BIG_HEADER,
                _row("大樂透", "2", "2026/01/01", "01,02,03,04,05,06", "06"),
            ]
        )
    )[2]
    assert any(issue.code == "SPECIAL_NUMBER_OVERLAP" for issue in overlap)


def test_trailing_blank_header_is_reported_and_unknown_non_empty_data_is_not_dropped() -> None:
    document = "\n".join(
        [
            f"{POWER_HEADER},,VendorNote",
            _row("威力彩", "6", "2026/01/01", "01,02,03,04,05,06", "08") + ",,kept",
        ]
    )
    member, draws, issues = _parse(document)
    assert member.header_fields[-1] == "VendorNote"
    assert draws[0].raw_fields[-1] == "kept"
    assert any(issue.code == "UNKNOWN_NON_EMPTY_COLUMN" for issue in issues)


def test_deterministic_parse_shape_can_be_serialized_without_hidden_state() -> None:
    member, draws, issues = _parse(
        "\n".join(
            [
                POWER_HEADER,
                _row("威力彩", "7", "2026/01/01", "01,02,03,04,05,06", "08"),
            ]
        )
    )
    first = json.dumps(
        {
            "member": member.member_path,
            "draw": draws[0].draw_identity,
            "issues": [issue.code for issue in issues],
        },
        sort_keys=True,
    )
    second = json.dumps(
        {
            "member": member.member_path,
            "draw": draws[0].draw_identity,
            "issues": [issue.code for issue in issues],
        },
        sort_keys=True,
    )
    assert first == second
