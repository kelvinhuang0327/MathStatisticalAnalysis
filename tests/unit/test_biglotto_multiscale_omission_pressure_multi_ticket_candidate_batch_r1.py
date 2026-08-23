"""Focused tests for the causal BigLotto multiscale omission-pressure candidate batch."""

from __future__ import annotations

import inspect
from collections.abc import Callable, Iterable
from fractions import Fraction
from itertools import combinations
from types import MappingProxyType
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
    biglotto_multiscale_markov_transition_multi_ticket_candidate_batch_r1 as markov_batch,
)
from lottolab.research import (
    biglotto_multiscale_omission_pressure_multi_ticket_candidate_batch_r1 as batch,
)
from lottolab.research import (
    biglotto_renyi2_regime_switched_multi_ticket_candidate_batch_r1 as renyi2_batch,
)

Ticket = tuple[int, int, int, int, int, int]


def _repeat(draw: Ticket, count: int) -> tuple[Ticket, ...]:
    return tuple(draw for _ in range(count))


def _make_distinct_draw(index: int) -> Ticket:
    start = (index * 6) % 43 + 1
    return (start, start + 1, start + 2, start + 3, start + 4, start + 5)


_FILLER: Ticket = (30, 31, 32, 33, 34, 35)
_ANCHOR: Ticket = (1, 2, 3, 4, 5, 6)
_HISTORY: tuple[Ticket, ...] = (*tuple(_make_distinct_draw(i) for i in range(749)), _ANCHOR)
_ZERO_INFORMATION_HISTORY: tuple[Ticket, ...] = (*_repeat(_FILLER, 749), _ANCHOR)


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


# --- History / causality tests ---


def test_fewer_than_750_prior_draws_are_rejected() -> None:
    with pytest.raises(batch.InsufficientHistoryError, match="insufficient history"):
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
    with pytest.raises(ValueError, match="six unique"):
        batch.calculate_window_rankings(history, len(history))


# --- Window semantics tests ---


@pytest.mark.parametrize("window", batch.OMISSION_WINDOWS)
def test_each_window_uses_exactly_w_draws(window: int) -> None:
    ranking = batch.rank_numbers_by_window(_HISTORY, 750, window)
    assert window == ranking.WINDOW
    assert window == ranking.WINDOW_DRAW_COUNT
    assert window == ranking.DRAW_COUNT


def test_window_ranking_rejects_unsupported_window() -> None:
    with pytest.raises(ValueError, match="window must be one of"):
        batch.rank_numbers_by_window(_HISTORY, 750, 100)


# --- Occurrence and gap tests ---


def test_occurrence_and_gap_exactness() -> None:
    # Build a specific 50-draw window
    # Draw 49 (latest, index 49): (1, 2, 3, 4, 5, 6) -> gap = 0
    # Draw 48 (index 48): (7, 8, 9, 10, 11, 12) -> gap = 1 for 7..12
    # Draw 40 (index 40): (13, 14, 15, 16, 17, 18) -> gap = 9 for 13..18
    # Numbers 40..49 never appear in W50 -> gap = 50, occurrence = 0
    history = [
        *_repeat(_FILLER, 700),
        *_repeat((20, 21, 22, 23, 24, 25), 40),
        (13, 14, 15, 16, 17, 18),
        *_repeat((20, 21, 22, 23, 24, 25), 7),
        (7, 8, 9, 10, 11, 12),
        (1, 2, 3, 4, 5, 6),
    ]
    assert len(history) == 750
    ranking = batch.rank_numbers_by_window(history, 750, 50)

    # Number 1: appears in latest draw
    assert ranking.current_gap(1) == 0
    assert ranking.occurrence_count(1) == 1

    # Number 7: appears in 1 draw before latest
    assert ranking.current_gap(7) == 1
    assert ranking.occurrence_count(7) == 1

    # Number 13: appears 9 draws before latest (index 40 in 50-draw window)
    assert ranking.current_gap(13) == 9
    assert ranking.occurrence_count(13) == 1

    # Number 49: absent from window
    assert ranking.current_gap(49) == 50
    assert ranking.occurrence_count(49) == 0


# --- Exact pressure formula tests ---


