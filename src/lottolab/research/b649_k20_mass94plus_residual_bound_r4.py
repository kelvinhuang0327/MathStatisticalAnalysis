"""Certified bounds for the K20 multi-r2 residual at overlap mass 94+.

The proof separates the exact three-heavy-edge boundary from every larger
heavy graph.  The boundary uses the exact three-ticket profile table and
ticket-label incidence.  Larger graphs use a seven-drawn-label incidence
bound on the number of tickets that can win one outcome.  No portfolio
outcomes or candidate ticket collections are enumerated.
"""

from __future__ import annotations

import argparse
import importlib
import json
from dataclasses import asdict, dataclass
from functools import cache
from itertools import combinations
from math import ceil, comb
from time import monotonic
from typing import Any, cast

from lottolab.research.b649_k20_heavy_pair_defect_global_bound_r2 import (
    exact_triple_profile_table,
)
from lottolab.research.b649_k20_outside_min_s2_global_penalty_bound_r1 import (
    INCUMBENT,
    PAIR_COUNT,
    PORTFOLIO_S1,
    TICKET_COUNT,
    pair_intersection_table,
)

BASE_HEAD = "c16be9ca51e3fbdb2414dc96b77187337425d370"
BASE_TREE = "f107b43faed6cb38d6cbd796718492b8443307c9"
TASK_BRANCH = "codex/b649-k20-multi-r2-mass94plus-residual-bound-r4"
PRIOR_FAMILY_B_BOUND = 357_794_343
MASS_THRESHOLD = 94
DRAWN_LABEL_COUNT = 7
TICKET_LABEL_COUNT = 6
NUMBER_LABEL_COUNT = 49
EXPECTED_PAIR_COUNTS = (
    107_800,
    574_000,
    1_695_988,
    3_469_942,
    6_224_512,
    10_776_332,
    18_611_432,
)

# This is the fixed solver budget for the one remaining h=45, M=94 motif.
# A FEASIBLE incumbent is never substituted for the solver's certified bound.
CP_SAT_TIME_LIMIT_SECONDS = 30.0
CP_SAT_WORKERS = 1
CP_SAT_RANDOM_SEED = 649

THREE_EDGE_MOTIF_DEGREES: dict[str, tuple[int, ...]] = {
    "THREE_DISJOINT_PAIRS": (1, 1, 1, 1, 1, 1) + (0,) * 14,
    "PATH_2_PLUS_DISJOINT_EDGE": (2, 1, 1, 1, 1) + (0,) * 15,
    "PATH_4": (2, 2, 1, 1) + (0,) * 16,
    "THREE_EDGE_STAR": (3, 1, 1, 1) + (0,) * 16,
    "TRIANGLE": (2, 2, 2) + (0,) * 17,
}


@dataclass(frozen=True)
class ThreeEdgeWitness:
    """S2/S3 terms for one exact three-edge heavy-graph motif."""

    motif: str
    heavy_degree_profile: tuple[int, ...]
    ordinary_edge_count: int
    overlap_mass: int
    s2_lower_bound: int
    ticket_overlap_degree_cap: int
    ordinary_degree_caps: tuple[int, ...]
    ordinary_wedges_upper: int
    heavy_normal_wedges_upper: int
    heavy_wedges: int
    triangle_counts_upper: tuple[int, int, int, int]
    s3_upper_bound: int
    upper_bound: int


@dataclass(frozen=True)
class MultiplicityWitness:
    """A graph-count and one-outcome multiplicity upper-bound witness."""

    heavy_pair_count: int
    minimum_overlap_mass: int
    ordinary_edge_count: int
    s2_lower_bound: int
    winning_ticket_cap: int
    pair_reuse_floor_at_cap: int
    pair_reuse_floor_above_cap: int | None
    duplicate_outcome_lower_bound: int
    upper_bound: int


@dataclass(frozen=True)
class CpSatWitness:
    """Bound returned by the compressed single-outcome CP-SAT model."""

    status: str
    objective: int | None
    certified_upper_bound: int | None
    wall_time_seconds: float
    time_limit_seconds: float
    workers: int
    scope: str


def pair_costs() -> tuple[int, ...]:
    """Return exact pair-event intersections for ticket overlaps zero through six."""

    counts = pair_intersection_table()
    if counts != EXPECTED_PAIR_COUNTS:
        raise AssertionError("exact K20 pair-intersection counts changed")
    return counts


