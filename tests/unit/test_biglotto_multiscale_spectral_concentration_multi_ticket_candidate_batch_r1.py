"""Focused tests for the causal BigLotto spectral-concentration candidate batch."""

# pyright: reportPrivateUsage=false

from __future__ import annotations

import inspect
from collections.abc import Callable, Iterable, Mapping
from fractions import Fraction
from itertools import combinations
from typing import cast

import pytest

from lottolab.domain.draws import LotteryType
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
    biglotto_multiscale_omission_pressure_multi_ticket_candidate_batch_r1 as omission_batch,
)
from lottolab.research import (
    biglotto_multiscale_spectral_concentration_multi_ticket_candidate_batch_r1 as batch,
)
from lottolab.research import (
    biglotto_multiscale_temporal_profile_cluster_multi_ticket_candidate_batch_r1 as cluster_batch,
)
from lottolab.research import (
    biglotto_renyi2_regime_switched_multi_ticket_candidate_batch_r1 as renyi2_batch,
)
from lottolab.strategies.adapters import biglotto_power_fourier_rhythm as power_fourier
from lottolab.strategies.adapters.base import CausalDrawRow

Ticket = tuple[int, int, int, int, int, int]


def _repeat(draw: Ticket, count: int) -> tuple[Ticket, ...]:
    return tuple(draw for _ in range(count))


def _make_distinct_draw(index: int) -> Ticket:
    start = (index * 6) % 43 + 1
    return (start, start + 1, start + 2, start + 3, start + 4, start + 5)


def _draw_with_numbers(*numbers: int) -> Ticket:
    values = [30, 31, 32, 33, 34, 35]
    for position, number in enumerate(numbers):
        values[position] = number
    return cast(Ticket, tuple(sorted(values)))


_FILLER: Ticket = (30, 31, 32, 33, 34, 35)
_ANCHOR: Ticket = (1, 2, 3, 4, 5, 6)
_HISTORY: tuple[Ticket, ...] = (*tuple(_make_distinct_draw(i) for i in range(749)), _ANCHOR)
_ZERO_INFORMATION_HISTORY: tuple[Ticket, ...] = _repeat(_FILLER, 750)

_PERIODIC_POSITIONS = frozenset({0, 10, 20, 30, 40})
_IRREGULAR_POSITIONS = frozenset({0, 1, 2, 3, 4})
_SPECTRAL_WINDOW_HISTORY: tuple[Ticket, ...] = (
    *_repeat(_FILLER, 700),
    *tuple(
        _draw_with_numbers(
            *tuple(
                number
                for number, positions in (
                    (1, _PERIODIC_POSITIONS),
                    (2, _IRREGULAR_POSITIONS),
                )
                if index in positions
            )
        )
        for index in range(50)
    ),
)


def _legal_ticket(ticket: object) -> bool:
    if not isinstance(ticket, tuple):
        return False
    raw_numbers = cast(tuple[object, ...], ticket)
    if len(raw_numbers) != 6:
        return False
    return (
        all(type(number) is int and 1 <= number <= 49 for number in raw_numbers)
        and len(set(cast(tuple[int, ...], raw_numbers))) == 6
        and tuple(sorted(cast(tuple[int, ...], raw_numbers))) == raw_numbers
    )


def _manual_ranking(window: int, normalized: tuple[Fraction, ...]) -> batch.WindowRanking:
    return batch.WindowRanking(
        WINDOW=window,
        WINDOW_DRAW_COUNT=window,
        OCCURRENCE_COUNTS=(0,) * 49,
        MEANS=(Fraction(0, 1),) * 49,
        SPECTRAL_IPRS=(Fraction(0, 1),) * 49,
        PEAK_NORMALIZED_CIRCULAR_AUTOCORRS=(Fraction(0, 1),) * 49,
        ORDERED_NUMBERS=tuple(range(1, 50)),
        POSITIONS=tuple(range(1, 50)),
        NORMALIZED_RANKS=normalized,
        CALCULATIONS=(),
    )