def test_exact_omission_pressure_formula_and_zero_cases() -> None:
    # W = 50
    # gap = 0 => pressure = 0
    # occ = 0 => gap = 50, cycle = (50+1)/(0+1) = 51, pressure = 50 / 51
    # gap = 10, occ = 2 => cycle = 51 / 3 = 17, pressure = 10 / 17 = Fraction(30, 51)
    occurrences = [1, 1, 1, 2, 0] + [0] * 44
    current_gaps = [0, 1, 9, 10, 50] + [50] * 44

    cycles = batch.calculate_recurrence_cycles(occurrences, 50)
    assert cycles[0] == Fraction(51, 2)
    assert cycles[3] == Fraction(51, 3)
    assert cycles[4] == Fraction(51, 1)

    pressures = batch.calculate_omission_pressures(current_gaps, occurrences, 50)
    assert pressures[0] == Fraction(0, 1)
    assert pressures[1] == Fraction(1 * 2, 51)
    assert pressures[2] == Fraction(9 * 2, 51)
    assert pressures[3] == Fraction(10 * 3, 51)
    assert pressures[4] == Fraction(50 * 1, 51)

    assert all(isinstance(p, Fraction) for p in pressures)
    assert all(isinstance(c, Fraction) for c in cycles)


# --- Omission specificity gate tests ---


def test_omission_specificity_case_a_same_count_different_gap() -> None:
    # Two numbers with same occurrence count but different trailing gaps rank differently
    # Let number 10 and 11 have occ=5 in W50. Number 10 has gap=0, number 11 has gap=10.
    # Pressure(10) = 0 * 6 / 51 = 0
    # Pressure(11) = 10 * 6 / 51 = 60/51
    # Total history must be at least 750 draws.
    # 735 filler + 4 + 1 + 9 + 1 = 750
    history = [
        *_repeat(_FILLER, 735),
        *_repeat((10, 11, 20, 21, 22, 23), 4),
        (11, 24, 25, 26, 27, 28),
        *_repeat((20, 21, 22, 23, 24, 25), 9),
        (10, 20, 21, 22, 23, 24),
    ]
    assert len(history) == 750
    ranking = batch.rank_numbers_by_window(history, 750, 50)
    assert ranking.occurrence_count(10) == ranking.occurrence_count(11) == 5
    assert ranking.current_gap(10) == 0
    assert ranking.current_gap(11) == 10
    assert ranking.omission_pressure(10) != ranking.omission_pressure(11)
    assert ranking.omission_pressure(11) > ranking.omission_pressure(10)
    assert ranking.position(11) < ranking.position(10)


def test_omission_specificity_case_b_same_gap_different_count() -> None:
    # Two numbers with same trailing gap but different occurrence counts rank differently
    # Let number 10 have occ=2, gap=5. Pressure = 5 * 3 / 51 = 15/51.
    # Let number 11 have occ=7, gap=5. Pressure = 5 * 8 / 51 = 40/51.
    # 737 filler + 6 + 1 + 1 + 5 = 750
    history = [
        *_repeat(_FILLER, 737),
        *_repeat((11, 20, 21, 22, 23, 24), 6),
        (10, 20, 21, 22, 23, 24),
        (10, 11, 20, 21, 22, 23),
        *_repeat((20, 21, 22, 23, 24, 25), 5),
    ]
    assert len(history) == 750
    ranking = batch.rank_numbers_by_window(history, 750, 50)
    assert ranking.current_gap(10) == ranking.current_gap(11) == 5
    assert ranking.occurrence_count(10) == 2
    assert ranking.occurrence_count(11) == 7
    assert ranking.omission_pressure(10) != ranking.omission_pressure(11)
    assert ranking.omission_pressure(11) > ranking.omission_pressure(10)
    assert ranking.position(11) < ranking.position(10)


def test_omission_specificity_case_c_differs_from_raw_frequency() -> None:
    # Number A: High frequency (20 occurrences), but gap = 0 (just drawn). Pressure = 0.
    # Number B: Low frequency (5 occurrences), but gap = 15. Pressure = 15 * 6 / 51 = 90/51.
    # 711 filler + 19 + 5 + 14 + 1 = 750
    history = [
        *_repeat(_FILLER, 711),
        *_repeat((1, 20, 21, 22, 23, 24), 19),
        *_repeat((2, 20, 21, 22, 23, 24), 5),
        *_repeat((20, 21, 22, 23, 24, 25), 14),
        (1, 20, 21, 22, 23, 24),
    ]
    assert len(history) == 750
    raw_freq_order = batch.raw_frequency_order_for_window(history, 750, 50)
    pressure_order = batch.rank_numbers_by_window(history, 750, 50).ORDERED_NUMBERS
    assert raw_freq_order != pressure_order
    assert raw_freq_order.index(1) < raw_freq_order.index(2)
    assert pressure_order.index(2) < pressure_order.index(1)


