"""Synthetic/math verification for the frozen L2 pairwise null-Z2 x Bayes-changepoint design.

Design `B649_PAIRWISE_NULL_Z2_BAYES_CHANGEPOINT_WEIGHTED_SCORE_50_V1`. Every
expected value below is derived from the frozen formula text itself
(re-derived independently in this file via `math.comb`/`math.factorial`,
never by importing the module's own internal helpers) or from a synthetic
fixture constructed so the exact answer is knowable by hand. Nothing here
reads real draw history, a replay result, or any empirical performance
value.
"""

from __future__ import annotations

import json
import math
from fractions import Fraction

import pytest

from lottolab.research import (
    biglotto_l2_pairwise_entropy_bayesian_weighted_score_candidate_batch_r1 as l2pw,
)

MINIMUM_HISTORY = l2pw.MINIMUM_HISTORY
PairwiseNullZ2BayesChangepointPrediction = l2pw.PairwiseNullZ2BayesChangepointPrediction
bayes_changepoint_bma_50 = l2pw.bayes_changepoint_bma_50
beta_evidence = l2pw.beta_evidence
official_null_z2_50 = l2pw.official_null_z2_50
pairwise_score_50 = l2pw.pairwise_score_50
ranked_pool_50 = l2pw.ranked_pool_50
predict = l2pw.predict_biglotto_l2_pairwise_null_z2_bayes_changepoint_weighted_score_50

#: A neutral 6-number draw that never appears in any test's numbers under study.
FILLER: tuple[int, ...] = (44, 45, 46, 47, 48, 49)

#: 25 numbers disjoint from FILLER and from every dominant/edge target this
#: file uses, for building windows where every "other" number's count stays
#: far below the number under study.
OTHER_POOL = list(range(20, 45))


def _signal_draw(target: int) -> tuple[int, ...]:
    """FILLER with its first slot swapped for `target`: only `target` (up

    by one) and 44 (down by one) ever change count relative to FILLER --
    every other number is untouched.
    """

    assert target not in FILLER
    return (target, 45, 46, 47, 48, 49)


def _dominant_window(target: int) -> tuple[tuple[int, ...], ...]:
    """50 draws where `target` appears in every draw (count 50, split 25/25)

    and every other number appears in at most 10 of the 50 draws -- built so
    `target` is unambiguously the most frequent number in the window by a
    wide margin, verified numerically before use (see task notes).
    """

    assert target not in OTHER_POOL
    draws: list[tuple[int, ...]] = []
    for i in range(50):
        shift = (i * 5) % 25
        fillers = tuple(OTHER_POOL[(shift + j) % 25] for j in range(5))
        draws.append((target, *fillers))
    return tuple(draws)


def _bayes_window(k_old: int, k_recent: int, target: int) -> tuple[tuple[int, ...], ...]:
    """A 50-draw window where `target` appears in exactly `k_old` of the

    older 25 draws and `k_recent` of the recent 25 draws.
    """

    older = [_signal_draw(target)] * k_old + [FILLER] * (25 - k_old)
    recent = [_signal_draw(target)] * k_recent + [FILLER] * (25 - k_recent)
    return tuple(older + recent)


def _reference_beta_evidence(alpha: int, beta: int, k: int, n: int) -> Fraction:
    """BETA_EVIDENCE via a different closed form than the module under test:

    C(alpha+k-1, k) * C(beta+n-k-1, n-k) / C(alpha+beta+n-1, n) -- an
    independent algebraic rearrangement of the same Beta-Binomial marginal
    likelihood, not a copy of the module's own `_beta_function` factorial
    path.
    """

    return Fraction(
        math.comb(alpha + k - 1, k) * math.comb(beta + n - k - 1, n - k),
        math.comb(alpha + beta + n - 1, n),
    )


def _reference_posterior_m1(k_old: int, k_recent: int) -> Fraction:
    alpha, beta = 6, 43
    k_total = k_old + k_recent
    evidence_m0 = _reference_beta_evidence(alpha, beta, k_total, 50)
    evidence_m1 = _reference_beta_evidence(alpha, beta, k_old, 25) * _reference_beta_evidence(
        alpha, beta, k_recent, 25
    )
    return evidence_m1 / (evidence_m0 + evidence_m1)


# --- 1. minimum-history boundary; 2. insufficient-history behavior --------


def test_minimum_history_boundary() -> None:
    assert predict([FILLER] * (MINIMUM_HISTORY - 1)) is None

    result = predict([FILLER] * MINIMUM_HISTORY)
    assert result is not None
    assert len(result.ticket) == 6
    assert result.ticket == tuple(sorted(result.ticket))
    assert len(result.ranked_pool) == 49
    assert set(result.ranked_pool) == set(range(1, 50))
    assert set(result.ticket) == set(result.ranked_pool[:6])


