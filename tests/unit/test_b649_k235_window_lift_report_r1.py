from __future__ import annotations

import json
from datetime import date, timedelta
from fractions import Fraction
from pathlib import Path

import pytest
from tools.b649_k235_window_lift_report_r1 import INPUT_SCHEMA_VERSION
from tools.b649_k235_window_lift_report_r1 import main as cli_main

from lottolab.research.b649_k235_window_lift_report_r1 import (
    ZERO_OVERLAP_RANDOM_BASELINES,
    HistoricalDrawOutcome,
    K235WindowLiftError,
    K235WindowLiftReport,
    K235WindowMetric,
    PredictionStatus,
    StrategyTargetReplay,
    compare_k235_strategies,
    evaluate_k235_history,
    exact_portfolio_random_probability,
)


def test_batched_exact_count_matches_original_scalar_enumeration() -> None:
    from lottolab.research import b649_k235_window_lift_report_r1 as engine

    for tickets in (
        ((1, 2, 3, 4, 5, 6), (1, 7, 8, 9, 10, 11)),
        ((1, 2, 3, 4, 5, 6), (1, 7, 8, 9, 10, 11), (2, 7, 8, 12, 13, 14)),
        ((1, 2, 3, 4, 5, 6),) * 5,
        tuple(tuple(range(1 + i * 4, 7 + i * 4)) for i in range(5)),
    ):
        expected = engine._enumerate_portfolio_probability(tickets)  # pyright: ignore[reportPrivateUsage]
        actual = engine._batched_portfolio_probability(tickets)  # pyright: ignore[reportPrivateUsage]
        assert actual == expected
        assert exact_portfolio_random_probability(tickets) == expected


def test_native_adapter_does_not_slice_higher_cost_strategies() -> None:
    from lottolab.research.b649_k235_window_lift_report_r1 import evaluate_native_k235_history

    report = evaluate_native_k235_history(
        (_draw(0),), (StrategyTargetReplay("c", "1", _disjoint_tickets(5)),), {"c": 5}
    )
    assert [(row.strategy_id, row.k) for row in report.strategy_reports] == [("c", 5)]
    with pytest.raises(K235WindowLiftError, match="exactly K"):
        evaluate_native_k235_history(
            (_draw(0),), (StrategyTargetReplay("c", "1", _disjoint_tickets(5)),), {"c": 2}
        )


def _draw(
    index: int,
    main: tuple[int, ...] = (1, 2, 3, 4, 5, 6),
    special: int = 7,
) -> HistoricalDrawOutcome:
    return HistoricalDrawOutcome(
        draw_id=str(index + 1),
        draw_date=date(2025, 1, 1) + timedelta(days=index),
        winning_main_numbers=main,
        winning_special_number=special,
    )


def _disjoint_tickets(count: int) -> tuple[tuple[int, ...], ...]:
    return tuple(tuple(range(1 + index * 6, 7 + index * 6)) for index in range(count))


def _metric(
    report: K235WindowLiftReport, strategy_id: str, k: int, window: str
) -> K235WindowMetric:
    strategy_reports = report.strategy_reports
    strategy = next(
        row for row in strategy_reports if row.strategy_id == strategy_id and row.k == k
    )
    return next(row for row in strategy.windows if row.window == window)


def test_zero_overlap_baselines_and_overlapping_portfolio_are_exact() -> None:
    from lottolab.research.b649_official_any_prize_exact import evaluate_portfolio

    expected_percent = {2: 6.1724283504, 3: 9.2317509739, 5: 15.2966131173}
    for k in (2, 3, 5):
        tickets = _disjoint_tickets(k)
        assert exact_portfolio_random_probability(tickets) == ZERO_OVERLAP_RANDOM_BASELINES[k]
        reference_probability = evaluate_portfolio(tickets).official_any_prize
        assert reference_probability == ZERO_OVERLAP_RANDOM_BASELINES[k]
        assert round(float(reference_probability) * 100, 10) == expected_percent[k]

    overlapping = ((1, 2, 3, 4, 5, 6), (1, 7, 8, 9, 10, 11))
    actual = exact_portfolio_random_probability(overlapping)
    assert actual != ZERO_OVERLAP_RANDOM_BASELINES[2]

    assert actual == evaluate_portfolio(overlapping).official_any_prize


