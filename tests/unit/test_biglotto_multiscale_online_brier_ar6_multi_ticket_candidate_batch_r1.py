"""Focused tests for the causal BigLotto online Brier AR6 candidate batch."""

# pyright: reportPrivateUsage=false

from __future__ import annotations

import inspect
from collections.abc import Iterable, Mapping
from fractions import Fraction
from itertools import combinations
from typing import cast

import pytest

from lottolab.research import (
    biglotto_conditional_cooccurrence_multi_ticket_candidate_batch_r1 as conditional_batch,
)
from lottolab.research import (
    biglotto_fixed_cross_family_ensemble_multi_ticket_candidate_batch_r1 as ensemble_batch,
)
from lottolab.research import (
    biglotto_graph_network_multi_ticket_candidate_batch_r1 as graph_batch,
)
from lottolab.research import (
    biglotto_multi_ticket_candidate_batch_r1 as frequency_batch,
)
from lottolab.research import (
    biglotto_multi_ticket_constructors_r1 as constructors,
)
from lottolab.research import (
    biglotto_multiscale_bayes_changepoint_bma_multi_ticket_candidate_batch_r1 as bayes_batch,
)
from lottolab.research import (
    biglotto_multiscale_codraw_geometric_residual_multi_ticket_candidate_batch_r1 as codraw_batch,
)
from lottolab.research import (
    biglotto_multiscale_markov_transition_multi_ticket_candidate_batch_r1 as markov_batch,
)
from lottolab.research import (
    biglotto_multiscale_official_null_surprise_multi_ticket_candidate_batch_r1 as null_batch,
)
from lottolab.research import (
    biglotto_multiscale_omission_pressure_multi_ticket_candidate_batch_r1 as omission_batch,
)
from lottolab.research import (
    biglotto_multiscale_online_brier_ar6_multi_ticket_candidate_batch_r1 as batch,
)
from lottolab.research import (
    biglotto_multiscale_spectral_concentration_multi_ticket_candidate_batch_r1 as spectral_batch,
)
from lottolab.research import (
    biglotto_multiscale_temporal_profile_cluster_multi_ticket_candidate_batch_r1 as cluster_batch,
)
from lottolab.research import (
    biglotto_renyi2_regime_switched_multi_ticket_candidate_batch_r1 as renyi2_batch,
)

Ticket = tuple[int, int, int, int, int, int]

_FILLER: Ticket = (30, 31, 32, 33, 34, 35)
_HISTORY_LENGTH = 756


def _draw_with_numbers(*numbers: int) -> Ticket:
    selected = list(dict.fromkeys(numbers))
    if len(selected) > 6:
        raise ValueError("fixture draw has more than six selected numbers")
    filler = [number for number in _FILLER if number not in selected]
    return cast(Ticket, tuple(sorted(selected + filler[: 6 - len(selected)])))


def _history_with_positions(
    number_positions: Mapping[int, Iterable[int]], length: int = _HISTORY_LENGTH
) -> tuple[Ticket, ...]:
    position_sets = {
        number: frozenset(positions) for number, positions in number_positions.items()
    }
    return tuple(
        _draw_with_numbers(
            *tuple(number for number, positions in position_sets.items() if index in positions)
        )
        for index in range(length)
    )


def _legal_ticket(ticket: object) -> bool:
    if not isinstance(ticket, tuple):
        return False
    numbers = cast(tuple[object, ...], ticket)
    if len(numbers) != 6 or not all(
        type(number) is int and 1 <= number <= 49 for number in numbers
    ):
        return False
    integer_numbers = cast(tuple[int, ...], numbers)
    return len(set(integer_numbers)) == 6 and tuple(sorted(integer_numbers)) == integer_numbers


_ZERO_INFORMATION_HISTORY: tuple[Ticket, ...] = tuple(
    _FILLER for _ in range(_HISTORY_LENGTH)
)
_ORDER_FIXTURE = _history_with_positions(
    {
        1: range(700, 750, 2),
        2: range(699, 749, 2),
        3: range(0, 50, 2),
    }
)


def _manual_horizon(
    horizon: int, normalized: tuple[Fraction, ...]
) -> batch.HorizonRanking:
    return batch.HorizonRanking(
        HORIZON=horizon,
        TARGET_PROBABILITIES=(Fraction(0, 1),) * 49,
        ORDERED_NUMBERS=tuple(range(1, 50)),
        POSITIONS=tuple(range(1, 50)),
        NORMALIZED_RANKS=normalized,
    )


