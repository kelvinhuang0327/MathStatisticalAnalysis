"""Pure deterministic analytics for source-ordered historical ticket prefixes.

The core consumes one already-validated :class:`HistoricalRunImport`. It does
not execute strategies, select tickets by outcome, read external state, or
make predictive claims. Every prefix is the literal first N tickets in the
stored tuple and every ranking ratio is compared by integer cross-product.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from functools import cmp_to_key

from lottolab.domain.historical_results import (
    HistoricalDrawSnapshot,
    HistoricalGovernanceStatus,
    HistoricalIdentityKind,
    HistoricalLotteryType,
    HistoricalPortfolio,
    HistoricalRunImport,
    HistoricalStrategyDescriptor,
    HistoricalTicket,
)
from lottolab.domain.lottery_rules import (
    BigLottoPrizeTier,
    BigLottoPrizeTierId,
    NoPrizeResult,
    resolve_big_lotto_prize_tier,
)

RESULT_SCHEMA_VERSION = "1.0.0"
RANKING_POLICY_ID = "LEGACY_BEST_NBET_PREFIX_V1"
HISTORICAL_ONLY_DISCLAIMER_ID = "HISTORICAL_REPLAY_ONLY_NO_FUTURE_GUARANTEE_V1"
SUPPORTED_PREFIX_COUNTS = (1, 2, 3, 4, 5, 10, 15, 20)
RANKING_PREFIX_COUNTS = (1, 2, 3, 4, 5)
PORTFOLIO_TICKET_COUNT = 20

RANKING_TIE_BREAK_PROVENANCE = (
    "portfolio_success_rate_desc_exact",
    "average_best_main_hit_count_desc_exact",
    "average_total_main_hit_count_desc_exact",
    "max_single_main_hit_count_desc",
    "max_portfolio_total_main_hit_count_desc",
    "distinct_draw_count_desc",
    "strategy_id_asc",
    "strategy_version_asc",
    "replicate_asc",
)

_TIER_COUNT_FIELD_BY_ID = {
    BigLottoPrizeTierId.FIRST: "first_prize_ticket_count",
    BigLottoPrizeTierId.SECOND: "second_prize_ticket_count",
    BigLottoPrizeTierId.THIRD: "third_prize_ticket_count",
    BigLottoPrizeTierId.FOURTH: "fourth_prize_ticket_count",
    BigLottoPrizeTierId.FIFTH: "fifth_prize_ticket_count",
    BigLottoPrizeTierId.SIXTH: "sixth_prize_ticket_count",
    BigLottoPrizeTierId.SEVENTH: "seventh_prize_ticket_count",
    BigLottoPrizeTierId.GENERAL: "general_prize_ticket_count",
}


class HistoricalPrefixAnalyticsInputError(ValueError):
    """The complete import cannot be analyzed without repairing its contents."""


class HistoricalPrefixSummaryStatus(StrEnum):
    ANALYZED = "ANALYZED"
    NO_PORTFOLIOS = "NO_PORTFOLIOS"


class HistoricalPrefixRankingStatus(StrEnum):
    RANKED = "RANKED"
    NO_ELIGIBLE_STRATEGIES = "NO_ELIGIBLE_STRATEGIES"


class HistoricalPrefixRankingExclusionReason(StrEnum):
    ALIAS = "ALIAS"
    NO_PORTFOLIOS = "NO_PORTFOLIOS"


@dataclass(frozen=True, slots=True)
class ExactRatio:
    """An exact rational value; ``0/0`` is the sole unavailable state."""

    numerator: int
    denominator: int

    def __post_init__(self) -> None:
        if type(self.numerator) is not int or type(self.denominator) is not int:
            raise ValueError("ratio numerator and denominator must be integers")
        if self.numerator < 0 or self.denominator < 0:
            raise ValueError("ratio numerator and denominator must be non-negative")
        if self.denominator == 0 and self.numerator != 0:
            raise ValueError("an unavailable ratio must be exactly 0/0")

    @classmethod
    def unavailable(cls) -> ExactRatio:
        return cls(0, 0)

    @property
    def is_available(self) -> bool:
        return self.denominator > 0


@dataclass(frozen=True, slots=True)
class HistoricalStrategyIdentity:
    strategy_id: str
    effective_strategy_id: str
    strategy_version: str
    replicate: int
    identity_kind: HistoricalIdentityKind
    governance_status: HistoricalGovernanceStatus
    alias_of_strategy_id: str | None
    equivalence_group: str | None
    nested_prefix_supported: bool


@dataclass(frozen=True, slots=True)
class HistoricalDrawIdentity:
    draw_number: int
    draw_date: str
    draw_sha256: str


@dataclass(frozen=True, slots=True)
class HistoricalPerDrawPrefixMetrics:
    identity: HistoricalStrategyIdentity
    prefix_count: int
    prefix_ticket_count: int
    included_ticket_positions: tuple[int, ...]
    best_single_main_hit_count: int
    best_single_ticket_position: int
    total_main_hit_count: int
    portfolio_success: bool
    m3plus: bool
    m4plus: bool
    m5plus: bool
    m6: bool
    special_hit: bool
    special_hit_ticket_count: int
    winning_ticket_count: int
    no_prize_ticket_count: int
    first_prize_ticket_count: int
    second_prize_ticket_count: int
    third_prize_ticket_count: int
    fourth_prize_ticket_count: int
    fifth_prize_ticket_count: int
    sixth_prize_ticket_count: int
    seventh_prize_ticket_count: int
    general_prize_ticket_count: int
    strongest_winning_tier: BigLottoPrizeTierId | NoPrizeResult
    target: HistoricalDrawIdentity
    cutoff: HistoricalDrawIdentity


@dataclass(frozen=True, slots=True)
class HistoricalStrategyPrefixSummary:
    identity: HistoricalStrategyIdentity
    prefix_count: int
    status: HistoricalPrefixSummaryStatus
    distinct_draw_count: int
    replay_ticket_count: int
    portfolio_success_count: int
    portfolio_success_rate: ExactRatio
    sum_best_main_hit_count: int
    average_best_main_hit_count: ExactRatio
    sum_total_main_hit_count: int
    average_total_main_hit_count: ExactRatio
    max_single_main_hit_count: int
    max_portfolio_total_main_hit_count: int
    max_hit_target: HistoricalDrawIdentity | None
    m3plus_draw_count: int
    m4plus_draw_count: int
    m5plus_draw_count: int
    m6_draw_count: int
    special_hit_draw_count: int
    special_hit_ticket_count: int
    winning_draw_count: int
    winning_ticket_count: int
    no_prize_ticket_count: int
    first_prize_ticket_count: int
    second_prize_ticket_count: int
    third_prize_ticket_count: int
    fourth_prize_ticket_count: int
    fifth_prize_ticket_count: int
    sixth_prize_ticket_count: int
    seventh_prize_ticket_count: int
    general_prize_ticket_count: int
    ranking_eligible: bool
    ranking_exclusion_reason: HistoricalPrefixRankingExclusionReason | None


@dataclass(frozen=True, slots=True)
class HistoricalPrefixRankingCandidate:
    rank: int
    identity: HistoricalStrategyIdentity
    summary: HistoricalStrategyPrefixSummary
    tie_break_provenance: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class HistoricalPrefixRankingGroup:
    prefix_count: int
    ranking_policy_id: str
    status: HistoricalPrefixRankingStatus
    candidates: tuple[HistoricalPrefixRankingCandidate, ...]


@dataclass(frozen=True, slots=True)
class HistoricalPrefixAnalyticsResult:
    result_schema_version: str
    source_import_identity_sha256: str
    source_manifest_sha256: str
    source_artifact_sha256: str
    dataset_identity: str
    dataset_sha256: str
    lottery_type: HistoricalLotteryType
    supported_prefixes: tuple[int, ...]
    per_draw_metrics: tuple[HistoricalPerDrawPrefixMetrics, ...]
    all_strategy_summaries: tuple[HistoricalStrategyPrefixSummary, ...]
    ranking_groups: tuple[HistoricalPrefixRankingGroup, ...]
    ranking_policy_id: str
    historical_only_disclaimer_id: str


def _input_error(message: str) -> HistoricalPrefixAnalyticsInputError:
    return HistoricalPrefixAnalyticsInputError(message)


def _identity(descriptor: HistoricalStrategyDescriptor) -> HistoricalStrategyIdentity:
    return HistoricalStrategyIdentity(
        strategy_id=descriptor.strategy_id,
        effective_strategy_id=descriptor.effective_strategy_id,
        strategy_version=descriptor.strategy_version,
        replicate=descriptor.replicate,
        identity_kind=descriptor.identity_kind,
        governance_status=descriptor.governance_status,
        alias_of_strategy_id=descriptor.alias_of_strategy_id,
        equivalence_group=descriptor.equivalence_group,
        nested_prefix_supported=descriptor.nested_prefix_supported,
    )


def _draw_identity(draw: HistoricalDrawSnapshot) -> HistoricalDrawIdentity:
    return HistoricalDrawIdentity(
        draw_number=draw.draw_number,
        draw_date=draw.draw_date,
        draw_sha256=draw.draw_sha256,
    )


def _validate_requested_prefixes(prefix_counts: Iterable[int]) -> tuple[int, ...]:
    try:
        requested = tuple(prefix_counts)
    except TypeError as exc:
        raise _input_error("prefix_counts must be an iterable of integers") from exc
    unsupported = tuple(
        prefix
        for prefix in requested
        if type(prefix) is not int or prefix not in SUPPORTED_PREFIX_COUNTS
    )
    if unsupported:
        raise _input_error(f"unsupported prefix count(s): {unsupported}")
    if requested != SUPPORTED_PREFIX_COUNTS:
        raise _input_error(
            f"prefix_counts must be the complete canonical sequence {SUPPORTED_PREFIX_COUNTS}"
        )
    return requested


def _validate_input(
    run_import: HistoricalRunImport,
    prefix_counts: tuple[int, ...],
) -> tuple[
    dict[tuple[str, str, int], HistoricalStrategyDescriptor],
    dict[int, HistoricalDrawSnapshot],
]:
    if type(run_import) is not HistoricalRunImport:
        raise _input_error("run_import must be a HistoricalRunImport")
    if run_import.dataset.lottery_type is not HistoricalLotteryType.BIG_LOTTO:
        raise _input_error("lottery type must be exactly BIG_LOTTO")
    if prefix_counts != SUPPORTED_PREFIX_COUNTS:
        raise _input_error("every supported prefix must be derivable")

    descriptors: dict[tuple[str, str, int], HistoricalStrategyDescriptor] = {}
    for descriptor in run_import.strategy_descriptors:
        if type(descriptor) is not HistoricalStrategyDescriptor:
            raise _input_error("strategy_descriptors contains a malformed descriptor")
        key = (descriptor.strategy_id, descriptor.strategy_version, descriptor.replicate)
        if key in descriptors:
            raise _input_error(f"duplicate exact strategy descriptor: {key!r}")
        descriptors[key] = descriptor

    draws: dict[int, HistoricalDrawSnapshot] = {}
    for draw in run_import.draw_snapshots:
        if type(draw) is not HistoricalDrawSnapshot:
            raise _input_error("draw_snapshots contains a malformed draw")
        if draw.draw_number in draws:
            raise _input_error(f"duplicate draw snapshot: {draw.draw_number}")
        draws[draw.draw_number] = draw

    portfolio_targets: set[tuple[str, str, int, int]] = set()
    for portfolio in run_import.portfolios:
        if type(portfolio) is not HistoricalPortfolio:
            raise _input_error("portfolios contains a malformed portfolio")
        identity_key = (
            portfolio.strategy_id,
            portfolio.strategy_version,
            portfolio.replicate,
        )
        if identity_key not in descriptors:
            raise _input_error(f"portfolio has no exact strategy descriptor: {identity_key!r}")
        if portfolio.target_draw_number not in draws:
            raise _input_error(f"portfolio target draw is unknown: {portfolio.target_draw_number}")
        if portfolio.cutoff_draw_number not in draws:
            raise _input_error(f"portfolio cutoff draw is unknown: {portfolio.cutoff_draw_number}")
        target_key = (*identity_key, portfolio.target_draw_number)
        if target_key in portfolio_targets:
            raise _input_error(f"duplicate exact strategy-target portfolio: {target_key!r}")
        portfolio_targets.add(target_key)
        if type(portfolio.tickets) is not tuple or len(portfolio.tickets) != PORTFOLIO_TICKET_COUNT:
            raise _input_error("every portfolio must contain exactly 20 tickets")
        for expected_position, ticket in enumerate(portfolio.tickets, start=1):
            if type(ticket) is not HistoricalTicket:
                raise _input_error("portfolio contains a malformed ticket identity")
            if ticket.portfolio_position != expected_position:
                raise _input_error("ticket positions must be exactly 1..20 in tuple order")
            try:
                resolve_big_lotto_prize_tier(ticket.main_hit_count, ticket.special_hit)
            except (TypeError, ValueError) as exc:
                raise _input_error(
                    "ticket has a hit signature rejected by the canonical prize resolver"
                ) from exc

    return descriptors, draws


def _tier_count_payload(tier_counts: dict[BigLottoPrizeTierId, int]) -> dict[str, int]:
    return {field: tier_counts[tier_id] for tier_id, field in _TIER_COUNT_FIELD_BY_ID.items()}


def _build_per_draw_metrics(
    *,
    descriptor: HistoricalStrategyDescriptor,
    portfolio: HistoricalPortfolio,
    target: HistoricalDrawSnapshot,
    cutoff: HistoricalDrawSnapshot,
    prefix_count: int,
) -> HistoricalPerDrawPrefixMetrics:
    tickets = portfolio.tickets[:prefix_count]
    best_hit = max(ticket.main_hit_count for ticket in tickets)
    best_position = next(
        ticket.portfolio_position for ticket in tickets if ticket.main_hit_count == best_hit
    )
    tier_counts = {tier_id: 0 for tier_id in BigLottoPrizeTierId}
    no_prize_count = 0
    for ticket in tickets:
        resolved = resolve_big_lotto_prize_tier(ticket.main_hit_count, ticket.special_hit)
        if isinstance(resolved, BigLottoPrizeTier):
            tier_counts[resolved.tier_id] += 1
        else:
            no_prize_count += 1
    winning_count = sum(tier_counts.values())
    strongest = next(
        (tier_id for tier_id in BigLottoPrizeTierId if tier_counts[tier_id]),
        NoPrizeResult.NO_PRIZE,
    )
    return HistoricalPerDrawPrefixMetrics(
        identity=_identity(descriptor),
        prefix_count=prefix_count,
        prefix_ticket_count=len(tickets),
        included_ticket_positions=tuple(ticket.portfolio_position for ticket in tickets),
        best_single_main_hit_count=best_hit,
        best_single_ticket_position=best_position,
        total_main_hit_count=sum(ticket.main_hit_count for ticket in tickets),
        portfolio_success=any(ticket.main_hit_count >= 1 for ticket in tickets),
        m3plus=any(ticket.main_hit_count >= 3 for ticket in tickets),
        m4plus=any(ticket.main_hit_count >= 4 for ticket in tickets),
        m5plus=any(ticket.main_hit_count >= 5 for ticket in tickets),
        m6=any(ticket.main_hit_count == 6 for ticket in tickets),
        special_hit=any(ticket.special_hit for ticket in tickets),
        special_hit_ticket_count=sum(ticket.special_hit for ticket in tickets),
        winning_ticket_count=winning_count,
        no_prize_ticket_count=no_prize_count,
        strongest_winning_tier=strongest,
        target=_draw_identity(target),
        cutoff=_draw_identity(cutoff),
        **_tier_count_payload(tier_counts),
    )


def _sum_field(metrics: tuple[HistoricalPerDrawPrefixMetrics, ...], name: str) -> int:
    return sum(getattr(metric, name) for metric in metrics)


def _empty_summary(
    descriptor: HistoricalStrategyDescriptor,
    prefix_count: int,
) -> HistoricalStrategyPrefixSummary:
    return HistoricalStrategyPrefixSummary(
        identity=_identity(descriptor),
        prefix_count=prefix_count,
        status=HistoricalPrefixSummaryStatus.NO_PORTFOLIOS,
        distinct_draw_count=0,
        replay_ticket_count=0,
        portfolio_success_count=0,
        portfolio_success_rate=ExactRatio.unavailable(),
        sum_best_main_hit_count=0,
        average_best_main_hit_count=ExactRatio.unavailable(),
        sum_total_main_hit_count=0,
        average_total_main_hit_count=ExactRatio.unavailable(),
        max_single_main_hit_count=0,
        max_portfolio_total_main_hit_count=0,
        max_hit_target=None,
        m3plus_draw_count=0,
        m4plus_draw_count=0,
        m5plus_draw_count=0,
        m6_draw_count=0,
        special_hit_draw_count=0,
        special_hit_ticket_count=0,
        winning_draw_count=0,
        winning_ticket_count=0,
        no_prize_ticket_count=0,
        first_prize_ticket_count=0,
        second_prize_ticket_count=0,
        third_prize_ticket_count=0,
        fourth_prize_ticket_count=0,
        fifth_prize_ticket_count=0,
        sixth_prize_ticket_count=0,
        seventh_prize_ticket_count=0,
        general_prize_ticket_count=0,
        ranking_eligible=False,
        ranking_exclusion_reason=HistoricalPrefixRankingExclusionReason.NO_PORTFOLIOS,
    )


def _build_summary(
    descriptor: HistoricalStrategyDescriptor,
    prefix_count: int,
    metrics: tuple[HistoricalPerDrawPrefixMetrics, ...],
) -> HistoricalStrategyPrefixSummary:
    if not metrics:
        return _empty_summary(descriptor, prefix_count)
    draw_count = len(metrics)
    success_count = sum(metric.portfolio_success for metric in metrics)
    sum_best = _sum_field(metrics, "best_single_main_hit_count")
    sum_total = _sum_field(metrics, "total_main_hit_count")
    max_metric = min(
        metrics,
        key=lambda metric: (
            -metric.best_single_main_hit_count,
            -metric.total_main_hit_count,
            metric.target.draw_date,
            metric.target.draw_number,
        ),
    )
    is_alias = descriptor.alias_of_strategy_id is not None
    return HistoricalStrategyPrefixSummary(
        identity=_identity(descriptor),
        prefix_count=prefix_count,
        status=HistoricalPrefixSummaryStatus.ANALYZED,
        distinct_draw_count=draw_count,
        replay_ticket_count=draw_count * prefix_count,
        portfolio_success_count=success_count,
        portfolio_success_rate=ExactRatio(success_count, draw_count),
        sum_best_main_hit_count=sum_best,
        average_best_main_hit_count=ExactRatio(sum_best, draw_count),
        sum_total_main_hit_count=sum_total,
        average_total_main_hit_count=ExactRatio(sum_total, draw_count),
        max_single_main_hit_count=max(metric.best_single_main_hit_count for metric in metrics),
        max_portfolio_total_main_hit_count=max(metric.total_main_hit_count for metric in metrics),
        max_hit_target=max_metric.target,
        m3plus_draw_count=sum(metric.m3plus for metric in metrics),
        m4plus_draw_count=sum(metric.m4plus for metric in metrics),
        m5plus_draw_count=sum(metric.m5plus for metric in metrics),
        m6_draw_count=sum(metric.m6 for metric in metrics),
        special_hit_draw_count=sum(metric.special_hit for metric in metrics),
        special_hit_ticket_count=_sum_field(metrics, "special_hit_ticket_count"),
        winning_draw_count=sum(metric.winning_ticket_count > 0 for metric in metrics),
        winning_ticket_count=_sum_field(metrics, "winning_ticket_count"),
        no_prize_ticket_count=_sum_field(metrics, "no_prize_ticket_count"),
        first_prize_ticket_count=_sum_field(metrics, "first_prize_ticket_count"),
        second_prize_ticket_count=_sum_field(metrics, "second_prize_ticket_count"),
        third_prize_ticket_count=_sum_field(metrics, "third_prize_ticket_count"),
        fourth_prize_ticket_count=_sum_field(metrics, "fourth_prize_ticket_count"),
        fifth_prize_ticket_count=_sum_field(metrics, "fifth_prize_ticket_count"),
        sixth_prize_ticket_count=_sum_field(metrics, "sixth_prize_ticket_count"),
        seventh_prize_ticket_count=_sum_field(metrics, "seventh_prize_ticket_count"),
        general_prize_ticket_count=_sum_field(metrics, "general_prize_ticket_count"),
        ranking_eligible=not is_alias,
        ranking_exclusion_reason=(
            HistoricalPrefixRankingExclusionReason.ALIAS if is_alias else None
        ),
    )


def _compare_ratio_desc(left: ExactRatio, right: ExactRatio) -> int:
    if not left.is_available or not right.is_available:
        raise _input_error("ranking requires available exact ratios")
    left_product = left.numerator * right.denominator
    right_product = right.numerator * left.denominator
    return -1 if left_product > right_product else 1 if left_product < right_product else 0


def _compare_summaries(
    left: HistoricalStrategyPrefixSummary,
    right: HistoricalStrategyPrefixSummary,
) -> int:
    for left_ratio, right_ratio in (
        (left.portfolio_success_rate, right.portfolio_success_rate),
        (left.average_best_main_hit_count, right.average_best_main_hit_count),
        (left.average_total_main_hit_count, right.average_total_main_hit_count),
    ):
        comparison = _compare_ratio_desc(left_ratio, right_ratio)
        if comparison:
            return comparison
    for left_value, right_value in (
        (left.max_single_main_hit_count, right.max_single_main_hit_count),
        (left.max_portfolio_total_main_hit_count, right.max_portfolio_total_main_hit_count),
        (left.distinct_draw_count, right.distinct_draw_count),
    ):
        if left_value != right_value:
            return -1 if left_value > right_value else 1
    left_identity = (
        left.identity.strategy_id,
        left.identity.strategy_version,
        left.identity.replicate,
    )
    right_identity = (
        right.identity.strategy_id,
        right.identity.strategy_version,
        right.identity.replicate,
    )
    return -1 if left_identity < right_identity else 1 if left_identity > right_identity else 0


def _build_ranking_groups(
    summaries: tuple[HistoricalStrategyPrefixSummary, ...],
) -> tuple[HistoricalPrefixRankingGroup, ...]:
    groups: list[HistoricalPrefixRankingGroup] = []
    for prefix_count in RANKING_PREFIX_COUNTS:
        eligible = [
            summary
            for summary in summaries
            if summary.prefix_count == prefix_count and summary.ranking_eligible
        ]
        eligible.sort(key=cmp_to_key(_compare_summaries))
        candidates = tuple(
            HistoricalPrefixRankingCandidate(
                rank=rank,
                identity=summary.identity,
                summary=summary,
                tie_break_provenance=RANKING_TIE_BREAK_PROVENANCE,
            )
            for rank, summary in enumerate(eligible, start=1)
        )
        groups.append(
            HistoricalPrefixRankingGroup(
                prefix_count=prefix_count,
                ranking_policy_id=RANKING_POLICY_ID,
                status=(
                    HistoricalPrefixRankingStatus.RANKED
                    if candidates
                    else HistoricalPrefixRankingStatus.NO_ELIGIBLE_STRATEGIES
                ),
                candidates=candidates,
            )
        )
    return tuple(groups)


def analyze_historical_prefixes(
    run_import: HistoricalRunImport,
    *,
    prefix_counts: Iterable[int] = SUPPORTED_PREFIX_COUNTS,
) -> HistoricalPrefixAnalyticsResult:
    """Analyze all exact identities and canonical prefixes without external state."""

    requested_prefixes = _validate_requested_prefixes(prefix_counts)
    descriptors, draws = _validate_input(run_import, requested_prefixes)

    per_draw: list[HistoricalPerDrawPrefixMetrics] = []
    for portfolio in run_import.portfolios:
        descriptor = descriptors[
            (portfolio.strategy_id, portfolio.strategy_version, portfolio.replicate)
        ]
        target = draws[portfolio.target_draw_number]
        cutoff = draws[portfolio.cutoff_draw_number]
        per_draw.extend(
            _build_per_draw_metrics(
                descriptor=descriptor,
                portfolio=portfolio,
                target=target,
                cutoff=cutoff,
                prefix_count=prefix_count,
            )
            for prefix_count in requested_prefixes
        )
    per_draw_metrics = tuple(per_draw)

    summaries = tuple(
        _build_summary(
            descriptor,
            prefix_count,
            tuple(
                metric
                for metric in per_draw_metrics
                if metric.identity == _identity(descriptor) and metric.prefix_count == prefix_count
            ),
        )
        for descriptor in run_import.strategy_descriptors
        for prefix_count in requested_prefixes
    )
    return HistoricalPrefixAnalyticsResult(
        result_schema_version=RESULT_SCHEMA_VERSION,
        source_import_identity_sha256=run_import.import_identity_sha256,
        source_manifest_sha256=run_import.manifest_sha256,
        source_artifact_sha256=run_import.source.source_artifact_sha256,
        dataset_identity=run_import.dataset.dataset_identity,
        dataset_sha256=run_import.dataset.dataset_sha256,
        lottery_type=run_import.dataset.lottery_type,
        supported_prefixes=SUPPORTED_PREFIX_COUNTS,
        per_draw_metrics=per_draw_metrics,
        all_strategy_summaries=summaries,
        ranking_groups=_build_ranking_groups(summaries),
        ranking_policy_id=RANKING_POLICY_ID,
        historical_only_disclaimer_id=HISTORICAL_ONLY_DISCLAIMER_ID,
    )


__all__ = [
    "HISTORICAL_ONLY_DISCLAIMER_ID",
    "RANKING_POLICY_ID",
    "RANKING_PREFIX_COUNTS",
    "RANKING_TIE_BREAK_PROVENANCE",
    "RESULT_SCHEMA_VERSION",
    "SUPPORTED_PREFIX_COUNTS",
    "ExactRatio",
    "HistoricalDrawIdentity",
    "HistoricalPerDrawPrefixMetrics",
    "HistoricalPrefixAnalyticsInputError",
    "HistoricalPrefixAnalyticsResult",
    "HistoricalPrefixRankingCandidate",
    "HistoricalPrefixRankingExclusionReason",
    "HistoricalPrefixRankingGroup",
    "HistoricalPrefixRankingStatus",
    "HistoricalPrefixSummaryStatus",
    "HistoricalStrategyIdentity",
    "HistoricalStrategyPrefixSummary",
    "analyze_historical_prefixes",
]
