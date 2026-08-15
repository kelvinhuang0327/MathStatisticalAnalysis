"""GREEDY_MIN_OVERLAP_CONSTRUCTOR_T539_V1 -- DAILY_539 (5/39) native
instance of the shared greedy_min_overlap_constructor, arm B of
STRATEGY_MATRIX_PHASE5_T539_NON_SIDON_LOW_OVERLAP_NATIVE_DESIGN_R1.

Unlike cyclic_sidon_shift_t539.py, this module hardcodes no *derived*
constant: greedy_min_overlap_portfolio
(src/lottolab/research/greedy_min_overlap_constructor.py) already takes
`(pool_size, draw_size)` as plain parameters and contains no
B649-specific tuning anywhere in its body (confirmed by reading that
module's unmodified source in this task, and previously established by
strategy-matrix-phase5-diversification-constructor-frontier-design-r1.md
S11(c): "neither module hard-codes 49 or 6 anywhere"). The only
"mapping" this module performs is supplying DAILY_539's own pool/draw
size -- 39 and 5, matching DAILY_539_RULE_CONTRACT
(main_number_max=39, main_number_count=5) in
src/lottolab/domain/lottery_rules.py, not invented or guessed.

This module exists only so the later execution task has one stable,
named entry point with the same `portfolio(ticket_count)` shape as
cyclic_sidon_shift_t539.sidon_shift_portfolio, not because the shared
algorithm needed any lottery-specific change.

Not invoked at real (39, 5) scale by this design task -- see
docs/research/strategy-matrix-phase5-t539-non-sidon-low-overlap-native-design-r1.md
S2 and S6.
"""

from __future__ import annotations

from lottolab.research.greedy_min_overlap_constructor import greedy_min_overlap_portfolio

POOL_SIZE = 39
DRAW_SIZE = 5


def greedy_min_overlap_portfolio_t539(
    ticket_count: int,
) -> tuple[tuple[int, ...], ...]:
    """The first `ticket_count` DAILY_539 tickets under the greedy
    min-max-overlap rule -- an unconditional delegation to the shared,
    unmodified `greedy_min_overlap_portfolio(POOL_SIZE, DRAW_SIZE, ...)`.
    See that function's own docstring for the full rule definition.
    """

    return greedy_min_overlap_portfolio(POOL_SIZE, DRAW_SIZE, ticket_count)
