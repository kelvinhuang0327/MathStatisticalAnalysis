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

from lottolab.application.historical_prefix_queries import (
    HistoricalPrefixQueryContractError,
    HistoricalPrefixStrategyKey,
)
from lottolab.application.use_cases.query_historical_prefix_analytics import (
    GetHistoricalPrefixBestRankings,
    ListHistoricalPrefixReplay,
    ListHistoricalPrefixStrategyOverview,
)
from lottolab.domain.historical_prefix_analytics import (
    HistoricalPrefixAnalyticsResult,
    HistoricalPrefixSummaryStatus,
    analyze_historical_prefixes,
)
from lottolab.domain.historical_results import (
    HistoricalGovernanceStatus,
    HistoricalLotteryType,
)


def _rich_result() -> HistoricalPrefixAnalyticsResult:
    descriptors = (
        build_descriptor("base", strategy_version="v1", replicate=1),
        build_descriptor("base", strategy_version="v1", replicate=2),
        build_descriptor("base", strategy_version="v2", replicate=1),
        build_descriptor(
            "alias",
            effective_strategy_id="base",
            alias_of_strategy_id="base",
            governance_status=HistoricalGovernanceStatus.RETIRED,
        ),
        build_descriptor("zero", governance_status=HistoricalGovernanceStatus.REJECTED),
    )
    draws = (
        build_draw(1, draw_date="2025-12-31"),
        build_draw(10, draw_date="2026-01-02"),
        build_draw(9, draw_date="2026-01-02"),
        build_draw(11, draw_date="2026-01-03"),
    )
    portfolios = (
        build_portfolio("base", target_draw_number=10, cutoff_draw_number=1),
        build_portfolio("base", target_draw_number=9, cutoff_draw_number=1),
        build_portfolio("base", replicate=2, target_draw_number=11, cutoff_draw_number=1),
        build_portfolio(
            "base", strategy_version="v2", target_draw_number=11, cutoff_draw_number=1
        ),
        build_portfolio("alias", target_draw_number=11, cutoff_draw_number=1),
    )
    return analyze_historical_prefixes(
        build_run_import(descriptors=descriptors, draws=draws, portfolios=portfolios)
    )


def _strategy(
    strategy_id: str = "base", strategy_version: str = "v1", replicate: int = 1
) -> HistoricalPrefixStrategyKey:
    return HistoricalPrefixStrategyKey(strategy_id, strategy_version, replicate)


def test_best_rankings_preserve_complete_group_order_global_ranks_and_source() -> None:
    result = _rich_result()
    before = result
    response = GetHistoricalPrefixBestRankings().execute(result, top_k=2)

    assert tuple(group.prefix_count for group in response.groups) == (1, 2, 3, 4, 5)
    for source, group in zip(result.ranking_groups, response.groups, strict=True):
        assert group.status is source.status
        assert group.total_candidate_count == len(source.candidates)
        assert group.requested_top_k == 2
        assert group.candidates == source.candidates[:2]
        assert tuple(candidate.rank for candidate in group.candidates) == tuple(
            candidate.rank for candidate in source.candidates[:2]
        )
        assert all(candidate.summary is original.summary for candidate, original in zip(
            group.candidates, source.candidates, strict=False
        ))
    assert result == before


def test_best_rankings_never_rerank_the_supplied_complete_core_order() -> None:
    result = _rich_result()
    first = result.ranking_groups[0]
    reversed_candidates = tuple(
        replace(candidate, rank=rank)
        for rank, candidate in enumerate(reversed(first.candidates), start=1)
    )
    supplied_order = replace(
        result,
        ranking_groups=(replace(first, candidates=reversed_candidates), *result.ranking_groups[1:]),
    )

    response = GetHistoricalPrefixBestRankings().execute(supplied_order, top_k=100)
    assert response.groups[0].candidates == reversed_candidates


def test_empty_eligible_ranking_group_is_preserved() -> None:
    run_import = replace(
        build_run_import(),
        strategy_descriptors=(build_descriptor("zero"),),
        portfolios=(),
    )
    result = analyze_historical_prefixes(
        run_import
    )
    response = GetHistoricalPrefixBestRankings().execute(result)
    assert all(group.total_candidate_count == 0 for group in response.groups)
    assert all(group.candidates == () for group in response.groups)


