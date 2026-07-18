from __future__ import annotations

from pathlib import Path

import pytest

from lottolab.domain.draws import LotteryType
from lottolab.evidence.models import DatasetProvenance, DatasetProvenanceKind
from lottolab.normalization import NormalizationOutcome, NormalizationParameters, normalize
from lottolab.normalization.synthetic_csv import EXPECTED_HEADER, MAX_SOURCE_BYTES

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = REPO_ROOT / "tests/fixtures/normalization/synthetic"


def _source(*records: str) -> bytes:
    return (EXPECTED_HEADER + "\n" + "\n".join(records) + "\n").encode("ascii")


def _normalize(source: bytes):
    return normalize(
        source,
        format_id="synthetic_draw_csv",
        format_version="1.0.0",
        parameters=NormalizationParameters(
            dataset_id="SYNTHETIC_BIGLOTTO_CSV_TEST",
            dataset_version="1.0.0",
            lottery_type=LotteryType.BIG_LOTTO,
        ),
        provenance=DatasetProvenance(
            kind=DatasetProvenanceKind.SYNTHETIC,
            declared_description="Synthetic parser test only.",
        ),
    )


REJECTION_FIXTURES = {
    "reject_bom.csv": "NRM_SRC_INVALID_BYTE_DOMAIN",
    "reject_crlf.csv": "NRM_SRC_INVALID_BYTE_DOMAIN",
    "reject_blank_row.csv": "NRM_SRC_BLANK_RECORD",
    "reject_bad_header.csv": "NRM_SRC_HEADER_MISMATCH",
    "reject_reordered_header.csv": "NRM_SRC_HEADER_MISMATCH",
    "reject_unknown_header.csv": "NRM_SRC_HEADER_MISMATCH",
    "reject_missing_field.csv": "NRM_SRC_FIELD_COUNT_MISMATCH",
    "reject_malformed_date.csv": "NRM_REC_DATE_LEXICAL_INVALID",
    "reject_impossible_date.csv": "NRM_REC_DATE_INVALID",
    "reject_leading_zero_integer.csv": "NRM_REC_INTEGER_LEXICAL_INVALID",
    "reject_invalid_integer.csv": "NRM_REC_INTEGER_LEXICAL_INVALID",
    "reject_range.csv": "NRM_RULE_NUMBER_OUT_OF_RANGE",
    "reject_duplicate_number.csv": "NRM_RULE_DUPLICATE_NUMBER",
    "reject_main_count.csv": "NRM_RULE_MAIN_COUNT_MISMATCH",
    "reject_special_count.csv": "NRM_RULE_SPECIAL_COUNT_MISMATCH",
    "reject_special_range.csv": "NRM_RULE_NUMBER_OUT_OF_RANGE",
    "reject_overlap.csv": "NRM_RULE_MAIN_SPECIAL_OVERLAP",
    "reject_duplicate_id.csv": "NRM_DUP_DRAW_ID",
    "reject_duplicate_sequence.csv": "NRM_DUP_SEQUENCE",
    "reject_identical_duplicate.csv": "NRM_DUP_DRAW_ID",
    "reject_conflicting_duplicate.csv": "NRM_DUP_RECORD_CONFLICT",
    "reject_sequence_gap.csv": "NRM_SEQ_GAP",
    "reject_date_regression.csv": "NRM_SEQ_DATE_REGRESSION",
    "reject_unsorted_numbers.csv": "NRM_RULE_NUMBER_ORDER_INVALID",
    "reject_quoted.csv": "NRM_SRC_QUOTING_FORBIDDEN",
}


@pytest.mark.parametrize("filename,expected_code", REJECTION_FIXTURES.items())
def test_committed_rejection_fixture_fails_closed(filename: str, expected_code: str) -> None:
    raw = (FIXTURES / filename).read_bytes()
    first = _normalize(raw)
    second = _normalize(raw)
    assert first == second
    assert first.outcome is NormalizationOutcome.NORMALIZATION_REJECTED_SOURCE
    assert first.snapshot is None and first.manifest is None
    assert expected_code in {finding.reason_code for finding in first.findings}
    assert first.findings == tuple(
        sorted(
            first.findings,
            key=lambda item: (item.source_record_ordinal, item.reason_code, item.field),
        )
    )
    for finding in first.findings:
        assert finding.message.isascii()
        assert "SYN-D" not in finding.message
        assert "Traceback" not in finding.message


@pytest.mark.parametrize(
    "bad_byte", [b"\x00", b"\t", b"\x7f", b"\x80", b"\xc3\xa9", b"\xff"]
)
def test_byte_domain_rejects_controls_and_non_ascii(bad_byte: bytes) -> None:
    raw = (FIXTURES / "minimal.csv").read_bytes().replace(b"SYN-D-0", b"SYN" + bad_byte + b"D-0")
    result = _normalize(raw)
    assert result.outcome is NormalizationOutcome.NORMALIZATION_REJECTED_SOURCE
    assert [finding.reason_code for finding in result.findings] == [
        "NRM_SRC_INVALID_BYTE_DOMAIN"
    ]


