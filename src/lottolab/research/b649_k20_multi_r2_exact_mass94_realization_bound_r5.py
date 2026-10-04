"""Close the exact K20 Family-B overlap-mass-94 residual.

The 49-label incidence and pair-mass equations leave two support-multiplicity
profiles.  Their shared-triple masses, together with a weighted-graph wedge
relaxation, give a certified S1-S2+S3 upper bound for every clique
decomposition of the 45 weight-2 and 4 weight-1 pair graph.  Ticket and number
identities are not enumerated.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from itertools import combinations
from math import comb

from lottolab.research.b649_k20_heavy_pair_defect_global_bound_r2 import (
    triple_intersection_count,
)
from lottolab.research.b649_k20_mass94plus_residual_bound_r4 import pair_costs
from lottolab.research.b649_k20_outside_min_s2_global_penalty_bound_r1 import (
    INCUMBENT,
    TICKET_COUNT,
)

BASE_HEAD = "6d14fe4009047cc9396660db812442798c8b2d0c"
TASK_BRANCH = "codex/b649-k20-multi-r2-exact-mass94-realization-bound-r5"
NUMBER_LABEL_COUNT = 49
TICKET_LABEL_COUNT = 6
TOTAL_INCIDENCES = TICKET_COUNT * TICKET_LABEL_COUNT
PAIR_COUNT = comb(TICKET_COUNT, 2)
OVERLAP_MASS = 94
HEAVY_PAIR_COUNT = 45
LIGHT_PAIR_COUNT = 4
HEAVY_WEIGHT = 2
FAMILY_B_S1 = 372_228_640


@dataclass(frozen=True)
class MultiplicityProfile:
    """Counts of number supports by multiplicity, indexed from m=1."""

    counts_by_multiplicity: tuple[int, ...]
    label_count: int
    incidence_count: int
    pair_mass: int
    shared_triple_mass: int

    def count(self, multiplicity: int) -> int:
        if not 1 <= multiplicity <= len(self.counts_by_multiplicity):
            raise ValueError("multiplicity is outside the profile")
        return self.counts_by_multiplicity[multiplicity - 1]


@dataclass(frozen=True)
class WeightedWedgeCertificate:
    """Integer ceilings for pair-edge wedges in the weighted ticket graph."""

    ticket_overlap_degree_cap: int
    heavy_degree_cap: int
    heavy_heavy_wedges: int
    heavy_light_wedges: int
    light_light_wedges: int
    total_wedges: int
    triangle_count: int


@dataclass(frozen=True)
class ProfileBound:
    """The S3 and portfolio ceilings for one surviving support profile."""

    profile: tuple[int, ...]
    shared_triple_mass: int
    s3_upper_bound: int
    family_b_upper_bound: int


def balanced_pair_mass(total: int, label_count: int) -> int:
    """Minimum sum of choose(frequency, 2) over ``label_count`` labels."""

    if total < 0 or label_count < 1:
        raise ValueError("total must be nonnegative and label_count positive")
    quotient, remainder = divmod(total, label_count)
    return (label_count - remainder) * comb(quotient, 2) + remainder * comb(quotient + 1, 2)


def _ceil_div(numerator: int, denominator: int) -> int:
    return -((-numerator) // denominator)


def _profile_from_counts(counts: tuple[int, ...]) -> MultiplicityProfile:
    if len(counts) != TICKET_COUNT or any(value < 0 for value in counts):
        raise ValueError("a profile must contain nonnegative counts for m=1..20")
    label_count = sum(counts)
    incidence_count = sum(multiplicity * count for multiplicity, count in enumerate(counts, 1))
    pair_mass = sum(comb(multiplicity, 2) * count for multiplicity, count in enumerate(counts, 1))
    shared_triple_mass = sum(
        comb(multiplicity, 3) * count for multiplicity, count in enumerate(counts, 1)
    )
    return MultiplicityProfile(
        counts_by_multiplicity=counts,
        label_count=label_count,
        incidence_count=incidence_count,
        pair_mass=pair_mass,
        shared_triple_mass=shared_triple_mass,
    )


def enumerate_multiplicity_profiles_recursive() -> tuple[MultiplicityProfile, ...]:
    """Enumerate all profiles satisfying 120 incidences, mass 94, and 49 labels."""

    counts = [0] * TICKET_COUNT
    profiles: set[MultiplicityProfile] = set()

    def visit(multiplicity: int, remaining_incidence: int, remaining_mass: int) -> None:
        if multiplicity == 1:
            if remaining_mass != 0:
                return
            counts[0] = remaining_incidence
            profile = _profile_from_counts(tuple(counts))
            if profile.label_count <= NUMBER_LABEL_COUNT:
                profiles.add(profile)
            counts[0] = 0
            return

        pairs_per_label = comb(multiplicity, 2)
        maximum_count = min(
            remaining_incidence // multiplicity,
            remaining_mass // pairs_per_label,
        )
        for count in range(maximum_count + 1):
            counts[multiplicity - 1] = count
            visit(
                multiplicity - 1,
                remaining_incidence - count * multiplicity,
                remaining_mass - count * pairs_per_label,
            )
        counts[multiplicity - 1] = 0

    visit(TICKET_COUNT, TOTAL_INCIDENCES, OVERLAP_MASS)
    return tuple(sorted(profiles, key=lambda profile: profile.counts_by_multiplicity))


def enumerate_multiplicity_profiles_dynamic() -> tuple[MultiplicityProfile, ...]:
    """Independently enumerate profile vectors with an incidence/mass DP."""

    # Each vector stores counts for multiplicities 2, 3, ..., 20.  The third
    # state coordinate is the number of repeated-incidence savings, so the
    # final number of distinct labels is 120-savings.
    state: dict[tuple[int, int, int], set[tuple[int, ...]]] = {(0, 0, 0): {()}}
    for multiplicity in range(2, TICKET_COUNT + 1):
        pairs_per_label = comb(multiplicity, 2)
        next_state: dict[tuple[int, int, int], set[tuple[int, ...]]] = {}
        for (incidences, pair_mass, savings), vectors in state.items():
            maximum_count = min(
                (TOTAL_INCIDENCES - incidences) // multiplicity,
                (OVERLAP_MASS - pair_mass) // pairs_per_label,
            )
            for count in range(maximum_count + 1):
                key = (
                    incidences + count * multiplicity,
                    pair_mass + count * pairs_per_label,
                    savings + count * (multiplicity - 1),
                )
                next_state.setdefault(key, set()).update((*vector, count) for vector in vectors)
        state = next_state

    profiles: set[MultiplicityProfile] = set()
    for (incidences, pair_mass, savings), vectors in state.items():
        label_count = TOTAL_INCIDENCES - savings
        if pair_mass != OVERLAP_MASS or label_count > NUMBER_LABEL_COUNT:
            continue
        singleton_count = TOTAL_INCIDENCES - incidences
        for vector in vectors:
            profiles.add(_profile_from_counts((singleton_count, *vector)))
    return tuple(sorted(profiles, key=lambda profile: profile.counts_by_multiplicity))


def support_pair_weights(
    supports: Iterable[Iterable[int]], *, vertex_count: int
) -> dict[tuple[int, int], int]:
    """Turn number supports into pair weights by adding one clique per support."""

    if vertex_count < 1:
        raise ValueError("vertex_count must be positive")
    weights: dict[tuple[int, int], int] = {}
    for raw_support in supports:
        support = tuple(raw_support)
        if len(set(support)) != len(support):
            raise ValueError("a support cannot contain a ticket more than once")
        if any(ticket < 0 or ticket >= vertex_count for ticket in support):
            raise ValueError("support ticket is outside the weighted graph")
        for left, right in combinations(sorted(support), 2):
            edge = (left, right)
            weights[edge] = weights.get(edge, 0) + 1
            if weights[edge] > HEAVY_WEIGHT:
                raise ValueError("support cliques give a pair weight greater than two")
    return dict(sorted(weights.items()))


def support_common_triples(
    supports: Iterable[Iterable[int]], *, vertex_count: int
) -> dict[tuple[int, int, int], int]:
    """Count support labels common to each ticket triple."""

    if vertex_count < 1:
        raise ValueError("vertex_count must be positive")
    common: dict[tuple[int, int, int], int] = {}
    for raw_support in supports:
        support = tuple(raw_support)
        if len(set(support)) != len(support):
            raise ValueError("a support cannot contain a ticket more than once")
        if any(ticket < 0 or ticket >= vertex_count for ticket in support):
            raise ValueError("support ticket is outside the weighted graph")
        for triple in combinations(sorted(support), 3):
            common[triple] = common.get(triple, 0) + 1
    return dict(sorted(common.items()))


def ticket_overlap_degree_cap() -> int:
    """Bound one ticket's weighted graph degree from the 49-label pair mass."""

    feasible_sums = [
        selected_sum
        for selected_sum in range(TICKET_LABEL_COUNT, TOTAL_INCIDENCES + 1)
        if balanced_pair_mass(selected_sum, TICKET_LABEL_COUNT)
        + balanced_pair_mass(
            TOTAL_INCIDENCES - selected_sum,
            NUMBER_LABEL_COUNT - TICKET_LABEL_COUNT,
        )
        <= OVERLAP_MASS
    ]
    if not feasible_sums or max(feasible_sums) != 19:
        raise AssertionError("the selected six-label frequency cap must be 19")
    return max(feasible_sums) - TICKET_LABEL_COUNT


