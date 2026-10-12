"""A conditional local-incidence bound for K20 portfolios with a heavy pair.

The bound anchors on a pair with maximum ticket overlap r >= 3. It counts the
union of the two anchor events exactly, then bounds each other ticket's
outcomes outside that union by exact pair and triple event counts. It never
constructs or searches complete portfolios.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from lottolab.research.b649_k20_outside_min_s2_global_penalty_bound_r1 import (
    DRAW_SIZE,
    INCUMBENT,
    PAIR_COUNT,
    POOL_SIZE,
    PORTFOLIO_S1,
    TICKET_COUNT,
    minimum_pair_overlap_mass,
    pair_intersection_table,
    triple_intersection_count,
)

BASE_HEAD = "12c4e62ae377b6808eb971bd6dd906bc83987918"
TASK_BRANCH = "codex/b649-k20-heavy-pair-r3plus-global-bound-r3"
PRIOR_FAMILY_A_BOUND = 357_841_345
EXPECTED_PAIR_COUNTS = (
    107_800,
    574_000,
    1_695_988,
    3_469_942,
    6_224_512,
    10_776_332,
    18_611_432,
)


@dataclass(frozen=True)
class LocalTripleProfile:
    """One feasible third-ticket incidence profile around an anchor pair."""

    shared_labels: int
    left_only_labels: int
    right_only_labels: int
    outside_labels: int
    left_overlap: int
    right_overlap: int
    triple_recovery: int
    pair_cost_recovery: int
    net_recovery: int


@dataclass(frozen=True)
class HeavyPairCase:
    """Exact local certificate for one value of the maximum pair overlap."""

    maximum_pair_overlap: int
    s2_floor: int
    anchor_pair_intersection: int
    maximum_triple_recovery_per_third_ticket: int
    local_s3_recovery_ceiling: int
    maximum_net_recovery_per_third_ticket: int
    net_maximizing_profile: LocalTripleProfile
    s3_maximizing_profile: LocalTripleProfile
    upper_bound: int


def exact_pair_counts() -> tuple[int, ...]:
    """Recompute and validate the exact simultaneous-win counts I(0)..I(6)."""

    counts = pair_intersection_table()
    if counts != EXPECTED_PAIR_COUNTS:
        raise AssertionError("exact pair-intersection counts changed")
    return counts


def pair_cost_convexity_excess(pair_costs: tuple[int, ...] | None = None) -> tuple[int, ...]:
    """Return I(r) minus the exact overlap-zero/one tangent at each r."""

    costs = exact_pair_counts() if pair_costs is None else pair_costs
    if len(costs) != DRAW_SIZE + 1:
        raise ValueError("pair-cost table must cover overlaps 0 through draw_size")
    first_difference = costs[1] - costs[0]
    return tuple(cost - costs[0] - r * first_difference for r, cost in enumerate(costs))


def exact_s2_floors_by_r() -> dict[int, int]:
    """Return the exact frequency-floor S2 bound for a designated overlap r.

    The 120 ticket-label incidences across 49 numbers force pair-overlap mass
    at least 93, attained by the balanced frequency profile 27*2 + 22*3.
    Convexity excess is nonnegative on every pair, while the designated edge
    contributes at least its exact excess at overlap r.
    """

    minimum_mass, frequencies = minimum_pair_overlap_mass()
    if minimum_mass != 93 or frequencies != (2,) * 27 + (3,) * 22:
        raise AssertionError("the K20 balanced frequency floor changed")
    costs = exact_pair_counts()
    excess = pair_cost_convexity_excess(costs)
    baseline = PAIR_COUNT * costs[0] + minimum_mass * (costs[1] - costs[0])
    if baseline != 63_838_600:
        raise AssertionError("the exact K20 minimum-S2 baseline changed")
    return {r: baseline + excess[r] for r in range(3, DRAW_SIZE + 1)}


def local_heavy_pair_profiles(maximum_overlap: int) -> tuple[LocalTripleProfile, ...]:
    """Enumerate exact local Venn profiles for one third ticket.

    ``shared_labels`` are selected from the r labels common to the anchor
    pair. The two exclusive-label counts are bounded by the anchor tickets'
    remaining ``6-r`` labels. Requiring both anchor overlaps <= r conditions
    this profile on r being the portfolio maximum.
    """

    if not 0 <= maximum_overlap <= DRAW_SIZE:
        raise ValueError("maximum overlap must be within 0..draw_size")
    costs = exact_pair_counts()
    profiles: list[LocalTripleProfile] = []
    exclusive_capacity = DRAW_SIZE - maximum_overlap
    for shared in range(maximum_overlap + 1):
        exclusive_limit = min(exclusive_capacity, maximum_overlap - shared)
        for left_only in range(exclusive_limit + 1):
            for right_only in range(exclusive_limit + 1):
                outside = DRAW_SIZE - shared - left_only - right_only
                if outside < 0:
                    continue
                left_overlap = shared + left_only
                right_overlap = shared + right_only
                triple = triple_intersection_count(
                    (maximum_overlap, left_overlap, right_overlap), shared
                )
                pair_recovery = costs[left_overlap] + costs[right_overlap]
                profiles.append(
                    LocalTripleProfile(
                        shared_labels=shared,
                        left_only_labels=left_only,
                        right_only_labels=right_only,
                        outside_labels=outside,
                        left_overlap=left_overlap,
                        right_overlap=right_overlap,
                        triple_recovery=triple,
                        pair_cost_recovery=pair_recovery,
                        net_recovery=triple - pair_recovery,
                    )
                )
    return tuple(profiles)


def heavy_pair_case(maximum_overlap: int) -> HeavyPairCase:
    """Certify the anchor-pair union bound for one exact maximum overlap."""

    if not 3 <= maximum_overlap <= DRAW_SIZE:
        raise ValueError("Family A maximum overlap must be within 3..draw_size")
    profiles = local_heavy_pair_profiles(maximum_overlap)
    net_profile = max(profiles, key=lambda profile: profile.net_recovery)
    s3_profile = max(profiles, key=lambda profile: profile.triple_recovery)
    anchor_pair_cost = exact_pair_counts()[maximum_overlap]
    s3_ceiling = (TICKET_COUNT - 2) * s3_profile.triple_recovery
    upper_bound = (
        PORTFOLIO_S1
        - anchor_pair_cost
        + (TICKET_COUNT - 2) * net_profile.net_recovery
    )
    return HeavyPairCase(
        maximum_pair_overlap=maximum_overlap,
        s2_floor=exact_s2_floors_by_r()[maximum_overlap],
        anchor_pair_intersection=anchor_pair_cost,
        maximum_triple_recovery_per_third_ticket=s3_profile.triple_recovery,
        local_s3_recovery_ceiling=s3_ceiling,
        maximum_net_recovery_per_third_ticket=net_profile.net_recovery,
        net_maximizing_profile=net_profile,
        s3_maximizing_profile=s3_profile,
        upper_bound=upper_bound,
    )


def family_a_result_record() -> dict[str, Any]:
    """Build the auditable R3 Family A certificate and exact case bounds."""

    pair_costs = exact_pair_counts()
    cases = tuple(heavy_pair_case(r) for r in range(3, DRAW_SIZE + 1))
    family_bound = max(case.upper_bound for case in cases)
    case_bounds = {
        f"R{case.maximum_pair_overlap}_BOUND": case.upper_bound for case in cases
    }
    return {
        "TASK_ID": "B649_K20_HEAVY_PAIR_R3PLUS_GLOBAL_BOUND_R3",
        "TASK_STATUS": "CERTIFIED_FAMILY_A_BOUND_TIGHTENED",
        "BASE_HEAD": BASE_HEAD,
        "TASK_BRANCH": TASK_BRANCH,
        "INCUMBENT": INCUMBENT,
        "PRIOR_FAMILY_A_BOUND": PRIOR_FAMILY_A_BOUND,
        "PAIR_INTERSECTION_COUNTS_BY_OVERLAP": list(pair_costs),
        "PAIR_COST_CONVEXITY_EXCESS": list(pair_cost_convexity_excess(pair_costs)),
        "S2_FREQUENCY_FLOOR": {
            "TICKET_LABEL_INCIDENCES": DRAW_SIZE * TICKET_COUNT,
            "POOL_SIZE": POOL_SIZE,
            "PAIR_OVERLAP_MASS_FLOOR": 93,
            "FREQUENCY_HISTOGRAM": {"2": 27, "3": 22},
            "BASELINE": 63_838_600,
            "BY_MAXIMUM_OVERLAP": {
                str(case.maximum_pair_overlap): case.s2_floor for case in cases
            },
        },
        "ANCHOR_PAIR_BOUND": {
            "IDENTITY": (
                "|A union B| + sum_C |C \\ (A union B)|; "
                "|C \\ (A union B)| = N-I(a)-I(b)+J(r,a,b,c)"
            ),
            "LOCAL_PROFILE": (
                "c shared anchor labels, u left-only, v right-only, and "
                "6-c-u-v outside labels; c<=r, u,v<=6-r, c+u<=r, c+v<=r"
            ),
            "THIRD_TICKETS": TICKET_COUNT - 2,
            "SHARED_LABEL_INCIDENCE_CAP_BY_R": {
                str(case.maximum_pair_overlap): (TICKET_COUNT - 2)
                * case.maximum_pair_overlap
                for case in cases
            },
            "LOCAL_S3_RECOVERY_CEILING_BY_R": {
                str(case.maximum_pair_overlap): case.local_s3_recovery_ceiling
                for case in cases
            },
            "CASES": {str(case.maximum_pair_overlap): asdict(case) for case in cases},
        },
        "FAMILY_A_BOUND": family_bound,
        **case_bounds,
        "FAMILY_A_STATUS": "CLOSED" if family_bound <= INCUMBENT else "TIGHTENED_OPEN",
        "IMPROVEMENT_VS_PRIOR_BOUND": PRIOR_FAMILY_A_BOUND - family_bound,
        "REMAINING_GAP": family_bound - INCUMBENT,
        "SUCCESS_A": family_bound <= INCUMBENT,
        "SUCCESS_B": family_bound < PRIOR_FAMILY_A_BOUND,
        "NEW_PORTFOLIO_SEARCH_STARTED": "NO",
        "PRODUCTION_MUTATION": "NONE",
    }


__all__ = [
    "BASE_HEAD",
    "EXPECTED_PAIR_COUNTS",
    "PRIOR_FAMILY_A_BOUND",
    "TASK_BRANCH",
    "HeavyPairCase",
    "LocalTripleProfile",
    "exact_pair_counts",
    "exact_s2_floors_by_r",
    "family_a_result_record",
    "heavy_pair_case",
    "local_heavy_pair_profiles",
    "pair_cost_convexity_excess",
]
