"""Structural upper bounds for the final unresolved K10 multiplicity profile.

The only structures modeled here have ten ticket vertices, four size-three
repeated-label supports, and three size-two repeated-label supports. The
remaining 42 incidences are singletons, assigned privately to fill each ticket
to size six. Singleton identities do not enter any intersection count.
"""

from __future__ import annotations

import argparse
import itertools
import json
import math
import time
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from functools import cache
from math import comb
from typing import Any, cast

from lottolab.research.b649_k10_overlap_mass12_bonferroni_screen_r1 import (
    _joint_count_from_regions,  # pyright: ignore[reportPrivateUsage]
    _joint_event_count,  # pyright: ignore[reportPrivateUsage]
)

TASK_ID = "B649_K10_PROFILE_42_3_4_EXACT_CLOSURE_R1"
TICKET_COUNT = 10
TICKET_SIZE = 6
POOL_SIZE = 49
DRAW_SIZE = 6
OUTRIGHT_MATCHES = 3
DOUBLE_LABEL_COUNT = 3
TRIPLE_LABEL_COUNT = 4
REPEATED_LABEL_COUNT = DOUBLE_LABEL_COUNT + TRIPLE_LABEL_COUNT
OVERLAP_MASS = DOUBLE_LABEL_COUNT + 3 * TRIPLE_LABEL_COUNT
INCUMBENT_OUTCOME_COUNT = 176_345_645
PREVIOUS_PROFILE_BOUND = 182_166_320
SINGLE_TICKET_OUTCOME_COUNT = 18_611_432
S1 = TICKET_COUNT * SINGLE_TICKET_OUTCOME_COUNT
MAX_SIMULTANEOUS_WINNERS = 6

Vertex = int
Support = tuple[Vertex, ...]


@dataclass(frozen=True)
class CollisionBound:
    """Exact pair-event lower bound for a fixed number of occupied pairs."""

    occupied_pairs: int
    pair_intersection_lower_bound: int
    outcome_upper_bound: int


@dataclass(frozen=True)
class LinearCoreBound:
    """Third-order Bonferroni bound for all pair-linear target structures."""

    pair_intersection_sum: int
    triple_intersection_counts: tuple[int, int, int, int, int]
    wedge_upper_bound: int
    graph_triangle_upper_bound: int
    triple_intersection_sum_upper_bound: int
    outcome_upper_bound: int


@dataclass(frozen=True)
class CollisionSolverBound:
    """Certified bound for non-linear structures with at least four pairs."""

    solver_status: str
    objective_incumbent: int | None
    raw_objective_upper_bound: float | None
    certified_outcome_upper_bound: int | None
    elapsed_seconds: float
    time_limit_seconds: float
    num_search_workers: int
    occupied_pair_count: int | None
    pair_intersection_sum: int | None
    third_order_union_bound: int | None
    second_moment_union_bound: int | None


def _ticket_mask(numbers: range) -> int:
    return sum(1 << number for number in numbers)


@cache
def pair_event_counts(
    pool_size: int = POOL_SIZE,
    draw_size: int = DRAW_SIZE,
    outright_matches: int = OUTRIGHT_MATCHES,
) -> tuple[int, ...]:
    """Exact pair-event counts indexed by ticket intersection size 0..d-1."""

    if not 1 <= outright_matches <= draw_size < pool_size:
        raise ValueError("invalid lottery parameters")
    left = _ticket_mask(range(draw_size))
    result: list[int] = []
    for shared in range(draw_size):
        right = _ticket_mask(range(shared)) | _ticket_mask(
            range(draw_size, 2 * draw_size - shared)
        )
        result.append(
            _joint_event_count(
                (left, right),
                pool_size=pool_size,
                draw_size=draw_size,
                outright_matches=outright_matches,
            )
        )
    return tuple(result)


