"""Frozen Level-2 Pairwise Big Lotto research candidate.

This module implements
``B649_PAIRWISE_CONDITIONAL_COOCCURRENCE_SPECTRAL_IPR_WEIGHTED_SCORE_300_V1``
as a standalone, deterministic, standard-library-only research candidate.  It
does not load draws, access persistence, perform replay, or use a random source.

The two causal windows are intentionally different and must remain so:

* conditional co-occurrence uses ``history[-301:-1]`` and conditions on
  ``history[-1]`` without counting that anchor in its estimation window;
* spectral IPR uses ``history[-300:]`` and therefore includes the anchor.

Every value that can affect a rank is a :class:`fractions.Fraction`.  Circular
autocorrelations are evaluated through exact integer numerators; no FFT or
floating-point value participates in scoring or tie resolution.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction
from typing import cast

METHOD_ID = "BMSGV1_L2_PAIRWISE_8abbaed2ea78e47f"
DESIGN_NAME = "B649_PAIRWISE_CONDITIONAL_COOCCURRENCE_SPECTRAL_IPR_WEIGHTED_SCORE_300_V1"
SEMANTIC_SIGNATURE = "a299e56636b9a90a5a2e0caa8fa5c89a251b1523a9c11e87630eda390cb70d58"

MINIMUM_CAUSAL_HISTORY = 751
WINDOW_SIZE = 300
NUMBER_DOMAIN = tuple(range(1, 50))
_NUMBER_SET = frozenset(NUMBER_DOMAIN)
_DRAW_SIZE = 6
_RANK_DENOMINATOR = len(NUMBER_DOMAIN) - 1

Draw = tuple[int, ...]
ExactScoreMap = dict[int, Fraction]


@dataclass(frozen=True, slots=True)
class SpectralIprComponentScores:
    """Exact spectral scores and the frozen secondary peak tie-break."""

    ipr_scores: Mapping[int, Fraction]
    peak_scores: Mapping[int, Fraction]


@dataclass(frozen=True, slots=True)
class PairwiseCandidatePrediction:
    """Complete frozen output for one causal prediction."""

    normalized_cooccurrence_scores: Mapping[int, Fraction]
    normalized_spectral_ipr_scores: Mapping[int, Fraction]
    pairwise_scores: Mapping[int, Fraction]
    ranked_pool: tuple[int, ...]
    ticket: tuple[int, ...]


def _validate_draw(draw: object, *, location: str) -> Draw:
    if isinstance(draw, (str, bytes)) or not isinstance(draw, Sequence):
        raise ValueError(f"{location} must be a sequence of exactly six integers")

    values = tuple(cast(Sequence[object], draw))
    if len(values) != _DRAW_SIZE:
        raise ValueError(f"{location} must contain exactly six values")
    if any(type(value) is not int for value in values):
        raise ValueError(f"{location} values must be integers and must not be booleans")

    integers = tuple(cast(int, value) for value in values)
    if any(value < 1 or value > 49 for value in integers):
        raise ValueError(f"{location} values must lie in 1..49")
    if len(set(integers)) != _DRAW_SIZE:
        raise ValueError(f"{location} values must be distinct")
    return integers


def _validate_draws(draws: object, *, location: str) -> tuple[Draw, ...]:
    if isinstance(draws, (str, bytes)) or not isinstance(draws, Sequence):
        raise ValueError(f"{location} must be a chronological sequence of draws")
    return tuple(
        _validate_draw(draw, location=f"{location}[{index}]")
        for index, draw in enumerate(cast(Sequence[object], draws))
    )


def _conditional_cooccurrence_scores(
    estimation_window: tuple[Draw, ...], anchor_draw: Draw
) -> ExactScoreMap:
    window_sets = tuple(frozenset(draw) for draw in estimation_window)
    anchors = tuple(sorted(anchor_draw))
    occurrence_counts = {
        anchor: sum(anchor in draw for draw in window_sets) for anchor in anchors
    }

    scores: ExactScoreMap = {}
    for number in NUMBER_DOMAIN:
        score = Fraction(0, 1)
        for anchor in anchors:
            if number == anchor:
                continue
            occurrence_count = occurrence_counts[anchor]
            if occurrence_count == 0:
                continue
            pair_count = sum(anchor in draw and number in draw for draw in window_sets)
            score += Fraction(pair_count, occurrence_count)
        scores[number] = score
    return scores


def conditional_cooccurrence_scores(
    estimation_window: Sequence[Sequence[int]], anchor_draw: Sequence[int]
) -> ExactScoreMap:
    """Return the exact raw conditional co-occurrence score for all 49 numbers."""

    window = _validate_draws(estimation_window, location="estimation_window")
    if len(window) != WINDOW_SIZE:
        raise ValueError("estimation_window must contain exactly 300 draws")
    anchor = _validate_draw(anchor_draw, location="anchor_draw")
    return _conditional_cooccurrence_scores(window, anchor)


def _spectral_ipr_scores(spectral_window: tuple[Draw, ...]) -> SpectralIprComponentScores:
    window_sets = tuple(frozenset(draw) for draw in spectral_window)
    ipr_scores: ExactScoreMap = {}
    peak_scores: ExactScoreMap = {}

    for number in NUMBER_DOMAIN:
        positions = frozenset(
            index for index, draw in enumerate(window_sets) if number in draw
        )
        count = len(positions)
        r_zero_numerator = count * (WINDOW_SIZE - count)
        if r_zero_numerator == 0:
            ipr_scores[number] = Fraction(0, 1)
            peak_scores[number] = Fraction(0, 1)
            continue

        squared_numerator_sum = 0
        peak_absolute_numerator = 0
        count_squared = count * count
        for lag in range(WINDOW_SIZE):
            joint_count = sum(
                (position + lag) % WINDOW_SIZE in positions for position in positions
            )
            # R(l) = joint_count - count**2 / 300.  Keeping its common
            # denominator out of the loop gives an exact integer numerator.
            autocorrelation_numerator = WINDOW_SIZE * joint_count - count_squared
            squared_numerator_sum += autocorrelation_numerator**2
            if 1 <= lag <= WINDOW_SIZE // 2:
                peak_absolute_numerator = max(
                    peak_absolute_numerator, abs(autocorrelation_numerator)
                )

        ipr_scores[number] = Fraction(
            squared_numerator_sum,
            WINDOW_SIZE * r_zero_numerator**2,
        )
        peak_scores[number] = Fraction(peak_absolute_numerator, r_zero_numerator)

    return SpectralIprComponentScores(ipr_scores=ipr_scores, peak_scores=peak_scores)


def spectral_ipr_scores(
    spectral_window: Sequence[Sequence[int]],
) -> SpectralIprComponentScores:
    """Return exact full-lag spectral IPR and peak scores for all 49 numbers."""

    window = _validate_draws(spectral_window, location="spectral_window")
    if len(window) != WINDOW_SIZE:
        raise ValueError("spectral_window must contain exactly 300 draws")
    return _spectral_ipr_scores(window)


def _require_exact_score_map(scores: Mapping[int, Fraction], *, location: str) -> None:
    if frozenset(scores) != _NUMBER_SET:
        raise ValueError(f"{location} must contain every number in 1..49 exactly once")
    if any(type(scores[number]) is not Fraction for number in NUMBER_DOMAIN):
        raise ValueError(f"{location} values must be Fraction instances")


def rank_conditional_cooccurrence(scores: Mapping[int, Fraction]) -> tuple[int, ...]:
    """Apply the frozen raw-score-descending, number-ascending parent order."""

    _require_exact_score_map(scores, location="cooccurrence scores")
    return tuple(sorted(NUMBER_DOMAIN, key=lambda number: (-scores[number], number)))


def rank_spectral_ipr(scores: SpectralIprComponentScores) -> tuple[int, ...]:
    """Apply IPR descending, peak descending, then number ascending."""

    _require_exact_score_map(scores.ipr_scores, location="spectral IPR scores")
    _require_exact_score_map(scores.peak_scores, location="spectral peak scores")
    return tuple(
        sorted(
            NUMBER_DOMAIN,
            key=lambda number: (
                -scores.ipr_scores[number],
                -scores.peak_scores[number],
                number,
            ),
        )
    )


def normalize_ranked_domain(ranked_numbers: Sequence[int]) -> ExactScoreMap:
    """Normalize one-based positions by ``(49 - position) / 48`` exactly."""

    order = tuple(ranked_numbers)
    if any(type(number) is not int for number in order) or frozenset(order) != _NUMBER_SET:
        raise ValueError("ranked_numbers must be a permutation of integers 1..49")
    if len(order) != len(NUMBER_DOMAIN):
        raise ValueError("ranked_numbers must contain exactly 49 numbers")

    positions = {number: position for position, number in enumerate(order, start=1)}
    return {
        number: Fraction(len(NUMBER_DOMAIN) - positions[number], _RANK_DENOMINATOR)
        for number in NUMBER_DOMAIN
    }


def fuse_normalized_scores(
    normalized_cooccurrence_scores: Mapping[int, Fraction],
    normalized_spectral_ipr_scores: Mapping[int, Fraction],
) -> ExactScoreMap:
    """Apply the frozen symmetric ``1/2 + 1/2`` exact fusion."""

    _require_exact_score_map(
        normalized_cooccurrence_scores, location="normalized cooccurrence scores"
    )
    _require_exact_score_map(
        normalized_spectral_ipr_scores, location="normalized spectral IPR scores"
    )
    return {
        number: (
            normalized_cooccurrence_scores[number]
            + normalized_spectral_ipr_scores[number]
        )
        / 2
        for number in NUMBER_DOMAIN
    }


def predict_biglotto_l2_pairwise_conditional_cooccurrence_spectral_ipr_weighted_score_300(
    history: Sequence[Sequence[int]],
) -> PairwiseCandidatePrediction | None:
    """Predict one frozen native Big Lotto ticket from chronological history.

    Every supplied draw is validated before the minimum-history branch.  A
    well-formed history shorter than 751 draws returns ``None``; malformed
    input always raises :class:`ValueError` before any score is calculated.
    The caller owns the oldest-to-newest order contract, and this function
    never reorders chronological draws.
    """

    validated_history = _validate_draws(history, location="history")
    if len(validated_history) < MINIMUM_CAUSAL_HISTORY:
        return None

    anchor_draw = validated_history[-1]
    cooccurrence_window = validated_history[-301:-1]
    spectral_window = validated_history[-300:]

    raw_cooccurrence = _conditional_cooccurrence_scores(
        cooccurrence_window, anchor_draw
    )
    raw_spectral = _spectral_ipr_scores(spectral_window)

    normalized_cooccurrence = normalize_ranked_domain(
        rank_conditional_cooccurrence(raw_cooccurrence)
    )
    normalized_spectral = normalize_ranked_domain(rank_spectral_ipr(raw_spectral))
    pairwise_scores = fuse_normalized_scores(
        normalized_cooccurrence, normalized_spectral
    )
    ranked_pool = tuple(
        sorted(NUMBER_DOMAIN, key=lambda number: (-pairwise_scores[number], number))
    )
    ticket = tuple(sorted(ranked_pool[:_DRAW_SIZE]))

    return PairwiseCandidatePrediction(
        normalized_cooccurrence_scores=normalized_cooccurrence,
        normalized_spectral_ipr_scores=normalized_spectral,
        pairwise_scores=pairwise_scores,
        ranked_pool=ranked_pool,
        ticket=ticket,
    )


def _score_rows(scores: Mapping[int, Fraction]) -> list[list[int]]:
    return [
        [number, scores[number].numerator, scores[number].denominator]
        for number in NUMBER_DOMAIN
    ]


def canonical_prediction_json(prediction: PairwiseCandidatePrediction) -> str:
    """Serialize the complete prediction deterministically with exact ratios."""

    payload = {
        "method_id": METHOD_ID,
        "semantic_signature": SEMANTIC_SIGNATURE,
        "normalized_cooccurrence_scores": _score_rows(
            prediction.normalized_cooccurrence_scores
        ),
        "normalized_spectral_ipr_scores": _score_rows(
            prediction.normalized_spectral_ipr_scores
        ),
        "pairwise_scores": _score_rows(prediction.pairwise_scores),
        "ranked_pool": list(prediction.ranked_pool),
        "ticket": list(prediction.ticket),
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


__all__ = [
    "DESIGN_NAME",
    "METHOD_ID",
    "MINIMUM_CAUSAL_HISTORY",
    "NUMBER_DOMAIN",
    "SEMANTIC_SIGNATURE",
    "WINDOW_SIZE",
    "PairwiseCandidatePrediction",
    "SpectralIprComponentScores",
    "canonical_prediction_json",
    "conditional_cooccurrence_scores",
    "fuse_normalized_scores",
    "normalize_ranked_domain",
    "predict_biglotto_l2_pairwise_conditional_cooccurrence_spectral_ipr_weighted_score_300",
    "rank_conditional_cooccurrence",
    "rank_spectral_ipr",
    "spectral_ipr_scores",
]
