"""Canonical draw CSV parsing remains fail-closed until lottery rules are proven."""

from __future__ import annotations

import hashlib
from datetime import date

import pytest

from lottolab.domain.draws import LotteryType
from lottolab.domain.ingestion import (
    DrawCsvParseResult,
    DrawImportErrorCode,
    LotteryRuleStatus,
)
from lottolab.infrastructure.imports.csv_draws import (
    MAX_CSV_BYTES,
    MAX_CSV_ROWS,
    PARSER_VERSION,
    SUPPORTED_LOTTERY_TYPES,
    parse_draw_csv,
)

HEADER = "lottery_type,draw_number,draw_date,main_numbers"


def error_codes(result: DrawCsvParseResult) -> list[DrawImportErrorCode]:
    return [error.code for error in result.errors]


def test_canonical_csv_normalizes_generic_values_but_stops_on_unknown_rules() -> None:
    content = (
        " lottery_type , DRAW_NUMBER , Draw_Date , MAIN_NUMBERS , SPECIAL_NUMBERS , "
        "SOURCE , Ignored Note\n"
        " big_lotto , 000123 , 2026-07-16 , 9|01|3 , 49 , =1+1 , ignored\n"
    )

    result = parse_draw_csv(content, filename="../../display-only.csv")

    assert result.source_filename == "../../display-only.csv"
    assert result.ignored_columns == ("ignored note",)
    assert result.total_rows == 1
    assert result.blank_rows == 0
    assert result.valid_rows == 0
    assert not result.is_valid
    assert error_codes(result) == [DrawImportErrorCode.RULE_CONTRACT_UNKNOWN]
    assert SUPPORTED_LOTTERY_TYPES == ()

    row = result.normalized_rows[0]
    assert row.lottery_type is LotteryType.BIG_LOTTO
    assert row.draw_number == "123"
    assert row.draw_date == date(2026, 7, 16)
    assert row.main_numbers == (1, 3, 9)
    assert row.special_numbers == (49,)
    assert row.source == "=1+1"
    assert row.rule_status is LotteryRuleStatus.UNKNOWN


@pytest.mark.parametrize(
    "content",
    [
        "\ufeff" + HEADER + "\nBIG_LOTTO,1,2026-07-16,1|2\n",
        b"\xef\xbb\xbf" + (HEADER + "\nBIG_LOTTO,1,2026-07-16,1|2\n").encode(),
    ],
)
def test_utf8_bom_is_accepted(content: str | bytes) -> None:
    result = parse_draw_csv(content)

    assert len(result.normalized_rows) == 1
    assert error_codes(result) == [DrawImportErrorCode.RULE_CONTRACT_UNKNOWN]


def test_optional_columns_may_be_absent() -> None:
    result = parse_draw_csv(HEADER + "\nBIG_LOTTO,1,2026-07-16,1|2\n")

    row = result.normalized_rows[0]
    assert row.special_numbers == ()
    assert row.source is None


def test_missing_required_columns_fail_the_document() -> None:
    result = parse_draw_csv("lottery_type,draw_number\nBIG_LOTTO,1\n")

    assert error_codes(result) == [
        DrawImportErrorCode.MISSING_REQUIRED_COLUMN,
        DrawImportErrorCode.MISSING_REQUIRED_COLUMN,
    ]
    assert [error.field for error in result.errors] == ["draw_date", "main_numbers"]
    assert result.normalized_rows == ()


def test_blank_csv_records_are_skipped_and_counted() -> None:
    content = HEADER + "\n\n,,,\nBIG_LOTTO,1,2026-07-16,1|2\n"

    result = parse_draw_csv(content)

    assert result.total_rows == 3
    assert result.blank_rows == 2
    assert len(result.normalized_rows) == 1


def test_equivalent_numeric_forms_have_the_same_record_hash() -> None:
    first = parse_draw_csv(HEADER + "\nBIG_LOTTO,0007,2026-07-16,09|1|3\n")
    second = parse_draw_csv(HEADER + "\nBIG_LOTTO,7,2026-07-16,3|9|01\n")

    assert first.content_sha256 != second.content_sha256
    assert first.normalized_rows[0].normalized_record_hash == (
        second.normalized_rows[0].normalized_record_hash
    )


def test_source_is_provenance_and_does_not_change_semantic_record_hash() -> None:
    header = HEADER + ",source"
    first = parse_draw_csv(header + "\nBIG_LOTTO,7,2026-07-16,1|3|9,source-a\n")
    second = parse_draw_csv(header + "\nBIG_LOTTO,7,2026-07-16,1|3|9,source-b\n")

    assert first.normalized_rows[0].source == "source-a"
    assert second.normalized_rows[0].source == "source-b"
    assert first.normalized_rows[0].normalized_record_hash == (
        second.normalized_rows[0].normalized_record_hash
    )


