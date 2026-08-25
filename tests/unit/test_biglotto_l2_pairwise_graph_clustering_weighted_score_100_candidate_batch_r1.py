"""Focused acceptance tests for the sealed GRAPH + CLUSTERING candidate."""

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
    biglotto_l2_pairwise_graph_clustering_weighted_score_100_candidate_batch_r1 as batch,
)
from lottolab.research import (
    biglotto_multiscale_temporal_profile_cluster_multi_ticket_candidate_batch_r1,
)

clustering_parent = biglotto_multiscale_temporal_profile_cluster_multi_ticket_candidate_batch_r1

Ticket = tuple[int, int, int, int, int, int]
_AUTHORITY_ROOT = Path(
    "/Users/kelvin/VibeCoding-WorkSpace/.task-data/"
    "ADVANCE_LEVEL2_FRONTIER_AFTER_BMSGV1_L2_PAIRWISE_A9BF271FE5419F15_R1"
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


def _reference_graph_edges(
    history: Sequence[Ticket], window: int
) -> tuple[tuple[int, ...], ...]:
    edges = [[0] * 49 for _ in range(49)]
    for draw in history[-window:]:
        for left, right in combinations(sorted(draw), 2):
            edges[left - 1][right - 1] += 1
            edges[right - 1][left - 1] += 1
    return tuple(tuple(row) for row in edges)


def _reference_page_rank(
    edges: tuple[tuple[int, ...], ...], iterations: int = 20
) -> tuple[Fraction, ...]:
    strengths = tuple(sum(row) for row in edges)
    damping = Fraction(17, 20)
    ranks: tuple[Fraction, ...] = (Fraction(1, 49),) * 49
    for _ in range(iterations):
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
                    if strengths[source] > 0 and source != target
                ),
                Fraction(0, 1),
            )
            next_ranks.append(
                (1 - damping) * Fraction(1, 49)
                + damping * (incoming + dangling / 49)
            )
        ranks = tuple(next_ranks)
    return ranks


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
    assert authority["EXPECTED_FOCUSED_TEST_MODULE"] == batch.EXPECTED_FOCUSED_TEST_MODULE

    completed = json.loads(
        (_AUTHORITY_ROOT / "completed_v1_semantics.json").read_text(encoding="utf-8")
    )
    signature_object = cast(dict[str, object], completed["DESIGN_SIGNATURE_OBJECT"])
    assert json.loads(batch.canonical_semantic_json(batch.CANDIDATE_SEMANTICS)) == (
        signature_object
    )
    assert batch.signature_hash_for_semantics(batch.CANDIDATE_SEMANTICS) == (
        batch.DESIGN_SIGNATURE_SHA256
    )


def test_candidate_count_and_authority_controlled_fields_are_exactly_one() -> None:
    authority = _authority()
    assert len(batch.CANDIDATE_AUTHORITIES) == 1
    assert batch.CANDIDATE_IDS == (batch.CANDIDATE_ID,)
    assert batch.CANDIDATE_ID == "BMSGV1_L2_PAIRWISE_67e4bb1a0ca281fe"
    assert batch.SELECTED_GAP_ID == batch.CANDIDATE_ID
    assert batch.FEATURE_1 == "GRAPH"
    assert batch.FEATURE_2 == "CLUSTERING"
    assert batch.WINDOW == 100
    assert batch.WINDOWS == (50, 300, 750)
    assert batch.FUSION == "WEIGHTED_SCORE"
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


def test_graph_parent_edges_pagerank_and_fusion_match_independent_reference() -> None:
    history = _history(750)
    rankings = batch.calculate_graph_window_rankings(history, 750)
    assert tuple(window.WINDOW for window in rankings) == (50, 300, 750)
    assert rankings == graph_parent.calculate_window_rankings(history, 750)
    for ranking in rankings:
        expected_edges = _reference_graph_edges(history, ranking.WINDOW)
        assert expected_edges == ranking.EDGE_COUNTS
        assert _reference_page_rank(expected_edges) == ranking.PAGERANKS
        assert sum(map(sum, ranking.EDGE_COUNTS)) == ranking.WINDOW * 30
        assert sum(ranking.PAGERANKS, Fraction(0, 1)) == Fraction(1, 1)
        assert all(ranking.EDGE_COUNTS[number][number] == 0 for number in range(49))

    fused = batch.calculate_graph_parent_ranking(history, 750)
    assert fused == graph_parent.calculate_fused_number_ranking(history, 750)
    assert fused.ORDERED_NUMBERS[:10] == fused.TOP_NUMBERS
    assert len(fused.TOP_NUMBERS) == 10
    graph_component = batch.calculate_graph_ranking(history, 750)
    assert graph_component.POOL_NUMBERS == fused.TOP_NUMBERS
    assert tuple(
        Fraction(10 - position, 9) for position in range(1, 11)
    ) == graph_component.NORMALIZED_RANKS
    assert all(
        tuple(sorted(fused.robustness(number))) == fused.robustness(number)
        for number in range(1, 50)
    )