def test_mixed_overlap_geometry_uses_poisson_binomial_null() -> None:
    outcomes = (_draw(0), _draw(1))
    predictions = (
        StrategyTargetReplay("candidate", "1", _disjoint_tickets(2)),
        StrategyTargetReplay("candidate", "2", ((1, 2, 3, 4, 5, 6), (1, 7, 8, 9, 10, 11))),
    )

    report = evaluate_k235_history(outcomes, predictions)
    metric = _metric(report, "candidate", 2, "FULL")

    assert metric.denominator == 2
    assert dict(metric.random_probability_method_counts) == {
        "EXACT_OVERLAPPING_PORTFOLIO": 1,
        "ZERO_OVERLAP_REFERENCE": 1,
    }
    assert metric.statistical_result is not None
    assert metric.statistical_result.method == "POISSON_BINOMIAL_DP_FLOAT64"


def test_official_prize_resolver_counts_special_and_does_not_use_m1_plus() -> None:
    outcomes = (
        _draw(0),
        _draw(1, (20, 21, 22, 23, 24, 25), 26),
        _draw(2, (30, 31, 32, 36, 37, 38), 40),
    )
    predictions = (
        StrategyTargetReplay(
            "candidate",
            "1",
            ((1, 2, 7, 8, 9, 10), (8, 9, 10, 11, 12, 13)),
        ),
        StrategyTargetReplay(
            "candidate",
            "2",
            ((20, 26, 30, 31, 32, 33), (34, 35, 36, 37, 38, 39)),
        ),
        StrategyTargetReplay(
            "candidate",
            "3",
            ((30, 31, 32, 33, 34, 35), (1, 2, 3, 4, 5, 6)),
        ),
    )

    report = evaluate_k235_history(outcomes, predictions)
    metric = _metric(report, "candidate", 2, "FULL")
    results = next(
        row.target_results
        for row in report.strategy_reports
        if row.strategy_id == "candidate" and row.k == 2
    )

    assert metric.official_any_prize_success_count == 2
    assert metric.denominator == 3
    assert [row.official_any_prize for row in results] == [True, False, True]
    assert report.to_dict()["event_definition"] == (
        "OFFICIAL_ANY_PRIZE via resolve_big_lotto_prize_tier"
    )


def test_windows_count_target_periods_but_use_only_evaluable_denominators() -> None:
    outcomes = tuple(_draw(index) for index in range(60))
    tickets = _disjoint_tickets(2)
    predictions: list[StrategyTargetReplay] = []
    for index, outcome in enumerate(outcomes):
        if index == 59:
            continue
        if index == 58:
            predictions.append(
                StrategyTargetReplay(
                    "candidate", outcome.draw_id, None, PredictionStatus.FAILED, "EXECUTION_ERROR"
                )
            )
        elif index == 57:
            predictions.append(StrategyTargetReplay("candidate", outcome.draw_id, tickets[:1]))
        else:
            predictions.append(StrategyTargetReplay("candidate", outcome.draw_id, tickets))

    report = evaluate_k235_history(outcomes, predictions)
    full = _metric(report, "candidate", 2, "FULL")
    recent_50 = _metric(report, "candidate", 2, "RECENT_50")
    recent_300 = _metric(report, "candidate", 2, "RECENT_300")
    recent_1500 = _metric(report, "candidate", 2, "RECENT_1500")
    k5_full = _metric(report, "candidate", 5, "FULL")

    assert (full.target_period_count, full.denominator) == (60, 57)
    assert (full.missing_period_count, full.failed_period_count) == (1, 1)
    assert full.not_evaluable_period_count == 1
    assert (recent_50.target_period_count, recent_50.denominator) == (50, 47)
    assert (
        recent_50.missing_period_count,
        recent_50.failed_period_count,
        recent_50.not_evaluable_period_count,
    ) == (1, 1, 1)
    assert (recent_300.target_period_count, recent_300.denominator) == (60, 57)
    assert (recent_1500.target_period_count, recent_1500.denominator) == (60, 57)
    assert (
        k5_full.denominator,
        k5_full.not_evaluable_period_count,
        k5_full.missing_period_count,
        k5_full.failed_period_count,
    ) == (0, 58, 1, 1)
    assert k5_full.historical_win_rate is None
    assert k5_full.statistical_result is None


