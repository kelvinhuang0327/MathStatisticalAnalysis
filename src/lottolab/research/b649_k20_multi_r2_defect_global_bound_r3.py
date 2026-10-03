"""Structural upper bounds for K20 portfolios with multiple overlap-2 pairs.

This module optimizes only over overlap-graph degree summaries. It neither
constructs tickets nor searches portfolios. The exact three-event profile
ceilings are reused from the preceding heavy-pair analysis.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from functools import cache
from itertools import combinations
from math import comb
from typing import Any

from lottolab.research.b649_k20_heavy_pair_defect_global_bound_r2 import (
    exact_triple_profile_table,
)
from lottolab.research.b649_k20_outside_min_s2_global_penalty_bound_r1 import (
    INCUMBENT,
    PAIR_COUNT,
    PORTFOLIO_S1,
    TICKET_COUNT,
    minimum_pair_overlap_mass,
    pair_intersection_table,
)

BASE_HEAD = "12c4e62ae377b6808eb971bd6dd906bc83987918"
TASK_BRANCH = "codex/b649-k20-multi-r2-defect-global-bound-r3"
EXPECTED_PAIR_COUNTS = (
    107_800,
    574_000,
    1_695_988,
    3_469_942,
    6_224_512,
    10_776_332,
    18_611_432,
)
MINIMUM_OVERLAP_MASS = 93
MAX_MINIMUM_MASS_HEAVY_GRAPH_DEGREE = 6
PARENT_BOUND = 357_906_542
TWO_SHARED_HEAVY_DEGREES = (2, 1, 1) + (0,) * (TICKET_COUNT - 3)
TWO_DISJOINT_HEAVY_DEGREES = (1, 1, 1, 1) + (0,) * (TICKET_COUNT - 4)

_WEDGE_CAPS = {
    (1, 1): 2_800,
    (1, 2): 14_420,
    (2, 2): 33_264,
}
_TRIANGLE_CORRECTIONS = {
    0: 11_872,
    1: 24_486,
    2: 69_860,
    3: 244_720,
}


def _canonical_pair(left: int, right: int) -> tuple[int, int]:
    low, high = sorted((left, right))
    return low, high


def _canonical_profile(profile: tuple[int, int, int]) -> tuple[int, int, int]:
    low, middle, high = sorted(profile)
    return low, middle, high


@dataclass(frozen=True)
class BoundWitness:
    """The arithmetic terms attaining a relaxed structural upper bound."""

    upper_bound: int
    s2_lower_bound: int
    s3_upper_bound: int
    heavy_pair_count: int
    ordinary_edge_count: int
    ordinary_wedge_upper: int
    heavy_normal_wedge_upper: int
    heavy_wedge_upper: int
    triangle_counts_upper: tuple[int, int, int, int]
    degree_profile: tuple[int, ...] = ()


@cache
def pair_costs() -> tuple[int, ...]:
    """Return and verify exact pair-event intersection counts for overlaps 0..6."""

    counts = pair_intersection_table()
    if counts != EXPECTED_PAIR_COUNTS:
        raise AssertionError("exact K20 pair-intersection counts changed")
    return counts


def classify_heavy_graph(edges: tuple[tuple[int, int], ...]) -> str:
    """Classify the requested mutually exclusive heavy-pair graph families."""

    normalized: list[tuple[int, int]] = []
    for left, right in edges:
        if left == right or min(left, right) < 0 or max(left, right) >= TICKET_COUNT:
            raise ValueError("heavy-pair edges must join two distinct K20 tickets")
        normalized.append(_canonical_pair(left, right))
    if len(set(normalized)) != len(normalized):
        raise ValueError("heavy-pair graph cannot contain duplicate edges")
    if len(normalized) < 2:
        raise ValueError("the multi-r2 family requires at least two heavy pairs")
    if len(normalized) >= 3:
        return "THREE_OR_MORE_HEAVY_PAIRS"
    return (
        "TWO_SHARED_VERTEX"
        if set(normalized[0]) & set(normalized[1])
        else "TWO_DISJOINT"
    )


def s2_floor_for_heavy_count(heavy_pair_count: int) -> int:
    """Return the exact pair-cost floor implied by overlap mass at least 93."""

    if not 0 <= heavy_pair_count <= PAIR_COUNT:
        raise ValueError("heavy-pair count must fit the K20 pair count")
    costs = pair_costs()
    ordinary_edges = max(0, MINIMUM_OVERLAP_MASS - 2 * heavy_pair_count)
    return (
        PAIR_COUNT * costs[0]
        + ordinary_edges * (costs[1] - costs[0])
        + heavy_pair_count * (costs[2] - costs[0])
    )


def _pair_cost_s2(ordinary_edges: int, heavy_pair_count: int) -> int:
    costs = pair_costs()
    return (
        PAIR_COUNT * costs[0]
        + ordinary_edges * (costs[1] - costs[0])
        + heavy_pair_count * (costs[2] - costs[0])
    )


@cache
def _triple_profile_maxima() -> dict[tuple[int, int, int], int]:
    return {
        _canonical_profile((ab, ac, bc)): maximum
        for ab, ac, bc, maximum in exact_triple_profile_table()
    }


def triple_profile_cap(overlaps: tuple[int, int, int]) -> int:
    """Return the exact Venn-profile ceiling for a triple of ticket overlaps."""

    if len(overlaps) != 3 or any(value not in (0, 1, 2) for value in overlaps):
        raise ValueError("multi-r2 profiles require three overlaps in 0..2")
    return _triple_profile_maxima()[_canonical_profile(overlaps)]


def _wedge_cap(left: int, right: int) -> int:
    if left == 0 or right == 0:
        return 0
    return _WEDGE_CAPS[_canonical_pair(left, right)]


def decomposed_triple_profile_cap(overlaps: tuple[int, int, int]) -> int:
    """Recover the exact profile ceiling from wedge bases and triangle correction."""

    if len(overlaps) != 3 or any(value not in (0, 1, 2) for value in overlaps):
        raise ValueError("multi-r2 profiles require three overlaps in 0..2")
    positive = tuple(value for value in overlaps if value)
    if len(positive) == 1:
        return 2_240 if positive[0] == 2 else 0

    wedge_total = sum(_wedge_cap(left, right) for left, right in combinations(positive, 2))
    if len(positive) < 3:
        return wedge_total
    heavy_edges = sum(value == 2 for value in positive)
    return wedge_total + _TRIANGLE_CORRECTIONS[heavy_edges]


def _triangle_bonus(
    ordinary_wedges: int,
    heavy_normal_wedges: int,
    heavy_wedges: int,
    heavy_pair_count: int,
) -> tuple[int, tuple[int, int, int, int]]:
    """Maximize the triangle corrections under wedge and heavy-edge slot caps.

    A 0/1/2/3-heavy-edge triangle consumes respectively
    (3,0,0)/(1,2,0)/(0,2,1)/(0,0,3) ordinary/hi/HH wedges and
    0/1/2/3 slots among the 18 third tickets incident to each heavy edge.
    The exact reward-per-scarce-resource ordering is three-heavy, two-heavy,
    one-heavy, then zero-heavy, so the greedy allocation solves this small
    integer relaxation exactly.
    """

    three_heavy = heavy_wedges // 3
    remaining_hh = heavy_wedges - 3 * three_heavy
    remaining_heavy_slots = 18 * heavy_pair_count - 3 * three_heavy

    two_heavy = min(
        remaining_hh,
        heavy_normal_wedges // 2,
        remaining_heavy_slots // 2,
    )
    remaining_hn = heavy_normal_wedges - 2 * two_heavy
    remaining_heavy_slots -= 2 * two_heavy

    one_heavy = min(
        ordinary_wedges,
        remaining_hn // 2,
        remaining_heavy_slots,
    )
    zero_heavy = (ordinary_wedges - one_heavy) // 3
    counts = (zero_heavy, one_heavy, two_heavy, three_heavy)
    reward = sum(
        count * _TRIANGLE_CORRECTIONS[heavy_edges]
        for heavy_edges, count in enumerate(counts)
    )
    return reward, counts


def _s3_from_wedge_ceilings(
    *,
    ordinary_wedges: int,
    heavy_normal_wedges: int,
    heavy_wedges: int,
    heavy_pair_count: int,
) -> tuple[int, tuple[int, int, int, int]]:
    triangle_bonus, triangle_counts = _triangle_bonus(
        ordinary_wedges,
        heavy_normal_wedges,
        heavy_wedges,
        heavy_pair_count,
    )
    wedge_recovery = (
        _WEDGE_CAPS[(1, 1)] * ordinary_wedges
        + _WEDGE_CAPS[(1, 2)] * heavy_normal_wedges
        + _WEDGE_CAPS[(2, 2)] * heavy_wedges
    )
    isolated_heavy_edge_recovery = 2_240 * 18 * heavy_pair_count
    return wedge_recovery + triangle_bonus + isolated_heavy_edge_recovery, triangle_counts


def _maximize_convex_wedge_sum(
    lower: tuple[int, ...], upper: tuple[int, ...], total: int
) -> int | None:
    """Maximize ``sum C(x,2)`` with integer box bounds and a fixed total."""

    if len(lower) != TICKET_COUNT or len(upper) != TICKET_COUNT:
        raise ValueError("degree profiles must contain exactly 20 tickets")
    if any(lo < 0 or hi < lo for lo, hi in zip(lower, upper, strict=True)):
        raise ValueError("invalid degree interval")
    if not sum(lower) <= total <= sum(upper):
        return None

    values = list(lower)
    remaining = total - sum(values)
    while remaining:
        index = max(
            (i for i in range(TICKET_COUNT) if values[i] < upper[i]),
            key=lambda i: (values[i], upper[i]),
        )
        increment = min(remaining, upper[index] - values[index])
        values[index] += increment
        remaining -= increment
    return sum(comb(value, 2) for value in values)


def _maximize_weighted_wedges(
    heavy_degrees: tuple[int, ...],
    lower: tuple[int, ...],
    upper: tuple[int, ...],
    total: int,
) -> int | None:
    """Maximize ``sum heavy_degree * normal_degree`` under the same boxes."""

    if not sum(lower) <= total <= sum(upper):
        return None
    values = list(lower)
    remaining = total - sum(values)
    for index in sorted(range(TICKET_COUNT), key=lambda i: heavy_degrees[i], reverse=True):
        increment = min(remaining, upper[index] - values[index])
        values[index] += increment
        remaining -= increment
    if remaining:
        return None
    return sum(degree * normal for degree, normal in zip(heavy_degrees, values, strict=True))


def _heavy_degree_profiles(heavy_pair_count: int) -> tuple[tuple[int, ...], ...]:
    """Enumerate all sorted degree multisets up to six, relaxing graph realizability."""

    profiles: list[tuple[int, ...]] = []
    target = 2 * heavy_pair_count

    def visit(position: int, maximum: int, remaining: int, prefix: tuple[int, ...]) -> None:
        if position == TICKET_COUNT:
            if remaining == 0:
                profiles.append(prefix)
            return
        remaining_slots = TICKET_COUNT - position - 1
        minimum = max(
            0,
            remaining - MAX_MINIMUM_MASS_HEAVY_GRAPH_DEGREE * remaining_slots,
        )
        high = min(maximum, MAX_MINIMUM_MASS_HEAVY_GRAPH_DEGREE, remaining)
        for degree in range(high, minimum - 1, -1):
            visit(position + 1, degree, remaining - degree, (*prefix, degree))

    visit(0, MAX_MINIMUM_MASS_HEAVY_GRAPH_DEGREE, target, ())
    return tuple(profiles)


def _minimum_mass_profile_witness(
    heavy_pair_count: int,
    heavy_degrees: tuple[int, ...],
) -> BoundWitness | None:
    ordinary_edges = MINIMUM_OVERLAP_MASS - 2 * heavy_pair_count
    if ordinary_edges < 0:
        return None
    normal_total = 2 * ordinary_edges
    lower = tuple(max(0, 6 - 2 * degree) for degree in heavy_degrees)
    upper = tuple(12 - 2 * degree for degree in heavy_degrees)
    ordinary_wedges = _maximize_convex_wedge_sum(lower, upper, normal_total)
    heavy_normal_wedges = _maximize_weighted_wedges(
        heavy_degrees, lower, upper, normal_total
    )
    if ordinary_wedges is None or heavy_normal_wedges is None:
        return None
    heavy_wedges = sum(comb(degree, 2) for degree in heavy_degrees)
    s3, triangle_counts = _s3_from_wedge_ceilings(
        ordinary_wedges=ordinary_wedges,
        heavy_normal_wedges=heavy_normal_wedges,
        heavy_wedges=heavy_wedges,
        heavy_pair_count=heavy_pair_count,
    )
    s2 = _pair_cost_s2(ordinary_edges, heavy_pair_count)
    return BoundWitness(
        upper_bound=PORTFOLIO_S1 - s2 + s3,
        s2_lower_bound=s2,
        s3_upper_bound=s3,
        heavy_pair_count=heavy_pair_count,
        ordinary_edge_count=ordinary_edges,
        ordinary_wedge_upper=ordinary_wedges,
        heavy_normal_wedge_upper=heavy_normal_wedges,
        heavy_wedge_upper=heavy_wedges,
        triangle_counts_upper=triangle_counts,
        degree_profile=heavy_degrees,
    )


def _minimum_mass_multi_witnesses() -> dict[int, BoundWitness]:
    """Bound every feasible heavy degree profile at exact mass 93."""

    witnesses: dict[int, BoundWitness] = {}
    for heavy_pair_count in range(3, MINIMUM_OVERLAP_MASS // 2 + 1):
        best: BoundWitness | None = None
        for heavy_degrees in _heavy_degree_profiles(heavy_pair_count):
            candidate = _minimum_mass_profile_witness(heavy_pair_count, heavy_degrees)
            if candidate is not None and (
                best is None or candidate.upper_bound > best.upper_bound
            ):
                best = candidate
        if best is not None:
            witnesses[heavy_pair_count] = best
    return witnesses


def _ordinary_wedge_upper_with_degrees(
    ordinary_edges: int,
    heavy_degrees: tuple[int, ...],
) -> int:
    lower = (0,) * TICKET_COUNT
    capacities = tuple(19 - degree for degree in heavy_degrees)
    result = _maximize_convex_wedge_sum(lower, capacities, 2 * ordinary_edges)
    if result is None:
        raise AssertionError("ordinary overlap graph degree relaxation is infeasible")
    return result


def _graph_relaxation_witness(
    heavy_pair_count: int,
    ordinary_edges: int,
    heavy_degrees: tuple[int, ...],
) -> BoundWitness:
    heavy_wedges = sum(comb(degree, 2) for degree in heavy_degrees)
    ordinary_wedges = _ordinary_wedge_upper_with_degrees(ordinary_edges, heavy_degrees)
    heavy_normal_wedges = min(36 * heavy_pair_count, 12 * ordinary_edges)
    s3, triangle_counts = _s3_from_wedge_ceilings(
        ordinary_wedges=ordinary_wedges,
        heavy_normal_wedges=heavy_normal_wedges,
        heavy_wedges=heavy_wedges,
        heavy_pair_count=heavy_pair_count,
    )
    s2 = _pair_cost_s2(ordinary_edges, heavy_pair_count)
    return BoundWitness(
        upper_bound=PORTFOLIO_S1 - s2 + s3,
        s2_lower_bound=s2,
        s3_upper_bound=s3,
        heavy_pair_count=heavy_pair_count,
        ordinary_edge_count=ordinary_edges,
        ordinary_wedge_upper=ordinary_wedges,
        heavy_normal_wedge_upper=heavy_normal_wedges,
        heavy_wedge_upper=heavy_wedges,
        triangle_counts_upper=triangle_counts,
        degree_profile=heavy_degrees,
    )


def _best_graph_relaxation(
    heavy_pair_count: int,
    minimum_overlap_mass: int,
    heavy_degrees: tuple[int, ...],
) -> BoundWitness:
    minimum_ordinary_edges = max(0, minimum_overlap_mass - 2 * heavy_pair_count)
    best: BoundWitness | None = None
    for ordinary_edges in range(minimum_ordinary_edges, PAIR_COUNT - heavy_pair_count + 1):
        candidate = _graph_relaxation_witness(
            heavy_pair_count,
            ordinary_edges,
            heavy_degrees,
        )
        if best is None or candidate.upper_bound > best.upper_bound:
            best = candidate
    if best is None:
        raise AssertionError("graph relaxation has no edge-count rows")
    return best


def _multi_overflow_star_witness() -> dict[str, int]:
    """Bound every mass>=94 multi-r2 portfolio by its exact S2 star floor."""

    best: dict[str, int] | None = None
    for heavy_pair_count in range(3, PAIR_COUNT + 1):
        ordinary_edges = max(0, MINIMUM_OVERLAP_MASS + 1 - 2 * heavy_pair_count)
        s2 = _pair_cost_s2(ordinary_edges, heavy_pair_count)
        star_floor = (2 * s2 + TICKET_COUNT - 1) // TICKET_COUNT
        candidate = {
            "upper_bound": PORTFOLIO_S1 - star_floor,
            "s2_lower_bound": s2,
            "star_intersection_lower_bound": star_floor,
            "heavy_pair_count": heavy_pair_count,
            "ordinary_edge_count": ordinary_edges,
        }
        if best is None or candidate["upper_bound"] > best["upper_bound"]:
            best = candidate
    if best is None:
        raise AssertionError("multi-r2 star bound has no defect counts")
    return best


def _minimum_mass_topology_witness(
    heavy_pair_count: int,
    heavy_degrees: tuple[int, ...],
) -> BoundWitness:
    candidate = _minimum_mass_profile_witness(heavy_pair_count, heavy_degrees)
    if candidate is None:
        raise AssertionError("two-defect graph has no minimum-mass profile")
    return candidate


@cache
def defect_bound_certificates() -> dict[str, Any]:
    """Build all three graph-family certificates and the unique residual family."""

    counts = pair_costs()
    if counts[2] != 1_695_988:
        raise AssertionError("the exact r=2 pair cost changed")
    mass, frequencies = minimum_pair_overlap_mass()
    if mass != MINIMUM_OVERLAP_MASS or frequencies != (2,) * 27 + (3,) * 22:
        raise AssertionError("the exact minimum overlap-mass profile changed")
    if PORTFOLIO_S1 != 364_421_560:
        raise AssertionError("the exact single-ticket total changed")

    shared_minimum_mass = _minimum_mass_topology_witness(2, TWO_SHARED_HEAVY_DEGREES)
    disjoint_minimum_mass = _minimum_mass_topology_witness(2, TWO_DISJOINT_HEAVY_DEGREES)
    shared_general = _best_graph_relaxation(
        2, MINIMUM_OVERLAP_MASS, TWO_SHARED_HEAVY_DEGREES
    )
    disjoint_general = _best_graph_relaxation(
        2, MINIMUM_OVERLAP_MASS, TWO_DISJOINT_HEAVY_DEGREES
    )
    shared_bound = max(shared_minimum_mass.upper_bound, shared_general.upper_bound)
    disjoint_bound = max(disjoint_minimum_mass.upper_bound, disjoint_general.upper_bound)

    minimum_mass_multi = _minimum_mass_multi_witnesses()
    multi_minimum_witness = max(
        minimum_mass_multi.values(), key=lambda witness: witness.upper_bound
    )
    multi_overflow_witness = _multi_overflow_star_witness()

    multi_bound = max(
        multi_minimum_witness.upper_bound,
        multi_overflow_witness["upper_bound"],
    )
    family_bound = max(shared_bound, disjoint_bound, multi_bound)
    unresolved = (
        "THREE_OR_MORE_HEAVY_PAIRS_WITH_OVERLAP_MASS_AT_LEAST_94"
        if multi_overflow_witness["upper_bound"] > INCUMBENT
        else None
    )
    closed = [
        name
        for name, bound in (
            ("TWO_SHARED_VERTEX", shared_bound),
            ("TWO_DISJOINT", disjoint_bound),
            ("THREE_OR_MORE_AT_MASS_93", multi_minimum_witness.upper_bound),
        )
        if bound <= INCUMBENT
    ]
    status = "CLOSED" if family_bound <= INCUMBENT else "BOUNDED_OPEN_RESIDUAL"
    return {
        "DEFECT_GRAPH_FAMILY_COUNT": 3,
        "SHARED_VERTEX_R2_BOUND": shared_bound,
        "DISJOINT_R2_BOUND": disjoint_bound,
        "MULTI_R2_BOUND": multi_bound,
        "FAMILY_B_BOUND": family_bound,
        "FAMILY_B_STATUS": status,
        "UNRESOLVED_DEFECT_GRAPH": unresolved,
        "CLOSED_DEFECT_FAMILIES": closed,
        "S2_MINIMUMS": {
            "TWO_SHARED_VERTEX": shared_minimum_mass.s2_lower_bound,
            "TWO_DISJOINT": disjoint_minimum_mass.s2_lower_bound,
            "THREE_OR_MORE": s2_floor_for_heavy_count(3),
            "THREE_OR_MORE_MASS_AT_LEAST_94": _pair_cost_s2(88, 3),
            "FORMULA_FOR_HEAVY_COUNT_H": (
                "190*I(0)+max(0,93-2h)*(I(1)-I(0))+h*(I(2)-I(0))"
            ),
        },
        "MINIMUM_MASS_MULTI_BOUNDS_BY_HEAVY_COUNT": {
            str(heavy_count): asdict(witness)
            for heavy_count, witness in minimum_mass_multi.items()
        },
        "SHARED_VERTEX_WITNESSES": {
            "MASS_93": asdict(shared_minimum_mass),
            "GRAPH_RELAXATION": asdict(shared_general),
        },
        "DISJOINT_WITNESSES": {
            "MASS_93": asdict(disjoint_minimum_mass),
            "GRAPH_RELAXATION": asdict(disjoint_general),
        },
        "MULTI_MASS_93_WITNESS": asdict(multi_minimum_witness),
        "MULTI_MASS_GE_94_WITNESS": multi_overflow_witness,
        "INCUMBENT": INCUMBENT,
        "REMAINING_GAP": family_bound - INCUMBENT,
        "CP_SAT": {
            "STATUS": "NOT_RUN",
            "REASON": "The degree and wedge certificates meet Success B without a solver run.",
        },
    }


def result_record() -> dict[str, Any]:
    """Return the durable, JSON-serializable task result."""

    certificates = defect_bound_certificates()
    parent_gap = PARENT_BOUND - int(certificates["FAMILY_B_BOUND"])
    return {
        "TASK_ID": "B649_K20_MULTI_R2_DEFECT_GLOBAL_BOUND_R3",
        "TASK_STATUS": "BOUNDED_WITH_UNIQUE_MULTI_R2_OVERFLOW_RESIDUAL",
        "BASE_HEAD": BASE_HEAD,
        "TASK_BRANCH": TASK_BRANCH,
        "INCUMBENT": INCUMBENT,
        "CURRENT_PARENT_BOUND": PARENT_BOUND,
        "PORTFOLIO_S1": PORTFOLIO_S1,
        "TICKET_PAIR_COUNT": PAIR_COUNT,
        "PAIR_INTERSECTION_COUNTS_BY_OVERLAP": list(pair_costs()),
        "MINIMUM_OVERLAP_MASS": MINIMUM_OVERLAP_MASS,
        "MINIMUM_FREQUENCY_PROFILE": {"2": 27, "3": 22},
        "MASS_93_HEAVY_PAIR_DEGREE_BOUND": MAX_MINIMUM_MASS_HEAVY_GRAPH_DEGREE,
        "METHOD": {
            "PAIR_COST": "S2=190*I(0)+E*(I(1)-I(0))+h*(I(2)-I(0))",
            "OVERLAP_MASS": "E+2h>=93; exact mass-93 incidence gives dN=6+r-2*dH, 0<=r<=6",
            "S3": (
                "Exact triple-profile maxima decomposed into NN/HN/HH wedges, "
                "four triangle corrections, "
                "and at most 18h isolated heavy-edge triples."
            ),
            "HIGH_OVERLAP_MASS_BOUND": (
                "For h>=3 and E+2h>=94, Hunter-star gives S1-ceil(S2/10); "
                "the exact S2 floor is minimized at h=3,E=88."
            ),
            "CP_SAT": (
                "NOT RUN; exact mass-93 wedge certificates and the overflow Hunter-star "
                "bound were sufficient for Success B."
            ),
        },
        "CERTIFICATES": certificates,
        "PARENT_BOUND_IMPROVEMENT": parent_gap,
        "SUCCESS_A": certificates["FAMILY_B_BOUND"] <= INCUMBENT,
        "SUCCESS_B": certificates["FAMILY_B_BOUND"] < PARENT_BOUND
        and certificates["UNRESOLVED_DEFECT_GRAPH"] is not None,
        "NEW_PORTFOLIO_SEARCH_STARTED": "NO",
        "PRODUCTION_MUTATION": "NONE",
    }


__all__ = [
    "BASE_HEAD",
    "EXPECTED_PAIR_COUNTS",
    "BoundWitness",
    "classify_heavy_graph",
    "decomposed_triple_profile_cap",
    "defect_bound_certificates",
    "pair_costs",
    "result_record",
    "s2_floor_for_heavy_count",
    "triple_profile_cap",
]
