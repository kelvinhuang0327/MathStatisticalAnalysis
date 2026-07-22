from __future__ import annotations

from dataclasses import replace
from typing import Any, cast

import pytest
from tests.fixtures.historical.prefix_analytics_builder import (
    build_descriptor,
    build_draw,
    build_portfolio,
    build_run_import,
)

from lottolab.domain.historical_prefix_analytics import (
    HISTORICAL_ONLY_DISCLAIMER_ID,
    RANKING_POLICY_ID,
    SUPPORTED_PREFIX_COUNTS,
    ExactRatio,
    HistoricalPrefixAnalyticsInputError,
    HistoricalPrefixSummaryStatus,
    analyze_historical_prefixes,
)
from lottolab.domain.historical_results import (
    HistoricalIdentityKind,
    HistoricalLotteryType,
)
from lottolab.domain.lottery_rules import BigLottoPrizeTierId


def _metric(result: Any, *, strategy_id: str = "strategy_a", prefix: int) -> Any:
    return next(
        metric
        for metric in result.per_draw_metrics
        if metric.identity.strategy_id == strategy_id and metric.prefix_count == prefix
    )


def _summary(result: Any, *, strategy_id: str, prefix: int, replicate: int = 1) -> Any:
    return next(
        summary
        for summary in result.all_strategy_summaries
        if summary.identity.strategy_id == strategy_id
        and summary.identity.replicate == replicate
        and summary.prefix_count == prefix
    )


def test_prefixes_are_exact_source_order_slices_without_outcome_selection() -> None:
    hits = [0] * 20
    hits[9] = 3
    hits[10] = 4
    hits[14] = 5
    hits[15] = 5
    hits[19] = 6
    result = analyze_historical_prefixes(
        build_run_import(portfolios=(build_portfolio(hit_counts=hits),))
    )

    for prefix in SUPPORTED_PREFIX_COUNTS:
        metric = _metric(result, prefix=prefix)
        assert metric.included_ticket_positions == tuple(range(1, prefix + 1))
        assert metric.prefix_ticket_count == prefix
    assert _metric(result, prefix=5).best_single_main_hit_count == 0
    assert _metric(result, prefix=10).best_single_ticket_position == 10
    assert _metric(result, prefix=15).best_single_ticket_position == 15
    assert _metric(result, prefix=20).best_single_ticket_position == 20


@pytest.mark.parametrize(
    "portfolio",
    [
        build_portfolio(hit_counts=(0,) * 19),
        build_portfolio(hit_counts=(0,) * 21),
        build_portfolio(positions=(*range(1, 20), 19)),
        build_portfolio(positions=(*range(1, 20), 21)),
        build_portfolio(positions=(2, 1, *range(3, 21))),
    ],
)
def test_malformed_ticket_count_or_position_fails_closed(portfolio: Any) -> None:
    with pytest.raises(HistoricalPrefixAnalyticsInputError):
        analyze_historical_prefixes(build_run_import(portfolios=(portfolio,)))


def test_per_draw_metrics_reuse_all_official_prize_tiers() -> None:
    hits = (6, 5, 5, 4, 4, 3, 2, 3, 1, 0, *(0 for _ in range(10)))
    specials = (False, True, False, True, False, True, True, False, True, False) + (False,) * 10
    result = analyze_historical_prefixes(
        build_run_import(portfolios=(build_portfolio(hit_counts=hits, special_hits=specials),))
    )
    metric = _metric(result, prefix=20)

    assert metric.best_single_main_hit_count == 6
    assert metric.best_single_ticket_position == 1
    assert metric.total_main_hit_count == sum(hits)
    assert metric.portfolio_success is True
    assert (metric.m3plus, metric.m4plus, metric.m5plus, metric.m6) == (True, True, True, True)
    assert metric.special_hit is True
    assert metric.special_hit_ticket_count == 5
    assert metric.winning_ticket_count == 8
    assert metric.no_prize_ticket_count == 12
    assert metric.first_prize_ticket_count == 1
    assert metric.second_prize_ticket_count == 1
    assert metric.third_prize_ticket_count == 1
    assert metric.fourth_prize_ticket_count == 1
    assert metric.fifth_prize_ticket_count == 1
    assert metric.sixth_prize_ticket_count == 1
    assert metric.seventh_prize_ticket_count == 1
    assert metric.general_prize_ticket_count == 1
    assert metric.strongest_winning_tier is BigLottoPrizeTierId.FIRST


def test_portfolio_success_threshold_is_one_main_number_hit() -> None:
    result = analyze_historical_prefixes(
        build_run_import(
            portfolios=(build_portfolio(hit_counts=(1,) + (0,) * 19),),
        )
    )
    metric = _metric(result, prefix=1)
    assert metric.portfolio_success is True
    assert metric.m3plus is False


def test_summaries_use_exact_ratios_and_deterministic_numeric_max_target() -> None:
    descriptor = build_descriptor()
    portfolios = (
        build_portfolio(target_draw_number=9, cutoff_draw_number=1, hit_counts=(4, 1) + (0,) * 18),
        build_portfolio(target_draw_number=10, cutoff_draw_number=1, hit_counts=(4, 2) + (0,) * 18),
        build_portfolio(target_draw_number=11, cutoff_draw_number=1, hit_counts=(0,) * 20),
    )
    draws = (
        build_draw(1, draw_date="2025-12-31"),
        build_draw(9, draw_date="2026-01-02"),
        build_draw(10, draw_date="2026-01-02"),
        build_draw(11, draw_date="2026-01-03"),
    )
    result = analyze_historical_prefixes(
        build_run_import(descriptors=(descriptor,), draws=draws, portfolios=portfolios)
    )
    summary = _summary(result, strategy_id="strategy_a", prefix=2)

    assert summary.status is HistoricalPrefixSummaryStatus.ANALYZED
    assert summary.distinct_draw_count == 3
    assert summary.replay_ticket_count == 6
    assert summary.portfolio_success_rate == ExactRatio(2, 3)
    assert summary.average_best_main_hit_count == ExactRatio(8, 3)
    assert summary.average_total_main_hit_count == ExactRatio(11, 3)
    assert summary.max_hit_target is not None
    assert summary.max_hit_target.draw_number == 10


