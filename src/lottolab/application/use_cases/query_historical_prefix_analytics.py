"""Deterministic in-memory queries over one historical-prefix analytics result."""

from __future__ import annotations

from lottolab.application.historical_prefix_queries import (
    DEFAULT_PAGE_LIMIT,
    DEFAULT_TOP_K,
    MAX_PAGE_LIMIT,
    MAX_TOP_K,
    MIN_PAGE_LIMIT,
    MIN_TOP_K,
    OVERVIEW_PREFIX_COUNTS,
    HistoricalPrefixBestRankings,
    HistoricalPrefixQueryContractError,
    HistoricalPrefixQueryMetadata,
    HistoricalPrefixRankingGroupSlice,
    HistoricalPrefixReplayPage,
    HistoricalPrefixStrategyKey,
    HistoricalPrefixStrategyOverview,
)
from lottolab.domain.historical_prefix_analytics import (
    HISTORICAL_ONLY_DISCLAIMER_ID,
    RANKING_POLICY_ID,
    RANKING_PREFIX_COUNTS,
    RESULT_SCHEMA_VERSION,
    SUPPORTED_PREFIX_COUNTS,
    HistoricalPerDrawPrefixMetrics,
    HistoricalPrefixAnalyticsResult,
    HistoricalPrefixRankingCandidate,
    HistoricalPrefixRankingGroup,
    HistoricalPrefixRankingStatus,
    HistoricalStrategyIdentity,
    HistoricalStrategyPrefixSummary,
)
from lottolab.domain.historical_results import HistoricalLotteryType

_IdentityKey = tuple[str, str, int]
_SummaryKey = tuple[str, str, int, int]


def _error(message: str) -> HistoricalPrefixQueryContractError:
    return HistoricalPrefixQueryContractError(message)


def _identity_key(identity: HistoricalStrategyIdentity) -> _IdentityKey:
    return (identity.strategy_id, identity.strategy_version, identity.replicate)


def _summary_key(summary: HistoricalStrategyPrefixSummary) -> _SummaryKey:
    return (*_identity_key(summary.identity), summary.prefix_count)


def _validate_result(result: object) -> HistoricalPrefixAnalyticsResult:
    if type(result) is not HistoricalPrefixAnalyticsResult:
        raise _error("result must be exactly a HistoricalPrefixAnalyticsResult")
    if result.lottery_type is not HistoricalLotteryType.BIG_LOTTO:
        raise _error("lottery type must be exactly BIG_LOTTO")
    if result.result_schema_version != RESULT_SCHEMA_VERSION:
        raise _error("result schema version does not match the merged analytics core")
    if result.ranking_policy_id != RANKING_POLICY_ID:
        raise _error("ranking policy does not match the merged analytics core")
    if result.historical_only_disclaimer_id != HISTORICAL_ONLY_DISCLAIMER_ID:
        raise _error("historical-only disclaimer does not match the merged analytics core")
    if result.supported_prefixes != SUPPORTED_PREFIX_COUNTS:
        raise _error("supported prefixes must be the complete canonical sequence")

    summaries: dict[_SummaryKey, HistoricalStrategyPrefixSummary] = {}
    prefixes_by_identity: dict[_IdentityKey, set[int]] = {}
    for summary in result.all_strategy_summaries:
        if type(summary) is not HistoricalStrategyPrefixSummary:
            raise _error("all_strategy_summaries contains a malformed summary")
        if type(summary.identity) is not HistoricalStrategyIdentity:
            raise _error("a strategy summary contains a malformed identity")
        if summary.prefix_count not in SUPPORTED_PREFIX_COUNTS:
            raise _error("a strategy summary contains an unsupported prefix")
        key = _summary_key(summary)
        if key in summaries:
            raise _error(f"duplicate exact strategy summary: {key!r}")
        summaries[key] = summary
        prefixes_by_identity.setdefault(key[:3], set()).add(summary.prefix_count)
    expected_prefixes = set(SUPPORTED_PREFIX_COUNTS)
    if any(prefixes != expected_prefixes for prefixes in prefixes_by_identity.values()):
        raise _error("every exact strategy identity must have every canonical prefix summary")

    metric_targets: set[tuple[_SummaryKey, object]] = set()
    for metric in result.per_draw_metrics:
        if type(metric) is not HistoricalPerDrawPrefixMetrics:
            raise _error("per_draw_metrics contains a malformed metric")
        if type(metric.identity) is not HistoricalStrategyIdentity:
            raise _error("a per-draw metric contains a malformed identity")
        key = (*_identity_key(metric.identity), metric.prefix_count)
        if key not in summaries:
            raise _error(f"per-draw metric has no exact strategy summary: {key!r}")
        target_key = (key, metric.target)
        if target_key in metric_targets:
            raise _error(f"duplicate per-draw exact strategy/prefix/target: {key!r}")
        metric_targets.add(target_key)

    if type(result.ranking_groups) is not tuple:
        raise _error("ranking_groups must be an immutable tuple")
    if any(type(group) is not HistoricalPrefixRankingGroup for group in result.ranking_groups):
        raise _error("ranking_groups contains a malformed group")
    group_prefixes = tuple(group.prefix_count for group in result.ranking_groups)
    if group_prefixes != RANKING_PREFIX_COUNTS:
        raise _error("ranking groups must contain exactly prefixes 1..5 in canonical order")
    for group in result.ranking_groups:
        _validate_ranking_group(group, summaries)
    return result