def test_insufficient_history_various_small_sizes_return_none() -> None:
    for size in (0, 1, 50, 100, 700, MINIMUM_HISTORY - 1):
        assert predict([FILLER] * size) is None


# --- 3. simple pair-count/null case; 4. positive/negative deviation -------


def test_official_null_z2_50_simple_count_case_matches_closed_form() -> None:
    window = tuple([_signal_draw(7)] * 10 + [FILLER] * 40)
    assert official_null_z2_50(window, 7) == Fraction((49 * 10 - 6 * 50) ** 2, 258 * 50)


def test_official_null_z2_50_positive_and_negative_deviation() -> None:
    window = tuple(
        [_signal_draw(11)] * 20 + [_signal_draw(13)] * 2 + [_signal_draw(17)] * 6 + [FILLER] * 22
    )

    z2_above_expected = official_null_z2_50(window, 11)  # count=20: deviation is positive
    z2_below_expected = official_null_z2_50(window, 13)  # count=2: deviation is negative
    z2_near_expected = official_null_z2_50(window, 17)  # count=6: closest to the null mean

    assert z2_above_expected == Fraction((49 * 20 - 6 * 50) ** 2, 258 * 50)
    assert z2_below_expected == Fraction((49 * 2 - 6 * 50) ** 2, 258 * 50)
    assert z2_near_expected == Fraction((49 * 6 - 6 * 50) ** 2, 258 * 50)

    assert (49 * 20 - 6 * 50) > 0
    assert (49 * 2 - 6 * 50) < 0
    assert z2_near_expected < z2_above_expected
    assert z2_near_expected < z2_below_expected


# --- 5. Bayesian component behavior ----------------------------------------


def test_beta_evidence_matches_independent_closed_form() -> None:
    for k, n in [(0, 25), (5, 25), (25, 25), (0, 50), (6, 50), (50, 50), (12, 25), (37, 50)]:
        assert beta_evidence(6, 43, k, n) == _reference_beta_evidence(6, 43, k, n)


def test_beta_evidence_uniform_prior_matches_known_uniform_result() -> None:
    # Beta(1, 1) is uniform; the textbook Beta-Binomial marginal under a
    # uniform prior is 1/(n+1) for every k -- a fact independent of both
    # closed forms above, so this check depends on neither.
    for n in (1, 5, 25, 50):
        for k in range(n + 1):
            assert beta_evidence(1, 1, k, n) == Fraction(1, n + 1)


def test_beta_evidence_rejects_k_out_of_range() -> None:
    with pytest.raises(ValueError, match="k must lie"):
        beta_evidence(6, 43, -1, 25)
    with pytest.raises(ValueError, match="k must lie"):
        beta_evidence(6, 43, 26, 25)


# --- 6. changepoint weighting behavior -------------------------------------


def test_bayes_changepoint_posterior_prefers_balanced_split_at_equal_total() -> None:
    # At equal total count, this frozen construction assigns a HIGHER
    # changepoint-model (M1) posterior to the more evenly balanced
    # old/recent split than to a one-sided split with the same total --
    # verified directly against the independent closed form, not asserted
    # from intuition (a naive "sharper split -> more changepoint evidence"
    # guess is false for this prior/window combination).
    lopsided = bayes_changepoint_bma_50(_bayes_window(0, 10, 29), 29)
    balanced = bayes_changepoint_bma_50(_bayes_window(5, 5, 31), 31)

    assert lopsided.posterior_m1 == _reference_posterior_m1(0, 10)
    assert balanced.posterior_m1 == _reference_posterior_m1(5, 5)
    assert balanced.posterior_m1 > lopsided.posterior_m1


# --- 7. combined weighted-score behavior; 9. candidate construction -------


def test_pairwise_score_dominant_number_achieves_maximum_score_of_one() -> None:
    window = _dominant_window(5)
    scores = pairwise_score_50(window)
    assert scores[5] == Fraction(1, 1)
    assert ranked_pool_50(window)[0] == 5

    history = [FILLER] * 700 + list(window)
    prediction = predict(history)
    assert prediction is not None
    assert 5 in prediction.ticket
    assert prediction.ranked_pool[0] == 5


def test_ranked_pool_cardinality_and_domain() -> None:
    pool = ranked_pool_50(_dominant_window(5))
    assert len(pool) == 49
    assert len(set(pool)) == 49
    assert set(pool) == set(range(1, 50))


# --- 8. tie condition and exact tie-break -----------------------------------