@pytest.mark.parametrize("top_k", [1, 100])
def test_best_rankings_accept_top_k_boundaries(top_k: int) -> None:
    assert GetHistoricalPrefixBestRankings().execute(_rich_result(), top_k=top_k).top_k == top_k


@pytest.mark.parametrize("top_k", [0, 101, -1, True])
def test_best_rankings_reject_invalid_top_k_without_clamping(top_k: Any) -> None:
    with pytest.raises(HistoricalPrefixQueryContractError):
        GetHistoricalPrefixBestRankings().execute(_rich_result(), top_k=top_k)


@pytest.mark.parametrize("prefix_count", [10, 15, 20])
def test_strategy_overview_keeps_every_exact_identity_and_governance_state(
    prefix_count: int,
) -> None:
    response = ListHistoricalPrefixStrategyOverview().execute(
        _rich_result(), prefix_count=prefix_count
    )
    keys = tuple(
        (
            summary.identity.strategy_id,
            summary.identity.strategy_version,
            summary.identity.replicate,
        )
        for summary in response.summaries
    )
    assert keys == tuple(sorted(keys))
    assert keys == (
        ("alias", "v1", 1),
        ("base", "v1", 1),
        ("base", "v1", 2),
        ("base", "v2", 1),
        ("zero", "v1", 1),
    )
    alias = response.summaries[0]
    zero = response.summaries[-1]
    assert alias.identity.effective_strategy_id == "base"
    assert alias.identity.alias_of_strategy_id == "base"
    assert alias.identity.governance_status is HistoricalGovernanceStatus.RETIRED
    assert zero.status is HistoricalPrefixSummaryStatus.NO_PORTFOLIOS
    assert zero.identity.governance_status is HistoricalGovernanceStatus.REJECTED
    assert response.total_count == 5


@pytest.mark.parametrize("prefix_count", [1, 2, 3, 4, 5, 9, 11, True])
def test_strategy_overview_rejects_non_overview_prefixes(prefix_count: Any) -> None:
    with pytest.raises(HistoricalPrefixQueryContractError):
        ListHistoricalPrefixStrategyOverview().execute(
            _rich_result(), prefix_count=prefix_count
        )


@pytest.mark.parametrize("prefix_count", [1, 2, 3, 4, 5, 10, 15, 20])
def test_replay_accepts_all_canonical_prefixes(prefix_count: int) -> None:
    page = ListHistoricalPrefixReplay().execute(
        _rich_result(), strategy=_strategy(), prefix_count=prefix_count
    )
    assert page is not None
    assert page.prefix_count == prefix_count


def test_replay_matches_exact_three_part_identity() -> None:
    result = _rich_result()
    v1_rep1 = ListHistoricalPrefixReplay().execute(
        result, strategy=_strategy(), prefix_count=1
    )
    v1_rep2 = ListHistoricalPrefixReplay().execute(
        result, strategy=_strategy(replicate=2), prefix_count=1
    )
    v2_rep1 = ListHistoricalPrefixReplay().execute(
        result, strategy=_strategy(strategy_version="v2"), prefix_count=1
    )
    assert v1_rep1 is not None and v1_rep1.total_count == 2
    assert v1_rep2 is not None and v1_rep2.total_count == 1
    assert v2_rep1 is not None and v2_rep1.total_count == 1
    assert ListHistoricalPrefixReplay().execute(
        result, strategy=_strategy(strategy_version="missing"), prefix_count=1
    ) is None
    assert ListHistoricalPrefixReplay().execute(
        result, strategy=_strategy(replicate=3), prefix_count=1
    ) is None


def test_replay_zero_portfolio_descriptor_returns_successful_empty_page() -> None:
    page = ListHistoricalPrefixReplay().execute(
        _rich_result(), strategy=_strategy("zero"), prefix_count=20
    )
    assert page is not None
    assert page.items == ()
    assert page.total_count == 0


def test_replay_sorts_numerically_then_paginates_and_preserves_metrics() -> None:
    result = _rich_result()
    source_metrics = tuple(
        metric
        for metric in result.per_draw_metrics
        if metric.identity.strategy_id == "base"
        and metric.identity.strategy_version == "v1"
        and metric.identity.replicate == 1
        and metric.prefix_count == 5
    )
    page = ListHistoricalPrefixReplay().execute(
        result,
        strategy=_strategy(),
        prefix_count=5,
        limit=1,
        offset=1,
    )
    assert page is not None
    assert page.total_count == 2
    assert tuple(metric.target.draw_number for metric in source_metrics) == (10, 9)
    assert tuple(metric.target.draw_number for metric in page.items) == (10,)
    assert page.items[0] is source_metrics[0]


