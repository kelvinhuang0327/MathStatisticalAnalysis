from __future__ import annotations

import ast
import inspect
import json
from collections.abc import Mapping
from fractions import Fraction
from typing import cast

import pytest

from lottolab.research import (
    biglotto_l2_pairwise_transition_markov_graph_pagerank_traversal_candidate_batch_r1 as candidate,
)

type Draw = tuple[int, ...]

DRAW_A: Draw = (1, 2, 3, 4, 5, 6)
DRAW_B: Draw = (7, 8, 9, 10, 11, 12)
DRAW_C: Draw = (13, 14, 15, 16, 17, 18)
c = candidate
p = c.predict_biglotto_l2_pairwise_transition_markov_graph_pagerank_traversal_weighted_score_100


def _total_map(
    default: Fraction = Fraction(0),
    overrides: Mapping[int, Fraction] | None = None,
) -> dict[int, Fraction]:
    result = {number: default for number in candidate.NUMBER_DOMAIN}
    if overrides is not None:
        for number in candidate.NUMBER_DOMAIN:
            if number in overrides:
                result[number] = overrides[number]
    return result


def _uniform_graph() -> candidate.WeightedCodrawGraph:
    size = len(candidate.NUMBER_DOMAIN)
    weights = tuple(tuple(0 for _ in candidate.NUMBER_DOMAIN) for _ in candidate.NUMBER_DOMAIN)
    kernel = tuple(
        tuple(Fraction(1, size) for _ in candidate.NUMBER_DOMAIN) for _ in candidate.NUMBER_DOMAIN
    )
    return candidate.WeightedCodrawGraph(weights, tuple(0 for _ in candidate.NUMBER_DOMAIN), kernel)


@pytest.fixture(scope="module")
def deterministic_predictions() -> tuple[
    candidate.BigLottoPairwiseCandidatePrediction,
    candidate.BigLottoPairwiseCandidatePrediction,
]:
    history = (DRAW_A,) * candidate.MINIMUM_HISTORY
    first = p(history)
    second = p(history)
    assert first is not None
    assert second is not None
    return first, second


@pytest.fixture(scope="module")
def connected_traversal() -> tuple[
    candidate.WeightedCodrawGraph,
    tuple[int, ...],
    tuple[Fraction, ...],
]:
    draws = tuple(
        tuple(sorted(((start + offset) % 49) + 1 for offset in range(6))) for start in range(101)
    )
    transition_model = candidate.build_transition_model(draws)
    transition_scores = candidate.score_transition_model(transition_model, draws[-1])
    transition_ranks = candidate.rank_transition_scores(transition_scores)
    graph = candidate.build_weighted_codraw_graph(draws[-100:])
    pagerank_vector = candidate.solve_exact_pagerank(graph.kernel)
    pagerank_scores = {number: pagerank_vector[number - 1] for number in candidate.NUMBER_DOMAIN}
    traversal, priorities = candidate.deterministic_graph_traversal(
        anchor=draws[-1],
        transition_scores=transition_scores,
        transition_ranks=transition_ranks,
        graph=graph,
        pagerank_scores=pagerank_scores,
    )
    return graph, traversal, priorities


def test_frozen_identity_constants_match_sealed_authority() -> None:
    assert candidate.METHOD_ID == "BMSGV1_L2_PAIRWISE_a9bf271fe5419f15"
    assert (
        candidate.DESIGN_NAME
        == "B649_PAIRWISE_TRANSITION_MARKOV_GRAPH_PAGERANK_TRAVERSAL_WEIGHTED_SCORE_100_V1"
    )
    assert (
        candidate.SEMANTIC_SIGNATURE
        == "77a875147dc4f0520dcfb4e1929df20aa3bfde638cd01d9860764ed53fb4cc1b"
    )


