# pyright: reportMissingTypeStubs=false

"""Structural Bonferroni bound for K10 portfolios with overlap mass >= 13."""

from __future__ import annotations

import itertools
import json
import math
from collections import Counter
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from functools import cache
from math import comb
from typing import Any, cast

from lottolab.research.b649_k10_overlap_mass12_bonferroni_screen_r1 import (
    _joint_count_from_regions,  # pyright: ignore[reportPrivateUsage]
    _joint_event_count,  # pyright: ignore[reportPrivateUsage]
)

TASK_ID = "B649_K10_MASS13_PLUS_GLOBAL_BOUND_R1"
TICKET_COUNT = 10
TICKET_SIZE = 6
POOL_SIZE = 49
DRAW_SIZE = 6
OUTRIGHT_MATCHES = 3
MASS_FLOOR = 13
INCUMBENT_OUTCOME_COUNT = 176_345_645
INCUMBENT_PROBABILITY = "536005/1827672"
INCIDENCE_EXCESS = TICKET_COUNT * TICKET_SIZE - POOL_SIZE
TRIPLE_COUNT = comb(TICKET_COUNT, 3)


@dataclass(frozen=True)
class StructuralBound:
    """A CP-SAT upper bound over every all-label-used K10 structure."""

    solver_status: str
    outcome_upper_bound: int
    best_feasible_upper: int | None
    raw_objective_upper_bound: float
    elapsed_seconds: float
    multiplicity_profile: tuple[int, ...] | None
    overlap_mass: int | None


def number_multiplicity_profile(portfolio: Sequence[Sequence[int]]) -> tuple[int, ...]:
    """Return counts for frequencies 0..10 for a legal K10 portfolio."""

    if len(portfolio) != TICKET_COUNT:
        raise ValueError("a K10 portfolio must contain ten tickets")
    frequencies: Counter[int] = Counter()
    normalized: list[tuple[int, ...]] = []
    for ticket in portfolio:
        numbers = tuple(ticket)
        if (
            len(numbers) != TICKET_SIZE
            or len(set(numbers)) != TICKET_SIZE
            or any(type(number) is not int or not 1 <= number <= POOL_SIZE for number in numbers)
        ):
            raise ValueError(f"illegal ticket: {numbers}")
        normalized.append(numbers)
        frequencies.update(numbers)
    if len(set(normalized)) != TICKET_COUNT:
        raise ValueError("K10 tickets must be distinct")

    profile = [0] * (TICKET_COUNT + 1)
    profile[0] = POOL_SIZE - len(frequencies)
    for frequency in frequencies.values():
        profile[frequency] += 1
    return tuple(profile)


def overlap_mass(portfolio: Sequence[Sequence[int]]) -> int:
    """Compute sum_n C(r_n, 2) for a legal K10 portfolio."""

    profile = number_multiplicity_profile(portfolio)
    return sum(comb(frequency, 2) * profile[frequency] for frequency in range(2, 11))


def _profile_mass(profile: tuple[int, ...]) -> int:
    if len(profile) != TICKET_COUNT + 1:
        raise ValueError("a frequency profile must have entries for 0..10")
    return sum(comb(frequency, 2) * profile[frequency] for frequency in range(2, 11))


def _profile_triple_excess(profile: tuple[int, ...]) -> int:
    """Sum the within-triple overlap excess over all 120 ticket triples."""

    return sum(
        (comb(frequency, 2) * (TICKET_COUNT - frequency) + 2 * comb(frequency, 3))
        * profile[frequency]
        for frequency in range(2, 11)
    )


def _profile_maximum_winners(profile: tuple[int, ...]) -> int:
    """Upper-bound tickets winning on a seven-number main-plus-special set."""

    seven_largest = sorted(
        (
            frequency
            for frequency in range(1, TICKET_COUNT + 1)
            for _ in range(profile[frequency])
        ),
        reverse=True,
    )[: DRAW_SIZE + 1]
    return sum(seven_largest) // OUTRIGHT_MATCHES