def _canonical_edges(
    edges: tuple[tuple[int, int], ...], vertex_count: int
) -> tuple[tuple[int, int], ...]:
    if vertex_count < 1:
        raise ValueError("vertex_count must be positive")
    normalized: list[tuple[int, int]] = []
    for left, right in edges:
        if left == right or min(left, right) < 0 or max(left, right) >= vertex_count:
            raise ValueError("heavy-pair edges must join distinct in-range tickets")
        low, high = sorted((left, right))
        normalized.append((low, high))
    if len(set(normalized)) != len(normalized):
        raise ValueError("heavy-pair graph cannot contain duplicate edges")
    return tuple(sorted(normalized))


def classify_three_edge_motif(
    edges: tuple[tuple[int, int], ...], *, vertex_count: int = TICKET_COUNT
) -> str:
    """Classify every realizable simple graph with exactly three heavy edges."""

    normalized = _canonical_edges(edges, vertex_count)
    if len(normalized) != 3:
        raise ValueError("three-edge motif classification requires exactly three edges")
    degrees = [0] * vertex_count
    for left, right in normalized:
        degrees[left] += 1
        degrees[right] += 1
    positive = tuple(sorted((degree for degree in degrees if degree), reverse=True))
    if positive == (1, 1, 1, 1, 1, 1):
        return "THREE_DISJOINT_PAIRS"
    if positive == (2, 1, 1, 1, 1):
        return "PATH_2_PLUS_DISJOINT_EDGE"
    if positive == (2, 2, 1, 1):
        return "PATH_4"
    if positive == (3, 1, 1, 1):
        return "THREE_EDGE_STAR"
    if positive == (2, 2, 2):
        return "TRIANGLE"
    raise AssertionError("three-edge simple graph had an impossible degree profile")


def minimum_mass_for_heavy_count(heavy_pair_count: int, mass_floor: int = MASS_THRESHOLD) -> int:
    """Return the least overlap mass allowed by h exact-r=2 edges and mass_floor."""

    if not 0 <= heavy_pair_count <= PAIR_COUNT:
        raise ValueError("heavy_pair_count must fit the 20-ticket pair count")
    if mass_floor < 0:
        raise ValueError("mass_floor must be nonnegative")
    return max(mass_floor, 2 * heavy_pair_count)


def minimum_s2_for_heavy_count(heavy_pair_count: int, overlap_mass: int) -> int:
    """Return exact S2 for h overlap-2 pairs and total overlap mass M.

    Every other pair in Family B overlaps in zero or one label, so the number
    of overlap-1 pairs is exactly M-2h.  The routine checks this pair-count
    profile before applying the exact pair-event costs.
    """

    if not 0 <= heavy_pair_count <= PAIR_COUNT:
        raise ValueError("heavy_pair_count must fit the 20-ticket pair count")
    ordinary_edges = overlap_mass - 2 * heavy_pair_count
    if ordinary_edges < 0 or ordinary_edges > PAIR_COUNT - heavy_pair_count:
        raise ValueError("overlap mass is incompatible with the pair-count profile")
    costs = pair_costs()
    return (
        PAIR_COUNT * costs[0]
        + ordinary_edges * (costs[1] - costs[0])
        + heavy_pair_count * (costs[2] - costs[0])
    )


def balanced_pair_mass(total_incidences: int, label_count: int) -> int:
    """Minimum sum of choose(frequency, 2) over a fixed number of labels."""

    if total_incidences < 0 or label_count < 1:
        raise ValueError("incidences must be nonnegative and label_count positive")
    quotient, remainder = divmod(total_incidences, label_count)
    return (label_count - remainder) * comb(quotient, 2) + remainder * comb(quotient + 1, 2)


def ticket_overlap_degree_cap_at_mass_94() -> int:
    """Bound one ticket's total overlap degree using all 49 label frequencies.

    For a ticket using six labels with total frequency R, its overlap degree is
    R-6.  Convexity minimizes the pair mass of those six frequencies and of the
    other 43 frequencies when each group is balanced.  R=19 permits total mass
    94; R=20 already requires mass 95, and the lower bound increases thereafter.
    """

    total_incidences = TICKET_COUNT * TICKET_LABEL_COUNT
    other_labels = NUMBER_LABEL_COUNT - TICKET_LABEL_COUNT
    feasible_sums = [
        selected_sum
        for selected_sum in range(TICKET_LABEL_COUNT, total_incidences + 1)
        if balanced_pair_mass(selected_sum, TICKET_LABEL_COUNT)
        + balanced_pair_mass(total_incidences - selected_sum, other_labels)
        <= MASS_THRESHOLD
    ]
    if not feasible_sums:
        raise AssertionError("no six-label incidence profile fits mass 94")
    if max(feasible_sums) != 19:
        raise AssertionError("the exact mass-94 ticket-incidence threshold changed")
    return max(feasible_sums) - TICKET_LABEL_COUNT