def test_minimum_history_750_returns_none_and_751_returns_complete_result(
    deterministic_predictions: tuple[
        candidate.BigLottoPairwiseCandidatePrediction,
        candidate.BigLottoPairwiseCandidatePrediction,
    ],
) -> None:
    short = p((DRAW_A,) * 750)
    assert short is None

    result = deterministic_predictions[0]
    assert len(result.ticket) == 6
    assert tuple(sorted(result.ticket)) == result.ticket
    assert len(set(result.ticket)) == 6
    assert len(result.traversal_order) == 49
    assert tuple(sorted(result.traversal_order)) == candidate.NUMBER_DOMAIN
    assert len(result.selected_step_priorities) == 49


def test_complete_history_is_validated_before_insufficient_history_fallback() -> None:
    malformed_last_draw: object = (1, 2, 3, 4, 5, 5)
    history: tuple[object, ...] = (*((DRAW_A,) * 749), malformed_last_draw)
    with pytest.raises(ValueError, match="distinct"):
        p(history)


@pytest.mark.parametrize(
    "history",
    [
        None,
        "not-a-history",
        (DRAW_A[:5],),
        ((1, 2, 3, 4, 5, 5),),
        ((True, 2, 3, 4, 5, 6),),
        ((1.0, 2, 3, 4, 5, 6),),
        (("1", 2, 3, 4, 5, 6),),
        ((0, 2, 3, 4, 5, 6),),
        ((1, 2, 3, 4, 5, 50),),
        ((1, 2, 3, 4, 5, 6, 7),),
        ({"numbers": DRAW_A},),
    ],
)
def test_malformed_inputs_raise_value_error(history: object) -> None:
    with pytest.raises(ValueError):
        p(history)


def test_draw_internal_order_is_canonicalized_but_history_order_is_not_repaired() -> None:
    assert candidate.validate_history(((6, 5, 4, 3, 2, 1),)) == (DRAW_A,)

    forward = candidate.build_transition_model((DRAW_B,) + (DRAW_A,) * 100)
    reverse = candidate.build_transition_model((DRAW_A,) * 100 + (DRAW_B,))
    assert forward.pair_counts != reverse.pair_counts


def test_causal_slices_use_exact_100_transitions_and_trailing_100_graph_draws() -> None:
    suffix = tuple(DRAW_A if index % 2 == 0 else DRAW_B for index in range(101))
    first_history = (DRAW_A,) * 650 + suffix
    second_history = (DRAW_C,) * 650 + suffix

    first = candidate.extract_causal_windows(first_history)
    second = candidate.extract_causal_windows(second_history)
    assert first is not None
    assert second is not None
    assert first == second
    assert first.transition_draws == suffix
    assert len(first.transition_draws) - 1 == candidate.TRANSITION_COUNT == 100
    assert first.graph_draws == suffix[-100:]
    assert len(first.graph_draws) == candidate.GRAPH_DRAW_COUNT == 100
    assert first.anchor == suffix[-1]


def test_changing_oldest_transition_draw_changes_markov_only_not_graph_or_anchor() -> None:
    base_history = (DRAW_C,) * 650 + (DRAW_A,) * 101
    changed_history = (DRAW_C,) * 650 + (DRAW_B,) + (DRAW_A,) * 100
    base = candidate.extract_causal_windows(base_history)
    changed = candidate.extract_causal_windows(changed_history)
    assert base is not None
    assert changed is not None
    assert base.graph_draws == changed.graph_draws
    assert base.anchor == changed.anchor
    assert candidate.build_weighted_codraw_graph(
        base.graph_draws
    ) == candidate.build_weighted_codraw_graph(changed.graph_draws)
    assert candidate.build_transition_model(
        base.transition_draws
    ) != candidate.build_transition_model(changed.transition_draws)


def test_adding_latest_completed_draw_shifts_both_frozen_causal_windows() -> None:
    history = (DRAW_C,) * 650 + (DRAW_A,) * 101
    before = candidate.extract_causal_windows(history)
    after = candidate.extract_causal_windows((*history, DRAW_B))
    assert before is not None
    assert after is not None
    assert after.transition_draws == (*before.transition_draws[1:], DRAW_B)
    assert after.graph_draws == (*before.graph_draws[1:], DRAW_B)
    assert after.anchor == DRAW_B
    assert after.transition_draws[-2:] == (DRAW_A, DRAW_B)


