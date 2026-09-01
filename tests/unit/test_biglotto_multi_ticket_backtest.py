"""Causal, same-portfolio prefix backtest tests."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, cast

import pytest
from typer.testing import CliRunner

from lottolab.application.biglotto_multi_ticket_backtest import (
    INPUT_SCHEMA_VERSION,
    MultiTicketBacktestInputError,
    evaluate_biglotto_exact_native_official_metrics,
    evaluate_biglotto_multi_ticket_backtest,
)
from lottolab.domain.biglotto_full_strategy_catalog import (
    ReproductionStatus,
    load_full_strategy_catalog,
)
from lottolab.interfaces.cli.biglotto_multi_ticket_backtest import (
    CHECKSUM_FILENAME,
    EXECUTION_AUDIT_CSV_FILENAME,
    METRICS_CSV_FILENAME,
    OFFICIAL_PRIZE_DISTRIBUTION_CSV_FILENAME,
    OFFICIAL_RANKINGS_CSV_FILENAME,
    OFFICIAL_REVIEW_FILENAME,
    OFFICIAL_STABILITY_CSV_FILENAME,
    OFFICIAL_TOP20_CSV_FILENAME,
    PRIZES_CSV_FILENAME,
    RANKINGS_CSV_FILENAME,
    REPORT_JSON_FILENAME,
    TOP10_CSV_FILENAME,
    UNIVERSE_CSV_FILENAME,
)
from lottolab.interfaces.cli.main import app

runner = CliRunner()


def _strategy_identity() -> tuple[str, str]:
    record = next(
        record
        for record in load_full_strategy_catalog().records
        if record.legacy_method_id
        == "tools/evolving_strategy_engine/evolution_engine.py"
    )
    return record.strategy_id, record.strategy_version


def _input_document() -> dict[str, object]:
    strategy_id, strategy_version = _strategy_identity()
    winning_ticket = [1, 2, 3, 4, 5, 6]
    ordered_portfolio = [winning_ticket for _ in range(20)]
    return {
        "dataset_id": "fixture-dataset",
        "dataset_sha256": "a" * 64,
        "dataset_version": "v1",
        "executions": [
            {
                "candidate_k": 12,
                "combination_count": 924,
                "history_cutoff_draw_date": "2020-01-01",
                "history_cutoff_draw_number": "99",
                "native_ticket_count": 2,
                "native_tickets": [winning_ticket, winning_ticket],
                "ordered_portfolio": ordered_portfolio,
                "portfolio_derivation": "test-constructor/v1",
                "portfolio_ticket_count": 20,
                "status": "OK",
                "strategy_id": strategy_id,
                "strategy_version": strategy_version,
                "target_draw_number": "100",
            },
            {
                "candidate_k": 12,
                "combination_count": 924,
                "history_cutoff_draw_date": "2020-01-02",
                "history_cutoff_draw_number": "100",
                "native_ticket_count": 2,
                "native_tickets": [winning_ticket, winning_ticket],
                "ordered_portfolio": ordered_portfolio,
                "portfolio_derivation": "test-constructor/v1",
                "portfolio_ticket_count": 20,
                "status": "OK",
                "strategy_id": strategy_id,
                "strategy_version": strategy_version,
                "target_draw_number": "101",
            },
        ],
        "lottery_type": "BIG_LOTTO",
        "schema_version": INPUT_SCHEMA_VERSION,
        "targets": [
            {
                "draw_date": "2020-01-02",
                "draw_number": "100",
                "winning_main_numbers": winning_ticket,
                "winning_special_number": 7,
            },
            {
                "draw_date": "2020-01-03",
                "draw_number": "101",
                "winning_main_numbers": [10, 11, 12, 13, 14, 15],
                "winning_special_number": 16,
            },
        ],
    }


def _input_bytes(document: dict[str, object] | None = None) -> bytes:
    return json.dumps(
        document or _input_document(),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


@pytest.fixture(scope="module")
def report() -> dict[str, object]:
    return evaluate_biglotto_multi_ticket_backtest(_input_bytes())


def test_report_uses_all_four_prefixes_windows_and_eight_criteria(
    report: dict[str, object],
) -> None:
    metrics = cast(list[dict[str, Any]], report["metrics"])
    rankings = cast(list[dict[str, Any]], report["rankings"])
    top_10 = cast(list[dict[str, Any]], report["top_10"])

    assert len(metrics) == 4 * 4 * 8
    assert {metric["prefix_count"] for metric in metrics} == {5, 10, 15, 20}
    assert {metric["window"] for metric in metrics} == {
        "FULL",
        "RECENT_750",
        "RECENT_300",
        "RECENT_50",
    }
    assert len({metric["criterion"] for metric in metrics}) == 8
    assert len(rankings) == 4 * 4 * 8 * 221
    assert len(top_10) == 4 * 4 * 8
    assert all(len(metric["execution_status_counts"]) >= 1 for metric in metrics)


def test_report_exposes_official_primary_metrics_and_isolates_ticket_windows(
    report: dict[str, object],
) -> None:
    official_metrics = cast(list[dict[str, Any]], report["official_metrics"])
    official_rankings = cast(list[dict[str, Any]], report["official_rankings"])
    official_top_20 = cast(list[dict[str, Any]], report["official_top_20"])

    assert len(official_metrics) == 4 * 4
    assert len(official_rankings) == 4 * 4 * 221
    assert {row["criterion"] for row in official_rankings} == {
        "OFFICIAL_ANY_PRIZE"
    }
    assert all(
        len(
            [
                row
                for row in official_rankings
                if row["prefix_count"] == prefix_count
                and row["window"] == window
            ]
        )
        == 221
        for prefix_count in (5, 10, 15, 20)
        for window in ("FULL", "RECENT_750", "RECENT_300", "RECENT_50")
    )
    assert len(official_top_20) == 4 * 4

    metric = next(
        row
        for row in official_metrics
        if row["prefix_count"] == 5 and row["window"] == "FULL"
    )
    assert metric["official_any_prize_count"] == 1
    assert metric["official_any_prize_rate"] == {
        "decimal_18": "0.500000000000000000",
        "denominator": 2,
        "numerator": 1,
    }
    assert metric["official_random_baseline_probability"]["numerator"] > 0
    assert metric["official_random_baseline_delta"]["numerator"] > 0


def test_exact_native_metrics_score_only_the_two_native_ticket_positions() -> None:
    exact_report = evaluate_biglotto_exact_native_official_metrics(_input_bytes())
    records = cast(list[dict[str, Any]], exact_report["records"])
    k2_full = next(
        row
        for row in records
        if row["ticket_count"] == 2 and row["window"] == "FULL"
    )
    k3_full = next(
        row
        for row in records
        if row["ticket_count"] == 3 and row["window"] == "FULL"
    )

    assert k2_full["metric_status"] == "AVAILABLE"
    assert k2_full["available_observation_count"] == 2
    assert k2_full["ticket_position_count"] == 4
    assert k2_full["official_any_prize_count"] == 1
    assert k2_full["official_any_prize_rate"] == {
        "decimal_18": "0.500000000000000000",
        "denominator": 2,
        "numerator": 1,
    }
    assert k2_full["official_prize_tier_counts"]["FIRST"] == 2
    assert k2_full["no_prize_count"] == 2
    assert k3_full["metric_status"] == "UNAVAILABLE"
    assert k3_full["unavailable_reason"] == "NATIVE_TICKET_COUNT_MISMATCH"
    assert k3_full["official_any_prize_count"] is None
    assert k3_full["official_any_prize_rate"] is None


def test_variable_native_cardinality_is_typed_unavailable_not_partially_scored() -> None:
    document = _input_document()
    executions = cast(list[dict[str, object]], document["executions"])
    native_tickets = cast(list[object], executions[1]["native_tickets"])
    executions[1]["native_tickets"] = [*native_tickets, native_tickets[0]]
    executions[1]["native_ticket_count"] = 3

    exact_report = evaluate_biglotto_exact_native_official_metrics(
        _input_bytes(document)
    )
    records = cast(list[dict[str, Any]], exact_report["records"])

    assert len(records) == 8
    assert {row["metric_status"] for row in records} == {"UNAVAILABLE"}
    assert {
        row["native_ticket_count_classification"] for row in records
    } == {"VARIABLE_NATIVE_TICKET_COUNT"}
    assert {row["unavailable_reason"] for row in records} == {
        "VARIABLE_NATIVE_TICKET_COUNT"
    }
    assert all(row["official_any_prize_count"] is None for row in records)
    assert all(row["official_any_prize_rate"] is None for row in records)


def test_two_main_plus_special_is_official_success_but_not_m3_plus() -> None:
    document = _input_document()
    two_main_plus_special = [1, 2, 7, 10, 11, 12]
    targets = cast(list[dict[str, object]], document["targets"])
    targets[1]["winning_main_numbers"] = [20, 21, 22, 23, 24, 25]
    targets[1]["winning_special_number"] = 26
    for execution in cast(list[dict[str, object]], document["executions"]):
        execution["native_tickets"] = [two_main_plus_special, two_main_plus_special]
        execution["ordered_portfolio"] = [two_main_plus_special for _ in range(20)]

    report = evaluate_biglotto_multi_ticket_backtest(_input_bytes(document))
    metrics = cast(list[dict[str, Any]], report["metrics"])
    official_metrics = cast(list[dict[str, Any]], report["official_metrics"])
    m3 = next(
        row
        for row in metrics
        if row["prefix_count"] == 5
        and row["window"] == "FULL"
        and row["criterion"] == "M3_PLUS"
    )
    official = next(
        row
        for row in official_metrics
        if row["prefix_count"] == 5 and row["window"] == "FULL"
    )

    assert m3["observed_success_count"] == 0
    assert official["official_any_prize_count"] == 1


def test_complete_ranking_retains_closed_strategies_and_reasons(
    report: dict[str, object],
) -> None:
    catalog = load_full_strategy_catalog()
    closed_ids = {
        record.strategy_id
        for record in catalog.records
        if record.reproduction_status is ReproductionStatus.CLOSED_UNEXECUTABLE
    }
    universe = cast(list[dict[str, Any]], report["universe"])
    rankings = cast(list[dict[str, Any]], report["rankings"])
    closed_universe = [row for row in universe if row["strategy_id"] in closed_ids]
    one_ranking_cell = [
        row
        for row in rankings
        if row["strategy_id"] in closed_ids
        and row["prefix_count"] == 5
        and row["window"] == "FULL"
        and row["criterion"] == "M6"
    ]

    assert len(closed_universe) == len(closed_ids) == 74
    assert all(row["reproduction_status"] == "CLOSED_UNEXECUTABLE" for row in closed_universe)
    assert len(one_ranking_cell) == 74
    assert all(row["rank"] == "" for row in one_ranking_cell)
    assert all(
        cast(str, row["unranked_reason"]).startswith("CLOSED_UNEXECUTABLE:")
        for row in one_ranking_cell
    )


def test_prefixes_come_from_one_ordered_20_and_preserve_duplicate_audit(
    report: dict[str, object],
) -> None:
    audit = cast(list[dict[str, Any]], report["execution_audit"])
    contract = cast(dict[str, Any], report["portfolio_contract"])

    assert contract == {
        "candidate_k_is_ticket_count": False,
        "combination_count_is_ticket_count": False,
        "prefix_counts": [5, 10, 15, 20],
        "same_ordered_20_portfolio_for_every_prefix": True,
    }
    assert len(audit) == 2
    assert audit[0]["candidate_k"] == 12
    assert audit[0]["combination_count"] == 924
    assert audit[0]["native_ticket_count"] == 2
    assert audit[0]["native_duplicate_ticket_count"] == 1
    assert audit[0]["portfolio_ticket_count"] == 20
    assert audit[0]["portfolio_duplicate_ticket_count"] == 19
    expected = json.dumps(
        [[1, 2, 3, 4, 5, 6]] * 20,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    assert audit[0]["ordered_portfolio_sha256"] == hashlib.sha256(expected).hexdigest()


def test_exact_baseline_prizes_coverage_and_progress_are_reported(
    report: dict[str, object],
) -> None:
    metrics = cast(list[dict[str, Any]], report["metrics"])
    metric = next(
        item
        for item in metrics
        if item["prefix_count"] == 5 and item["window"] == "FULL" and item["criterion"] == "M6"
    )
    prizes = cast(list[dict[str, Any]], report["official_prize_distributions"])
    prize = next(item for item in prizes if item["prefix_count"] == 5 and item["window"] == "FULL")

    assert metric["observed_success_count"] == 1
    assert metric["observed_success_rate"] == {
        "decimal_18": "0.500000000000000000",
        "denominator": 2,
        "numerator": 1,
    }
    assert metric["coverage"]["numerator"] == 1
    assert metric["coverage"]["denominator"] == 1
    assert metric["exact_random_baseline_probability"]["numerator"] > 0
    assert metric["random_baseline_rate_difference"]["numerator"] > 0
    assert prize["official_prize_tier_counts"]["FIRST"] == 5
    assert prize["no_prize_count"] == 5
    assert prize["observed_duplicate_ticket_count"] == 8
    assert report["progress"] == {
        "backtested_count": 135,
        "closed_count": 74,
        "duplicate_alias_count": 12,
        "owner_decision_required_count": 0,
        "reproduced_count": 135,
        "total_strategy_count": 221,
        "uncompleted_count": 0,
    }
    assert "do not guarantee future prizes" in cast(str, report["research_disclaimer"])


def test_noncausal_cutoff_is_rejected() -> None:
    document = _input_document()
    executions = cast(list[dict[str, object]], document["executions"])
    executions[0]["history_cutoff_draw_date"] = "2020-01-02"

    with pytest.raises(MultiTicketBacktestInputError, match="not strictly before"):
        evaluate_biglotto_multi_ticket_backtest(_input_bytes(document))


def test_native_generation_cutoff_must_match_execution() -> None:
    document = _input_document()
    executions = cast(list[dict[str, object]], document["executions"])
    executions[0]["native_generation"] = {
        "candidate_k": None,
        "combination_count": None,
        "history_cutoff_draw_number": "98",
        "history_draw_count": 10,
        "history_first_draw_number": "1",
        "legacy_method_id": "fixture",
        "native_ticket_count": 2,
        "native_ticket_order": "SOURCE_ORDER",
        "protocol": "fixture/v1",
        "replicate_id": 0,
        "seed_digest": "b" * 64,
        "seed_material": "fixture",
        "source_history_order": "OLDEST_FIRST",
        "source_sha256": "c" * 64,
        "target_draw_number": "100",
    }

    with pytest.raises(MultiTicketBacktestInputError, match="cutoff contradicts"):
        evaluate_biglotto_multi_ticket_backtest(_input_bytes(document))


def test_portfolio_must_have_exactly_twenty_positions() -> None:
    document = _input_document()
    executions = cast(list[dict[str, object]], document["executions"])
    executions[0]["ordered_portfolio"] = cast(list[object], executions[0]["ordered_portfolio"])[:19]

    with pytest.raises(MultiTicketBacktestInputError, match="exactly 20"):
        evaluate_biglotto_multi_ticket_backtest(_input_bytes(document))


def test_closed_result_semantics_are_explicit_and_carry_no_tickets() -> None:
    document = _input_document()
    strategy_id, strategy_version = _strategy_identity()
    document["executions"] = [
        {
            "reason_code": "AVAILABLE_HISTORY_BELOW_MINIMUM",
            "status": "CLOSED_INSUFFICIENT_HISTORY",
            "strategy_id": strategy_id,
            "strategy_version": strategy_version,
            "target_draw_number": "100",
        }
    ]

    closed_report = evaluate_biglotto_multi_ticket_backtest(_input_bytes(document))
    audit = cast(list[dict[str, Any]], closed_report["execution_audit"])
    assert audit == [
        {
            "history_cutoff_draw_date": "",
            "history_cutoff_draw_number": "",
            "reason_code": "AVAILABLE_HISTORY_BELOW_MINIMUM",
            "status": "CLOSED_INSUFFICIENT_HISTORY",
            "strategy_id": strategy_id,
            "strategy_version": strategy_version,
            "target_draw_number": "100",
        }
    ]
    assert closed_report["progress"] == load_full_strategy_catalog().progress.canonical_dict()


def test_cli_exports_json_csv_and_checksums(tmp_path: Path) -> None:
    input_file = tmp_path / "input.json"
    output = tmp_path / "output"
    input_file.write_bytes(_input_bytes())

    result = runner.invoke(
        app,
        [
            "backtest-biglotto-portfolios",
            "--input-file",
            str(input_file),
            "--output-directory",
            str(output),
        ],
    )

    assert result.exit_code == 0
    summary = json.loads(result.stdout)
    assert summary["total_strategy_count"] == 221
    assert summary["backtested_count"] == 135
    assert summary["closed_count"] == 74
    expected_files = {
        REPORT_JSON_FILENAME,
        UNIVERSE_CSV_FILENAME,
        EXECUTION_AUDIT_CSV_FILENAME,
        METRICS_CSV_FILENAME,
        PRIZES_CSV_FILENAME,
        RANKINGS_CSV_FILENAME,
        TOP10_CSV_FILENAME,
        OFFICIAL_RANKINGS_CSV_FILENAME,
        OFFICIAL_TOP20_CSV_FILENAME,
        OFFICIAL_PRIZE_DISTRIBUTION_CSV_FILENAME,
        OFFICIAL_STABILITY_CSV_FILENAME,
        OFFICIAL_REVIEW_FILENAME,
    }
    checksums = {
        filename: digest
        for line in (output / CHECKSUM_FILENAME).read_text(encoding="ascii").splitlines()
        for digest, filename in (line.split("  ", maxsplit=1),)
    }
    assert set(checksums) == expected_files
    for filename, digest in checksums.items():
        assert hashlib.sha256((output / filename).read_bytes()).hexdigest() == digest