def weighted_wedge_certificate() -> WeightedWedgeCertificate:
    """Bound weighted-edge wedges using h=45, l=4, and degree at most 13."""

    degree_cap = ticket_overlap_degree_cap()
    heavy_degree_cap = degree_cap // HEAVY_WEIGHT
    # Sum of heavy degrees is 2*45=90.  With each degree at most six,
    # convexity maximizes choose(a_i,2) by placing degree six at 15 vertices.
    heavy_heavy = (HEAVY_PAIR_COUNT * 2 // heavy_degree_cap) * comb(heavy_degree_cap, 2) + comb(
        (2 * HEAVY_PAIR_COUNT) % heavy_degree_cap, 2
    )
    # There are eight light-edge endpoints in total and each a_i is at most 6.
    heavy_light = heavy_degree_cap * (2 * LIGHT_PAIR_COUNT)
    # Convexity gives sum choose(b_i,2) <= choose(sum b_i,2).
    light_light = comb(2 * LIGHT_PAIR_COUNT, 2)
    total = heavy_heavy + heavy_light + light_light
    return WeightedWedgeCertificate(
        ticket_overlap_degree_cap=degree_cap,
        heavy_degree_cap=heavy_degree_cap,
        heavy_heavy_wedges=heavy_heavy,
        heavy_light_wedges=heavy_light,
        light_light_wedges=light_light,
        total_wedges=total,
        triangle_count=total // 3,
    )