def test_exact_final_lf_rules() -> None:
    valid = (FIXTURES / "minimal.csv").read_bytes()
    missing = _normalize(valid[:-1])
    extra = _normalize(valid + b"\n")
    assert [finding.reason_code for finding in missing.findings] == [
        "NRM_SRC_FINAL_LF_REQUIRED"
    ]
    assert [finding.reason_code for finding in extra.findings] == ["NRM_SRC_EXTRA_FINAL_LF"]


def test_header_only_source_is_rejected() -> None:
    result = _normalize((EXPECTED_HEADER + "\n").encode("ascii"))
    assert result.outcome is NormalizationOutcome.NORMALIZATION_REJECTED_SOURCE
    assert result.findings[0].reason_code == "NRM_SRC_BLANK_RECORD"


def test_source_record_and_field_limits_are_enforced_before_conversion() -> None:
    too_large = _normalize(b"A" * (MAX_SOURCE_BYTES + 1))
    assert too_large.findings[0].reason_code == "NRM_SRC_TOO_LARGE"

    oversized_record = _normalize(_source(",".join(["A" * 120] * 5)))
    assert oversized_record.findings[0].reason_code == "NRM_SRC_RECORD_TOO_LARGE"

    oversized_field = _normalize(
        _source("A" * 129 + ",0,2020-01-01,1|2|3|4|5|6,7")
    )
    assert oversized_field.findings[0].reason_code == "NRM_SRC_FIELD_TOO_LARGE"

    line = "SYN-D-0,0,2020-01-01,1|2|3|4|5|6,7"
    too_many = _normalize(_source(*([line] * 10_001)))
    assert too_many.findings[0].reason_code == "NRM_SRC_RECORD_LIMIT_EXCEEDED"


@pytest.mark.parametrize("token", ["00", "01", "+1", "-1", "1_0", "1.0", "", "12345678901"])
def test_sequence_uses_closed_ascii_integer_lexical_form(token: str) -> None:
    result = _normalize(_source(f"SYN-D-0,{token},2020-01-01,1|2|3|4|5|6,7"))
    codes = {finding.reason_code for finding in result.findings}
    assert codes & {"NRM_REC_SEQUENCE_LEXICAL_INVALID", "NRM_REC_NUMERIC_TOKEN_TOO_LONG"}
    assert result.snapshot is None and result.manifest is None


@pytest.mark.parametrize("draw_id", ["", "lower", "-BAD", "A SPACE", "A" * 65])
def test_draw_id_uses_exact_closed_pattern(draw_id: str) -> None:
    result = _normalize(_source(f"{draw_id},0,2020-01-01,1|2|3|4|5|6,7"))
    assert "NRM_REC_DRAW_ID_INVALID" in {finding.reason_code for finding in result.findings}


def test_middle_row_omission_is_not_silently_resequenced() -> None:
    lines = (FIXTURES / "six_draw.csv").read_text(encoding="ascii").splitlines()
    mutated = ("\n".join([*lines[:3], *lines[4:]]) + "\n").encode("ascii")
    result = _normalize(mutated)
    codes = {finding.reason_code for finding in result.findings}
    assert "NRM_SEQ_ORDINAL_MISMATCH" in codes
    assert "NRM_SEQ_GAP" in codes
    assert result.snapshot is None and result.manifest is None


def test_reordered_rows_are_rejected_without_sorting() -> None:
    lines = (FIXTURES / "six_draw.csv").read_text(encoding="ascii").splitlines()
    mutated = ("\n".join([lines[0], lines[2], lines[1], *lines[3:]]) + "\n").encode(
        "ascii"
    )
    result = _normalize(mutated)
    assert result.outcome is NormalizationOutcome.NORMALIZATION_REJECTED_SOURCE
    assert "NRM_SEQ_ORDINAL_MISMATCH" in {
        finding.reason_code for finding in result.findings
    }


def test_duplicate_date_is_allowed_when_identity_and_order_are_valid() -> None:
    source = (FIXTURES / "six_draw.csv").read_bytes()
    result = normalize(
        source,
        format_id="synthetic_draw_csv",
        format_version="1.0.0",
        parameters=NormalizationParameters(
            dataset_id="SYNTHETIC_BIGLOTTO_NORMALIZATION_SIX_DRAW",
            dataset_version="1.0.0",
            lottery_type=LotteryType.BIG_LOTTO,
        ),
        provenance=DatasetProvenance(
            kind=DatasetProvenanceKind.SYNTHETIC,
            declared_description="Synthetic six-draw normalization fixture only.",
        ),
    )
    assert result.outcome is NormalizationOutcome.NORMALIZATION_PASS
    assert result.snapshot is not None
    assert result.snapshot.draws[1].draw_date == result.snapshot.draws[2].draw_date
