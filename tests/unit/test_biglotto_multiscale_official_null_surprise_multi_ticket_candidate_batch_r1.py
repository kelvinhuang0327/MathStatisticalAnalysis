"""Focused tests for the causal BigLotto official-null candidate batch."""

# pyright: reportPrivateUsage=false

from __future__ import annotations

import inspect
from collections.abc import Callable, Iterable, Mapping
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
    biglotto_multiscale_official_null_surprise_multi_ticket_candidate_batch_r1 as batch,
)
from lottolab.research import (
    biglotto_multiscale_omission_pressure_multi_ticket_candidate_batch_r1 as omission_batch,
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
_HISTORY_LENGTH = 750


def _draw_with_numbers(*numbers: int) -> Ticket:
    selected = list(dict.fromkeys(numbers))
    if len(selected) > 6:
        raise ValueError("fixture draw has more than six selected numbers")
    filler = [number for number in _FILLER if number not in selected]
    values = selected + filler[: 6 - len(selected)]
    return cast(Ticket, tuple(sorted(values)))


def _history_with_positions(
    number_positions: Mapping[int, Iterable[int]],
) -> tuple[Ticket, ...]:
    position_sets = {
        number: frozenset(positions) for number, positions in number_positions.items()
    }
    history: list[Ticket] = []
    for index in range(_HISTORY_LENGTH):
        active = tuple(
            number for number, positions in position_sets.items() if index in positions
        )
        history.append(_draw_with_numbers(*active))
    return tuple(history)


def _legal_ticket(ticket: object) -> bool:
    if not isinstance(ticket, tuple):
        return False
    raw_numbers = cast(tuple[object, ...], ticket)
    if len(raw_numbers) != 6:
        return False
    numbers = cast(tuple[int, ...], raw_numbers)
    return (
        all(type(number) is int and 1 <= number <= 49 for number in numbers)
        and len(set(numbers)) == 6
        and tuple(sorted(numbers)) == numbers
    )


_ZERO_INFORMATION_HISTORY: tuple[Ticket, ...] = tuple(
    _FILLER for _ in range(_HISTORY_LENGTH)
)
_COUNT_FIXTURE = _history_with_positions(
    {
        1: (700, 701, 702),
        2: range(500, 507),
        3: range(4),
    }
)


def _manual_ranking(window: int, normalized: tuple[Fraction, ...]) -> batch.WindowRanking:
    expected = batch.expected_count(window)
    variance = batch.null_variance(window)
    return batch.WindowRanking(
        WINDOW=window,
        WINDOW_DRAW_COUNT=window,
        OCCURRENCE_COUNTS=(0,) * 49,
        EXPECTED_COUNTS=(expected,) * 49,
        NULL_VARIANCES=(variance,) * 49,
        SIGNED_NULL_RESIDUALS=(0,) * 49,
        OFFICIAL_NULL_Z2S=(Fraction(0, 1),) * 49,
        NULL_DIRECTIONS=("NEUTRAL",) * 49,
        ORDERED_NUMBERS=tuple(range(1, 50)),
        POSITIONS=tuple(range(1, 50)),
        NORMALIZED_RANKS=normalized,
        CALCULATIONS=(),
    )


def test_causality_minimum_prefix_and_input_contract() -> None:
    with pytest.raises(batch.InsufficientHistoryError, match="required minimum 750"):
        batch.validate_prior_history(_ZERO_INFORMATION_HISTORY[:749], 749)
    assert len(batch.validate_prior_history(_ZERO_INFORMATION_HISTORY, 750)) == 750

    target_and_future: tuple[object, ...] = (
        *_ZERO_INFORMATION_HISTORY,
        (44, 45, 46, 47, 48, 49),
        object(),
    )
    expected = batch.produce_source_ticket_universe(_ZERO_INFORMATION_HISTORY, 750)
    assert batch.produce_source_ticket_universe(target_and_future, 750) == expected

    mutable_history = [list(draw) for draw in _ZERO_INFORMATION_HISTORY]
    before = [row.copy() for row in mutable_history]
    batch.produce_source_ticket_universe(mutable_history, 750)
    assert mutable_history == before

    malformed = list(_ZERO_INFORMATION_HISTORY)
    malformed[10] = (1, 2, 3, 4, 5, 5)
    with pytest.raises(ValueError, match="six unique numbers"):
        batch.calculate_window_counts(malformed, 750, 50)


def test_official_null_constants_expected_count_variance_and_exact_z2() -> None:
    assert Fraction(6, 49) == batch.OFFICIAL_NULL_P0
    assert Fraction(6, 49) == batch.P0
    assert batch.expected_count(50) == Fraction(300, 49)
    assert batch.expected_count(300) == Fraction(1800, 49)
    assert batch.expected_count(750) == Fraction(4500, 49)
    assert batch.null_variance(50) == Fraction(258 * 50, 2401)
    assert batch.null_variance(300) == Fraction(258 * 300, 2401)
    assert batch.null_variance(750) == Fraction(258 * 750, 2401)

    count = 5
    window = 50
    direct = (
        Fraction(count, 1) - batch.expected_count(window)
    ) ** 2 / batch.null_variance(window)
    simplified = Fraction((49 * count - 6 * window) ** 2, 258 * window)
    assert batch.official_null_z2(count, window) == direct == simplified
    assert batch.official_null_z2(5, 50) >= 0
    assert batch.official_null_z2(6, 49) == 0
    assert batch.official_null_z2(5, 49) == batch.official_null_z2(7, 49)


def test_signed_residual_and_direction_are_diagnostic_only() -> None:
    assert batch.signed_null_residual(0, 50) == -300
    assert batch.signed_null_residual(13, 50) == 337
    assert batch.null_direction(-300) == "COLD"
    assert batch.null_direction(337) == "HOT"
    assert batch.null_direction(0) == "NEUTRAL"
    assert batch.direction_for_count(0, 50) == "COLD"
    assert batch.direction_for_count(13, 50) == "HOT"

    # Equal exact scores are ordered by number, with no sign-based key.
    assert tuple(sorted((5, 7), key=lambda n: (-batch.official_null_z2(n, 49), n))) == (
        5,
        7,
    )
    assert batch.SIGN_DIRECTION_USED_FOR_RANKING == "NO"


def test_counts_and_window_slices_are_exact() -> None:
    r50 = batch.rank_numbers_by_window(_COUNT_FIXTURE, 750, 50)
    r300 = batch.rank_numbers_by_window(_COUNT_FIXTURE, 750, 300)
    r750 = batch.rank_numbers_by_window(_COUNT_FIXTURE, 750, 750)
    assert r50.occurrence_count(1) == 3
    assert r300.occurrence_count(1) == 3
    assert r750.occurrence_count(1) == 3
    assert r50.occurrence_count(2) == 0
    assert r300.occurrence_count(2) == 7
    assert r750.occurrence_count(2) == 7
    assert r50.occurrence_count(3) == 0
    assert r300.occurrence_count(3) == 0
    assert r750.occurrence_count(3) == 4
    assert r50.WINDOW_DRAW_COUNT == 50
    assert r300.WINDOW_DRAW_COUNT == 300
    assert r750.WINDOW_DRAW_COUNT == 750


def test_two_sided_cold_surprise_can_beat_more_frequent_hot_count() -> None:
    assert batch.official_null_z2(0, 50) > batch.official_null_z2(12, 50)
    history = _history_with_positions({2: range(700, 712)})
    ranking = batch.rank_numbers_by_window(history, 750, 50)
    assert ranking.occurrence_count(2) == 12
    assert ranking.official_null_z2(1) > ranking.official_null_z2(2)
    assert ranking.null_direction(1) == "COLD"
    assert ranking.null_direction(2) == "HOT"
    assert ranking.position(1) < ranking.position(2)


def test_permutation_and_last_hit_gap_invariance() -> None:
    first = _history_with_positions({1: (700, 710, 720, 730, 740)})
    altered = _history_with_positions({1: (705, 715, 725, 735, 745)})
    first_ranking = batch.rank_numbers_by_window(first, 750, 50)
    altered_ranking = batch.rank_numbers_by_window(altered, 750, 50)
    assert first_ranking.occurrence_count(1) == altered_ranking.occurrence_count(1) == 5
    assert first_ranking.SIGNED_NULL_RESIDUALS == altered_ranking.SIGNED_NULL_RESIDUALS
    assert first_ranking.OFFICIAL_NULL_Z2S == altered_ranking.OFFICIAL_NULL_Z2S


def test_null_source_differs_from_raw_frequency_and_temporal_or_posterior_families() -> None:
    null_ranking = batch.calculate_fused_number_ranking(_COUNT_FIXTURE, 750)
    raw_counts = {number: 0 for number in range(1, 50)}
    for draw in _COUNT_FIXTURE[-50:]:
        for number in draw:
            raw_counts[number] += 1
    raw_frequency = tuple(sorted(raw_counts, key=lambda number: (-raw_counts[number], number)))
    assert raw_frequency != null_ranking.ORDERED_NUMBERS
    assert frequency_batch.calculate_fused_number_ranking(
        _COUNT_FIXTURE, 750
    ).ORDERED_NUMBERS != null_ranking.ORDERED_NUMBERS
    assert batch.SOURCE_UNIVERSE_ID != omission_batch.SOURCE_UNIVERSE_ID
    assert batch.SOURCE_UNIVERSE_ID != bayes_batch.SOURCE_UNIVERSE_ID
    assert batch.SOURCE_UNIVERSE_ID != spectral_batch.SOURCE_UNIVERSE_ID
    assert batch.LAST_HIT_GAP_USED == "NO"
    assert batch.TEMPORAL_ORDER_USED_WITHIN_WINDOW == "NO"
    source = inspect.getsource(batch)
    assert "posterior" not in source.lower()
    assert "spectral" not in source.lower()
    assert "markov" not in source.lower()


def test_same_total_history_can_have_different_multiscale_fused_ranking() -> None:
    recent_number_one = _history_with_positions(
        {1: range(700, 705), 2: range(500, 505)}
    )
    recent_number_two = _history_with_positions(
        {1: range(500, 505), 2: range(700, 705)}
    )
    first = batch.calculate_fused_number_ranking(recent_number_one, 750)
    second = batch.calculate_fused_number_ranking(recent_number_two, 750)
    assert first.WINDOW_RANKINGS[2].OCCURRENCE_COUNTS == second.WINDOW_RANKINGS[2].OCCURRENCE_COUNTS
    assert first.ORDERED_NUMBERS != second.ORDERED_NUMBERS


def test_window_fusion_uses_exact_rank_mean_robustness_and_number_fallback() -> None:
    r50 = [Fraction(0, 1)] * 49
    r300 = [Fraction(0, 1)] * 49
    r750 = [Fraction(0, 1)] * 49
    r50[0], r50[1], r50[2] = Fraction(1, 1), Fraction(2, 3), Fraction(1, 2)
    r300[0], r300[1], r300[2] = Fraction(0, 1), Fraction(1, 3), Fraction(1, 3)
    r750[0], r750[1], r750[2] = Fraction(0, 1), Fraction(0, 1), Fraction(1, 6)
    fused = batch.fuse_window_rankings(
        (
            _manual_ranking(50, tuple(r50)),
            _manual_ranking(300, tuple(r300)),
            _manual_ranking(750, tuple(r750)),
        )
    )
    assert fused.mean_rank(1) == fused.mean_rank(2) == fused.mean_rank(3) == Fraction(1, 3)
    assert fused.robustness(3) == (Fraction(1, 6), Fraction(1, 3), Fraction(1, 2))
    assert fused.robustness(2) == (Fraction(0, 1), Fraction(1, 3), Fraction(2, 3))
    assert fused.robustness(1) == (Fraction(0, 1), Fraction(0, 1), Fraction(1, 1))
    assert fused.ORDERED_NUMBERS[:3] == (3, 2, 1)


def test_source_universe_has_exact_top10_and_rank_position_ticket_order() -> None:
    fused = batch.calculate_fused_number_ranking(_ZERO_INFORMATION_HISTORY, 750)
    source = batch.produce_source_ticket_universe(_ZERO_INFORMATION_HISTORY, 750)
    expected = tuple(
        tuple(sorted(fused.TOP_NUMBERS[position] for position in combo))
        for combo in combinations(range(10), 6)
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
    assert all(candidate_id.startswith("BMSGV1_NB_") for candidate_id in batch.CANDIDATE_IDS)
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

    required_keys = {
        "CAUSAL_CUTOFF_RULE",
        "CONSTRUCTOR_ID",
        "CONSTRUCTOR_VERSION",
        "EXPECTED_COUNT_RULE",
        "FEATURE_WINDOWS",
        "HYPOTHESIS_VERSION",
        "LAST_HIT_GAP_USED",
        "METHOD_FAMILY",
        "NULL_VARIANCE_RULE",
        "OFFICIAL_NULL_P0",
        "OFFICIAL_NULL_Z2_RULE",
        "PER_WINDOW_RANKING_RULE",
        "SIGN_DIRECTION_USED_FOR_RANKING",
        "SOURCE_UNIVERSE_ID",
        "SOURCE_UNIVERSE_VERSION",
        "TICKET_COUNT",
        "WINDOW_FUSION_RULE",
    }
    for metadata in batch.CANDIDATE_AUTHORITIES:
        semantics = metadata.SEMANTICS
        assert required_keys <= semantics.keys()
        assert semantics["METHOD_FAMILY"] == "NULL_BASELINE"
        assert semantics["OFFICIAL_NULL_P0"] == Fraction(6, 49)
        assert semantics["RNG_SEED"] is None
        identity = batch.derive_candidate_identity(semantics)
        assert identity.CANDIDATE_ID == metadata.CANDIDATE_ID
        assert identity.SIGNATURE_HASH == metadata.SIGNATURE_HASH
        assert " " not in identity.CANONICAL_SEMANTIC_JSON


def test_no_collision_with_all_eleven_predecessor_lane1_batches() -> None:
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


def test_source_has_no_production_catalog_or_external_io() -> None:
    source = inspect.getsource(batch)
    assert "_constructors.construct_" in source
    assert "def _select_low_overlap" not in source
    assert "def _select_exposure_balanced" not in source
    assert "def _select_hybrid_diversity" not in source
    assert "production_catalog" not in source
    assert "import os" not in source
    assert "import pathlib" not in source
    assert "import random" not in source
    assert "import sqlite" not in source
    assert "import requests" not in source
    assert "import socket" not in source
    assert "import time" not in source
    assert "p_value" not in source
    assert "chi_square" not in source


@pytest.mark.parametrize(
    "metadata", batch.CANDIDATE_AUTHORITIES, ids=lambda item: item.CANDIDATE_ID
)
def test_all_candidate_portfolios_are_legal_distinct_and_deterministic(
    metadata: batch.CandidateMetadata,
) -> None:
    first = batch.produce_candidate_portfolio(
        metadata.CANDIDATE_ID, _ZERO_INFORMATION_HISTORY, 750
    )
    second = batch.produce_candidate_portfolio(
        metadata.CANDIDATE_ID, _ZERO_INFORMATION_HISTORY, 750
    )
    assert len(first) == metadata.TICKET_COUNT
    assert len(set(first)) == metadata.TICKET_COUNT
    assert all(_legal_ticket(ticket) for ticket in first)
    assert first == second


@pytest.mark.parametrize("constructor_id", batch.CONSTRUCTOR_IDS)
def test_budget_outputs_are_exact_prefixes_by_constructor(constructor_id: str) -> None:
    outputs = {
        count: batch.produce_candidate_portfolio(
            batch.candidate_id_for(constructor_id, count), _ZERO_INFORMATION_HISTORY, 750
        )
        for count in batch.TICKET_COUNTS
    }
    assert outputs[10][:5] == outputs[5]
    assert outputs[20][:10] == outputs[10]


def test_frozen_constructors_are_invoked_directly() -> None:
    universe = batch.produce_source_ticket_universe(_COUNT_FIXTURE, 750)
    low = constructors.construct_b649_candidate_set_low_overlap_v1(universe, 5)
    exposure = constructors.construct_b649_candidate_set_exposure_balanced_v1(universe, 10)
    hybrid = constructors.construct_b649_candidate_set_hybrid_diversity_v1(universe, 20)
    assert batch.produce_b649_multiscale_official_null_surprise_multiticket_low_overlap_v1_k5(
        _COUNT_FIXTURE, 750
    ) == low
    assert (
        batch.produce_b649_multiscale_official_null_surprise_multiticket_exposure_balanced_v1_k10(
            _COUNT_FIXTURE, 750
        )
        == exposure
    )
    assert batch.produce_b649_multiscale_official_null_surprise_multiticket_hybrid_diversity_v1_k20(
        _COUNT_FIXTURE, 750
    ) == hybrid


def test_named_producers_cover_all_nine_candidates() -> None:
    symbols = {
        metadata.IMPLEMENTATION_SYMBOL for metadata in batch.CANDIDATE_AUTHORITIES
    }
    assert len(symbols) == 9
    for symbol in symbols:
        producer = cast(
            Callable[[batch.HistoryInput, int], batch.TicketPortfolio],
            getattr(batch, symbol),
        )
        metadata = next(
            item for item in batch.CANDIDATE_AUTHORITIES if symbol == item.IMPLEMENTATION_SYMBOL
        )
        assert len(producer(_ZERO_INFORMATION_HISTORY, 750)) == metadata.TICKET_COUNT


def test_lottery_and_source_contract_constants_are_frozen() -> None:
    assert batch.SOURCE_UNIVERSE_ID == "B649_MULTISCALE_OFFICIAL_NULL_Z2_RANKED_POOL_V1"
    assert batch.METHOD_FAMILY == "NULL_BASELINE"
    assert batch.NUMBER_DOMAIN == (1, 49)
    assert batch.PICK_COUNT == 6
    assert batch.FEATURE_WINDOWS == (50, 300, 750)
    assert batch.SOURCE_CANDIDATE_TICKET_COUNT == 210
    assert batch.TICKET_COUNTS == (5, 10, 20)
    assert batch.SIGN_DIRECTION_USED_FOR_RANKING == "NO"
    assert batch.TEMPORAL_ORDER_USED_WITHIN_WINDOW == "NO"
