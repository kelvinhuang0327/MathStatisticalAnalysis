"""BIGLOTTO Level-2 pairwise candidate: frozen official-null-Z2 x Bayes-changepoint fusion.

Implements the frozen design `B649_PAIRWISE_NULL_Z2_BAYES_CHANGEPOINT_WEIGHTED_SCORE_50_V1`
(semantic signature `259e140c70571b37e15f326688ddf5f4a0e18ba0d1982f8098565232ee375508`,
selected gap id `BMSGV1_L2_PAIRWISE_378b7fc29066cbc8`) exactly as frozen in
`.task-data/BIGLOTTO_L2_PAIRWISE_FRONTIER_RECONSTRUCTION_AND_NEXT_DESIGN_FREEZE_R1/`.
This module does not choose or tune any of its own parameters.

The two parent scores live on unrelated scales -- an unbounded chi-square-like
deviation statistic versus a `[0, 1]` posterior-predictive probability -- so
the frozen design fuses them by averaging each parent's own *rank position*
within the trailing window (`NORMALIZED = (49 - POSITION) / 48`), never their
raw magnitudes; z-scoring, min-max fitting, or any outcome-dependent
calibration is explicitly forbidden by the design.

Every score is computed as an exact `fractions.Fraction` end to end. The
Beta(6, 43) evidence terms are Beta-Binomial marginal likelihoods, which for
the integer counts this module ever sees (window sizes 25/50) reduce to a
ratio of factorials with no floating-point rounding -- ranking and
tie-breaking are therefore exact, not float-comparison-sensitive. This
project ships no numpy/scipy dependency, and none is needed here.

This module never reads a target draw, replay result, or any empirical
performance value -- every parameter (window, prior, split, weights,
minimum history) is fixed by the frozen design, not fit or tuned.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from fractions import Fraction

#: Official BIG_LOTTO rule shape: 6 main numbers drawn from a pool of 1..49.
POOL_SIZE = 49
MAIN_NUMBERS_PER_DRAW = 6

#: Frozen PARENT_COMPONENT_RULE_1 (`B649_MULTISCALE_OFFICIAL_NULL_Z2_RANKED_POOL_V1`):
#: OFFICIAL_NULL_Z2_50(n) = (49*COUNT_50(n) - 6*50)^2 / (258*50).
NULL_Z2_WINDOW = 50
NULL_Z2_VARIANCE_CONSTANT = 258  # frozen literal constant; 258 = 6 * 43, not derived here

#: Frozen PARENT_COMPONENT_RULE_2 (`B649_MULTISCALE_BAYES_CHANGEPOINT_BMA_RANKED_POOL_V1`):
#: a two-model (no-change vs. one-changepoint-at-the-midpoint) Bayesian model
#: average under a Beta(6, 43) prior.
BAYES_WINDOW = 50
BAYES_HALF_WINDOW = 25
PRIOR_ALPHA = 6
PRIOR_BETA = 43

#: Frozen COMPONENT_NORMALIZATION_RULE: NORMALIZED = (49 - POSITION) / 48.
RANK_NORMALIZATION_DENOMINATOR = POOL_SIZE - 1

#: Frozen FALLBACK_RULE: at least 750 causal history rows are required.
MINIMUM_HISTORY = 750

#: Frozen TICKET_SELECTION_RULE: ranked positions 1..6 become the one native ticket.
NATIVE_TICKET_COUNT = 6

Draw = tuple[int, ...]


def _validate_draw(draw: Sequence[int]) -> Draw:
    numbers = tuple(draw)
    if len(numbers) != MAIN_NUMBERS_PER_DRAW:
        raise ValueError(
            f"a draw must contain exactly {MAIN_NUMBERS_PER_DRAW} main numbers, "
            f"got {len(numbers)}: {numbers!r}"
        )
    if len(set(numbers)) != len(numbers):
        raise ValueError(f"a draw's main numbers must be distinct, got {numbers!r}")
    if any(not 1 <= number <= POOL_SIZE for number in numbers):
        raise ValueError(f"main numbers must lie in 1..{POOL_SIZE}, got {numbers!r}")
    return numbers


def _validate_history(history: Sequence[Sequence[int]]) -> tuple[Draw, ...]:
    return tuple(_validate_draw(draw) for draw in history)


def _validate_number(number: int) -> None:
    if not 1 <= number <= POOL_SIZE:
        raise ValueError(f"number must lie in 1..{POOL_SIZE}, got {number}")


def _count_containing(window: Sequence[Draw], number: int) -> int:
    return sum(1 for draw in window if number in draw)


def official_null_z2_50(window: Sequence[Draw], number: int) -> Fraction:
    """OFFICIAL_NULL_Z2_50(n) = (49*COUNT_50(n) - 6*50)^2 / (258*50), exact.

    `window` must be exactly the frozen trailing 50-draw window (chronological
    oldest-to-newest, target draw excluded) -- the constants folded into this
    formula are the frozen WINDOW=50 contract, not a general window size.
    """

    if len(window) != NULL_Z2_WINDOW:
        raise ValueError(
            f"window must contain exactly {NULL_Z2_WINDOW} draws, got {len(window)}"
        )
    _validate_number(number)
    count = _count_containing(window, number)
    numerator = (POOL_SIZE * count - MAIN_NUMBERS_PER_DRAW * NULL_Z2_WINDOW) ** 2
    denominator = NULL_Z2_VARIANCE_CONSTANT * NULL_Z2_WINDOW
    return Fraction(numerator, denominator)


def _beta_function(a: int, b: int) -> Fraction:
    """Exact B(a, b) for positive integers a, b: (a-1)!(b-1)!/(a+b-1)!."""

    return Fraction(math.factorial(a - 1) * math.factorial(b - 1), math.factorial(a + b - 1))


def beta_evidence(alpha: int, beta: int, k: int, n: int) -> Fraction:
    """Exact Beta-Binomial marginal likelihood BETA_EVIDENCE(alpha, beta, k, n):

    P(k successes out of n trials | Beta(alpha, beta) prior), integrated over
    the unknown success probability -- the "evidence" each changepoint
    sub-model contributes to the Bayesian model average below.
    """

    if not 0 <= k <= n:
        raise ValueError(f"k must lie in 0..{n}, got {k}")
    return (
        Fraction(math.comb(n, k))
        * _beta_function(alpha + k, beta + n - k)
        / _beta_function(alpha, beta)
    )


@dataclass(frozen=True, slots=True)
class BayesChangepointComponents:
    """Every intermediate value behind BMA_50(n), exposed for independent verification."""

    k_total: int
    k_old: int
    k_recent: int
    evidence_m0: Fraction
    evidence_m1: Fraction
    posterior_m0: Fraction
    posterior_m1: Fraction
    predictive_m0: Fraction
    predictive_m1: Fraction
    bma: Fraction


def bayes_changepoint_bma_50(window: Sequence[Draw], number: int) -> BayesChangepointComponents:
    """BMA_50(n): equal-prior Bayesian model average of a no-change model M0

    against a one-changepoint-at-the-midpoint model M1, both built on a
    Beta(6, 43) prior -- the frozen PARENT_COMPONENT_RULE_2 contract.
    `window` must be exactly the frozen trailing 50-draw window (chronological
    oldest-to-newest, target draw excluded), split into the older 25 and the
    recent 25.
    """

    if len(window) != BAYES_WINDOW:
        raise ValueError(f"window must contain exactly {BAYES_WINDOW} draws, got {len(window)}")
    _validate_number(number)

    older = window[:BAYES_HALF_WINDOW]
    recent = window[BAYES_HALF_WINDOW:]
    k_total = _count_containing(window, number)
    k_old = _count_containing(older, number)
    k_recent = _count_containing(recent, number)

    evidence_m0 = beta_evidence(PRIOR_ALPHA, PRIOR_BETA, k_total, BAYES_WINDOW)
    evidence_m1 = beta_evidence(
        PRIOR_ALPHA, PRIOR_BETA, k_old, BAYES_HALF_WINDOW
    ) * beta_evidence(PRIOR_ALPHA, PRIOR_BETA, k_recent, BAYES_HALF_WINDOW)
    evidence_sum = evidence_m0 + evidence_m1
    posterior_m0 = evidence_m0 / evidence_sum
    posterior_m1 = evidence_m1 / evidence_sum
    predictive_m0 = Fraction(PRIOR_ALPHA + k_total, PRIOR_ALPHA + PRIOR_BETA + BAYES_WINDOW)
    predictive_m1 = Fraction(
        PRIOR_ALPHA + k_recent, PRIOR_ALPHA + PRIOR_BETA + BAYES_HALF_WINDOW
    )
    bma = posterior_m0 * predictive_m0 + posterior_m1 * predictive_m1

    return BayesChangepointComponents(
        k_total=k_total,
        k_old=k_old,
        k_recent=k_recent,
        evidence_m0=evidence_m0,
        evidence_m1=evidence_m1,
        posterior_m0=posterior_m0,
        posterior_m1=posterior_m1,
        predictive_m0=predictive_m0,
        predictive_m1=predictive_m1,
        bma=bma,
    )


def _rank_positions_z2(window: Sequence[Draw]) -> dict[int, int]:
    scores = {number: official_null_z2_50(window, number) for number in range(1, POOL_SIZE + 1)}
    ordered = sorted(scores, key=lambda number: (-scores[number], number))
    return {number: position + 1 for position, number in enumerate(ordered)}


def _rank_positions_bma(window: Sequence[Draw]) -> dict[int, int]:
    components = {
        number: bayes_changepoint_bma_50(window, number) for number in range(1, POOL_SIZE + 1)
    }
    ordered = sorted(
        components,
        key=lambda number: (
            -components[number].bma,
            -components[number].posterior_m1,
            -components[number].predictive_m1,
            number,
        ),
    )
    return {number: position + 1 for position, number in enumerate(ordered)}


def _normalize_rank(position: int) -> Fraction:
    return Fraction(POOL_SIZE - position, RANK_NORMALIZATION_DENOMINATOR)


def pairwise_score_50(window: Sequence[Draw]) -> dict[int, Fraction]:
    """PAIRWISE_SCORE(n) for every legal number, exact: the average of each

    parent's own rank-normalized score within `window` -- a fusion of the two
    parents' rank positions, never a raw-value fusion of their unrelated
    scales.
    """

    if len(window) != NULL_Z2_WINDOW:
        raise ValueError(
            f"window must contain exactly {NULL_Z2_WINDOW} draws, got {len(window)}"
        )
    z2_positions = _rank_positions_z2(window)
    bma_positions = _rank_positions_bma(window)
    return {
        number: (_normalize_rank(z2_positions[number]) + _normalize_rank(bma_positions[number]))
        / 2
        for number in range(1, POOL_SIZE + 1)
    }


def ranked_pool_50(window: Sequence[Draw]) -> tuple[int, ...]:
    """All 49 legal numbers ordered by PAIRWISE_SCORE descending, ties broken

    by number ascending -- the frozen NUMBER_RANKING_RULE / NUMBER_TIE_BREAK_RULE,
    with no intermediate Top-K pool or candidate subsampling.
    """

    scores = pairwise_score_50(window)
    return tuple(sorted(scores, key=lambda number: (-scores[number], number)))


@dataclass(frozen=True, slots=True)
class PairwiseNullZ2BayesChangepointPrediction:
    """The frozen design's single native ticket, plus its full ranked pool and scores."""

    ticket: tuple[int, ...]
    ranked_pool: tuple[int, ...]
    scores: dict[int, Fraction]


def predict_biglotto_l2_pairwise_null_z2_bayes_changepoint_weighted_score_50(
    history: Sequence[Sequence[int]],
) -> PairwiseNullZ2BayesChangepointPrediction | None:
    """The frozen design's top-level entry point.

    `history` must already be causal: every draw strictly before the target
    cutoff, chronological oldest-to-newest, with the target draw and every
    future draw excluded by the caller -- this module never reads them.
    Returns `None` (never a substitute method, window, weight, or random
    fallback) when fewer than `MINIMUM_HISTORY` causal rows are available.
    """

    validated = _validate_history(history)
    if len(validated) < MINIMUM_HISTORY:
        return None

    window = validated[-NULL_Z2_WINDOW:]
    scores = pairwise_score_50(window)
    ranked_pool = tuple(sorted(scores, key=lambda number: (-scores[number], number)))
    ticket = tuple(sorted(ranked_pool[:NATIVE_TICKET_COUNT]))
    return PairwiseNullZ2BayesChangepointPrediction(
        ticket=ticket, ranked_pool=ranked_pool, scores=scores
    )
