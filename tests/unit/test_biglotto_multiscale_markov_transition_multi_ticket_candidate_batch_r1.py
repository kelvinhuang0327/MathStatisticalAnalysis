"""Focused tests for the causal BigLotto multiscale transition-Markov batch."""

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
    biglotto_multiscale_markov_transition_multi_ticket_candidate_batch_r1 as batch,
)
from lottolab.research import (
    biglotto_renyi2_regime_switched_multi_ticket_candidate_batch_r1 as renyi2_batch,
)

Ticket = tuple[int, int, int, int, int, int]


def _repeat(draw: Ticket, count: int) -> tuple[Ticket, ...]:
    return tuple(draw for _ in range(count))


def _draw(index: int, offset: int = 0) -> Ticket:
    values = tuple(((index * 11 + offset + position * 7) % 49) + 1 for position in range(6))
    return cast(Ticket, values)


_FILLER: Ticket = (30, 31, 32, 33, 34, 35)
_ANCHOR: Ticket = (1, 2, 3, 4, 5, 6)
_HISTORY: tuple[Ticket, ...] = (*tuple(_draw(index) for index in range(750)), _ANCHOR)
_ZERO_INFORMATION_HISTORY: tuple[Ticket, ...] = (*_repeat(_FILLER, 750), _ANCHOR)


def _transition_fixture() -> tuple[Ticket, ...]:
    return (
        *_repeat(_FILLER, 700),
        *_repeat((1, 7, 9, 10, 11, 12), 20),
        *_repeat((8, 13, 14, 15, 16, 17), 30),
        _ANCHOR,
    )


def _directional_histories() -> tuple[tuple[Ticket, ...], tuple[Ticket, ...]]:
    source_a = (1, 2, 3, 4, 5, 6)
    source_b = (7, 8, 9, 10, 11, 12)
    anchor = (1, 13, 14, 15, 16, 17)
    prefix = _repeat(_FILLER, 748)
    return (
        (*prefix, source_a, source_b, anchor),
        (*prefix, source_b, source_a, anchor),
    )


_ZERO_MATRIX = tuple(tuple(0 for _ in range(49)) for _ in range(49))
_ZERO_PROBABILITIES = tuple(tuple(Fraction(0, 1) for _ in range(49)) for _ in range(49))


def _manual_ranking(
    window: int,
    normalized_ranks: tuple[Fraction, ...],
) -> batch.WindowRanking:
    return batch.WindowRanking(
        WINDOW=window,
        ANCHOR_DRAW=_ANCHOR,
        WINDOW_DRAW_COUNT=window + 1,
        TRANSITION_COUNT=window,
        TRANSITION_COUNTS=_ZERO_MATRIX,
        OUTGOING_COUNTS=(0,) * 49,
        CONDITIONAL_PROBABILITIES=_ZERO_PROBABILITIES,
        SCORES=(Fraction(0, 1),) * 49,
        ORDERED_NUMBERS=tuple(range(1, 50)),
        POSITIONS=tuple(range(1, 50)),
        NORMALIZED_RANKS=normalized_ranks,
    )


def _all_zero_ranking(window: int) -> batch.WindowRanking:
    return _manual_ranking(window, (Fraction(0, 1),) * 49)


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


def test_fewer_than_751_prior_draws_are_rejected() -> None:
    with pytest.raises(batch.InsufficientHistoryError, match="insufficient history"):
        batch.validate_prior_history(_HISTORY[:750], 750)


def test_exactly_751_prior_draws_are_accepted() -> None:
    assert len(batch.produce_source_ticket_universe(_HISTORY, 751)) == 210


def test_target_row_is_excluded_and_future_suffix_is_invariant() -> None:
    target_row: object = (44, 45, 46, 47, 48, 49)
    future_suffix: tuple[object, ...] = (object(), ("unreadable",))
    with_target = (*_HISTORY, target_row, *future_suffix)
    expected = batch.produce_source_ticket_universe(_HISTORY, 751)
    assert batch.produce_source_ticket_universe(with_target, 751) == expected


def test_anchor_is_target_index_minus_one() -> None:
    ranking = batch.rank_numbers_by_window(_HISTORY, 751, 50)
    assert ranking.ANCHOR_DRAW == _ANCHOR


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


