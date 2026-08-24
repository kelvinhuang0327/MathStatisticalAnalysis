"""Focused tests for the frozen BigLotto Level-2 pairwise candidate."""

from __future__ import annotations

import hashlib
import inspect
import json
from fractions import Fraction
from pathlib import Path

import pytest

from lottolab.research import (
    biglotto_l2_pairwise_signal_fourier_ml_like_weighted_score_candidate_batch_r1 as batch,
)
from lottolab.research import (
    biglotto_multiscale_online_brier_ar6_multi_ticket_candidate_batch_r1 as ml_parent,
)
from lottolab.research import (
    biglotto_multiscale_spectral_concentration_multi_ticket_candidate_batch_r1 as spectral_parent,
)

Ticket = tuple[int, int, int, int, int, int]

_DRAW_TYPES: tuple[Ticket, ...] = (
    (1, 2, 3, 4, 5, 6),
    (1, 7, 13, 14, 15, 16),
    (2, 8, 17, 18, 19, 20),
    (30, 31, 32, 33, 34, 35),
)


def _history(count: int) -> tuple[Ticket, ...]:
    return tuple(_DRAW_TYPES[index % len(_DRAW_TYPES)] for index in range(count))


def _authority_root() -> Path:
    root_name = "BIGLOTTO_L2_PAIRWISE_SIGNAL_FOURIER_ML_LIKE_DESIGN_COMPLETION_R1"
    for parent in Path(__file__).resolve().parents:
        candidate = parent / ".task-data" / root_name
        if candidate.is_dir():
            return candidate
    pytest.fail("completed design-authority task-data root is unavailable")


def _component_fixture(
    spectral_number_1: Fraction = Fraction(0, 1),
    spectral_number_2: Fraction = Fraction(0, 1),
    ml_number_1: Fraction = Fraction(0, 1),
    ml_number_2: Fraction = Fraction(0, 1),
) -> tuple[list[Fraction], list[Fraction]]:
    spectral = [Fraction(0, 1)] * 49
    ml = [Fraction(0, 1)] * 49
    spectral[0] = spectral_number_1
    spectral[1] = spectral_number_2
    ml[0] = ml_number_1
    ml[1] = ml_number_2
    return spectral, ml


def test_design_authority_exists_checksum_and_exact_identity() -> None:
    authority_root = _authority_root()
    authority_path = authority_root / "completed_v1_semantics.json"
    checksum_path = authority_root / "SHA256SUMS"
    assert authority_path.is_file()
    expected_line = next(
        line
        for line in checksum_path.read_text(encoding="utf-8").splitlines()
        if line.endswith("completed_v1_semantics.json")
    )
    expected_hash = expected_line.split(maxsplit=1)[0]
    assert hashlib.sha256(authority_path.read_bytes()).hexdigest() == expected_hash

    authority = json.loads(authority_path.read_text(encoding="utf-8"))
    assert authority["SELECTED_GAP_ID"] == batch.SELECTED_GAP_ID
    assert authority["DESIGN_ID"] == batch.DESIGN_ID
    assert authority["DESIGN_SIGNATURE_SHA256"] == batch.DESIGN_SIGNATURE_SHA256
    assert authority["IMPLEMENTATION_READY"] == "YES"
    assert authority["CANONICAL_SEMANTIC_OBJECT"]["WINDOW"] == 300
    assert authority["CANONICAL_SEMANTIC_OBJECT"]["MINIMUM_HISTORY"] == 306


def test_candidate_authority_is_one_candidate_and_identity_layers_are_distinct() -> None:
    assert len(batch.CANDIDATE_AUTHORITIES) == 1
    assert batch.CANDIDATE_IDS == (batch.CANDIDATE_ID,)
    assert batch.CANDIDATE_METADATA.CANDIDATE_ID == batch.CANDIDATE_ID
    assert batch.CANDIDATE_METADATA.DESIGN_SIGNATURE_SHA256 == batch.DESIGN_SIGNATURE_SHA256
    assert batch.candidate_id_for_semantics(batch.CANDIDATE_SEMANTICS) == batch.CANDIDATE_ID
    assert not batch.CANDIDATE_ID.endswith(batch.DESIGN_SIGNATURE_SHA256[:16])
    identity = batch.derive_candidate_identity(batch.CANDIDATE_SEMANTICS)
    assert identity.CANDIDATE_ID == batch.CANDIDATE_ID
    assert identity.SIGNATURE_HASH == batch.DESIGN_SIGNATURE_SHA256


def test_spectral_parent_300_component_parity_is_exact() -> None:
    history = _history(756)
    candidate_components = batch.calculate_spectral_components(history, 756)
    parent_ranking = spectral_parent.calculate_window_rankings(history, 756, 300)
    assert candidate_components == parent_ranking.SPECTRAL_IPRS
    assert all(isinstance(value, Fraction) for value in candidate_components)


