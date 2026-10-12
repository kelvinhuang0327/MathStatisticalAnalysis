"""Certified upper bounds for K=20 portfolios with heavy ticket pairs.

The models optimize over necessary overlap constraints and triple-event caps.
They do not enumerate portfolios or construct candidate tickets.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from functools import cache
from itertools import combinations, product
from math import ceil, comb, isfinite
from typing import Any, cast

from lottolab.research.b649_k20_outside_min_s2_global_penalty_bound_r1 import (
    DRAW_SIZE,
    INCUMBENT,
    PAIR_COUNT,
    POOL_SIZE,
    PORTFOLIO_S1,
    SINGLE_TICKET_OUTCOMES,
    TICKET_COUNT,
    TRIPLE_COUNT,
    minimum_pair_overlap_mass,
    pair_intersection_table,
    triple_intersection_count,
)

BASE_HEAD = "909697cbb1fc53b9f9653f6d4a17c875297787b9"
R1_LOW_OVERLAP_BOUND = 311_435_293
EXPECTED_PAIR_COUNTS = (107_800, 574_000, 1_695_988, 3_469_942, 6_224_512, 10_776_332, 18_611_432)
EXPECTED_MIN_EXTRA_S2 = 466_200
EXPECTED_HEAVY_PAIR_EXCESS = 655_788
SUPPLIED_C_PRELIMINARY_BOUND = 312_807_298
CP_SAT_TIME_LIMIT_SECONDS = 120.0
CP_SAT_WORKERS = 1
HEAVY_PAIR = (0, 1)


def _cp_model_api() -> Any:
    from ortools.sat.python import cp_model

    return cast(Any, cp_model)


@dataclass(frozen=True)
class CpSatEvidence:
    """A CP-SAT observation retaining the certified maximization bound."""

    status: str
    objective: int | None
    certified_objective_bound: int
    upper_bound: int
    time_limit_seconds: float
    workers: int


@dataclass(frozen=True)
class CWedgeCertificate:
    """Degree and special-pair recovery ceilings for Family C."""

    upper_bound: int
    s2_at_maximum: int
    s3_upper_bound: int
    ordinary_edge_count: int
    heavy_endpoint_spokes: int
    common_neighbors: int
    wedge_count_upper: int
    regular_wedge_count_upper: int
    special_triple_recovery_upper: int


def exact_pair_costs() -> tuple[int, ...]:
    """Return the exact simultaneous-win counts for pair overlaps 0 through 6."""

    counts = pair_intersection_table()
    if counts != EXPECTED_PAIR_COUNTS:
        raise AssertionError("exact pair-intersection counts changed")
    return counts


def pair_cost_convexity_excess(pair_costs: tuple[int, ...] | None = None) -> tuple[int, ...]:
    """Return each pair cost's excess over the overlap-zero/one tangent."""

    costs = exact_pair_costs() if pair_costs is None else pair_costs
    if len(costs) != DRAW_SIZE + 1:
        raise ValueError("pair-cost table must cover overlaps 0 through draw_size")
    first_difference = costs[1] - costs[0]
    return tuple(cost - costs[0] - overlap * first_difference for overlap, cost in enumerate(costs))


def exact_triple_profile_table() -> tuple[tuple[int, int, int, int], ...]:
    """Return the 343 maxima over feasible triple-common Venn cells."""

    table: list[tuple[int, int, int, int]] = []
    for ab, ac, bc in product(range(DRAW_SIZE + 1), repeat=3):
        overlaps = (ab, ac, bc)
        feasible_counts: list[int] = []
        for common in range(min(overlaps) + 1):
            try:
                feasible_counts.append(triple_intersection_count(overlaps, common))
            except ValueError:
                continue
        table.append((ab, ac, bc, max(feasible_counts, default=0)))
    if len(table) != 343:
        raise AssertionError("the ordered triple-profile table must contain 343 rows")
    return tuple(table)