def pair_overlap_multiplicities(
    repeated_label_supports: Sequence[Sequence[int]],
) -> tuple[int, ...]:
    """Return the 45 ticket-pair overlap multiplicities in vertex order."""

    if len(repeated_label_supports) != REPEATED_LABEL_COUNT:
        raise ValueError("the target profile must have seven repeated labels")
    sizes = Counter(len(support) for support in repeated_label_supports)
    if sizes != Counter({2: DOUBLE_LABEL_COUNT, 3: TRIPLE_LABEL_COUNT}):
        raise ValueError("the target profile requires three doubles and four triples")

    overlaps: Counter[tuple[int, int]] = Counter()
    for raw_support in repeated_label_supports:
        support = tuple(raw_support)
        if (
            len(set(support)) != len(support)
            or any(type(vertex) is not int or not 0 <= vertex < TICKET_COUNT for vertex in support)
        ):
            raise ValueError(f"invalid repeated-label support: {support}")
        for pair in itertools.combinations(sorted(support), 2):
            overlaps[pair] += 1
    return tuple(
        overlaps[(left, right)]
        for left, right in itertools.combinations(range(TICKET_COUNT), 2)
    )


def exact_pair_intersection_sum(pair_multiplicities: Sequence[int]) -> int:
    """Compute S2 from the exact official pair-event table."""

    expected_pairs = comb(TICKET_COUNT, 2)
    if len(pair_multiplicities) != expected_pairs:
        raise ValueError("a K10 pair-multiplicity vector must have 45 entries")
    counts = pair_event_counts()
    if any(type(value) is not int or not 0 <= value < TICKET_SIZE for value in pair_multiplicities):
        raise ValueError("ticket pairs must intersect in 0..5 labels")
    return sum(counts[value] for value in pair_multiplicities)


def _balanced_pair_multiplicities(occupied_pairs: int) -> tuple[int, ...]:
    if not 3 <= occupied_pairs <= OVERLAP_MASS:
        raise ValueError("15 overlap incidences occupy between 3 and 15 pairs")
    base, remainder = divmod(OVERLAP_MASS, occupied_pairs)
    positive = [base + 1] * remainder + [base] * (occupied_pairs - remainder)
    if max(positive) > TICKET_SIZE - 1:
        raise ValueError("the pair multiplicity exceeds the distinct-ticket limit")
    return tuple(positive + [0] * (comb(TICKET_COUNT, 2) - occupied_pairs))


@cache
def collision_bound_rows() -> tuple[CollisionBound, ...]:
    """Return convexity bounds for each possible occupied-pair count."""

    counts = pair_event_counts()
    increments = tuple(counts[index + 1] - counts[index] for index in range(5))
    if any(left > right for left, right in itertools.pairwise(increments)):
        raise AssertionError("exact pair-event counts must be discretely convex")

    rows: list[CollisionBound] = []
    for occupied in range(3, OVERLAP_MASS + 1):
        minimum_s2 = exact_pair_intersection_sum(_balanced_pair_multiplicities(occupied))
        moment_bound = (
            MAX_SIMULTANEOUS_WINNERS * S1 - 2 * minimum_s2
        ) // MAX_SIMULTANEOUS_WINNERS
        rows.append(CollisionBound(occupied, minimum_s2, moment_bound))
    return tuple(rows)


def _triple_event_count(
    ab: int,
    ac: int,
    bc: int,
    triple_shared: int,
) -> int:
    """Exact intersection count for three tickets from their Venn regions."""

    regions = (
        TICKET_SIZE - ab - ac + triple_shared,
        TICKET_SIZE - ab - bc + triple_shared,
        ab - triple_shared,
        TICKET_SIZE - ac - bc + triple_shared,
        ac - triple_shared,
        bc - triple_shared,
        triple_shared,
    )
    if min(regions) < 0:
        raise ValueError("ticket overlaps do not define nonnegative Venn regions")
    return _joint_count_from_regions(
        regions,
        3,
        POOL_SIZE,
        DRAW_SIZE,
        OUTRIGHT_MATCHES,
    )