@pytest.mark.parametrize("window", batch.TRANSITION_WINDOWS)
def test_each_window_uses_exactly_w_plus_one_draws_and_w_transitions(
    window: int,
) -> None:
    ranking = batch.rank_numbers_by_window(_HISTORY, 751, window)
    assert window + 1 == ranking.WINDOW_DRAW_COUNT
    assert window == ranking.TRANSITION_COUNT
    assert sum(map(sum, ranking.TRANSITION_COUNTS)) == window * 36


def test_each_adjacent_pair_contributes_exactly_36_ordered_increments() -> None:
    draws = ((_ANCHOR), (7, 8, 9, 10, 11, 12), (13, 14, 15, 16, 17, 18))
    counts = batch.build_transition_counts(draws)
    assert sum(map(sum, counts)) == 2 * 36
    assert counts[0][6] == 1
    assert counts[6][12] == 1


def test_transition_direction_is_counted_independently() -> None:
    draws = ((_ANCHOR), (7, 8, 9, 10, 11, 12))
    counts = batch.build_transition_counts(draws)
    assert counts[0][6] == 1
    assert counts[6][0] == 0


def test_self_transition_is_allowed_and_outgoing_counts_are_exact() -> None:
    draw = (1, 2, 3, 4, 5, 6)
    counts = batch.build_transition_counts((draw, draw))
    assert counts[0][0] == 1
    assert batch.calculate_outgoing_counts(counts)[0] == 6
    assert sum(batch.calculate_outgoing_counts(counts)) == 36


def test_exact_conditional_probability_has_no_smoothing() -> None:
    counts = batch.build_transition_counts((_ANCHOR, (7, 8, 9, 10, 11, 12)))
    probabilities = batch.calculate_conditional_transition_probabilities(counts)
    assert probabilities[0][6] == Fraction(1, 6)
    assert probabilities[0][0] == Fraction(0, 1)
    assert probabilities[48][48] == Fraction(0, 1)


def test_transition_window_probabilities_are_exact_and_anchor_weighted() -> None:
    history = (*_repeat(_FILLER, 700), *_repeat((1, 7, 8, 9, 10, 11), 50), _ANCHOR)
    ranking = batch.rank_numbers_by_window(history, 751, 50)
    assert ranking.transition_count(1, 7) == 49
    assert ranking.outgoing_count(1) == 300
    assert ranking.conditional_probability(1, 7) == Fraction(49, 300)
    assert ranking.score(7) == Fraction(49, 1800)
    assert all(isinstance(score, Fraction) for score in ranking.SCORES)


def test_probability_mass_invariant_is_exact_without_global_renormalization() -> None:
    history = (*_repeat(_FILLER, 700), *_repeat((1, 7, 8, 9, 10, 11), 50), _ANCHOR)
    ranking = batch.rank_numbers_by_window(history, 751, 50)
    assert sum(ranking.SCORES, Fraction(0, 1)) == Fraction(1, 6)
    assert batch.GLOBAL_RENORMALIZATION_RULE == "NONE"


def test_zero_outgoing_anchor_numbers_contribute_zero_without_fallback() -> None:
    ranking = batch.rank_numbers_by_window(_ZERO_INFORMATION_HISTORY, 751, 50)
    assert (Fraction(0, 1),) * 49 == ranking.SCORES
    assert tuple(range(1, 50)) == ranking.ORDERED_NUMBERS


def test_transition_signal_differs_from_raw_frequency_order() -> None:
    history = _transition_fixture()
    raw_order = batch.raw_frequency_order_for_window(history, 751, 50)
    markov_order = batch.rank_numbers_by_window(history, 751, 50).ORDERED_NUMBERS
    assert raw_order != markov_order
    assert raw_order.index(8) < raw_order.index(7)
    assert markov_order.index(7) < markov_order.index(8)


def test_reversing_transition_direction_changes_anchor_score_structure() -> None:
    history_ab, history_ba = _directional_histories()
    ranking_ab = batch.rank_numbers_by_window(history_ab, 751, 50)
    ranking_ba = batch.rank_numbers_by_window(history_ba, 751, 50)
    assert ranking_ab.transition_count(1, 7) == 1
    assert ranking_ba.transition_count(1, 7) == 0
    assert ranking_ab.score(7) > ranking_ba.score(7)


def test_per_window_ties_use_ascending_number_and_normalize_exactly() -> None:
    ranking = batch.rank_numbers_by_window(_ZERO_INFORMATION_HISTORY, 751, 50)
    assert tuple(range(1, 50)) == ranking.ORDERED_NUMBERS
    assert ranking.position(1) == 1
    assert ranking.position(49) == 49
    assert ranking.normalized_rank(1) == Fraction(1, 1)
    assert ranking.normalized_rank(49) == Fraction(0, 1)


