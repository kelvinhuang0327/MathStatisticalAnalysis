"""Focused tests for the causal BigLotto graph/network candidate batch."""

from __future__ import annotations

from collections.abc import Iterable
from fractions import Fraction
from itertools import combinations
from pathlib import Path
from types import MappingProxyType
from typing import cast

import pytest

from lottolab.research import (
    biglotto_conditional_cooccurrence_multi_ticket_candidate_batch_r1 as conditional_batch,
)
from lottolab.research import biglotto_graph_network_multi_ticket_candidate_batch_r1 as batch
from lottolab.research import biglotto_multi_ticket_candidate_batch_r1 as frequency_batch
from lottolab.research import biglotto_multi_ticket_constructors_r1 as constructors
from lottolab.research import (
    biglotto_renyi2_regime_switched_multi_ticket_candidate_batch_r1 as renyi2_batch,
)


def _draw(index: int, offset: int = 0) -> tuple[int, int, int, int, int, int]:
    values: tuple[int, ...] = tuple(
        ((index * 11 + offset + position * 7) % 49) + 1 for position in range(6)
    )
    return cast(tuple[int, int, int, int, int, int], values)


def _history(length: int = 750) -> tuple[tuple[int, int, int, int, int, int], ...]:
    return tuple(_draw(index) for index in range(length))


def _structural_history() -> tuple[tuple[int, int, int, int, int, int], ...]:
    prefix = [_draw(index) for index in range(700)]
    tail = (
        [(1, 2, 3, 4, 5, 6)] * 20
        + [(1, 7, 8, 9, 10, 11)] * 10
        + [(7, 12, 13, 14, 15, 16)] * 10
        + [(17, 18, 19, 20, 21, 22)] * 10
    )
    return tuple(prefix + tail)


_HISTORY = _history()
_STRUCTURAL = _structural_history()
_ZERO_MATRIX = tuple(tuple(0 for _ in range(49)) for _ in range(49))


def _legal_ticket(ticket: object) -> bool:
    if not isinstance(ticket, tuple):
        return False
    values: tuple[object, ...] = cast(tuple[object, ...], ticket)
    if len(values) != 6:
        return False
    if not all(type(number) is int and 1 <= number <= 49 for number in values):
        return False
    numbers = tuple(cast(int, number) for number in values)
    return len(set(numbers)) == 6 and tuple(sorted(numbers)) == numbers


def _synthetic_window_ranking(
    window: int,
    special_normalized_ranks: dict[int, Fraction],
) -> batch.GraphWindow:
    normalized = [Fraction(0, 1)] * 49
    for number, value in special_normalized_ranks.items():
        normalized[number - 1] = value
    # The fusion function uses the normalized vector only; the remaining
    # immutable fields make a valid public GraphWindow fixture.
    return batch.GraphWindow(
        WINDOW=window,
        EDGE_COUNTS=_ZERO_MATRIX,
        NODE_STRENGTHS=(0,) * 49,
        PAGERANKS=(Fraction(1, 49),) * 49,
        ORDERED_NUMBERS=tuple(range(1, 50)),
        POSITIONS=tuple(range(1, 50)),
        NORMALIZED_RANKS=tuple(normalized),
    )


def test_history_minimum_and_exact_cutoff_are_enforced() -> None:
    assert len(batch.validate_prior_history(_HISTORY, 750)) == 750
    with pytest.raises(batch.InsufficientHistoryError):
        batch.validate_prior_history(_HISTORY[:749], 749)
    with pytest.raises(batch.InsufficientHistoryError):
        batch.validate_prior_history(_HISTORY, 749)


def test_target_row_and_future_suffix_are_excluded() -> None:
    target_row = (44, 45, 46, 47, 48, 49)
    history_with_target = (*_HISTORY, target_row)
    history_with_future = (*history_with_target, _draw(999, 3), _draw(1000, 5))
    expected = batch.calculate_fused_number_ranking(_HISTORY, 750)
    assert batch.calculate_fused_number_ranking(history_with_target, 750) == expected
    assert batch.calculate_fused_number_ranking(history_with_future, 750) == expected


def test_caller_history_is_not_mutated() -> None:
    caller_history = [list(draw) for draw in _HISTORY]
    before = [row.copy() for row in caller_history]
    batch.produce_source_ticket_universe(caller_history, 750)
    assert caller_history == before


@pytest.mark.parametrize(
    "bad_draw",
    [
        (1, 2, 3, 4, 5),
        (1, 2, 3, 4, 5, 5),
        (0, 2, 3, 4, 5, 6),
        (1, 2, 3, 4, 5, 50),
        (1, 2, 3, 4, 5, "6"),
    ],
)
def test_malformed_prior_draw_is_rejected(bad_draw: object) -> None:
    history = list(_HISTORY)
    history[10] = bad_draw  # type: ignore[assignment]
    with pytest.raises(ValueError):
        batch.calculate_window_rankings(history, 750)