def _power_rows(positions: frozenset[int]) -> tuple[CausalDrawRow, ...]:
    rows: list[CausalDrawRow] = []
    for index in range(750):
        numbers = _FILLER if index not in positions else _draw_with_numbers(17)
        rows.append(
            CausalDrawRow(
                draw=str(index + 1),
                date="2026-01-01",
                numbers=numbers,
            )
        )
    return tuple(rows)


# --- Causality and input validation ---


def test_fewer_than_750_prior_draws_are_rejected() -> None:
    with pytest.raises(batch.InsufficientHistoryError, match="required minimum 750"):
        batch.validate_prior_history(_HISTORY[:749], 749)


def test_exactly_750_prior_draws_are_accepted() -> None:
    assert len(batch.produce_source_ticket_universe(_HISTORY, 750)) == 210


def test_target_row_is_excluded_and_future_suffix_is_invariant() -> None:
    target_row: object = (44, 45, 46, 47, 48, 49)
    future_suffix: tuple[object, ...] = (object(), ("unreadable",))
    with_target = (*_HISTORY, target_row, *future_suffix)
    expected = batch.produce_source_ticket_universe(_HISTORY, 750)
    assert batch.produce_source_ticket_universe(with_target, 750) == expected


def test_input_history_is_not_mutated() -> None:
    history = [list(draw) for draw in _HISTORY]
    before = [row.copy() for row in history]
    batch.produce_source_ticket_universe(history, len(history))
    assert history == before


def test_malformed_historical_draw_is_rejected() -> None:
    history = list(_HISTORY)
    history[10] = (1, 2, 3, 4, 5, 5)
    with pytest.raises(ValueError, match="duplicate number"):
        batch.calculate_window_rankings(history, len(history), 50)


# --- Exact centered binary series and autocorrelation ---


def test_binary_appearance_series_count_mean_and_exact_centering() -> None:
    series = batch.binary_appearance_series(_SPECTRAL_WINDOW_HISTORY, 750, 50, 1)
    assert series == tuple(1 if index in _PERIODIC_POSITIONS else 0 for index in range(50))
    assert sum(series) == 5

    centered = batch.mean_centered_binary_series(series)
    assert all(isinstance(value, Fraction) for value in centered)
    assert centered[0] == Fraction(9, 10)
    assert centered[1] == Fraction(-1, 10)
    assert sum(centered, Fraction(0, 1)) == 0


def test_circular_autocorrelation_is_exact_and_symmetric() -> None:
    centered = (Fraction(1, 1), Fraction(0, 1), Fraction(-1, 1), Fraction(0, 1))
    result = batch.circular_autocorrelation(centered)
    assert result == (Fraction(2, 1), Fraction(0, 1), Fraction(-2, 1), Fraction(0, 1))
    assert all(isinstance(value, Fraction) for value in result)
    assert result[0] == sum(value * value for value in centered)
    assert result[1] == result[3]
    assert result[2] == result[2]


def test_circular_autocorrelation_uses_deterministic_modulo_indexing() -> None:
    centered = tuple(Fraction(value, 1) for value in (1, 0, 0, -1, 0))
    expected = tuple(
        sum(
            centered[index] * centered[(index + lag) % len(centered)]
            for index in range(len(centered))
        )
        for lag in range(len(centered))
    )
    assert batch.circular_autocorrelation(centered) == expected


# --- Exact spectral concentration ---


def test_zero_variance_series_has_zero_spectral_ipr_and_peak() -> None:
    centered = batch.mean_centered_binary_series((0, 0, 0, 0))
    autocorrelation = batch.circular_autocorrelation(centered)
    assert autocorrelation == (Fraction(0, 1),) * 4
    assert batch.spectral_ipr_from_circular_autocorrelation(autocorrelation) == 0
    assert batch.peak_normalized_circular_autocorrelation(autocorrelation) == 0


def test_spectral_ipr_exact_parseval_autocorrelation_formula() -> None:
    autocorrelation = (Fraction(2, 1), Fraction(0, 1), Fraction(-2, 1), Fraction(0, 1))
    numerator = sum(value * value for value in autocorrelation)
    denominator = len(autocorrelation) * autocorrelation[0] ** 2
    assert numerator == 8
    assert denominator == 16
    assert batch.spectral_ipr_from_circular_autocorrelation(autocorrelation) == Fraction(1, 2)
    assert batch.spectral_ipr_from_circular_autocorrelation(autocorrelation) >= 0


