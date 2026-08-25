from __future__ import annotations

import ast
import json
from collections.abc import Sequence
from fractions import Fraction
from pathlib import Path
from typing import cast

import pytest

from lottolab.research import (
    biglotto_l2_pairwise_cooccurrence_spectral_weighted_score_candidate_batch_r1 as candidate,
)

Draw = tuple[int, ...]
History = tuple[Draw, ...]


def _constant_history(draw: Draw, length: int) -> History:
    return (draw,) * length


def _prediction(history: History) -> candidate.PairwiseCandidatePrediction:
    result = (
        candidate.predict_biglotto_l2_pairwise_conditional_cooccurrence_spectral_ipr_weighted_score_300(
            history
        )
    )
    assert result is not None
    return result


def _hand_cooccurrence_window() -> History:
    # Anchor occurrence counts: OCC(1)=150, OCC(2)=100, OCC(3..6)=0.
    return (
        ((1, 7, 8, 9, 10, 11),) * 100
        + ((1, 2, 7, 12, 13, 14),) * 50
        + ((2, 8, 15, 16, 17, 18),) * 50
        + ((19, 20, 21, 22, 23, 24),) * 100
    )


def _single_impulse_spectral_window() -> History:
    # Number 1 occurs only at t=0; number 7 occurs at every t except t=0.
    # Numbers 2..6 are constant-one series.
    return ((1, 2, 3, 4, 5, 6),) + ((2, 3, 4, 5, 6, 7),) * 299


def _exclusive_boundary_history(first_estimation_draw: Draw) -> History:
    older_history = ((40, 41, 42, 43, 44, 45),) * 450
    remaining_estimation_window = ((1, 9, 10, 11, 12, 13),) * 299
    anchor = (1, 2, 3, 4, 5, 6)
    return (*older_history, first_estimation_draw, *remaining_estimation_window, anchor)


def test_frozen_identity_constants_match_the_sealed_authority() -> None:
    assert candidate.METHOD_ID == "BMSGV1_L2_PAIRWISE_8abbaed2ea78e47f"
    assert (
        candidate.DESIGN_NAME
        == "B649_PAIRWISE_CONDITIONAL_COOCCURRENCE_SPECTRAL_IPR_WEIGHTED_SCORE_300_V1"
    )
    assert (
        candidate.SEMANTIC_SIGNATURE
        == "a299e56636b9a90a5a2e0caa8fa5c89a251b1523a9c11e87630eda390cb70d58"
    )
    assert candidate.MINIMUM_CAUSAL_HISTORY == 751
    assert candidate.WINDOW_SIZE == 300


def test_minimum_history_boundary_is_exactly_750_then_751() -> None:
    draw = (1, 2, 3, 4, 5, 6)
    predictor = (
        candidate.predict_biglotto_l2_pairwise_conditional_cooccurrence_spectral_ipr_weighted_score_300
    )
    assert predictor(_constant_history(draw, 750)) is None
    assert predictor(_constant_history(draw, 751)) is not None


def test_malformed_insufficient_history_raises_before_no_prediction_branch() -> None:
    malformed = ((1, 1, 2, 3, 4, 5),) + ((1, 2, 3, 4, 5, 6),) * 749
    with pytest.raises(ValueError, match="distinct"):
        candidate.predict_biglotto_l2_pairwise_conditional_cooccurrence_spectral_ipr_weighted_score_300(
            malformed
        )


@pytest.mark.parametrize(
    "draw",
    [
        (1, 2, 3, 4, 5),
        (1, 2, 3, 4, 5, 6, 7),
        (1, 1, 2, 3, 4, 5),
        (True, 2, 3, 4, 5, 6),
        (0, 2, 3, 4, 5, 6),
        (1, 2, 3, 4, 5, 50),
        (1.0, 2, 3, 4, 5, 6),
        ("1", 2, 3, 4, 5, 6),
    ],
)
def test_malformed_draw_contract_is_rejected(draw: tuple[object, ...]) -> None:
    malformed_history = cast(Sequence[Sequence[int]], (draw,))
    with pytest.raises(ValueError):
        candidate.predict_biglotto_l2_pairwise_conditional_cooccurrence_spectral_ipr_weighted_score_300(
            malformed_history
        )