def _pair_intersection_lower_bound(mass: int) -> int:
    pair_counts = _pair_event_counts()
    if any(
        pair_counts[index + 1] - pair_counts[index]
        > pair_counts[index + 2] - pair_counts[index + 1]
        for index in range(4)
    ):
        raise AssertionError("pair-intersection counts must be convex")
    if not 0 <= mass <= 48:
        raise ValueError("all-label-used K10 overlap mass must be in 0..48")
    if mass <= 45:
        return (45 - mass) * pair_counts[0] + mass * pair_counts[1]
    return 45 * pair_counts[1] + (mass - 45) * (pair_counts[2] - pair_counts[1])


def second_moment_profile_upper_bound(profile: tuple[int, ...]) -> int:
    """Bound union coverage by S1 - 2*S2/T, with T from the top seven labels.

    An OFFICIAL_ANY_PRIZE outcome has seven labels. If ``t`` tickets win, then
    ``3t`` is at most the total multiplicity of those labels, hence at most
    ``T``. For every integer ``1 <= t <= T``,
    ``1 <= t - (2/T) * C(t, 2)``. Summing this pointwise inequality gives the
    bound. Pair convexity supplies the profile-only lower bound for S2.
    """

    mass = _profile_mass(profile)
    if not MASS_FLOOR <= mass <= 48:
        raise ValueError("profile is outside the all-label-used mass>=13 family")
    maximum_winners = _profile_maximum_winners(profile)
    if maximum_winners < 1:
        raise AssertionError("a legal profile must allow at least one winner")
    single = _joint_event_count((sum(1 << number for number in range(TICKET_SIZE)),))
    pair_lower = _pair_intersection_lower_bound(mass)
    numerator = TICKET_COUNT * single * maximum_winners - 2 * pair_lower
    return numerator // maximum_winners


def _partitions(total: int, maximum: int) -> Iterator[tuple[int, ...]]:
    if total == 0:
        yield ()
        return
    for part in range(min(total, maximum), 0, -1):
        for rest in _partitions(total - part, part):
            yield (part, *rest)


@cache
def mass_ge13_profiles() -> tuple[tuple[int, ...], ...]:
    """All all-label-used K10 profiles with overlap mass >= 13.

    With all 49 labels used, the multiplicity excess is 60 - 49 = 11. A part
    ``r - 1`` of a partition of 11 represents one label used by ``r`` tickets.
    The two excluded partitions are the already-certified mass-11 and mass-12
    profiles. Frequencies above ten are impossible for ten tickets.
    """

    profiles: list[tuple[int, ...]] = []
    for parts in _partitions(INCIDENCE_EXCESS, TICKET_COUNT - 1):
        profile = [0] * (TICKET_COUNT + 1)
        repeated_label_count = len(parts)
        profile[1] = POOL_SIZE - repeated_label_count
        for part in parts:
            profile[part + 1] += 1
        candidate = tuple(profile)
        if _profile_mass(candidate) >= MASS_FLOOR:
            if sum(candidate) != POOL_SIZE or sum(
                frequency * candidate[frequency] for frequency in range(1, 11)
            ) != TICKET_COUNT * TICKET_SIZE:
                raise AssertionError("derived K10 profile violates the incidence equations")
            profiles.append(candidate)

    result = tuple(sorted(profiles))
    if len(result) != 52 or min(map(_profile_mass, result)) != 13 or max(
        map(_profile_mass, result)
    ) != 48:
        raise AssertionError("the K10 mass>=13 profile characterization changed")
    return result