def test_recent_windows_roll_over_full_valid_history_for_each_k() -> None:
    outcomes = tuple(_draw(index) for index in range(1601))
    predictions = tuple(
        StrategyTargetReplay("candidate", outcome.draw_id, _disjoint_tickets(5))
        for outcome in outcomes
    )

    report = evaluate_k235_history(outcomes, predictions)
    expected = {
        "FULL": (1601, "1", "1601"),
        "RECENT_50": (50, "1552", "1601"),
        "RECENT_300": (300, "1302", "1601"),
        "RECENT_750": (750, "852", "1601"),
        "RECENT_1500": (1500, "102", "1601"),
    }
    for k in (2, 3, 5):
        for window, (count, first_draw_id, last_draw_id) in expected.items():
            metric = _metric(report, "candidate", k, window)
            assert (metric.target_period_count, metric.denominator) == (count, count)
            assert (metric.first_draw_id, metric.last_draw_id) == (first_draw_id, last_draw_id)


def test_paired_comparison_uses_only_shared_evaluable_draws() -> None:
    outcomes = tuple(_draw(index) for index in range(4))
    wins = _disjoint_tickets(2)
    losses = ((13, 14, 15, 16, 17, 18), (19, 20, 21, 22, 23, 24))
    predictions: list[StrategyTargetReplay] = []
    for index, outcome in enumerate(outcomes):
        if index != 0:
            predictions.append(
                StrategyTargetReplay(
                    "candidate", outcome.draw_id, wins if index in (1, 3) else losses
                )
            )
        predictions.append(
            StrategyTargetReplay("incumbent", outcome.draw_id, wins if index in (2, 3) else losses)
        )

    report = evaluate_k235_history(outcomes, predictions, incumbent_strategy_id="incumbent")
    paired = compare_k235_strategies(report, "candidate", "incumbent", k=2, window="FULL")

    assert paired.target_period_count == 4
    assert paired.common_evaluable_period_count == 3
    assert (paired.strategy_a_only_success_count, paired.strategy_b_only_success_count) == (1, 1)
    assert paired.paired_success_rate_difference == Fraction(0, 1)
    assert paired.mcnemar_exact_two_sided_p_value == 1.0
    assert paired.paired_difference_ci_method == "BONFERRONI_WILSON_95_PERCENT"
    assert len(report.incumbent_comparisons) == 3 * 5


def test_duplicate_prediction_and_out_of_order_targets_fail_closed() -> None:
    with pytest.raises(K235WindowLiftError, match="duplicate prediction"):
        evaluate_k235_history(
            (_draw(0),),
            (
                StrategyTargetReplay("candidate", "1", _disjoint_tickets(2)),
                StrategyTargetReplay("candidate", "1", _disjoint_tickets(2)),
            ),
        )

    with pytest.raises(K235WindowLiftError, match="ascending historical date order"):
        evaluate_k235_history(
            (_draw(1), _draw(0)),
            (StrategyTargetReplay("candidate", "2", _disjoint_tickets(2)),),
        )


def test_cli_reads_supplied_json_and_writes_report(tmp_path: Path) -> None:
    input_path = tmp_path / "input.json"
    output_path = tmp_path / "result.json"
    document = {
        "schema_version": INPUT_SCHEMA_VERSION,
        "draws": [
            {
                "draw_id": "1",
                "draw_date": "2025-01-01",
                "winning_main_numbers": [1, 2, 3, 4, 5, 6],
                "winning_special_number": 7,
            }
        ],
        "predictions": [
            {
                "strategy_id": "candidate",
                "draw_id": "1",
                "status": "OK",
                "native_tickets": [list(ticket) for ticket in _disjoint_tickets(2)],
            }
        ],
    }
    input_path.write_text(json.dumps(document), encoding="utf-8")

    assert cli_main(["--input", str(input_path), "--output", str(output_path)]) == 0

    result = json.loads(output_path.read_text(encoding="utf-8"))
    assert result["history_draw_count"] == 1
    k2_full = next(
        window
        for strategy in result["strategies"]
        if strategy["strategy_id"] == "candidate" and strategy["k"] == 2
        for window in strategy["windows"]
        if window["window"] == "FULL"
    )
    assert k2_full["denominator"] == 1
    assert k2_full["official_any_prize_success_count"] == 1