def test_fixed_graph_domain_and_one_draw_edge_contribution() -> None:
    draw = (1, 2, 3, 4, 5, 6)
    edges = batch.build_cooccurrence_edge_counts((draw,))
    assert len(edges) == 49
    assert all(len(row) == 49 for row in edges)
    assert sum(map(sum, edges)) == 30
    for left, right in combinations(draw, 2):
        assert edges[left - 1][right - 1] == 1
        assert edges[right - 1][left - 1] == 1
    assert all(edges[number][number] == 0 for number in range(49))
    assert all(
        edges[left][right] == edges[right][left]
        for left in range(49)
        for right in range(49)
    )


@pytest.mark.parametrize("window", batch.WINDOWS)
def test_each_window_uses_exact_strictly_prior_slice(window: int) -> None:
    graph = batch.build_graph_for_window(_HISTORY, 750, window)
    expected_edges = batch.build_cooccurrence_edge_counts(_HISTORY[750 - window : 750])
    assert expected_edges == graph.EDGE_COUNTS
    assert sum(map(sum, graph.EDGE_COUNTS)) == 30 * window
    assert window == graph.WINDOW
    assert tuple(sum(row) for row in expected_edges) == graph.NODE_STRENGTHS


def test_page_rank_is_exact_and_uniformly_redistributes_dangling_mass() -> None:
    ranks = batch.calculate_page_rank(_ZERO_MATRIX)
    assert Fraction(17, 20) == batch.PAGERANK_DAMPING
    assert batch.PAGERANK_ITERATIONS == 20
    assert all(type(rank) is Fraction for rank in ranks)
    assert all(rank == Fraction(1, 49) for rank in ranks)
    assert sum(ranks, Fraction(0, 1)) == Fraction(1, 1)


def test_page_rank_accepts_exact_integer_graph_and_preserves_invariants() -> None:
    edges = [list(row) for row in _ZERO_MATRIX]
    edges[0][1] = 1
    edges[1][0] = 1
    ranks = batch.calculate_page_rank(edges, (1, 1) + (0,) * 47)
    assert all(type(rank) is Fraction and rank >= 0 for rank in ranks)
    assert sum(ranks, Fraction(0, 1)) == Fraction(1, 1)
    assert ranks[0] == ranks[1]
    assert ranks[0] > ranks[2]


def test_page_rank_rejects_asymmetric_or_non_integer_graphs() -> None:
    asymmetric = [list(row) for row in _ZERO_MATRIX]
    asymmetric[0][1] = 1
    with pytest.raises(ValueError, match="symmetric"):
        batch.calculate_page_rank(asymmetric)
    non_integer = [list(row) for row in _ZERO_MATRIX]
    non_integer[0][1] = 0.5  # type: ignore[assignment]
    with pytest.raises(ValueError, match="non-negative integer"):
        batch.calculate_page_rank(non_integer)


def test_graph_page_rank_order_differs_from_raw_frequency_order() -> None:
    raw_order = batch.raw_frequency_order_for_window(_STRUCTURAL, 750, 50)
    graph_order = batch.build_graph_for_window(_STRUCTURAL, 750, 50).ORDERED_NUMBERS
    assert graph_order != raw_order
    assert graph_order[:3] == (1, 7, 2)


def test_window_rank_ties_use_ascending_number_and_normalize_exactly() -> None:
    graph = batch.build_graph_for_window(_HISTORY, 750, 50)
    tied_rank = graph.PAGERANKS[0]
    tied_numbers = [
        number for number, rank in enumerate(graph.PAGERANKS, start=1) if rank == tied_rank
    ]
    assert tuple(sorted(tied_numbers)) == tuple(
        number for number in graph.ORDERED_NUMBERS if number in tied_numbers
    )
    assert graph.normalized_rank(graph.ORDERED_NUMBERS[0]) == Fraction(1, 1)
    assert graph.normalized_rank(graph.ORDERED_NUMBERS[-1]) == Fraction(0, 1)
    assert all(type(value) is Fraction for value in graph.NORMALIZED_RANKS)


def test_equal_rank_fusion_and_robustness_are_exact() -> None:
    rankings = (
        _synthetic_window_ranking(50, {1: Fraction(1), 2: Fraction(1, 3)}),
        _synthetic_window_ranking(300, {1: Fraction(0), 2: Fraction(1, 3)}),
        _synthetic_window_ranking(750, {1: Fraction(0), 2: Fraction(1, 3)}),
    )
    fused = batch.fuse_window_rankings(rankings)
    assert fused.mean_rank(1) == Fraction(1, 3)
    assert fused.mean_rank(2) == Fraction(1, 3)
    assert fused.robustness(1) == (Fraction(0), Fraction(0), Fraction(1))
    assert fused.robustness(2) == (Fraction(1, 3),) * 3
    assert fused.ORDERED_NUMBERS[:2] == (2, 1)


