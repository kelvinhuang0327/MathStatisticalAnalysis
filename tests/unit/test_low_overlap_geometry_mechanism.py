from __future__ import annotations

import itertools
import math
from fractions import Fraction

import pytest

from lottolab.research.low_overlap_geometry_mechanism import (
    exact_hit_multiplicity_decomposition,
    gain_over_random_ratio_to_sidon,
    portfolio_geometry,
    relative_coverage_delta_vs_sidon,
    relative_lift_vs_random,
    s2_from_ticket_pair_intersection_histogram,
    ticket_pair_hit_event_intersection_size,
)

Ticket = tuple[int, ...]


def _direct_pair_hit_event_intersection_size(
    pool_size: int,
    draw_size: int,
    minimum_matches: int,
    left: Ticket,
    right: Ticket,
) -> int:
    return sum(
        len(set(winner) & set(left)) >= minimum_matches
        and len(set(winner) & set(right)) >= minimum_matches
        for winner in itertools.combinations(range(1, pool_size + 1), draw_size)
    )


def test_metric_semantics_are_exact_and_not_interchangeable() -> None:
    q_random = Fraction(1, 5)
    q_sidon = Fraction(1, 4)
    q_b = Fraction(3, 10)

    assert relative_lift_vs_random(q_b, q_random) == Fraction(1, 2)
    assert relative_coverage_delta_vs_sidon(q_b, q_sidon) == Fraction(1, 5)
    assert gain_over_random_ratio_to_sidon(q_b, q_random, q_sidon) == 2


def test_gain_over_random_ratio_requires_positive_sidon_gain() -> None:
    with pytest.raises(ValueError, match="q_sidon - q_random must be > 0"):
        gain_over_random_ratio_to_sidon(Fraction(1, 3), Fraction(1, 4), Fraction(1, 4))


@pytest.mark.parametrize(
    ("left", "right"),
    [
        ((1, 2, 3), (4, 5, 6)),
        ((1, 2, 3), (1, 4, 5)),
        ((1, 2, 3), (1, 2, 4)),
        ((1, 2, 3), (1, 2, 3)),
    ],
)
def test_pair_hit_event_formula_matches_direct_winner_enumeration(
    left: Ticket, right: Ticket
) -> None:
    pool_size, draw_size, minimum_matches = 7, 3, 2
    ticket_intersection = len(set(left) & set(right))

    assert ticket_pair_hit_event_intersection_size(
        pool_size, draw_size, minimum_matches, ticket_intersection
    ) == _direct_pair_hit_event_intersection_size(
        pool_size, draw_size, minimum_matches, left, right
    )


def test_geometry_metrics_freeze_histogram_reuse_and_dispersion_semantics() -> None:
    portfolio = ((1, 2, 3), (1, 4, 5), (2, 4, 6))

    geometry = portfolio_geometry(portfolio, pool_size=7, draw_size=3)

    assert geometry.ticket_pair_intersection_histogram == ((1, 3),)
    assert geometry.max_pairwise_overlap == 1
    assert geometry.mean_pairwise_overlap == 1
    assert geometry.per_number_reuse_vector == (2, 2, 1, 2, 1, 1, 0)
    assert geometry.unique_number_coverage == 6
    assert geometry.reuse_dispersion_population_variance == Fraction(24, 49)
    assert math.isclose(geometry.reuse_dispersion, math.sqrt(24 / 49))
    assert geometry.duplicate_count == 0


def test_fixed_incidence_redundancy_and_inclusion_exclusion_identities() -> None:
    portfolio = ((1, 2, 3), (1, 4, 5), (2, 4, 6))

    result = exact_hit_multiplicity_decomposition(
        portfolio, pool_size=7, draw_size=3, minimum_matches=2
    )

    assert result.total_winning_combinations == 35
    assert result.hit_event_size_per_ticket == 13
    assert result.total_hit_incidence == 39 == 3 * 13
    assert result.multiplicity_counts == (7, 18, 9, 1)
    assert result.covered == 28
    assert result.redundancy == 11 == result.total_hit_incidence - result.covered
    assert result.collision_moments == (35, 39, 12, 1)
    assert result.inclusion_exclusion_covered == 39 - 12 + 1 == result.covered


def test_s2_from_pair_geometry_matches_winner_multiplicity_route() -> None:
    portfolio = ((1, 2, 3), (1, 4, 5), (2, 4, 6))
    geometry = portfolio_geometry(portfolio, pool_size=7, draw_size=3)
    result = exact_hit_multiplicity_decomposition(
        portfolio, pool_size=7, draw_size=3, minimum_matches=2
    )

    s2_from_geometry = s2_from_ticket_pair_intersection_histogram(
        pool_size=7,
        draw_size=3,
        minimum_matches=2,
        histogram=dict(geometry.ticket_pair_intersection_histogram),
    )

    assert s2_from_geometry == 12 == result.collision_moments[2]


def test_equal_pairwise_geometry_can_hide_a_higher_order_coverage_difference() -> None:
    # Both portfolios have three ticket pairs and every pair intersects in
    # exactly one number.  Their S2 values are therefore identical.  The
    # second portfolio nevertheless has one triple-hit winner (S3=1), so
    # inclusion-exclusion gives it one additional covered winner.  This is
    # the exact synthetic counterexample that prevents the future study from
    # assuming pairwise geometry is automatically the whole mechanism.
    no_triple_collision = ((1, 2, 3), (1, 4, 5), (1, 6, 7))
    one_triple_collision = ((1, 2, 3), (1, 4, 5), (2, 4, 6))

    first_geometry = portfolio_geometry(no_triple_collision, pool_size=7, draw_size=3)
    second_geometry = portfolio_geometry(one_triple_collision, pool_size=7, draw_size=3)
    first = exact_hit_multiplicity_decomposition(
        no_triple_collision, pool_size=7, draw_size=3, minimum_matches=2
    )
    second = exact_hit_multiplicity_decomposition(
        one_triple_collision, pool_size=7, draw_size=3, minimum_matches=2
    )

    assert first_geometry.ticket_pair_intersection_histogram == ((1, 3),)
    assert second_geometry.ticket_pair_intersection_histogram == ((1, 3),)
    assert first.collision_moments[2] == second.collision_moments[2] == 12
    assert first.collision_moments[3] == 0
    assert second.collision_moments[3] == 1
    assert first.covered == 27
    assert second.covered == 28
