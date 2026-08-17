from __future__ import annotations

import itertools

import pytest

from lottolab.research.fourth_order_geometry import (
    canonical_quadruple_region_shape,
    max_pairwise_overlap_forces_zero_quadruple_collisions,
    quadruple_collision_is_impossible,
    quadruple_collision_mass,
    quadruple_region_mass,
    quadruple_shape_is_saturated,
    s4_from_ticket_quadruple_region_histogram,
    ticket_quadruple_hit_event_intersection_size,
    ticket_quadruple_intersection_histogram,
)
from lottolab.research.low_overlap_geometry_mechanism import (
    exact_hit_multiplicity_decomposition,
)

Ticket = tuple[int, ...]


# Same (n,d,m) and same S2/S3, but different S4.  These are deliberately
# synthetic; the portfolios are not native lottery constructors.
SAME_S2_S3_A: tuple[Ticket, ...] = (
    (1, 4, 7),
    (2, 3, 8),
    (2, 4, 7),
    (4, 6, 7),
)
SAME_S2_S3_B: tuple[Ticket, ...] = (
    (1, 6, 7),
    (2, 3, 6),
    (2, 5, 7),
    (2, 7, 8),
)

# At d=5,m=3, six pairwise-only shared numbers still provide mass 6, below
# the required mass 7.  The concrete quadruple has all six pairwise overlaps
# equal to one and no triple or quadruple intersection.
ZERO_S4_D5: tuple[Ticket, ...] = (
    (1, 2, 3, 4, 5),
    (1, 6, 7, 8, 9),
    (2, 6, 10, 11, 12),
    (3, 7, 10, 13, 14),
)

# At d=6,m=3, the six distinct pairwise-shared numbers exactly meet the mass
# boundary.  The one winning draw {1,...,6} hits all four tickets three times.
NONZERO_S4_D6: tuple[Ticket, ...] = (
    (1, 2, 3, 7, 8, 9),
    (1, 4, 5, 10, 11, 12),
    (2, 4, 6, 13, 14, 15),
    (3, 5, 6, 16, 17, 18),
)


def _brute_force_s4(
    portfolio: tuple[Ticket, ...], pool_size: int, draw_size: int, minimum_matches: int
) -> int:
    return exact_hit_multiplicity_decomposition(
        portfolio,
        pool_size=pool_size,
        draw_size=draw_size,
        minimum_matches=minimum_matches,
    ).collision_moments[4]


def _geometry_s4(
    portfolio: tuple[Ticket, ...], pool_size: int, draw_size: int, minimum_matches: int
) -> int:
    histogram = dict(ticket_quadruple_intersection_histogram(portfolio, pool_size))
    return s4_from_ticket_quadruple_region_histogram(
        pool_size, draw_size, minimum_matches, histogram
    )


def test_same_s2_s3_can_have_different_s4() -> None:
    common = {"pool_size": 8, "draw_size": 3, "minimum_matches": 2}
    first = exact_hit_multiplicity_decomposition(SAME_S2_S3_A, **common)
    second = exact_hit_multiplicity_decomposition(SAME_S2_S3_B, **common)

    assert (first.collision_moments[2], first.collision_moments[3]) == (28, 6)
    assert (second.collision_moments[2], second.collision_moments[3]) == (28, 6)
    assert first.collision_moments[4] == 0
    assert second.collision_moments[4] == 1


def test_full_region_shape_is_invariant_to_ticket_relabeling() -> None:
    reference = canonical_quadruple_region_shape(18, *NONZERO_S4_D6)
    for permutation in itertools.permutations(NONZERO_S4_D6):
        assert canonical_quadruple_region_shape(18, *permutation) == reference


def test_mass_bound_forces_zero_s4_under_daily539_like_shape() -> None:
    pairwise = (1, 1, 1, 1, 1, 1)
    triple = (0, 0, 0, 0)
    assert quadruple_collision_mass(pairwise, triple, 0) == 6
    assert quadruple_collision_is_impossible(5, 3, pairwise, triple, 0)
    assert max_pairwise_overlap_forces_zero_quadruple_collisions(5, 3, 1)
    assert _brute_force_s4(ZERO_S4_D5, 14, 5, 3) == 0


def test_realizable_nonzero_s4_at_the_d6_mass_boundary() -> None:
    shape = canonical_quadruple_region_shape(18, *NONZERO_S4_D6)
    assert quadruple_region_mass(shape) == 6
    assert quadruple_shape_is_saturated(6, 3, shape)
    assert not quadruple_collision_is_impossible(6, 3, (1, 1, 1, 1, 1, 1), (0, 0, 0, 0), 0)
    assert ticket_quadruple_hit_event_intersection_size(18, 6, 3, shape) == 1
    assert _brute_force_s4(NONZERO_S4_D6, 18, 6, 3) == 1


@pytest.mark.parametrize(
    ("portfolio", "pool_size", "draw_size", "minimum_matches"),
    [
        (SAME_S2_S3_A, 8, 3, 2),
        (SAME_S2_S3_B, 8, 3, 2),
        (ZERO_S4_D5, 14, 5, 3),
        (NONZERO_S4_D6, 18, 6, 3),
    ],
    ids=["same-s2-s3-a", "same-s2-s3-b", "mass-bound-zero", "boundary-nonzero"],
)
def test_geometry_s4_equals_brute_force_multiplicity_s4(
    portfolio: tuple[Ticket, ...], pool_size: int, draw_size: int, minimum_matches: int
) -> None:
    assert _geometry_s4(portfolio, pool_size, draw_size, minimum_matches) == _brute_force_s4(
        portfolio, pool_size, draw_size, minimum_matches
    )
