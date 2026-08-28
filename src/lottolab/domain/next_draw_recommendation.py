"""Boundary contract for the Next-Draw Recommendation product surface.

This module composes existing descriptive/backtest evidence into a ranking
of strategies *within one native-ticket-count bucket*; it does not replace,
reinterpret, or mutate any existing descriptive authority. In particular:

* ``replay_portfolio_ranking.py``'s ``ticket_count`` ranks combinations of
  *distinct strategies* forming one portfolio -- an unrelated axis. It is
  never reused as native-ticket-count evidence.
* The B649 multi-ticket records (``prefix_count`` in {5, 10, 15, 20}) rank
  strategies by top-K ranked-number pool coverage -- also an unrelated axis
  from one strategy's own native ticket output. It is never silently
  substituted for native-ticket-count evidence either.

A strategy's rank under ``NEXT_DRAW_ROBUSTNESS_V1`` is a descriptive
statement about its own real, causally-replayed historical hit-tier
performance against an exact random baseline, for its own native ticket
output, within one native_ticket_count bucket. It is not a predictive or
future-performance claim: recommendation != proof of future edge. Higher
rank never implies a proven edge, and the live "as of now" ticket
preview is display-only -- it is never a ranking input.

This surface is a PREVIEW: it is computed from causal history up to the
latest completed draw and is never bound or sealed to a future target.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from fractions import Fraction

RECOMMENDATION_POLICY_ID = "NEXT_DRAW_ROBUSTNESS_V1"
RECOMMENDATION_DOMAIN_SCHEMA_VERSION = "1.0.0"

NATIVE_TICKET_COUNT_BUCKETS: tuple[int, ...] = (1, 2, 3, 5, 10, 20)
TOP_N = 3

RANKING_WINDOW_KINDS: tuple[str, ...] = ("WINDOW_50", "WINDOW_300", "WINDOW_750")
TIE_BREAK_WINDOW_ORDER: tuple[str, ...] = ("WINDOW_750", "WINDOW_300", "WINDOW_50")


class RecommendationContractError(ValueError):
    """Base class for closed-contract validation failures in this module."""


class BucketAvailabilityStatus(StrEnum):
    AVAILABLE = "AVAILABLE"
    LIMITED_POOL = "LIMITED_POOL"
    UNAVAILABLE = "UNAVAILABLE"


class RecommendationExclusionReason(StrEnum):
    NOT_EXECUTABLE = "NOT_EXECUTABLE"
    WRONG_LOTTERY_TYPE = "WRONG_LOTTERY_TYPE"
    TICKET_COUNT_MISMATCH = "TICKET_COUNT_MISMATCH"
    EXECUTION_UNREACHABLE = "EXECUTION_UNREACHABLE"
    EVIDENCE_UNAVAILABLE = "EVIDENCE_UNAVAILABLE"
    INSUFFICIENT_WINDOW_HISTORY = "INSUFFICIENT_WINDOW_HISTORY"


def bucket_availability(
    candidate_count: int, *, top_n: int = TOP_N
) -> BucketAvailabilityStatus:
    """Classify one native-ticket-count bucket's real candidate pool size.

    A small pool is surfaced transparently (``LIMITED_POOL``), never hidden:
    a bucket whose candidate count is at or below ``top_n`` still shows every
    candidate it has, just with no elimination effect.
    """

    if candidate_count < 0:
        raise RecommendationContractError("candidate_count must be non-negative")
    if candidate_count == 0:
        return BucketAvailabilityStatus.UNAVAILABLE
    if candidate_count <= top_n:
        return BucketAvailabilityStatus.LIMITED_POOL
    return BucketAvailabilityStatus.AVAILABLE


@dataclass(frozen=True, slots=True)
class RecommendationWindowMetric:
    """One window's observed-vs-random evidence for one strategy.

    Mirrors the exact-Fraction, all-or-nothing invariant already enforced by
    ``base_method_evaluation.MetricCell``: a window either has none of
    (observed_rate, random_baseline_rate, delta_vs_random), or all three,
    and the delta is always exactly the difference of the other two.
    """

    window_kind: str
    eligible_draw_count: int
    window_complete: bool
    observed_rate: Fraction | None
    random_baseline_rate: Fraction | None
    delta_vs_random: Fraction | None

    def __post_init__(self) -> None:
        if not self.window_kind.strip():
            raise RecommendationContractError("window_kind must not be blank")
        if self.eligible_draw_count < 0:
            raise RecommendationContractError("eligible_draw_count must be non-negative")
        present = (
            self.observed_rate is not None,
            self.random_baseline_rate is not None,
            self.delta_vs_random is not None,
        )
        if len(set(present)) != 1:
            raise RecommendationContractError(
                "observed_rate, random_baseline_rate, and delta_vs_random "
                "must be all-present or all-absent"
            )
        if all(present):
            assert self.observed_rate is not None
            assert self.random_baseline_rate is not None
            assert self.delta_vs_random is not None
            if self.delta_vs_random != self.observed_rate - self.random_baseline_rate:
                raise RecommendationContractError(
                    "delta_vs_random must equal observed_rate - random_baseline_rate"
                )


@dataclass(frozen=True, slots=True)
class RecommendationCandidate:
    """One ranked strategy within one native-ticket-count bucket."""

    rank: int
    strategy_id: str
    strategy_name: str
    native_ticket_count: int
    windows: tuple[RecommendationWindowMetric, ...]
    cross_window_rank_sum: int | None

    def __post_init__(self) -> None:
        if self.rank < 1:
            raise RecommendationContractError("rank must be >= 1")
        if not self.strategy_id.strip():
            raise RecommendationContractError("strategy_id must not be blank")
        if self.native_ticket_count < 1:
            raise RecommendationContractError("native_ticket_count must be >= 1")
        window_kinds = [metric.window_kind for metric in self.windows]
        if len(window_kinds) != len(set(window_kinds)):
            raise RecommendationContractError("windows must have unique window_kind values")


@dataclass(frozen=True, slots=True)
class RecommendationExclusion:
    """One candidate excluded from ranking, with a transparent reason."""

    strategy_id: str
    reason: RecommendationExclusionReason
    detail: str = ""

    def __post_init__(self) -> None:
        if not self.strategy_id.strip():
            raise RecommendationContractError("strategy_id must not be blank")


@dataclass(frozen=True, slots=True)
class RecommendationBucketView:
    """One native-ticket-count bucket's complete recommendation projection."""

    native_ticket_count: int
    availability: BucketAvailabilityStatus
    total_candidate_count: int
    ranked: tuple[RecommendationCandidate, ...]
    excluded: tuple[RecommendationExclusion, ...]

    def __post_init__(self) -> None:
        if self.native_ticket_count not in NATIVE_TICKET_COUNT_BUCKETS:
            raise RecommendationContractError(
                f"native_ticket_count must be one of {NATIVE_TICKET_COUNT_BUCKETS}"
            )
        if self.total_candidate_count < 0:
            raise RecommendationContractError("total_candidate_count must be non-negative")
        expected = bucket_availability(self.total_candidate_count)
        if self.availability is not expected:
            raise RecommendationContractError(
                f"availability {self.availability} contradicts "
                f"total_candidate_count={self.total_candidate_count} "
                f"(expected {expected})"
            )
        ranks = [candidate.rank for candidate in self.ranked]
        if ranks != list(range(1, len(ranks) + 1)):
            raise RecommendationContractError("ranked candidates must be contiguously ranked from 1")
        if len(self.ranked) + len(self.excluded) != self.total_candidate_count:
            raise RecommendationContractError(
                "ranked + excluded counts must equal total_candidate_count"
            )


