"""Unit tests for the closed draw-data integrity domain values."""

from __future__ import annotations

import dataclasses

import pytest

from lottolab.domain.draw_data_integrity import (
    DrawDataIntegrityFinding,
    DrawDataIntegrityFindingCode,
    DrawDataIntegrityReport,
    DrawDataIntegrityStatus,
    DrawDataLotterySummary,
    DrawDataTableCount,
)

_ZERO_FINDINGS = tuple(
    DrawDataIntegrityFinding(code=code, count=0) for code in DrawDataIntegrityFindingCode
)
_TABLE_COUNTS = (
    DrawDataTableCount(table_name="draws", row_count=2),
    DrawDataTableCount(table_name="ingestion_runs", row_count=1),
    DrawDataTableCount(table_name="ingestion_items", row_count=1),
)
_SUMMARY = DrawDataLotterySummary(
    lottery_type="BIG_LOTTO",
    draw_count=2,
    first_draw_number="1",
    first_draw_date="2026-01-01",
    last_draw_number="2",
    last_draw_date="2026-01-08",
)


def _findings_with(code: DrawDataIntegrityFindingCode, count: int) -> tuple[
    DrawDataIntegrityFinding, ...
]:
    return tuple(
        DrawDataIntegrityFinding(code=entry, count=count if entry is code else 0)
        for entry in DrawDataIntegrityFindingCode
    )


def test_closed_statuses_are_exactly_absent_healthy_unhealthy() -> None:
    assert {status.value for status in DrawDataIntegrityStatus} == {
        "ABSENT",
        "HEALTHY",
        "UNHEALTHY",
    }


def test_closed_finding_codes_are_exactly_the_six_required() -> None:
    assert {code.value for code in DrawDataIntegrityFindingCode} == {
        "SQLITE_QUICK_CHECK_FAILED",
        "FOREIGN_KEY_VIOLATION",
        "DUPLICATE_DRAW_IDENTITY",
        "INVALID_DRAW_NUMBER",
        "INVALID_NORMALIZED_RECORD_HASH",
        "INVALID_NUMBERS_JSON",
    }


