"""Exact anchor-incidence and outside-collision bound for K20, r_max = 3.

The module enumerates all local ticket types around a pair of tickets with
three shared labels, then applies an exact finite weighted-forest census to
the fully outside tickets. It counts outcome events only; it never builds or
searches portfolios and does not use a solver.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import cache
from math import comb
from typing import Any

from lottolab.research.b649_k20_outside_min_s2_global_penalty_bound_r1 import (
    DRAW_SIZE,
    INCUMBENT,
    POOL_SIZE,
    PORTFOLIO_S1,
    TICKET_COUNT,
    pair_intersection_table,
    triple_intersection_count,
)

BASE_HEAD = "dc2c5760d9b63cffb1ccc7435b42d2c12f07d80b"
TASK_BRANCH = "codex/b649-k20-r3-anchor-incidence-bound-r5"
ANCHOR_OVERLAP = 3
OUTSIDE_TICKET_COUNT = TICKET_COUNT - 2
OUTSIDE_LABEL_CAPACITY = POOL_SIZE - (2 * DRAW_SIZE - ANCHOR_OVERLAP)

CURRENT_R3_BOUND = 356_667_548
UNCORRECTED_R3_BOUND = 357_241_548
FROZEN_R4_BOUND = 354_779_928
FROZEN_R5_BOUND = 350_778_728
FROZEN_R6_BOUND = 343_869_728

EXPECTED_PAIR_COUNTS = (
    107_800,
    574_000,
    1_695_988,
    3_469_942,
    6_224_512,
    10_776_332,
    18_611_432,
)
EXPECTED_GOOD_TRIPLES = (0, 2_240, 9_485)
EXPECTED_GOOD_PAIR_RESIDUAL_FLOORS = (574_000, 1_691_508, 3_450_972)
WEIGHTS = EXPECTED_GOOD_PAIR_RESIDUAL_FLOORS


@dataclass(frozen=True)
class AnchorIncidenceProfile:
    """Exact local event contribution for one anchor incidence vector."""

    shared: int
    a_only: int
    b_only: int
    outside: int
    overlap_with_a: int
    overlap_with_b: int
    triple_recovery: int
    pair_recovery_cost: int
    net_recovery: int


@dataclass(frozen=True)
class ForestCensus:
    """Minimum weighted-forest correction under a finite edge-count census."""

    good_ticket_count: int
    minimum_label_pair_mass: int
    threshold_pair_counts: tuple[int, int, int]
    threshold_rank_floors: tuple[int, int, int]
    residual_union_penalty: int


@dataclass(frozen=True)
class TradeoffCase:
    """Local-recovery loss plus forced outside-event union correction."""

    good_ticket_count: int
    minimum_label_pair_mass: int
    threshold_pair_counts: tuple[int, int, int]
    threshold_rank_floors: tuple[int, int, int]
    outside_overlap_penalty: int
    non_good_local_loss: int
    total_recovery_reduction: int


@dataclass(frozen=True)
class AnchorTradeoff:
    """Certified r=3 incidence and outside-overlap tradeoff."""

    good_local_net_recovery: int
    maximum_non_good_local_net_recovery: int
    minimum_non_good_local_loss: int
    good_ticket_collision_threshold: int
    minimum_forced_penalty_at_or_above_threshold: int
    guaranteed_recovery_reduction: int
    worst_case_good_ticket_count: int
    cases: tuple[TradeoffCase, ...]


def exact_pair_counts() -> tuple[int, ...]:
    """Return the exact simultaneous-win counts I(0)..I(6)."""

    counts = pair_intersection_table()
    if counts != EXPECTED_PAIR_COUNTS:
        raise AssertionError("the exact K20 pair-intersection table changed")
    return counts


def feasible_anchor_incidence_signatures(
    anchor_overlap: int, ticket_size: int
) -> tuple[tuple[int, int, int, int], ...]:
    """Enumerate (shared, A-only, B-only, outside) ticket-size signatures.

    The anchor pair has ``anchor_overlap`` shared labels and ``ticket_size -
    anchor_overlap`` exclusive labels on each side. The maximum pair overlap
    condition requires each outside ticket to meet either anchor in at most
    ``anchor_overlap`` labels.
    """

    if not 0 <= anchor_overlap <= ticket_size:
        raise ValueError("anchor overlap must be within 0..ticket_size")
    exclusive_capacity = ticket_size - anchor_overlap
    signatures: list[tuple[int, int, int, int]] = []
    for shared in range(anchor_overlap + 1):
        for a_only in range(exclusive_capacity + 1):
            if shared + a_only > anchor_overlap:
                continue
            for b_only in range(exclusive_capacity + 1):
                if shared + b_only > anchor_overlap:
                    continue
                outside = ticket_size - shared - a_only - b_only
                if outside >= 0:
                    signatures.append((shared, a_only, b_only, outside))
    return tuple(signatures)


@cache
def anchor_incidence_profiles() -> tuple[AnchorIncidenceProfile, ...]:
    """Compute exact pair/triple contributions for all K20 anchor types."""

    pair_counts = exact_pair_counts()
    profiles: list[AnchorIncidenceProfile] = []
    for shared, a_only, b_only, outside in feasible_anchor_incidence_signatures(
        ANCHOR_OVERLAP, DRAW_SIZE
    ):
        overlap_with_a = shared + a_only
        overlap_with_b = shared + b_only
        triple = triple_intersection_count(
            (ANCHOR_OVERLAP, overlap_with_a, overlap_with_b), shared
        )
        pair_cost = pair_counts[overlap_with_a] + pair_counts[overlap_with_b]
        profiles.append(
            AnchorIncidenceProfile(
                shared=shared,
                a_only=a_only,
                b_only=b_only,
                outside=outside,
                overlap_with_a=overlap_with_a,
                overlap_with_b=overlap_with_b,
                triple_recovery=triple,
                pair_recovery_cost=pair_cost,
                net_recovery=triple - pair_cost,
            )
        )
    return tuple(profiles)


@cache
def _rank_floor(edge_count: int) -> int:
    """Minimum forest rank capable of containing ``edge_count`` edges."""

    if edge_count < 0:
        raise ValueError("edge count must be nonnegative")
    rank = 0
    while comb(rank + 1, 2) < edge_count:
        rank += 1
    return rank


def _minimum_label_pair_mass(good_ticket_count: int) -> int:
    """Minimize sum_l binom(f_l, 2) over 40 outside labels."""

    if not 0 <= good_ticket_count <= OUTSIDE_TICKET_COUNT:
        raise ValueError("good ticket count must be within 0..18")
    quotient, remainder = divmod(DRAW_SIZE * good_ticket_count, OUTSIDE_LABEL_CAPACITY)
    return remainder * comb(quotient + 1, 2) + (
        OUTSIDE_LABEL_CAPACITY - remainder
    ) * comb(quotient, 2)


@cache
def _minimum_forest_census(good_ticket_count: int) -> ForestCensus:
    """Exhaust the exact threshold-edge relaxation for a fixed good count."""

    minimum_mass = _minimum_label_pair_mass(good_ticket_count)
    edge_capacity = comb(good_ticket_count, 2)
    best_penalty: int | None = None
    best_counts: tuple[int, int, int] | None = None
    best_ranks: tuple[int, int, int] | None = None

    # e_t counts pairs sharing at least t outside labels. Every legal graph
    # has e_1 >= e_2 >= e_3 and e_1 + e_2 + e_3 equal to its label-pair mass.
    for e1 in range(edge_capacity + 1):
        rank1 = _rank_floor(e1)
        for e2 in range(e1 + 1):
            rank2 = _rank_floor(e2)
            for e3 in range(e2 + 1):
                if e1 + e2 + e3 < minimum_mass:
                    continue
                rank3 = _rank_floor(e3)
                penalty = (
                    WEIGHTS[0] * rank1
                    + (WEIGHTS[1] - WEIGHTS[0]) * rank2
                    + (WEIGHTS[2] - WEIGHTS[1]) * rank3
                )
                if best_penalty is None or penalty < best_penalty:
                    best_penalty = penalty
                    best_counts = (e1, e2, e3)
                    best_ranks = (rank1, rank2, rank3)

    if best_penalty is None or best_counts is None or best_ranks is None:
        raise AssertionError("the finite outside-overlap census is infeasible")
    return ForestCensus(
        good_ticket_count=good_ticket_count,
        minimum_label_pair_mass=minimum_mass,
        threshold_pair_counts=best_counts,
        threshold_rank_floors=best_ranks,
        residual_union_penalty=best_penalty,
    )


@cache
def anchor_tradeoff() -> AnchorTradeoff:
    """Build the exact 0..18 good-ticket tradeoff and global correction."""

    profiles = anchor_incidence_profiles()
    good_profiles = tuple(
        profile
        for profile in profiles
        if profile.shared == profile.a_only == profile.b_only == 0
    )
    non_good_profiles = tuple(profile for profile in profiles if profile not in good_profiles)
    if len(good_profiles) != 1 or not non_good_profiles:
        raise AssertionError("the anchor-incidence type partition changed")

    good_net = good_profiles[0].net_recovery
    maximum_non_good_net = max(profile.net_recovery for profile in non_good_profiles)
    non_good_loss = good_net - maximum_non_good_net
    collision_threshold = OUTSIDE_LABEL_CAPACITY // DRAW_SIZE + 1
    cases: list[TradeoffCase] = []
    for good_count in range(OUTSIDE_TICKET_COUNT + 1):
        census = _minimum_forest_census(good_count)
        local_loss = (OUTSIDE_TICKET_COUNT - good_count) * non_good_loss
        cases.append(
            TradeoffCase(
                good_ticket_count=good_count,
                minimum_label_pair_mass=census.minimum_label_pair_mass,
                threshold_pair_counts=census.threshold_pair_counts,
                threshold_rank_floors=census.threshold_rank_floors,
                outside_overlap_penalty=census.residual_union_penalty,
                non_good_local_loss=local_loss,
                total_recovery_reduction=local_loss + census.residual_union_penalty,
            )
        )

    worst = min(cases, key=lambda case: case.total_recovery_reduction)
    positive_good_cases = tuple(
        case for case in cases if case.good_ticket_count >= collision_threshold
    )
    minimum_forced_penalty = min(case.outside_overlap_penalty for case in positive_good_cases)

    if (
        len(profiles) != 30
        or good_net != -206_115
        or maximum_non_good_net != -649_005
        or non_good_loss != 442_890
        or collision_threshold != 7
        or minimum_forced_penalty != 1_148_000
        or worst.good_ticket_count != 6
        or worst.total_recovery_reduction != 5_314_680
    ):
        raise AssertionError("the certified K20 r=3 anchor tradeoff changed")

    return AnchorTradeoff(
        good_local_net_recovery=good_net,
        maximum_non_good_local_net_recovery=maximum_non_good_net,
        minimum_non_good_local_loss=non_good_loss,
        good_ticket_collision_threshold=collision_threshold,
        minimum_forced_penalty_at_or_above_threshold=minimum_forced_penalty,
        guaranteed_recovery_reduction=worst.total_recovery_reduction,
        worst_case_good_ticket_count=worst.good_ticket_count,
        cases=tuple(cases),
    )


def revised_r3_bound() -> int:
    """Return the exact r=3 upper bound after the incidence tradeoff."""

    pair_counts = exact_pair_counts()
    profiles = anchor_incidence_profiles()
    tradeoff = anchor_tradeoff()
    good_net = tradeoff.good_local_net_recovery
    local_bound = (
        PORTFOLIO_S1
        - pair_counts[ANCHOR_OVERLAP]
        + OUTSIDE_TICKET_COUNT * good_net
    )
    if local_bound != UNCORRECTED_R3_BOUND:
        raise AssertionError("the uncorrected anchor-pair bound changed")
    bound = local_bound - tradeoff.guaranteed_recovery_reduction
    if bound != 351_926_868 or bound >= CURRENT_R3_BOUND:
        raise AssertionError("the revised r=3 bound failed to improve the certified bound")
    if max(profile.net_recovery for profile in profiles) != good_net:
        raise AssertionError("the fully outside ticket is not the local maximum")
    return bound


def family_a_result_record() -> dict[str, Any]:
    """Build the compact r=3 proof record and frozen Family-A handoff."""

    pair_counts = exact_pair_counts()
    profiles = anchor_incidence_profiles()
    tradeoff = anchor_tradeoff()
    r3_bound = revised_r3_bound()
    family_bound = max(r3_bound, FROZEN_R4_BOUND, FROZEN_R5_BOUND, FROZEN_R6_BOUND)
    return {
        "TASK_ID": "B649_K20_R3_ANCHOR_INCIDENCE_BOUND_R5",
        "TASK_STATUS": "CERTIFIED_R3_BOUND_TIGHTENED",
        "BASE_HEAD": BASE_HEAD,
        "BASE_TREE": "1dd021b0b87fa911c71807cd9e0fa76bf229a5a0",
        "TASK_BRANCH": TASK_BRANCH,
        "INCUMBENT": INCUMBENT,
        "PAIR_INTERSECTION_COUNTS_BY_OVERLAP": list(pair_counts),
        "ANCHOR_INCIDENCE_TYPE_COUNT": len(profiles),
        "LOCAL_TYPE_EXTREMA": {
            "GOOD_PROFILE": [0, 0, 0, DRAW_SIZE, 9_485, 215_600, -206_115],
            "MAXIMUM_NON_GOOD_NET_RECOVERY": (
                tradeoff.maximum_non_good_local_net_recovery
            ),
        },
        "CAPACITY_CONSTRAINTS": {
            "ANCHOR_SHARED_LABELS": 3,
            "ANCHOR_A_ONLY_LABELS": 3,
            "ANCHOR_B_ONLY_LABELS": 3,
            "OUTSIDE_LABELS": OUTSIDE_LABEL_CAPACITY,
            "OUTSIDE_TICKETS": OUTSIDE_TICKET_COUNT,
            "TYPE_RULES": (
                "0<=s<=3; 0<=a,b<=3; s+a<=3; s+b<=3; "
                "o=6-s-a-b>=0"
            ),
            "TYPE_COUNT_CONSTRAINTS": (
                "For integer n_t>=0, sum_t n_t=18; the four coordinate totals "
                "equal their physical-label frequency sums, with at most "
                "3*18 incidences in each 3-label anchor cell and 40*18 outside."
            ),
            "LABEL_FREQUENCIES": (
                "Each of the 3+3+3+40 physical labels has an integer frequency "
                "from 0 through 18 among outside tickets; cell frequency sums "
                "equal the corresponding type-coordinate totals."
            ),
            "PAIRWISE_MAXIMUM_OVERLAP": (
                "For every outside-ticket pair, shared-label counts across the "
                "four cells sum to at most 3; good-ticket pairs therefore share "
                "at most 3 outside labels."
            ),
        },
        "R3_LOCAL_TRADEOFF": {
            "GOOD_LOCAL_NET_RECOVERY": tradeoff.good_local_net_recovery,
            "MAXIMUM_NON_GOOD_LOCAL_NET_RECOVERY": (
                tradeoff.maximum_non_good_local_net_recovery
            ),
            "MINIMUM_NON_GOOD_LOCAL_LOSS": tradeoff.minimum_non_good_local_loss,
            "UNCORRECTED_ANCHOR_BOUND": UNCORRECTED_R3_BOUND,
            "GUARANTEED_RECOVERY_REDUCTION": tradeoff.guaranteed_recovery_reduction,
            "WORST_CASE_GOOD_TICKET_COUNT": tradeoff.worst_case_good_ticket_count,
        },
        "OUTSIDE_OVERLAP_PENALTY": {
            "GOOD_TICKET_COLLISION_THRESHOLD": tradeoff.good_ticket_collision_threshold,
            "MINIMUM_FORCED_PENALTY_AT_OR_ABOVE_THRESHOLD": (
                tradeoff.minimum_forced_penalty_at_or_above_threshold
            ),
            "RESIDUAL_PAIR_FLOORS_BY_OVERLAP": {
                "1": WEIGHTS[0],
                "2": WEIGHTS[1],
                "3": WEIGHTS[2],
            },
            "TRADEOFF_COLUMNS": [
                "good_count",
                "minimum_label_pair_mass",
                "e1",
                "e2",
                "e3",
                "rank1_floor",
                "rank2_floor",
                "rank3_floor",
                "outside_overlap_penalty",
                "non_good_local_loss",
                "total_recovery_reduction",
            ],
            "TRADEOFF_ROWS_ENCODING": (
                "Each row is a comma-separated integer string in column order."
            ),
            "TRADEOFF_BY_GOOD_TICKET_COUNT": [
                ",".join(
                    str(value)
                    for value in (
                        case.good_ticket_count,
                        case.minimum_label_pair_mass,
                        *case.threshold_pair_counts,
                        *case.threshold_rank_floors,
                        case.outside_overlap_penalty,
                        case.non_good_local_loss,
                        case.total_recovery_reduction,
                    )
                )
                for case in tradeoff.cases
            ],
        },
        "R3_PROOF": {
            "LOCAL_RESIDUAL_IDENTITY": (
                "|E_C \\ (E_A union E_B)| = N - I(s+a) - I(s+b) + J(3,s+a,s+b;s)"
            ),
            "ANCHOR_COVER_IDENTITY": (
                "|union E_i| <= S1 - I(3) + sum_C net(C), "
                "where net(C)=J-I(s+a)-I(s+b)"
            ),
            "OUTSIDE_LABEL_PAIR_MASS": (
                "For m good tickets, f_l in 0..m, sum_l f_l=6m over 40 labels, "
                "Q=sum_l binom(f_l,2)=sum_{i<j} d_ij. Convexity gives the "
                "balanced-frequency minimum."
            ),
            "WEIGHTED_FOREST_CENSUS": (
                "With e_t=#pairs sharing at least t outside labels, "
                "e1>=e2>=e3 and e1+e2+e3=Q. A graph of forest rank r has at "
                "most binom(r+1,2) edges, so rank>=rho(e_t), where "
                "rho(e)=min{r:binom(r+1,2)>=e}. The maximum weighted forest "
                "has weight w1*rank(G1)+(w2-w1)*rank(G2)+(w3-w2)*rank(G3). "
                "Exhausting the finite e1,e2,e3 relaxation yields the "
                "recorded residual-union penalty."
            ),
            "RESIDUAL_PAIR_IDENTITY": (
                "|R_C intersect R_D| >= I(d)-2*J(0,0,d); the omitted "
                "four-way anchor intersection is nonnegative."
            ),
            "FOREST_UNION_CORRECTION": (
                "For any forest on good residual events, union size is at most "
                "the sum of event sizes minus the sum of edge intersections."
            ),
            "TRADEOFF": (
                "At m<=6, at least 12 non-good tickets lose 442890 each. "
                "At m>=7, the exact frequency/forest census forces at least "
                "1148000 residual outcomes of outside-overlap correction; the "
                "combined minimum over m=0..18 is 5314680 at m=6."
            ),
        },
        "R3_PRIOR_BOUND": CURRENT_R3_BOUND,
        "R3_BOUND": r3_bound,
        "R4_BOUND": FROZEN_R4_BOUND,
        "R5_BOUND": FROZEN_R5_BOUND,
        "R6_BOUND": FROZEN_R6_BOUND,
        "FAMILY_A_BOUND": family_bound,
        "FAMILY_A_STATUS": "CLOSED" if family_bound <= INCUMBENT else "TIGHTENED_OPEN",
        "IMPROVEMENT_VS_CURRENT_R3_BOUND": CURRENT_R3_BOUND - r3_bound,
        "REMAINING_GAP": family_bound - INCUMBENT,
        "SUCCESS_A": family_bound <= INCUMBENT,
        "SUCCESS_B": r3_bound < CURRENT_R3_BOUND,
        "SOLVER_STATUS": "NOT_NEEDED_ANALYTIC_EXACT_FINITE_CENSUS",
        "SOLVER_CONFIGURED_WALL_LIMIT": "NOT_APPLICABLE",
        "SOLVER_ACTUAL_WALL_TIME": "NOT_APPLICABLE",
        "SOLVER_CERTIFIED_BOUND": None,
        "NEW_PORTFOLIO_SEARCH_STARTED": "NO",
        "PRODUCTION_MUTATION": "NONE",
        "WORKTREE_DISPOSITION": "RETAIN",
    }


if __name__ == "__main__":
    print(json.dumps(family_a_result_record(), indent=2, sort_keys=True))


__all__ = [
    "ANCHOR_OVERLAP",
    "BASE_HEAD",
    "EXPECTED_GOOD_PAIR_RESIDUAL_FLOORS",
    "EXPECTED_GOOD_TRIPLES",
    "EXPECTED_PAIR_COUNTS",
    "TASK_BRANCH",
    "AnchorIncidenceProfile",
    "AnchorTradeoff",
    "ForestCensus",
    "TradeoffCase",
    "anchor_incidence_profiles",
    "anchor_tradeoff",
    "exact_pair_counts",
    "family_a_result_record",
    "feasible_anchor_incidence_signatures",
    "revised_r3_bound",
]
