"""Domain contract coverage for Next-Draw Recommendation (P0)."""

from __future__ import annotations

from fractions import Fraction

import pytest

from lottolab.domain.next_draw_recommendation import (
    NATIVE_TICKET_COUNT_BUCKETS,
    TOP_N,
    BucketAvailabilityStatus,
    RecommendationBucketView,
    RecommendationCandidate,
    RecommendationContractError,
    RecommendationExclusion,
    RecommendationExclusionReason,
    RecommendationWindowMetric,
    bucket_availability,
    cross_window_rank_sum,
    rank_candidate_order,
)


def _metric(
    window_kind: str,
    *,
    n: int = 750,
    observed: Fraction | None = None,
    baseline: Fraction | None = None,
    complete: bool = True,
) -> RecommendationWindowMetric:
    delta = None if observed is None else observed - baseline
    return RecommendationWindowMetric(
        window_kind=window_kind,
        eligible_draw_count=n,
        window_complete=complete,
        observed_rate=observed,
        random_baseline_rate=baseline,
        delta_vs_random=delta,
    )


class TestBucketAvailability:
    def test_zero_candidates_is_unavailable(self) -> None:
        assert bucket_availability(0) is BucketAvailabilityStatus.UNAVAILABLE

    def test_at_or_below_top_n_is_limited_pool(self) -> None:
        assert bucket_availability(1) is BucketAvailabilityStatus.LIMITED_POOL
        assert bucket_availability(TOP_N) is BucketAvailabilityStatus.LIMITED_POOL

    def test_above_top_n_is_available(self) -> None:
        assert bucket_availability(TOP_N + 1) is BucketAvailabilityStatus.AVAILABLE

    def test_negative_count_rejected(self) -> None:
        with pytest.raises(RecommendationContractError):
            bucket_availability(-1)


class TestRecommendationWindowMetric:
    def test_all_present_and_consistent_is_valid(self) -> None:
        metric = _metric("WINDOW_50", observed=Fraction(1, 10), baseline=Fraction(1, 12))
        assert metric.delta_vs_random == Fraction(1, 10) - Fraction(1, 12)

    def test_all_absent_is_valid(self) -> None:
        _metric("WINDOW_50", complete=False)  # must not raise

    def test_partial_presence_is_rejected(self) -> None:
        with pytest.raises(RecommendationContractError):
            RecommendationWindowMetric(
                window_kind="WINDOW_50",
                eligible_draw_count=50,
                window_complete=True,
                observed_rate=Fraction(1, 10),
                random_baseline_rate=None,
                delta_vs_random=None,
            )

    def test_delta_must_equal_observed_minus_baseline(self) -> None:
        with pytest.raises(RecommendationContractError):
            RecommendationWindowMetric(
                window_kind="WINDOW_50",
                eligible_draw_count=50,
                window_complete=True,
                observed_rate=Fraction(1, 10),
                random_baseline_rate=Fraction(1, 12),
                delta_vs_random=Fraction(999),
            )


class TestRecommendationBucketView:
    def _candidate(self, rank: int, strategy_id: str) -> RecommendationCandidate:
        return RecommendationCandidate(
            rank=rank,
            strategy_id=strategy_id,
            strategy_name=strategy_id,
            native_ticket_count=2,
            windows=(_metric("WINDOW_750", observed=Fraction(1, 10), baseline=Fraction(1, 12)),),
            cross_window_rank_sum=rank,
            highest_historical_prize_label=None,
        )

    def test_valid_view_round_trips(self) -> None:
        view = RecommendationBucketView(
            native_ticket_count=2,
            availability=BucketAvailabilityStatus.AVAILABLE,
            total_candidate_count=5,
            ranked=(self._candidate(1, "a"), self._candidate(2, "b")),
            excluded=(
                RecommendationExclusion("c", RecommendationExclusionReason.NOT_EXECUTABLE),
                RecommendationExclusion("d", RecommendationExclusionReason.EVIDENCE_UNAVAILABLE),
                RecommendationExclusion("e", RecommendationExclusionReason.TICKET_COUNT_MISMATCH),
            ),
        )
        assert view.availability is BucketAvailabilityStatus.AVAILABLE

    def test_native_ticket_count_must_be_a_known_bucket(self) -> None:
        with pytest.raises(RecommendationContractError):
            RecommendationBucketView(
                native_ticket_count=7,
                availability=BucketAvailabilityStatus.UNAVAILABLE,
                total_candidate_count=0,
                ranked=(),
                excluded=(),
            )

    def test_availability_must_match_total_candidate_count(self) -> None:
        with pytest.raises(RecommendationContractError):
            RecommendationBucketView(
                native_ticket_count=2,
                availability=BucketAvailabilityStatus.AVAILABLE,
                total_candidate_count=1,
                ranked=(self._candidate(1, "a"),),
                excluded=(),
            )

    def test_ranks_must_be_contiguous_from_one(self) -> None:
        with pytest.raises(RecommendationContractError):
            RecommendationBucketView(
                native_ticket_count=2,
                availability=BucketAvailabilityStatus.LIMITED_POOL,
                total_candidate_count=1,
                ranked=(self._candidate(2, "a"),),
                excluded=(),
            )

    def test_ranked_plus_excluded_must_equal_total(self) -> None:
        with pytest.raises(RecommendationContractError):
            RecommendationBucketView(
                native_ticket_count=2,
                availability=BucketAvailabilityStatus.LIMITED_POOL,
                total_candidate_count=5,
                ranked=(self._candidate(1, "a"),),
                excluded=(),
            )


