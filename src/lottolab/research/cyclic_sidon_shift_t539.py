"""A deterministic, pairwise-low-overlap ticket family for DAILY_539 (5/39),

via a Sidon set in Z_39. Structurally identical to
`cyclic_sidon_shift.py` (BIG_LOTTO, 6/49) -- see that module's docstring
for the full mathematical argument. This is a separate, explicit module
rather than a generalization of the BIG_LOTTO one, matching how each
locked preregistration hardcodes its own verified, lottery-native
constant rather than sharing a mutable parameterization.

The base set was found by deterministic greedy search (start from `{0}`;
repeatedly try the smallest not-yet-included residue and keep it only if
it introduces no duplicate pairwise difference with the current set; stop
at 5 elements) -- run independently for modulus 39, not derived from or
assumed to match BIG_LOTTO's base set. It happens to equal the first five
elements of the BIG_LOTTO base set `{0,1,3,7,12,20}`, disclosed here, not
hidden -- but this equality is not claimed to be mathematically forced.
"A subset of a Sidon set is itself a Sidon set" is true, and is exactly
why this set's Sidon-in-Z_39 property was worth independently checking
(and was: see `test_base_set_is_a_sidon_set_mod_39`) -- but that lemma
alone does not imply two independent greedy searches over *different*
moduli (39 vs. 49) must produce the same prefix, since Sidon-ness mod 39
and mod 49 are different conditions on different difference sets. The
two searches agreeing here is consistent with both starting from `{0}`
and never yet needing to wrap around within the first five elements
(every pairwise difference involved is well under the smaller modulus),
not a theorem that guarantees agreement in general.
"""

from __future__ import annotations

POOL_SIZE = 39

#: 0-based Sidon base set in Z_39: all 20 ordered pairwise differences are
#: distinct (verified in tests, both via direct computation and via
#: exhaustive overlap-size checking across every one of the 39 possible
#: shifts).
SIDON_BASE_SET_0_INDEXED: tuple[int, ...] = (0, 1, 3, 7, 12)


def sidon_shift_ticket(shift: int) -> tuple[int, ...]:
    """The 1-based, ascending-sorted 5-number ticket for shift `shift`

    (`shift` may be any integer; only its value mod 39 matters).
    """

    return tuple(sorted((x + shift) % POOL_SIZE + 1 for x in SIDON_BASE_SET_0_INDEXED))


def sidon_shift_portfolio(ticket_count: int) -> tuple[tuple[int, ...], ...]:
    """The first `ticket_count` tickets, `T_0, T_1, ..., T_{ticket_count-1}`.

    A strict prefix relationship holds by construction, identical to the
    BIG_LOTTO module.
    """

    if not 0 <= ticket_count <= POOL_SIZE:
        raise ValueError("ticket_count must lie in [0, 39] -- only 39 distinct shifts exist")
    return tuple(sidon_shift_ticket(shift) for shift in range(ticket_count))
