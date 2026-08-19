"""POWER_LOTTO Zone-1 (6/38) native mapping of GREEDY_MINMAX_THEN_SUM_OVERLAP_V1.

The shared constructor already takes `(pool_size, draw_size)` and contains
no B649 49/6 or T539 39/5 algorithm. This module only supplies POWER_LOTTO
Zone-1's own pool/draw size from `POWER_LOTTO_RULE_CONTRACT`. Zone-2 is
out of scope and is never read.
"""

from __future__ import annotations

from lottolab.domain.lottery_rules import POWER_LOTTO_RULE_CONTRACT
from lottolab.research.greedy_minmax_then_sum_overlap_constructor import (
    greedy_minmax_then_sum_overlap_portfolio,
)

NATIVE_MAPPING_STOP = "STOP_PHASE7_P638_NATIVE_MAPPING_DRIFT"

POOL_SIZE = POWER_LOTTO_RULE_CONTRACT.main_number_max
DRAW_SIZE = POWER_LOTTO_RULE_CONTRACT.main_number_count


def greedy_minmax_then_sum_overlap_portfolio_p638_zone1(
    ticket_count: int,
) -> tuple[tuple[int, ...], ...]:
    """The first `ticket_count` POWER_LOTTO Zone-1 tickets under the locked rule."""

    if POOL_SIZE != 38 or DRAW_SIZE != 6:
        raise ValueError(NATIVE_MAPPING_STOP)
    return greedy_minmax_then_sum_overlap_portfolio(POOL_SIZE, DRAW_SIZE, ticket_count)