@cache
def _triple_profile_caps() -> dict[tuple[int, int, int], int]:
    maxima: dict[tuple[int, int, int], int] = {}
    rows = exact_triple_profile_table()
    if len(rows) != 343:
        raise AssertionError("the exact triple-profile table must contain 343 rows")
    for left, middle, right, maximum in rows:
        low, center, high = sorted((left, middle, right))
        key = (low, center, high)
        prior = maxima.setdefault(key, maximum)
        if prior != maximum:
            raise AssertionError("exact triple profile changed under ticket permutation")
    return maxima


def triple_profile_cap(overlaps: tuple[int, int, int]) -> int:
    """Return the exact table ceiling for a three-ticket overlap profile in 0..2."""

    if len(overlaps) != 3 or any(overlap not in (0, 1, 2) for overlap in overlaps):
        raise ValueError("Family B triple profiles require three overlaps in 0..2")
    low, center, high = sorted(overlaps)
    return _triple_profile_caps()[(low, center, high)]


def _triple_decomposition() -> tuple[
    int,
    dict[tuple[int, int], int],
    tuple[int, int, int, int],
]:
    single_heavy = triple_profile_cap((0, 0, 2))
    wedge_caps = {
        (1, 1): triple_profile_cap((0, 1, 1)),
        (1, 2): triple_profile_cap((0, 1, 2)),
        (2, 2): triple_profile_cap((0, 2, 2)),
    }
    triangle_profiles = (
        (1, 1, 1),
        (1, 1, 2),
        (1, 2, 2),
        (2, 2, 2),
    )
    corrections: list[int] = []
    for profile in triangle_profiles:
        wedge_sum = 0
        for left, right in combinations(profile, 2):
            if min(left, right) > 0:
                low, high = sorted((left, right))
                wedge_sum += wedge_caps[(low, high)]
        correction = triple_profile_cap(profile) - wedge_sum
        if correction < 0:
            raise AssertionError("triangle correction cannot be negative")
        corrections.append(correction)
    if triple_profile_cap((0, 0, 1)) != 0:
        raise AssertionError("a one-edge ordinary triple must have zero recovery")
    return single_heavy, wedge_caps, tuple(corrections)  # type: ignore[return-value]


def _maximize_convex_wedges(upper: tuple[int, ...], total: int) -> int:
    if len(upper) != TICKET_COUNT or any(value < 0 for value in upper):
        raise ValueError("ordinary degree caps must be nonnegative for all 20 tickets")
    if not 0 <= total <= sum(upper):
        raise ValueError("ordinary degree total does not fit its ticket caps")
    degrees = [0] * TICKET_COUNT
    remaining = total
    while remaining:
        index = max(
            (i for i in range(TICKET_COUNT) if degrees[i] < upper[i]),
            key=lambda i: (degrees[i], upper[i]),
        )
        amount = min(remaining, upper[index] - degrees[index])
        degrees[index] += amount
        remaining -= amount
    return sum(comb(degree, 2) for degree in degrees)


def _maximize_heavy_normal_wedges(
    heavy_degrees: tuple[int, ...], upper: tuple[int, ...], total: int
) -> int:
    if len(heavy_degrees) != TICKET_COUNT or len(upper) != TICKET_COUNT:
        raise ValueError("heavy and ordinary degree profiles must cover 20 tickets")
    if not 0 <= total <= sum(upper):
        raise ValueError("ordinary degree total does not fit its ticket caps")
    remaining = total
    ordinary_degrees = [0] * TICKET_COUNT
    for index in sorted(range(TICKET_COUNT), key=lambda i: heavy_degrees[i], reverse=True):
        amount = min(remaining, upper[index])
        ordinary_degrees[index] = amount
        remaining -= amount
    if remaining:
        raise AssertionError("weighted wedge maximization left degree unassigned")
    return sum(
        heavy * ordinary
        for heavy, ordinary in zip(heavy_degrees, ordinary_degrees, strict=True)
    )


