from __future__ import annotations

from tests.fixtures.historical.prefix_analytics_builder import (
    build_descriptor,
    build_draw,
    build_portfolio,
    build_run_import,
)

from lottolab.domain.historical_prefix_analytics import (
    RANKING_POLICY_ID,
    HistoricalPrefixAnalyticsResult,
    HistoricalPrefixRankingStatus,
    analyze_historical_prefixes,
)
from lottolab.domain.historical_results import HistoricalDrawSnapshot, HistoricalPortfolio


def _ranked_ids(result: HistoricalPrefixAnalyticsResult, prefix: int) -> list[tuple[str, str, int]]:
    groups = result.ranking_groups
    group = next(group for group in groups if group.prefix_count == prefix)
    return [
        (
            candidate.identity.strategy_id,
            candidate.identity.strategy_version,
            candidate.identity.replicate,
        )
        for candidate in group.candidates
    ]


def test_legacy_best_n_means_same_strategy_first_n_tickets_and_exact_ratio_ranking() -> None:
    descriptors = (build_descriptor("many"), build_descriptor("precise"))
    draws: list[HistoricalDrawSnapshot] = [build_draw(1, draw_date="2025-12-31")]
    portfolios: list[HistoricalPortfolio] = []
    for target in range(2, 102):
        draws.append(build_draw(target, draw_date=f"2026-01-{((target - 2) % 28) + 1:02d}"))
        hit = 1 if target <= 34 else 0
        portfolios.append(
            build_portfolio(
                "many",
                target_draw_number=target,
                cutoff_draw_number=1,
                hit_counts=(hit,) + (0,) * 19,
            )
        )
    for target in (102, 103, 104):
        draws.append(build_draw(target, draw_date=f"2026-02-{target - 101:02d}"))
        hit = 1 if target == 102 else 0
        portfolios.append(
            build_portfolio(
                "precise",
                target_draw_number=target,
                cutoff_draw_number=1,
                hit_counts=(hit,) + (0,) * 19,
            )
        )

    result = analyze_historical_prefixes(
        build_run_import(descriptors=descriptors, draws=draws, portfolios=portfolios)
    )
    assert _ranked_ids(result, 1)[0][0] == "precise"  # 1/3 > 33/100 exactly.
    assert result.ranking_policy_id == RANKING_POLICY_ID


def test_ranking_never_uses_rounded_float_ties() -> None:
    descriptors = (build_descriptor("z_exact"), build_descriptor("a_rounded"))
    draws: list[HistoricalDrawSnapshot] = [build_draw(1, draw_date="2025-12-31")]
    portfolios: list[HistoricalPortfolio] = []
    target = 2
    for strategy_id, successes, total in (("z_exact", 1, 3), ("a_rounded", 3333, 10000)):
        for index in range(total):
            draws.append(
                build_draw(target, draw_date=f"2026-{(index % 12) + 1:02d}-{(index % 28) + 1:02d}")
            )
            portfolios.append(
                build_portfolio(
                    strategy_id,
                    target_draw_number=target,
                    cutoff_draw_number=1,
                    hit_counts=((1 if index < successes else 0),) + (0,) * 19,
                )
            )
            target += 1
    result = analyze_historical_prefixes(
        build_run_import(descriptors=descriptors, draws=draws, portfolios=portfolios)
    )
    assert _ranked_ids(result, 1)[0][0] == "z_exact"


def test_aliases_are_visible_but_excluded_replicates_are_independent_and_groups_always_exist() -> (
    None
):
    descriptors = (
        build_descriptor("base", replicate=1),
        build_descriptor("base", replicate=2),
        build_descriptor("alias", alias_of_strategy_id="base"),
        build_descriptor("zero"),
    )
    portfolios = (
        build_portfolio("base", replicate=1, hit_counts=(1,) + (0,) * 19),
        build_portfolio("base", replicate=2, hit_counts=(2,) + (0,) * 19),
        build_portfolio("alias", hit_counts=(6,) + (0,) * 19),
    )
    result = analyze_historical_prefixes(
        build_run_import(descriptors=descriptors, portfolios=portfolios)
    )

    assert len(result.ranking_groups) == 5
    assert all(
        group.status is HistoricalPrefixRankingStatus.RANKED for group in result.ranking_groups
    )
    ranked = _ranked_ids(result, 1)
    assert ranked == [("base", "v1", 2), ("base", "v1", 1)]
    assert {summary.identity.strategy_id for summary in result.all_strategy_summaries} == {
        "alias",
        "base",
        "zero",
    }


def test_final_ties_are_strategy_id_then_version_then_replicate_ascending() -> None:
    descriptors = (
        build_descriptor("b", strategy_version="v1", replicate=1),
        build_descriptor("a", strategy_version="v2", replicate=2),
        build_descriptor("a", strategy_version="v1", replicate=2),
        build_descriptor("a", strategy_version="v1", replicate=1),
    )
    portfolios = tuple(
        build_portfolio(
            descriptor.strategy_id,
            strategy_version=descriptor.strategy_version,
            replicate=descriptor.replicate,
            hit_counts=(1,) + (0,) * 19,
        )
        for descriptor in descriptors
    )
    result = analyze_historical_prefixes(
        build_run_import(descriptors=descriptors, portfolios=portfolios)
    )
    assert _ranked_ids(result, 1) == [
        ("a", "v1", 1),
        ("a", "v1", 2),
        ("a", "v2", 2),
        ("b", "v1", 1),
    ]


