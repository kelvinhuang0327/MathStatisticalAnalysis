"""Focused acceptance tests for the sealed HOT_COLD + GRAPH candidate."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator, Sequence
from fractions import Fraction
from itertools import combinations
from pathlib import Path
from typing import cast

import pytest

from lottolab.research import (
    biglotto_graph_network_multi_ticket_candidate_batch_r1 as graph_parent,
)
from lottolab.research import (
    biglotto_l2_pairwise_hot_cold_graph_weighted_score_100_candidate_batch_r1 as batch,
)

Ticket = tuple[int, int, int, int, int, int]
_AUTHORITY_ROOT = Path(
    "/Users/kelvin/VibeCoding-WorkSpace/.task-data/"
    "ADVANCE_LEVEL2_FRONTIER_AFTER_BMSGV1_L2_PAIRWISE_5B92DF6E42366E6B_R1"
)
_DRAW_TYPES: tuple[Ticket, ...] = (
    (1, 2, 3, 4, 5, 6),
    (1, 7, 13, 14, 15, 16),
    (2, 8, 17, 18, 19, 20),
    (21, 22, 23, 24, 25, 26),
    (30, 31, 32, 33, 34, 35),
    (36, 37, 38, 39, 40, 41),
    (42, 43, 44, 45, 46, 47),
)


def _history(count: int) -> tuple[Ticket, ...]:
    return tuple(_DRAW_TYPES[index % len(_DRAW_TYPES)] for index in range(count))


def _reference_hot_cold(history: Sequence[Ticket]) -> tuple[Fraction, ...]:
    counts = [0] * 50
    first_observation: list[int | None] = [None] * 50
    observation_index = 0
    for draw in history[-50:]:
        for number in draw:
            counts[number] += 1
            if first_observation[number] is None:
                first_observation[number] = observation_index
            observation_index += 1
    positive = tuple(number for number in range(1, 50) if counts[number] > 0)
    positive_order = tuple(
        sorted(
            positive,
            key=lambda number: (
                -counts[number],
                cast(int, first_observation[number]),
                number,
            ),
        )
    )
    hot_pool = positive_order[:20]
    pair_counts = [[0] * 50 for _ in range(50)]
    for draw in history[-100:]:
        for left, right in combinations(draw, 2):
            pair_counts[left][right] += 1
            pair_counts[right][left] += 1
    scores = [Fraction(0, 1)] * 50
    size = len(hot_pool)
    for index, number in enumerate(hot_pool):
        rank_score = Fraction(size - index, size)
        mean = (
            Fraction(0, 1)
            if size <= 1
            else sum(
                (
                    Fraction(pair_counts[number][other], 100)
                    for other in hot_pool
                    if other != number
                ),
                Fraction(0, 1),
            )
            / (size - 1)
        )
        scores[number] = Fraction(7, 10) * rank_score + Fraction(3, 10) * mean
    return tuple(scores[1:])


def _authority() -> dict[str, object]:
    return cast(
        dict[str, object],
        json.loads(
            (_AUTHORITY_ROOT / "implementation_handoff.json").read_text(
                encoding="utf-8"
            )
        ),
    )


def test_authority_checksum_identity_signature_and_paths_are_exact() -> None:
    for line in (_AUTHORITY_ROOT / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
        expected_hash, relative_path = line.split(maxsplit=1)
        assert hashlib.sha256(
            (_AUTHORITY_ROOT / relative_path).read_bytes()
        ).hexdigest() == expected_hash

    authority = _authority()
    assert authority["SELECTED_GAP_ID"] == batch.SELECTED_GAP_ID
    assert authority["CANDIDATE_ID"] == batch.CANDIDATE_ID
    assert authority["DESIGN_ID"] == batch.DESIGN_ID
    assert authority["DESIGN_SIGNATURE_SHA256"] == batch.DESIGN_SIGNATURE_SHA256
    assert authority["IMPLEMENTATION_READY"] == "YES"
    assert authority["EXPECTED_IMPLEMENTATION_MODULE"] == batch.IMPLEMENTATION_MODULE
    assert authority["EXPECTED_IMPLEMENTATION_SYMBOL"] == batch.IMPLEMENTATION_SYMBOL
    assert authority["EXPECTED_FOCUSED_TEST_MODULE"] == batch.EXPECTED_FOCUSED_TEST_MODULE
    assert json.loads(batch.canonical_semantic_json(batch.CANDIDATE_SEMANTICS)) == (
        authority["DESIGN_SIGNATURE_OBJECT"]
    )
    assert batch.signature_hash_for_semantics(batch.CANDIDATE_SEMANTICS) == (
        batch.DESIGN_SIGNATURE_SHA256
    )


def test_candidate_identity_contract_is_exactly_one_and_fully_frozen() -> None:
    authority = _authority()
    assert len(batch.CANDIDATE_AUTHORITIES) == 1
    assert batch.CANDIDATE_IDS == (batch.CANDIDATE_ID,)
    assert batch.SELECTED_GAP_ID == batch.CANDIDATE_ID
    assert batch.FEATURE_1 == "HOT_COLD"
    assert batch.FEATURE_2 == "GRAPH"
    assert batch.WINDOW == 100
    assert batch.WINDOWS == (50, 300, 750)
    assert batch.MINIMUM_HISTORY == 750
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


def test_graph_parent_parity_and_frozen_ten_number_traversal_pool() -> None:
    history = _history(750)
    rankings = batch.calculate_graph_window_rankings(history, 750)
    assert tuple(window.WINDOW for window in rankings) == (50, 300, 750)
    assert rankings == graph_parent.calculate_window_rankings(history, 750)
    fused = batch.calculate_graph_parent_ranking(history, 750)
    assert fused == graph_parent.calculate_fused_number_ranking(history, 750)
    pool = batch.calculate_graph_traversal_pool(history, 750)
    assert pool == fused.TOP_NUMBERS
    assert len(pool) == 10
    assert len(set(pool)) == 10
    assert tuple(batch.calculate_graph_ranking(history, 750).ORDERED_NUMBERS) == pool


def test_hot_cold_parent_raw_scores_match_independent_exact_reference() -> None:
    history = _history(750)
    assert batch.calculate_hot_cold_raw_scores(history, 750) == _reference_hot_cold(history)
    raw = batch.calculate_hot_cold_raw_scores(history, 750)
    assert all(isinstance(value, Fraction) for value in raw)
    assert all(value >= 0 for value in raw)
    pool = batch.calculate_graph_traversal_pool(history, 750)
    ranking = batch.calculate_hot_cold_ranking(history, 750)
    assert pool == ranking.POOL_NUMBERS
    assert tuple(raw[number - 1] for number in pool) == ranking.RAW_SCORES
    assert tuple(sorted(pool, key=lambda number: (-raw[number - 1], number))) == (
        ranking.ORDERED_NUMBERS
    )
    assert tuple(
        Fraction(10 - ranking.position(number), 9) for number in pool
    ) == ranking.NORMALIZED_RANKS


def test_history_gate_target_exclusion_future_invariance_and_malformed_rejection() -> None:
    with pytest.raises(batch.InsufficientHistoryError, match="750"):
        batch.calculate_pairwise_ranking(_history(749), 749)

    history = list(_history(750))
    expected = batch.produce_candidate_portfolio(history, 750)
    before = history.copy()
    with_target_and_future: list[object] = [*history, object(), object()]
    assert batch.produce_candidate_portfolio(with_target_and_future, 750) == expected
    with_target_and_future[750] = (1, 1, 1, 1, 1, 1)
    assert batch.produce_candidate_portfolio(with_target_and_future, 750) == expected
    assert history == before

    malformed = cast(list[object], history.copy())
    malformed[10] = (1, 2, 3, 4, 5, 5)
    with pytest.raises(ValueError, match="six unique"):
        batch.calculate_pairwise_ranking(malformed, 750)
    malformed[10] = (1, 2, 3, 4, 5)
    with pytest.raises(ValueError, match="exactly six"):
        batch.calculate_pairwise_ranking(malformed, 750)


def test_iterable_history_reads_only_the_causal_prefix() -> None:
    class PrefixOnly:
        def __iter__(self) -> Iterator[object]:
            yield from _history(750)
            raise AssertionError("future rows were consumed")

    result = batch.produce_candidate_portfolio(PrefixOnly(), 750)
    assert len(result) == 1
    assert len(result[0]) == 6


def test_exact_pool_normalization_equal_fusion_and_pairwise_dependence() -> None:
    pool = tuple(range(1, 11))
    descending = tuple(Fraction(10 - position, 9) for position in range(1, 11))
    ascending = tuple(Fraction(position - 1, 9) for position in range(1, 11))
    fused = batch.rank_pairwise_scores(descending, ascending, pool)
    assert all(score == Fraction(1, 2) for score in fused.PAIRWISE_SCORES)
    assert descending == fused.HOT_COLD_COMPONENTS
    assert ascending == fused.GRAPH_COMPONENTS
    assert all(isinstance(score, Fraction) for score in fused.PAIRWISE_SCORES)

    hot_changed = list(ascending)
    hot_changed[0], hot_changed[1] = hot_changed[1], hot_changed[0]
    assert batch.rank_pairwise_scores(
        ascending, descending, pool
    ).RANKED_NUMBERS != batch.rank_pairwise_scores(
        tuple(hot_changed), descending, pool
    ).RANKED_NUMBERS

    graph_changed = list(descending)
    graph_changed[0], graph_changed[1] = graph_changed[1], graph_changed[0]
    assert batch.rank_pairwise_scores(
        ascending, descending, pool
    ).RANKED_NUMBERS != batch.rank_pairwise_scores(
        ascending, tuple(graph_changed), pool
    ).RANKED_NUMBERS

    graph_spike = tuple(Fraction(1 if number == 1 else 0, 1) for number in pool)
    hot_spike = tuple(Fraction(1 if number == 10 else 0, 1) for number in pool)
    combined = batch.rank_pairwise_scores(hot_spike, graph_spike, pool)
    assert pool != combined.RANKED_NUMBERS
    assert Fraction(1, 2) == batch.FUSION_WEIGHT_1
    assert Fraction(1, 2) == batch.FUSION_WEIGHT_2


def test_ticket_shape_deterministic_regeneration_and_no_rng() -> None:
    history = _history(750)
    first = batch.calculate_pairwise_ranking(history, 750)
    second = batch.calculate_pairwise_ranking(history, 750)
    assert first == second
    assert first.POOL_NUMBERS == first.GRAPH_TRAVERSAL_POOL
    assert len(first.RANKED_NUMBERS) == 10
    assert len(set(first.RANKED_NUMBERS)) == 10
    assert len(first.TICKETS) == batch.NATIVE_TICKET_COUNT == 1
    assert tuple(sorted(first.NATIVE_TICKET)) == first.NATIVE_TICKET
    assert len(first.NATIVE_TICKET) == 6
    assert len(set(first.NATIVE_TICKET)) == 6
    assert all(1 <= number <= 49 for number in first.NATIVE_TICKET)
    assert tuple(sorted(first.RANKED_NUMBERS[:6])) == first.NATIVE_TICKET
    assert batch.RNG is None
    assert batch.RNG_SEMANTICS == "NONE"
    assert batch.DETERMINISM_CLASS == "PURE_DETERMINISTIC_NO_RNG"


def test_pairwise_requires_both_parent_vectors_and_identity_rejects_drift() -> None:
    pool = tuple(range(1, 11))
    ones = (Fraction(1, 1),) * 10
    zeros = (Fraction(0, 1),) * 10
    assert pool == batch.rank_pairwise_scores(ones, zeros, pool).RANKED_NUMBERS
    assert pool == batch.rank_pairwise_scores(zeros, ones, pool).RANKED_NUMBERS
    with pytest.raises(ValueError, match="DESIGN_ID"):
        batch.candidate_id_for_semantics({"DESIGN_ID": "wrong"})
    with pytest.raises(ValueError, match="CANDIDATE_ID"):
        batch.candidate_id_for_semantics({"CANDIDATE_ID": "wrong"})