def triangle_common_linear_certificate() -> tuple[int, int]:
    """Return a valid ``base + bonus*q`` ceiling for every positive-edge triple."""

    values: list[tuple[int, int]] = []
    for left in (1, 2):
        for middle in (1, 2):
            for right in (1, 2):
                overlaps: tuple[int, int, int] = (left, middle, right)
                for common in range(min(overlaps) + 1):
                    try:
                        value = triple_intersection_count(overlaps, common)
                    except ValueError:
                        continue
                    values.append((common, value))
    zero_common = [value for common, value in values if common == 0]
    if not zero_common:
        raise AssertionError("positive-edge triples need feasible zero-common rows")
    base = max(zero_common)
    bonus = max(
        (_ceil_div(value - base, common) for common, value in values if common),
        default=0,
    )
    if (base, bonus) != (206_843, 77_455):
        raise AssertionError("the exact positive-edge triple table changed")
    return base, bonus


def exact_mass_94_s2() -> int:
    """Return exact S2 for 45 weight-2 edges, 4 weight-1 edges, and 141 zeros."""

    costs = pair_costs()
    if len(costs) != TICKET_LABEL_COUNT + 1 or PAIR_COUNT != 190:
        raise AssertionError("the exact K20 pair table dimensions changed")
    zero_pairs = PAIR_COUNT - HEAVY_PAIR_COUNT - LIGHT_PAIR_COUNT
    if zero_pairs != 141 or 2 * HEAVY_PAIR_COUNT + LIGHT_PAIR_COUNT != OVERLAP_MASS:
        raise AssertionError("the exact 45/4 overlap graph counts changed")
    value = zero_pairs * costs[0] + LIGHT_PAIR_COUNT * costs[1] + HEAVY_PAIR_COUNT * costs[2]
    if value != 93_815_260:
        raise AssertionError("the exact mass-94 S2 contribution changed")
    return value