def profile_witness(profile: tuple[int, ...]) -> tuple[tuple[int, ...], ...]:
    """Construct legal tickets for an all-label-used multiplicity profile.

    Repeated-label supports are laid consecutively around ten ticket indices.
    There are at most 22 repeated incidences, so each ticket receives at most
    three of them and therefore at least three private labels. This proves all
    derived profiles are realizable by ten distinct six-number tickets.
    """

    if (
        len(profile) != TICKET_COUNT + 1
        or any(type(count) is not int or count < 0 for count in profile)
        or profile[0] != 0
        or sum(profile) != POOL_SIZE
        or sum(frequency * profile[frequency] for frequency in range(1, 11))
        != TICKET_COUNT * TICKET_SIZE
        or sum((frequency - 1) * profile[frequency] for frequency in range(2, 11))
        != INCIDENCE_EXCESS
        or _profile_mass(profile) < MASS_FLOOR
    ):
        raise ValueError("profile is not an all-label-used K10 mass>=13 profile")

    repeated_frequencies = [
        frequency
        for frequency in range(TICKET_COUNT, 1, -1)
        for _ in range(profile[frequency])
    ]
    tickets: list[list[int]] = [[] for _ in range(TICKET_COUNT)]
    cursor = 0
    for number, frequency in enumerate(repeated_frequencies, start=1):
        for offset in range(frequency):
            tickets[(cursor + offset) % TICKET_COUNT].append(number)
        cursor += frequency

    next_number = len(repeated_frequencies) + 1
    for ticket in tickets:
        private_count = TICKET_SIZE - len(ticket)
        if private_count < 0:
            raise AssertionError("cyclic support construction exceeded a ticket size")
        for _ in range(private_count):
            ticket.append(next_number)
            next_number += 1
    if next_number != POOL_SIZE + 1:
        raise AssertionError("cyclic support construction did not use exactly 49 labels")

    witness = tuple(tuple(sorted(ticket)) for ticket in tickets)
    if number_multiplicity_profile(witness) != profile:
        raise AssertionError("cyclic support construction changed its profile")
    return witness


@cache
def _pair_event_counts() -> tuple[int, ...]:
    """Exact OFFICIAL_ANY_PRIZE pair intersections for ticket overlap 0..5."""

    left = sum(1 << number for number in range(TICKET_SIZE))
    counts: list[int] = []
    for shared in range(TICKET_SIZE):
        right = sum(1 << number for number in range(shared)) | sum(
            1 << number for number in range(TICKET_SIZE, 2 * TICKET_SIZE - shared)
        )
        counts.append(_joint_event_count((left, right)))
    return tuple(counts)


@cache
def _triple_event_upper_by_excess() -> tuple[int, ...]:
    """Maximum exact triple-event intersection for each 3-ticket excess.

    A triple's overlap excess is 18 minus the union size of its tickets. Its
    seven Venn-region sizes determine the exact joint event count.
    """

    maxima = [-1] * 12
    for triple_shared in range(TICKET_SIZE + 1):
        for ab_only in range(TICKET_SIZE + 1):
            for ac_only in range(TICKET_SIZE + 1):
                for bc_only in range(TICKET_SIZE + 1):
                    a_only = TICKET_SIZE - ab_only - ac_only - triple_shared
                    b_only = TICKET_SIZE - ab_only - bc_only - triple_shared
                    c_only = TICKET_SIZE - ac_only - bc_only - triple_shared
                    if min(a_only, b_only, c_only) < 0:
                        continue
                    if max(
                        ab_only + triple_shared,
                        ac_only + triple_shared,
                        bc_only + triple_shared,
                    ) > TICKET_SIZE - 1:
                        continue
                    excess = ab_only + ac_only + bc_only + 2 * triple_shared
                    regions = (
                        a_only,
                        b_only,
                        ab_only,
                        c_only,
                        ac_only,
                        bc_only,
                        triple_shared,
                    )
                    outcomes = _joint_count_from_regions(
                        regions,
                        3,
                        POOL_SIZE,
                        DRAW_SIZE,
                        OUTRIGHT_MATCHES,
                    )
                    maxima[excess] = max(maxima[excess], outcomes)

    if any(value < 0 for value in maxima):
        raise AssertionError("a three-ticket excess value has no legal realization")
    return tuple(maxima)


