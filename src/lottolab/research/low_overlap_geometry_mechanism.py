"""Exact, lottery-agnostic identities for hit-event redundancy studies.

This module contains only pure combinatorial helpers.  It does not load a
lottery result artifact, construct a native B649/T539/P638 portfolio, read
historical draws, or write a Matrix result.  The Phase-5 low-overlap geometry
mechanism design uses the helpers at toy scale so the formulas can be tested
before a separate Owner-authorized lock-and-execute task exists.
"""

from __future__ import annotations

import itertools
import math
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction

from lottolab.research.exact_coverage_baseline import qualifying_ticket_count

Ticket = tuple[int, ...]


@dataclass(frozen=True)
class PortfolioGeometry:
    """Exact geometry fields for one fixed portfolio.

    ``ticket_pair_intersection_histogram`` is a sorted tuple of
    ``(intersection_cardinality, pair_count)`` entries.  The population
    variance behind ``reuse_dispersion`` is retained exactly; the standard
    deviation itself is an explicitly presentation-only float because its
    square root need not be rational.
    """

    ticket_pair_intersection_histogram: tuple[tuple[int, int], ...]
    max_pairwise_overlap: int
    mean_pairwise_overlap: Fraction
    per_number_reuse_vector: tuple[int, ...]
    unique_number_coverage: int
    reuse_dispersion_population_variance: Fraction
    reuse_dispersion: float
    duplicate_count: int


@dataclass(frozen=True)
class HitMultiplicityDecomposition:
    """Exact winner-level multiplicity decomposition for one portfolio.

    ``multiplicity_counts[c]`` is :math:`N_c`, the number of winning
    combinations hit by exactly ``c`` tickets. ``collision_moments[j]`` is
    :math:`S_j = sum_w C(c(w), j)`.  Index zero is retained in both tuples:
    ``N_0`` is load-bearing for the uncovered count and ``S_0`` equals the
    total number of winning combinations.
    """

    total_winning_combinations: int
    ticket_count: int
    hit_event_size_per_ticket: int
    total_hit_incidence: int
    multiplicity_counts: tuple[int, ...]
    covered: int
    redundancy: int
    collision_moments: tuple[int, ...]
    inclusion_exclusion_covered: int


def relative_lift_vs_random(q_b: Fraction, q_random: Fraction) -> Fraction:
    """``RELATIVE_LIFT_VS_RANDOM = (Q_B - Q_R) / Q_R``."""

    if q_random <= 0:
        raise ValueError("q_random must be > 0")
    return (q_b - q_random) / q_random


def relative_coverage_delta_vs_sidon(q_b: Fraction, q_sidon: Fraction) -> Fraction:
    """``RELATIVE_COVERAGE_DELTA_VS_SIDON = (Q_B - Q_S) / Q_S``."""

    if q_sidon <= 0:
        raise ValueError("q_sidon must be > 0")
    return (q_b - q_sidon) / q_sidon


def gain_over_random_ratio_to_sidon(
    q_b: Fraction, q_random: Fraction, q_sidon: Fraction
) -> Fraction:
    """``GAIN_OVER_RANDOM_RATIO_TO_SIDON = (Q_B-Q_R)/(Q_S-Q_R)``.

    The metric is defined only when Sidon's gain over random is strictly
    positive.  In the future native study this makes ``k=1`` not applicable,
    rather than silently manufacturing a value for the exact ``0/0`` case.
    """

    denominator = q_sidon - q_random
    if denominator <= 0:
        raise ValueError("q_sidon - q_random must be > 0")
    return (q_b - q_random) / denominator


def _validate_shape(pool_size: int, draw_size: int, minimum_matches: int) -> None:
    if not 1 <= draw_size <= pool_size:
        raise ValueError("draw_size must lie in [1, pool_size]")
    if not 1 <= minimum_matches <= draw_size:
        raise ValueError("minimum_matches must lie in [1, draw_size]")


def _validated_portfolio(
    portfolio: Sequence[Ticket], pool_size: int, draw_size: int
) -> tuple[Ticket, ...]:
    tickets = tuple(portfolio)
    for ticket in tickets:
        if len(ticket) != draw_size or len(set(ticket)) != draw_size:
            raise ValueError("every ticket must contain draw_size distinct numbers")
        if tuple(sorted(ticket)) != ticket:
            raise ValueError("tickets must be ascending-sorted")
        if any(number < 1 or number > pool_size for number in ticket):
            raise ValueError("ticket number outside 1..pool_size")
    return tickets


def portfolio_geometry(
    portfolio: Sequence[Ticket], pool_size: int, draw_size: int
) -> PortfolioGeometry:
    """Compute the frozen pair-overlap and number-reuse quantities exactly."""

    _validate_shape(pool_size, draw_size, minimum_matches=1)
    tickets = _validated_portfolio(portfolio, pool_size, draw_size)
    pair_overlaps = [
        len(set(left) & set(right)) for left, right in itertools.combinations(tickets, 2)
    ]
    histogram_counter: Counter[int] = Counter(pair_overlaps)
    histogram = tuple(sorted(histogram_counter.items()))
    pair_count = len(pair_overlaps)
    mean_overlap = Fraction(sum(pair_overlaps), pair_count) if pair_count else Fraction(0)

    reuse = [0] * pool_size
    for ticket in tickets:
        for number in ticket:
            reuse[number - 1] += 1
    mean_reuse = Fraction(len(tickets) * draw_size, pool_size)
    reuse_variance = (
        sum(
            ((Fraction(count) - mean_reuse) ** 2 for count in reuse),
            start=Fraction(0),
        )
        / pool_size
    )

    return PortfolioGeometry(
        ticket_pair_intersection_histogram=histogram,
        max_pairwise_overlap=max(pair_overlaps, default=0),
        mean_pairwise_overlap=mean_overlap,
        per_number_reuse_vector=tuple(reuse),
        unique_number_coverage=sum(count > 0 for count in reuse),
        reuse_dispersion_population_variance=reuse_variance,
        reuse_dispersion=math.sqrt(float(reuse_variance)),
        duplicate_count=len(tickets) - len(set(tickets)),
    )