def _two_strategy_result(
    left_portfolios: tuple[HistoricalPortfolio, ...],
    right_portfolios: tuple[HistoricalPortfolio, ...],
    *,
    target_dates: dict[int, str],
) -> HistoricalPrefixAnalyticsResult:
    descriptors = (build_descriptor("left"), build_descriptor("right"))
    draws = (
        build_draw(1, draw_date="2025-12-31"),
        *(build_draw(target, draw_date=target_dates[target]) for target in sorted(target_dates)),
    )
    return analyze_historical_prefixes(
        build_run_import(
            descriptors=descriptors,
            draws=draws,
            portfolios=(*left_portfolios, *right_portfolios),
        )
    )


def test_second_priority_is_higher_exact_average_best_hit() -> None:
    result = _two_strategy_result(
        (
            build_portfolio(
                "left", target_draw_number=2, cutoff_draw_number=1, hit_counts=(2,) + (0,) * 19
            ),
        ),
        (
            build_portfolio(
                "right", target_draw_number=2, cutoff_draw_number=1, hit_counts=(1,) + (0,) * 19
            ),
        ),
        target_dates={2: "2026-01-02"},
    )
    assert _ranked_ids(result, 1)[0][0] == "left"


def test_third_priority_is_higher_exact_average_total_hit() -> None:
    result = _two_strategy_result(
        (
            build_portfolio(
                "left", target_draw_number=2, cutoff_draw_number=1, hit_counts=(1, 1) + (0,) * 18
            ),
        ),
        (
            build_portfolio(
                "right", target_draw_number=2, cutoff_draw_number=1, hit_counts=(1, 0) + (0,) * 18
            ),
        ),
        target_dates={2: "2026-01-02"},
    )
    assert _ranked_ids(result, 2)[0][0] == "left"


def test_fourth_priority_is_higher_max_single_hit() -> None:
    target_dates = {2: "2026-01-02", 3: "2026-01-03", 4: "2026-01-04"}
    left = tuple(
        build_portfolio(
            "left", target_draw_number=target, cutoff_draw_number=1, hit_counts=(hit,) + (0,) * 19
        )
        for target, hit in zip(target_dates, (3, 1, 0), strict=True)
    )
    right = tuple(
        build_portfolio(
            "right", target_draw_number=target, cutoff_draw_number=1, hit_counts=(hit,) + (0,) * 19
        )
        for target, hit in zip(target_dates, (2, 2, 0), strict=True)
    )
    result = _two_strategy_result(left, right, target_dates=target_dates)
    assert _ranked_ids(result, 1)[0][0] == "left"


def test_fifth_priority_is_higher_max_portfolio_total_hit() -> None:
    target_dates = {2: "2026-01-02", 3: "2026-01-03", 4: "2026-01-04"}
    left_hits = ((2, 2), (1, 0), (0, 0))
    right_hits = ((2, 1), (1, 1), (0, 0))
    left = tuple(
        build_portfolio(
            "left", target_draw_number=target, cutoff_draw_number=1, hit_counts=hits + (0,) * 18
        )
        for target, hits in zip(target_dates, left_hits, strict=True)
    )
    right = tuple(
        build_portfolio(
            "right", target_draw_number=target, cutoff_draw_number=1, hit_counts=hits + (0,) * 18
        )
        for target, hits in zip(target_dates, right_hits, strict=True)
    )
    result = _two_strategy_result(left, right, target_dates=target_dates)
    assert _ranked_ids(result, 2)[0][0] == "left"


def test_sixth_priority_is_larger_distinct_draw_count() -> None:
    target_dates = {2: "2026-01-02", 3: "2026-01-03"}
    left = (
        build_portfolio(
            "left", target_draw_number=2, cutoff_draw_number=1, hit_counts=(1,) + (0,) * 19
        ),
    )
    right = (
        build_portfolio(
            "right", target_draw_number=2, cutoff_draw_number=1, hit_counts=(1,) + (0,) * 19
        ),
        build_portfolio(
            "right", target_draw_number=3, cutoff_draw_number=1, hit_counts=(1,) + (0,) * 19
        ),
    )
    result = _two_strategy_result(left, right, target_dates=target_dates)
    assert _ranked_ids(result, 1)[0][0] == "right"


def test_groups_report_no_eligible_strategies_when_only_alias_or_zero_draws_exist() -> None:
    descriptors = (
        build_descriptor("base"),
        build_descriptor("alias", alias_of_strategy_id="base"),
    )
    result = analyze_historical_prefixes(
        build_run_import(
            descriptors=descriptors,
            portfolios=(build_portfolio("alias", hit_counts=(6,) + (0,) * 19),),
        )
    )
    assert all(
        group.status is HistoricalPrefixRankingStatus.NO_ELIGIBLE_STRATEGIES
        and not group.candidates
        for group in result.ranking_groups
    )
