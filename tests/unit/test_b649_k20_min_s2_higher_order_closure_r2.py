"""Independent checks for the compressed K20 fourth-order intersection formula."""

from __future__ import annotations

import itertools
from collections.abc import Sequence
from fractions import Fraction
from math import comb

from lottolab.research.b649_k20_min_s2_higher_order_closure_r2 import (
    compressed_four_ticket_intersection_count,
    fourth_order_intersection_sum,
    k20_min_s2_family_official_any_prize_upper_bound,
    k20_min_s2_s4_decomposition,
    k20_min_s2_s4_lower_bound_certificate,
)

type Ticket = tuple[int, ...]


def _tickets_from_pattern(
    pair_edges: Sequence[tuple[int, int]],
    *,
    contained_triple: tuple[int, int, int] | None = None,
) -> tuple[Ticket, Ticket, Ticket, Ticket]:
    tickets = [set[int]() for _ in range(4)]
    next_label = 1

    if contained_triple is not None:
        for ticket_index in contained_triple:
            tickets[ticket_index].add(next_label)
        next_label += 1

    for left, right in pair_edges:
        tickets[left].add(next_label)
        tickets[right].add(next_label)
        next_label += 1

    for ticket in tickets:
        while len(ticket) < 6:
            ticket.add(next_label)
            next_label += 1

    return tuple(tuple(sorted(ticket)) for ticket in tickets)  # type: ignore[return-value]


def _profile(tickets: Sequence[Sequence[int]], pool_size: int) -> tuple[int, ...]:
    counts = [0] * 16
    for label in range(1, pool_size + 1):
        mask = sum(
            1 << ticket_index
            for ticket_index, ticket in enumerate(tickets)
            if label in ticket
        )
        counts[mask] += 1
    return tuple(counts)


def _brute_force_four_way_intersection(
    tickets: Sequence[Sequence[int]], *, pool_size: int, draw_size: int, outright_matches: int
) -> int:
    ticket_sets = [set(ticket) for ticket in tickets]
    outcomes = 0
    for draw in itertools.combinations(range(1, pool_size + 1), draw_size):
        draw_set = set(draw)
        for special in range(1, pool_size + 1):
            if special in draw_set:
                continue
            if all(
                (hits := len(ticket & draw_set)) >= outright_matches
                or (hits == outright_matches - 1 and special in ticket)
                for ticket in ticket_sets
            ):
                outcomes += 1
    return outcomes


def _valid_k20_incidence_fixture() -> tuple[Ticket, ...]:
    tickets = [set[int]() for _ in range(20)]
    next_label = 1

    def add_label(support: tuple[int, ...]) -> None:
        nonlocal next_label
        for ticket_index in support:
            tickets[ticket_index].add(next_label)
        next_label += 1

    fano_lines = (
        (0, 1, 2),
        (0, 3, 4),
        (0, 5, 6),
        (1, 3, 5),
        (1, 4, 6),
        (2, 3, 6),
        (2, 4, 5),
    )
    for line_index, points in enumerate(fano_lines):
        for point in points:
            add_label((point, 7 + line_index))
    for index in range(6):
        add_label((14 + index, 14 + (index + 1) % 6))

    add_label((7, 9, 12))
    matchings = (
        ((0, 1), (2, 3), (4, 5)),
        ((6, 7), (8, 9), (10, 11)),
        ((12, 13), (0, 2), (4, 6)),
        ((1, 3), (5, 7), (8, 10)),
        ((9, 11), (12, 0), (2, 4)),
        ((13, 1), (3, 5), (6, 8)),
    )
    for index, matching in enumerate(matchings):
        for left, right in matching:
            add_label((left, right, 14 + index))
    for support in ((11, 14, 17), (13, 15, 18), (10, 16, 19)):
        add_label(support)

    assert next_label == 50
    assert all(len(ticket) == 6 for ticket in tickets)
    return tuple(tuple(sorted(ticket)) for ticket in tickets)  # type: ignore[return-value]


def test_official_overlap_types_match_the_compressed_label_dp() -> None:
    all_pairs = tuple(itertools.combinations(range(4), 2))
    diamond_pairs = tuple(pair for pair in all_pairs if pair != (0, 1))

    cases = (
        (_tickets_from_pattern(diamond_pairs), 112),
        (_tickets_from_pattern(all_pairs), 679),
        (
            _tickets_from_pattern(
                ((0, 3), (1, 3), (2, 3)), contained_triple=(0, 1, 2)
            ),
            448,
        ),
        (
            _tickets_from_pattern(
                ((0, 3), (1, 3)), contained_triple=(0, 1, 2)
            ),
            0,
        ),
    )

    for tickets, expected in cases:
        compressed = compressed_four_ticket_intersection_count(
            _profile(tickets, 49),
            pool_size=49,
            draw_size=6,
            outright_matches=3,
        )

        assert compressed == expected
        assert fourth_order_intersection_sum(tickets) == expected


