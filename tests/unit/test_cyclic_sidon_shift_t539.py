from __future__ import annotations

import pytest

from lottolab.research.cyclic_sidon_shift_t539 import (
    POOL_SIZE,
    SIDON_BASE_SET_0_INDEXED,
    sidon_shift_portfolio,
    sidon_shift_ticket,
)

TICKET_SIZE = 5


def test_base_set_has_five_distinct_elements_in_range() -> None:
    assert len(SIDON_BASE_SET_0_INDEXED) == TICKET_SIZE
    assert len(set(SIDON_BASE_SET_0_INDEXED)) == TICKET_SIZE
    assert all(0 <= x < POOL_SIZE for x in SIDON_BASE_SET_0_INDEXED)


def test_base_set_is_a_sidon_set_mod_39() -> None:
    differences = [
        (a - b) % POOL_SIZE
        for a in SIDON_BASE_SET_0_INDEXED
        for b in SIDON_BASE_SET_0_INDEXED
        if a != b
    ]
    assert len(differences) == TICKET_SIZE * (TICKET_SIZE - 1)
    assert len(set(differences)) == len(differences)


def test_first_ticket_matches_the_disclosed_one_based_set() -> None:
    assert sidon_shift_ticket(0) == (1, 2, 4, 8, 13)


def test_every_ticket_has_five_distinct_in_range_numbers() -> None:
    for shift in range(POOL_SIZE):
        ticket = sidon_shift_ticket(shift)
        assert len(ticket) == TICKET_SIZE
        assert len(set(ticket)) == TICKET_SIZE
        assert all(1 <= n <= POOL_SIZE for n in ticket)


def test_pairwise_overlap_is_at_most_one_across_every_possible_shift_pair() -> None:
    tickets = [set(sidon_shift_ticket(shift)) for shift in range(POOL_SIZE)]
    max_overlap = 0
    for i in range(POOL_SIZE):
        for j in range(i + 1, POOL_SIZE):
            max_overlap = max(max_overlap, len(tickets[i] & tickets[j]))
    assert max_overlap <= 1


def test_shift_periodicity_is_exactly_39() -> None:
    assert sidon_shift_ticket(0) == sidon_shift_ticket(39)
    assert sidon_shift_ticket(5) == sidon_shift_ticket(44)


def test_portfolio_is_a_strict_nested_prefix() -> None:
    portfolio_20 = sidon_shift_portfolio(20)
    for k in (1, 3, 5, 10, 15):
        assert sidon_shift_portfolio(k) == portfolio_20[:k]


def test_portfolio_rejects_out_of_range_count() -> None:
    with pytest.raises(ValueError, match="ticket_count must lie in"):
        sidon_shift_portfolio(40)
    with pytest.raises(ValueError, match="ticket_count must lie in"):
        sidon_shift_portfolio(-1)


def test_portfolio_at_pool_size_uses_every_shift_exactly_once() -> None:
    portfolio = sidon_shift_portfolio(POOL_SIZE)
    assert len(portfolio) == POOL_SIZE
    assert len(set(portfolio)) == POOL_SIZE


def test_shares_the_first_five_elements_of_the_big_lotto_base_set() -> None:
    # Documented, not asserted as a coincidence: both greedy searches share
    # the same deterministic path from the same starting point.
    assert SIDON_BASE_SET_0_INDEXED == (0, 1, 3, 7, 12)