def test_spectral_formula_is_exact_and_no_floating_fft_ranking_is_used() -> None:
    autocorrelation = (Fraction(2, 1), Fraction(0, 1), Fraction(-2, 1), Fraction(0, 1))
    assert spectral_parent.spectral_ipr_from_circular_autocorrelation(autocorrelation) == (
        Fraction(1, 2)
    )
    assert batch.FLOATING_FFT_USED_FOR_RANKING == "NO"
    assert batch.LAST_HIT_GAP_USED == "NO"
    assert batch.DOMINANT_PERIOD_USED_FOR_PRIMARY_SCORE == "NO"
    source = inspect.getsource(batch)
    assert "numpy.fft" not in source
    assert "scipy.fft" not in source


def test_ml_parent_300_component_parity_and_frozen_ar6_semantics_are_exact() -> None:
    history = _history(756)
    candidate_components = batch.calculate_ml_components(history, 756)
    parent_ranking = ml_parent.rank_numbers_by_horizon(history, 756, 300)
    assert candidate_components == parent_ranking.TARGET_PROBABILITIES
    assert all(isinstance(value, Fraction) for value in candidate_components)
    model = parent_ranking.model(1)
    assert model.HORIZON == 300
    assert tuple(range(456, 756)) == model.TRAINING_EXAMPLES
    assert (
        Fraction(6, 49),
        Fraction(0, 1),
        Fraction(0, 1),
        Fraction(0, 1),
        Fraction(0, 1),
        Fraction(0, 1),
        Fraction(0, 1),
    ) == model.INITIAL_WEIGHTS
    assert Fraction(1, 64) == model.LEARNING_RATE
    assert all(len(features) == 7 for features in model.TRAINING_FEATURES)


def test_causality_requires_306_prior_draws_and_excludes_target_and_future_suffix() -> None:
    prefix = _history(306)
    with pytest.raises(batch.InsufficientHistoryError):
        batch.calculate_pairwise_ranking(prefix[:305], 305)

    accepted = batch.produce_candidate_portfolio(prefix, 306)
    future_suffix: tuple[object, ...] = ((7, 8, 9, 10, 11, 12), object())
    with_suffix = (*prefix, *future_suffix)
    assert batch.produce_candidate_portfolio(with_suffix, 306) == accepted


def test_caller_history_is_unchanged_and_malformed_prior_draw_is_rejected() -> None:
    history = list(_history(306))
    snapshot = history.copy()
    batch.calculate_pairwise_ranking(history, 306)
    assert history == snapshot

    malformed = history.copy()
    malformed[0] = (1, 1, 2, 3, 4, 5)
    with pytest.raises(ValueError, match="duplicate"):
        batch.calculate_pairwise_ranking(malformed, 306)


def test_fusion_uses_identity_normalization_and_exact_one_half_weights() -> None:
    spectral, ml = _component_fixture(
        spectral_number_1=Fraction(3, 4),
        spectral_number_2=Fraction(1, 2),
        ml_number_1=Fraction(0, 1),
        ml_number_2=Fraction(1, 1),
    )
    ranking = batch.rank_pairwise_scores(spectral, ml)
    assert batch.COMPONENT_NORMALIZATION == "IDENTITY"
    assert Fraction(1, 2) == batch.SPECTRAL_WEIGHT
    assert Fraction(1, 2) == batch.ML_WEIGHT
    assert ranking.pairwise_score(1) == Fraction(3, 8)
    assert ranking.pairwise_score(2) == Fraction(3, 4)
    assert ranking.spectral_component(1) == Fraction(3, 4)
    assert ranking.ml_component(2) == Fraction(1, 1)
    assert ranking.RANKED_NUMBERS[0] == 2


def test_component_values_are_not_observationally_normalized() -> None:
    spectral, ml = _component_fixture(
        spectral_number_1=Fraction(1, 4),
        spectral_number_2=Fraction(1, 8),
    )
    ranking = batch.rank_pairwise_scores(spectral, ml)
    assert ranking.pairwise_score(1) == Fraction(1, 8)
    assert ranking.pairwise_score(2) == Fraction(1, 16)


def test_exact_ties_use_ascending_number_without_parent_preference() -> None:
    zeros = [Fraction(0, 1)] * 49
    ranking = batch.rank_pairwise_scores(zeros, zeros)
    assert tuple(range(1, 50)) == ranking.RANKED_NUMBERS
    assert tuple(range(1, 50)) == ranking.POSITIONS


def test_changing_only_either_parent_component_can_change_pairwise_ordering() -> None:
    zeros = [Fraction(0, 1)] * 49
    spectral_changed = zeros.copy()
    spectral_changed[4] = Fraction(1, 1)
    ml_changed = zeros.copy()
    ml_changed[6] = Fraction(1, 1)
    baseline = batch.rank_pairwise_scores(zeros, zeros)
    assert batch.rank_pairwise_scores(spectral_changed, zeros).RANKED_NUMBERS[0] == 5
    assert batch.rank_pairwise_scores(zeros, ml_changed).RANKED_NUMBERS[0] == 7
    assert baseline.RANKED_NUMBERS[0] == 1


