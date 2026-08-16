from __future__ import annotations

import itertools

import pytest

from lottolab.research.higher_order_residual_mechanism import (
    max_pairwise_overlap_forces_zero_triple_collisions,
    s3_from_ticket_triple_intersection_histogram,
    ticket_triple_hit_event_intersection_size,
    ticket_triple_intersection_histogram,
    triple_collision_is_impossible,
)
from lottolab.research.low_overlap_geometry_mechanism import (
    exact_hit_multiplicity_decomposition,
    portfolio_geometry,
)

Ticket = tuple[int, ...]


def _direct_triple_hit_event_intersection_size(
    pool_size: int,
    draw_size: int,
    minimum_matches: int,
    first: Ticket,
    second: Ticket,
    third: Ticket,
) -> int:
    return sum(
        len(set(winner) & set(first)) >= minimum_matches
        and len(set(winner) & set(second)) >= minimum_matches
        and len(set(winner) & set(third)) >= minimum_matches
        for winner in itertools.combinations(range(1, pool_size + 1), draw_size)
    )


# STAR: all three pairwise overlaps run through the same shared number (s=1).
# CHAIN: the three pairwise overlaps are three distinct numbers (s=0). Both
# have three ticket pairs each intersecting in exactly one number, so they
# share a pairwise histogram and S2 -- this is the same shape distinction as
# the sealed Phase-5 fixture (test_equal_pairwise_geometry_can_hide_a_
# higher_order_coverage_difference), replayed here at the real M3+
# threshold (m=3) and BIG_LOTTO/POWER_LOTTO_zone1's draw size (d=6) instead
# of that fixture's toy m=2/d=3.
STAR_M3_D6: tuple[Ticket, ...] = ((1, 2, 3, 4, 5, 6), (1, 7, 8, 9, 10, 11), (1, 12, 13, 14, 15, 16))
CHAIN_M3_D6: tuple[Ticket, ...] = ((1, 2, 3, 4, 5, 6), (1, 7, 8, 9, 10, 11), (2, 7, 12, 13, 14, 15))
DISJOINT_M3_D6: tuple[Ticket, ...] = (
    (1, 2, 3, 4, 5, 6),
    (7, 8, 9, 10, 11, 12),
    (13, 14, 15, 16, 17, 18),
)


# -- Toy Test A: identical pairwise geometry/S2, different S3 ---------------


def test_star_and_chain_share_pairwise_geometry_but_not_s3() -> None:
    star_geometry = portfolio_geometry(STAR_M3_D6, pool_size=16, draw_size=6)
    chain_geometry = portfolio_geometry(CHAIN_M3_D6, pool_size=16, draw_size=6)
    assert star_geometry.ticket_pair_intersection_histogram == ((1, 3),)
    assert chain_geometry.ticket_pair_intersection_histogram == ((1, 3),)

    common = {"pool_size": 16, "draw_size": 6, "minimum_matches": 3}
    star = exact_hit_multiplicity_decomposition(STAR_M3_D6, **common)
    chain = exact_hit_multiplicity_decomposition(CHAIN_M3_D6, **common)
    assert star.collision_moments[2] == chain.collision_moments[2]
    assert star.collision_moments[3] == 0
    assert chain.collision_moments[3] == 64
    assert star.covered != chain.covered


@pytest.mark.parametrize(
    ("portfolio", "pool_size"),
    [(STAR_M3_D6, 16), (CHAIN_M3_D6, 16), (DISJOINT_M3_D6, 18)],
    ids=["star", "chain", "disjoint"],
)
def test_geometry_route_reproduces_multiplicity_route_for_s3(
    portfolio: tuple[Ticket, ...], pool_size: int
) -> None:
    histogram = dict(ticket_triple_intersection_histogram(portfolio))
    s3_geometry = s3_from_ticket_triple_intersection_histogram(
        pool_size=pool_size, draw_size=6, minimum_matches=3, histogram=histogram
    )
    s3_multiplicity = exact_hit_multiplicity_decomposition(
        portfolio, pool_size=pool_size, draw_size=6, minimum_matches=3
    ).collision_moments[3]
    assert s3_geometry == s3_multiplicity


# -- General correctness: formula matches direct winner enumeration ---------