def test_causality_minimum_prefix_target_exclusion_and_input_contract() -> None:
    with pytest.raises(batch.InsufficientHistoryError, match="required minimum 756"):
        batch.validate_prior_history(_ZERO_INFORMATION_HISTORY[:755], 755)
    assert len(batch.validate_prior_history(_ZERO_INFORMATION_HISTORY, 756)) == 756

    expected = batch.produce_source_ticket_universe(_ZERO_INFORMATION_HISTORY, 756)
    target_and_future: tuple[object, ...] = (
        *_ZERO_INFORMATION_HISTORY,
        (1, 2, 3, 4, 5, 6),
        object(),
    )
    assert batch.produce_source_ticket_universe(target_and_future, 756) == expected

    mutable_history = [list(draw) for draw in _ZERO_INFORMATION_HISTORY]
    before = [row.copy() for row in mutable_history]
    batch.produce_source_ticket_universe(mutable_history, 756)
    assert mutable_history == before

    malformed = list(_ZERO_INFORMATION_HISTORY)
    malformed[10] = (1, 2, 3, 4, 5, 5)
    with pytest.raises(ValueError, match="six unique numbers"):
        batch.calculate_horizon_rankings(malformed, 756)


def test_binary_labels_and_exact_ar6_features() -> None:
    history = _history_with_positions({1: (0, 2, 6), 2: (1,)}, length=8)
    assert batch.binary_occurrence(history[0], 1) == 1
    assert batch.binary_occurrence(history[1], 1) == 0
    assert batch.calculate_binary_occurrence_series(history, 1) == (
        1,
        0,
        1,
        0,
        0,
        0,
        1,
        0,
    )
    assert batch.calculate_binary_occurrence_at(history, 2, 1) == 1

    labels = (0, 1, 0, 1, 1, 0)
    assert batch.extract_lag_features(labels, 6) == (0, 1, 1, 0, 1, 0)
    assert batch.build_feature_vector(labels, 6) == (1, 0, 1, 1, 0, 1, 0)
    assert batch.FEATURE_DIMENSION == 7
    assert batch.FEATURE_RULE.endswith("OWN_NUMBER_ONLY;BINARY_EXACT")


def test_initialization_is_exact_and_independent() -> None:
    expected = (Fraction(6, 49), Fraction(0, 1), Fraction(0, 1), Fraction(0, 1),
                Fraction(0, 1), Fraction(0, 1), Fraction(0, 1))
    assert batch.initial_weights() == expected
    assert batch.initial_weights() == batch.initial_weights()
    assert batch.OFFICIAL_NULL_P0 == batch.INITIAL_INTERCEPT == Fraction(6, 49)
    assert (Fraction(0, 1),) * 6 == batch.INITIAL_LAG_WEIGHTS

    labels = tuple(index % 3 == 0 for index in range(756))
    labels = tuple(int(label) for label in labels)
    models = tuple(batch.train_online_model(labels, horizon) for horizon in batch.TRAINING_HORIZONS)
    assert all(expected == model.INITIAL_WEIGHTS for model in models)
    assert [model.HORIZON for model in models] == [50, 300, 750]


def test_raw_score_clipping_and_no_float_driven_probability() -> None:
    weights = (Fraction(1, 2), Fraction(1, 4), Fraction(0, 1), Fraction(0, 1),
               Fraction(0, 1), Fraction(0, 1), Fraction(0, 1))
    feature = (1, 1, 0, 0, 0, 0, 0)
    assert batch.raw_linear_score(weights, feature) == Fraction(3, 4)
    assert batch.clip_probability(Fraction(-1, 1)) == Fraction(0, 1)
    assert batch.clip_probability(Fraction(3, 4)) == Fraction(3, 4)
    assert batch.clip_probability(Fraction(2, 1)) == Fraction(1, 1)

    ranking = batch.rank_numbers_by_horizon(_ZERO_INFORMATION_HISTORY, 756, 50)
    assert all(type(score) is Fraction for score in ranking.TARGET_PROBABILITIES)


def test_online_update_uses_one_pre_update_error_for_all_coordinates() -> None:
    weights = batch.initial_weights()
    feature = (1, 1, 0, 0, 0, 0, 0)
    step = batch.online_update_step(weights, feature, 1)
    expected_error = Fraction(43, 49)
    expected_intercept = Fraction(6, 49) + Fraction(1, 64) * expected_error
    expected_lag_one = Fraction(1, 64) * expected_error
    assert Fraction(6, 49) == step.PREDICTION
    assert expected_error == step.ERROR
    assert (
        expected_intercept,
        expected_lag_one,
        Fraction(0, 1),
        Fraction(0, 1),
        Fraction(0, 1),
        Fraction(0, 1),
        Fraction(0, 1),
    ) == step.POST_UPDATE_WEIGHTS
    assert batch.online_delta_update(weights, feature, 1) == step.POST_UPDATE_WEIGHTS
    assert batch.brier_loss(step.PREDICTION, 1) == expected_error**2