def profile_bounds(
    profiles: tuple[MultiplicityProfile, ...] | None = None,
) -> tuple[ProfileBound, ...]:
    """Bound S3 for every moment-feasible clique multiplicity profile."""

    candidates = enumerate_multiplicity_profiles_recursive() if profiles is None else profiles
    wedge = weighted_wedge_certificate()
    single_heavy = triple_intersection_count((0, 0, HEAVY_WEIGHT), 0)
    heavy_heavy_cap = triple_intersection_count((0, HEAVY_WEIGHT, HEAVY_WEIGHT), 0)
    heavy_light_cap = triple_intersection_count((0, 1, HEAVY_WEIGHT), 0)
    light_light_cap = triple_intersection_count((0, 1, 1), 0)
    triangle_base, common_bonus = triangle_common_linear_certificate()
    single_edge_bound = (TICKET_COUNT - 2) * HEAVY_PAIR_COUNT * single_heavy
    wedge_bound = (
        wedge.heavy_heavy_wedges * heavy_heavy_cap
        + wedge.heavy_light_wedges * heavy_light_cap
        + wedge.light_light_wedges * light_light_cap
    )
    fixed_s3 = single_edge_bound + wedge_bound + wedge.triangle_count * triangle_base
    s2 = exact_mass_94_s2()
    results: list[ProfileBound] = []
    for profile in candidates:
        if (
            profile.incidence_count != TOTAL_INCIDENCES
            or profile.pair_mass != OVERLAP_MASS
            or profile.label_count > NUMBER_LABEL_COUNT
        ):
            raise ValueError("profile is outside the exact mass-94 constraints")
        s3 = fixed_s3 + common_bonus * profile.shared_triple_mass
        family_bound = FAMILY_B_S1 - s2 + s3
        results.append(
            ProfileBound(
                profile=profile.counts_by_multiplicity,
                shared_triple_mass=profile.shared_triple_mass,
                s3_upper_bound=s3,
                family_b_upper_bound=family_bound,
            )
        )
    return tuple(results)