class TestRankCandidateOrder:
    def test_higher_delta_at_750_wins_when_rank_sums_tie(self) -> None:
        # a: rank 1 at every window (rank_sum=3). b: rank 2 at every window (rank_sum=6).
        # a must win outright -- this is not a tie case, just a sanity check.
        metrics = {
            "a": {
                "WINDOW_50": _metric("WINDOW_50", observed=Fraction(2, 10), baseline=Fraction(1, 12)),
                "WINDOW_300": _metric("WINDOW_300", observed=Fraction(2, 10), baseline=Fraction(1, 12)),
                "WINDOW_750": _metric("WINDOW_750", observed=Fraction(2, 10), baseline=Fraction(1, 12)),
            },
            "b": {
                "WINDOW_50": _metric("WINDOW_50", observed=Fraction(1, 10), baseline=Fraction(1, 12)),
                "WINDOW_300": _metric("WINDOW_300", observed=Fraction(1, 10), baseline=Fraction(1, 12)),
                "WINDOW_750": _metric("WINDOW_750", observed=Fraction(1, 10), baseline=Fraction(1, 12)),
            },
        }
        assert rank_candidate_order(["b", "a"], metrics) == ("a", "b")

    def test_tie_break_prefers_higher_750_delta(self) -> None:
        # With exactly 2 candidates a rank-sum tie is mathematically impossible
        # (per-window ranks are the complementary pair {1,2}, summing to 3 over
        # any 3 windows regardless of split). Three candidates are required to
        # construct a genuine tie between two of them:
        #   WINDOW_50/300:  b > a > c  (ranks a=2, b=1, c=3 each window)
        #   WINDOW_750:     a > c > b  (ranks a=1, b=3, c=2)
        #   rank_sum: a=2+2+1=5, b=1+1+3=5 (TIE), c=3+3+2=8
        # a and b tie on rank_sum; a's WINDOW_750 delta (0.5) beats b's (0.1),
        # so a must be placed ahead of b.
        zero = Fraction(0)
        metrics = {
            "a": {
                "WINDOW_50": _metric("WINDOW_50", observed=Fraction(3, 10), baseline=zero),
                "WINDOW_300": _metric("WINDOW_300", observed=Fraction(3, 10), baseline=zero),
                "WINDOW_750": _metric("WINDOW_750", observed=Fraction(5, 10), baseline=zero),
            },
            "b": {
                "WINDOW_50": _metric("WINDOW_50", observed=Fraction(5, 10), baseline=zero),
                "WINDOW_300": _metric("WINDOW_300", observed=Fraction(5, 10), baseline=zero),
                "WINDOW_750": _metric("WINDOW_750", observed=Fraction(1, 10), baseline=zero),
            },
            "c": {
                "WINDOW_50": _metric("WINDOW_50", observed=Fraction(1, 10), baseline=zero),
                "WINDOW_300": _metric("WINDOW_300", observed=Fraction(1, 10), baseline=zero),
                "WINDOW_750": _metric("WINDOW_750", observed=Fraction(3, 10), baseline=zero),
            },
        }
        assert cross_window_rank_sum("a", metrics, ["a", "b", "c"]) == 5
        assert cross_window_rank_sum("b", metrics, ["a", "b", "c"]) == 5
        assert rank_candidate_order(["c", "b", "a"], metrics) == ("a", "b", "c")

    def test_missing_metric_ranks_worst_but_is_not_dropped(self) -> None:
        metrics = {
            "a": {
                "WINDOW_50": _metric("WINDOW_50", observed=Fraction(2, 10), baseline=Fraction(1, 12)),
                "WINDOW_300": _metric("WINDOW_300", observed=Fraction(2, 10), baseline=Fraction(1, 12)),
                "WINDOW_750": _metric("WINDOW_750", observed=Fraction(2, 10), baseline=Fraction(1, 12)),
            },
            "b": {},  # no evaluable window at all (e.g. INSUFFICIENT_WINDOW_HISTORY everywhere)
        }
        order = rank_candidate_order(["a", "b"], metrics)
        assert order == ("a", "b")
        assert "b" in order  # transparency: excluded-from-evidence is not excluded-from-listing

    def test_cross_window_rank_sum_matches_manual_computation(self) -> None:
        metrics = {
            "a": {
                "WINDOW_50": _metric("WINDOW_50", observed=Fraction(2, 10), baseline=Fraction(1, 12)),
                "WINDOW_300": _metric("WINDOW_300", observed=Fraction(2, 10), baseline=Fraction(1, 12)),
                "WINDOW_750": _metric("WINDOW_750", observed=Fraction(2, 10), baseline=Fraction(1, 12)),
            },
            "b": {
                "WINDOW_50": _metric("WINDOW_50", observed=Fraction(1, 10), baseline=Fraction(1, 12)),
                "WINDOW_300": _metric("WINDOW_300", observed=Fraction(1, 10), baseline=Fraction(1, 12)),
                "WINDOW_750": _metric("WINDOW_750", observed=Fraction(1, 10), baseline=Fraction(1, 12)),
            },
        }
        assert cross_window_rank_sum("a", metrics, ["a", "b"]) == 3
        assert cross_window_rank_sum("b", metrics, ["a", "b"]) == 6


class TestConstants:
    def test_buckets_and_top_n_are_frozen(self) -> None:
        assert NATIVE_TICKET_COUNT_BUCKETS == (1, 2, 3, 5, 10, 20)
        assert TOP_N == 3