def _validate_ranking_group(
    group: HistoricalPrefixRankingGroup,
    summaries: dict[_SummaryKey, HistoricalStrategyPrefixSummary],
) -> None:
    if type(group) is not HistoricalPrefixRankingGroup:
        raise _error("ranking_groups contains a malformed group")
    if group.ranking_policy_id != RANKING_POLICY_ID:
        raise _error("a ranking group uses an unexpected ranking policy")
    expected_status = (
        HistoricalPrefixRankingStatus.RANKED
        if group.candidates
        else HistoricalPrefixRankingStatus.NO_ELIGIBLE_STRATEGIES
    )
    if group.status is not expected_status:
        raise _error("a ranking group status does not match its candidates")

    candidate_keys: set[_SummaryKey] = set()
    for expected_rank, candidate in enumerate(group.candidates, start=1):
        if type(candidate) is not HistoricalPrefixRankingCandidate:
            raise _error("a ranking group contains a malformed candidate")
        if candidate.rank != expected_rank:
            raise _error("ranking candidate ranks must be positive and sequential")
        if candidate.summary.prefix_count != group.prefix_count:
            raise _error("ranking candidate summary prefix does not match its group")
        if candidate.identity != candidate.summary.identity:
            raise _error("ranking candidate identity does not match its summary")
        key = _summary_key(candidate.summary)
        if key in candidate_keys:
            raise _error("a ranking group contains a duplicate exact strategy candidate")
        candidate_keys.add(key)
        if summaries.get(key) != candidate.summary or not candidate.summary.ranking_eligible:
            raise _error("ranking candidate does not map to an eligible exact summary")

    eligible_keys = {
        key
        for key, summary in summaries.items()
        if summary.prefix_count == group.prefix_count and summary.ranking_eligible
    }
    if candidate_keys != eligible_keys:
        raise _error("ranking group does not contain every eligible exact strategy summary")


def _validate_bounded_int(value: int, *, name: str, minimum: int, maximum: int) -> None:
    if type(value) is not int or not minimum <= value <= maximum:
        raise _error(f"{name} must be an integer between {minimum} and {maximum}")


def _validate_prefix(prefix_count: int, *, allowed: tuple[int, ...]) -> None:
    if type(prefix_count) is not int or prefix_count not in allowed:
        choices = ", ".join(str(value) for value in allowed)
        raise _error(f"prefix_count must be one of {choices}")


