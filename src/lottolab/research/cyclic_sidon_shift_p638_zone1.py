"""A deterministic, pairwise-low-overlap ticket family for POWER_LOTTO zone1

(6/38, the main draw; the separate 1/8 second zone is out of scope -- see
`docs/research/matrix-native-results/diversification-coverage-p638-zone1-v1-preregistration.md`
Sec 7), via a Sidon set in Z_38. Structurally identical in intent to
`cyclic_sidon_shift.py` (BIG_LOTTO, 6/49) and `cyclic_sidon_shift_t539.py`
(DAILY_539, 5/39) -- see the BIG_LOTTO module's docstring for the full
mathematical argument for why a Sidon base set gives every cyclic shift
pairwise ticket overlap <= 1.

**Construction differs from the other two lotteries, disclosed here.** The
identical no-lookahead greedy recipe used for BIG_LOTTO and DAILY_539
(start from `{0}`; repeatedly append the smallest not-yet-included residue
that introduces no duplicate pairwise difference; stop once the draw size
is reached) reaches the same `{0, 1, 3, 7, 12}` prefix in Z_38 that the
other two lotteries' searches independently also reached in their own
moduli -- but then **stalls**: no residue in `12 < x < 38` extends
`{0, 1, 3, 7, 12}` to a valid 6th element mod 38 (every one of them
collides with an already-used pairwise difference; checked exhaustively,
not asserted). Z_38 is simply tighter than Z_39/Z_49 for a 6-element Sidon
set (30 ordered differences needed out of only 37 available nonzero
residues, versus 48 for Z_49).

This module therefore uses **deterministic backtracking search** instead:
depth-first, smallest untried candidate at each position exactly as
before, but backtracking to the most recent choice point (not just
stopping) when a position has no valid extension. Still fully
deterministic, still smallest-first, still discloses everything it tries
-- a minimal, principled extension of the same recipe, not a different
family of construction. This mirrors how the BIG_LOTTO cell itself
superseded an earlier `CYCLIC_MINIMUM_REUSE` draft constructor before
locking (see that preregistration's header) -- iterating on constructor
*feasibility* pre-lock is the established, legitimate process; it is
*post-lock* results that this project's no-rescue rule protects.

The backtracking search rejects `12` as the 5th element (not `7` or
earlier) and finds `{0, 1, 3, 7, 17, 30}`: the first **four** elements
coincide with BIG_LOTTO/DAILY_539's shared prefix, not five -- disclosed,
not hidden, and (as with the other two moduli) not claimed to be
mathematically forced.
"""

from __future__ import annotations

POOL_SIZE = 38

#: 0-based Sidon base set in Z_38: all 30 ordered pairwise differences are
#: distinct (verified in tests, both via direct computation and via
#: exhaustive overlap-size checking across every one of the 38 possible
#: shifts). Found by deterministic backtracking search, not plain greedy
#: -- see module docstring.
SIDON_BASE_SET_0_INDEXED: tuple[int, ...] = (0, 1, 3, 7, 17, 30)


def sidon_shift_ticket(shift: int) -> tuple[int, ...]:
    """The 1-based, ascending-sorted 6-number zone1 ticket for shift `shift`

    (`shift` may be any integer; only its value mod 38 matters).
    """

    return tuple(sorted((x + shift) % POOL_SIZE + 1 for x in SIDON_BASE_SET_0_INDEXED))


def sidon_shift_portfolio(ticket_count: int) -> tuple[tuple[int, ...], ...]:
    """The first `ticket_count` tickets, `T_0, T_1, ..., T_{ticket_count-1}`.

    A strict prefix relationship holds by construction, identical to the
    BIG_LOTTO and DAILY_539 modules.
    """

    if not 0 <= ticket_count <= POOL_SIZE:
        raise ValueError("ticket_count must lie in [0, 38] -- only 38 distinct shifts exist")
    return tuple(sidon_shift_ticket(shift) for shift in range(ticket_count))