def test_non_sequence_history_is_rejected_as_value_error() -> None:
    malformed_history = cast(Sequence[Sequence[int]], None)
    with pytest.raises(ValueError, match="chronological sequence"):
        candidate.predict_biglotto_l2_pairwise_conditional_cooccurrence_spectral_ipr_weighted_score_300(
            malformed_history
        )


def test_every_draw_is_validated_even_when_it_is_older_than_scoring_windows() -> None:
    malformed_old_draw = (1, 1, 2, 3, 4, 5)
    history = (malformed_old_draw,) + ((1, 2, 3, 4, 5, 6),) * 750
    with pytest.raises(ValueError, match=r"history\[0\].*distinct"):
        candidate.predict_biglotto_l2_pairwise_conditional_cooccurrence_spectral_ipr_weighted_score_300(
            history
        )


def test_component_helpers_require_the_frozen_300_draw_window() -> None:
    short_window = ((1, 2, 3, 4, 5, 6),) * 299
    with pytest.raises(ValueError, match="exactly 300"):
        candidate.conditional_cooccurrence_scores(
            short_window, (1, 2, 3, 4, 5, 6)
        )
    with pytest.raises(ValueError, match="exactly 300"):
        candidate.spectral_ipr_scores(short_window)


def test_conditional_cooccurrence_matches_hand_calculated_exact_ratios() -> None:
    scores = candidate.conditional_cooccurrence_scores(
        _hand_cooccurrence_window(), (1, 2, 3, 4, 5, 6)
    )

    # n=7: 150/150 from anchor 1 plus 50/100 from anchor 2.
    assert scores[7] == Fraction(3, 2)
    # n=8: 100/150 from anchor 1 plus 50/100 from anchor 2.
    assert scores[8] == Fraction(7, 6)
    # Self-anchor terms are zero: n=1 receives only the anchor-2 term.
    assert scores[1] == Fraction(1, 2)
    assert scores[2] == Fraction(1, 3)
    # Zero-occurrence anchors 3..6 contribute exactly zero without smoothing.
    assert scores[3] == 0
    assert scores[49] == 0
    assert all(type(score) is Fraction for score in scores.values())


def test_cooccurrence_parent_ties_use_number_ascending() -> None:
    all_zero = {number: Fraction(0, 1) for number in candidate.NUMBER_DOMAIN}
    assert candidate.rank_conditional_cooccurrence(all_zero) == candidate.NUMBER_DOMAIN


def test_spectral_ipr_matches_single_impulse_hand_calculation() -> None:
    scores = candidate.spectral_ipr_scores(_single_impulse_spectral_window())

    # For a one-impulse binary series, the common autocorrelation numerators
    # are 299 at lag 0 and -1 at each of the other 299 lags.  Therefore:
    # IPR=(299**2 + 299)/(300*299**2)=1/299 and peak=1/299.
    assert scores.ipr_scores[1] == Fraction(1, 299)
    assert scores.peak_scores[1] == Fraction(1, 299)
    # The 299-ones complement has the same exact centered autocorrelation.
    assert scores.ipr_scores[7] == Fraction(1, 299)
    assert scores.peak_scores[7] == Fraction(1, 299)
    # Constant-zero and constant-one series take the frozen R(0)=0 branch.
    assert scores.ipr_scores[2] == 0
    assert scores.peak_scores[2] == 0
    assert scores.ipr_scores[49] == 0
    assert scores.peak_scores[49] == 0


def test_spectral_ipr_matches_alternating_series_hand_calculation() -> None:
    window = tuple(
        (1, 2, 3, 4, 5, 14) if index % 2 == 0 else (1, 2, 3, 4, 5, 15)
        for index in range(300)
    )
    scores = candidate.spectral_ipr_scores(window)

    # For either alternating centered series, Z(t)=+/-1/2 and R(l)=+75
    # on every even lag and -75 on every odd lag.  All 300 squared terms
    # therefore equal R(0)^2, so IPR=1 and the lag-1 peak ratio is also 1.
    assert scores.ipr_scores[14] == Fraction(1, 1)
    assert scores.peak_scores[14] == Fraction(1, 1)
    assert scores.ipr_scores[15] == Fraction(1, 1)
    assert scores.peak_scores[15] == Fraction(1, 1)