def test_window_calculation_uses_exact_autocorrelation_identity() -> None:
    ranking = batch.rank_numbers_by_window(_SPECTRAL_WINDOW_HISTORY, 750, 50)
    for number in range(1, 50):
        calculation = ranking.calculation_for(number)
        direct = batch.circular_autocorrelation(calculation.CENTERED_SERIES)
        assert direct == calculation.CIRCULAR_AUTOCORRELATIONS
        assert direct[0] == calculation.R0
        assert batch.spectral_ipr_from_circular_autocorrelation(direct) == calculation.SPECTRAL_IPR
        assert calculation.R0 >= 0


def test_equal_count_temporal_spacing_changes_spectral_ipr() -> None:
    periodic = batch.mean_centered_binary_series(
        tuple(1 if index in (0, 3, 6, 9) else 0 for index in range(12))
    )
    irregular = batch.mean_centered_binary_series((1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0))
    periodic_ipr = batch.spectral_ipr_from_circular_autocorrelation(
        batch.circular_autocorrelation(periodic)
    )
    irregular_ipr = batch.spectral_ipr_from_circular_autocorrelation(
        batch.circular_autocorrelation(irregular)
    )
    assert sum(value > 0 for value in periodic) == sum(value > 0 for value in irregular)
    assert periodic_ipr != irregular_ipr


def test_regular_periodic_pattern_has_different_concentration_than_irregular_pattern() -> None:
    periodic = (1, 0, 0) * 4
    irregular = (1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0)
    periodic_ipr = batch.spectral_ipr_from_circular_autocorrelation(
        batch.circular_autocorrelation(batch.mean_centered_binary_series(periodic))
    )
    irregular_ipr = batch.spectral_ipr_from_circular_autocorrelation(
        batch.circular_autocorrelation(batch.mean_centered_binary_series(irregular))
    )
    assert periodic_ipr > irregular_ipr


def test_circular_phase_shift_preserves_ipr_and_peak_exactly() -> None:
    centered = batch.mean_centered_binary_series((1, 0, 1, 0, 0, 1, 0, 0))
    shift = 3
    shifted = centered[-shift:] + centered[:-shift]
    original_autocorrelation = batch.circular_autocorrelation(centered)
    shifted_autocorrelation = batch.circular_autocorrelation(shifted)
    assert original_autocorrelation == shifted_autocorrelation
    assert batch.spectral_ipr_from_circular_autocorrelation(original_autocorrelation) == (
        batch.spectral_ipr_from_circular_autocorrelation(shifted_autocorrelation)
    )
    assert batch.peak_normalized_circular_autocorrelation(original_autocorrelation) == (
        batch.peak_normalized_circular_autocorrelation(shifted_autocorrelation)
    )


def test_spectral_ranking_differs_from_raw_and_multiscale_frequency_ranking() -> None:
    spectral = batch.calculate_fused_number_ranking(_SPECTRAL_WINDOW_HISTORY, 750)
    raw_counts = {number: 0 for number in range(1, 50)}
    for draw in _SPECTRAL_WINDOW_HISTORY[-50:]:
        for number in draw:
            raw_counts[number] += 1
    raw_frequency = tuple(
        sorted(range(1, 50), key=lambda number: (-raw_counts[number], number))
    )
    multiscale_frequency = frequency_batch.calculate_fused_number_ranking(
        _SPECTRAL_WINDOW_HISTORY, 750
    ).ORDERED_NUMBERS
    window_ranking = spectral.WINDOW_RANKINGS[0]
    assert window_ranking.occurrence_count(1) == 5
    assert window_ranking.occurrence_count(2) == 5
    assert window_ranking.spectral_ipr(1) != window_ranking.spectral_ipr(2)
    assert raw_frequency != spectral.ORDERED_NUMBERS
    assert multiscale_frequency != spectral.ORDERED_NUMBERS


