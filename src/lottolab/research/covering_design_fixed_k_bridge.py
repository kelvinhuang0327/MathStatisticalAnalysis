"""Research composition from a Tabu7 candidate cover to fixed-K Big Lotto tickets.

CANDIDATE_POOL_COMPLETE_PAIR_COVER: YES (independently checked before selection).
SELECTED_FIXED_K_PORTFOLIO_COMPLETE_PAIR_COVER: NOT_CLAIMED.

Only the upstream candidate pool is a complete pair-cover. The selected
fixed-K portfolio is not a complete covering design. This bridge adds no
optimizer or objective and claims no global low-overlap optimum, predictive
edge, expected-match improvement, profitability, Matrix correctness
registration, or production strategy support.
"""

from __future__ import annotations

import itertools

from lottolab.domain.lottery_rules import BIG_LOTTO_RULE_CONTRACT
from lottolab.research.covering_design_tabu7 import (
    TabuSearch7RunConfig,
    run_covering_design_tabu7,
)
from lottolab.research.low_overlap_portfolio_constructor import build_low_overlap_portfolio

_K_TICKET_SCOPE = (2, 3, 5, 10, 20)


def build_big_lotto_fixed_k_portfolio_from_tabu7_cover(
    k_ticket: int,
    *,
    config: TabuSearch7RunConfig,
) -> tuple[tuple[int, ...], ...]:
    """Select exactly k_ticket distinct legal main-number tickets from a verified pool.

    k_ticket is restricted to 2, 3, 5, 10, or 20; it is not the design's
    block size (6). Only best_complete_blocks supplies candidates. Map
    zero-based elements to 1..49, canonicalize and deduplicate lexically,
    and independently verify all pairs before geometry-only selection.

    The returned portfolio preserves selector order and is reproducible
    for identical complete config and source identity. Complete pair
    coverage is guaranteed only for the candidate pool, never the result.

    Raise ValueError for unsupported k_ticket, illegal candidates, or an
    incomplete candidate pool. Producer and selector errors propagate.
    """
    if type(k_ticket) is not int or k_ticket not in _K_TICKET_SCOPE:
        raise ValueError("k_ticket must be an integer in {2, 3, 5, 10, 20}")

    result = run_covering_design_tabu7(v=49, k=6, t=2, config=config)
    rules = BIG_LOTTO_RULE_CONTRACT
    unique: set[tuple[int, ...]] = set()
    for index, block in enumerate(result.best_complete_blocks):
        if len(block) != rules.main_number_count:
            raise ValueError(f"Tabu7 candidate {index} must contain six numbers")
        # Check before adding one: bool would otherwise become a legal-looking int.
        if any(type(number) is not int for number in block):
            raise ValueError(f"Tabu7 candidate {index} contains a non-integer number")
        ticket = tuple(sorted(number + 1 for number in block))
        if len(set(ticket)) != rules.main_number_count:
            raise ValueError(f"Tabu7 candidate {index} contains duplicate numbers")
        if any(not rules.main_number_min <= number <= rules.main_number_max for number in ticket):
            raise ValueError(f"Tabu7 candidate {index} maps outside Big Lotto range 1..49")
        unique.add(ticket)

    candidates = tuple(sorted(unique))
    required_pairs = set(
        itertools.combinations(range(rules.main_number_min, rules.main_number_max + 1), 2)
    )
    covered_pairs = {pair for ticket in candidates for pair in itertools.combinations(ticket, 2)}
    missing_pairs = required_pairs - covered_pairs
    if missing_pairs:
        raise ValueError(
            "Tabu7 candidate pool is not a complete Big Lotto pair-cover: "
            f"{len(missing_pairs)} missing pairs; first missing pair {min(missing_pairs)}"
        )

    return build_low_overlap_portfolio(
        candidates, k_ticket, BIG_LOTTO_RULE_CONTRACT, optional_scores=None
    )


__all__ = ["build_big_lotto_fixed_k_portfolio_from_tabu7_cover"]