def test_all_four_ticket_overlap_graph_profiles_match_the_exact_type_table() -> None:
    pairs = tuple(itertools.combinations(range(4), 2))
    core_triples = tuple(itertools.combinations(range(4), 3))

    for edge_mask in range(1 << len(pairs)):
        edges = tuple(
            pair for bit, pair in enumerate(pairs) if edge_mask & (1 << bit)
        )
        for core in (None, *core_triples):
            core_edges: set[tuple[int, int]] = (
                set(itertools.combinations(core, 2)) if core is not None else set()
            )
            if not core_edges.issubset(edges):
                continue

            profile = [0] * 16
            if core is not None:
                profile[sum(1 << index for index in core)] += 1
            for left, right in edges:
                if (left, right) in core_edges:
                    continue
                profile[(1 << left) | (1 << right)] += 1

            ticket_loads = [
                sum(
                    count
                    for mask, count in enumerate(profile)
                    if mask & (1 << ticket_index)
                )
                for ticket_index in range(4)
            ]
            if any(load > 6 for load in ticket_loads):
                continue
            for ticket_index, load in enumerate(ticket_loads):
                profile[1 << ticket_index] += 6 - load
            profile[0] += 49 - sum(profile)

            expected = (
                112
                if len(edges) == 5 and core is None
                else 679
                if len(edges) == 6 and core is None
                else 448
                if len(edges) == 6 and core is not None
                else 0
            )
            assert compressed_four_ticket_intersection_count(
                profile,
                pool_size=49,
                draw_size=6,
                outright_matches=3,
            ) == expected


def test_compressed_count_matches_independent_small_lottery_exhaustion() -> None:
    pool_size, draw_size, outright_matches = 9, 3, 2
    all_tickets = list(itertools.combinations(range(1, pool_size + 1), draw_size))
    small_ticket_set = all_tickets[:8]

    for tickets in itertools.combinations(small_ticket_set, 4):
        compressed = compressed_four_ticket_intersection_count(
            _profile(tickets, pool_size),
            pool_size=pool_size,
            draw_size=draw_size,
            outright_matches=outright_matches,
        )

        assert compressed == _brute_force_four_way_intersection(
            tickets,
            pool_size=pool_size,
            draw_size=draw_size,
            outright_matches=outright_matches,
        )


def test_profile_rejects_invalid_pool_and_negative_counts() -> None:
    valid = [0] * 16
    valid[0] = 49

    try:
        compressed_four_ticket_intersection_count(
            valid,
            pool_size=48,
            draw_size=6,
            outright_matches=3,
        )
    except ValueError as error:
        assert "sum to pool_size" in str(error)
    else:
        raise AssertionError("a profile with the wrong pool count must be rejected")

    invalid = [0] * 16
    invalid[0] = 48
    invalid[1] = -1
    try:
        compressed_four_ticket_intersection_count(
            invalid,
            pool_size=49,
            draw_size=6,
            outright_matches=3,
        )
    except ValueError as error:
        assert "non-negative integers" in str(error)
    else:
        raise AssertionError("a profile with a negative category count must be rejected")


def test_overlap_sum_rejects_non_linear_ticket_pairs() -> None:
    tickets = (
        (1, 2, 3, 4, 5, 6),
        (1, 2, 7, 8, 9, 10),
        (11, 12, 13, 14, 15, 16),
        (17, 18, 19, 20, 21, 22),
    )

    try:
        fourth_order_intersection_sum(tickets)
    except ValueError as error:
        assert "at most one label" in str(error)
    else:
        raise AssertionError("a ticket pair with overlap two must be rejected")


def test_k20_profile_is_valid_and_s4_uses_its_compressed_decomposition() -> None:
    family = _valid_k20_incidence_fixture()

    decomposition = k20_min_s2_s4_decomposition(family)

    assert (
        decomposition.five_edges_without_contained_triple,
        decomposition.six_edges_without_contained_triple,
        decomposition.six_edges_with_contained_triple,
    ) == (161, 10, 16)
    assert decomposition.s4 == fourth_order_intersection_sum(family)
    assert decomposition.five_edges_without_contained_triple >= 0
    assert decomposition.six_edges_without_contained_triple >= 0
    assert decomposition.six_edges_with_contained_triple >= 0


def test_triple_core_counting_certificate_proves_s4_floor_and_family_bound() -> None:
    certificate = k20_min_s2_s4_lower_bound_certificate()

    assert certificate.minimum_triple_incidence_square_sum == 222
    assert certificate.cross_incidence_lower_bound == 486
    assert certificate.core_outside_pair_count == 374
    assert certificate.double_incidence_lower_bound_if_no_contribution == 112
    assert certificate.core_edge_count == 66
    assert certificate.s4_lower_bound == 112

    assert k20_min_s2_family_official_any_prize_upper_bound() == 313_916_056


def test_order_three_bonferroni_excess_covers_fourth_order_credit_through_seven() -> None:
    for multiplicity in range(8):
        third_order_value = (
            multiplicity
            - comb(multiplicity, 2)
            + comb(multiplicity, 3)
        )
        union_indicator = int(multiplicity > 0)

        assert third_order_value - union_indicator >= Fraction(
            4 * comb(multiplicity, 4), 7
        )
