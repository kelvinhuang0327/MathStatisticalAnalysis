from __future__ import annotations

import subprocess
from collections import Counter
from decimal import Decimal
from pathlib import Path

import pytest
from tools.export_b649_all_strategy_backtest_index import (
    ABOVE_RANDOM_DESCRIPTIVE,
    AT_RANDOM_DESCRIPTIVE,
    BELOW_RANDOM_DESCRIPTIVE,
    METRIC_UNAVAILABLE,
    NOT_COMPARABLE,
    B649Index,
    build_b649_index,
    classify_comparison,
)

from lottolab.application.biglotto_multi_ticket_records import (
    B649_HISTORY_WINDOWS,
    B649_PREFIX_COUNTS,
    B649_SUCCESS_CRITERIA,
)
from lottolab.infrastructure.biglotto_multi_ticket_record_reader import (
    PackagedB649MultiTicketRecordReader,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def b649_index(tmp_path_factory: pytest.TempPathFactory) -> B649Index:
    source_checkout = tmp_path_factory.mktemp("pinned-source") / "repo"
    subprocess.run(
        [
            "git",
            "-C",
            str(REPO_ROOT),
            "worktree",
            "add",
            "--detach",
            str(source_checkout),
            "e382ae5f361ea29214cf7780fc31c09bfec1981e",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    try:
        index = build_b649_index(source_checkout)
        assert index.summary["source_head"] == "e382ae5f361ea29214cf7780fc31c09bfec1981e"
        assert index.summary["source_tree"] == "b2419f540c62a576a6f9591397e1e2432a0b00f7"
        return index
    finally:
        subprocess.run(
            [
                "git",
                "-C",
                str(REPO_ROOT),
                "worktree",
                "remove",
                str(source_checkout),
            ],
            check=True,
            capture_output=True,
            text=True,
        )


def test_index_keeps_all_strategy_states_and_all_projection_dimensions(
    b649_index: B649Index,
) -> None:
    status_rows = b649_index.strategy_status_records
    metric_rows = b649_index.backtest_metrics_records

    assert len(status_rows) == 221
    assert len({row["strategy_id"] for row in status_rows}) == 221
    assert Counter(row["reproduction_status"] for row in status_rows) == {
        "BACKTESTED": 135,
        "CLOSED_UNEXECUTABLE": 74,
        "DUPLICATE_ALIAS": 12,
    }
    assert len(metric_rows) == 221 * 4 * 4 * 8
    assert len(
        {
            (row["strategy_id"], row["prefix_count"], row["window"], row["criterion"])
            for row in metric_rows
        }
    ) == len(metric_rows)
    assert {row["prefix_count"] for row in metric_rows} == set(B649_PREFIX_COUNTS)
    assert {row["window"] for row in metric_rows} == {
        window.value for window in B649_HISTORY_WINDOWS
    }
    assert {row["criterion"] for row in metric_rows} == {
        criterion.value for criterion in B649_SUCCESS_CRITERIA
    }


def test_metrics_availability_is_separate_from_performance_and_aliases(
    b649_index: B649Index,
) -> None:
    status_rows = b649_index.strategy_status_records
    availability = Counter(row["metrics_availability"] for row in status_rows)
    assert availability == {
        "AVAILABLE": 133,
        "UNAVAILABLE": 2,
        "NOT_APPLICABLE": 86,
    }

    aliases = [row for row in status_rows if row["reproduction_status"] == "DUPLICATE_ALIAS"]
    assert len(aliases) == 12
    assert all(row["duplicate_alias_target"] for row in aliases)
    unexecutable = [
        row for row in status_rows if row["reproduction_status"] == "CLOSED_UNEXECUTABLE"
    ]
    assert len(unexecutable) == 74
    assert all(row["why_not_runnable"] for row in unexecutable)

    unavailable = [row for row in status_rows if row["metrics_availability"] == "UNAVAILABLE"]
    assert len(unavailable) == 2
    assert all(row["metrics_unavailable_reason"] for row in unavailable)
    unavailable_ids = {row["strategy_id"] for row in unavailable}
    unavailable_metrics = [
        row
        for row in b649_index.backtest_metrics_records
        if row["strategy_id"] in unavailable_ids
    ]
    assert len(unavailable_metrics) == 2 * 128
    assert all(
        row["descriptive_comparison_classification"] == METRIC_UNAVAILABLE
        for row in unavailable_metrics
    )


def test_negative_and_positive_source_deltas_are_retained_with_provenance(
    b649_index: B649Index,
) -> None:
    rows = b649_index.backtest_metrics_records
    criterion_counts = Counter(row["descriptive_comparison_classification"] for row in rows)
    assert criterion_counts[ABOVE_RANDOM_DESCRIPTIVE] > 0
    assert criterion_counts[BELOW_RANDOM_DESCRIPTIVE] > 0
    assert all(
        row["random_baseline_rate_difference"] is None
        for row in rows
        if row["metrics_availability"] != "AVAILABLE"
        and row["reproduction_status"] == "BACKTESTED"
    )

    below_random = next(
        row
        for row in rows
        if row["descriptive_comparison_classification"] == BELOW_RANDOM_DESCRIPTIVE
    )
    assert Decimal(str(below_random["random_baseline_rate_difference"])) < 0
    assert below_random["report_sha256"]
    assert below_random["report_file_sha256"]
    assert below_random["catalog_sha256"] == b649_index.summary["catalog_sha256"]
    assert below_random["catalog_file_sha256"] == b649_index.summary["catalog_file_sha256"]

    source_records = PackagedB649MultiTicketRecordReader().read().records
    source_negative = next(
        record
        for record in source_records
        if record.random_baseline_rate_difference is not None
        and Decimal(record.random_baseline_rate_difference) < 0
    )
    indexed_source = next(
        row
        for row in rows
        if row["strategy_id"] == source_negative.strategy_id
        and row["prefix_count"] == source_negative.prefix_count
        and row["window"] == source_negative.window.value
        and row["criterion"] == source_negative.criterion.value
    )
    assert (
        indexed_source["random_baseline_rate_difference"]
        == source_negative.random_baseline_rate_difference
    )
    assert b649_index.summary["zero_delta_record_count"] == 0


def test_official_zero_over_zero_is_unavailable_but_raw_source_value_is_kept(
    b649_index: B649Index,
) -> None:
    rows = [
        row
        for row in b649_index.backtest_metrics_records
        if row["official_any_prize_count"] == 0 and row["successful_execution_count"] == 0
    ]
    assert rows
    assert all(row["official_any_prize_rate"] is None for row in rows)
    assert all(row["official_random_baseline_delta"] is None for row in rows)
    assert all(
        row["official_any_prize_rate_availability_reason"]
        == "ZERO_SUCCESSFUL_EXECUTION_COUNT"
        for row in rows
    )
    assert all(
        Decimal(str(row["official_any_prize_rate_source_value"])) == 0
        for row in rows
    )
    assert all(row["official_random_baseline_delta_source_value"] is not None for row in rows)
    assert all(
        row["official_any_prize_descriptive_classification"] == NOT_COMPARABLE
        for row in rows
    )

    official_zero_n = [
        row
        for row in b649_index.backtest_metrics_records
        if row["official_any_prize_count"] == 0
        and row["successful_execution_count"] not in (None, 0)
    ]
    assert official_zero_n
    assert all(
        row["official_any_prize_rate"] == row["official_any_prize_rate_source_value"]
        and Decimal(str(row["official_any_prize_rate"])) == 0
        for row in official_zero_n
    )

    criterion_zero_n = [
        row
        for row in b649_index.backtest_metrics_records
        if row["success_count"] == 0
        and row["effective_backtest_draw_count"] not in (None, 0)
    ]
    assert criterion_zero_n
    assert all(
        row["historical_success_rate"] == row["historical_success_rate_source_value"]
        and Decimal(str(row["historical_success_rate"])) == 0
        for row in criterion_zero_n
    )


def test_denominators_keep_zero_zero_unavailable_and_zero_over_n_valid() -> None:
    assert classify_comparison(
        "AVAILABLE",
        numerator=132,
        denominator=125,
        observed_rate="0.176000000000000000",
        random_baseline_rate="0.185568678357414570",
        source_delta="-0.009568678357414570",
    ) == BELOW_RANDOM_DESCRIPTIVE
    assert classify_comparison(
        "AVAILABLE",
        numerator=132,
        denominator=125,
        observed_rate="0.176000000000000000",
        random_baseline_rate="0.185568678357414570",
        source_delta="-0.009568678357414570",
        require_numerator_le_denominator=True,
    ) == NOT_COMPARABLE
    assert classify_comparison(
        "AVAILABLE",
        numerator=0,
        denominator=0,
        observed_rate=None,
        random_baseline_rate="0.1",
        source_delta=None,
    ) == NOT_COMPARABLE
    assert classify_comparison(
        "AVAILABLE",
        numerator=0,
        denominator=12,
        observed_rate="0.000000000000000000",
        random_baseline_rate="0.1",
        source_delta="-0.100000000000000000",
    ) == BELOW_RANDOM_DESCRIPTIVE
    assert classify_comparison(
        "AVAILABLE",
        numerator=1,
        denominator=12,
        observed_rate="0.1",
        random_baseline_rate="0.1",
        source_delta="0.000000000000000000",
    ) == AT_RANDOM_DESCRIPTIVE
    assert classify_comparison(
        "UNAVAILABLE",
        numerator=None,
        denominator=None,
        observed_rate=None,
        random_baseline_rate=None,
        source_delta=None,
    ) == METRIC_UNAVAILABLE
    assert classify_comparison(
        "AVAILABLE",
        numerator=None,
        denominator=None,
        observed_rate=None,
        random_baseline_rate=None,
        source_delta=None,
    ) == NOT_COMPARABLE


def test_summary_does_not_claim_recalculation_or_predictive_lift(
    b649_index: B649Index,
) -> None:
    assert b649_index.summary["ranking_recomputed"] is False
    assert b649_index.summary["historical_backtests_recomputed"] is False
    assert b649_index.summary["predictive_lift"] == "NOT ESTABLISHED"
    assert b649_index.summary["metrics_available_strategy_count"] == 133
    assert b649_index.summary["metrics_unavailable_strategy_count"] == 2
    assert b649_index.summary["source_report_count"] == 52