def test_spectral_parent_uses_peak_then_number_for_exact_ties() -> None:
    ipr = {number: Fraction(0, 1) for number in candidate.NUMBER_DOMAIN}
    peak = {number: Fraction(0, 1) for number in candidate.NUMBER_DOMAIN}
    ipr[10] = ipr[11] = Fraction(2, 5)
    peak[10] = Fraction(1, 3)
    peak[11] = Fraction(1, 2)
    ipr[20] = ipr[21] = Fraction(1, 3)
    peak[20] = peak[21] = Fraction(1, 4)

    order = candidate.rank_spectral_ipr(
        candidate.SpectralIprComponentScores(ipr_scores=ipr, peak_scores=peak)
    )
    assert order[:2] == (11, 10)
    assert order.index(20) < order.index(21)


def test_rank_normalization_has_exact_one_half_and_zero_endpoints() -> None:
    normalized = candidate.normalize_ranked_domain(tuple(reversed(candidate.NUMBER_DOMAIN)))
    assert normalized[49] == Fraction(1, 1)
    assert normalized[25] == Fraction(1, 2)
    assert normalized[1] == Fraction(0, 1)


def test_symmetric_fusion_is_exact_one_half_plus_one_half() -> None:
    ascending = candidate.normalize_ranked_domain(candidate.NUMBER_DOMAIN)
    descending = candidate.normalize_ranked_domain(tuple(reversed(candidate.NUMBER_DOMAIN)))
    fused = candidate.fuse_normalized_scores(ascending, descending)
    assert set(fused) == set(candidate.NUMBER_DOMAIN)
    assert all(score == Fraction(1, 2) for score in fused.values())


def test_full_49_number_order_final_tie_break_and_ticket_construction() -> None:
    prediction = _prediction(_constant_history((1, 2, 3, 4, 5, 6), 751))

    assert prediction.ranked_pool == candidate.NUMBER_DOMAIN
    assert len(prediction.ranked_pool) == 49
    assert len(set(prediction.ranked_pool)) == 49
    assert prediction.ticket == (1, 2, 3, 4, 5, 6)
    assert len(prediction.ticket) == 6
    assert tuple(sorted(prediction.ticket)) == prediction.ticket
    assert prediction.normalized_cooccurrence_scores[1] == 1
    assert prediction.normalized_cooccurrence_scores[25] == Fraction(1, 2)
    assert prediction.normalized_cooccurrence_scores[49] == 0


def test_pairwise_scores_are_the_exact_frozen_average_for_every_number() -> None:
    prediction = _prediction(
        _exclusive_boundary_history((1, 7, 14, 15, 16, 17))
    )
    for number in candidate.NUMBER_DOMAIN:
        expected = (
            prediction.normalized_cooccurrence_scores[number]
            + prediction.normalized_spectral_ipr_scores[number]
        ) / 2
        assert prediction.pairwise_scores[number] == expected
        assert type(prediction.pairwise_scores[number]) is Fraction


def test_edge_numbers_one_and_49_are_validated_scored_and_serialized() -> None:
    prediction = _prediction(_constant_history((1, 2, 3, 4, 5, 49), 751))
    for scores in (
        prediction.normalized_cooccurrence_scores,
        prediction.normalized_spectral_ipr_scores,
        prediction.pairwise_scores,
    ):
        assert set(scores) == set(range(1, 50))
        assert 1 in scores
        assert 49 in scores
    assert all(1 <= number <= 49 for number in prediction.ticket)


def test_draw_at_minus_301_changes_cooccurrence_but_not_spectral_component() -> None:
    history_a = _exclusive_boundary_history((1, 7, 14, 15, 16, 17))
    history_b = _exclusive_boundary_history((1, 8, 14, 15, 16, 17))
    prediction_a = _prediction(history_a)
    prediction_b = _prediction(history_b)

    raw_a = candidate.conditional_cooccurrence_scores(
        history_a[-301:-1], history_a[-1]
    )
    raw_b = candidate.conditional_cooccurrence_scores(
        history_b[-301:-1], history_b[-1]
    )
    assert raw_a[7] == Fraction(1, 300)
    assert raw_b[7] == 0
    assert prediction_a.normalized_cooccurrence_scores != (
        prediction_b.normalized_cooccurrence_scores
    )
    # The changed draw is exactly outside history[-300:].
    assert history_a[-300:] == history_b[-300:]
    assert prediction_a.normalized_spectral_ipr_scores == (
        prediction_b.normalized_spectral_ipr_scores
    )