@pytest.mark.parametrize(
    ("prefix_count", "limit", "offset"),
    [(6, 50, 0), (1, 0, 0), (1, 201, 0), (1, True, 0), (1, 50, -1), (1, 50, True)],
)
def test_replay_rejects_invalid_page_bounds_and_prefix(
    prefix_count: Any, limit: Any, offset: Any
) -> None:
    with pytest.raises(HistoricalPrefixQueryContractError):
        ListHistoricalPrefixReplay().execute(
            _rich_result(),
            strategy=_strategy(),
            prefix_count=prefix_count,
            limit=limit,
            offset=offset,
        )


def test_replay_rejects_non_key_strategy_without_effective_id_substitution() -> None:
    with pytest.raises(HistoricalPrefixQueryContractError):
        ListHistoricalPrefixReplay().execute(
            _rich_result(),
            strategy=cast(Any, ("base", "v1", 1)),
            prefix_count=1,
        )


def _assert_contract_error(result: Any) -> None:
    with pytest.raises(HistoricalPrefixQueryContractError):
        GetHistoricalPrefixBestRankings().execute(result)


def test_contract_rejects_wrong_result_type_lottery_schema_policy_and_disclaimer() -> None:
    result = _rich_result()
    wrong_lottery = replace(
        result,
        lottery_type=cast(HistoricalLotteryType, cast(Any, "DAILY_539")),
    )
    for malformed in (
        cast(Any, object()),
        wrong_lottery,
        replace(result, result_schema_version="wrong"),
        replace(result, ranking_policy_id="wrong"),
        replace(result, historical_only_disclaimer_id="wrong"),
        replace(result, supported_prefixes=(1, 2, 3, 4, 5)),
    ):
        _assert_contract_error(malformed)


def test_contract_rejects_missing_duplicate_or_malformed_ranking_groups_atomically() -> None:
    result = _rich_result()
    first = result.ranking_groups[0]
    bad_rank = replace(first.candidates[0], rank=2)
    malformed = (
        replace(result, ranking_groups=result.ranking_groups[1:]),
        replace(result, ranking_groups=(first, first, *result.ranking_groups[2:])),
        replace(result, ranking_groups=cast(Any, (object(), *result.ranking_groups[1:]))),
        replace(
            result,
            ranking_groups=(
                replace(first, candidates=(bad_rank, *first.candidates[1:])),
                *result.ranking_groups[1:],
            ),
        ),
    )
    for value in malformed:
        _assert_contract_error(value)


def test_contract_rejects_candidate_summary_identity_or_prefix_mismatch() -> None:
    result = _rich_result()
    first = result.ranking_groups[0]
    candidate = first.candidates[0]
    other_identity = first.candidates[1].identity
    wrong_identity = replace(candidate, identity=other_identity)
    wrong_prefix = replace(candidate, summary=replace(candidate.summary, prefix_count=2))
    for malformed_candidate in (wrong_identity, wrong_prefix):
        malformed_group = replace(
            first, candidates=(malformed_candidate, *first.candidates[1:])
        )
        _assert_contract_error(
            replace(result, ranking_groups=(malformed_group, *result.ranking_groups[1:]))
        )


def test_contract_rejects_duplicate_summary_duplicate_target_and_metric_without_summary() -> None:
    result = _rich_result()
    duplicate_summary = replace(
        result,
        all_strategy_summaries=(
            *result.all_strategy_summaries,
            result.all_strategy_summaries[0],
        ),
    )
    duplicate_metric = replace(
        result,
        per_draw_metrics=(*result.per_draw_metrics, result.per_draw_metrics[0]),
    )
    metric = result.per_draw_metrics[0]
    unknown_identity = replace(metric.identity, strategy_id="missing")
    metric_without_summary = replace(
        result,
        per_draw_metrics=(replace(metric, identity=unknown_identity), *result.per_draw_metrics[1:]),
    )
    for malformed in (duplicate_summary, duplicate_metric, metric_without_summary):
        _assert_contract_error(malformed)
