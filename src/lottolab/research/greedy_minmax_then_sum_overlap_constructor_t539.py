"""DAILY_539 (5/39) native mapping of GREEDY_MINMAX_THEN_SUM_OVERLAP_V1.

The shared constructor already takes `(pool_size, draw_size)` and contains
no B649-specific 49/6 algorithm. This module only supplies DAILY_539's
own pool/draw size from `DAILY_539_RULE_CONTRACT`.
"""

from __future__ import annotations

from lottolab.domain.lottery_rules import DAILY_539_RULE_CONTRACT
from lottolab.research.greedy_minmax_then_sum_overlap_constructor import (
    greedy_minmax_then_sum_overlap_portfolio,
)

NATIVE_MAPPING_STOP = "STOP_PHASE7_T539_NATIVE_MAPPING_DRIFT"

POOL_SIZE = DAILY_539_RULE_CONTRACT.main_number_max
DRAW_SIZE = DAILY_539_RULE_CONTRACT.main_number_count


def greedy_minmax_then_sum_overlap_portfolio_t539(
    ticket_count: int,
) -> tuple[tuple[int, ...], ...]:
    """The first `ticket_count` DAILY_539 tickets under the locked rule."""

    if POOL_SIZE != 39 or DRAW_SIZE != 5:
        raise ValueError(NATIVE_MAPPING_STOP)
    return greedy_minmax_then_sum_overlap_portfolio(POOL_SIZE, DRAW_SIZE, ticket_count)