def test_online_pass_is_chronological_single_pass_and_causal() -> None:
    labels = tuple(index % 2 for index in range(56))
    model = batch.train_online_model(labels, 50)
    assert model.TRAINING_START == 6
    assert model.TRAINING_END_EXCLUSIVE == 56
    assert tuple(range(6, 56)) == model.TRAINING_EXAMPLES
    assert labels[6:] == model.TRAINING_LABELS
    assert model.TRAINING_FEATURES[0] == batch.build_feature_vector(labels, 6)
    assert len(model.TRAINING_PREDICTIONS) == 50
    assert len(model.BRIER_LOSSES) == 50

    base = (0,) * 56
    changed_current = (*base[:6], 1, *base[7:])
    first = batch.train_online_model(base, 50)
    second = batch.train_online_model(changed_current, 50)
    assert first.TRAINING_PREDICTIONS[0] == second.TRAINING_PREDICTIONS[0]
    assert first.TRAINING_PREDICTIONS[1] != second.TRAINING_PREDICTIONS[1]

    target_zero = batch.train_online_model((*base, 0), 50, target_index=56)
    target_one = batch.train_online_model((*base, 1), 50, target_index=56)
    future_mutated = batch.train_online_model((*base, 1, object()), 50, target_index=56)
    assert target_zero.TARGET_PROBABILITY == target_one.TARGET_PROBABILITY
    assert target_zero.WEIGHTS == target_one.WEIGHTS == future_mutated.WEIGHTS


def test_multiscale_training_uses_exact_trailing_horizons_with_reset() -> None:
    labels = tuple(int(index % 5 == 0) for index in range(756))
    models = {
        horizon: batch.train_online_model(labels, horizon)
        for horizon in batch.TRAINING_HORIZONS
    }
    assert models[50].TRAINING_START == 706
    assert models[300].TRAINING_START == 456
    assert models[750].TRAINING_START == 6
    assert labels[-50:] == models[50].TRAINING_LABELS
    assert labels[-300:] == models[300].TRAINING_LABELS
    assert labels[-750:] == models[750].TRAINING_LABELS
    assert all(batch.initial_weights() == model.INITIAL_WEIGHTS for model in models.values())


def test_online_specificity_equal_count_and_equal_tail_histories_differ() -> None:
    alternating = tuple([1, 0] * 28)
    reversed_order = tuple(reversed(alternating))
    first = batch.train_online_model(alternating, 50)
    second = batch.train_online_model(reversed_order, 50)
    assert sum(alternating) == sum(reversed_order)
    assert first.TARGET_PROBABILITY != second.TARGET_PROBABILITY

    same_tail_a = alternating
    same_tail_b = (0,) * 50 + alternating[-6:]
    first_tail = batch.train_online_model(same_tail_a, 50)
    second_tail = batch.train_online_model(same_tail_b, 50)
    assert same_tail_a[-6:] == same_tail_b[-6:]
    assert first_tail.TARGET_FEATURE == second_tail.TARGET_FEATURE
    assert first_tail.TARGET_PROBABILITY != second_tail.TARGET_PROBABILITY


def test_online_ranking_differs_from_occurrence_and_other_families() -> None:
    ml_ranking = batch.calculate_fused_number_ranking(_ORDER_FIXTURE, 756)
    frequency_ranking = frequency_batch.calculate_fused_number_ranking(_ORDER_FIXTURE, 756)
    assert ml_ranking.ORDERED_NUMBERS != frequency_ranking.ORDERED_NUMBERS

    predecessors = (
        frequency_batch,
        conditional_batch,
        renyi2_batch,
        graph_batch,
        ensemble_batch,
        markov_batch,
        omission_batch,
        bayes_batch,
        cluster_batch,
        codraw_batch,
        spectral_batch,
        null_batch,
    )
    assert all(batch.SOURCE_UNIVERSE_ID != item.SOURCE_UNIVERSE_ID for item in predecessors)
    source = inspect.getsource(batch).lower()
    for forbidden in (
        "markov",
        "bayesian",
        "spectral",
        "posterior",
        "cooccurrence",
        "transition",
        "geometry",
        "frequency",
    ):
        assert forbidden not in source
    assert "OWN_NUMBER_ONLY" in batch.FEATURE_RULE
    assert "_constructors.construct_" in source