@pytest.mark.parametrize("value", ["2026/07/16", "2026-02-30", "20260716"])
def test_invalid_date_is_structured(value: str) -> None:
    result = parse_draw_csv(HEADER + f"\nBIG_LOTTO,1,{value},1|2\n")

    assert DrawImportErrorCode.INVALID_DRAW_DATE in error_codes(result)
    assert result.normalized_rows == ()


@pytest.mark.parametrize("value", ["1|x", "1|2.5", "1||2", "-1|2"])
def test_invalid_number_is_structured(value: str) -> None:
    result = parse_draw_csv(HEADER + f"\nBIG_LOTTO,1,2026-07-16,{value}\n")

    assert DrawImportErrorCode.INVALID_NUMBER in error_codes(result)
    assert result.normalized_rows == ()


@pytest.mark.parametrize(
    ("main_numbers", "special_numbers"),
    [("1|01", ""), ("1|2", "02")],
)
def test_duplicate_numbers_fail_after_numeric_normalization(
    main_numbers: str, special_numbers: str
) -> None:
    content = HEADER + ",special_numbers\n"
    content += f"BIG_LOTTO,1,2026-07-16,{main_numbers},{special_numbers}\n"

    result = parse_draw_csv(content)

    assert DrawImportErrorCode.DUPLICATE_NUMBER in error_codes(result)
    assert result.normalized_rows == ()


@pytest.mark.parametrize("lottery_type", ["DAILY_539", "POWER_LOTTO", "UNKNOWN"])
def test_unsupported_lottery_type_fails(lottery_type: str) -> None:
    result = parse_draw_csv(HEADER + f"\n{lottery_type},1,2026-07-16,1|2\n")

    assert error_codes(result) == [DrawImportErrorCode.UNSUPPORTED_LOTTERY_TYPE]
    assert result.normalized_rows == ()


def test_semantically_duplicate_csv_row_is_reported() -> None:
    content = HEADER + ",source\n"
    content += "BIG_LOTTO,001,2026-07-16,2|1,source-a\n"
    content += "BIG_LOTTO,1,2026-07-16,01|2,source-b\n"

    result = parse_draw_csv(content)

    assert result.duplicate_input_rows == 1
    assert result.conflicting_input_rows == 0
    duplicate_error = next(
        error for error in result.errors if error.code is DrawImportErrorCode.DUPLICATE_INPUT_ROW
    )
    assert duplicate_error.row_number == 3
    assert "row 2" in duplicate_error.message


def test_conflicting_same_draw_identity_is_reported() -> None:
    content = HEADER + "\nBIG_LOTTO,1,2026-07-16,1|2\nBIG_LOTTO,01,2026-07-16,1|3\n"

    result = parse_draw_csv(content)

    assert result.duplicate_input_rows == 0
    assert result.conflicting_input_rows == 1
    assert DrawImportErrorCode.CONFLICTING_INPUT_ROW in error_codes(result)


def test_row_limit_rejects_before_row_normalization() -> None:
    rows = "\n".join(
        f"BIG_LOTTO,{draw_number},2026-07-16,1" for draw_number in range(MAX_CSV_ROWS + 1)
    )

    result = parse_draw_csv(HEADER + "\n" + rows)

    assert result.total_rows == MAX_CSV_ROWS + 1
    assert error_codes(result) == [DrawImportErrorCode.ROW_LIMIT_EXCEEDED]
    assert result.normalized_rows == ()


def test_byte_limit_rejects_before_csv_processing() -> None:
    content = b"x" * (MAX_CSV_BYTES + 1)

    result = parse_draw_csv(content)

    assert error_codes(result) == [DrawImportErrorCode.FILE_TOO_LARGE]
    assert result.content_sha256 == hashlib.sha256(content).hexdigest()
    assert result.total_rows == 0


def test_content_sha_and_parser_version_are_deterministic() -> None:
    content = HEADER + "\nBIG_LOTTO,1,2026-07-16,1|2\n"

    first = parse_draw_csv(content)
    second = parse_draw_csv(content)

    assert first.content_sha256 == hashlib.sha256(content.encode()).hexdigest()
    assert first.content_sha256 == second.content_sha256
    assert first.parser_version == second.parser_version == PARSER_VERSION
    assert first == second


def test_invalid_utf8_bytes_fail_without_parsing() -> None:
    content = b"\xff\xfe"

    result = parse_draw_csv(content)

    assert error_codes(result) == [DrawImportErrorCode.INVALID_UTF8]
    assert result.content_sha256 == hashlib.sha256(content).hexdigest()