@pytest.mark.parametrize(
    ("first", "second", "third", "pool_size", "draw_size", "minimum_matches"),
    [
        ((1, 2, 3), (1, 4, 5), (1, 6, 7), 7, 3, 2),
        ((1, 2, 3), (1, 4, 5), (2, 4, 6), 7, 3, 2),
        ((1, 2, 3), (4, 5, 6), (7, 8, 9), 9, 3, 2),
        ((1, 2, 3), (1, 2, 4), (1, 2, 5), 6, 3, 2),
        ((1, 2, 3, 4), (1, 2, 5, 6), (1, 3, 5, 7), 8, 4, 3),
    ],
    ids=["star-toy", "chain-toy", "disjoint-toy", "heavy-overlap", "larger-draw-mixed-shape"],
)
def test_triple_hit_event_formula_matches_direct_winner_enumeration(
    first: Ticket,
    second: Ticket,
    third: Ticket,
    pool_size: int,
    draw_size: int,
    minimum_matches: int,
) -> None:
    pairwise_12 = len(set(first) & set(second))
    pairwise_13 = len(set(first) & set(third))
    pairwise_23 = len(set(second) & set(third))
    triple = len(set(first) & set(second) & set(third))

    formula_result = ticket_triple_hit_event_intersection_size(
        pool_size, draw_size, minimum_matches, pairwise_12, pairwise_13, pairwise_23, triple
    )
    direct_result = _direct_triple_hit_event_intersection_size(
        pool_size, draw_size, minimum_matches, first, second, third
    )
    assert formula_result == direct_result


def test_triple_hit_event_size_is_symmetric_under_ticket_relabeling() -> None:
    # Distinct r-values so a labeling bug (e.g. swapping which region belongs
    # to which ticket) would change the result.
    base = {"pool_size": 20, "draw_size": 6, "minimum_matches": 3, "triple": 0}
    r_values = (2, 1, 0)

    def evaluate(r12: int, r13: int, r23: int) -> int:
        return ticket_triple_hit_event_intersection_size(
            pairwise_12=r12, pairwise_13=r13, pairwise_23=r23, **base
        )

    reference = evaluate(*r_values)
    for permuted in itertools.permutations(r_values):
        assert evaluate(*permuted) == reference


def test_hit_event_size_is_pool_size_independent_at_the_exact_boundary_shape() -> None:
    # At the exact boundary (mass == 3m-d, zero slack) every valid winning
    # draw must spend its entire budget on the triple's own shared/exclusive
    # numbers, leaving no room for outside-pool numbers -- so growing the
    # pool cannot add new valid configurations. Verified computationally
    # here, not assumed; see the Phase-6 design doc S5 for the argument.
    values = {
        ticket_triple_hit_event_intersection_size(
            pool_size=pool_size,
            draw_size=6,
            minimum_matches=3,
            pairwise_12=1,
            pairwise_13=1,
            pairwise_23=1,
            triple=0,
        )
        for pool_size in (15, 16, 20, 38, 49, 100)
    }
    assert values == {64}


# -- Toy Test B: exact conditions where S3 is forced to zero -----------------


def test_necessary_mass_bound_lemma_forces_zero_at_daily539_shape() -> None:
    # DAILY_539 shape: draw_size=5, minimum_matches=3. Even the best-case
    # (maximum mass) triple under a pairwise-overlap-<=1 cap -- three
    # distinct single-number pairwise overlaps, no triple point -- is short
    # of the required mass (3m-d=4 > available 3).
    assert triple_collision_is_impossible(
        draw_size=5, minimum_matches=3, pairwise_12=1, pairwise_13=1, pairwise_23=1, triple=0
    )
    boundary_shape = {"pairwise_12": 1, "pairwise_13": 1, "pairwise_23": 1, "triple": 0}
    assert (
        ticket_triple_hit_event_intersection_size(
            pool_size=12, draw_size=5, minimum_matches=3, **boundary_shape
        )
        == 0
    )
    first, second, third = (1, 2, 3, 4, 5), (1, 6, 7, 8, 9), (2, 6, 10, 11, 12)
    assert _direct_triple_hit_event_intersection_size(12, 5, 3, first, second, third) == 0