@cache
def _triple_sum_upper(total_excess: int) -> int:
    """Relax the 120 triple excesses independently, preserving their sum."""

    by_excess = _triple_event_upper_by_excess()
    states = {0: 0}
    for _ in range(TRIPLE_COUNT):
        updated: dict[int, int] = {}
        for used, subtotal in states.items():
            for excess, outcomes in enumerate(by_excess):
                combined = used + excess
                if combined <= total_excess:
                    updated[combined] = max(
                        updated.get(combined, -1), subtotal + outcomes
                    )
        states = updated
    if total_excess not in states:
        raise AssertionError("profile triple excess has no 120-triple allocation")
    return states[total_excess]


@cache
def cheap_profile_upper_bound(profile: tuple[int, ...]) -> int:
    """Take the stronger of two profile-level Bonferroni/moment relaxations."""

    mass = _profile_mass(profile)
    if not MASS_FLOOR <= mass <= 48:
        raise ValueError("profile is outside the all-label-used mass>=13 family")
    single = _joint_event_count((sum(1 << number for number in range(TICKET_SIZE)),))
    bonferroni = (
        TICKET_COUNT * single
        - _pair_intersection_lower_bound(mass)
        + _triple_sum_upper(_profile_triple_excess(profile))
    )
    return min(bonferroni, second_moment_profile_upper_bound(profile))


def _triple_table() -> tuple[tuple[int, int, int, int, int], ...]:
    allowed: list[tuple[int, int, int, int, int]] = []
    for ab, ac, bc in itertools.product(range(TICKET_SIZE), repeat=3):
        for triple_shared in range(TICKET_SIZE):
            a_only = TICKET_SIZE - ab - ac + triple_shared
            b_only = TICKET_SIZE - ab - bc + triple_shared
            c_only = TICKET_SIZE - ac - bc + triple_shared
            if min(
                a_only,
                b_only,
                c_only,
                ab - triple_shared,
                ac - triple_shared,
                bc - triple_shared,
            ) < 0:
                continue
            regions = (
                a_only,
                b_only,
                ab - triple_shared,
                c_only,
                ac - triple_shared,
                bc - triple_shared,
                triple_shared,
            )
            outcomes = _joint_count_from_regions(
                regions,
                3,
                POOL_SIZE,
                DRAW_SIZE,
                OUTRIGHT_MATCHES,
            )
            allowed.append((ab, ac, bc, triple_shared, outcomes))
    return tuple(allowed)


