"""Frozen Level-2 transition-Markov plus graph-PageRank Big Lotto candidate.

The module is deliberately standalone and standard-library only.  It accepts
already completed synthetic or caller-supplied draws, performs the frozen
causal slicing, and applies exact rational arithmetic end to end.  It does not
load a database, read a result artifact, run a replay, consult a clock, or use
randomness.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction
from itertools import combinations, pairwise
from typing import cast

METHOD_ID = "BMSGV1_L2_PAIRWISE_a9bf271fe5419f15"
DESIGN_NAME = "B649_PAIRWISE_TRANSITION_MARKOV_GRAPH_PAGERANK_TRAVERSAL_WEIGHTED_SCORE_100_V1"
SEMANTIC_SIGNATURE = "77a875147dc4f0520dcfb4e1929df20aa3bfde638cd01d9860764ed53fb4cc1b"

NUMBER_DOMAIN: tuple[int, ...] = tuple(range(1, 50))
MINIMUM_HISTORY = 751
TRANSITION_DRAW_COUNT = 101
TRANSITION_COUNT = 100
GRAPH_DRAW_COUNT = 100
PAGERANK_DAMPING = Fraction(17, 20)

type Draw = tuple[int, ...]
type FractionVector = tuple[Fraction, ...]
type FractionMatrix = tuple[FractionVector, ...]
type IntMatrix = tuple[tuple[int, ...], ...]


@dataclass(frozen=True, slots=True)
class CausalWindows:
    """The exact frozen causal slices derived from a validated history."""

    transition_draws: tuple[Draw, ...]
    graph_draws: tuple[Draw, ...]
    anchor: Draw


@dataclass(frozen=True, slots=True)
class TransitionModel:
    """Exact directed transition counts and row-stochastic kernel."""

    origin_counts: tuple[int, ...]
    pair_counts: IntMatrix
    kernel: FractionMatrix


@dataclass(frozen=True, slots=True)
class WeightedCodrawGraph:
    """Frozen undirected weighted co-draw graph and random-walk kernel."""

    weights: IntMatrix
    strengths: tuple[int, ...]
    kernel: FractionMatrix


@dataclass(frozen=True, slots=True)
class GraphStepScores:
    """All exact graph-component values recomputed at one traversal step."""

    local_graph_exposure: Mapping[int, Fraction]
    graph_scores: Mapping[int, Fraction]
    normalized_ranks: Mapping[int, Fraction]


@dataclass(frozen=True, slots=True)
class BigLottoPairwiseCandidatePrediction:
    """Complete deterministic research result for the frozen candidate."""

    transition_scores: Mapping[int, Fraction]
    transition_normalized_ranks: Mapping[int, Fraction]
    pagerank_scores: Mapping[int, Fraction]
    traversal_order: tuple[int, ...]
    selected_step_priorities: tuple[Fraction, ...]
    ticket: tuple[int, ...]


def _validate_draw(draw: object, *, label: str) -> Draw:
    if isinstance(draw, (str, bytes, bytearray)) or not isinstance(draw, Sequence):
        raise ValueError(f"{label} must be a finite ordered sequence of six integers")
    draw_values = cast(Sequence[object], draw)
    if len(draw_values) != 6:
        raise ValueError(f"{label} must contain exactly six values")

    numbers: list[int] = []
    for value in draw_values:
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"{label} values must be non-boolean base-10 integers")
        if not 1 <= value <= 49:
            raise ValueError(f"{label} values must lie in 1..49")
        numbers.append(value)
    if len(set(numbers)) != 6:
        raise ValueError(f"{label} values must be distinct")
    return tuple(sorted(numbers))


def validate_history(history: object) -> tuple[Draw, ...]:
    """Validate every supplied draw and preserve chronological sequence order.

    Validation intentionally finishes before the minimum-history fallback is
    considered.  A malformed short history therefore raises ``ValueError``.
    """

    if isinstance(history, (str, bytes, bytearray)) or not isinstance(history, Sequence):
        raise ValueError("history must be a finite ordered sequence of draws")
    history_draws = cast(Sequence[object], history)
    return tuple(
        _validate_draw(draw, label=f"history[{index}]") for index, draw in enumerate(history_draws)
    )


def extract_causal_windows(history: object) -> CausalWindows | None:
    """Return the frozen last-101/last-100/anchor slices, or no result below 751."""

    draws = validate_history(history)
    if len(draws) < MINIMUM_HISTORY:
        return None
    return CausalWindows(
        transition_draws=draws[-TRANSITION_DRAW_COUNT:],
        graph_draws=draws[-GRAPH_DRAW_COUNT:],
        anchor=draws[-1],
    )


def _build_transition_model_from_validated(
    transition_draws: tuple[Draw, ...],
) -> TransitionModel:
    origin_counts = [0] * len(NUMBER_DOMAIN)
    pair_counts = [[0] * len(NUMBER_DOMAIN) for _ in NUMBER_DOMAIN]

    for origin_draw, destination_draw in pairwise(transition_draws):
        for origin in origin_draw:
            origin_index = origin - 1
            origin_counts[origin_index] += 1
            for destination in destination_draw:
                pair_counts[origin_index][destination - 1] += 1

    uniform_row_value = Fraction(1, len(NUMBER_DOMAIN))
    kernel_rows: list[FractionVector] = []
    for origin_index in range(len(NUMBER_DOMAIN)):
        origin_count = origin_counts[origin_index]
        if origin_count == 0:
            kernel_rows.append(tuple(uniform_row_value for _ in NUMBER_DOMAIN))
        else:
            denominator = 6 * origin_count
            kernel_rows.append(
                tuple(
                    Fraction(pair_counts[origin_index][destination_index], denominator)
                    for destination_index in range(len(NUMBER_DOMAIN))
                )
            )

    return TransitionModel(
        origin_counts=tuple(origin_counts),
        pair_counts=tuple(tuple(row) for row in pair_counts),
        kernel=tuple(kernel_rows),
    )


def build_transition_model(transition_draws: object) -> TransitionModel:
    """Build exactly 100 adjacent transitions from exactly 101 validated draws."""

    draws = validate_history(transition_draws)
    if len(draws) != TRANSITION_DRAW_COUNT:
        raise ValueError("transition_draws must contain exactly 101 draws")
    return _build_transition_model_from_validated(draws)


def score_transition_model(model: TransitionModel, anchor: object) -> dict[int, Fraction]:
    """Apply the frozen equal-weight anchor mixture to a transition kernel."""

    anchor_draw = _validate_draw(anchor, label="anchor")
    anchor_weight = Fraction(1, 6)
    return {
        number: anchor_weight
        * sum(
            (model.kernel[anchor_number - 1][number - 1] for anchor_number in anchor_draw),
            start=Fraction(0),
        )
        for number in NUMBER_DOMAIN
    }


def _build_weighted_codraw_graph_from_validated(
    graph_draws: tuple[Draw, ...],
) -> WeightedCodrawGraph:
    weights = [[0] * len(NUMBER_DOMAIN) for _ in NUMBER_DOMAIN]
    for draw in graph_draws:
        for first, second in combinations(draw, 2):
            first_index = first - 1
            second_index = second - 1
            weights[first_index][second_index] += 1
            weights[second_index][first_index] += 1

    strengths = [sum(row) for row in weights]
    uniform_row_value = Fraction(1, len(NUMBER_DOMAIN))
    kernel_rows: list[FractionVector] = []
    for origin_index in range(len(NUMBER_DOMAIN)):
        strength = strengths[origin_index]
        if strength == 0:
            kernel_rows.append(tuple(uniform_row_value for _ in NUMBER_DOMAIN))
        else:
            kernel_rows.append(
                tuple(
                    Fraction(weights[origin_index][destination_index], strength)
                    for destination_index in range(len(NUMBER_DOMAIN))
                )
            )

    return WeightedCodrawGraph(
        weights=tuple(tuple(row) for row in weights),
        strengths=tuple(strengths),
        kernel=tuple(kernel_rows),
    )


def build_weighted_codraw_graph(graph_draws: object) -> WeightedCodrawGraph:
    """Build the exact 49-node weighted graph from exactly 100 validated draws."""

    draws = validate_history(graph_draws)
    if len(draws) != GRAPH_DRAW_COUNT:
        raise ValueError("graph_draws must contain exactly 100 draws")
    return _build_weighted_codraw_graph_from_validated(draws)


def _coerce_stochastic_kernel(kernel: object) -> FractionMatrix:
    if isinstance(kernel, (str, bytes, bytearray)) or not isinstance(kernel, Sequence):
        raise ValueError("kernel must be a finite square sequence")
    kernel_rows = cast(Sequence[object], kernel)
    size = len(kernel_rows)
    if size == 0:
        raise ValueError("kernel must be non-empty")

    rows: list[FractionVector] = []
    for row_index, row in enumerate(kernel_rows):
        if isinstance(row, (str, bytes, bytearray)) or not isinstance(row, Sequence):
            raise ValueError(f"kernel row {row_index} must be a finite sequence")
        row_values = cast(Sequence[object], row)
        if len(row_values) != size:
            raise ValueError("kernel must be square")
        fractions: list[Fraction] = []
        for value in row_values:
            if isinstance(value, bool) or not isinstance(value, (int, Fraction)):
                raise ValueError("kernel entries must be exact integers or Fractions")
            fraction = Fraction(value)
            if fraction < 0:
                raise ValueError("kernel entries must be non-negative")
            fractions.append(fraction)
        if sum(fractions, start=Fraction(0)) != 1:
            raise ValueError("every kernel row must sum exactly to one")
        rows.append(tuple(fractions))
    return tuple(rows)


def _solve_fraction_linear_system(matrix: FractionMatrix, vector: FractionVector) -> FractionVector:
    size = len(vector)
    if len(matrix) != size or any(len(row) != size for row in matrix):
        raise ValueError("linear system matrix must be square and match the vector")

    augmented = [[*matrix[row], vector[row]] for row in range(size)]
    for column in range(size):
        pivot_row = next(
            (row for row in range(column, size) if augmented[row][column] != 0),
            None,
        )
        if pivot_row is None:
            raise ValueError("linear system is singular")
        if pivot_row != column:
            augmented[column], augmented[pivot_row] = (
                augmented[pivot_row],
                augmented[column],
            )

        pivot = augmented[column][column]
        for row in range(column + 1, size):
            entry = augmented[row][column]
            if entry == 0:
                continue
            factor = entry / pivot
            augmented[row][column] = Fraction(0)
            for position in range(column + 1, size + 1):
                augmented[row][position] -= factor * augmented[column][position]

    solution = [Fraction(0)] * size
    for row in range(size - 1, -1, -1):
        known = sum(
            (augmented[row][column] * solution[column] for column in range(row + 1, size)),
            start=Fraction(0),
        )
        solution[row] = (augmented[row][size] - known) / augmented[row][row]
    return tuple(solution)


def solve_exact_pagerank(kernel: object, *, damping: object = PAGERANK_DAMPING) -> FractionVector:
    """Solve exact PageRank for a finite row-stochastic rational kernel.

    The helper is dimension-generic so small independently solvable graphs can
    verify the same equation.  The candidate itself always supplies the frozen
    49-by-49 graph kernel.
    """

    if not isinstance(damping, Fraction) or not 0 < damping < 1:
        raise ValueError("damping must be an exact Fraction strictly between zero and one")
    exact_damping = damping
    rows = _coerce_stochastic_kernel(kernel)
    size = len(rows)
    identity = Fraction(1)
    zero = Fraction(0)
    matrix: FractionMatrix = tuple(
        tuple(
            (identity if equation_index == variable_index else zero)
            - exact_damping * rows[variable_index][equation_index]
            for variable_index in range(size)
        )
        for equation_index in range(size)
    )
    teleport = (1 - exact_damping) * Fraction(1, size)
    solution = _solve_fraction_linear_system(matrix, tuple(teleport for _ in range(size)))

    stationary = tuple(
        teleport
        + exact_damping
        * sum(
            (solution[origin] * rows[origin][destination] for origin in range(size)),
            start=Fraction(0),
        )
        for destination in range(size)
    )
    if solution != stationary or sum(solution, start=Fraction(0)) != 1:
        raise ArithmeticError("exact PageRank solution failed stationarity or normalization")
    if any(value <= 0 for value in solution):
        raise ArithmeticError("uniform teleportation must produce positive PageRank values")
    return solution


def _total_fraction_map(values: Mapping[int, object], *, label: str) -> dict[int, Fraction]:
    if len(values) != len(NUMBER_DOMAIN) or any(number not in values for number in NUMBER_DOMAIN):
        raise ValueError(f"{label} must define every number in 1..49 exactly once")
    result: dict[int, Fraction] = {}
    for number in NUMBER_DOMAIN:
        value = values[number]
        if not isinstance(value, Fraction):
            raise ValueError(f"{label} values must be exact Fractions")
        result[number] = value
    return result


def _normalized_ranks_from_order(order: Sequence[int]) -> dict[int, Fraction]:
    if len(order) != len(NUMBER_DOMAIN) or tuple(sorted(order)) != NUMBER_DOMAIN:
        raise ValueError("rank order must be a permutation of 1..49")
    denominator = len(NUMBER_DOMAIN) - 1
    return {
        number: Fraction(len(NUMBER_DOMAIN) - position, denominator)
        for position, number in enumerate(order, start=1)
    }


def rank_transition_scores(scores: Mapping[int, Fraction]) -> dict[int, Fraction]:
    """Apply the frozen transition score-descending, number-ascending order."""

    exact_scores = _total_fraction_map(scores, label="transition scores")
    order = sorted(NUMBER_DOMAIN, key=lambda number: (-exact_scores[number], number))
    return _normalized_ranks_from_order(order)


def rank_graph_scores(
    graph_scores: Mapping[int, Fraction],
    pagerank_scores: Mapping[int, Fraction],
    local_graph_exposure: Mapping[int, Fraction],
) -> dict[int, Fraction]:
    """Apply the complete frozen graph-component ordering chain."""

    exact_graph = _total_fraction_map(graph_scores, label="graph scores")
    exact_pagerank = _total_fraction_map(pagerank_scores, label="PageRank scores")
    exact_local = _total_fraction_map(local_graph_exposure, label="local graph exposure")
    order = sorted(
        NUMBER_DOMAIN,
        key=lambda number: (
            -exact_graph[number],
            -exact_pagerank[number],
            -exact_local[number],
            number,
        ),
    )
    return _normalized_ranks_from_order(order)


def fuse_rank_scores(
    transition_ranks: Mapping[int, Fraction], graph_ranks: Mapping[int, Fraction]
) -> dict[int, Fraction]:
    """Apply the exact symmetric Level-2 rank fusion."""

    exact_transition = _total_fraction_map(transition_ranks, label="transition ranks")
    exact_graph = _total_fraction_map(graph_ranks, label="graph ranks")
    half = Fraction(1, 2)
    return {
        number: half * exact_transition[number] + half * exact_graph[number]
        for number in NUMBER_DOMAIN
    }


def _validate_context(context: object) -> tuple[int, ...]:
    if isinstance(context, (str, bytes, bytearray)) or not isinstance(context, Sequence):
        raise ValueError("context must be a finite sequence of unique numbers")
    context_values = cast(Sequence[object], context)
    values: list[int] = []
    for value in context_values:
        if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 49:
            raise ValueError("context values must be non-boolean integers in 1..49")
        values.append(value)
    if not values or len(set(values)) != len(values):
        raise ValueError("context must be non-empty and contain unique numbers")
    return tuple(sorted(values))


def score_graph_step(
    graph: WeightedCodrawGraph,
    pagerank_scores: Mapping[int, Fraction],
    context: object,
) -> GraphStepScores:
    """Recompute exposure, graph score, and all-49 graph ranks for one context."""

    exact_pagerank = _total_fraction_map(pagerank_scores, label="PageRank scores")
    context_numbers = _validate_context(context)
    context_weight = Fraction(1, len(context_numbers))
    local = {
        number: context_weight
        * sum(
            (graph.kernel[origin - 1][number - 1] for origin in context_numbers),
            start=Fraction(0),
        )
        for number in NUMBER_DOMAIN
    }
    half = Fraction(1, 2)
    graph_scores = {
        number: half * exact_pagerank[number] + half * local[number] for number in NUMBER_DOMAIN
    }
    normalized = rank_graph_scores(graph_scores, exact_pagerank, local)
    return GraphStepScores(local, graph_scores, normalized)


def _select_next_number_unchecked(
    selected: Sequence[int],
    fused_priorities: Mapping[int, Fraction],
    graph_ranks: Mapping[int, Fraction],
    pagerank_scores: Mapping[int, Fraction],
    local_graph_exposure: Mapping[int, Fraction],
    transition_ranks: Mapping[int, Fraction],
    transition_scores: Mapping[int, Fraction],
) -> int:
    eligible = [number for number in NUMBER_DOMAIN if number not in selected]
    if not eligible:
        raise ValueError("no eligible numbers remain")
    return min(
        eligible,
        key=lambda number: (
            -fused_priorities[number],
            -graph_ranks[number],
            -pagerank_scores[number],
            -local_graph_exposure[number],
            -transition_ranks[number],
            -transition_scores[number],
            number,
        ),
    )


def select_next_number(
    selected: Sequence[int],
    fused_priorities: Mapping[int, Fraction],
    graph_ranks: Mapping[int, Fraction],
    pagerank_scores: Mapping[int, Fraction],
    local_graph_exposure: Mapping[int, Fraction],
    transition_ranks: Mapping[int, Fraction],
    transition_scores: Mapping[int, Fraction],
) -> int:
    """Select one eligible number with the complete frozen traversal tie chain."""

    selected_values = tuple(selected)
    if len(set(selected_values)) != len(selected_values) or any(
        number not in NUMBER_DOMAIN for number in selected_values
    ):
        raise ValueError("selected must contain unique numbers in 1..49")
    exact_fused = _total_fraction_map(fused_priorities, label="fused priorities")
    exact_graph_ranks = _total_fraction_map(graph_ranks, label="graph ranks")
    exact_pagerank = _total_fraction_map(pagerank_scores, label="PageRank scores")
    exact_local = _total_fraction_map(local_graph_exposure, label="local graph exposure")
    exact_transition_ranks = _total_fraction_map(transition_ranks, label="transition ranks")
    exact_transition_scores = _total_fraction_map(transition_scores, label="transition scores")
    return _select_next_number_unchecked(
        selected_values,
        exact_fused,
        exact_graph_ranks,
        exact_pagerank,
        exact_local,
        exact_transition_ranks,
        exact_transition_scores,
    )


def deterministic_graph_traversal(
    *,
    anchor: object,
    transition_scores: Mapping[int, Fraction],
    transition_ranks: Mapping[int, Fraction],
    graph: WeightedCodrawGraph,
    pagerank_scores: Mapping[int, Fraction],
) -> tuple[tuple[int, ...], tuple[Fraction, ...]]:
    """Generate the frozen 49-step adaptive traversal and selected priorities."""

    anchor_draw = _validate_draw(anchor, label="anchor")
    exact_transition_scores = _total_fraction_map(transition_scores, label="transition scores")
    exact_transition_ranks = _total_fraction_map(transition_ranks, label="transition ranks")
    exact_pagerank = _total_fraction_map(pagerank_scores, label="PageRank scores")

    selected: list[int] = []
    selected_priorities: list[Fraction] = []
    for _step in range(len(NUMBER_DOMAIN)):
        context = tuple(
            number for number in NUMBER_DOMAIN if number in anchor_draw or number in selected
        )
        graph_step = score_graph_step(graph, exact_pagerank, context)
        fused = fuse_rank_scores(exact_transition_ranks, graph_step.normalized_ranks)
        choice = _select_next_number_unchecked(
            selected,
            fused,
            graph_step.normalized_ranks,
            exact_pagerank,
            graph_step.local_graph_exposure,
            exact_transition_ranks,
            exact_transition_scores,
        )
        selected.append(choice)
        selected_priorities.append(fused[choice])

    return tuple(selected), tuple(selected_priorities)


def predict_biglotto_l2_pairwise_transition_markov_graph_pagerank_traversal_weighted_score_100(
    history: object,
) -> BigLottoPairwiseCandidatePrediction | None:
    """Run the exact frozen research candidate on completed draws only."""

    windows = extract_causal_windows(history)
    if windows is None:
        return None

    transition_model = _build_transition_model_from_validated(windows.transition_draws)
    transition_scores = score_transition_model(transition_model, windows.anchor)
    transition_ranks = rank_transition_scores(transition_scores)

    graph = _build_weighted_codraw_graph_from_validated(windows.graph_draws)
    pagerank_vector = solve_exact_pagerank(graph.kernel)
    pagerank_scores = {number: pagerank_vector[number - 1] for number in NUMBER_DOMAIN}
    traversal_order, selected_priorities = deterministic_graph_traversal(
        anchor=windows.anchor,
        transition_scores=transition_scores,
        transition_ranks=transition_ranks,
        graph=graph,
        pagerank_scores=pagerank_scores,
    )
    ticket = tuple(sorted(traversal_order[:6]))
    return BigLottoPairwiseCandidatePrediction(
        transition_scores=transition_scores,
        transition_normalized_ranks=transition_ranks,
        pagerank_scores=pagerank_scores,
        traversal_order=traversal_order,
        selected_step_priorities=selected_priorities,
        ticket=ticket,
    )


def _fraction_payload(value: Fraction) -> list[int]:
    return [value.numerator, value.denominator]


def canonical_serialize_prediction(
    prediction: BigLottoPairwiseCandidatePrediction | None,
) -> bytes:
    """Serialize a result deterministically without converting any rational to float."""

    if prediction is None:
        return b"null"
    payload = {
        "method_id": METHOD_ID,
        "design_name": DESIGN_NAME,
        "semantic_signature": SEMANTIC_SIGNATURE,
        "transition_scores": [
            [number, *_fraction_payload(prediction.transition_scores[number])]
            for number in NUMBER_DOMAIN
        ],
        "transition_normalized_ranks": [
            [number, *_fraction_payload(prediction.transition_normalized_ranks[number])]
            for number in NUMBER_DOMAIN
        ],
        "pagerank_scores": [
            [number, *_fraction_payload(prediction.pagerank_scores[number])]
            for number in NUMBER_DOMAIN
        ],
        "traversal_order": list(prediction.traversal_order),
        "selected_step_priorities": [
            _fraction_payload(value) for value in prediction.selected_step_priorities
        ],
        "ticket": list(prediction.ticket),
    }
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