def test_markov_counts_kernel_scores_zero_rows_and_self_transitions_are_exact() -> None:
    model = candidate.build_transition_model((DRAW_B,) + (DRAW_A,) * 100)

    for number in DRAW_A:
        assert model.origin_counts[number - 1] == 99
    for number in DRAW_B:
        assert model.origin_counts[number - 1] == 1
    assert model.origin_counts[12:] == (0,) * 37

    assert model.pair_counts[0][0] == 99
    assert model.pair_counts[0][5] == 99
    assert model.pair_counts[6][0] == 1
    assert model.pair_counts[6][5] == 1
    assert model.pair_counts[0][6] == 0

    assert model.kernel[0][0] == Fraction(1, 6)
    assert model.kernel[0][6] == 0
    assert model.kernel[6][0] == Fraction(1, 6)
    assert model.kernel[12] == (Fraction(1, 49),) * 49
    assert all(sum(row, start=Fraction(0)) == 1 for row in model.kernel)

    scores = candidate.score_transition_model(model, DRAW_A)
    expected = {
        number: Fraction(1, 6) if number in DRAW_A else Fraction(0)
        for number in candidate.NUMBER_DOMAIN
    }
    assert scores == expected
    assert sum(scores.values(), start=Fraction(0)) == 1


def test_graph_weights_strengths_symmetry_no_self_edges_and_dangling_rows_are_exact() -> None:
    graph = candidate.build_weighted_codraw_graph((DRAW_A,) * 99 + (DRAW_B,))

    assert graph.weights[0][1] == graph.weights[1][0] == 99
    assert graph.weights[6][7] == graph.weights[7][6] == 1
    assert graph.weights[0][6] == graph.weights[6][0] == 0
    assert all(graph.weights[index][index] == 0 for index in range(49))
    assert (
        sum(graph.weights[first][second] for first in range(49) for second in range(first + 1, 49))
        == 100 * 15
    )
    assert graph.strengths[:6] == (495,) * 6
    assert graph.strengths[6:12] == (5,) * 6
    assert graph.strengths[12:] == (0,) * 37
    assert graph.kernel[0][0] == 0
    assert graph.kernel[0][1] == Fraction(1, 5)
    assert graph.kernel[12] == (Fraction(1, 49),) * 49
    assert all(sum(row, start=Fraction(0)) == 1 for row in graph.kernel)


def test_exact_pagerank_matches_independently_derived_three_node_path_solution() -> None:
    kernel = (
        (Fraction(0), Fraction(1), Fraction(0)),
        (Fraction(1, 2), Fraction(0), Fraction(1, 2)),
        (Fraction(0), Fraction(1), Fraction(0)),
    )
    expected = (Fraction(19, 74), Fraction(18, 37), Fraction(19, 74))
    pagerank = candidate.solve_exact_pagerank(kernel)

    assert pagerank == expected
    assert sum(pagerank, start=Fraction(0)) == 1
    teleport = Fraction(1 - candidate.PAGERANK_DAMPING, 3)
    for destination in range(3):
        independently_evaluated = teleport + candidate.PAGERANK_DAMPING * sum(
            (pagerank[origin] * kernel[origin][destination] for origin in range(3)),
            start=Fraction(0),
        )
        assert pagerank[destination] == independently_evaluated


def test_exact_pagerank_handles_disconnected_and_dangling_nodes_without_substitution() -> None:
    kernel = (
        (Fraction(0), Fraction(1), Fraction(0)),
        (Fraction(1), Fraction(0), Fraction(0)),
        (Fraction(1, 3), Fraction(1, 3), Fraction(1, 3)),
    )
    pagerank = candidate.solve_exact_pagerank(kernel)
    assert sum(pagerank, start=Fraction(0)) == 1
    assert all(value > 0 for value in pagerank)
    assert pagerank[0] == pagerank[1]