def test_robustness_median_and_maximum_are_retained_before_number_fallback() -> None:
    rankings = (
        _synthetic_window_ranking(50, {1: Fraction(1), 2: Fraction(0)}),
        _synthetic_window_ranking(300, {1: Fraction(0), 2: Fraction(1, 3)}),
        _synthetic_window_ranking(750, {1: Fraction(0), 2: Fraction(2, 3)}),
    )
    fused = batch.fuse_window_rankings(rankings)
    assert fused.robustness(1) == (Fraction(0), Fraction(0), Fraction(1))
    assert fused.robustness(2) == (Fraction(0), Fraction(1, 3), Fraction(2, 3))
    assert fused.ORDERED_NUMBERS[0] == 2

    all_zero = tuple(_synthetic_window_ranking(window, {}) for window in batch.WINDOWS)
    assert tuple(range(1, 50)) == batch.fuse_window_rankings(all_zero).ORDERED_NUMBERS


def test_source_universe_is_exactly_rank_position_combination_order() -> None:
    fused = batch.calculate_fused_number_ranking(_HISTORY, 750)
    source = batch.produce_source_ticket_universe(_HISTORY, 750)
    expected = tuple(
        tuple(sorted(fused.TOP_NUMBERS[position] for position in positions))
        for positions in combinations(range(10), 6)
    )
    assert len(fused.TOP_NUMBERS) == 10
    assert len(source) == 210
    assert source == expected
    assert len(set(source)) == 210
    assert all(_legal_ticket(ticket) for ticket in source)


def test_source_universe_repeats_deterministically() -> None:
    first = batch.produce_source_ticket_universe(_HISTORY, 750)
    second = batch.produce_source_ticket_universe(_HISTORY, 750)
    assert first == second