def test_changed_anchor_affects_spectral_but_not_zero_occurrence_cooccurrence() -> None:
    older_history = ((40, 41, 42, 43, 44, 45),) * 450
    estimation_window = ((7, 8, 9, 10, 11, 12),) * 300
    history_a = older_history + estimation_window + ((1, 2, 3, 4, 5, 6),)
    history_b = older_history + estimation_window + ((1, 2, 3, 4, 5, 13),)
    prediction_a = _prediction(history_a)
    prediction_b = _prediction(history_b)

    # Every anchor in both fixtures has OCC=0 in the excluded estimation
    # window, so the complete conditional component remains the same.
    assert prediction_a.normalized_cooccurrence_scores == (
        prediction_b.normalized_cooccurrence_scores
    )
    spectral_a = candidate.spectral_ipr_scores(history_a[-300:])
    spectral_b = candidate.spectral_ipr_scores(history_b[-300:])
    assert spectral_a.ipr_scores[6] == Fraction(1, 299)
    assert spectral_b.ipr_scores[6] == 0
    assert spectral_a.ipr_scores[13] == 0
    assert spectral_b.ipr_scores[13] == Fraction(1, 299)
    assert prediction_a.normalized_spectral_ipr_scores != (
        prediction_b.normalized_spectral_ipr_scores
    )


def test_history_older_than_minus_301_is_accepted_but_not_scored() -> None:
    recent = (
        ((1, 9, 10, 11, 12, 13),) * 300
        + ((1, 2, 3, 4, 5, 6),)
    )
    history_a = ((20, 21, 22, 23, 24, 25),) * 450 + recent
    history_b = ((30, 31, 32, 33, 34, 35),) * 450 + recent
    assert _prediction(history_a) == _prediction(history_b)


def test_chronological_draw_sequence_is_consumed_without_reordering() -> None:
    chronological = _exclusive_boundary_history((1, 7, 14, 15, 16, 17))
    reversed_by_caller = tuple(reversed(chronological))
    assert _prediction(chronological) != _prediction(reversed_by_caller)


def test_repeated_execution_and_canonical_serialization_are_identical() -> None:
    history = _exclusive_boundary_history((1, 7, 14, 15, 16, 17))
    first = _prediction(history)
    second = _prediction(history)

    assert first.normalized_cooccurrence_scores == second.normalized_cooccurrence_scores
    assert first.normalized_spectral_ipr_scores == second.normalized_spectral_ipr_scores
    assert first.pairwise_scores == second.pairwise_scores
    assert first.ranked_pool == second.ranked_pool
    assert first.ticket == second.ticket
    first_serialized = candidate.canonical_prediction_json(first)
    second_serialized = candidate.canonical_prediction_json(second)
    assert first_serialized.encode("utf-8") == second_serialized.encode("utf-8")

    decoded = json.loads(first_serialized)
    assert decoded["method_id"] == candidate.METHOD_ID
    assert decoded["semantic_signature"] == candidate.SEMANTIC_SIGNATURE
    assert len(decoded["pairwise_scores"]) == 49
    assert decoded["ranked_pool"] == list(first.ranked_pool)
    assert decoded["ticket"] == list(first.ticket)


def test_module_imports_exclude_rng_fft_network_database_and_replay_dependencies() -> None:
    module_path_text = candidate.__file__
    assert module_path_text is not None
    module_path = Path(module_path_text)
    syntax_tree = ast.parse(module_path.read_text(encoding="utf-8"))
    imported_roots: set[str] = set()
    for node in ast.walk(syntax_tree):
        if isinstance(node, ast.Import):
            imported_roots.update(alias.name.split(".", maxsplit=1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported_roots.add(node.module.split(".", maxsplit=1)[0])

    assert imported_roots <= {
        "__future__",
        "collections",
        "dataclasses",
        "fractions",
        "json",
        "typing",
    }
    assert imported_roots.isdisjoint(
        {
            "asyncio",
            "httpx",
            "lottolab",
            "numpy",
            "pandas",
            "random",
            "requests",
            "secrets",
            "socket",
            "sqlalchemy",
        }
    )