def maximize_structural_upper_bound(*, time_limit_seconds: float = 120.0) -> StructuralBound:
    """Optimize a combined valid coverage bound over every mass>=13 structure.

    Integer variables count labels by their exact ticket-support subset. The
    excess equation is fixed at 11, ticket degrees are at most six, and pair
    intersections at most five enforce distinct tickets. Thus every legal
    all-label-used portfolio in the target family is represented, independent
    of any candidate pool or ticket construction. The optimized bound is the
    minimum of the exact third-order Bonferroni ceiling and the profile-aware
    second-moment ceiling.
    """

    if not math.isfinite(time_limit_seconds) or time_limit_seconds <= 0:
        raise ValueError("time limit must be finite and positive")

    from ortools.sat.python import cp_model

    # OR-Tools ships no complete pyright declarations for its CP-SAT API.
    cp_model_api = cast(Any, cp_model)
    model: Any = cp_model_api.CpModel()
    support_masks = tuple(
        mask for mask in range(1 << TICKET_COUNT) if mask.bit_count() >= 2
    )
    support_count = {
        mask: mask.bit_count()
        for mask in support_masks
    }
    labels_by_support: dict[int, Any] = {
        mask: model.NewIntVar(0, INCIDENCE_EXCESS, f"support_{mask:04x}")
        for mask in support_masks
    }

    model.Add(
        sum((support_count[mask] - 1) * labels_by_support[mask] for mask in support_masks)
        == INCIDENCE_EXCESS
    )
    overlap_mass = model.NewIntVar(MASS_FLOOR, 48, "overlap_mass")
    model.Add(
        overlap_mass
        == sum(
            comb(support_count[mask], 2) * labels_by_support[mask]
            for mask in support_masks
        )
    )

    ticket_degrees: list[Any] = []
    for ticket in range(TICKET_COUNT):
        degree = model.NewIntVar(0, TICKET_SIZE, f"ticket_degree_{ticket}")
        model.Add(
            degree
            == sum(
                labels_by_support[mask]
                for mask in support_masks
                if mask & (1 << ticket)
            )
        )
        ticket_degrees.append(degree)
    for ticket in range(TICKET_COUNT - 1):
        model.Add(ticket_degrees[ticket] >= ticket_degrees[ticket + 1])

    pair_overlaps: dict[tuple[int, int], Any] = {}
    pair_events: list[Any] = []
    for left, right in itertools.combinations(range(TICKET_COUNT), 2):
        shared = model.NewIntVar(0, TICKET_SIZE - 1, f"overlap_{left}_{right}")
        model.Add(
            shared
            == sum(
                labels_by_support[mask]
                for mask in support_masks
                if mask & (1 << left) and mask & (1 << right)
            )
        )
        event_count = model.NewIntVar(0, _pair_event_counts()[-1], f"pair_event_{left}_{right}")
        model.AddElement(shared, list(_pair_event_counts()), event_count)
        pair_overlaps[(left, right)] = shared
        pair_events.append(event_count)

    triple_events: list[Any] = []
    table = _triple_table()
    for left, middle, right in itertools.combinations(range(TICKET_COUNT), 3):
        triple_shared = model.NewIntVar(
            0, TICKET_SIZE - 1, f"triple_shared_{left}_{middle}_{right}"
        )
        model.Add(
            triple_shared
            == sum(
                labels_by_support[mask]
                for mask in support_masks
                if mask & (1 << left)
                and mask & (1 << middle)
                and mask & (1 << right)
            )
        )
        triple_event = model.NewIntVar(
            0,
            _joint_event_count((sum(1 << number for number in range(TICKET_SIZE)),)),
            f"triple_event_{left}_{middle}_{right}",
        )
        model.AddAllowedAssignments(
            (
                pair_overlaps[(left, middle)],
                pair_overlaps[(left, right)],
                pair_overlaps[(middle, right)],
                triple_shared,
                triple_event,
            ),
            table,
        )
        triple_events.append(triple_event)

    single = _joint_event_count((sum(1 << number for number in range(TICKET_SIZE)),))
    u3 = TICKET_COUNT * single - sum(pair_events) + sum(triple_events)
    coverage_upper = model.NewIntVar(
        0, TICKET_COUNT * single, "combined_coverage_upper_bound"
    )
    model.Add(coverage_upper <= u3)

    profiles = mass_ge13_profiles()
    profile_selectors = [
        model.NewBoolVar(f"profile_{index:02d}") for index in range(len(profiles))
    ]
    model.Add(sum(profile_selectors) == 1)
    for frequency in range(2, TICKET_COUNT + 1):
        model.Add(
            sum(
                labels_by_support[mask]
                for mask in support_masks
                if support_count[mask] == frequency
            )
            == sum(
                profile[frequency] * selector
                for profile, selector in zip(profiles, profile_selectors, strict=True)
            )
        )

    second_moment = sum(pair_events)
    for profile, selector in zip(profiles, profile_selectors, strict=True):
        maximum_winners = _profile_maximum_winners(profile)
        model.Add(
            maximum_winners * coverage_upper
            <= maximum_winners * TICKET_COUNT * single - 2 * second_moment
        ).OnlyEnforceIf(selector)
        model.Add(coverage_upper <= cheap_profile_upper_bound(profile)).OnlyEnforceIf(
            selector
        )
    model.Maximize(coverage_upper)

    solver: Any = cp_model_api.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit_seconds
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = 0
    status: int = solver.Solve(model)
    if status in (cp_model_api.MODEL_INVALID, cp_model_api.INFEASIBLE):
        raise RuntimeError(f"structural CP-SAT model failed: {solver.StatusName(status)}")

    status_name: str = str(solver.StatusName(status))
    raw_upper = float(solver.BestObjectiveBound())
    if not math.isfinite(raw_upper):
        # The elementary ten-event union bound remains valid if CP-SAT times
        # out before exposing a finite structural objective bound.
        single = _joint_event_count((sum(1 << number for number in range(TICKET_SIZE)),))
        upper_bound = TICKET_COUNT * single
    else:
        # The objective is integral. Round the floating report outward to keep
        # this result a valid upper bound under solver-output rounding.
        upper_bound = math.floor(raw_upper + 1e-6)

    feasible_upper: int | None = None
    profile: tuple[int, ...] | None = None
    mass_value: int | None = None
    if status in (cp_model_api.OPTIMAL, cp_model_api.FEASIBLE):
        feasible_upper = round(solver.ObjectiveValue())
        histogram = [0] * (TICKET_COUNT + 1)
        for mask, variable in labels_by_support.items():
            histogram[mask.bit_count()] += int(solver.Value(variable))
        histogram[1] = POOL_SIZE - sum(histogram[2:])
        profile = tuple(histogram)
        mass_value = int(solver.Value(overlap_mass))
        if _profile_mass(profile) != mass_value or mass_value < MASS_FLOOR:
            raise AssertionError("CP-SAT witness profile disagrees with its overlap mass")

    if status == cp_model_api.OPTIMAL:
        upper_bound = feasible_upper if feasible_upper is not None else upper_bound
    return StructuralBound(
        solver_status=status_name,
        outcome_upper_bound=upper_bound,
        best_feasible_upper=feasible_upper,
        raw_objective_upper_bound=raw_upper,
        elapsed_seconds=float(solver.WallTime()),
        multiplicity_profile=profile,
        overlap_mass=mass_value,
    )