# --- Existing Fourier neighbor specificity ---


def test_spectral_source_is_structurally_distinct_from_power_fourier_rhythm() -> None:
    source = inspect.getsource(batch)
    assert batch.SOURCE_UNIVERSE_ID != "B649_POWER_FOURIER_RHYTHM_RANKED_POOL_V1"
    assert batch.FEATURE_WINDOWS == (50, 300, 750)
    assert 500 not in batch.FEATURE_WINDOWS
    assert "numpy.fft" not in source
    assert "scipy.fft" not in source
    assert "bluestein_dft" not in source
    assert "last_hit_gap" not in source
    assert "dominant_frequency" not in source
    assert "def _select_low_overlap" not in source
    assert batch.AUTHORITATIVE_COMPUTATION.startswith("EXACT_CIRCULAR_AUTOCORRELATION")


def test_circular_shift_can_change_neighbor_phase_sensitive_value_but_not_spectral_score() -> None:
    first = _power_rows(frozenset({700, 710, 720, 730, 740}))
    shifted = _power_rows(frozenset({705, 715, 725, 735, 745}))
    first_component = power_fourier._fourier_rhythm_component(first, 17)
    shifted_component = power_fourier._fourier_rhythm_component(shifted, 17)
    assert first_component.last_hit_gap != shifted_component.last_hit_gap

    first_series = tuple(1 if index in (0, 10, 20, 30, 40) else 0 for index in range(50))
    shifted_series = tuple(1 if index in (5, 15, 25, 35, 45) else 0 for index in range(50))
    first_centered = batch.mean_centered_binary_series(first_series)
    shifted_centered = batch.mean_centered_binary_series(shifted_series)
    first_ac = batch.circular_autocorrelation(first_centered)
    shifted_ac = batch.circular_autocorrelation(shifted_centered)
    assert batch.spectral_ipr_from_circular_autocorrelation(first_ac) == (
        batch.spectral_ipr_from_circular_autocorrelation(shifted_ac)
    )


# --- Ranking and fusion ---


def test_per_window_ranking_uses_ipr_then_peak_then_number() -> None:
    ranking = batch.rank_numbers_by_window(_SPECTRAL_WINDOW_HISTORY, 750, 50)
    assert ranking.spectral_ipr(1) > ranking.spectral_ipr(2)
    assert ranking.position(1) < ranking.position(2)

    zero_ranking = batch.rank_numbers_by_window(_ZERO_INFORMATION_HISTORY, 750, 50)
    assert zero_ranking.spectral_ipr(1) == zero_ranking.spectral_ipr(2) == 0
    assert zero_ranking.peak_normalized_circular_autocorr(1) == (
        zero_ranking.peak_normalized_circular_autocorr(2)
    )
    assert zero_ranking.position(1) < zero_ranking.position(2)
    assert zero_ranking.normalized_rank(zero_ranking.ORDERED_NUMBERS[0]) == Fraction(1, 1)
    assert zero_ranking.normalized_rank(zero_ranking.ORDERED_NUMBERS[-1]) == Fraction(0, 1)


def test_three_window_fusion_uses_exact_equal_rank_and_robustness_order() -> None:
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


# --- Source-ticket universe ---


def test_source_universe_has_exact_top10_and_210_lexicographic_tickets() -> None:
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


# --- Candidate identity, novelty, and isolation ---


def test_candidate_authority_is_exact_three_by_three() -> None:
    assert len(batch.CANDIDATE_AUTHORITIES) == 9
    assert len(set(batch.CANDIDATE_IDS)) == 9
    assert len(set(batch.CANDIDATE_SIGNATURE_HASHES.values())) == 9
    assert all(candidate_id.startswith("BMSGV1_SP_") for candidate_id in batch.CANDIDATE_IDS)
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