def test_max_target_draw_number_tie_break_is_numeric_not_lexicographic() -> None:
    portfolios = (
        build_portfolio(target_draw_number=9, cutoff_draw_number=1, hit_counts=(2,) + (0,) * 19),
        build_portfolio(target_draw_number=10, cutoff_draw_number=1, hit_counts=(2,) + (0,) * 19),
    )
    draws = (
        build_draw(1, draw_date="2025-12-31"),
        build_draw(9, draw_date="2026-01-02"),
        build_draw(10, draw_date="2026-01-02"),
    )
    result = analyze_historical_prefixes(build_run_import(draws=draws, portfolios=portfolios))
    summary = _summary(result, strategy_id="strategy_a", prefix=1)
    assert summary.max_hit_target is not None
    assert summary.max_hit_target.draw_number == 9


def test_every_descriptor_alias_replicate_synthetic_and_zero_portfolio_remains_visible() -> None:
    descriptors = (
        build_descriptor("base", replicate=1),
        build_descriptor("base", replicate=2),
        build_descriptor("alias", alias_of_strategy_id="base"),
        build_descriptor("zero"),
        build_descriptor("SYNTHETIC_X", identity_kind=HistoricalIdentityKind.SYNTHETIC_TEST_ONLY),
    )
    portfolios = (
        build_portfolio("base", replicate=1),
        build_portfolio("base", replicate=2),
        build_portfolio("alias"),
        build_portfolio("SYNTHETIC_X"),
    )
    result = analyze_historical_prefixes(
        build_run_import(descriptors=descriptors, portfolios=portfolios)
    )

    assert len(result.all_strategy_summaries) == len(descriptors) * len(SUPPORTED_PREFIX_COUNTS)
    assert _summary(result, strategy_id="alias", prefix=1).ranking_eligible is False
    assert _summary(result, strategy_id="base", prefix=1, replicate=1).ranking_eligible is True
    assert _summary(result, strategy_id="base", prefix=1, replicate=2).ranking_eligible is True
    zero = _summary(result, strategy_id="zero", prefix=1)
    assert zero.status is HistoricalPrefixSummaryStatus.NO_PORTFOLIOS
    assert zero.portfolio_success_rate == ExactRatio.unavailable()
    synthetic = _summary(result, strategy_id="SYNTHETIC_X", prefix=1)
    assert synthetic.identity.identity_kind is HistoricalIdentityKind.SYNTHETIC_TEST_ONLY


def test_result_preserves_source_hashes_and_is_repeatably_equal_without_mutation() -> None:
    run_import = build_run_import()
    before = (run_import, run_import.source, run_import.portfolios[0].tickets)
    first = analyze_historical_prefixes(run_import)
    second = analyze_historical_prefixes(run_import)

    assert first == second
    assert before == (run_import, run_import.source, run_import.portfolios[0].tickets)
    assert first.source_import_identity_sha256 == run_import.import_identity_sha256
    assert first.source_manifest_sha256 == run_import.manifest_sha256
    assert first.source_artifact_sha256 == run_import.source.source_artifact_sha256
    assert first.ranking_policy_id == RANKING_POLICY_ID
    assert first.historical_only_disclaimer_id == HISTORICAL_ONLY_DISCLAIMER_ID


def test_whole_input_validation_rejects_all_cross_reference_failures() -> None:
    valid = build_run_import()
    missing_descriptor = replace(valid, strategy_descriptors=(build_descriptor("other"),))
    missing_target = replace(valid, draw_snapshots=(valid.draw_snapshots[0],))
    missing_cutoff = replace(valid, draw_snapshots=(valid.draw_snapshots[1],))
    duplicate_portfolio = replace(valid, portfolios=(valid.portfolios[0], valid.portfolios[0]))
    wrong_lottery = replace(
        valid,
        dataset=replace(
            valid.dataset,
            lottery_type=cast(HistoricalLotteryType, cast(Any, "DAILY_539")),
        ),
    )

    for invalid in (
        missing_descriptor,
        missing_target,
        missing_cutoff,
        duplicate_portfolio,
        wrong_lottery,
    ):
        with pytest.raises(HistoricalPrefixAnalyticsInputError):
            analyze_historical_prefixes(invalid)


def test_unsupported_prefix_fails_before_returning_any_result() -> None:
    with pytest.raises(HistoricalPrefixAnalyticsInputError, match="unsupported prefix"):
        analyze_historical_prefixes(build_run_import(), prefix_counts=(1, 6))


def test_invalid_canonical_prize_signature_is_a_typed_atomic_input_failure() -> None:
    portfolio = build_portfolio(
        hit_counts=(6,) + (0,) * 19,
        special_hits=(True,) + (False,) * 19,
    )
    with pytest.raises(
        HistoricalPrefixAnalyticsInputError,
        match="canonical prize resolver",
    ):
        analyze_historical_prefixes(build_run_import(portfolios=(portfolio,)))