def test_equal_rank_fusion_uses_exact_mean_and_robustness() -> None:
    ranking_a = [Fraction(0, 1)] * 49
    ranking_b = [Fraction(0, 1)] * 49
    ranking_c = [Fraction(0, 1)] * 49
    ranking_a[0] = Fraction(1, 1)
    ranking_a[1] = Fraction(2, 3)
    ranking_a[2] = Fraction(1, 2)
    ranking_b[0] = Fraction(0, 1)
    ranking_b[1] = Fraction(1, 3)
    ranking_b[2] = Fraction(1, 3)
    ranking_c[0] = Fraction(0, 1)
    ranking_c[1] = Fraction(0, 1)
    ranking_c[2] = Fraction(1, 6)
    fused = batch.fuse_window_rankings(
        (
            _manual_ranking(50, tuple(ranking_a)),
            _manual_ranking(300, tuple(ranking_b)),
            _manual_ranking(750, tuple(ranking_c)),
        )
    )
    assert fused.mean_rank(1) == fused.mean_rank(2) == fused.mean_rank(3)
    assert fused.robustness(3) > fused.robustness(2) > fused.robustness(1)
    assert fused.ORDERED_NUMBERS[:3] == (3, 2, 1)


def test_zero_fusion_falls_back_to_ascending_number() -> None:
    fused = batch.fuse_window_rankings(
        (_all_zero_ranking(50), _all_zero_ranking(300), _all_zero_ranking(750))
    )
    assert tuple(range(1, 50)) == fused.ORDERED_NUMBERS


def test_source_universe_is_top10_combination_order_and_repeats_identically() -> None:
    fused = batch.calculate_fused_number_ranking(_ZERO_INFORMATION_HISTORY, 751)
    source = batch.produce_source_ticket_universe(_ZERO_INFORMATION_HISTORY, 751)
    expected = tuple(
        tuple(sorted(fused.TOP_NUMBERS[position] for position in positions))
        for positions in combinations(range(10), 6)
    )
    assert len(fused.TOP_NUMBERS) == 10
    assert len(source) == 210
    assert source == expected
    assert len(set(source)) == 210
    assert all(_legal_ticket(ticket) for ticket in source)
    assert source == batch.produce_source_ticket_universe(_ZERO_INFORMATION_HISTORY, 751)


def test_candidate_authority_is_exact_three_by_three_with_unique_identity() -> None:
    assert len(batch.CANDIDATE_AUTHORITIES) == 9
    assert len(set(batch.CANDIDATE_IDS)) == 9
    assert len(set(batch.CANDIDATE_SIGNATURE_HASHES)) == 9
    assert all(candidate_id.startswith("BMSGV1_MK_") for candidate_id in batch.CANDIDATE_IDS)
    assert {
        (metadata.CONSTRUCTOR_ID, metadata.TICKET_COUNT) for metadata in batch.CANDIDATE_AUTHORITIES
    } == {
        (constructor_id, ticket_count)
        for constructor_id in batch.CONSTRUCTOR_IDS
        for ticket_count in batch.TICKET_COUNTS
    }
    assert sum(metadata.TICKET_COUNT == 5 for metadata in batch.CANDIDATE_AUTHORITIES) == 3
    assert sum(metadata.TICKET_COUNT == 10 for metadata in batch.CANDIDATE_AUTHORITIES) == 3
    assert sum(metadata.TICKET_COUNT == 20 for metadata in batch.CANDIDATE_AUTHORITIES) == 3