def ticket_pair_hit_event_intersection_size(
    pool_size: int,
    draw_size: int,
    minimum_matches: int,
    ticket_intersection: int,
) -> int:
    """Count winners hitting both tickets using only their intersection size.

    Split the pool into four regions: the shared ticket numbers (size ``r``),
    the left-only and right-only numbers (each size ``draw_size-r``), and the
    numbers outside the union (size ``pool_size-2*draw_size+r``).  Summing the
    corresponding binomial products over valid region counts gives the exact
    pair-event intersection cardinality ``H_m(n, d, r)``.
    """

    _validate_shape(pool_size, draw_size, minimum_matches)
    minimum_possible_intersection = max(0, 2 * draw_size - pool_size)
    if not minimum_possible_intersection <= ticket_intersection <= draw_size:
        raise ValueError("ticket_intersection is impossible for this pool/draw shape")

    shared_size = ticket_intersection
    exclusive_size = draw_size - ticket_intersection
    outside_size = pool_size - 2 * draw_size + ticket_intersection
    total = 0
    for shared_hits in range(shared_size + 1):
        for left_only_hits in range(exclusive_size + 1):
            if shared_hits + left_only_hits < minimum_matches:
                continue
            for right_only_hits in range(exclusive_size + 1):
                if shared_hits + right_only_hits < minimum_matches:
                    continue
                outside_hits = draw_size - shared_hits - left_only_hits - right_only_hits
                if not 0 <= outside_hits <= outside_size:
                    continue
                total += (
                    math.comb(shared_size, shared_hits)
                    * math.comb(exclusive_size, left_only_hits)
                    * math.comb(exclusive_size, right_only_hits)
                    * math.comb(outside_size, outside_hits)
                )
    return total


def s2_from_ticket_pair_intersection_histogram(
    pool_size: int,
    draw_size: int,
    minimum_matches: int,
    histogram: Mapping[int, int],
) -> int:
    """Derive ``S_2`` from the exact ticket-pair intersection histogram."""

    total = 0
    for ticket_intersection, pair_count in histogram.items():
        if pair_count < 0:
            raise ValueError("pair counts must be non-negative")
        total += pair_count * ticket_pair_hit_event_intersection_size(
            pool_size, draw_size, minimum_matches, ticket_intersection
        )
    return total


def exact_hit_multiplicity_decomposition(
    portfolio: Sequence[Ticket],
    pool_size: int,
    draw_size: int,
    minimum_matches: int,
) -> HitMultiplicityDecomposition:
    """Enumerate a small winning space and derive all exact mechanism identities.

    The function is generic, but the design task's tests invoke it only on
    toy/synthetic pools.  A later lock-and-execute task must provide its own
    explicit authorization before using the same identities on native lottery
    winning spaces.
    """

    _validate_shape(pool_size, draw_size, minimum_matches)
    tickets = _validated_portfolio(portfolio, pool_size, draw_size)
    ticket_masks = tuple(sum(1 << (number - 1) for number in ticket) for ticket in tickets)
    multiplicity_counts = [0] * (len(tickets) + 1)

    for winner in itertools.combinations(range(1, pool_size + 1), draw_size):
        winner_mask = sum(1 << (number - 1) for number in winner)
        multiplicity = sum(
            (winner_mask & ticket_mask).bit_count() >= minimum_matches
            for ticket_mask in ticket_masks
        )
        multiplicity_counts[multiplicity] += 1

    total_winners = math.comb(pool_size, draw_size)
    hit_event_size = qualifying_ticket_count(pool_size, draw_size, minimum_matches)
    total_hit_incidence = sum(
        multiplicity * count for multiplicity, count in enumerate(multiplicity_counts)
    )
    expected_incidence = len(tickets) * hit_event_size
    if total_hit_incidence != expected_incidence:
        raise ArithmeticError("fixed-incidence identity failed")

    covered = sum(multiplicity_counts[1:])
    redundancy = sum(
        (multiplicity - 1) * multiplicity_counts[multiplicity]
        for multiplicity in range(2, len(multiplicity_counts))
    )
    if redundancy != total_hit_incidence - covered:
        raise ArithmeticError("redundancy identity failed")

    collision_moments = tuple(
        sum(
            math.comb(multiplicity, order) * multiplicity_counts[multiplicity]
            for multiplicity in range(len(multiplicity_counts))
        )
        for order in range(len(multiplicity_counts))
    )
    inclusion_exclusion_covered = sum(
        moment if order % 2 else -moment
        for order, moment in enumerate(collision_moments[1:], start=1)
    )
    if inclusion_exclusion_covered != covered:
        raise ArithmeticError("inclusion-exclusion identity failed")

    return HitMultiplicityDecomposition(
        total_winning_combinations=total_winners,
        ticket_count=len(tickets),
        hit_event_size_per_ticket=hit_event_size,
        total_hit_incidence=total_hit_incidence,
        multiplicity_counts=tuple(multiplicity_counts),
        covered=covered,
        redundancy=redundancy,
        collision_moments=collision_moments,
        inclusion_exclusion_covered=inclusion_exclusion_covered,
    )