def result_record() -> dict[str, object]:
    """Build the compact certificate for the exact mass-94 residual only."""

    recursive = enumerate_multiplicity_profiles_recursive()
    dynamic = enumerate_multiplicity_profiles_dynamic()
    if recursive != dynamic or len(recursive) != 2:
        raise AssertionError("independent profile enumerators disagree")
    bounds = profile_bounds(recursive)
    s2 = exact_mass_94_s2()
    s3 = max(bound.s3_upper_bound for bound in bounds)
    family_bound = max(bound.family_b_upper_bound for bound in bounds)
    status = "CLOSED" if family_bound <= INCUMBENT else "OPEN"
    triangle_base, common_bonus = triangle_common_linear_certificate()
    wedge = weighted_wedge_certificate()
    profile_rows = [
        {
            "counts_by_multiplicity": {
                str(multiplicity): count
                for multiplicity, count in enumerate(profile.counts_by_multiplicity, 1)
                if count
            },
            "label_count": profile.label_count,
            "incidence_count": profile.incidence_count,
            "pair_mass": profile.pair_mass,
            "shared_triple_mass": profile.shared_triple_mass,
        }
        for profile in recursive
    ]
    return {
        "TASK_ID": "B649_K20_MULTI_R2_EXACT_MASS94_REALIZATION_BOUND_R5",
        "TASK_STATUS": "CLOSED" if status == "CLOSED" else "BOUNDED_OPEN",
        "BASE_HEAD": BASE_HEAD,
        "TASK_BRANCH": TASK_BRANCH,
        "OVERLAP_GRAPH": {
            "ticket_count": TICKET_COUNT,
            "weight_2_edges": HEAVY_PAIR_COUNT,
            "weight_1_edges": LIGHT_PAIR_COUNT,
            "weight_0_edges": PAIR_COUNT - HEAVY_PAIR_COUNT - LIGHT_PAIR_COUNT,
            "total_overlap_mass": OVERLAP_MASS,
        },
        "MULTIPLICITY_PROFILE_COUNT": len(recursive),
        "REALIZABLE_PROFILE_COUNT": None,
        "REALIZABLE_PROFILE_COUNT_NOTE": (
            "Two profiles satisfy the exact incidence, pair-mass, and 49-label "
            "constraints. An unlabeled clique-decomposition census was not "
            "needed for the universal bound, so profile-specific existence is "
            "not classified."
        ),
        "MULTIPLICITY_PROFILES": profile_rows,
        "PAIR_GRAPH_REALIZABLE": "NOT_CLASSIFIED",
        "COVERAGE_BOUND_METHOD": "Bonferroni upper bound S1 - S2 + S3",
        "S1": FAMILY_B_S1,
        "S2": s2,
        "S3_BOUND": s3,
        "PROFILE_BOUNDS": [asdict(bound) for bound in bounds],
        "FAMILY_B_BOUND": family_bound,
        "FAMILY_B_STATUS": status,
        "INCUMBENT": INCUMBENT,
        "REMAINING_GAP": family_bound - INCUMBENT,
        "WEDGE_CERTIFICATE": asdict(wedge),
        "S3_CERTIFICATE": {
            "single_heavy_triple_cap": triple_intersection_count((0, 0, HEAVY_WEIGHT), 0),
            "single_heavy_triple_slots_upper": (TICKET_COUNT - 2) * HEAVY_PAIR_COUNT,
            "heavy_heavy_wedge_cap": triple_intersection_count((0, HEAVY_WEIGHT, HEAVY_WEIGHT), 0),
            "heavy_light_wedge_cap": triple_intersection_count((0, 1, HEAVY_WEIGHT), 0),
            "light_light_wedge_cap": triple_intersection_count((0, 1, 1), 0),
            "positive_triangle_zero_common_cap": triangle_base,
            "per_common_label_triangle_bonus": common_bonus,
            "maximum_shared_triple_mass": max(profile.shared_triple_mass for profile in recursive),
            "bound_formula": (
                "18*45*2240 + 225*33264 + 48*14420 + 28*2800 + floor(301/3)*206843 + 24*77455"
            ),
        },
        "SOLVER_STATUS": "NOT_RUN",
        "SOLVER_CONFIGURED_WALL_LIMIT": None,
        "SOLVER_ACTUAL_WALL_TIME": None,
        "SOLVER_CERTIFIED_BOUND": None,
        "NEW_PORTFOLIO_SEARCH_STARTED": "NO",
        "PRODUCTION_MUTATION": "NONE",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    print(json.dumps(result_record(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()


__all__ = [
    "BASE_HEAD",
    "LIGHT_PAIR_COUNT",
    "NUMBER_LABEL_COUNT",
    "OVERLAP_MASS",
    "TASK_BRANCH",
    "MultiplicityProfile",
    "ProfileBound",
    "WeightedWedgeCertificate",
    "balanced_pair_mass",
    "enumerate_multiplicity_profiles_dynamic",
    "enumerate_multiplicity_profiles_recursive",
    "exact_mass_94_s2",
    "profile_bounds",
    "result_record",
    "support_common_triples",
    "support_pair_weights",
    "ticket_overlap_degree_cap",
    "triangle_common_linear_certificate",
    "weighted_wedge_certificate",
]