def proof_summary(*, time_limit_seconds: float = 120.0) -> dict[str, object]:
    profiles = mass_ge13_profiles()
    cheap_bounds = tuple(cheap_profile_upper_bound(profile) for profile in profiles)
    structural = maximize_structural_upper_bound(time_limit_seconds=time_limit_seconds)
    worst_profile_index = max(range(len(profiles)), key=cheap_bounds.__getitem__)
    unresolved_profiles = [
        profile
        for profile, bound in zip(profiles, cheap_bounds, strict=True)
        if bound > INCUMBENT_OUTCOME_COUNT
    ]
    return {
        "task_id": TASK_ID,
        "incumbent_outcome_count": INCUMBENT_OUTCOME_COUNT,
        "incumbent_probability": INCUMBENT_PROBABILITY,
        "mass_ge13_profile_count": len(profiles),
        "mass_ge13_analytically_closed": len(profiles) - len(unresolved_profiles),
        "mass_ge13_structurally_analyzed": len(unresolved_profiles),
        "maximum_cheap_profile_bound": max(cheap_bounds),
        "structural_solver_status": structural.solver_status,
        "mass_ge13_upper_bound": min(structural.outcome_upper_bound, max(cheap_bounds)),
        "best_feasible_structural_bound": structural.best_feasible_upper,
        "structural_bound_raw": structural.raw_objective_upper_bound,
        "structural_elapsed_seconds": structural.elapsed_seconds,
        "unresolved_profile": profiles[worst_profile_index],
        "unresolved_profile_mass": _profile_mass(profiles[worst_profile_index]),
        "structural_candidate_profile": structural.multiplicity_profile,
        "structural_candidate_mass": structural.overlap_mass,
        "global_optimum_status": (
            "PROVEN"
            if min(structural.outcome_upper_bound, max(cheap_bounds))
            <= INCUMBENT_OUTCOME_COUNT
            else "UNKNOWN"
        ),
        "remaining_gap": max(
            0,
            min(structural.outcome_upper_bound, max(cheap_bounds))
            - INCUMBENT_OUTCOME_COUNT,
        ),
    }


def main() -> int:
    print(json.dumps(proof_summary(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
