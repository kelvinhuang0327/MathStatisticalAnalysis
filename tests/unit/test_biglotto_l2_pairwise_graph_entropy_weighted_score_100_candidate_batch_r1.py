"""Focused acceptance tests for the sealed GRAPH + ENTROPY candidate."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator, Sequence
from fractions import Fraction
from pathlib import Path
from typing import cast

import pytest

from lottolab.research import (
    biglotto_graph_network_multi_ticket_candidate_batch_r1 as graph_parent,
)
from lottolab.research import (
    biglotto_l2_pairwise_graph_entropy_weighted_score_100_candidate_batch_r1 as batch,
)

Ticket = tuple[int, int, int, int, int, int]
_AUTHORITY_ROOT = Path(
    "/Users/kelvin/VibeCoding-WorkSpace/.task-data/"
    "ADVANCE_LEVEL2_FRONTIER_AFTER_BMSGV1_L2_PAIRWISE_4DC9FF4FD526D800_R1"
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


def _authority() -> dict[str, object]:
    return cast(
        dict[str, object],
        json.loads(
            (_AUTHORITY_ROOT / "implementation_handoff.json").read_text(
                encoding="utf-8"
            )
        ),
    )


def _reference_entropy(history: Sequence[Ticket]) -> tuple[Fraction, ...]:
    counts = tuple(
        sum(number in draw for draw in history[-50:])
        for number in range(1, 50)
    )
    expected = Fraction(300, 49)
    epsilon = Fraction(1, 10)
    return tuple(
        Fraction(1, 1) / (abs(Fraction(count, 1) - expected) + epsilon)
        for count in counts
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
    assert batch.FEATURE_1 == "GRAPH"
    assert batch.FEATURE_2 == "ENTROPY"
    assert batch.WINDOW == 100
    assert batch.GRAPH_WINDOWS == (50, 300, 750)
    assert batch.ENTROPY_WINDOW == 50
    assert batch.MINIMUM_HISTORY == 750
    assert batch.RANKED_POOL_CARDINALITY == 10
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


def test_graph_parent_window_and_fused_pool_outputs_are_exactly_reused() -> None:
    history = _history(750)
    expected_windows = graph_parent.calculate_window_rankings(history, 750)
    actual_windows = batch.calculate_graph_window_rankings(history, 750)
    assert actual_windows == expected_windows
    assert tuple(window.WINDOW for window in actual_windows) == (50, 300, 750)

    expected_fused = graph_parent.fuse_window_rankings(expected_windows)
    actual_fused = batch.calculate_graph_parent_ranking(history, 750)
    assert actual_fused == expected_fused
    assert len(expected_fused.TOP_NUMBERS) == 10
    assert batch.calculate_graph_traversal_pool(history, 750) == expected_fused.TOP_NUMBERS

    graph_ranking = batch.calculate_graph_ranking(history, 750)
    assert graph_ranking.POOL_NUMBERS == expected_fused.TOP_NUMBERS
    assert graph_ranking.ORDERED_NUMBERS == expected_fused.TOP_NUMBERS
    assert tuple(
        expected_fused.mean_rank(number) for number in expected_fused.TOP_NUMBERS
    ) == graph_ranking.RAW_SCORES
    assert tuple(
        Fraction(10 - position, 9) for position in range(1, 11)
    ) == graph_ranking.NORMALIZED_RANKS


def test_entropy_parent_statistics_and_pool_order_match_independent_exact_reference() -> None:
    history = _history(750)
    expected = _reference_entropy(history)
    statistics = batch.calculate_entropy_statistics(history, 750)
    assert tuple(range(1, 50)) == statistics.POOL_NUMBERS
    assert tuple(
        sum(number in draw for draw in history[-50:])
        for number in range(1, 50)
    ) == statistics.COUNTS_50
    assert expected == statistics.RAW_SCORES
    assert all(isinstance(value, Fraction) for value in statistics.RAW_SCORES)

    pool = batch.calculate_graph_traversal_pool(history, 750)
    ranking = batch.calculate_entropy_pool_ranking(history, 750, pool)
    expected_order = tuple(sorted(pool, key=lambda number: (-expected[number - 1], number)))
    assert expected_order == ranking.ORDERED_NUMBERS
    assert tuple(expected[number - 1] for number in pool) == ranking.RAW_SCORES
    assert tuple(
        expected_order.index(number) + 1 for number in pool
    ) == ranking.POSITIONS
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
    with pytest.raises(ValueError, match="duplicate"):
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


def test_exact_ten_number_normalization_equal_fusion_and_pairwise_dependence() -> None:
    pool = tuple(range(1, 11))
    descending = tuple(Fraction(10 - position, 9) for position in range(1, 11))
    ascending = tuple(Fraction(position - 1, 9) for position in range(1, 11))
    fused = batch.rank_pairwise_scores(descending, ascending, pool)
    assert all(score == Fraction(1, 2) for score in fused.PAIRWISE_SCORES)
    assert descending == fused.GRAPH_COMPONENTS
    assert ascending == fused.ENTROPY_COMPONENTS
    assert all(isinstance(score, Fraction) for score in fused.PAIRWISE_SCORES)

    graph_spike = tuple(Fraction(1 if number == 1 else 0) for number in pool)
    entropy_spike = tuple(Fraction(1 if number == 10 else 0) for number in pool)
    combined = batch.rank_pairwise_scores(graph_spike, entropy_spike, pool)
    assert len(combined.RANKED_NUMBERS) == 10
    assert tuple(sorted(combined.NATIVE_TICKET)) == combined.NATIVE_TICKET
    assert Fraction(1, 2) == batch.FUSION_WEIGHT_1
    assert Fraction(1, 2) == batch.FUSION_WEIGHT_2


def test_ticket_shape_deterministic_regeneration_and_no_rng() -> None:
    history = _history(750)
    first = batch.calculate_pairwise_ranking(history, 750)
    second = batch.calculate_pairwise_ranking(history, 750)
    assert first == second
    assert len(first.POOL_NUMBERS) == 10
    assert len(first.RANKED_NUMBERS) == 10
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
    with pytest.raises(TypeError, match="exact Fraction or integer"):
        batch.rank_pairwise_scores((0.5,) * 10, zeros, pool)


def test_entropy_formula_uses_six_main_numbers_and_no_cooccurrence_side_channel() -> None:
    history = list(_history(750))
    history[-1] = (1, 2, 3, 4, 5, 49)
    statistics = batch.calculate_entropy_statistics(history, 750)
    count_1 = sum(1 in draw for draw in history[-50:])
    expected = Fraction(1, 1) / (
        abs(Fraction(count_1, 1) - Fraction(300, 49)) + Fraction(1, 10)
    )
    assert statistics.RAW_SCORES[0] == expected
    assert statistics.RAW_SCORES[0] != statistics.RAW_SCORES[48] or count_1 == sum(
        49 in draw for draw in history[-50:]
    )


def test_parent_pairwise_components_are_both_present_in_final_records() -> None:
    ranking = batch.calculate_pairwise_ranking(_history(750), 750)
    assert len(ranking.SCORES) == 10
    assert all(
        record.GRAPH_COMPONENT >= 0
        and record.ENTROPY_COMPONENT >= 0
        and Fraction(1, 2) * record.GRAPH_COMPONENT
        + Fraction(1, 2) * record.ENTROPY_COMPONENT
        == record.PAIRWISE_SCORE
        for record in ranking.SCORES
    )
    assert tuple(record.NUMBER for record in ranking.SCORES) == ranking.RANKED_NUMBERS