@cache
def _triple_event_table() -> tuple[tuple[int, int, int, int, int], ...]:
    """Exact local table for three ticket pairs and their common labels."""

    rows: list[tuple[int, int, int, int, int]] = []
    for ab in range(TICKET_SIZE):
        for ac in range(TICKET_SIZE):
            for bc in range(TICKET_SIZE):
                for common in range(min(ab, ac, bc) + 1):
                    try:
                        events = _triple_event_count(ab, ac, bc, common)
                    except ValueError:
                        continue
                    rows.append((ab, ac, bc, common, events))
    return tuple(rows)


@cache
def linear_core_bound() -> LinearCoreBound:
    """Bound S3 over all pair-linear structures without a class census.

    The overlap graph has 15 edges. Each graph edge lies in eight vertex
    triples. If W is its number of wedges and Q its number of graph triangles,
    the counts of 3-sets inducing 0, 1, 2, or 3 overlap edges are respectively
    W-Q, 120-2W+3Q, W-3Q, and Q. Four marked triangles represent the four
    repeated labels of multiplicity three and replace the unmarked triangle
    intersection count by their exact common-label count.
    """

    pair_counts = pair_event_counts()
    pair_s2 = 30 * pair_counts[0] + OVERLAP_MASS * pair_counts[1]
    triple_counts = (
        _triple_event_count(0, 0, 0, 0),
        _triple_event_count(1, 0, 0, 0),
        _triple_event_count(1, 1, 0, 0),
        _triple_event_count(1, 1, 1, 0),
        _triple_event_count(1, 1, 1, 1),
    )
    j0, j1, j2, j3, marked = triple_counts
    wedge_coefficient = j0 - 2 * j1 + j2
    triangle_coefficient = -j0 + 3 * j1 - 3 * j2 + j3
    constant = 120 * j1 + TRIPLE_LABEL_COUNT * (marked - j3)

    # W = sum_v C(deg(v),2); deg(v) <= 9 and sum_v deg(v) = 30.
    wedge_upper = ((TICKET_COUNT - 2) // 2) * 2 * OVERLAP_MASS
    triangle_lower = TRIPLE_LABEL_COUNT
    triangle_upper = comb(TICKET_COUNT, 3)
    wedge_term = wedge_coefficient * (wedge_upper if wedge_coefficient >= 0 else 0)
    triangle_term = triangle_coefficient * (
        triangle_upper if triangle_coefficient >= 0 else triangle_lower
    )
    s3_upper = constant + wedge_term + triangle_term
    outcome_upper = S1 - pair_s2 + s3_upper
    return LinearCoreBound(
        pair_intersection_sum=pair_s2,
        triple_intersection_counts=triple_counts,
        wedge_upper_bound=wedge_upper,
        graph_triangle_upper_bound=triangle_upper,
        triple_intersection_sum_upper_bound=s3_upper,
        outcome_upper_bound=outcome_upper,
    )


def materialize_profile_hypergraph(
    repeated_label_supports: Sequence[Sequence[int]],
) -> tuple[tuple[int, ...], ...]:
    """Assign seven repeated labels and 42 private labels to ten tickets."""

    normalized = tuple(tuple(sorted(support)) for support in repeated_label_supports)
    pair_overlap_multiplicities(normalized)
    degrees = [0] * TICKET_COUNT
    for support in normalized:
        for vertex in support:
            degrees[vertex] += 1
    if any(degree > TICKET_SIZE for degree in degrees):
        raise ValueError("a ticket has more than six repeated-label incidences")

    tickets: list[list[int]] = [[] for _ in range(TICKET_COUNT)]
    for label, support in enumerate(normalized, start=1):
        for vertex in support:
            tickets[vertex].append(label)

    next_label = REPEATED_LABEL_COUNT + 1
    for ticket in tickets:
        for _ in range(TICKET_SIZE - len(ticket)):
            ticket.append(next_label)
            next_label += 1
    if next_label != POOL_SIZE + 1:
        raise AssertionError("the repeated supports must leave exactly 42 singleton labels")

    portfolio = tuple(tuple(sorted(ticket)) for ticket in tickets)
    if (
        len(set(portfolio)) != TICKET_COUNT
        or any(
            len(ticket) != TICKET_SIZE or len(set(ticket)) != TICKET_SIZE
            for ticket in portfolio
        )
    ):
        raise ValueError("materialized tickets must be distinct six-label sets")
    multiplicities = Counter(
        sum(label in ticket for ticket in portfolio) for label in range(1, POOL_SIZE + 1)
    )
    if multiplicities != Counter({1: 42, 2: DOUBLE_LABEL_COUNT, 3: TRIPLE_LABEL_COUNT}):
        raise AssertionError("materialization did not preserve the target profile")
    return portfolio


def _s2_and_s3_for_supports(
    repeated_label_supports: Sequence[Sequence[int]],
) -> tuple[int, int]:
    pair_overlaps = pair_overlap_multiplicities(repeated_label_supports)
    s2 = exact_pair_intersection_sum(pair_overlaps)
    pair_map = {
        pair: pair_overlaps[index]
        for index, pair in enumerate(itertools.combinations(range(TICKET_COUNT), 2))
    }
    triple_counts = Counter(
        tuple(sorted(support))
        for support in repeated_label_supports
        if len(support) == 3
    )
    s3 = 0
    for a, b, c in itertools.combinations(range(TICKET_COUNT), 3):
        s3 += _triple_event_count(
            pair_map[(a, b)],
            pair_map[(a, c)],
            pair_map[(b, c)],
            triple_counts[(a, b, c)],
        )
    return s2, s3


def maximize_collision_u3_bound(*, time_limit_seconds: float = 120.0) -> CollisionSolverBound:
    """Optimize min(U2,U3) over only non-linear structures with >=4 pairs.

    Variables are repeated-label supports on ten ticket vertices. The model
    includes exactly three size-two and four size-three supports, ticket
    repeated-degree at most six, distinct tickets (pair overlap at most five),
    and at least one collision among at least four occupied ticket pairs.
    """

    if not math.isfinite(time_limit_seconds) or time_limit_seconds <= 0:
        raise ValueError("time limit must be finite and positive")

    from ortools.sat.python import cp_model

    cp_model_api = cast(Any, cp_model)
    model: Any = cp_model_api.CpModel()
    vertices = range(TICKET_COUNT)
    pairs = tuple(itertools.combinations(vertices, 2))
    triples = tuple(itertools.combinations(vertices, 3))
    pair_labels = {
        pair: model.NewIntVar(0, DOUBLE_LABEL_COUNT, f"double_{pair[0]}_{pair[1]}")
        for pair in pairs
    }
    triple_labels = {
        triple: model.NewIntVar(
            0,
            TRIPLE_LABEL_COUNT,
            f"triple_{triple[0]}_{triple[1]}_{triple[2]}",
        )
        for triple in triples
    }
    model.Add(sum(pair_labels.values()) == DOUBLE_LABEL_COUNT)
    model.Add(sum(triple_labels.values()) == TRIPLE_LABEL_COUNT)

    vertex_degrees: list[Any] = []
    for vertex in vertices:
        degree = model.NewIntVar(0, TICKET_SIZE, f"repeated_degree_{vertex}")
        model.Add(
            degree
            == sum(value for pair, value in pair_labels.items() if vertex in pair)
            + sum(value for triple, value in triple_labels.items() if vertex in triple)
        )
        vertex_degrees.append(degree)
    # Every isomorphism class has a representative with sorted vertex degrees.
    for vertex in range(TICKET_COUNT - 1):
        model.Add(vertex_degrees[vertex] >= vertex_degrees[vertex + 1])

    pair_overlaps: dict[tuple[int, int], Any] = {}
    pair_events: list[Any] = []
    occupied_pair_flags: list[Any] = []
    collision_flags: list[Any] = []
    pair_counts = pair_event_counts()
    for left, right in pairs:
        overlap = model.NewIntVar(0, TICKET_SIZE - 1, f"overlap_{left}_{right}")
        model.Add(
            overlap
            == pair_labels[(left, right)]
            + sum(
                value
                for triple, value in triple_labels.items()
                if left in triple and right in triple
            )
        )
        pair_overlaps[(left, right)] = overlap

        occupied = model.NewBoolVar(f"occupied_{left}_{right}")
        model.Add(overlap >= 1).OnlyEnforceIf(occupied)
        model.Add(overlap == 0).OnlyEnforceIf(occupied.Not())
        occupied_pair_flags.append(occupied)

        collision = model.NewBoolVar(f"collision_{left}_{right}")
        model.Add(overlap >= 2).OnlyEnforceIf(collision)
        model.Add(overlap <= 1).OnlyEnforceIf(collision.Not())
        collision_flags.append(collision)

        pair_event = model.NewIntVar(0, pair_counts[-1], f"pair_event_{left}_{right}")
        model.AddElement(overlap, list(pair_counts), pair_event)
        pair_events.append(pair_event)

    model.Add(sum(occupied_pair_flags) >= 4)
    model.Add(sum(collision_flags) >= 1)

    triple_events: list[Any] = []
    triple_table = list(_triple_event_table())
    for left, middle, right in triples:
        triple_event = model.NewIntVar(
            0,
            SINGLE_TICKET_OUTCOME_COUNT,
            f"triple_event_{left}_{middle}_{right}",
        )
        model.AddAllowedAssignments(
            (
                pair_overlaps[(left, middle)],
                pair_overlaps[(left, right)],
                pair_overlaps[(middle, right)],
                triple_labels[(left, middle, right)],
                triple_event,
            ),
            triple_table,
        )
        triple_events.append(triple_event)

    s2 = sum(pair_events)
    s3 = sum(triple_events)
    coverage_upper = model.NewIntVar(0, S1, "coverage_upper_bound")
    model.Add(coverage_upper <= S1 - s2 + s3)
    model.Add(
        MAX_SIMULTANEOUS_WINNERS * coverage_upper
        <= MAX_SIMULTANEOUS_WINNERS * S1 - 2 * s2
    )
    model.Maximize(coverage_upper)

    solver: Any = cp_model_api.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit_seconds
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = 0
    started = time.monotonic()
    status_code = solver.Solve(model)
    elapsed = time.monotonic() - started
    status = solver.StatusName(status_code)
    if status == "MODEL_INVALID":
        raise RuntimeError("CP-SAT rejected the fixed-profile collision model")

    incumbent: int | None = None
    occupied_count: int | None = None
    s2_incumbent: int | None = None
    u3_incumbent: int | None = None
    if status in {"OPTIMAL", "FEASIBLE"}:
        incumbent = int(solver.Value(coverage_upper))
        supports: list[Support] = []
        for pair in pairs:
            supports.extend([pair] * int(solver.Value(pair_labels[pair])))
        for triple in triples:
            supports.extend([triple] * int(solver.Value(triple_labels[triple])))
        pair_vector = pair_overlap_multiplicities(supports)
        occupied_count = sum(value > 0 for value in pair_vector)
        s2_incumbent, s3_incumbent = _s2_and_s3_for_supports(supports)
        u3_incumbent = S1 - s2_incumbent + s3_incumbent
        u2_incumbent = (
            MAX_SIMULTANEOUS_WINNERS * S1 - 2 * s2_incumbent
        ) // MAX_SIMULTANEOUS_WINNERS
        if incumbent > min(u2_incumbent, u3_incumbent):
            raise AssertionError("solver incumbent exceeds its independently recomputed bounds")

    if status == "INFEASIBLE":
        return CollisionSolverBound(
            status,
            None,
            None,
            0,
            elapsed,
            time_limit_seconds,
            1,
            None,
            None,
            None,
            None,
        )

    raw_bound = float(solver.BestObjectiveBound())
    certified = math.ceil(raw_bound)
    if status == "OPTIMAL" and incumbent is not None:
        certified = incumbent
    return CollisionSolverBound(
        solver_status=status,
        objective_incumbent=incumbent,
        raw_objective_upper_bound=raw_bound,
        certified_outcome_upper_bound=certified,
        elapsed_seconds=elapsed,
        time_limit_seconds=time_limit_seconds,
        num_search_workers=1,
        occupied_pair_count=occupied_count,
        pair_intersection_sum=s2_incumbent,
        third_order_union_bound=u3_incumbent,
        second_moment_union_bound=(
            None
            if s2_incumbent is None
            else (
                MAX_SIMULTANEOUS_WINNERS * S1 - 2 * s2_incumbent
            ) // MAX_SIMULTANEOUS_WINNERS
        ),
    )


def combine_profile_upper_bound(collision_solver_bound: int | None = None) -> int:
    """Combine the closed low-collision, linear, and nonlinear families."""

    rows = collision_bound_rows()
    three_pair_bound = rows[0].outcome_upper_bound
    nonlinear_pair_bound = max(
        row.outcome_upper_bound for row in rows if 4 <= row.occupied_pairs <= 14
    )
    if collision_solver_bound is not None:
        nonlinear_pair_bound = min(nonlinear_pair_bound, collision_solver_bound)
    structural_bound = max(
        three_pair_bound,
        linear_core_bound().outcome_upper_bound,
        nonlinear_pair_bound,
    )
    return min(PREVIOUS_PROFILE_BOUND, structural_bound)


def proof_summary(*, time_limit_seconds: float = 120.0) -> dict[str, object]:
    """Return the packet-scoped profile certificate summary."""

    collisions = collision_bound_rows()
    linear = linear_core_bound()
    collision_solver = maximize_collision_u3_bound(time_limit_seconds=time_limit_seconds)

    # At most three occupied pairs is closed by S2. The linear core is bounded
    # separately. For nonlinear structures, p <= 14; convexity gives the
    # strongest pair-only ceiling at p=14, combined with the solver ceiling.
    collision_upper = collision_solver.certified_outcome_upper_bound
    nonlinear_pair_upper = max(
        row.outcome_upper_bound
        for row in collisions
        if 4 <= row.occupied_pairs <= 14
    )
    nonlinear_combined_upper = (
        nonlinear_pair_upper
        if collision_upper is None
        else min(nonlinear_pair_upper, collision_upper)
    )
    profile_upper = combine_profile_upper_bound(collision_upper)
    if profile_upper < INCUMBENT_OUTCOME_COUNT:
        raise AssertionError("the certified upper bound contradicts the known incumbent")

    status = (
        "CLOSED"
        if profile_upper <= INCUMBENT_OUTCOME_COUNT
        else "OPEN_BOUND_IMPROVED"
        if profile_upper < PREVIOUS_PROFILE_BOUND
        else "OPEN_NO_PROGRESS"
    )
    return {
        "task_id": TASK_ID,
        "task_status": (
            "COMPLETED"
            if status == "CLOSED"
            else "COMPLETED_WITH_UNKNOWN_K10_GLOBAL_OPTIMALITY"
        ),
        "profile": {"singletons": 42, "doubles": 3, "triples": 4, "overlap_mass": OVERLAP_MASS},
        "structural_reduction": {
            "ticket_vertices": TICKET_COUNT,
            "triple_hyperedges": TRIPLE_LABEL_COUNT,
            "ordinary_edges": DOUBLE_LABEL_COUNT,
            "repeated_label_incidence": 18,
            "singleton_labels": 42,
            "ticket_size": TICKET_SIZE,
            "singleton_relabeling_invariant": True,
            "reason": (
                "Singleton labels have a one-ticket support; replacing their identities "
                "is a pool permutation and leaves every exact outcome count unchanged."
            ),
        },
        "incumbent_outcome_count": INCUMBENT_OUTCOME_COUNT,
        "previous_profile_bound": PREVIOUS_PROFILE_BOUND,
        "pair_event_counts_overlap_0_to_5": list(pair_event_counts()),
        "collision_families": [
            {
                "occupied_ticket_pairs": row.occupied_pairs,
                "minimum_exact_S2": row.pair_intersection_lower_bound,
                "second_moment_upper_bound": row.outcome_upper_bound,
                "closed_at_incumbent": row.outcome_upper_bound <= INCUMBENT_OUTCOME_COUNT,
            }
            for row in collisions
        ],
        "linear_core": {
            "pair_intersection_sum_S2": linear.pair_intersection_sum,
            "triple_intersection_counts_k0_k1_k2_k3_marked": list(
                linear.triple_intersection_counts
            ),
            "wedge_upper_bound": linear.wedge_upper_bound,
            "graph_triangle_upper_bound": linear.graph_triangle_upper_bound,
            "third_order_intersection_sum_upper_bound_S3": (
                linear.triple_intersection_sum_upper_bound
            ),
            "union_upper_bound": linear.outcome_upper_bound,
            "closed_at_incumbent": linear.outcome_upper_bound <= INCUMBENT_OUTCOME_COUNT,
        },
        "nonlinear_collision_pair_bound": {
            "occupied_pair_range": [4, 14],
            "minimum_exact_S2": collisions[-2].pair_intersection_lower_bound,
            "second_moment_upper_bound": nonlinear_pair_upper,
            "combined_with_solver_bound": nonlinear_combined_upper,
            "closed_at_incumbent": nonlinear_combined_upper <= INCUMBENT_OUTCOME_COUNT,
        },
        "nonlinear_collision_solver": {
            "structural_domain": (
                "three size-2 and four size-3 supports on ten vertices; repeated "
                "degree <= 6; pair overlap <= 5; at least four occupied pairs; "
                "at least one pair collision"
            ),
            "objective": "maximize min(S1 - S2 + S3, floor(S1 - 2*S2/6))",
            "solver_status": collision_solver.solver_status,
            "objective_incumbent": collision_solver.objective_incumbent,
            "raw_objective_upper_bound": collision_solver.raw_objective_upper_bound,
            "certified_outcome_upper_bound": collision_solver.certified_outcome_upper_bound,
            "elapsed_seconds": collision_solver.elapsed_seconds,
            "time_limit_seconds": collision_solver.time_limit_seconds,
            "num_search_workers": collision_solver.num_search_workers,
            "incumbent_occupied_pairs": collision_solver.occupied_pair_count,
            "incumbent_S2": collision_solver.pair_intersection_sum,
            "incumbent_U3": collision_solver.third_order_union_bound,
            "incumbent_U2": collision_solver.second_moment_union_bound,
        },
        "profile_upper_bound": profile_upper,
        "remaining_gap": profile_upper - INCUMBENT_OUTCOME_COUNT,
        "profile_status": status,
        "global_optimum_status": "PROVEN" if status == "CLOSED" else "UNKNOWN",
        "new_portfolio_search_started": "NO",
        "k20_takeover": "NO",
        "production_mutation": "NONE",
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--time-limit-seconds", type=float, default=120.0)
    arguments = parser.parse_args(argv)
    summary = proof_summary(time_limit_seconds=arguments.time_limit_seconds)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


__all__ = [
    "CollisionBound",
    "CollisionSolverBound",
    "LinearCoreBound",
    "collision_bound_rows",
    "combine_profile_upper_bound",
    "exact_pair_intersection_sum",
    "linear_core_bound",
    "materialize_profile_hypergraph",
    "maximize_collision_u3_bound",
    "pair_event_counts",
    "pair_overlap_multiplicities",
    "proof_summary",
]


if __name__ == "__main__":
    raise SystemExit(main())