def _tie_break_key(metric: RecommendationWindowMetric | None) -> tuple[int, Fraction]:
    """Order by descending delta_vs_random; a missing metric sorts last."""

    if metric is None or metric.delta_vs_random is None:
        return (1, Fraction(0))
    return (0, -metric.delta_vs_random)


def _window_rank_map(
    strategy_ids: Sequence[str],
    window_kind: str,
    metrics_by_strategy: Mapping[str, Mapping[str, RecommendationWindowMetric]],
) -> dict[str, int]:
    """Rank strategy_ids within one window by descending delta_vs_random.

    A strategy with no evaluable metric for this window ranks worst (tied at
    one past the last scored strategy), never excluded from the rank map.
    """

    scored: list[tuple[str, Fraction]] = []
    unscored: list[str] = []
    for strategy_id in strategy_ids:
        metric = metrics_by_strategy.get(strategy_id, {}).get(window_kind)
        if metric is not None and metric.delta_vs_random is not None:
            scored.append((strategy_id, metric.delta_vs_random))
        else:
            unscored.append(strategy_id)
    scored.sort(key=lambda pair: pair[1], reverse=True)
    ranks: dict[str, int] = {
        strategy_id: index for index, (strategy_id, _delta) in enumerate(scored, start=1)
    }
    worst_rank = len(scored) + 1
    for strategy_id in unscored:
        ranks[strategy_id] = worst_rank
    return ranks


