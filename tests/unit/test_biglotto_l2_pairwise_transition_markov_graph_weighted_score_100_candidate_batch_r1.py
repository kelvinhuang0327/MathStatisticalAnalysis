"""Focused acceptance tests for the sealed TRANSITION_MARKOV + GRAPH candidate."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator, Sequence
from fractions import Fraction
from itertools import combinations, pairwise
from pathlib import Path
from typing import cast

import pytest

from lottolab.research import (
    biglotto_l2_pairwise_transition_markov_graph_weighted_score_100_candidate_batch_r1,
)

batch = (
    biglotto_l2_pairwise_transition_markov_graph_weighted_score_100_candidate_batch_r1
)

Ticket = tuple[int, int, int, int, int, int]
_DRAW_TYPES: tuple[Ticket, ...] = (
    (1, 2, 3, 4, 5, 6),
    (1, 7, 13, 14, 15, 16),
    (2, 8, 17, 18, 19, 20),
    (30, 31, 32, 33, 34, 35),
    (36, 37, 38, 39, 40, 41),
    (42, 43, 44, 45, 46, 47),
    (44, 45, 46, 47, 48, 49),
)
_FILLER: Ticket = (1, 2, 3, 4, 5, 6)
_ALTERNATE: Ticket = (7, 8, 9, 10, 11, 12)
_AUTHORITY_ROOT = Path(
    "/Users/kelvin/VibeCoding-WorkSpace/.task-data/"
    "ADVANCE_LEVEL2_FRONTIER_AFTER_BMSGV1_L2_PAIRWISE_CCA5660423304B0B_R1"
)


def _history(count: int) -> tuple[Ticket, ...]:
    return tuple(_DRAW_TYPES[index % len(_DRAW_TYPES)] for index in range(count))


def _authority() -> dict[str, object]:
    return cast(
        dict[str, object],
        json.loads(
            (_AUTHORITY_ROOT / "implementation_handoff.json").read_text(
                encoding="utf-8"
            )
        ),
    )


def _reference_transition_window(
    history: Sequence[Ticket], window: int
) -> tuple[tuple[tuple[int, ...], ...], tuple[Fraction, ...]]:
    window_draws = history[-window:]
    counts = [[0] * 49 for _ in range(49)]
    for source_draw, destination_draw in pairwise(window_draws):
        for source_number in source_draw:
            for destination_number in destination_draw:
                counts[source_number - 1][destination_number - 1] += 1
    outgoing = tuple(sum(row) for row in counts)
    probabilities = tuple(
        tuple(
            Fraction(value, outgoing[source_index])
            if outgoing[source_index]
            else Fraction(0, 1)
            for value in row
        )
        for source_index, row in enumerate(counts)
    )
    source_state = tuple(sorted(history[-1]))
    scores = [Fraction(0, 1)] * 49
    for source_number in source_state:
        for candidate_number, probability in enumerate(
            probabilities[source_number - 1], start=1
        ):
            scores[candidate_number - 1] += probability / len(source_state)
    return tuple(tuple(row) for row in counts), tuple(scores)


def _reference_graph_edges(history: Sequence[Ticket], window: int) -> tuple[tuple[int, ...], ...]:
    edges = [[0] * 49 for _ in range(49)]
    for draw in history[-window:]:
        for left, right in combinations(sorted(draw), 2):
            edges[left - 1][right - 1] += 1
            edges[right - 1][left - 1] += 1
    return tuple(tuple(row) for row in edges)


def _reference_page_rank(edges: tuple[tuple[int, ...], ...]) -> tuple[Fraction, ...]:
    strengths = tuple(sum(row) for row in edges)
    damping = Fraction(17, 20)
    teleport = Fraction(1, 49)
    ranks: tuple[Fraction, ...] = (teleport,) * 49
    for _ in range(100):
        dangling = sum(
            (ranks[index] for index, strength in enumerate(strengths) if strength == 0),
            Fraction(0, 1),
        )
        next_ranks: list[Fraction] = []
        for target in range(49):
            incoming = sum(
                (
                    ranks[source] * edges[source][target] / strengths[source]
                    for source in range(49)
                    if strengths[source] > 0
                ),
                Fraction(0, 1),
            )
            next_ranks.append(
                (1 - damping) * teleport
                + damping * (incoming + dangling * teleport)
            )
        ranks = tuple(next_ranks)
    return ranks


def test_authority_checksum_identity_signature_and_paths_are_exact() -> None:
    for line in (_AUTHORITY_ROOT / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
        expected_hash, relative_path = line.split(maxsplit=1)
        assert hashlib.sha256((_AUTHORITY_ROOT / relative_path).read_bytes()).hexdigest() == (
            expected_hash
        )

    authority = _authority()
    assert authority["SELECTED_GAP_ID"] == batch.SELECTED_GAP_ID
    assert authority["CANDIDATE_ID"] == batch.CANDIDATE_ID
    assert authority["DESIGN_ID"] == batch.DESIGN_ID
    assert authority["DESIGN_SIGNATURE_SHA256"] == batch.DESIGN_SIGNATURE_SHA256
    assert authority["IMPLEMENTATION_READY"] == "YES"
    assert authority["EXPECTED_IMPLEMENTATION_MODULE"] == batch.IMPLEMENTATION_MODULE
    assert authority["EXPECTED_IMPLEMENTATION_SYMBOL"] == batch.IMPLEMENTATION_SYMBOL
    assert authority["EXPECTED_FOCUSED_TEST_MODULE"] == (
        "tests/unit/test_biglotto_l2_pairwise_transition_markov_graph_weighted_score_100_candidate_batch_r1.py"
    )

    signature_object = cast(dict[str, object], authority["DESIGN_SIGNATURE_OBJECT"])
    canonical = json.dumps(
        signature_object,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    assert hashlib.sha256(canonical).hexdigest() == batch.DESIGN_SIGNATURE_SHA256
    assert json.loads(batch.canonical_semantic_json(batch.CANDIDATE_SEMANTICS)) == (
        signature_object
    )
    assert batch.signature_hash_for_semantics(batch.CANDIDATE_SEMANTICS) == (
        batch.DESIGN_SIGNATURE_SHA256
    )


def test_candidate_count_and_authority_controlled_fields_are_exactly_one() -> None:
    authority = cast(dict[str, object], _authority()["DESIGN_SIGNATURE_OBJECT"])
    assert len(batch.CANDIDATE_AUTHORITIES) == 1
    assert batch.CANDIDATE_IDS == (batch.CANDIDATE_ID,)
    assert batch.CANDIDATE_ID == "BMSGV1_L2_PAIRWISE_a9bf271fe5419f15"
    assert batch.SELECTED_GAP_ID == batch.CANDIDATE_ID
    assert batch.WINDOW == 100
    assert batch.WINDOWS == (30, 100, 300)
    assert batch.FEATURE_1 == "TRANSITION_MARKOV"
    assert batch.FEATURE_2 == "GRAPH"
    assert batch.FUSION == "WEIGHTED_SCORE"
    assert batch.MINIMUM_HISTORY == 300
    for key in (
        "PARENT_SOURCE_UNIVERSE_ID_1",
        "PARENT_SOURCE_UNIVERSE_ID_2",
        "PARENT_COMPONENT_RULE_1",
        "PARENT_COMPONENT_RULE_2",
        "PARENT_WINDOW_RULE_1",
        "PARENT_WINDOW_RULE_2",
        "MINIMUM_HISTORY",
        "COMPONENT_NORMALIZATION_RULE",
        "COMPONENT_SCORE_DOMAIN_1",
        "COMPONENT_SCORE_DOMAIN_2",
        "FUSION_WEIGHT_1",
        "FUSION_WEIGHT_2",
        "FUSION_FORMULA",
        "NUMBER_RANKING_RULE",
        "NUMBER_TIE_BREAK_RULE",
        "RANKED_POOL_DOMAIN",
        "RANKED_POOL_CARDINALITY",
        "CANDIDATE_CONSTRUCTION_RULE",
        "TICKET_CONSTRUCTION",
        "TICKET_SELECTION_RULE",
        "NATIVE_TICKET_COUNT",
        "CAUSAL_CUTOFF_RULE",
        "FALLBACK_RULE",
        "PARAMETER_SELECTION_RULE",
        "DETERMINISM_CLASS",
        "RNG_SEMANTICS",
    ):
        expected = authority[key]
        actual = batch.SOURCE_UNIVERSE_CONTRACT[key]
        if isinstance(expected, list):
            assert actual == tuple(cast(list[object], expected))
        else:
            assert actual == expected


def test_transition_parent_window_counts_and_scores_match_independent_reference() -> None:
    history = _history(300)
    rankings = batch.calculate_markov_window_rankings(history, 300)
    assert tuple(window.WINDOW for window in rankings) == (30, 100, 300)
    for ranking in rankings:
        expected_counts, expected_scores = _reference_transition_window(
            history, ranking.WINDOW
        )
        assert expected_counts == ranking.TRANSITION_COUNTS
        assert expected_scores == ranking.SCORES
        assert ranking.WINDOW_DRAW_COUNT == ranking.WINDOW
        assert ranking.TRANSITION_COUNT == ranking.WINDOW - 1
        assert sum(map(sum, ranking.TRANSITION_COUNTS)) == (ranking.WINDOW - 1) * 36
        assert all(isinstance(value, Fraction) for value in ranking.SCORES)

    zero_counts = batch.build_transition_counts(tuple(_FILLER for _ in range(30)))
    zero_probabilities = batch.calculate_conditional_transition_probabilities(zero_counts)
    assert zero_probabilities[48] == (Fraction(0, 1),) * 49


def test_graph_parent_edges_pagerank_and_multiscale_fusion_are_exact() -> None:
    history = _history(300)
    rankings = batch.calculate_graph_window_rankings(history, 300)
    assert tuple(window.WINDOW for window in rankings) == (30, 100, 300)
    for ranking in rankings:
        expected_edges = _reference_graph_edges(history, ranking.WINDOW)
        assert expected_edges == ranking.EDGE_COUNTS
        assert _reference_page_rank(expected_edges) == ranking.PAGERANKS
        assert sum(map(sum, ranking.EDGE_COUNTS)) == ranking.WINDOW * 30
        assert sum(ranking.PAGERANKS, Fraction(0, 1)) == Fraction(1, 1)

    fused = batch.calculate_graph_parent_ranking(history, 300)
    for number in range(1, 50):
        expected = sum(
            (ranking.PAGERANKS[number - 1] for ranking in rankings), Fraction(0, 1)
        ) / 3
        assert fused.RAW_SCORES[number - 1] == expected
    assert Fraction(17, 20) == batch.PAGERANK_DAMPING
    assert Fraction(1, 49) == batch.PAGERANK_TELEPORT
    assert batch.PAGERANK_ITERATIONS == 100


def test_history_gate_target_exclusion_future_invariance_and_malformed_rejection() -> None:
    with pytest.raises(batch.InsufficientHistoryError, match="300"):
        batch.calculate_pairwise_ranking(_history(299), 299)

    history = list(_history(300))
    expected = batch.produce_candidate_portfolio(history, 300)
    with_target_and_future: list[object] = [*history, _ALTERNATE, object()]
    assert batch.produce_candidate_portfolio(with_target_and_future, 300) == expected
    with_target_and_future[300] = (13, 14, 15, 16, 17, 18)
    assert batch.produce_candidate_portfolio(with_target_and_future, 300) == expected
    before = history.copy()
    assert batch.produce_candidate_portfolio(history, 300) == expected
    assert history == before

    malformed = cast(list[object], history.copy())
    malformed[10] = (1, 2, 3, 4, 5, 5)
    with pytest.raises(ValueError, match="six unique"):
        batch.calculate_pairwise_ranking(malformed, 300)
    malformed[10] = (1, 2, 3, 4, 5)
    with pytest.raises(ValueError, match="exactly six"):
        batch.calculate_pairwise_ranking(malformed, 300)


def test_iterable_history_reads_only_the_causal_prefix() -> None:
    class PrefixOnly:
        def __iter__(self) -> Iterator[object]:
            yield from _history(300)
            raise AssertionError("future rows were consumed")

    result = batch.produce_candidate_portfolio(PrefixOnly(), 300)
    assert len(result) == 1
    assert len(result[0]) == 6


def test_exact_rank_normalization_and_equal_weight_pairwise_dependence() -> None:
    pool = tuple(range(1, 11))
    descending = tuple(Fraction(10 - position, 9) for position in range(1, 11))
    ascending = tuple(Fraction(position - 1, 9) for position in range(1, 11))
    fused = batch.rank_pairwise_scores(descending, ascending, pool)
    assert all(score == Fraction(1, 2) for score in fused.PAIRWISE_SCORES)
    assert tuple(range(1, 11)) == fused.RANKED_NUMBERS
    assert Fraction(1, 1) == fused.TRANSITION_MARKOV_COMPONENTS[0]
    assert Fraction(1, 1) == fused.GRAPH_COMPONENTS[-1]
    assert all(isinstance(score, Fraction) for score in fused.PAIRWISE_SCORES)

    markov_changed = list(descending)
    markov_changed[0], markov_changed[1] = markov_changed[1], markov_changed[0]
    assert batch.rank_pairwise_scores(
        descending, ascending, pool
    ).RANKED_NUMBERS != batch.rank_pairwise_scores(
        tuple(markov_changed), ascending, pool
    ).RANKED_NUMBERS

    graph_changed = list(ascending)
    graph_changed[0], graph_changed[1] = graph_changed[1], graph_changed[0]
    assert batch.rank_pairwise_scores(
        descending, ascending, pool
    ).RANKED_NUMBERS != batch.rank_pairwise_scores(
        descending, tuple(graph_changed), pool
    ).RANKED_NUMBERS

    markov_spike = tuple(Fraction(1 if number == 1 else 0, 1) for number in pool)
    graph_spike = tuple(Fraction(1 if number == 10 else 0, 1) for number in pool)
    combined = batch.rank_pairwise_scores(markov_spike, graph_spike, pool)
    markov_only = tuple(sorted(pool, key=lambda number: (-markov_spike[number - 1], number)))
    graph_only = tuple(sorted(pool, key=lambda number: (-graph_spike[number - 1], number)))
    assert markov_only != combined.RANKED_NUMBERS
    assert graph_only != combined.RANKED_NUMBERS


def test_traversal_pool_is_exactly_ten_and_uses_edge_then_fused_ties() -> None:
    zero_edges = tuple(tuple(Fraction(0, 1) for _ in range(49)) for _ in range(49))
    tied_scores = (Fraction(0, 1),) * 49
    assert batch.traverse_graph(zero_edges, tied_scores) == tuple(range(1, 11))

    edges = [[Fraction(0, 1)] * 49 for _ in range(49)]
    for left, right, weight in ((1, 2, 5), (1, 3, 5), (2, 4, 4), (3, 5, 6)):
        edges[left - 1][right - 1] = Fraction(weight, 1)
        edges[right - 1][left - 1] = Fraction(weight, 1)
    fused_scores = [Fraction(0, 1)] * 49
    fused_scores[2] = Fraction(1, 1)
    fused_scores[3] = Fraction(1, 1)
    pool = batch.traverse_graph(tuple(tuple(row) for row in edges), tuple(fused_scores))
    assert pool[:5] == (3, 5, 1, 2, 4)
    assert len(pool) == 10
    assert len(set(pool)) == 10


def test_aggregate_edges_and_final_candidate_are_legal_deterministic_and_causal() -> None:
    history = _history(300)
    edge_scores = batch.build_aggregate_graph_edge_scores(
        tuple(_FILLER for _ in range(300)), 300
    )
    assert edge_scores[0][1] == Fraction(1, 1)
    assert edge_scores[0][0] == Fraction(0, 1)
    assert all(
        edge_scores[left][right] == edge_scores[right][left]
        for left in range(49)
        for right in range(49)
    )

    first = batch.calculate_pairwise_ranking(history, 300)
    second = batch.calculate_pairwise_ranking(history, 300)
    assert first == second
    assert len(first.RANKED_NUMBERS) == 10
    assert first.RANKED_NUMBERS == first.GRAPH_TRAVERSAL_POOL
    assert len(set(first.RANKED_NUMBERS)) == 10
    assert len(first.TICKETS) == 1
    assert tuple(sorted(first.NATIVE_TICKET)) == first.NATIVE_TICKET
    assert len(first.NATIVE_TICKET) == 6
    assert len(set(first.NATIVE_TICKET)) == 6
    assert all(1 <= number <= 49 for number in first.NATIVE_TICKET)
    assert tuple(sorted(first.RANKED_NUMBERS[:6])) == first.NATIVE_TICKET


def test_identity_rejects_semantic_drift_and_no_rng_is_exposed() -> None:
    assert batch.DETERMINISM_CLASS == "PURE_DETERMINISTIC_NO_RNG"
    assert batch.RNG_SEMANTICS == "NONE"
    assert batch.RNG is None
    with pytest.raises(ValueError, match="DESIGN_ID"):
        batch.candidate_id_for_semantics({"DESIGN_ID": "wrong"})