def test_omission_specificity_case_d_differs_from_raw_gap() -> None:
    # Number A: Gap = 10, Occ = 1. Pressure = 10 * 2 / 51 = 20/51.
    # Number B: Gap = 8, Occ = 15. Pressure = 8 * 16 / 51 = 128/51.
    # Raw gap has Gap(A)=10 > Gap(B)=8 => A ranks before B in raw gap.
    # Pressure has Pressure(B)=128/51 > Pressure(A)=20/51 => B ranks before A in pressure.
    # 726 filler + 14 + 1 + 1 + 8 = 750
    history = [
        *_repeat(_FILLER, 726),
        *_repeat((2, 20, 21, 22, 23, 24), 14),
        (1, 20, 21, 22, 23, 24),
        (2, 20, 21, 22, 23, 24),
        *_repeat((20, 21, 22, 23, 24, 25), 8),
    ]
    assert len(history) == 750
    raw_gap_order = batch.raw_gap_order_for_window(history, 750, 50)
    pressure_order = batch.rank_numbers_by_window(history, 750, 50).ORDERED_NUMBERS
    assert raw_gap_order != pressure_order
    assert raw_gap_order.index(1) < raw_gap_order.index(2)
    assert pressure_order.index(2) < pressure_order.index(1)


def test_novelty_neighbor_semantic_non_equivalence() -> None:
    source = inspect.getsource(batch)
    assert batch.METHOD_FAMILY == "GAP_OMISSION"
    assert batch.SOURCE_UNIVERSE_ID == "B649_MULTISCALE_OMISSION_PRESSURE_RANKED_POOL_V1"
    assert "Orthogonal" not in source
    assert "Radical" not in source
    assert "ColdPool" not in source


# --- Per-window ranking and fusion tests ---


def test_per_window_tie_breaks_and_normalization() -> None:
    # Zero information history: all numbers have occ=0 (for numbers not in filler/anchor)
    ranking = batch.rank_numbers_by_window(_ZERO_INFORMATION_HISTORY, 750, 50)
    # Check that positions are 1..49 and normalized ranks are (49 - pos) / 48
    assert ranking.position(ranking.ORDERED_NUMBERS[0]) == 1
    assert ranking.normalized_rank(ranking.ORDERED_NUMBERS[0]) == Fraction(1, 1)
    assert ranking.position(ranking.ORDERED_NUMBERS[-1]) == 49
    assert ranking.normalized_rank(ranking.ORDERED_NUMBERS[-1]) == Fraction(0, 1)


def test_three_window_fusion_exact_rational_mean_and_robustness() -> None:
    # Create manual window rankings to test fusion tie-breaks
    def _manual_ranking(window: int, normalized: tuple[Fraction, ...]) -> batch.WindowRanking:
        return batch.WindowRanking(
            WINDOW=window,
            WINDOW_DRAW_COUNT=window,
            OCCURRENCE_COUNTS=(0,) * 49,
            CURRENT_GAPS=(window,) * 49,
            RECURRENCE_CYCLES=(Fraction(window + 1, 1),) * 49,
            OMISSION_PRESSURES=(Fraction(0, 1),) * 49,
            ORDERED_NUMBERS=tuple(range(1, 50)),
            POSITIONS=tuple(range(1, 50)),
            NORMALIZED_RANKS=normalized,
        )

    # Number 1: 1, 0, 0 -> mean = 1/3, sorted = (0, 0, 1)
    # Number 2: 2/3, 1/3, 0 -> mean = 1/3, sorted = (0, 1/3, 2/3)
    # Number 3: 1/2, 1/3, 1/6 -> mean = 1/3, sorted = (1/6, 1/3, 1/2)
    # Means are equal. Robustness min: Number 3 (1/6) > Number 2 (0) == Number 1 (0).
    # Robustness median: Number 2 (1/3) > Number 1 (0).
    # So order must be 3, 2, 1!
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


# --- Source universe tests ---


def test_source_universe_top10_and_210_ordered_tickets() -> None:
    fused = batch.calculate_fused_number_ranking(_ZERO_INFORMATION_HISTORY, 750)
    source = batch.produce_source_ticket_universe(_ZERO_INFORMATION_HISTORY, 750)
    expected = tuple(
        tuple(sorted(fused.TOP_NUMBERS[pos] for pos in combo))
        for combo in combinations(range(10), 6)
    )
    assert len(fused.TOP_NUMBERS) == 10
    assert len(source) == 210
    assert source == expected
    assert len(set(source)) == 210
    assert all(_legal_ticket(ticket) for ticket in source)
    assert source == batch.produce_source_ticket_universe(_ZERO_INFORMATION_HISTORY, 750)


# --- Candidate identities tests ---


