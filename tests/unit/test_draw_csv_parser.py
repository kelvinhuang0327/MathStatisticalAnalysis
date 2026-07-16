"""Focused tests for canonical CSV parsing and authoritative rule enforcement."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import replace
from datetime import date
from typing import cast

import pytest

from lottolab.domain.draws import LotteryType
from lottolab.domain.ingestion import (
    DrawCsvParseResult,
    DrawImportErrorCode,
    LotteryRuleStatus,
)
from lottolab.domain.lottery_rules import BIG_LOTTO_RULE_CONTRACT, LotteryRuleContract
from lottolab.infrastructure.imports.csv_draws import (
    MAX_CSV_BYTES,
    MAX_CSV_ROWS,
    MAX_DRAW_NUMBER_LENGTH,
    PARSER_VERSION,
    SUPPORTED_LOTTERY_TYPES,
    parse_draw_csv,
)

HEADER = "lottery_type,draw_number,draw_date,main_numbers,special_numbers"
VALID_MAIN = "1|9|3|49|24|17"
VALID_ROW = f"BIG_LOTTO,000123,2026-07-16,{VALID_MAIN},7"


def error_codes(result: DrawCsvParseResult) -> list[DrawImportErrorCode]:
    return [error.code for error in result.errors]


def parse_big_lotto(
    *,
    main_numbers: str = VALID_MAIN,
    special_numbers: str = "7",
    draw_number: str = "000123",
    rule_contracts: Mapping[LotteryType, LotteryRuleContract] | None = None,
) -> DrawCsvParseResult:
    content = HEADER + "\n"
    content += (
        f"BIG_LOTTO,{draw_number},2026-07-16,{main_numbers},{special_numbers}\n"
    )
    if rule_contracts is None:
        return parse_draw_csv(content)
    return parse_draw_csv(content, rule_contracts=rule_contracts)


def test_valid_official_shape_is_normalized_and_supported() -> None:
    content = (
        " lottery_type , DRAW_NUMBER , Draw_Date , MAIN_NUMBERS , SPECIAL_NUMBERS , "
        "SOURCE , Ignored Note\n"
        " big_lotto , 000123 , 2026-07-16 , 9|01|3|49|24|17 , 7 , =1+1 , ignored\n"
    )

    result = parse_draw_csv(content, filename="../../display-only.csv")

    assert result.source_filename == "../../display-only.csv"
    assert result.ignored_columns == ("ignored note",)
    assert result.total_rows == 1
    assert result.blank_rows == 0
    assert result.valid_rows == 1
    assert result.is_valid
    assert result.errors == ()
    assert SUPPORTED_LOTTERY_TYPES == (LotteryType.BIG_LOTTO,)

    row = result.normalized_rows[0]
    assert row.lottery_type is LotteryType.BIG_LOTTO
    assert row.draw_number == "000123"
    assert row.draw_date == date(2026, 7, 16)
    assert row.main_numbers == (1, 3, 9, 17, 24, 49)
    assert row.special_numbers == (7,)
    assert row.source == "=1+1"
    assert row.rule_status is LotteryRuleStatus.PROVEN


@pytest.mark.parametrize(
    "content",
    [
        "\ufeff" + HEADER + "\n" + VALID_ROW + "\n",
        b"\xef\xbb\xbf" + (HEADER + "\n" + VALID_ROW + "\n").encode(),
    ],
)
def test_utf8_bom_is_accepted(content: str | bytes) -> None:
    result = parse_draw_csv(content)

    assert result.is_valid
    assert len(result.normalized_rows) == 1


def test_missing_required_special_number_follows_contract() -> None:
    result = parse_draw_csv(
        "lottery_type,draw_number,draw_date,main_numbers\n"
        f"BIG_LOTTO,1,2026-07-16,{VALID_MAIN}\n"
    )

    assert error_codes(result) == [DrawImportErrorCode.NUMBER_COUNT_MISMATCH]
    assert result.errors[0].field == "special_numbers"
    assert result.normalized_rows == ()


def test_missing_required_columns_fail_the_document() -> None:
    result = parse_draw_csv("lottery_type,draw_number\nBIG_LOTTO,1\n")

    assert error_codes(result) == [
        DrawImportErrorCode.MISSING_REQUIRED_COLUMN,
        DrawImportErrorCode.MISSING_REQUIRED_COLUMN,
    ]
    assert [error.field for error in result.errors] == ["draw_date", "main_numbers"]
    assert result.normalized_rows == ()


def test_blank_csv_records_are_skipped_and_counted() -> None:
    content = HEADER + "\n\n,,,,\n" + VALID_ROW + "\n"

    result = parse_draw_csv(content)

    assert result.total_rows == 3
    assert result.blank_rows == 2
    assert result.valid_rows == 1


def test_equivalent_number_forms_have_the_same_record_hash() -> None:
    first = parse_big_lotto(main_numbers="09|1|3|49|24|17")
    second = parse_big_lotto(main_numbers="3|9|01|17|49|24")

    assert first.content_sha256 != second.content_sha256
    assert first.normalized_rows[0].normalized_record_hash == (
        second.normalized_rows[0].normalized_record_hash
    )


def test_draw_number_leading_zeroes_are_preserved_in_identity_and_hash() -> None:
    first = parse_big_lotto(draw_number="0007")
    second = parse_big_lotto(draw_number="7")

    assert first.normalized_rows[0].draw_number == "0007"
    assert second.normalized_rows[0].draw_number == "7"
    assert first.normalized_rows[0].normalized_record_hash != (
        second.normalized_rows[0].normalized_record_hash
    )


def test_source_is_provenance_and_does_not_change_semantic_record_hash() -> None:
    header = HEADER + ",source"
    first = parse_draw_csv(header + "\n" + VALID_ROW + ",source-a\n")
    second = parse_draw_csv(header + "\n" + VALID_ROW + ",source-b\n")

    assert first.normalized_rows[0].source == "source-a"
    assert second.normalized_rows[0].source == "source-b"
    assert first.normalized_rows[0].normalized_record_hash == (
        second.normalized_rows[0].normalized_record_hash
    )


@pytest.mark.parametrize("value", ["2026/07/16", "2026-02-30", "20260716"])
def test_invalid_date_is_structured(value: str) -> None:
    content = HEADER + "\n"
    content += f"BIG_LOTTO,1,{value},{VALID_MAIN},7\n"

    result = parse_draw_csv(content)

    assert DrawImportErrorCode.INVALID_DRAW_DATE in error_codes(result)
    assert result.normalized_rows == ()


@pytest.mark.parametrize("value", ["1|x", "1|2.5", "1||2", "-1|2"])
def test_invalid_number_is_structured(value: str) -> None:
    result = parse_big_lotto(main_numbers=value)

    assert DrawImportErrorCode.INVALID_NUMBER in error_codes(result)
    assert result.normalized_rows == ()


@pytest.mark.parametrize("value", ["12A", "\uff11\uff12\uff13", "+123", "1 2"])
def test_non_ascii_digit_draw_number_fails(value: str) -> None:
    result = parse_big_lotto(draw_number=value)

    assert error_codes(result) == [DrawImportErrorCode.INVALID_DRAW_NUMBER]
    assert result.normalized_rows == ()


def test_draw_number_length_is_bounded() -> None:
    accepted = parse_big_lotto(draw_number="0" * MAX_DRAW_NUMBER_LENGTH)
    rejected = parse_big_lotto(draw_number="0" * (MAX_DRAW_NUMBER_LENGTH + 1))

    assert accepted.is_valid
    assert error_codes(rejected) == [DrawImportErrorCode.INVALID_DRAW_NUMBER]


@pytest.mark.parametrize("value", ["1|2|3|4|5", "1|2|3|4|5|6|8"])
def test_wrong_main_count_fails(value: str) -> None:
    result = parse_big_lotto(main_numbers=value)

    assert error_codes(result) == [DrawImportErrorCode.NUMBER_COUNT_MISMATCH]


@pytest.mark.parametrize("value", ["0|2|3|4|5|6", "1|2|3|4|5|50"])
def test_main_number_out_of_range_fails(value: str) -> None:
    result = parse_big_lotto(main_numbers=value)

    assert error_codes(result) == [DrawImportErrorCode.NUMBER_OUT_OF_RANGE]


def test_duplicate_main_number_fails_after_numeric_normalization() -> None:
    result = parse_big_lotto(main_numbers="1|01|3|4|5|6")

    assert error_codes(result) == [DrawImportErrorCode.DUPLICATE_NUMBER]


@pytest.mark.parametrize("value", ["", "7|8"])
def test_wrong_special_count_fails(value: str) -> None:
    result = parse_big_lotto(special_numbers=value)

    assert DrawImportErrorCode.NUMBER_COUNT_MISMATCH in error_codes(result)


@pytest.mark.parametrize("value", ["0", "50"])
def test_special_number_out_of_range_fails(value: str) -> None:
    result = parse_big_lotto(special_numbers=value)

    assert error_codes(result) == [DrawImportErrorCode.NUMBER_OUT_OF_RANGE]


def test_duplicate_special_number_fails_where_uniqueness_applies() -> None:
    result = parse_big_lotto(special_numbers="7|07")

    assert DrawImportErrorCode.DUPLICATE_NUMBER in error_codes(result)


def test_main_special_overlap_is_rejected() -> None:
    result = parse_big_lotto(special_numbers="9")

    assert error_codes(result) == [DrawImportErrorCode.MAIN_SPECIAL_OVERLAP]


@pytest.mark.parametrize("lottery_type", ["DAILY_539", "POWER_LOTTO", "UNKNOWN"])
def test_unsupported_lottery_type_fails(lottery_type: str) -> None:
    content = HEADER + "\n"
    content += f"{lottery_type},1,2026-07-16,{VALID_MAIN},7\n"

    result = parse_draw_csv(content)

    assert error_codes(result) == [DrawImportErrorCode.UNSUPPORTED_LOTTERY_TYPE]
    assert result.normalized_rows == ()


def test_missing_rule_contract_fails_closed() -> None:
    result = parse_big_lotto(rule_contracts={})

    assert error_codes(result) == [DrawImportErrorCode.RULE_CONTRACT_UNKNOWN]
    assert result.normalized_rows == ()


def test_incomplete_rule_contract_fails_closed() -> None:
    incomplete = cast(LotteryRuleContract, object())

    result = parse_big_lotto(rule_contracts={LotteryType.BIG_LOTTO: incomplete})

    assert error_codes(result) == [DrawImportErrorCode.RULE_CONTRACT_UNKNOWN]
    assert result.normalized_rows == ()


def test_malformed_real_rule_contract_fails_closed() -> None:
    malformed = replace(BIG_LOTTO_RULE_CONTRACT)
    object.__setattr__(malformed, "special_number_required", 0)

    result = parse_big_lotto(
        special_numbers="",
        rule_contracts={LotteryType.BIG_LOTTO: malformed},
    )

    assert error_codes(result) == [DrawImportErrorCode.RULE_CONTRACT_UNKNOWN]
    assert result.normalized_rows == ()


def test_semantically_duplicate_csv_row_is_reported() -> None:
    content = HEADER + ",source\n"
    content += f"BIG_LOTTO,001,2026-07-16,{VALID_MAIN},7,source-a\n"
    content += "BIG_LOTTO,001,2026-07-16,01|3|9|17|24|49,07,source-b\n"

    result = parse_draw_csv(content)

    assert result.duplicate_input_rows == 1
    assert result.conflicting_input_rows == 0
    duplicate_error = next(
        error for error in result.errors if error.code is DrawImportErrorCode.DUPLICATE_INPUT_ROW
    )
    assert duplicate_error.row_number == 3
    assert "row 2" in duplicate_error.message


def test_conflicting_same_draw_identity_is_reported() -> None:
    content = HEADER + "\n"
    content += f"BIG_LOTTO,01,2026-07-16,{VALID_MAIN},7\n"
    content += "BIG_LOTTO,01,2026-07-16,1|3|9|17|24|48,7\n"

    result = parse_draw_csv(content)

    assert result.duplicate_input_rows == 0
    assert result.conflicting_input_rows == 1
    assert DrawImportErrorCode.CONFLICTING_INPUT_ROW in error_codes(result)


def test_row_limit_rejects_before_row_normalization() -> None:
    rows = "\n".join(
        f"BIG_LOTTO,{draw_number},2026-07-16,{VALID_MAIN},7"
        for draw_number in range(MAX_CSV_ROWS + 1)
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


def test_ordering_hash_and_parser_version_are_deterministic() -> None:
    content = HEADER + "\n" + VALID_ROW + "\n"

    first = parse_draw_csv(content)
    second = parse_draw_csv(content)

    assert first.content_sha256 == hashlib.sha256(content.encode()).hexdigest()
    assert first.content_sha256 == second.content_sha256
    assert first.normalized_rows[0].main_numbers == (1, 3, 9, 17, 24, 49)
    assert first.normalized_rows[0].normalized_record_hash == (
        second.normalized_rows[0].normalized_record_hash
    )
    assert first.parser_version == second.parser_version == PARSER_VERSION
    assert first == second


def test_invalid_utf8_bytes_fail_without_parsing() -> None:
    content = b"\xff\xfe"

    result = parse_draw_csv(content)

    assert error_codes(result) == [DrawImportErrorCode.INVALID_UTF8]
    assert result.content_sha256 == hashlib.sha256(content).hexdigest()