def test_clustering_parent_profiles_distances_and_partition_match_exact_parent() -> None:
    history = _history(750)
    profiles = batch.calculate_temporal_profiles(history, 750)
    assert profiles == clustering_parent.calculate_temporal_profiles(history, 750)
    for number in (1, 2, 7, 21, 49):
        counts = tuple(
            sum(number in draw for draw in history[-window:]) for window in (50, 300, 750)
        )
        assert profiles.OCCURRENCE_COUNTS[number - 1] == counts
        assert profiles.RATES[number - 1] == tuple(
            Fraction(count, window) for count, window in zip(counts, (50, 300, 750), strict=True)
        )
    for left, right in ((1, 2), (1, 49), (7, 21), (21, 49)):
        expected = sum(
            abs(a - b) for a, b in zip(profiles.profile(left), profiles.profile(right), strict=True)
        ) / 3
        assert profiles.profile_distance(left, right) == expected

    partition = batch.calculate_cluster_partition(history, 750)
    assert partition == clustering_parent.calculate_cluster_partition(history, 750)
    assert len(partition.ORDERED_CLUSTERS) == 10
    assert sorted(number for cluster in partition.ORDERED_CLUSTERS for number in cluster) == list(
        range(1, 50)
    )
    assert len(set(partition.ORDERED_REPRESENTATIVES)) == 10
    for cluster, representative in zip(
        partition.ORDERED_CLUSTERS, partition.ORDERED_REPRESENTATIVES, strict=True
    ):
        assert representative in cluster


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
    with pytest.raises(ValueError, match="exactly 6"):
        batch.calculate_pairwise_ranking(malformed, 750)


def test_iterable_history_reads_only_the_causal_prefix() -> None:
    class PrefixOnly:
        def __iter__(self) -> Iterator[object]:
            yield from _history(750)
            raise AssertionError("future rows were consumed")

    result = batch.produce_candidate_portfolio(PrefixOnly(), 750)
    assert len(result) == 1
    assert len(result[0]) == 6


def test_exact_normalization_equal_fusion_and_pairwise_dependence() -> None:
    pool = tuple(range(1, 11))
    descending = tuple(Fraction(10 - position, 9) for position in range(1, 11))
    ascending = tuple(Fraction(position - 1, 9) for position in range(1, 11))
    fused = batch.rank_pairwise_scores(descending, ascending, pool)
    assert all(score == Fraction(1, 2) for score in fused.PAIRWISE_SCORES)
    assert descending == fused.GRAPH_COMPONENTS
    assert ascending == fused.CLUSTERING_COMPONENTS
    assert all(isinstance(score, Fraction) for score in fused.PAIRWISE_SCORES)

    graph_changed = list(descending)
    graph_changed[0], graph_changed[1] = graph_changed[1], graph_changed[0]
    assert batch.rank_pairwise_scores(
        descending, ascending, pool
    ).RANKED_NUMBERS != batch.rank_pairwise_scores(
        tuple(graph_changed), ascending, pool
    ).RANKED_NUMBERS

    clustering_changed = list(ascending)
    clustering_changed[0], clustering_changed[1] = clustering_changed[1], clustering_changed[0]
    assert batch.rank_pairwise_scores(
        descending, ascending, pool
    ).RANKED_NUMBERS != batch.rank_pairwise_scores(
        descending, tuple(clustering_changed), pool
    ).RANKED_NUMBERS

    graph_spike = tuple(Fraction(1 if number == 1 else 0, 1) for number in pool)
    clustering_spike = tuple(Fraction(1 if number == 10 else 0, 1) for number in pool)
    combined = batch.rank_pairwise_scores(graph_spike, clustering_spike, pool)
    graph_only = tuple(sorted(pool, key=lambda number: (-graph_spike[number - 1], number)))
    clustering_only = tuple(
        sorted(pool, key=lambda number: (-clustering_spike[number - 1], number))
    )
    assert graph_only != combined.RANKED_NUMBERS
    assert clustering_only != combined.RANKED_NUMBERS
    assert Fraction(1, 2) == batch.FUSION_WEIGHT_1
    assert Fraction(1, 2) == batch.FUSION_WEIGHT_2

    all_tied = batch.rank_pairwise_scores((Fraction(1, 2),) * 10, (Fraction(1, 2),) * 10, pool)
    assert pool == all_tied.RANKED_NUMBERS


def test_graph_traversal_pool_ticket_shape_and_deterministic_regeneration() -> None:
    history = _history(750)
    graph_parent_ranking = batch.calculate_graph_parent_ranking(history, 750)
    pool = batch.calculate_graph_traversal_pool(history, 750)
    assert pool == graph_parent_ranking.TOP_NUMBERS
    assert pool == batch.build_graph_traversal_pool(history, 750)
    assert len(pool) == 10
    assert len(set(pool)) == 10
    assert all(1 <= number <= 49 for number in pool)

    first = batch.calculate_pairwise_ranking(history, 750)
    second = batch.calculate_pairwise_ranking(history, 750)
    assert first == second
    assert pool == first.GRAPH_TRAVERSAL_POOL
    assert len(first.RANKED_NUMBERS) == 10
    assert len(set(first.RANKED_NUMBERS)) == 10
    assert len(first.TICKETS) == batch.NATIVE_TICKET_COUNT == 1
    assert tuple(sorted(first.NATIVE_TICKET)) == first.NATIVE_TICKET
    assert len(first.NATIVE_TICKET) == 6
    assert len(set(first.NATIVE_TICKET)) == 6
    assert all(1 <= number <= 49 for number in first.NATIVE_TICKET)
    assert tuple(sorted(first.RANKED_NUMBERS[:6])) == first.NATIVE_TICKET
    assert batch.produce_candidate_portfolio(history, 750) == (first.NATIVE_TICKET,)


def test_identity_rejects_semantic_drift_and_no_rng_is_exposed() -> None:
    assert batch.DETERMINISM_CLASS == "PURE_DETERMINISTIC_NO_RNG"
    assert batch.RNG_SEMANTICS == "NONE"
    assert batch.RNG is None
    with pytest.raises(ValueError, match="DESIGN_ID"):
        batch.candidate_id_for_semantics({"DESIGN_ID": "wrong"})