def test_candidate_authority_is_exact_three_by_three() -> None:
    assert len(batch.CANDIDATE_AUTHORITIES) == 9
    assert len(set(batch.CANDIDATE_IDS)) == 9
    assert len(set(batch.CANDIDATE_SIGNATURE_HASHES)) == 9
    assert all(cid.startswith("BMSGV1_OM_") for cid in batch.CANDIDATE_IDS)
    assert {
        (meta.CONSTRUCTOR_ID, meta.TICKET_COUNT) for meta in batch.CANDIDATE_AUTHORITIES
    } == {
        (cid, tc) for cid in batch.CONSTRUCTOR_IDS for tc in batch.TICKET_COUNTS
    }
    assert sum(meta.TICKET_COUNT == 5 for meta in batch.CANDIDATE_AUTHORITIES) == 3
    assert sum(meta.TICKET_COUNT == 10 for meta in batch.CANDIDATE_AUTHORITIES) == 3
    assert sum(meta.TICKET_COUNT == 20 for meta in batch.CANDIDATE_AUTHORITIES) == 3


def test_candidate_semantics_contract_keys() -> None:
    required_keys = {
        "HYPOTHESIS_VERSION",
        "SOURCE_UNIVERSE_ID",
        "SOURCE_UNIVERSE_VERSION",
        "METHOD_FAMILY",
        "WINDOWS",
        "OCCURRENCE_COUNT_RULE",
        "CURRENT_GAP_RULE",
        "RECURRENCE_CYCLE_RULE",
        "BOUNDARY_CORRECTION_RULE",
        "OMISSION_PRESSURE_RULE",
        "PER_WINDOW_RANKING_RULE",
        "WINDOW_NORMALIZATION_RULE",
        "WINDOW_FUSION_RULE",
        "ROBUSTNESS_RULE",
        "TOP_NUMBER_COUNT",
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
    for meta in batch.CANDIDATE_AUTHORITIES:
        semantics = meta.SEMANTICS
        assert required_keys <= semantics.keys()
        assert semantics["METHOD_FAMILY"] == "GAP_OMISSION"
        assert semantics["WINDOWS"] == (50, 300, 750)
        assert semantics["MINIMUM_HISTORY"] == 750
        assert semantics["RNG_SEED"] is None
        identity = batch.derive_candidate_identity(semantics)
        assert identity.CANDIDATE_ID == meta.CANDIDATE_ID
        assert identity.SIGNATURE_HASH == meta.SIGNATURE_HASH


def test_no_collision_with_predecessors() -> None:
    previous_batches = (
        frequency_batch,
        conditional_batch,
        renyi2_batch,
        graph_batch,
        ensemble_batch,
        markov_batch,
    )
    previous_ids = {
        cid for prev in previous_batches for cid in prev.CANDIDATE_IDS
    }
    previous_signatures = {
        sig for prev in previous_batches for sig in prev.CANDIDATE_SIGNATURE_HASHES
    }
    assert previous_ids.isdisjoint(batch.CANDIDATE_IDS)
    assert previous_signatures.isdisjoint(batch.CANDIDATE_SIGNATURE_HASHES)


# --- Portfolio tests ---


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
def test_budget_outputs_are_exact_prefixes_by_constructor(
    constructor_id: str,
) -> None:
    outputs = {
        tc: batch.produce_candidate_portfolio(
            batch.candidate_id_for(constructor_id, tc),
            _ZERO_INFORMATION_HISTORY,
            750,
        )
        for tc in batch.TICKET_COUNTS
    }
    assert outputs[10][:5] == outputs[5]
    assert outputs[20][:10] == outputs[10]


def test_frozen_constructor_module_is_invoked_directly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tuple(tuple(sorted(numbers)) for numbers in combinations(range(1, 11), 6))
    calls: list[tuple[tuple[object, ...], int]] = []

    def fake_constructor(
        candidate_tickets: Iterable[object], ticket_count: int
    ) -> batch.TicketPortfolio:
        candidate_tuple = tuple(candidate_tickets)
        calls.append((candidate_tuple, ticket_count))
        return cast(batch.TicketPortfolio, candidate_tuple[:ticket_count])

    monkeypatch.setattr(
        constructors,
        "CONSTRUCTORS",
        MappingProxyType({batch.CONSTRUCTOR_IDS[0]: fake_constructor}),
    )

    def fake_source(
        _history: batch.HistoryInput, _target_index: int
    ) -> batch.TicketPortfolio:
        return cast(batch.TicketPortfolio, source)

    monkeypatch.setattr(batch, "produce_source_ticket_universe", fake_source)
    result = batch.produce_candidate_portfolio(
        batch.candidate_id_for(batch.CONSTRUCTOR_IDS[0], 5), _HISTORY, 750
    )
    assert result == source[:5]
    assert calls == [(source, 5)]


def test_no_constructor_copy_catalog_registration_io_or_rng() -> None:
    source = inspect.getsource(batch)
    assert "_constructors.CONSTRUCTORS" in source
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
            item
            for item in batch.CANDIDATE_AUTHORITIES
            if symbol == item.IMPLEMENTATION_SYMBOL
        )
        assert len(producer(_ZERO_INFORMATION_HISTORY, 750)) == metadata.TICKET_COUNT