def triple_profile_table_sha256() -> str:
    """Hash the canonical JSON representation of the ordered 343-row table."""

    payload = json.dumps(exact_triple_profile_table(), separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


@cache
def _triple_profile_maxima() -> dict[tuple[int, int, int], int]:
    return {(ab, ac, bc): maximum for ab, ac, bc, maximum in exact_triple_profile_table()}


@cache
def _exact_triple_rows() -> tuple[tuple[int, int, int, int, int], ...]:
    """Return feasible (three overlaps, common count, exact triple count) rows."""

    rows: list[tuple[int, int, int, int, int]] = []
    for ab, ac, bc in product(range(DRAW_SIZE + 1), repeat=3):
        for common in range(min(ab, ac, bc) + 1):
            try:
                count = triple_intersection_count((ab, ac, bc), common)
            except ValueError:
                continue
            rows.append((ab, ac, bc, common, count))
    return tuple(rows)


def exact_family_s2_floors(
    pair_costs: tuple[int, ...] | None = None,
) -> dict[str, int]:
    """Return exact S2 lower floors for A, B, and C from frequency convexity."""

    costs = exact_pair_costs() if pair_costs is None else pair_costs
    minimum_mass, frequencies = minimum_pair_overlap_mass()
    if minimum_mass != 93 or frequencies != (2,) * 27 + (3,) * 22:
        raise AssertionError("the K20 repeated-label frequency floor changed")
    c0, c1 = costs[:2]
    baseline = (PAIR_COUNT - minimum_mass) * c0 + minimum_mass * c1
    excess = pair_cost_convexity_excess(costs)
    floors = {
        "OUTSIDE_MIN_S2_BASELINE": baseline,
        "A_AT_LEAST_ONE_OVERLAP_3": baseline + excess[3],
        "B_AT_LEAST_TWO_OVERLAP_2": baseline + 2 * excess[2],
        "C_EXACTLY_ONE_OVERLAP_2": baseline + excess[2],
    }
    if baseline != 63_838_600:
        raise AssertionError("the minimum S2 baseline changed")
    return floors


def _ceil_div(numerator: int, denominator: int) -> int:
    return (numerator + denominator - 1) // denominator


def preliminary_family_bounds(pair_costs: tuple[int, ...] | None = None) -> dict[str, int]:
    """Compute the reproducible preliminary A/B bounds and their S2 floors."""

    costs = exact_pair_costs() if pair_costs is None else pair_costs
    floors = exact_family_s2_floors(costs)
    a_floor = floors["A_AT_LEAST_ONE_OVERLAP_3"]
    b_floor = floors["B_AT_LEAST_TWO_OVERLAP_2"]
    first_heavy_floor = floors["C_EXACTLY_ONE_OVERLAP_2"]
    return {
        **floors,
        "A_HUNTER_STAR_LOWER_BOUND": _ceil_div(2 * a_floor, TICKET_COUNT),
        "B_HUNTER_STAR_LOWER_BOUND": _ceil_div(2 * b_floor, TICKET_COUNT),
        "A_PRELIMINARY_BOUND": PORTFOLIO_S1 - _ceil_div(2 * a_floor, TICKET_COUNT),
        "B_PRELIMINARY_BOUND": PORTFOLIO_S1 - _ceil_div(2 * b_floor, TICKET_COUNT),
        "C_S2_FLOOR": first_heavy_floor,
    }


def c_wedge_certificate() -> CWedgeCertificate:
    """Bound C by maximizing a degree-based S3 ceiling over its edge counts.

    Delete the unique overlap-2 edge to form a simple graph. Wedges from a
    common neighbor of the heavy pair belong to the 18 special triples and
    are removed from the ordinary S3 wedge budget. The remaining graph wedges
    receive the exact triangle cap 20,272/3; the special triples use their
    exact 343-table profile maxima. Degree convexity bounds every graph at a
    fixed ordinary edge count and endpoint-spoke count.
    """

    costs = exact_pair_costs()
    maxima = _triple_profile_maxima()
    if (maxima[(2, 0, 0)], maxima[(2, 1, 0)], maxima[(2, 1, 1)]) != (
        2_240,
        14_420,
        56_126,
    ):
        raise AssertionError("heavy-pair triple recovery table changed")

    best: CWedgeCertificate | None = None
    edge_penalty = costs[1] - costs[0]
    for ordinary_edges in range(91, PAIR_COUNT):
        for spokes in range(37):
            other_degree_sum = 2 * ordinary_edges - spokes
            if not 0 <= other_degree_sum <= 18 * (TICKET_COUNT - 1):
                continue

            first_degree = min(spokes, TICKET_COUNT - 2)
            second_degree = spokes - first_degree
            if second_degree > TICKET_COUNT - 2:
                continue
            endpoint_wedges = comb(first_degree, 2) + comb(second_degree, 2)
            full_degrees, remainder = divmod(other_degree_sum, TICKET_COUNT - 1)
            other_wedges = (
                full_degrees * comb(TICKET_COUNT - 1, 2) + comb(remainder, 2)
            )
            wedge_count = endpoint_wedges + other_wedges

            for common_neighbors in range(max(0, spokes - 18), min(18, spokes // 2) + 1):
                regular_wedges = wedge_count - common_neighbors
                if regular_wedges < 0:
                    continue
                ordinary_recovery = (20_272 * regular_wedges) // 3
                special_recovery = (
                    maxima[(2, 0, 0)] * (18 - spokes + common_neighbors)
                    + maxima[(2, 1, 0)] * (spokes - 2 * common_neighbors)
                    + maxima[(2, 1, 1)] * common_neighbors
                )
                s3_upper = ordinary_recovery + special_recovery
                s2 = (
                    PAIR_COUNT * costs[0]
                    + (costs[2] - costs[0])
                    + edge_penalty * ordinary_edges
                )
                candidate = CWedgeCertificate(
                    upper_bound=PORTFOLIO_S1 - s2 + s3_upper,
                    s2_at_maximum=s2,
                    s3_upper_bound=s3_upper,
                    ordinary_edge_count=ordinary_edges,
                    heavy_endpoint_spokes=spokes,
                    common_neighbors=common_neighbors,
                    wedge_count_upper=wedge_count,
                    regular_wedge_count_upper=regular_wedges,
                    special_triple_recovery_upper=special_recovery,
                )
                if best is None or candidate.upper_bound > best.upper_bound:
                    best = candidate

    if best is None:
        raise AssertionError("Family C degree relaxation has no feasible summary")
    return best


def certified_integer_upper_bound(best_objective_bound: float) -> int:
    """Ceil a finite maximization bound; never substitute a feasible objective."""

    if not isfinite(best_objective_bound):
        raise ValueError("CP-SAT did not return a finite certified objective bound")
    return ceil(best_objective_bound)


def _finish_solver_run(solver: Any, status_code: int, constant: int) -> CpSatEvidence:
    cp_model_api = _cp_model_api()
    status = str(solver.StatusName(status_code))
    objective = None
    if status_code in (cp_model_api.OPTIMAL, cp_model_api.FEASIBLE):
        objective = round(float(solver.ObjectiveValue()))
    objective_bound = certified_integer_upper_bound(float(solver.BestObjectiveBound()))
    return CpSatEvidence(
        status=status,
        objective=objective,
        certified_objective_bound=objective_bound,
        upper_bound=constant + objective_bound,
        time_limit_seconds=CP_SAT_TIME_LIMIT_SECONDS,
        workers=CP_SAT_WORKERS,
    )


def solve_c_preliminary_bound() -> CpSatEvidence:
    """Bound C by optimizing its simple-overlap graph relaxation for 120 seconds."""

    cp_model_api = _cp_model_api()
    model: Any = cp_model_api.CpModel()
    normal_edges: dict[tuple[int, int], Any] = {}
    for edge in combinations(range(TICKET_COUNT), 2):
        if edge == HEAVY_PAIR:
            continue
        normal_edges[edge] = model.NewBoolVar(f"e_{edge[0]}_{edge[1]}")
    model.Add(sum(normal_edges.values()) >= 91)

    maxima = _triple_profile_maxima()
    triple_values: list[Any] = []
    for first, second, third in combinations(range(TICKET_COUNT), 3):
        edge_keys = ((first, second), (first, third), (second, third))
        value = model.NewIntVar(0, SINGLE_TICKET_OUTCOMES, f"j_{first}_{second}_{third}")
        if HEAVY_PAIR in edge_keys:
            free_keys = tuple(edge for edge in edge_keys if edge != HEAVY_PAIR)
            rows = [
                (2, left, right, maxima[(2, left, right)])
                for left, right in product((0, 1), repeat=2)
            ]
            model.AddAllowedAssignments(
                [normal_edges[free_keys[0]], normal_edges[free_keys[1]], value],
                [(row[1], row[2], row[3]) for row in rows],
            )
        else:
            rows = [
                (ab, ac, bc, maxima[(ab, ac, bc)])
                for ab, ac, bc in product((0, 1), repeat=3)
            ]
            model.AddAllowedAssignments(
                [
                    normal_edges[edge_keys[0]],
                    normal_edges[edge_keys[1]],
                    normal_edges[edge_keys[2]],
                    value,
                ],
                rows,
            )
        triple_values.append(value)

    edge_penalty = exact_pair_costs()[1] - exact_pair_costs()[0]
    model.Maximize(sum(triple_values) - edge_penalty * sum(normal_edges.values()))
    base_constant = (
        PORTFOLIO_S1
        - PAIR_COUNT * exact_pair_costs()[0]
        - (exact_pair_costs()[2] - exact_pair_costs()[0])
    )
    solver: Any = cp_model_api.CpSolver()
    solver.parameters.max_time_in_seconds = CP_SAT_TIME_LIMIT_SECONDS
    solver.parameters.num_search_workers = CP_SAT_WORKERS
    solver.parameters.random_seed = 0
    return _finish_solver_run(solver, solver.Solve(model), base_constant)


def _profile_max_rows() -> tuple[tuple[int, int, int, int], ...]:
    feasible = {(ab, ac, bc) for ab, ac, bc, _, _ in _exact_triple_rows()}
    maxima = _triple_profile_maxima()
    return tuple((*profile, maxima[profile]) for profile in sorted(feasible))


def _threshold_flags(
    model: Any,
    overlaps: dict[tuple[int, int], Any],
    threshold: int,
    prefix: str,
) -> list[Any]:
    flags: list[Any] = []
    for edge, overlap in overlaps.items():
        flag = model.NewBoolVar(f"{prefix}_{edge[0]}_{edge[1]}")
        model.Add(overlap >= threshold).OnlyEnforceIf(flag)
        model.Add(overlap < threshold).OnlyEnforceIf(flag.Not())
        flags.append(flag)
    return flags


def solve_ab_tightening_attempt() -> CpSatEvidence:
    """Run one joint A/B relaxation with pair costs, incidence moments, and exact S3 caps."""

    cp_model_api = _cp_model_api()
    model: Any = cp_model_api.CpModel()
    overlaps: dict[tuple[int, int], Any] = {}
    pair_costs: list[Any] = []
    cost_rows = [(overlap, count) for overlap, count in enumerate(exact_pair_costs())]
    for edge in combinations(range(TICKET_COUNT), 2):
        overlap = model.NewIntVar(0, DRAW_SIZE, f"r_{edge[0]}_{edge[1]}")
        cost = model.NewIntVar(
            min(EXPECTED_PAIR_COUNTS),
            max(EXPECTED_PAIR_COUNTS),
            f"c_{edge[0]}_{edge[1]}",
        )
        model.AddAllowedAssignments([overlap, cost], cost_rows)
        overlaps[edge] = overlap
        pair_costs.append(cost)

    heavy2 = _threshold_flags(model, overlaps, 2, "h2")
    heavy3 = _threshold_flags(model, overlaps, 3, "h3")
    choose_a = model.NewBoolVar("family_a_selected")
    choose_b = model.NewBoolVar("family_b_selected")
    model.Add(choose_a + choose_b >= 1)
    model.Add(sum(heavy3) >= choose_a)
    model.Add(sum(heavy2) >= 2 * choose_b)

    frequency_counts = [
        model.NewIntVar(0, POOL_SIZE, f"labels_with_frequency_{frequency}")
        for frequency in range(TICKET_COUNT + 1)
    ]
    model.Add(sum(frequency_counts) == POOL_SIZE)
    model.Add(
        sum(frequency * frequency_counts[frequency] for frequency in range(TICKET_COUNT + 1))
        == DRAW_SIZE * TICKET_COUNT
    )
    model.Add(
        sum(
            comb(frequency, 2) * frequency_counts[frequency]
            for frequency in range(TICKET_COUNT + 1)
        )
        == sum(overlaps.values())
    )

    profile_rows = _profile_max_rows()
    triple_values: list[Any] = []
    for first, second, third in combinations(range(TICKET_COUNT), 3):
        edge_keys = ((first, second), (first, third), (second, third))
        value = model.NewIntVar(0, SINGLE_TICKET_OUTCOMES, f"j_{first}_{second}_{third}")
        model.AddAllowedAssignments(
            [overlaps[edge_keys[0]], overlaps[edge_keys[1]], overlaps[edge_keys[2]], value],
            list(profile_rows),
        )
        triple_values.append(value)

    model.Maximize(PORTFOLIO_S1 - sum(pair_costs) + sum(triple_values))
    solver: Any = cp_model_api.CpSolver()
    solver.parameters.max_time_in_seconds = CP_SAT_TIME_LIMIT_SECONDS
    solver.parameters.num_search_workers = CP_SAT_WORKERS
    solver.parameters.random_seed = 0
    return _finish_solver_run(solver, solver.Solve(model), 0)


def preliminary_result_record(c_run: CpSatEvidence) -> dict[str, Any]:
    """Build the durable preliminary record before the A/B tightening attempt."""

    costs = exact_pair_costs()
    excess = pair_cost_convexity_excess(costs)
    bounds = preliminary_family_bounds(costs)
    c_certificate = c_wedge_certificate()
    c_bound = min(c_run.upper_bound, c_certificate.upper_bound)
    a_bound = bounds["A_PRELIMINARY_BOUND"]
    b_bound = bounds["B_PRELIMINARY_BOUND"]
    heavy_bound = max(a_bound, b_bound, c_bound)
    outside_bound = max(R1_LOW_OVERLAP_BOUND, heavy_bound)
    success_a = all(bound <= INCUMBENT for bound in (a_bound, b_bound, c_bound))
    success_b = c_bound <= INCUMBENT and heavy_bound < 357_972_121
    triple_table = exact_triple_profile_table()
    return {
        "TASK_ID": "B649_K20_HEAVY_PAIR_DEFECT_GLOBAL_BOUND_R2",
        "TASK_STATUS": "PRELIMINARY_BOUNDS_REPRODUCED_WITH_STRONGER_C_CERTIFICATE",
        "BASE_HEAD": BASE_HEAD,
        "INCUMBENT": INCUMBENT,
        "PORTFOLIO_S1": PORTFOLIO_S1,
        "TICKET_PAIR_COUNT": PAIR_COUNT,
        "TICKET_TRIPLE_COUNT": TRIPLE_COUNT,
        "PAIR_INTERSECTION_COUNTS_BY_OVERLAP": list(costs),
        "PAIR_INTERSECTION_COSTS": list(costs),
        "PAIR_COST_CONVEXITY_EXCESS": list(excess),
        "MIN_EXTRA_S2_OUTSIDE_MINIMUM": costs[1] - costs[0],
        "HEAVY_PAIR_EXCESS_MIN": excess[2],
        "REPEATED_LABEL_FREQUENCY_FLOOR": {
            "INCIDENCES": DRAW_SIZE * TICKET_COUNT,
            "POOL_SIZE": POOL_SIZE,
            "PAIR_OVERLAP_MASS": 93,
            "FREQUENCIES": {"2": 27, "3": 22},
        },
        "FAMILY_S2_FLOORS": {
            "A": bounds["A_AT_LEAST_ONE_OVERLAP_3"],
            "B": bounds["B_AT_LEAST_TWO_OVERLAP_2"],
            "C": bounds["C_EXACTLY_ONE_OVERLAP_2"],
        },
        "FAMILIES": {
            "A": {
                "DEFINITION": "at least one pair overlap >=3",
                "S2_FLOOR": bounds["A_AT_LEAST_ONE_OVERLAP_3"],
                "HUNTER_STAR_LOWER_BOUND": bounds["A_HUNTER_STAR_LOWER_BOUND"],
                "PRELIMINARY_UPPER_BOUND": a_bound,
                "STATUS": "UNRESOLVED" if a_bound > INCUMBENT else "CLOSED",
            },
            "B": {
                "DEFINITION": "at least two heavy pairs with overlap >=2",
                "S2_FLOOR": bounds["B_AT_LEAST_TWO_OVERLAP_2"],
                "HUNTER_STAR_LOWER_BOUND": bounds["B_HUNTER_STAR_LOWER_BOUND"],
                "PRELIMINARY_UPPER_BOUND": b_bound,
                "STATUS": "UNRESOLVED" if b_bound > INCUMBENT else "CLOSED",
            },
            "C": {
                "DEFINITION": "exactly one pair overlap=2 and every other pair overlap<=1",
                "S2_FLOOR": bounds["C_EXACTLY_ONE_OVERLAP_2"],
                "PRELIMINARY_UPPER_BOUND": c_bound,
                "SUPPLIED_REFERENCE_BOUND": SUPPLIED_C_PRELIMINARY_BOUND,
                "REFERENCE_BOUND_REPRODUCED_EXACTLY": c_bound == SUPPLIED_C_PRELIMINARY_BOUND,
                "REFERENCE_BOUND_DOMINATED": c_bound <= SUPPLIED_C_PRELIMINARY_BOUND,
                "STATUS": "UNRESOLVED" if c_bound > INCUMBENT else "CLOSED",
                "CERTIFICATE_FORMULAS": {
                    "DOMAIN": (
                        "E=91..189 ordinary edges; x=0..36 heavy-endpoint spokes; "
                        "t=max(0,x-18)..min(18,floor(x/2)); 0<=2E-x<=342"
                    ),
                    "WEDGE_DEGREE_CEILING": (
                        "W <= C(min(x,18),2)+C(x-min(x,18),2) "
                        "+ q*C(19,2)+C(r,2), where (q,r)=divmod(2E-x,19)"
                    ),
                    "S3_CEILING": (
                        "floor(20272*(W-t)/3) + 2240*(18-x+t) "
                        "+ 14420*(x-2t) + 56126*t"
                    ),
                    "S2_EXACT": (
                        "190*I(0)+(I(2)-I(0))+(I(1)-I(0))*E"
                    ),
                    "COVERAGE_CEILING": "S1-S2+S3",
                },
                "WEDGE_CERTIFICATE": asdict(c_certificate),
                "CP_SAT": asdict(c_run),
            },
        },
        "TRIPLE_PROFILE_TABLE": {
            "PROFILE_COUNT": len(triple_table),
            "CANONICAL_ORDER": "AB_AC_BC, each coordinate 0..6",
            "SHA256_CANONICAL_JSON": triple_profile_table_sha256(),
        },
        "R1_PAIR_OVERLAP_AT_MOST_ONE_FAMILY": {
            "UPPER_BOUND": R1_LOW_OVERLAP_BOUND,
            "STATUS": "CLOSED",
            "RECOMPUTED": False,
        },
        "PRELIMINARY_HEAVY_FAMILY_UPPER_BOUND": heavy_bound,
        "PRELIMINARY_OUTSIDE_MIN_S2_UPPER_BOUND": outside_bound,
        "PRELIMINARY_GAP": outside_bound - INCUMBENT,
        "SUCCESS_A": success_a,
        "SUCCESS_B": success_b,
        "CLOSED_FAMILIES": [
            name
            for name, bound in (("A", a_bound), ("B", b_bound), ("C", c_bound))
            if bound <= INCUMBENT
        ],
        "UNRESOLVED_FAMILY": [
            name
            for name, bound in (("A", a_bound), ("B", b_bound), ("C", c_bound))
            if bound > INCUMBENT
        ],
        "OUTSIDE_MIN_S2_UPPER_BOUND": outside_bound,
        "OUTSIDE_MIN_S2_STATUS": "CLOSED" if success_a else "OPEN",
        "REMAINING_GAP": outside_bound - INCUMBENT,
        "CP_SAT_STATUS": c_run.status,
        "CP_SAT_OBJECTIVE": c_run.objective,
        "CP_SAT_CERTIFIED_BOUND": c_run.upper_bound,
        "CP_SAT_OBJECTIVE_SEMANTICS": (
            "S3_max-(I(1)-I(0))*ordinary_edge_count; the feasible objective was not used as proof"
        ),
        "AB_TIGHTENING_ATTEMPT": "NOT_STARTED",
        "NEW_PORTFOLIO_SEARCH_STARTED": "NO",
        "PRODUCTION_MUTATION": "NONE",
    }


def apply_ab_tightening_result(
    preliminary: dict[str, Any], evidence: CpSatEvidence
) -> dict[str, Any]:
    """Apply the joint A/B certified bound without using its feasible objective."""

    result = dict(preliminary)
    families = dict(result["FAMILIES"])
    joint_bound = evidence.upper_bound
    for name in ("A", "B"):
        family = dict(families[name])
        family["TIGHTENED_UPPER_BOUND"] = min(family["PRELIMINARY_UPPER_BOUND"], joint_bound)
        family["UPPER_BOUND"] = family["TIGHTENED_UPPER_BOUND"]
        family["STATUS"] = "UNRESOLVED" if family["UPPER_BOUND"] > INCUMBENT else "CLOSED"
        families[name] = family
    c_family = dict(families["C"])
    c_family["UPPER_BOUND"] = c_family["PRELIMINARY_UPPER_BOUND"]
    families["C"] = c_family

    a_bound = int(families["A"]["UPPER_BOUND"])
    b_bound = int(families["B"]["UPPER_BOUND"])
    c_bound = int(families["C"]["UPPER_BOUND"])
    heavy_bound = max(a_bound, b_bound, c_bound)
    outside_bound = max(R1_LOW_OVERLAP_BOUND, heavy_bound)
    success_a = all(bound <= INCUMBENT for bound in (a_bound, b_bound, c_bound))
    success_b = c_bound <= INCUMBENT and heavy_bound < 357_972_121
    result.update(
        {
            "TASK_STATUS": (
                "ALL_OUTSIDE_MIN_S2_FAMILIES_CLOSED"
                if success_a
                else "BOUNDED_WITH_OPEN_A_OR_B"
            ),
            "FAMILIES": families,
            "AB_TIGHTENING_ATTEMPT": {
                "STATUS": "IMPROVED" if joint_bound < max(
                    int(preliminary["FAMILIES"]["A"]["PRELIMINARY_UPPER_BOUND"]),
                    int(preliminary["FAMILIES"]["B"]["PRELIMINARY_UPPER_BOUND"]),
                ) else "NO_IMPROVEMENT",
                "METHOD": (
                    "joint overlap-cost CP-SAT relaxation; repeated-label frequency histogram; "
                    "exact 343-profile S3 ceilings"
                ),
                "CERTIFIED_JOINT_AB_UPPER_BOUND": joint_bound,
                "CP_SAT": asdict(evidence),
            },
            "SUCCESS_A": success_a,
            "SUCCESS_B": success_b,
            "CLOSED_FAMILIES": [
                name for name, family in families.items() if family["STATUS"] == "CLOSED"
            ],
            "UNRESOLVED_FAMILY": [
                name for name, family in families.items() if family["STATUS"] == "UNRESOLVED"
            ],
            "HEAVY_FAMILY_UPPER_BOUND": heavy_bound,
            "FAMILY_A_BOUND": a_bound,
            "FAMILY_B_BOUND": b_bound,
            "FAMILY_C_BOUND": c_bound,
            "OUTSIDE_MIN_S2_UPPER_BOUND": outside_bound,
            "OUTSIDE_MIN_S2_STATUS": "CLOSED" if success_a else "OPEN",
            "REMAINING_GAP": outside_bound - INCUMBENT,
            "NEW_PORTFOLIO_SEARCH_STARTED": "NO",
            "PRODUCTION_MUTATION": "NONE",
        }
    )
    return result


__all__ = [
    "BASE_HEAD",
    "CP_SAT_TIME_LIMIT_SECONDS",
    "CP_SAT_WORKERS",
    "EXPECTED_HEAVY_PAIR_EXCESS",
    "EXPECTED_MIN_EXTRA_S2",
    "EXPECTED_PAIR_COUNTS",
    "INCUMBENT",
    "R1_LOW_OVERLAP_BOUND",
    "SUPPLIED_C_PRELIMINARY_BOUND",
    "CWedgeCertificate",
    "CpSatEvidence",
    "apply_ab_tightening_result",
    "c_wedge_certificate",
    "certified_integer_upper_bound",
    "exact_family_s2_floors",
    "exact_pair_costs",
    "exact_triple_profile_table",
    "pair_cost_convexity_excess",
    "preliminary_family_bounds",
    "preliminary_result_record",
    "solve_ab_tightening_attempt",
    "solve_c_preliminary_bound",
    "triple_profile_table_sha256",
]