def test_pairwise_ranking_is_not_spectral_only_or_ml_only() -> None:
    spectral = [Fraction(0, 1)] * 49
    ml = [Fraction(0, 1)] * 49
    spectral[0] = Fraction(1, 1)
    spectral[2] = Fraction(3, 4)
    ml[1] = Fraction(1, 1)
    ml[2] = Fraction(3, 4)
    pairwise = batch.rank_pairwise_scores(spectral, ml)
    spectral_only = batch.rank_pairwise_scores(spectral, [Fraction(0, 1)] * 49)
    ml_only = batch.rank_pairwise_scores([Fraction(0, 1)] * 49, ml)
    assert pairwise.RANKED_NUMBERS != spectral_only.RANKED_NUMBERS
    assert pairwise.RANKED_NUMBERS != ml_only.RANKED_NUMBERS


def test_both_parent_callables_feed_the_pairwise_implementation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spectral, ml = _component_fixture(
        spectral_number_1=Fraction(1, 1),
        ml_number_2=Fraction(1, 1),
    )

    def fake_spectral(_history: object, _target_index: int) -> tuple[Fraction, ...]:
        return tuple(spectral)

    def fake_ml(_history: object, _target_index: int) -> tuple[Fraction, ...]:
        return tuple(ml)

    monkeypatch.setattr(batch, "calculate_spectral_components", fake_spectral)
    monkeypatch.setattr(batch, "calculate_ml_components", fake_ml)
    ranking = batch.calculate_pairwise_ranking((), 0)
    assert ranking.spectral_component(1) == Fraction(1, 1)
    assert ranking.ml_component(2) == Fraction(1, 1)
    assert ranking.RANKED_NUMBERS[:2] == (1, 2)


def test_ranked_pool_is_all_49_and_ticket_is_first_six_sorted_once() -> None:
    spectral, ml = _component_fixture(
        spectral_number_1=Fraction(1, 1),
        spectral_number_2=Fraction(3, 4),
    )
    ml[2] = Fraction(1, 1)
    ranking = batch.rank_pairwise_scores(spectral, ml)
    assert len(ranking.RANKED_NUMBERS) == 49
    assert set(ranking.RANKED_NUMBERS) == set(range(1, 50))
    assert batch.RANKED_POOL_CARDINALITY == 49
    assert batch.TICKET_SELECTION_RULE == "FIRST_6_RANKED_NUMBERS"
    assert tuple(sorted(ranking.RANKED_NUMBERS[:6])) == ranking.NATIVE_TICKET
    assert len(ranking.NATIVE_TICKET) == 6
    assert len(set(ranking.NATIVE_TICKET)) == 6
    assert all(1 <= number <= 49 for number in ranking.NATIVE_TICKET)
    assert ranking.TICKETS == (ranking.NATIVE_TICKET,)
    assert batch.NATIVE_TICKET_COUNT == 1


def test_candidate_output_is_deterministic_and_exactly_one_native_ticket() -> None:
    history = _history(306)
    first = batch.produce_candidate_portfolio(history, 306)
    second = batch.produce_candidate_portfolio(history, 306)
    assert first == second
    assert len(first) == 1
    assert len(first[0]) == 6
    assert first[0] == tuple(sorted(first[0]))
    assert all(isinstance(number, int) and 1 <= number <= 49 for number in first[0])


def test_rejects_float_components_instead_of_using_float_ranking() -> None:
    with pytest.raises(TypeError, match="exact Fraction"):
        batch.rank_pairwise_scores([0.1] + [Fraction(0, 1)] * 48, [Fraction(0, 1)] * 49)


def test_public_metadata_freezes_required_semantics() -> None:
    assert batch.SOURCE_UNIVERSE_CONTRACT["SELECTED_GAP_ID"] == batch.SELECTED_GAP_ID
    assert batch.SOURCE_UNIVERSE_CONTRACT["DESIGN_ID"] == batch.DESIGN_ID
    assert batch.SOURCE_UNIVERSE_CONTRACT["SPECTRAL_PARENT_ID"] == batch.SPECTRAL_PARENT_ID
    assert batch.SOURCE_UNIVERSE_CONTRACT["ML_PARENT_ID"] == batch.ML_PARENT_ID
    assert batch.SOURCE_UNIVERSE_CONTRACT["WINDOW"] == 300
    assert batch.SOURCE_UNIVERSE_CONTRACT["MINIMUM_HISTORY"] == 306
    assert batch.SOURCE_UNIVERSE_CONTRACT["RANKED_POOL_CARDINALITY"] == 49
    assert batch.SOURCE_UNIVERSE_CONTRACT["NATIVE_TICKET_COUNT"] == 1
    assert batch.IMPLEMENTATION_MODULE.endswith("candidate_batch_r1")
    assert getattr(batch, batch.IMPLEMENTATION_SYMBOL) is batch.produce_candidate_portfolio