def test_tied_numbers_get_equal_score_and_ascending_number_tie_break() -> None:
    # Rank normalization operates on POSITION (a strict 1..49 permutation),
    # not raw score, so two numbers with an IDENTICAL raw Z2/BMA count do
    # NOT tie in PAIRWISE_SCORE: the ascending-number tie-break still gives
    # them adjacent, unequal positions. A genuine fused-score tie instead
    # needs matching *positions sums* across the two parents -- verified
    # here with 21 appearing once in the older half (nothing recent) against
    # 23 appearing once in the recent half (nothing older): same total count
    # (so equal raw Z2), but different recency shifts BMA enough to land on
    # an exact tie once both normalized scores are averaged.
    older = [_signal_draw(21)] * 1 + [FILLER] * 24
    recent = [_signal_draw(23)] * 1 + [FILLER] * 24
    window = tuple(older + recent)

    scores = pairwise_score_50(window)
    assert scores[21] == scores[23] == Fraction(7, 16)

    pool = ranked_pool_50(window)
    assert pool.index(21) < pool.index(23)


# --- 10. edge lottery numbers -----------------------------------------------


def test_edge_lottery_numbers_reach_top_rank_without_off_by_one() -> None:
    for edge_number in (1, 49):
        pool = ranked_pool_50(_dominant_window(edge_number))
        assert pool[0] == edge_number
        assert set(pool) == set(range(1, 50))


# --- 11. deterministic repeated execution -----------------------------------


def _canonical_serialization(prediction: PairwiseNullZ2BayesChangepointPrediction) -> str:
    return json.dumps(
        {
            "ticket": list(prediction.ticket),
            "ranked_pool": list(prediction.ranked_pool),
            "scores": [
                [number, str(prediction.scores[number])] for number in sorted(prediction.scores)
            ],
        },
        sort_keys=True,
    )


def test_predict_is_deterministic_across_repeated_calls() -> None:
    history = [FILLER] * 700 + list(_dominant_window(5))

    first = predict(history)
    second = predict(history)

    assert first is not None
    assert second is not None
    assert first == second
    assert _canonical_serialization(first) == _canonical_serialization(second)


# --- 12. malformed/invalid input --------------------------------------------


def test_window_length_mismatch_rejected_by_parent_functions() -> None:
    short_window = tuple([FILLER] * 49)
    with pytest.raises(ValueError, match="exactly 50"):
        official_null_z2_50(short_window, 1)
    with pytest.raises(ValueError, match="exactly 50"):
        bayes_changepoint_bma_50(short_window, 1)
    with pytest.raises(ValueError, match="exactly 50"):
        pairwise_score_50(short_window)


def test_number_out_of_domain_rejected_by_parent_functions() -> None:
    window = tuple([FILLER] * 50)
    with pytest.raises(ValueError, match=r"1\.\.49"):
        official_null_z2_50(window, 0)
    with pytest.raises(ValueError, match=r"1\.\.49"):
        official_null_z2_50(window, 50)
    with pytest.raises(ValueError, match=r"1\.\.49"):
        bayes_changepoint_bma_50(window, 50)


def test_malformed_draw_wrong_length_raises() -> None:
    bad_history = [FILLER] * (MINIMUM_HISTORY - 1) + [(1, 2, 3, 4, 5)]
    with pytest.raises(ValueError, match="exactly 6"):
        predict(bad_history)


def test_malformed_draw_duplicate_number_raises() -> None:
    bad_history = [FILLER] * (MINIMUM_HISTORY - 1) + [(1, 1, 2, 3, 4, 5)]
    with pytest.raises(ValueError, match="distinct"):
        predict(bad_history)


def test_malformed_draw_out_of_range_number_raises() -> None:
    bad_history_low = [FILLER] * (MINIMUM_HISTORY - 1) + [(0, 2, 3, 4, 5, 6)]
    with pytest.raises(ValueError, match=r"1\.\.49"):
        predict(bad_history_low)

    bad_history_high = [FILLER] * (MINIMUM_HISTORY - 1) + [(1, 2, 3, 4, 5, 50)]
    with pytest.raises(ValueError, match=r"1\.\.49"):
        predict(bad_history_high)


def test_malformed_draw_deep_in_unused_history_still_validated() -> None:
    # A malformed row far outside the trailing 50-draw window (the oldest
    # row of 751) must still be rejected: the whole causal history is
    # validated, not only the slice actually scored.
    bad_history = [(1, 2, 3, 4, 5, 6, 7)] + [FILLER] * MINIMUM_HISTORY
    with pytest.raises(ValueError, match="exactly 6"):
        predict(bad_history)