def test_necessary_mass_bound_lemma_allows_nonzero_at_biglotto_shape() -> None:
    # BIG_LOTTO/POWER_LOTTO_zone1 shape: draw_size=6, minimum_matches=3. The
    # same best-case triple exactly meets the required mass (3m-d=3==3): not
    # ruled out, and CHAIN_M3_D6 above shows it is in fact realized (S3=64).
    assert not triple_collision_is_impossible(
        draw_size=6, minimum_matches=3, pairwise_12=1, pairwise_13=1, pairwise_23=1, triple=0
    )


def test_formula_confirms_daily539_max_overlap_cap_forces_zero_s3() -> None:
    # Sealed Phase-5 report S5: DAILY_539's max_pairwise_overlap is 0 or 1
    # for both arms at every tested k, and the sealed decomposition (S3) is
    # exactly 0 at every one of those cells. The portfolio-level corollary
    # says this is not a coincidence: it is forced by draw_size=5 alone.
    assert max_pairwise_overlap_forces_zero_triple_collisions(
        draw_size=5, minimum_matches=3, max_pairwise_overlap=1
    )
    # BIG_LOTTO/POWER_LOTTO_zone1 have the identical observed overlap cap
    # (max_pairwise_overlap<=1 throughout) but are NOT forced to zero --
    # consistent with their observed nonzero S3. Pool size (49 vs 38 vs 39)
    # cannot be the discriminating variable: this predicate never reads it.
    assert not max_pairwise_overlap_forces_zero_triple_collisions(
        draw_size=6, minimum_matches=3, max_pairwise_overlap=1
    )


def test_formula_retrodicts_sealed_biglotto_and_powerlotto_k3_delta_s3() -> None:
    # Sealed Phase-5 report S5: both BIG_LOTTO (n=49) and POWER_LOTTO_zone1
    # (n=38) k=3 Sidon portfolios have max_pairwise_overlap=1 for every one
    # of their 3 ticket pairs (mean overlap exactly 1/1), consistent with
    # the CHAIN shape; Arm-B at k=3 is fully disjoint in both (S3_B=0). The
    # sealed report S3 (Full signed decomposition table) shows DELTA_S3=-64
    # for BOTH lotteries at k=3 -- reproduced here from the formula alone,
    # not read from the sealed result file.
    boundary_shape = {"pairwise_12": 1, "pairwise_13": 1, "pairwise_23": 1, "triple": 0}
    assert (
        ticket_triple_hit_event_intersection_size(
            pool_size=49, draw_size=6, minimum_matches=3, **boundary_shape
        )
        == 64
    )
    assert (
        ticket_triple_hit_event_intersection_size(
            pool_size=38, draw_size=6, minimum_matches=3, **boundary_shape
        )
        == 64
    )


# -- Toy Test C: a higher-order term opposing the pairwise benefit ----------


def test_higher_order_term_can_oppose_a_favorable_pairwise_component() -> None:
    # DISJOINT ("arm-B-like": no shared numbers between any pair) has fewer
    # pairwise collisions than CHAIN ("sidon-like": one shared number per
    # pair) -- so P=-DELTA_S2>0 favors DISJOINT. But DISJOINT's one triple is
    # fully disjoint (S3=0) while CHAIN's triple sits exactly at the
    # nonzero boundary (S3=64), so T3=DELTA_S3=0-64=-64<0 partially erodes
    # DISJOINT's net advantage instead of adding to it -- the same sign
    # pattern as the sealed BIG_LOTTO k=3 cell (T3=-64 there too).
    pool_size, draw_size, minimum_matches = 18, 6, 3
    disjoint = exact_hit_multiplicity_decomposition(
        DISJOINT_M3_D6, pool_size=pool_size, draw_size=draw_size, minimum_matches=minimum_matches
    )
    chain = exact_hit_multiplicity_decomposition(
        CHAIN_M3_D6, pool_size=pool_size, draw_size=draw_size, minimum_matches=minimum_matches
    )

    delta_s2 = disjoint.collision_moments[2] - chain.collision_moments[2]
    delta_s3 = disjoint.collision_moments[3] - chain.collision_moments[3]
    pairwise_component = -delta_s2
    higher_order_term_3 = delta_s3  # T_j = (-1)**(j+1) * DELTA_S_j, j=3 -> +DELTA_S3
    delta_covered = disjoint.covered - chain.covered

    assert pairwise_component > 0
    assert higher_order_term_3 == -64
    assert delta_covered == pairwise_component + higher_order_term_3
    assert 0 < delta_covered < pairwise_component