def _triangle_correction_upper(
    ordinary_wedges: int,
    heavy_normal_wedges: int,
    heavy_wedges: int,
    heavy_pair_count: int,
) -> tuple[int, tuple[int, int, int, int]]:
    """Solve the four-type triangle correction relaxation exactly."""

    _, _, corrections = _triple_decomposition()
    slots = 18 * heavy_pair_count
    best_reward = -1
    best_counts = (0, 0, 0, 0)
    max_three_heavy = min(heavy_wedges // 3, slots // 3)
    for three_heavy in range(max_three_heavy + 1):
        remaining_hh = heavy_wedges - 3 * three_heavy
        remaining_slots = slots - 3 * three_heavy
        max_two_heavy = min(
            remaining_hh,
            heavy_normal_wedges // 2,
            remaining_slots // 2,
        )
        for two_heavy in range(max_two_heavy + 1):
            remaining_hn = heavy_normal_wedges - 2 * two_heavy
            remaining_slots_after_two = remaining_slots - 2 * two_heavy
            max_one_heavy = min(
                ordinary_wedges,
                remaining_hn // 2,
                remaining_slots_after_two,
            )
            for one_heavy in range(max_one_heavy + 1):
                zero_heavy = (ordinary_wedges - one_heavy) // 3
                counts = (zero_heavy, one_heavy, two_heavy, three_heavy)
                reward = sum(
                    count * correction
                    for count, correction in zip(counts, corrections, strict=True)
                )
                if reward > best_reward:
                    best_reward = reward
                    best_counts = counts
    if best_reward < 0:
        raise AssertionError("triangle correction relaxation has no feasible row")
    return best_reward, best_counts


def three_edge_motif_witness(motif: str) -> ThreeEdgeWitness:
    """Bound S3 for one exact three-edge graph at M=94."""

    try:
        heavy_degrees = THREE_EDGE_MOTIF_DEGREES[motif]
    except KeyError as exc:
        raise ValueError("unknown three-edge heavy-pair motif") from exc
    ordinary_edge_count = MASS_THRESHOLD - 2 * 3
    if ordinary_edge_count != 88:
        raise AssertionError("the exact mass-94 ordinary-edge count changed")
    ticket_degree_cap = ticket_overlap_degree_cap_at_mass_94()
    ordinary_caps = tuple(ticket_degree_cap - 2 * degree for degree in heavy_degrees)
    if min(ordinary_caps) < 0:
        raise AssertionError("a three-edge motif exceeds the ticket overlap-degree cap")
    ordinary_wedges = _maximize_convex_wedges(ordinary_caps, 2 * ordinary_edge_count)
    heavy_normal_wedges = _maximize_heavy_normal_wedges(
        heavy_degrees, ordinary_caps, 2 * ordinary_edge_count
    )
    heavy_wedges = sum(comb(degree, 2) for degree in heavy_degrees)
    single_heavy, wedge_caps, _ = _triple_decomposition()
    triangle_bonus, triangle_counts = _triangle_correction_upper(
        ordinary_wedges,
        heavy_normal_wedges,
        heavy_wedges,
        3,
    )
    s3 = (
        wedge_caps[(1, 1)] * ordinary_wedges
        + wedge_caps[(1, 2)] * heavy_normal_wedges
        + wedge_caps[(2, 2)] * heavy_wedges
        + triangle_bonus
        + single_heavy * 18 * 3
    )
    s2 = minimum_s2_for_heavy_count(3, MASS_THRESHOLD)
    return ThreeEdgeWitness(
        motif=motif,
        heavy_degree_profile=heavy_degrees,
        ordinary_edge_count=ordinary_edge_count,
        overlap_mass=MASS_THRESHOLD,
        s2_lower_bound=s2,
        ticket_overlap_degree_cap=ticket_degree_cap,
        ordinary_degree_caps=ordinary_caps,
        ordinary_wedges_upper=ordinary_wedges,
        heavy_normal_wedges_upper=heavy_normal_wedges,
        heavy_wedges=heavy_wedges,
        triangle_counts_upper=triangle_counts,
        s3_upper_bound=s3,
        upper_bound=PORTFOLIO_S1 - s2 + s3,
    )


def three_edge_motif_witnesses() -> tuple[ThreeEdgeWitness, ...]:
    """Return the five exact three-edge simple-graph certificates."""

    return tuple(three_edge_motif_witness(motif) for motif in THREE_EDGE_MOTIF_DEGREES)


def pair_reuse_floor(winning_ticket_count: int) -> int:
    """Lower-bound heavy edges forced by q distinct hit-triples inside seven labels."""

    if not 0 <= winning_ticket_count <= TICKET_COUNT:
        raise ValueError("winning_ticket_count must be between zero and 20")
    # Each winning ticket contributes one distinct 3-subset and hence three
    # pair-label incidences.  Balance those incidences over the 21 pairs in the
    # seven-number outcome set to minimize repeated pair incidences.
    return balanced_pair_mass(3 * winning_ticket_count, comb(DRAWN_LABEL_COUNT, 2))


def winning_ticket_cap(heavy_pair_count: int) -> int:
    """Return the largest outcome multiplicity allowed by heavy-edge count h."""

    if not 0 <= heavy_pair_count <= PAIR_COUNT:
        raise ValueError("heavy_pair_count must fit the 20-ticket pair count")
    feasible = [
        count
        for count in range(TICKET_COUNT + 1)
        if pair_reuse_floor(count) <= heavy_pair_count
    ]
    return max(feasible)


def multiplicity_witness(
    heavy_pair_count: int, mass_floor: int = MASS_THRESHOLD
) -> MultiplicityWitness:
    """Apply S2 monotonicity and the seven-label ticket-multiplicity cap."""

    overlap_mass = minimum_mass_for_heavy_count(heavy_pair_count, mass_floor)
    ordinary_edges = overlap_mass - 2 * heavy_pair_count
    if ordinary_edges > PAIR_COUNT - heavy_pair_count:
        raise ValueError("no pair-count profile fits the requested overlap mass")
    s2 = minimum_s2_for_heavy_count(heavy_pair_count, overlap_mass)
    cap = winning_ticket_cap(heavy_pair_count)
    duplicate_lower = (2 * s2 + cap - 1) // cap
    return MultiplicityWitness(
        heavy_pair_count=heavy_pair_count,
        minimum_overlap_mass=overlap_mass,
        ordinary_edge_count=ordinary_edges,
        s2_lower_bound=s2,
        winning_ticket_cap=cap,
        pair_reuse_floor_at_cap=pair_reuse_floor(cap),
        pair_reuse_floor_above_cap=(
            pair_reuse_floor(cap + 1) if cap < TICKET_COUNT else None
        ),
        duplicate_outcome_lower_bound=duplicate_lower,
        upper_bound=PORTFOLIO_S1 - duplicate_lower,
    )


def _best_multiplicity_witness(mass_floor: int) -> MultiplicityWitness:
    witnesses = [
        multiplicity_witness(heavy_count, mass_floor)
        for heavy_count in range(3, PAIR_COUNT + 1)
    ]
    # The largest portfolio upper bound is the weakest certificate.
    return max(witnesses, key=lambda witness: witness.upper_bound)


def _best_exact_mass_94_witness() -> tuple[int, MultiplicityWitness | None]:
    motif_upper = max(witness.upper_bound for witness in three_edge_motif_witnesses())
    multiplicity_rows = [
        multiplicity_witness(heavy_count, MASS_THRESHOLD)
        for heavy_count in range(4, MASS_THRESHOLD // 2 + 1)
    ]
    best_multiplicity = max(multiplicity_rows, key=lambda witness: witness.upper_bound)
    if motif_upper >= best_multiplicity.upper_bound:
        return motif_upper, None
    return best_multiplicity.upper_bound, best_multiplicity


def _certified_multiplicity_bound(cp_sat: CpSatWitness | None) -> int | None:
    if cp_sat is None:
        return None
    return cp_sat.certified_upper_bound


def _compact_three_edge_witness(witness: ThreeEdgeWitness) -> dict[str, Any]:
    return {
        "motif": witness.motif,
        "heavy_degree_sequence": tuple(
            degree for degree in witness.heavy_degree_profile if degree
        ),
        "s2_lower_bound": witness.s2_lower_bound,
        "s3_upper_bound": witness.s3_upper_bound,
        "ordinary_wedges_upper": witness.ordinary_wedges_upper,
        "heavy_normal_wedges_upper": witness.heavy_normal_wedges_upper,
        "heavy_wedges": witness.heavy_wedges,
        "triangle_counts_upper": witness.triangle_counts_upper,
        "upper_bound": witness.upper_bound,
    }


def _mass_94_witness(cp_sat: CpSatWitness | None = None) -> dict[str, Any]:
    motif_witnesses = three_edge_motif_witnesses()
    motif_max = max(motif_witnesses, key=lambda witness: witness.upper_bound)
    best, pair_witness = _best_exact_mass_94_witness()
    cp_bound = _certified_multiplicity_bound(cp_sat)
    if (
        pair_witness is not None
        and pair_witness.heavy_pair_count == 45
        and cp_bound is not None
        and cp_bound < pair_witness.winning_ticket_cap
    ):
        tighter = multiplicity_witness(45, MASS_THRESHOLD)
        duplicate_lower = (2 * tighter.s2_lower_bound + cp_bound - 1) // cp_bound
        tighter = MultiplicityWitness(
            **{
                **asdict(tighter),
                "winning_ticket_cap": cp_bound,
                "duplicate_outcome_lower_bound": duplicate_lower,
                "upper_bound": PORTFOLIO_S1 - duplicate_lower,
            }
        )
        best = tighter.upper_bound
        pair_witness = tighter
    if pair_witness is None:
        return {
            "upper_bound": best,
            "witness_kind": "THREE_EDGE_TRIPLE_PROFILE",
            "three_edge_witness": _compact_three_edge_witness(motif_max),
        }
    return {
        "upper_bound": best,
        "witness_kind": "PAIR_MULTIPLICITY",
        "pair_multiplicity_witness": asdict(pair_witness),
        "three_edge_motif_maximum": _compact_three_edge_witness(motif_max),
    }


def run_residual_cpsat() -> CpSatWitness:
    """Maximize one-outcome ticket multiplicity in the h=45, M=94 residual.

    The model is a single structural incidence slice.  It does not score
    portfolios or enumerate lottery outcomes.  Its fixed 30-second, one-worker
    budget is declared above before the solve is started.
    """

    try:
        cp_model = cast(Any, importlib.import_module("ortools.sat.python.cp_model"))
    except ImportError:
        return CpSatWitness(
            status="NOT_AVAILABLE",
            objective=None,
            certified_upper_bound=None,
            wall_time_seconds=0.0,
            time_limit_seconds=CP_SAT_TIME_LIMIT_SECONDS,
            workers=CP_SAT_WORKERS,
            scope="h=45, M=94, maximize tickets sharing one fixed 7-label outcome",
        )

    started = monotonic()
    model: Any = cp_model.CpModel()
    ticket_labels: list[list[Any]] = [
        [model.NewBoolVar(f"ticket_{ticket}_label_{label}") for label in range(NUMBER_LABEL_COUNT)]
        for ticket in range(TICKET_COUNT)
    ]
    for ticket in range(TICKET_COUNT):
        model.Add(sum(ticket_labels[ticket]) == TICKET_LABEL_COUNT)

    pair_type_counts: list[list[Any]] = [[], [], []]
    for left, right in combinations(range(TICKET_COUNT), 2):
        shared_labels: list[Any] = []
        for label in range(NUMBER_LABEL_COUNT):
            shared = model.NewBoolVar(f"shared_{left}_{right}_{label}")
            model.Add(shared <= ticket_labels[left][label])
            model.Add(shared <= ticket_labels[right][label])
            model.Add(
                shared >= ticket_labels[left][label] + ticket_labels[right][label] - 1
            )
            shared_labels.append(shared)
        overlap = model.NewIntVar(0, 2, f"overlap_{left}_{right}")
        model.Add(overlap == sum(shared_labels))
        pair_types = [
            model.NewBoolVar(f"pair_type_{left}_{right}_{value}")
            for value in range(3)
        ]
        model.Add(sum(pair_types) == 1)
        model.Add(overlap == pair_types[1] + 2 * pair_types[2])
        for value in range(3):
            pair_type_counts[value].append(pair_types[value])
    model.Add(sum(pair_type_counts[2]) == 45)
    model.Add(sum(pair_type_counts[1]) == 4)

    # All seven outcome labels and all 42 outside labels are interchangeable.
    label_frequencies = [
        sum(ticket_labels[ticket][label] for ticket in range(TICKET_COUNT))
        for label in range(NUMBER_LABEL_COUNT)
    ]
    for label in range(DRAWN_LABEL_COUNT - 1):
        model.Add(label_frequencies[label] >= label_frequencies[label + 1])
    for label in range(DRAWN_LABEL_COUNT, NUMBER_LABEL_COUNT - 1):
        model.Add(label_frequencies[label] >= label_frequencies[label + 1])

    winners: list[Any] = []
    hit_counts: list[Any] = []
    for ticket in range(TICKET_COUNT):
        hits = model.NewIntVar(0, DRAWN_LABEL_COUNT, f"outcome_hits_{ticket}")
        model.Add(hits == sum(ticket_labels[ticket][label] for label in range(DRAWN_LABEL_COUNT)))
        winner = model.NewBoolVar(f"wins_fixed_outcome_{ticket}")
        model.Add(hits >= 3).OnlyEnforceIf(winner)
        model.Add(hits <= 2).OnlyEnforceIf(winner.Not())
        winners.append(winner)
        hit_counts.append(hits)
    for ticket in range(TICKET_COUNT - 1):
        model.Add(hit_counts[ticket] >= hit_counts[ticket + 1])
    model.Maximize(sum(winners))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = CP_SAT_TIME_LIMIT_SECONDS
    solver.parameters.num_search_workers = CP_SAT_WORKERS
    solver.parameters.random_seed = CP_SAT_RANDOM_SEED
    status_code = solver.Solve(model)
    status = str(solver.StatusName(status_code))
    objective: int | None = None
    certified_upper: int | None = None
    if status_code in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        objective = int(solver.ObjectiveValue())
        # For an integer maximization objective, ceil of the reported global
        # upper bound remains a conservative certified integer upper bound.
        certified_upper = ceil(solver.BestObjectiveBound())
        if status_code == cp_model.OPTIMAL:
            certified_upper = objective
    wall_time: float = (
        solver.WallTime()
        if hasattr(solver, "WallTime")
        else monotonic() - started
    )
    return CpSatWitness(
        status=status,
        objective=objective,
        certified_upper_bound=certified_upper,
        wall_time_seconds=wall_time,
        time_limit_seconds=CP_SAT_TIME_LIMIT_SECONDS,
        workers=CP_SAT_WORKERS,
        scope="h=45, M=94, maximize tickets sharing one fixed 7-label outcome",
    )


def result_record(cp_sat: CpSatWitness | None = None) -> dict[str, Any]:
    """Build the compact machine-readable residual-bound result."""

    costs = pair_costs()
    if costs[2] != 1_695_988 or INCUMBENT != 313_239_661:
        raise AssertionError("the exact r=2 pair cost or incumbent changed")
    exact_mass_94 = _mass_94_witness(cp_sat)
    mass_95_plus_witness = _best_multiplicity_witness(MASS_THRESHOLD + 1)
    mass_94_bound = int(exact_mass_94["upper_bound"])
    mass_95_plus_bound = mass_95_plus_witness.upper_bound
    family_bound = max(mass_94_bound, mass_95_plus_bound)
    residual = None
    residual_mass_partition = None
    if (
        family_bound == mass_94_bound
        and exact_mass_94["witness_kind"] == "PAIR_MULTIPLICITY"
    ):
        residual = exact_mass_94["pair_multiplicity_witness"]
        residual_mass_partition = "EXACT_MASS_94"
    elif family_bound == mass_95_plus_bound:
        residual = asdict(mass_95_plus_witness)
        residual_mass_partition = "MASS_95_PLUS"
    if family_bound != max(mass_94_bound, mass_95_plus_bound):
        raise AssertionError("Family B envelope does not dominate its mass partitions")
    unresolved = None
    if residual is not None:
        overlap_mass = residual.get(
            "minimum_overlap_mass",
            residual.get("overlap_mass"),
        )
        heavy_pair_count = int(residual["heavy_pair_count"])
        ordinary_edge_count = int(residual["ordinary_edge_count"])
        mass_description = (
            f"exactly {overlap_mass}"
            if residual_mass_partition == "EXACT_MASS_94"
            else f"at least {overlap_mass}"
        )
        unresolved = {
            "heavy_pair_count": heavy_pair_count,
            "ordinary_edge_count": ordinary_edge_count,
            "overlap_mass_floor": overlap_mass,
            "mass_partition": residual_mass_partition,
            "description": (
                f"exactly {heavy_pair_count} overlap-2 ticket pairs and "
                f"{ordinary_edge_count} overlap-1 pairs at total overlap mass "
                f"{mass_description}"
            ),
        }
    closed_graph_families = [
        witness.motif
        for witness in three_edge_motif_witnesses()
        if witness.upper_bound <= INCUMBENT
    ]
    return {
        "TASK_ID": "B649_K20_MULTI_R2_MASS94PLUS_RESIDUAL_BOUND_R4",
        "TASK_STATUS": "TIGHTENED_OPEN_RESIDUAL",
        "BASE_HEAD": BASE_HEAD,
        "BASE_TREE": BASE_TREE,
        "TASK_BRANCH": TASK_BRANCH,
        "RESIDUAL_GRAPH_FAMILY_COUNT": 1 if unresolved is not None else 0,
        "CLOSED_GRAPH_FAMILIES": closed_graph_families,
        "GRAPH_FAMILY_CLASSIFICATION": {
            "EXACTLY_THREE_HEAVY_EDGES": list(THREE_EDGE_MOTIF_DEGREES),
            "FOUR_OR_MORE_HEAVY_EDGES": (
                "All realizable simple graph topologies, including paths, stars, "
                "triangles, cycles, matchings with extra edges, and mixtures, "
                "are covered by the h-only multiplicity envelope."
            ),
        },
        "THREE_EDGE_BOUNDARY_CERTIFICATES": [
            _compact_three_edge_witness(witness)
            for witness in three_edge_motif_witnesses()
        ],
        "MASS94_BOUND": mass_94_bound,
        "MASS94_WITNESS": exact_mass_94,
        "MASS95PLUS_BOUND": mass_95_plus_bound,
        "MASS95PLUS_WITNESS": asdict(mass_95_plus_witness),
        "FAMILY_B_BOUND": family_bound,
        "FAMILY_B_STATUS": (
            "CLOSED" if family_bound <= INCUMBENT else "TIGHTENED_OPEN_RESIDUAL"
        ),
        "UNRESOLVED_RESIDUAL": unresolved,
        "INCUMBENT": INCUMBENT,
        "REMAINING_GAP": family_bound - INCUMBENT,
        "EXACT_PAIR_COUNTS_BY_OVERLAP": list(costs),
        "S2_FORMULA": (
            "190*I0 + (M-2h)*(I1-I0) + h*(I2-I0); "
            "at fixed h, increasing M by one adds I1-I0=466200"
        ),
        "WINNING_TICKET_MULTIPLICITY_PROOF": {
            "drawn_label_count": DRAWN_LABEL_COUNT,
            "ticket_label_count": TICKET_LABEL_COUNT,
            "pair_label_slots": comb(DRAWN_LABEL_COUNT, 2),
            "pair_reuse_floor": "balanced sum of choose(pair-label frequency, 2) over 21 slots",
            "inequality": "S2 <= K/2 * (S1-union), so duplicate loss >= ceil(2*S2/K)",
        },
        "TICKET_CAPACITY_6_INCIDENCE_BOUND": {
            "maximum_ticket_overlap_degree_at_M94": ticket_overlap_degree_cap_at_mass_94(),
            "selected_six_label_frequency_sum_limit": 19,
            "at_sum_19_minimum_pair_mass": 94,
            "at_sum_20_minimum_pair_mass": 95,
        },
        "MONOTONICITY": {
            "MASS_95PLUS": (
                "For fixed h, K(h) is fixed and S2 rises by 466200 per added mass. "
                "The worst row is at its minimum feasible mass."
            ),
            "HIGHER_HEAVY_COUNTS": (
                "For each fixed h, minimize at M=max(94,2h). All h=3..190 were "
                "checked by the closed integer formula."
            ),
        },
        "CP_SAT": {
            "STATUS": cp_sat.status if cp_sat is not None else "NOT_RUN",
            "OBJECTIVE": cp_sat.objective if cp_sat is not None else None,
            "CERTIFIED_UPPER_BOUND": (
                cp_sat.certified_upper_bound if cp_sat is not None else None
            ),
            "TIME_LIMIT_SECONDS": CP_SAT_TIME_LIMIT_SECONDS,
            "WORKERS": CP_SAT_WORKERS,
            "WALL_TIME_SECONDS": cp_sat.wall_time_seconds if cp_sat is not None else None,
            "SCOPE": (
                cp_sat.scope
                if cp_sat is not None
                else "smallest surviving slice h=45, M=94; not run"
            ),
            "REPORTED_WALL_TIME_EXCEEDS_FIXED_BUDGET": (
                cp_sat is not None
                and cp_sat.wall_time_seconds > CP_SAT_TIME_LIMIT_SECONDS
            ),
            "FEASIBLE_IS_NOT_PROOF": True,
        },
        "NEW_PORTFOLIO_SEARCH_STARTED": "NO",
        "PRODUCTION_MUTATION": "NONE",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--run-cpsat",
        action="store_true",
        help="run the fixed-budget solver on the h=45, M=94 residual only",
    )
    arguments = parser.parse_args()
    cp_sat = run_residual_cpsat() if arguments.run_cpsat else None
    print(json.dumps(result_record(cp_sat), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()


__all__ = [
    "BASE_HEAD",
    "BASE_TREE",
    "CP_SAT_RANDOM_SEED",
    "CP_SAT_TIME_LIMIT_SECONDS",
    "CP_SAT_WORKERS",
    "EXPECTED_PAIR_COUNTS",
    "THREE_EDGE_MOTIF_DEGREES",
    "MultiplicityWitness",
    "ThreeEdgeWitness",
    "balanced_pair_mass",
    "classify_three_edge_motif",
    "minimum_mass_for_heavy_count",
    "minimum_s2_for_heavy_count",
    "multiplicity_witness",
    "pair_costs",
    "pair_reuse_floor",
    "result_record",
    "run_residual_cpsat",
    "three_edge_motif_witness",
    "three_edge_motif_witnesses",
    "ticket_overlap_degree_cap_at_mass_94",
    "triple_profile_cap",
    "winning_ticket_cap",
]
