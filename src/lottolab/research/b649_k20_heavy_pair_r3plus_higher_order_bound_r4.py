"""Tighten the K20 heavy-pair bound with an anchor-neighborhood tradeoff.

For an anchor pair with overlap three, a third ticket disjoint from both
anchors maximizes its local inclusion-exclusion recovery. There can be at
most six such tickets before the 40 labels outside the anchors force two of
them to overlap. That overlap creates at least 574,000 outcomes counted by
both residual events. Tickets that meet an anchor lose more than this amount
in local recovery, so either case improves the previous r=3 bound by 574,000.

This is an outcome-counting proof. It does not construct or search portfolios.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any

from lottolab.research.b649_k20_heavy_pair_r3plus_global_bound_r3 import (
    exact_pair_counts,
    heavy_pair_case,
    local_heavy_pair_profiles,
)
from lottolab.research.b649_k20_outside_min_s2_global_penalty_bound_r1 import (
    DRAW_SIZE,
    INCUMBENT,
    POOL_SIZE,
    PORTFOLIO_S1,
    TICKET_COUNT,
    pair_intersection_count,
    triple_intersection_count,
)

BASE_HEAD = "c16be9ca51e3fbdb2414dc96b77187337425d370"
TASK_BRANCH = "codex/b649-k20-heavy-pair-r3plus-higher-order-bound-r4"
PRIOR_R3_BOUND = 357_241_548
PRIOR_R4_BOUND = 354_779_928
PRIOR_R5_BOUND = 350_778_728
PRIOR_R6_BOUND = 343_869_728
EXPECTED_DISJOINT_ANCHOR_TRIPLES = (0, 2_240, 9_485)


@dataclass(frozen=True)
class CollisionProfile:
    """Exact pair and triple event counts for a forced outside collision."""

    outside_ticket_overlap: int
    pair_intersection: int
    anchor_triple_intersection: int
    residual_pair_intersection_lower_bound: int


@dataclass(frozen=True)
class AnchorTradeoff:
    """Certified local-recovery versus outside-collision tradeoff for r=3."""

    anchor_overlap: int
    outside_label_capacity: int
    ticket_size: int
    good_ticket_collision_threshold: int
    outside_ticket_count: int
    good_local_net_recovery: int
    maximum_non_good_local_net_recovery: int
    minimum_non_good_local_loss: int
    non_good_case_minimum_loss: int
    collision_pair_recovery_floor: int
    guaranteed_recovery_improvement: int
    collision_profiles: tuple[CollisionProfile, ...]


def anchor_tradeoff() -> AnchorTradeoff:
    """Derive the r=3 tradeoff from exact local and event-intersection counts."""

    pair_counts = exact_pair_counts()
    profiles = local_heavy_pair_profiles(3)
    good_profiles = tuple(
        profile
        for profile in profiles
        if profile.left_overlap == 0 and profile.right_overlap == 0
    )
    non_good_profiles = tuple(
        profile
        for profile in profiles
        if profile.left_overlap > 0 or profile.right_overlap > 0
    )
    if len(good_profiles) != 1 or not non_good_profiles:
        raise AssertionError("the exact r=3 local profile partition changed")

    good_net = good_profiles[0].net_recovery
    maximum_non_good_net = max(profile.net_recovery for profile in non_good_profiles)
    non_good_loss = good_net - maximum_non_good_net
    outside_ticket_count = TICKET_COUNT - 2
    anchor_union_size = 2 * DRAW_SIZE - 3
    outside_labels = POOL_SIZE - anchor_union_size
    collision_threshold = outside_labels // DRAW_SIZE + 1
    non_good_count_in_no_collision_case = collision_threshold - 1
    non_good_case_loss = (
        outside_ticket_count - non_good_count_in_no_collision_case
    ) * non_good_loss

    collision_profiles = tuple(
        CollisionProfile(
            outside_ticket_overlap=overlap,
            pair_intersection=pair_intersection_count(overlap),
            anchor_triple_intersection=triple_intersection_count(
                (0, 0, overlap), 0
            ),
            residual_pair_intersection_lower_bound=(
                pair_intersection_count(overlap)
                - 2 * triple_intersection_count((0, 0, overlap), 0)
            ),
        )
        for overlap in range(1, 4)
    )
    if tuple(
        row.anchor_triple_intersection for row in collision_profiles
    ) != EXPECTED_DISJOINT_ANCHOR_TRIPLES:
        raise AssertionError("the exact disjoint-anchor triple counts changed")
    collision_floor = min(
        row.residual_pair_intersection_lower_bound for row in collision_profiles
    )
    improvement = min(non_good_case_loss, collision_floor)

    if (
        pair_counts[3] != 3_469_942
        or good_net != -206_115
        or maximum_non_good_net != -649_005
        or non_good_loss != 442_890
        or outside_labels != 40
        or collision_threshold != 7
        or collision_floor != 574_000
        or non_good_case_loss != 5_314_680
        or improvement != 574_000
    ):
        raise AssertionError("the certified r=3 tradeoff inputs changed")

    return AnchorTradeoff(
        anchor_overlap=3,
        outside_label_capacity=outside_labels,
        ticket_size=DRAW_SIZE,
        good_ticket_collision_threshold=collision_threshold,
        outside_ticket_count=outside_ticket_count,
        good_local_net_recovery=good_net,
        maximum_non_good_local_net_recovery=maximum_non_good_net,
        minimum_non_good_local_loss=non_good_loss,
        non_good_case_minimum_loss=non_good_case_loss,
        collision_pair_recovery_floor=collision_floor,
        guaranteed_recovery_improvement=improvement,
        collision_profiles=collision_profiles,
    )


def revised_r3_bound() -> int:
    """Return the anchor-pair upper bound after the collision correction."""

    tradeoff = anchor_tradeoff()
    old_r3 = heavy_pair_case(3).upper_bound
    bound = (
        PORTFOLIO_S1
        - pair_intersection_count(3)
        + tradeoff.outside_ticket_count * tradeoff.good_local_net_recovery
        - tradeoff.guaranteed_recovery_improvement
    )
    if old_r3 != PRIOR_R3_BOUND or bound != old_r3 - 574_000:
        raise AssertionError("the previous or revised r=3 bound changed")
    return bound


def family_a_result_record() -> dict[str, Any]:
    """Build the compact exact Family-A certificate and handoff fields."""

    pair_counts = exact_pair_counts()
    tradeoff = anchor_tradeoff()
    r3_bound = revised_r3_bound()
    unchanged_bounds = {
        r: heavy_pair_case(r).upper_bound for r in range(4, DRAW_SIZE + 1)
    }
    expected_unchanged = {
        4: PRIOR_R4_BOUND,
        5: PRIOR_R5_BOUND,
        6: PRIOR_R6_BOUND,
    }
    if unchanged_bounds != expected_unchanged:
        raise AssertionError("the frozen r=4..6 certificates changed")
    case_bounds = {3: r3_bound, **unchanged_bounds}
    family_bound = max(case_bounds.values())

    return {
        "TASK_ID": "B649_K20_HEAVY_PAIR_R3PLUS_HIGHER_ORDER_BOUND_R4",
        "TASK_STATUS": "CERTIFIED_FAMILY_A_BOUND_TIGHTENED",
        "BASE_HEAD": BASE_HEAD,
        "TASK_BRANCH": TASK_BRANCH,
        "INCUMBENT": INCUMBENT,
        "PAIR_INTERSECTION_COUNTS_BY_OVERLAP": list(pair_counts),
        "DISJOINT_ANCHOR_TRIPLE_COUNTS_BY_OUTSIDE_OVERLAP": {
            str(row.outside_ticket_overlap): row.anchor_triple_intersection
            for row in tradeoff.collision_profiles
        },
        "R3_PROOF": {
            "LOCAL_RESIDUAL_IDENTITY": (
                "|E_C \\ (E_A union E_B)| = N - I(|A intersect C)| "
                "- I(|B intersect C)| + J(A,B,C)"
            ),
            "ANCHOR_COVER_IDENTITY": (
                "|union E_i| <= S1 - I(3) + sum_C net(C), "
                "where net(C)=J(A,B,C)-I(A,C)-I(B,C)"
            ),
            "GOOD_TICKET_DEFINITION": (
                "C is good iff it is disjoint in labels from both anchors; "
                "good tickets use only the 40 labels outside A union B"
            ),
            "COLLISION_CASE": (
                "At least 7 good six-label tickets force a shared label. "
                "For overlap d in 1..3, residual pair intersection is at least "
                "I(d)-2*J(0,0,d), whose minimum is 574000."
            ),
            "LOW_GOOD_COUNT_CASE": (
                "At most 6 good tickets leaves at least 12 non-good tickets; "
                "each loses at least 442890 local net recovery, for a "
                "5314680 total reduction."
            ),
            "UNION_CORRECTION": (
                "For the forced residual pair C,D, |union R_i| <= "
                "sum_i |R_i| - |R_C intersect R_D|."
            ),
            "GUARANTEED_RECOVERY_REDUCTION": 574_000,
        },
        "R3_ANCHOR_TRADEOFF": asdict(tradeoff),
        "R3_PRIOR_BOUND": PRIOR_R3_BOUND,
        "R3_BOUND": r3_bound,
        "R4_BOUND": unchanged_bounds[4],
        "R5_BOUND": unchanged_bounds[5],
        "R6_BOUND": unchanged_bounds[6],
        "FAMILY_A_BOUND": family_bound,
        "FAMILY_A_STATUS": "CLOSED" if family_bound <= INCUMBENT else "TIGHTENED_OPEN",
        "IMPROVEMENT_VS_PRIOR_BOUND": PRIOR_R3_BOUND - r3_bound,
        "REMAINING_GAP": family_bound - INCUMBENT,
        "SUCCESS_A": family_bound <= INCUMBENT,
        "SUCCESS_B": family_bound < PRIOR_R3_BOUND,
        "CP_SAT_STATUS": "NOT_RUN",
        "CP_SAT_CERTIFIED_BOUND": None,
        "NEW_PORTFOLIO_SEARCH_STARTED": "NO",
        "PRODUCTION_MUTATION": "NONE",
        "WORKTREE_DISPOSITION": "RETAIN",
    }


if __name__ == "__main__":
    print(json.dumps(family_a_result_record(), indent=2, sort_keys=True))
