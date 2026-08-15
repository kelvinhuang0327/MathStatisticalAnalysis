"""GREEDY_MIN_OVERLAP_CONSTRUCTOR_P638_ZONE1_V1 -- POWER_LOTTO Zone-1 (6/38)
native instance of the shared greedy_min_overlap_constructor, arm B of
STRATEGY_MATRIX_PHASE5_P638_NON_SIDON_LOW_OVERLAP_NATIVE_DESIGN_R1.

Unlike `cyclic_sidon_shift_p638.py` -- which needed a genuinely new
*derived* constant (a backtracking-derived Sidon base set, because
Z_38's even modulus makes 19 = 38/2 its own negation, defeating plain
greedy Sidon search; see that module's own docstring) -- this module
hardcodes no derived constant at all: `greedy_min_overlap_portfolio`
(`src/lottolab/research/greedy_min_overlap_constructor.py`) already
takes `(pool_size, draw_size)` as plain parameters and contains no
B649/T539-specific tuning anywhere in its body (confirmed by reading
that module's unmodified source in this task; already established by
`strategy-matrix-phase5-diversification-constructor-frontier-design-r1.md`
S11(c) and re-confirmed independently by
`strategy-matrix-phase5-t539-non-sidon-low-overlap-native-design-r1.md`
S5). This module's only "mapping" is supplying POWER_LOTTO Zone-1's own
pool/draw size -- 38 and 6, matching `POWER_LOTTO_RULE_CONTRACT`
(`main_number_max=38`, `main_number_count=6`) in
`src/lottolab/domain/lottery_rules.py`, not invented or guessed. Zone-2
(1-of-8, `POWER_LOTTO_RULE_CONTRACT.special_number_*`) is out of scope
entirely and is never read by this module.

The shared constructor has no modular/cyclic-shift structure of any
kind -- its candidate space is a direct
`itertools.combinations(range(1, pool_size + 1), draw_size)` scan, and
its acceptance rule is a plain set-intersection overlap count. It
therefore has no analogue of the even-modulus self-paired-distance
obstruction that forced `cyclic_sidon_shift_p638.py`'s backtracking
search: there is no residue, no shift, and no "distance mod pool_size"
concept anywhere in this constructor for pool_size=38's evenness to
interact with. See the design doc S5 for the full argument and a
toy-scale check at a pool size sharing 38's own remainder shape
(`pool_size % draw_size == 2`).

This module exists only so a later execution task has one stable,
named entry point with the same `portfolio(ticket_count)` shape as
`cyclic_sidon_shift_p638.sidon_shift_portfolio`, not because the shared
algorithm needed any lottery-specific change.

Not invoked at real `(38, 6)` scale by this design task -- see the
design doc S2 and S6.
"""

from __future__ import annotations

from lottolab.research.greedy_min_overlap_constructor import greedy_min_overlap_portfolio

POOL_SIZE = 38
DRAW_SIZE = 6


def greedy_min_overlap_portfolio_p638_zone1(
    ticket_count: int,
) -> tuple[tuple[int, ...], ...]:
    """The first `ticket_count` POWER_LOTTO Zone-1 tickets under the greedy
    min-max-overlap rule -- an unconditional delegation to the shared,
    unmodified `greedy_min_overlap_portfolio(POOL_SIZE, DRAW_SIZE, ...)`.
    See that function's own docstring for the full rule definition.
    """

    return greedy_min_overlap_portfolio(POOL_SIZE, DRAW_SIZE, ticket_count)
