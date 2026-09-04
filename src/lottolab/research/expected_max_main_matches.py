"""EXPECTED_MAX_MAIN_MATCHES_V1: `E[max_t |t ∩ D|]` for a uniformly random draw `D`.

Frozen by `EXPECTED_HIT_UTILITY_CONTRACT_FREEZE_R1` as the sole retained
answer to `strategy_matrix_comparison.py`'s own `OBJECTIVE_GAPS /
EXPECTED_HIT_UTILITY_CONTRACT` gap ("coverage is a union probability; it is
not a utility or payout expectation"). This adds the expectation of the
*maximum* per-ticket main-number match count across a portfolio, exact via
the standard tail-sum identity for a bounded non-negative-integer random
variable `X`:

    E[X] = sum_{m=1}^{d} P(X >= m)          (X = max_t |t (intersect) D|, d = draw_size)

Each `P(X >= m)` term is exactly `Coverage(portfolio; m)` -- "at least one
ticket in the portfolio matches >= m of the draw's numbers" -- already
computed exactly by the existing evaluator family
(`bounded_coverage_optimizer.exact_portfolio_coverage` /
`exact_coverage_fast_evaluator.fast_exact_portfolio_coverage`). This module
adds no new combinatorial machinery: it calls that evaluator once per
threshold `m = 1..draw_size` and sums the results. Every threshold carries
forced unit weight -- there is no free parameter to tune.
"""

from __future__ import annotations

from collections.abc import Callable
from fractions import Fraction

from lottolab.research.exact_coverage_fast_evaluator import fast_exact_portfolio_coverage

Ticket = tuple[int, ...]
Portfolio = tuple[Ticket, ...]
CoverageEvaluator = Callable[[int, int, int, Portfolio], Fraction]


def expected_max_main_matches(
    pool_size: int,
    draw_size: int,
    portfolio: Portfolio,
    *,
    evaluator: CoverageEvaluator = fast_exact_portfolio_coverage,
) -> Fraction:
    """Exact `E[max_t |t ∩ D|]` over a uniformly random draw `D`.

    `evaluator` must share `fast_exact_portfolio_coverage`'s signature and
    return the exact `P(>= 1 ticket in portfolio has >= minimum_matches
    matches)`; `bounded_coverage_optimizer.exact_portfolio_coverage` is a
    drop-in, verified-parity alternative. The two evaluators' cost
    characteristics differ by threshold (see each module's own docstring):
    callers evaluating many distinct portfolios should pick and manage
    caching for whichever evaluator suits their scale, the same way
    existing callers of these evaluators already do.
    """

    total = Fraction(0)
    for minimum_matches in range(1, draw_size + 1):
        total += evaluator(pool_size, draw_size, minimum_matches, portfolio)
    return total