def _metadata(result: HistoricalPrefixAnalyticsResult) -> HistoricalPrefixQueryMetadata:
    return HistoricalPrefixQueryMetadata(
        result_schema_version=result.result_schema_version,
        source_import_identity_sha256=result.source_import_identity_sha256,
        source_manifest_sha256=result.source_manifest_sha256,
        source_artifact_sha256=result.source_artifact_sha256,
        dataset_identity=result.dataset_identity,
        dataset_sha256=result.dataset_sha256,
        lottery_type=result.lottery_type.value,
        ranking_policy_id=result.ranking_policy_id,
        historical_only_disclaimer_id=result.historical_only_disclaimer_id,
    )


class GetHistoricalPrefixBestRankings:
    def execute(
        self,
        result: HistoricalPrefixAnalyticsResult,
        *,
        top_k: int = DEFAULT_TOP_K,
    ) -> HistoricalPrefixBestRankings:
        validated = _validate_result(result)
        _validate_bounded_int(top_k, name="top_k", minimum=MIN_TOP_K, maximum=MAX_TOP_K)
        groups = tuple(
            HistoricalPrefixRankingGroupSlice(
                prefix_count=group.prefix_count,
                status=group.status,
                total_candidate_count=len(group.candidates),
                requested_top_k=top_k,
                candidates=group.candidates[:top_k],
            )
            for group in validated.ranking_groups
        )
        return HistoricalPrefixBestRankings(
            metadata=_metadata(validated),
            top_k=top_k,
            groups=groups,
        )


class ListHistoricalPrefixStrategyOverview:
    def execute(
        self,
        result: HistoricalPrefixAnalyticsResult,
        *,
        prefix_count: int,
    ) -> HistoricalPrefixStrategyOverview:
        validated = _validate_result(result)
        _validate_prefix(prefix_count, allowed=OVERVIEW_PREFIX_COUNTS)
        summaries = tuple(
            sorted(
                (
                    summary
                    for summary in validated.all_strategy_summaries
                    if summary.prefix_count == prefix_count
                ),
                key=lambda summary: _identity_key(summary.identity),
            )
        )
        return HistoricalPrefixStrategyOverview(
            metadata=_metadata(validated),
            prefix_count=prefix_count,
            summaries=summaries,
            total_count=len(summaries),
        )


class ListHistoricalPrefixReplay:
    def execute(
        self,
        result: HistoricalPrefixAnalyticsResult,
        *,
        strategy: HistoricalPrefixStrategyKey,
        prefix_count: int,
        limit: int = DEFAULT_PAGE_LIMIT,
        offset: int = 0,
    ) -> HistoricalPrefixReplayPage | None:
        validated = _validate_result(result)
        if type(strategy) is not HistoricalPrefixStrategyKey:
            raise _error("strategy must be exactly a HistoricalPrefixStrategyKey")
        _validate_prefix(prefix_count, allowed=SUPPORTED_PREFIX_COUNTS)
        _validate_bounded_int(limit, name="limit", minimum=MIN_PAGE_LIMIT, maximum=MAX_PAGE_LIMIT)
        if type(offset) is not int or offset < 0:
            raise _error("offset must be a non-negative integer")

        strategy_key = (strategy.strategy_id, strategy.strategy_version, strategy.replicate)
        if not any(
            _identity_key(summary.identity) == strategy_key
            for summary in validated.all_strategy_summaries
        ):
            return None

        items = tuple(
            sorted(
                (
                    metric
                    for metric in validated.per_draw_metrics
                    if _identity_key(metric.identity) == strategy_key
                    and metric.prefix_count == prefix_count
                ),
                key=lambda metric: (metric.target.draw_date, metric.target.draw_number),
            )
        )
        return HistoricalPrefixReplayPage(
            metadata=_metadata(validated),
            strategy=strategy,
            prefix_count=prefix_count,
            items=items[offset : offset + limit],
            total_count=len(items),
            limit=limit,
            offset=offset,
        )


__all__ = [
    "GetHistoricalPrefixBestRankings",
    "ListHistoricalPrefixReplay",
    "ListHistoricalPrefixStrategyOverview",
]