def rank_candidate_order(
    strategy_ids: Sequence[str],
    metrics_by_strategy: Mapping[str, Mapping[str, RecommendationWindowMetric]],
) -> tuple[str, ...]:
    """Order strategy_ids under the frozen ``NEXT_DRAW_ROBUSTNESS_V1`` rule.

    Primary key: the sum of per-window ranks over WINDOW_50/300/750 (lower is
    better; a strategy with no evaluable metric for a window is ranked worst
    within that window, never dropped). Ties break on raw delta_vs_random at
    WINDOW_750 first, then WINDOW_300, then WINDOW_50 -- higher delta wins.
    """

    per_window_ranks = {
        window_kind: _window_rank_map(strategy_ids, window_kind, metrics_by_strategy)
        for window_kind in RANKING_WINDOW_KINDS
    }

    def sort_key(strategy_id: str) -> tuple[object, ...]:
        rank_sum = sum(
            per_window_ranks[window_kind][strategy_id] for window_kind in RANKING_WINDOW_KINDS
        )
        tie_break = tuple(
            _tie_break_key(metrics_by_strategy.get(strategy_id, {}).get(window_kind))
            for window_kind in TIE_BREAK_WINDOW_ORDER
        )
        return (rank_sum, *tie_break)

    return tuple(sorted(strategy_ids, key=sort_key))


def cross_window_rank_sum(
    strategy_id: str,
    metrics_by_strategy: Mapping[str, Mapping[str, RecommendationWindowMetric]],
    all_strategy_ids: Sequence[str],
) -> int:
    """Return one strategy's displayed rank-sum (for the "why #1?" explainer)."""

    per_window_ranks = {
        window_kind: _window_rank_map(all_strategy_ids, window_kind, metrics_by_strategy)
        for window_kind in RANKING_WINDOW_KINDS
    }
    return sum(per_window_ranks[window_kind][strategy_id] for window_kind in RANKING_WINDOW_KINDS)


__all__ = [
    "NATIVE_TICKET_COUNT_BUCKETS",
    "RANKING_WINDOW_KINDS",
    "RECOMMENDATION_DOMAIN_SCHEMA_VERSION",
    "RECOMMENDATION_POLICY_ID",
    "TIE_BREAK_WINDOW_ORDER",
    "TOP_N",
    "BucketAvailabilityStatus",
    "RecommendationBucketView",
    "RecommendationCandidate",
    "RecommendationContractError",
    "RecommendationExclusion",
    "RecommendationExclusionReason",
    "RecommendationWindowMetric",
    "bucket_availability",
    "cross_window_rank_sum",
    "rank_candidate_order",
]
