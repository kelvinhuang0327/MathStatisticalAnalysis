from __future__ import annotations

import pytest

from lottolab.research.cyclic_sidon_shift_p638 import (
    POOL_SIZE,
    SIDON_BASE_SET_0_INDEXED,
    derive_base_set_by_backtracking_search,
    greedy_sidon_base,
    sidon_shift_portfolio,
    sidon_shift_ticket,
)

TICKET_SIZE = 6


def test_base_set_has_six_distinct_elements_in_range() -> None:
    assert len(SIDON_BASE_SET_0_INDEXED) == TICKET_SIZE
    assert len(set(SIDON_BASE_SET_0_INDEXED)) == TICKET_SIZE
    assert all(0 <= x < POOL_SIZE for x in SIDON_BASE_SET_0_INDEXED)


def test_base_set_is_a_sidon_set_mod_38() -> None:
    # All 6*5=30 ordered pairwise differences (a - b) mod 38, a != b, distinct.
    differences = [
        (a - b) % POOL_SIZE
        for a in SIDON_BASE_SET_0_INDEXED
        for b in SIDON_BASE_SET_0_INDEXED
        if a != b
    ]
    assert len(differences) == TICKET_SIZE * (TICKET_SIZE - 1)
    assert len(set(differences)) == len(differences)


def test_base_set_contains_no_self_paired_half_modulus_distance() -> None:
    # 19 == 38/2 is its own negation mod 38 -- the even-modulus pitfall this
    # module's docstring discloses. No pair of base elements may differ by
    # exactly this distance, or the Sidon check above could not hold.
    half = POOL_SIZE // 2
    for a in SIDON_BASE_SET_0_INDEXED:
        for b in SIDON_BASE_SET_0_INDEXED:
            if a != b:
                assert (a - b) % POOL_SIZE != half


def test_first_ticket_matches_the_disclosed_one_based_set() -> None:
    assert sidon_shift_ticket(0) == (1, 2, 4, 8, 18, 31)


def test_every_ticket_has_six_distinct_in_range_numbers() -> None:
    for shift in range(POOL_SIZE):
        ticket = sidon_shift_ticket(shift)
        assert len(ticket) == TICKET_SIZE
        assert len(set(ticket)) == TICKET_SIZE
        assert all(1 <= n <= POOL_SIZE for n in ticket)


def test_pairwise_overlap_is_at_most_one_across_every_possible_shift_pair() -> None:
    # Exhaustive over all C(38,2) = 703 shift pairs, not just the exposure
    # ladder this project's future execution task would use.
    tickets = [set(sidon_shift_ticket(shift)) for shift in range(POOL_SIZE)]
    max_overlap = 0
    pair_count = 0
    for i in range(POOL_SIZE):
        for j in range(i + 1, POOL_SIZE):
            pair_count += 1
            max_overlap = max(max_overlap, len(tickets[i] & tickets[j]))
    assert pair_count == 703
    assert max_overlap <= 1


def test_shift_periodicity_is_exactly_38() -> None:
    assert sidon_shift_ticket(0) == sidon_shift_ticket(38)
    assert sidon_shift_ticket(5) == sidon_shift_ticket(43)


def test_portfolio_is_a_strict_nested_prefix() -> None:
    portfolio_20 = sidon_shift_portfolio(20)
    for k in (1, 3, 5, 10, 15):
        assert sidon_shift_portfolio(k) == portfolio_20[:k]


def test_portfolio_rejects_out_of_range_count() -> None:
    with pytest.raises(ValueError, match="ticket_count must lie in"):
        sidon_shift_portfolio(39)
    with pytest.raises(ValueError, match="ticket_count must lie in"):
        sidon_shift_portfolio(-1)


def test_portfolio_at_pool_size_uses_every_shift_exactly_once() -> None:
    portfolio = sidon_shift_portfolio(POOL_SIZE)
    assert len(portfolio) == POOL_SIZE
    assert len(set(portfolio)) == POOL_SIZE


# --- Derivation-procedure tests: the module docstring's claims about how
# the base set was found are independently re-checked here, not just
# asserted in prose.


def test_plain_greedy_reproduces_big_lotto_and_daily_539() -> None:
    assert greedy_sidon_base(49, 6) == (0, 1, 3, 7, 12, 20)
    assert greedy_sidon_base(39, 5) == (0, 1, 3, 7, 12)


def test_plain_greedy_is_provably_insufficient_for_power_lotto_zone1() -> None:
    with pytest.raises(RuntimeError, match="exhausted all residues"):
        greedy_sidon_base(38, 6)


def test_backtracking_search_reproduces_big_lotto_and_daily_539() -> None:
    # Confirms backtracking is a completion of the same criterion, not a
    # different one: it must agree with plain greedy wherever greedy already
    # succeeds.
    assert derive_base_set_by_backtracking_search(49, 6) == (0, 1, 3, 7, 12, 20)
    assert derive_base_set_by_backtracking_search(39, 5) == (0, 1, 3, 7, 12)


def test_backtracking_search_reproduces_this_modules_own_constant() -> None:
    # Proves SIDON_BASE_SET_0_INDEXED was derived by the disclosed procedure,
    # not hand-picked: re-running the search must reproduce it exactly.
    assert derive_base_set_by_backtracking_search(38, 6) == SIDON_BASE_SET_0_INDEXED