def test_horizon_ranking_probability_primary_number_tiebreak_and_exact_normalization() -> None:
    ranking = batch.rank_numbers_by_horizon(_ZERO_INFORMATION_HISTORY, 756, 50)
    assert ranking.ORDERED_NUMBERS[6:35] == tuple(range(1, 30))
    for left, right in zip(
        ranking.ORDERED_NUMBERS, ranking.ORDERED_NUMBERS[1:], strict=False
    ):
        left_score = ranking.target_probability(left)
        right_score = ranking.target_probability(right)
        assert left_score > right_score or (left_score == right_score and left < right)
    for number in range(1, 50):
        assert ranking.normalized_rank(number) == Fraction(49 - ranking.position(number), 48)


def test_exact_equal_rank_fusion_uses_robustness_precedence() -> None:
    r50 = [Fraction(0, 1)] * 49
    r300 = [Fraction(0, 1)] * 49
    r750 = [Fraction(0, 1)] * 49
    r50[0], r50[1], r50[2] = Fraction(1, 1), Fraction(2, 3), Fraction(1, 2)
    r300[0], r300[1], r300[2] = Fraction(0, 1), Fraction(1, 3), Fraction(1, 3)
    r750[0], r750[1], r750[2] = Fraction(0, 1), Fraction(0, 1), Fraction(1, 6)
    fused = batch.fuse_horizon_rankings(
        (
            _manual_horizon(50, tuple(r50)),
            _manual_horizon(300, tuple(r300)),
            _manual_horizon(750, tuple(r750)),
        )
    )
    assert fused.mean_rank(1) == fused.mean_rank(2) == fused.mean_rank(3) == Fraction(1, 3)
    assert fused.robustness(3) == (Fraction(1, 6), Fraction(1, 3), Fraction(1, 2))
    assert fused.robustness(2) == (Fraction(0, 1), Fraction(1, 3), Fraction(2, 3))
    assert fused.robustness(1) == (Fraction(0, 1), Fraction(0, 1), Fraction(1, 1))
    assert fused.ORDERED_NUMBERS[:3] == (3, 2, 1)


def test_source_universe_is_exact_rank_position_combination_order() -> None:
    fused = batch.calculate_fused_number_ranking(_ORDER_FIXTURE, 756)
    source = batch.produce_source_ticket_universe(_ORDER_FIXTURE, 756)
    expected = tuple(
        tuple(sorted(fused.TOP_NUMBERS[position] for position in positions))
        for positions in combinations(range(10), 6)
    )
    assert len(fused.TOP_NUMBERS) == 10
    assert len(source) == 210
    assert source == expected
    assert len(set(source)) == 210
    assert all(_legal_ticket(ticket) for ticket in source)


def test_candidate_identity_is_exact_three_by_three_and_canonical() -> None:
    assert len(batch.CANDIDATE_AUTHORITIES) == 9
    assert len(set(batch.CANDIDATE_IDS)) == 9
    assert len(set(batch.CANDIDATE_SIGNATURE_HASHES.values())) == 9
    assert all(candidate_id.startswith("BMSGV1_ML_") for candidate_id in batch.CANDIDATE_IDS)
    expected_pairs = {
        (constructor_id, count)
        for constructor_id in batch.CONSTRUCTOR_IDS
        for count in batch.TICKET_COUNTS
    }
    assert {
        (metadata.CONSTRUCTOR_ID, metadata.TICKET_COUNT)
        for metadata in batch.CANDIDATE_AUTHORITIES
    } == expected_pairs
    assert sum(meta.TICKET_COUNT == 5 for meta in batch.CANDIDATE_AUTHORITIES) == 3
    assert sum(meta.TICKET_COUNT == 10 for meta in batch.CANDIDATE_AUTHORITIES) == 3
    assert sum(meta.TICKET_COUNT == 20 for meta in batch.CANDIDATE_AUTHORITIES) == 3

    for metadata in batch.CANDIDATE_AUTHORITIES:
        semantics = metadata.SEMANTICS
        assert semantics["METHOD_FAMILY"] == "ML_LIKE"
        assert semantics["INITIAL_INTERCEPT"] == Fraction(6, 49)
        assert semantics["LEARNING_RATE"] == Fraction(1, 64)
        assert semantics["RNG"] is None
        assert semantics["RNG_SEED"] is None
        identity = batch.derive_candidate_identity(semantics)
        assert identity.CANDIDATE_ID == metadata.CANDIDATE_ID
        assert identity.SIGNATURE_HASH == metadata.SIGNATURE_HASH
        assert " " not in identity.CANONICAL_SEMANTIC_JSON