@pytest.mark.parametrize(
    "kernel",
    [
        ((Fraction(1, 2), Fraction(1, 2)),),
        ((Fraction(1, 2), Fraction(1, 4)), (Fraction(0), Fraction(1))),
        ((0.0, 1.0), (1.0, 0.0)),
    ],
)
def test_exact_pagerank_rejects_malformed_or_approximate_kernels(kernel: object) -> None:
    with pytest.raises(ValueError):
        candidate.solve_exact_pagerank(kernel)


def test_full_component_ranks_and_symmetric_fusion_are_independently_calculable() -> None:
    transition_scores = {number: Fraction(49 - number) for number in candidate.NUMBER_DOMAIN}
    graph_scores = {number: Fraction(number) for number in candidate.NUMBER_DOMAIN}
    transition_ranks = candidate.rank_transition_scores(transition_scores)
    graph_ranks = candidate.rank_graph_scores(graph_scores, graph_scores, graph_scores)
    fused = candidate.fuse_rank_scores(transition_ranks, graph_ranks)

    expected_transition = {number: Fraction(49 - number, 48) for number in candidate.NUMBER_DOMAIN}
    expected_graph = {number: Fraction(number - 1, 48) for number in candidate.NUMBER_DOMAIN}
    assert transition_ranks == expected_transition
    assert graph_ranks == expected_graph
    assert transition_ranks[1] == graph_ranks[49] == 1
    assert transition_ranks[49] == graph_ranks[1] == 0
    assert fused == {number: Fraction(1, 2) for number in candidate.NUMBER_DOMAIN}


def test_graph_full_rank_uses_pagerank_local_exposure_then_number_ties() -> None:
    zeros = _total_map()

    pagerank_break = _total_map(overrides={2: Fraction(1)})
    ranks = candidate.rank_graph_scores(zeros, pagerank_break, zeros)
    assert ranks[2] == 1

    local_break = _total_map(overrides={3: Fraction(1)})
    ranks = candidate.rank_graph_scores(zeros, zeros, local_break)
    assert ranks[3] == 1

    all_tie_ranks = candidate.rank_graph_scores(zeros, zeros, zeros)
    assert all_tie_ranks == {
        number: Fraction(49 - number, 48) for number in candidate.NUMBER_DOMAIN
    }


@pytest.mark.parametrize(
    "winning_layer,expected",
    [
        ("fused", 2),
        ("graph_rank", 2),
        ("pagerank", 2),
        ("local", 2),
        ("transition_rank", 2),
        ("transition_score", 2),
        ("number", 1),
    ],
)
def test_complete_traversal_tie_chain_is_applied_in_frozen_order(
    winning_layer: str, expected: int
) -> None:
    layers: dict[str, dict[int, Fraction]] = {
        "fused": _total_map(),
        "graph_rank": _total_map(),
        "pagerank": _total_map(),
        "local": _total_map(),
        "transition_rank": _total_map(),
        "transition_score": _total_map(),
    }
    if winning_layer != "number":
        layers[winning_layer][2] = Fraction(1)

    selected = tuple(range(3, 50))
    assert (
        candidate.select_next_number(
            selected,
            layers["fused"],
            layers["graph_rank"],
            layers["pagerank"],
            layers["local"],
            layers["transition_rank"],
            layers["transition_score"],
        )
        == expected
    )


def test_adaptive_context_is_literal_anchor_union_selected_set() -> None:
    graph = candidate.build_weighted_codraw_graph((DRAW_A,) * 100)
    pagerank = _total_map(Fraction(1, 49))
    initial = candidate.score_graph_step(graph, pagerank, DRAW_A)
    after_selecting_anchor = candidate.score_graph_step(
        graph, pagerank, tuple(sorted(set(DRAW_A) | {1}))
    )
    after_selecting_isolated = candidate.score_graph_step(
        graph, pagerank, tuple(sorted(set(DRAW_A) | {7}))
    )

    assert initial == after_selecting_anchor
    assert initial.local_graph_exposure != after_selecting_isolated.local_graph_exposure
    assert sum(initial.local_graph_exposure.values(), start=Fraction(0)) == 1
    assert sum(after_selecting_isolated.local_graph_exposure.values(), start=Fraction(0)) == 1