def test_report_and_children_are_frozen() -> None:
    report = DrawDataIntegrityReport(
        status=DrawDataIntegrityStatus.ABSENT,
        schema_version=None,
        table_counts=(),
        lottery_summaries=(),
        findings=(),
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        report.status = DrawDataIntegrityStatus.HEALTHY  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        _SUMMARY.draw_count = 99  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        _TABLE_COUNTS[0].row_count = 99  # type: ignore[misc]


def test_report_collections_are_tuples() -> None:
    report = DrawDataIntegrityReport(
        status=DrawDataIntegrityStatus.HEALTHY,
        schema_version=1,
        table_counts=_TABLE_COUNTS,
        lottery_summaries=(_SUMMARY,),
        findings=_ZERO_FINDINGS,
    )
    assert isinstance(report.table_counts, tuple)
    assert isinstance(report.lottery_summaries, tuple)
    assert isinstance(report.findings, tuple)


def test_absent_report_carries_no_counts_summaries_or_findings() -> None:
    report = DrawDataIntegrityReport(
        status=DrawDataIntegrityStatus.ABSENT,
        schema_version=None,
        table_counts=(),
        lottery_summaries=(),
        findings=(),
    )
    assert report.status is DrawDataIntegrityStatus.ABSENT


def test_absent_report_rejects_a_schema_version() -> None:
    with pytest.raises(ValueError, match="ABSENT"):
        DrawDataIntegrityReport(
            status=DrawDataIntegrityStatus.ABSENT,
            schema_version=1,
            table_counts=(),
            lottery_summaries=(),
            findings=(),
        )


def test_absent_report_rejects_nonempty_table_counts() -> None:
    with pytest.raises(ValueError, match="ABSENT"):
        DrawDataIntegrityReport(
            status=DrawDataIntegrityStatus.ABSENT,
            schema_version=None,
            table_counts=_TABLE_COUNTS,
            lottery_summaries=(),
            findings=(),
        )


def test_healthy_report_requires_a_schema_version() -> None:
    with pytest.raises(ValueError, match="schema_version"):
        DrawDataIntegrityReport(
            status=DrawDataIntegrityStatus.HEALTHY,
            schema_version=None,
            table_counts=_TABLE_COUNTS,
            lottery_summaries=(),
            findings=_ZERO_FINDINGS,
        )


def test_table_counts_must_be_in_exact_required_order() -> None:
    reordered = (_TABLE_COUNTS[1], _TABLE_COUNTS[0], _TABLE_COUNTS[2])
    with pytest.raises(ValueError, match="exact order"):
        DrawDataIntegrityReport(
            status=DrawDataIntegrityStatus.HEALTHY,
            schema_version=1,
            table_counts=reordered,
            lottery_summaries=(),
            findings=_ZERO_FINDINGS,
        )


def test_table_counts_must_cover_all_three_required_tables() -> None:
    with pytest.raises(ValueError, match="exact order"):
        DrawDataIntegrityReport(
            status=DrawDataIntegrityStatus.HEALTHY,
            schema_version=1,
            table_counts=_TABLE_COUNTS[:2],
            lottery_summaries=(),
            findings=_ZERO_FINDINGS,
        )


def test_lottery_summaries_must_be_lexicographically_ordered() -> None:
    out_of_order = (
        DrawDataLotterySummary(
            lottery_type="POWER_LOTTO",
            draw_count=1,
            first_draw_number="1",
            first_draw_date="2026-01-01",
            last_draw_number="1",
            last_draw_date="2026-01-01",
        ),
        DrawDataLotterySummary(
            lottery_type="BIG_LOTTO",
            draw_count=1,
            first_draw_number="1",
            first_draw_date="2026-01-01",
            last_draw_number="1",
            last_draw_date="2026-01-01",
        ),
    )
    with pytest.raises(ValueError, match="lexicographically"):
        DrawDataIntegrityReport(
            status=DrawDataIntegrityStatus.HEALTHY,
            schema_version=1,
            table_counts=_TABLE_COUNTS,
            lottery_summaries=out_of_order,
            findings=_ZERO_FINDINGS,
        )


def test_lottery_summaries_must_not_repeat_a_lottery_type() -> None:
    duplicated = (_SUMMARY, _SUMMARY)
    with pytest.raises(ValueError, match="repeat"):
        DrawDataIntegrityReport(
            status=DrawDataIntegrityStatus.HEALTHY,
            schema_version=1,
            table_counts=_TABLE_COUNTS,
            lottery_summaries=duplicated,
            findings=_ZERO_FINDINGS,
        )


def test_findings_must_cover_every_closed_code_exactly_once() -> None:
    with pytest.raises(ValueError, match="every closed code"):
        DrawDataIntegrityReport(
            status=DrawDataIntegrityStatus.HEALTHY,
            schema_version=1,
            table_counts=_TABLE_COUNTS,
            lottery_summaries=(),
            findings=_ZERO_FINDINGS[:-1],
        )


def test_healthy_status_requires_all_findings_zero() -> None:
    nonzero = _findings_with(DrawDataIntegrityFindingCode.INVALID_DRAW_NUMBER, 1)
    with pytest.raises(ValueError, match="HEALTHY"):
        DrawDataIntegrityReport(
            status=DrawDataIntegrityStatus.HEALTHY,
            schema_version=1,
            table_counts=_TABLE_COUNTS,
            lottery_summaries=(),
            findings=nonzero,
        )


def test_unhealthy_status_requires_at_least_one_nonzero_finding() -> None:
    with pytest.raises(ValueError, match="UNHEALTHY"):
        DrawDataIntegrityReport(
            status=DrawDataIntegrityStatus.UNHEALTHY,
            schema_version=1,
            table_counts=_TABLE_COUNTS,
            lottery_summaries=(),
            findings=_ZERO_FINDINGS,
        )


def test_unhealthy_report_accepted_with_one_nonzero_finding() -> None:
    nonzero = _findings_with(DrawDataIntegrityFindingCode.FOREIGN_KEY_VIOLATION, 3)
    report = DrawDataIntegrityReport(
        status=DrawDataIntegrityStatus.UNHEALTHY,
        schema_version=1,
        table_counts=_TABLE_COUNTS,
        lottery_summaries=(),
        findings=nonzero,
    )
    assert report.status is DrawDataIntegrityStatus.UNHEALTHY


def test_finding_rejects_unknown_code() -> None:
    with pytest.raises(ValueError, match="unknown"):
        DrawDataIntegrityFinding(code="BOGUS_CODE", count=0)  # type: ignore[arg-type]


def test_finding_rejects_negative_count() -> None:
    with pytest.raises(ValueError, match="negative"):
        DrawDataIntegrityFinding(
            code=DrawDataIntegrityFindingCode.INVALID_DRAW_NUMBER, count=-1
        )


def test_table_count_rejects_unknown_table_name() -> None:
    with pytest.raises(ValueError, match="unknown"):
        DrawDataTableCount(table_name="strategies", row_count=0)


def test_table_count_rejects_negative_row_count() -> None:
    with pytest.raises(ValueError, match="negative"):
        DrawDataTableCount(table_name="draws", row_count=-1)


def test_lottery_summary_rejects_zero_draw_count() -> None:
    with pytest.raises(ValueError, match="draw_count"):
        DrawDataLotterySummary(
            lottery_type="BIG_LOTTO",
            draw_count=0,
            first_draw_number="1",
            first_draw_date="2026-01-01",
            last_draw_number="1",
            last_draw_date="2026-01-01",
        )