def test_candidate_semantics_include_the_frozen_transition_contract() -> None:
    required_keys = {
        "HYPOTHESIS_VERSION",
        "SOURCE_UNIVERSE_ID",
        "SOURCE_UNIVERSE_VERSION",
        "METHOD_FAMILY",
        "TRANSITION_WINDOWS",
        "MINIMUM_HISTORY",
        "ANCHOR_RULE",
        "TRANSITION_WINDOW_RULE",
        "TRANSITION_COUNT_RULE",
        "OUTGOING_COUNT_RULE",
        "SELF_TRANSITION_RULE",
        "ZERO_OUTGOING_RULE",
        "CONDITIONAL_PROBABILITY_RULE",
        "ANCHOR_WEIGHT_RULE",
        "MARKOV_SCORE_RULE",
        "GLOBAL_RENORMALIZATION_RULE",
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
        "CAUSAL_CUTOFF_RULE",
        "PARAMETER_SELECTION_RULE",
        "DETERMINISM_CLASS",
        "RNG_SEMANTICS",
        "EXPECTED_IMPROVEMENT_CHANNEL",
    }
    for metadata in batch.CANDIDATE_AUTHORITIES:
        semantics = metadata.SEMANTICS
        assert required_keys <= semantics.keys()
        assert semantics["METHOD_FAMILY"] == "TRANSITION_MARKOV"
        assert semantics["TRANSITION_WINDOWS"] == (50, 300, 750)
        assert semantics["MINIMUM_HISTORY"] == 751
        assert semantics["RNG_SEED"] is None
        identity = batch.derive_candidate_identity(semantics)
        assert identity.CANDIDATE_ID == metadata.CANDIDATE_ID
        assert identity.SIGNATURE_HASH == metadata.SIGNATURE_HASH


def test_candidate_ids_and_signatures_do_not_collide_with_any_frozen_predecessor() -> None:
    previous_batches = (
        frequency_batch,
        conditional_batch,
        renyi2_batch,
        graph_batch,
        ensemble_batch,
    )
    previous_ids = {
        candidate_id for previous in previous_batches for candidate_id in previous.CANDIDATE_IDS
    }
    previous_signatures = {
        signature
        for previous in previous_batches
        for signature in previous.CANDIDATE_SIGNATURE_HASHES
    }
    assert previous_ids.isdisjoint(batch.CANDIDATE_IDS)
    assert previous_signatures.isdisjoint(batch.CANDIDATE_SIGNATURE_HASHES)


def test_production_markov_neighbor_is_not_an_exact_semantic_duplicate() -> None:
    source = inspect.getsource(batch)
    assert batch.METHOD_FAMILY != "MARKOV"
    assert batch.SOURCE_UNIVERSE_ID != "legacy_biglotto__frontend_markov_strategy__2fc1cafea55c"
    assert "BigLottoFrontendMarkovAdapter" not in source
    assert batch.TRANSITION_WINDOWS == (50, 300, 750)
    assert batch.GLOBAL_RENORMALIZATION_RULE == "NONE"


@pytest.mark.parametrize(
    "metadata", batch.CANDIDATE_AUTHORITIES, ids=lambda item: item.CANDIDATE_ID
)
def test_all_candidate_portfolios_are_legal_distinct_and_deterministic(
    metadata: batch.CandidateMetadata,
) -> None:
    first = batch.produce_candidate_portfolio(metadata.CANDIDATE_ID, _ZERO_INFORMATION_HISTORY, 751)
    second = batch.produce_candidate_portfolio(
        metadata.CANDIDATE_ID, _ZERO_INFORMATION_HISTORY, 751
    )
    assert len(first) == metadata.TICKET_COUNT
    assert len(set(first)) == metadata.TICKET_COUNT
    assert all(_legal_ticket(ticket) for ticket in first)
    assert first == second


@pytest.mark.parametrize("constructor_id", batch.CONSTRUCTOR_IDS)
def test_budget_outputs_are_exact_prefixes_by_constructor(constructor_id: str) -> None:
    outputs = {
        ticket_count: batch.produce_candidate_portfolio(
            batch.candidate_id_for(constructor_id, ticket_count),
            _ZERO_INFORMATION_HISTORY,
            751,
        )
        for ticket_count in batch.TICKET_COUNTS
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

    def fake_source(_history: batch.HistoryInput, _target_index: int) -> batch.TicketPortfolio:
        return cast(batch.TicketPortfolio, source)

    monkeypatch.setattr(batch, "produce_source_ticket_universe", fake_source)
    result = batch.produce_candidate_portfolio(
        batch.candidate_id_for(batch.CONSTRUCTOR_IDS[0], 5), _HISTORY, 751
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
    symbols = {metadata.IMPLEMENTATION_SYMBOL for metadata in batch.CANDIDATE_AUTHORITIES}
    assert len(symbols) == 9
    for symbol in symbols:
        producer = cast(
            Callable[[batch.HistoryInput, int], batch.TicketPortfolio], getattr(batch, symbol)
        )
        metadata = next(
            item for item in batch.CANDIDATE_AUTHORITIES if symbol == item.IMPLEMENTATION_SYMBOL
        )
        assert len(producer(_ZERO_INFORMATION_HISTORY, 751)) == metadata.TICKET_COUNT