def test_all_tie_traversal_is_full_deterministic_permutation_with_exact_ticket() -> None:
    graph = _uniform_graph()
    transition_scores = _total_map()
    transition_ranks = candidate.rank_transition_scores(transition_scores)
    pagerank = _total_map(Fraction(1, 49))
    traversal, priorities = candidate.deterministic_graph_traversal(
        anchor=DRAW_A,
        transition_scores=transition_scores,
        transition_ranks=transition_ranks,
        graph=graph,
        pagerank_scores=pagerank,
    )

    assert traversal == candidate.NUMBER_DOMAIN
    assert tuple(sorted(traversal[:6])) == DRAW_A
    assert len(priorities) == 49
    assert all(isinstance(value, Fraction) for value in priorities)


def test_connected_graph_traversal_covers_every_node_and_terminates(
    connected_traversal: tuple[
        candidate.WeightedCodrawGraph,
        tuple[int, ...],
        tuple[Fraction, ...],
    ],
) -> None:
    graph, traversal, priorities = connected_traversal
    assert all(strength > 0 for strength in graph.strengths)
    assert tuple(sorted(traversal)) == candidate.NUMBER_DOMAIN
    assert len(set(traversal)) == 49
    assert 1 in traversal and 49 in traversal
    assert len(priorities) == 49


def test_disconnected_graph_prediction_uses_exact_fallback_and_includes_isolated_nodes(
    deterministic_predictions: tuple[
        candidate.BigLottoPairwiseCandidatePrediction,
        candidate.BigLottoPairwiseCandidatePrediction,
    ],
) -> None:
    result = deterministic_predictions[0]
    graph = candidate.build_weighted_codraw_graph((DRAW_A,) * 100)
    assert graph.strengths[48] == 0
    assert graph.kernel[48] == (Fraction(1, 49),) * 49
    assert result.ticket == DRAW_A
    assert 49 in result.traversal_order

    teleport = Fraction(1 - candidate.PAGERANK_DAMPING, 49)
    for destination in range(49):
        expected = teleport + candidate.PAGERANK_DAMPING * sum(
            (
                result.pagerank_scores[origin + 1] * graph.kernel[origin][destination]
                for origin in range(49)
            ),
            start=Fraction(0),
        )
        assert result.pagerank_scores[destination + 1] == expected


def test_repeated_execution_and_canonical_serialization_are_byte_identical(
    deterministic_predictions: tuple[
        candidate.BigLottoPairwiseCandidatePrediction,
        candidate.BigLottoPairwiseCandidatePrediction,
    ],
) -> None:
    first, second = deterministic_predictions
    assert first == second
    first_bytes = candidate.canonical_serialize_prediction(first)
    second_bytes = candidate.canonical_serialize_prediction(second)
    assert first_bytes == second_bytes
    assert candidate.canonical_serialize_prediction(None) == b"null"

    payload = cast(dict[str, object], json.loads(first_bytes))
    assert payload["method_id"] == candidate.METHOD_ID
    assert payload["semantic_signature"] == candidate.SEMANTIC_SIGNATURE
    assert all(isinstance(value, Fraction) for value in first.transition_scores.values())
    assert all(isinstance(value, Fraction) for value in first.transition_normalized_ranks.values())
    assert all(isinstance(value, Fraction) for value in first.pagerank_scores.values())
    assert all(isinstance(value, Fraction) for value in first.selected_step_priorities)


def test_module_imports_enforce_standard_library_scientific_firewall() -> None:
    tree = ast.parse(inspect.getsource(candidate))
    imported_roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_roots.update(alias.name.split(".", maxsplit=1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported_roots.add(node.module.split(".", maxsplit=1)[0])

    forbidden = {
        "datetime",
        "httpx",
        "lottolab",
        "numpy",
        "os",
        "pathlib",
        "random",
        "requests",
        "scipy",
        "secrets",
        "sqlite3",
        "time",
    }
    assert imported_roots.isdisjoint(forbidden)
    assert imported_roots <= {
        "__future__",
        "collections",
        "dataclasses",
        "fractions",
        "itertools",
        "json",
        "typing",
    }