def test_candidate_semantics_are_complete_and_hashes_are_canonical() -> None:
    required_keys = {
        "AUTHORITATIVE_COMPUTATION",
        "BINARY_APPEARANCE_RULE",
        "CENTERING_RULE",
        "CIRCULAR_AUTOCORRELATION_RULE",
        "FLOATING_FFT_USED_FOR_RANKING",
        "HYPOTHESIS_VERSION",
        "SOURCE_UNIVERSE_ID",
        "SOURCE_UNIVERSE_VERSION",
        "METHOD_FAMILY",
        "WINDOWS",
        "FEATURE_WINDOWS",
        "SOURCE_WINDOWS",
        "MEAN_CENTERING_RULE",
        "SPECTRAL_IPR_RULE",
        "PEAK_NORMALIZED_CIRCULAR_AUTOCORR_RULE",
        "PER_WINDOW_RANKING_RULE",
        "WINDOW_NORMALIZATION_RULE",
        "WINDOW_FUSION_RULE",
        "ROBUSTNESS_RULE",
        "TOP_NUMBER_COUNT",
        "SOURCE_NUMBER_POOL_COUNT",
        "SOURCE_CANDIDATE_TICKET_COUNT",
        "SOURCE_TICKET_ORDER",
        "CONSTRUCTOR_ID",
        "CONSTRUCTOR_VERSION",
        "TICKET_COUNT",
        "NATIVE_TICKET_COUNT",
        "OUTPUT_SHAPE",
        "MINIMUM_HISTORY",
        "CAUSAL_CUTOFF_RULE",
        "PARAMETER_SELECTION_RULE",
        "DETERMINISM_CLASS",
        "RNG_SEMANTICS",
        "EXPECTED_IMPROVEMENT_CHANNEL",
    }
    for metadata in batch.CANDIDATE_AUTHORITIES:
        semantics = metadata.SEMANTICS
        assert required_keys <= semantics.keys()
        assert semantics["METHOD_FAMILY"] == "SIGNAL_FOURIER"
        assert semantics["WINDOWS"] == (50, 300, 750)
        assert semantics["MINIMUM_HISTORY"] == 750
        assert semantics["FLOATING_FFT_USED_FOR_RANKING"] == "NO"
        assert semantics["RNG_SEED"] is None
        identity = batch.derive_candidate_identity(semantics)
        assert identity.CANDIDATE_ID == metadata.CANDIDATE_ID
        assert identity.SIGNATURE_HASH == metadata.SIGNATURE_HASH


def test_no_collision_with_all_ten_predecessor_lane1_batches() -> None:
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
    assert all(candidate_id.startswith("BMSGV1_SP_") for candidate_id in batch.CANDIDATE_IDS)


def test_no_production_catalog_copy_or_external_io() -> None:
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


# --- Portfolio constructors and prefix contracts ---


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


def test_constructor_functions_match_frozen_constructor_module() -> None:
    universe = batch.produce_source_ticket_universe(_HISTORY, 750)
    low = constructors.construct_b649_candidate_set_low_overlap_v1(universe, 5)
    exposure = constructors.construct_b649_candidate_set_exposure_balanced_v1(universe, 10)
    hybrid = constructors.construct_b649_candidate_set_hybrid_diversity_v1(universe, 20)
    assert batch.produce_b649_multiscale_spectral_concentration_multiticket_low_overlap_v1_k5(
        _HISTORY, 750
    ) == low
    assert (
        batch.produce_b649_multiscale_spectral_concentration_multiticket_exposure_balanced_v1_k10(
            _HISTORY, 750
        )
        == exposure
    )
    assert batch.produce_b649_multiscale_spectral_concentration_multiticket_hybrid_diversity_v1_k20(
        _HISTORY, 750
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
    assert LotteryType.BIG_LOTTO.value == "BIG_LOTTO"
    assert batch.LOTTERY_TYPE == "BIG_LOTTO"
    assert batch.NUMBER_DOMAIN == (1, 49)
    assert batch.PICK_COUNT == 6
    assert batch.FEATURE_WINDOWS == (50, 300, 750)
    assert batch.SOURCE_CANDIDATE_TICKET_COUNT == 210
    assert batch.TICKET_COUNTS == (5, 10, 20)
    assert batch.FLOATING_FFT_USED_FOR_RANKING == "NO"
