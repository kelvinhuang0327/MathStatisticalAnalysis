from __future__ import annotations

import pytest

from lottolab.research.cyclic_sidon_shift import (
    POOL_SIZE,
    SIDON_BASE_SET_0_INDEXED,
    sidon_shift_portfolio,
    sidon_shift_ticket,
)


def test_base_set_has_six_distinct_elements_in_range() -> None:
    assert len(SIDON_BASE_SET_0_INDEXED) == 6
    assert len(set(SIDON_BASE_SET_0_INDEXED)) == 6
    assert all(0 <= x < POOL_SIZE for x in SIDON_BASE_SET_0_INDEXED)


def test_base_set_is_a_sidon_set_mod_49() -> None:
    # All 30 ordered pairwise differences (a - b) mod 49, a != b, distinct.
    differences = [
        (a - b) % POOL_SIZE
        for a in SIDON_BASE_SET_0_INDEXED
        for b in SIDON_BASE_SET_0_INDEXED
        if a != b
    ]
    assert len(differences) == 30
    assert len(set(differences)) == 30


def test_first_ticket_matches_the_disclosed_one_based_set() -> None:
    assert sidon_shift_ticket(0) == (1, 2, 4, 8, 13, 21)


def test_every_ticket_has_six_distinct_in_range_numbers() -> None:
    for shift in range(POOL_SIZE):
        ticket = sidon_shift_ticket(shift)
        assert len(ticket) == 6
        assert len(set(ticket)) == 6
        assert all(1 <= n <= 49 for n in ticket)


def test_pairwise_overlap_is_at_most_one_across_every_possible_shift_pair() -> None:
    # Exhaustive over all C(49,2) = 1176 shift pairs, not just the exposure
    # ladder this project actually uses -- the whole point of a Sidon-set
    # construction is that this holds uniformly with no k=8-style boundary.
    tickets = [set(sidon_shift_ticket(shift)) for shift in range(POOL_SIZE)]
    max_overlap = 0
    for i in range(POOL_SIZE):
        for j in range(i + 1, POOL_SIZE):
            max_overlap = max(max_overlap, len(tickets[i] & tickets[j]))
    assert max_overlap <= 1


def test_shift_periodicity_is_exactly_49() -> None:
    assert sidon_shift_ticket(0) == sidon_shift_ticket(49)
    assert sidon_shift_ticket(5) == sidon_shift_ticket(54)


def test_portfolio_is_a_strict_nested_prefix() -> None:
    portfolio_20 = sidon_shift_portfolio(20)
    for k in (1, 3, 5, 10, 15):
        assert sidon_shift_portfolio(k) == portfolio_20[:k]


def test_portfolio_of_zero_is_empty() -> None:
    assert sidon_shift_portfolio(0) == ()


def test_portfolio_rejects_out_of_range_count() -> None:
    with pytest.raises(ValueError, match="ticket_count must lie in"):
        sidon_shift_portfolio(50)
    with pytest.raises(ValueError, match="ticket_count must lie in"):
        sidon_shift_portfolio(-1)


def test_portfolio_at_pool_size_uses_every_shift_exactly_once() -> None:
    portfolio = sidon_shift_portfolio(POOL_SIZE)
    assert len(portfolio) == POOL_SIZE
    assert len(set(portfolio)) == POOL_SIZE  # all 49 tickets are pairwise distinct