def test_no_collision_with_all_twelve_predecessor_lane1_batches() -> None:
    predecessors = (
        frequency_batch,
        conditional_batch,
        renyi2_batch,
        graph_batch,
        ensemble_batch,
        markov_batch,
        omission_batch,
        bayes_batch,
        cluster_batch,
        codraw_batch,
        spectral_batch,
        null_batch,
    )
    predecessor_ids: set[str] = set()
    predecessor_signatures: set[str] = set()
    for predecessor in predecessors:
        predecessor_ids.update(predecessor.CANDIDATE_IDS)
        raw_signatures: object = predecessor.CANDIDATE_SIGNATURE_HASHES
        if isinstance(raw_signatures, Mapping):
            predecessor_signatures.update(cast(Mapping[str, str], raw_signatures).values())
        else:
            predecessor_signatures.update(cast(Iterable[str], raw_signatures))
    assert set(batch.CANDIDATE_IDS).isdisjoint(predecessor_ids)
    assert set(batch.CANDIDATE_SIGNATURE_HASHES.values()).isdisjoint(predecessor_signatures)


def test_candidates_are_legal_deterministic_and_prefix_stable() -> None:
    first_by_constructor: dict[str, dict[int, tuple[Ticket, ...]]] = {}
    for metadata in batch.CANDIDATE_AUTHORITIES:
        first = batch.produce_candidate_portfolio(
            metadata.CANDIDATE_ID, _ORDER_FIXTURE, 756
        )
        second = batch.produce_candidate_portfolio(
            metadata.CANDIDATE_ID, _ORDER_FIXTURE, 756
        )
        assert len(first) == metadata.TICKET_COUNT
        assert len(set(first)) == metadata.TICKET_COUNT
        assert all(_legal_ticket(ticket) for ticket in first)
        assert first == second
        first_by_constructor.setdefault(metadata.CONSTRUCTOR_ID, {})[metadata.TICKET_COUNT] = first

    for outputs in first_by_constructor.values():
        assert outputs[10][:5] == outputs[5]
        assert outputs[20][:10] == outputs[10]


def test_frozen_constructors_are_invoked_directly() -> None:
    universe = batch.produce_source_ticket_universe(_ORDER_FIXTURE, 756)
    assert batch.produce_candidate_portfolio(
        batch.candidate_id_for(batch.CONSTRUCTOR_IDS[0], 5), _ORDER_FIXTURE, 756
    ) == constructors.construct_b649_candidate_set_low_overlap_v1(universe, 5)
    assert batch.produce_candidate_portfolio(
        batch.candidate_id_for(batch.CONSTRUCTOR_IDS[1], 10), _ORDER_FIXTURE, 756
    ) == constructors.construct_b649_candidate_set_exposure_balanced_v1(universe, 10)
    assert batch.produce_candidate_portfolio(
        batch.candidate_id_for(batch.CONSTRUCTOR_IDS[2], 20), _ORDER_FIXTURE, 756
    ) == constructors.construct_b649_candidate_set_hybrid_diversity_v1(universe, 20)


def test_source_has_no_catalog_database_network_clock_or_rng_surface() -> None:
    source = inspect.getsource(batch).lower()
    for forbidden in (
        "production_catalog",
        "import os",
        "import pathlib",
        "import random",
        "import sqlite",
        "import requests",
        "import socket",
        "import time",
        "def _select_low_overlap",
        "def _select_exposure_balanced",
        "def _select_hybrid_diversity",
    ):
        assert forbidden not in source
    assert batch.RNG_SEMANTICS == "NONE"
    assert batch.RNG is None


def test_lottery_contract_constants_are_frozen() -> None:
    assert batch.SOURCE_UNIVERSE_ID == "B649_MULTISCALE_ONLINE_BRIER_AR6_RANKED_POOL_V1"
    assert batch.METHOD_FAMILY == "ML_LIKE"
    assert batch.MODEL_CLASS == "ONLINE_LINEAR_PROBABILITY_AUTOREGRESSION"
    assert batch.LOSS_FAMILY == "BRIER_SQUARED_ERROR"
    assert batch.NUMBER_DOMAIN == (1, 49)
    assert batch.PICK_COUNT == 6
    assert batch.TRAINING_HORIZONS == (50, 300, 750)
    assert batch.AUTOREGRESSIVE_LAG_DEPTH == 6
    assert batch.FEATURE_DIMENSION == 7
    assert batch.MINIMUM_HISTORY == 756
    assert Fraction(1, 64) == batch.LEARNING_RATE
    assert batch.SOURCE_CANDIDATE_TICKET_COUNT == 210
    assert batch.TICKET_COUNTS == (5, 10, 20)
