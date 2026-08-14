"""A deterministic, pairwise-low-overlap ticket family via a Sidon set in Z_49.

A Sidon set (B_2 set) is a set where every ordered pairwise difference is
distinct. For a 6-element Sidon set `B` in `Z_49`, cyclic shifts
`T_i = {(x + i) mod 49 : x in B}` have a clean, provable property: any two
distinct shifts intersect in at most one element (see `test_sidon_property`
in the test module for the full argument and an exhaustive verification
over all 49 possible shifts, not just the ones this project's exposure
ladder uses). This gives every ticket count in `1..49` a well-defined,
uniform-overlap-bound portfolio with no special-casing needed once the
pool is exhausted (unlike a naive disjoint-block construction, which must
decide what to do once more tickets are requested than fit disjointly).

This module makes no optimality claim -- it names one specific, disclosed,
verified geometry, nothing more.
"""

from __future__ import annotations

POOL_SIZE = 49

#: 0-based Sidon base set in Z_49: all 30 ordered pairwise differences are
#: distinct (verified in tests, both via direct computation and via
#: exhaustive overlap-size checking across every one of the 49 possible
#: shifts).
SIDON_BASE_SET_0_INDEXED: tuple[int, ...] = (0, 1, 3, 7, 12, 20)


def sidon_shift_ticket(shift: int) -> tuple[int, ...]:
    """The 1-based, ascending-sorted 6-number ticket for shift `shift`

    (`shift` may be any integer; only its value mod 49 matters).
    """

    return tuple(sorted((x + shift) % POOL_SIZE + 1 for x in SIDON_BASE_SET_0_INDEXED))


def sidon_shift_portfolio(ticket_count: int) -> tuple[tuple[int, ...], ...]:
    """The first `ticket_count` tickets, `T_0, T_1, ..., T_{ticket_count-1}`.

    A strict prefix relationship holds by construction: the portfolio for
    `ticket_count=k` is always the portfolio for `ticket_count=k-1` with
    exactly one ticket appended -- nothing is ever reordered or rebuilt.
    """

    if not 0 <= ticket_count <= POOL_SIZE:
        raise ValueError("ticket_count must lie in [0, 49] -- only 49 distinct shifts exist")
    return tuple(sidon_shift_ticket(shift) for shift in range(ticket_count))