def test_candidate_semantic_records_have_frozen_graph_contract() -> None:
    required_keys = {
        "HYPOTHESIS_VERSION",
        "SOURCE_UNIVERSE_ID",
        "SOURCE_UNIVERSE_VERSION",
        "METHOD_FAMILY",
        "WINDOWS",
        "GRAPH_NODE_DOMAIN",
        "EDGE_DEFINITION",
        "EDGE_WEIGHT_RULE",
        "PAGERANK_DAMPING",
        "PAGERANK_ITERATIONS",
        "PAGERANK_INITIALIZATION",
        "PAGERANK_DANGLING_RULE",
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
    assert len(batch.CANDIDATE_AUTHORITIES) == 9
    assert len(set(batch.CANDIDATE_IDS)) == 9
    assert len(set(batch.CANDIDATE_SIGNATURE_HASHES)) == 9
    assert all(candidate_id.startswith("BMSGV1_GR_") for candidate_id in batch.CANDIDATE_IDS)
    for metadata in batch.CANDIDATE_AUTHORITIES:
        semantics = metadata.SEMANTICS
        assert required_keys <= semantics.keys()
        assert semantics["SOURCE_UNIVERSE_ID"] == batch.SOURCE_UNIVERSE_ID
        assert semantics["METHOD_FAMILY"] == "GRAPH"
        assert semantics["WINDOWS"] == (50, 300, 750)
        assert semantics["SOURCE_WINDOWS"] == (50, 300, 750)
        assert semantics["EDGE_WEIGHT_RULE"] == "UNDECAYED_INTEGER_SAME_DRAW_COOCCURRENCE"
        assert semantics["PAGERANK_DAMPING"] == "17/20"
        assert semantics["PAGERANK_ITERATIONS"] == 20
        assert semantics["PAGERANK_ARITHMETIC"] == "EXACT_RATIONAL"
        assert semantics["RNG_SEED"] is None
        assert semantics["NATIVE_TICKET_COUNT"] == metadata.TICKET_COUNT
        assert semantics["TICKET_COUNT"] == metadata.TICKET_COUNT


def test_canonical_semantic_json_is_sorted_compact_utf8() -> None:
    assert batch.canonicalize_semantic_record({"b": None, "a": (1, 2)}) == b'{"a":[1,2],"b":null}'
    assert batch.canonicalize_semantic_record({"value": Fraction(1, 2)}) == b'{"value":"1/2"}'
    for metadata in batch.CANDIDATE_AUTHORITIES:
        identity = batch.derive_candidate_identity(metadata.SEMANTICS)
        assert identity.CANDIDATE_ID == metadata.CANDIDATE_ID
        assert identity.SIGNATURE_HASH == metadata.SIGNATURE_HASH


def test_candidate_batch_has_no_collision_with_previous_frozen_batches() -> None:
    previous_ids = set(frequency_batch.CANDIDATE_IDS)
    previous_ids.update(conditional_batch.CANDIDATE_IDS)
    previous_ids.update(renyi2_batch.CANDIDATE_IDS)
    previous_signatures = set(frequency_batch.CANDIDATE_SIGNATURE_HASHES)
    previous_signatures.update(conditional_batch.CANDIDATE_SIGNATURE_HASHES)
    previous_signatures.update(renyi2_batch.CANDIDATE_SIGNATURE_HASHES)
    assert previous_ids.isdisjoint(batch.CANDIDATE_IDS)
    assert previous_signatures.isdisjoint(batch.CANDIDATE_SIGNATURE_HASHES)


def test_candidate_matrix_is_exactly_three_constructors_by_three_budgets() -> None:
    actual_pairs = {
        (metadata.CONSTRUCTOR_ID, metadata.TICKET_COUNT)
        for metadata in batch.CANDIDATE_AUTHORITIES
    }
    expected_pairs = {
        (constructor_id, ticket_count)
        for constructor_id in batch.CONSTRUCTOR_IDS
        for ticket_count in (5, 10, 20)
    }
    assert actual_pairs == expected_pairs
    assert sum(metadata.TICKET_COUNT == 5 for metadata in batch.CANDIDATE_AUTHORITIES) == 3
    assert sum(metadata.TICKET_COUNT == 10 for metadata in batch.CANDIDATE_AUTHORITIES) == 3
    assert sum(metadata.TICKET_COUNT == 20 for metadata in batch.CANDIDATE_AUTHORITIES) == 3


@pytest.mark.parametrize(
    "metadata", batch.CANDIDATE_AUTHORITIES, ids=lambda item: item.CANDIDATE_ID
)
def test_all_candidate_portfolios_are_legal_and_deterministic(
    metadata: batch.CandidateMetadata,
) -> None:
    first = batch.produce_candidate_portfolio(metadata.CANDIDATE_ID, _HISTORY, 750)
    second = batch.produce_candidate_portfolio(metadata.CANDIDATE_ID, _HISTORY, 750)
    assert len(first) == metadata.TICKET_COUNT
    assert len(set(first)) == metadata.TICKET_COUNT
    assert all(_legal_ticket(ticket) for ticket in first)
    assert first == second


@pytest.mark.parametrize("constructor_id", batch.CONSTRUCTOR_IDS)
def test_budget_outputs_are_exact_prefixes_by_constructor(constructor_id: str) -> None:
    portfolios = [
        batch.produce_candidate_portfolio(
            batch.candidate_id_for(constructor_id, count), _HISTORY, 750
        )
        for count in (5, 10, 20)
    ]
    assert portfolios[0] == portfolios[1][:5]
    assert portfolios[1] == portfolios[2][:10]


def test_frozen_constructor_module_is_invoked_directly(monkeypatch: pytest.MonkeyPatch) -> None:
    source = tuple(
        tuple(sorted(numbers)) for numbers in combinations(range(1, 11), 6)
    )
    calls: list[tuple[tuple[object, ...], int]] = []

    def fake_constructor(
        candidate_tickets: Iterable[object], ticket_count: int
    ) -> batch.TicketPortfolio:
        candidate_tuple = tuple(candidate_tickets)
        calls.append((candidate_tuple, ticket_count))
        return candidate_tuple[:ticket_count]  # type: ignore[return-value]

    constructor_id = batch.CONSTRUCTOR_IDS[0]
    monkeypatch.setattr(
        constructors,
        "CONSTRUCTORS",
        MappingProxyType({constructor_id: fake_constructor}),
    )
    def fake_source(_history: batch.HistoryInput, _target_index: int) -> batch.TicketPortfolio:
        return source  # type: ignore[return-value]

    monkeypatch.setattr(batch, "produce_source_ticket_universe", fake_source)
    result = batch.produce_candidate_portfolio(
        batch.candidate_id_for(constructor_id, 5), _HISTORY, 750
    )
    assert result == source[:5]
    assert calls == [(source, 5)]


def test_source_does_not_copy_constructor_bodies_or_register_production_catalog() -> None:
    source_text = Path(batch.__file__).read_text(encoding="utf-8")
    assert "_constructors.CONSTRUCTORS" in source_text
    assert "def _select_low_overlap" not in source_text
    assert "def _select_exposure_balanced" not in source_text
    assert "def _select_hybrid_diversity" not in source_text
    assert "BigLottoGraphPredictorAdapter" not in source_text
    assert "import os" not in source_text
    assert "import random" not in source_text
    assert "import sqlite" not in source_text
    assert "import requests" not in source_text
    assert "import urllib" not in source_text
    assert "import subprocess" not in source_text
    assert "import time" not in source_text
