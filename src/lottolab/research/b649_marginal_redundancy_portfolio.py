"""Frozen pre-draw ranking candidate ``B649_MARGINAL_REDUNDANCY_PORTFOLIO_V1``.

A pre-draw ranking hypothesis over the canonical 11-stream B649 candidate
pool whose primary ranking key is *marginal redundancy* -- the number-set
overlap of a ticket against the already-selected prefix -- rather than
cross-stream support count.

The module invents no mathematics. It composes two authorities that already
exist on ``origin/main`` and modifies neither:

* :func:`lottolab.application.b649_operational_portfolio_selector.build_portfolio`
  -- the operational incumbent ``B649_OPERATIONAL_PORTFOLIO_SELECTOR``
  v1.0.0. It is called here purely as a *base-order authority*, with the
  production ``quality_by_strategy={}`` and a bucket equal to the distinct
  pool size, so the returned bucket is the incumbent's own full total order.
* ``construct_b649_candidate_set_low_overlap_v1`` in
  :mod:`lottolab.research.biglotto_multi_ticket_constructors_r1` -- the canonical
  deterministic constructor ``B649_CANDIDATE_SET_LOW_OVERLAP_V1`` v1, whose
  frozen objective is
  ``lexicographic_minimum(MAX_OVERLAP, TOTAL_OVERLAP, ORIGINAL_RANK)`` over a
  caller-supplied ordered candidate pool.

Every input is available strictly before the target draw: the pool is the
tickets the 11 streams emit from prior history, and the ranking consumes only
those tickets' own numbers. No winning-number, prize, hit or outcome field is
read, and no parameter is fitted to any outcome.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from itertools import pairwise
from typing import Final

from lottolab.application.b649_operational_portfolio_selector import (
    StrategyCandidate,
    Ticket,
    build_portfolio,
)
from lottolab.research.biglotto_multi_ticket_constructors_r1 import (
    B649_CANDIDATE_SET_LOW_OVERLAP_V1_METADATA,
    construct_b649_candidate_set_low_overlap_v1,
)

CANDIDATE_NAME: Final[str] = "B649_MARGINAL_REDUNDANCY_PORTFOLIO_V1"
CANDIDATE_VERSION: Final[str] = "1.0.0"
SUPPORTED_K: Final[tuple[int, int, int]] = (5, 10, 20)

BASE_ORDER_AUTHORITY: Final[str] = "B649_OPERATIONAL_PORTFOLIO_SELECTOR@1.0.0"
SELECTION_AUTHORITY: Final[str] = "B649_CANDIDATE_SET_LOW_OVERLAP_V1@v1"

PRE_DRAW_FEATURES_USED: Final[tuple[str, ...]] = (
    "MAX_OVERLAP: max_{s in selected} |numbers(t) & numbers(s)|",
    "TOTAL_OVERLAP: sum_{s in selected} |numbers(t) & numbers(s)|",
    "ORIGINAL_RANK: index of t in the incumbent's full total order",
)
RANK_FORMULA: Final[str] = (
    "greedy sequential; at each step select the unselected pool ticket minimizing "
    "(MAX_OVERLAP, TOTAL_OVERLAP, ORIGINAL_RANK) lexicographically"
)
TIE_BREAK_RULE: Final[str] = (
    "ORIGINAL_RANK, i.e. the incumbent order (-support_count, -summed_quality, ticket ASC); "
    "distinct per ticket, so the induced order is total and no residual tie exists"
)
DETERMINISM_RULE: Final[str] = (
    "PURE_DETERMINISTIC_NO_RNG: no random source, wall clock, hash-order or floating point; "
    "invariant to the order in which the 11 streams are supplied, because the pool is "
    "deduplicated and canonically re-ordered by the incumbent before selection"
)
OUTCOME_FIELDS_USED: Final[str] = "NONE"


@dataclass(frozen=True)
class MarginalRedundancyPortfolio:
    """One frozen candidate ranking over a single pre-draw pool."""

    candidate_name: str
    candidate_version: str
    base_order: tuple[Ticket, ...]
    tickets_by_k: Mapping[int, tuple[Ticket, ...]]

    @property
    def ranked_order(self) -> tuple[Ticket, ...]:
        """The candidate's total order, i.e. its largest supported prefix."""
        return self.tickets_by_k[max(self.tickets_by_k)]


def incumbent_base_order(candidates: Sequence[StrategyCandidate]) -> tuple[Ticket, ...]:
    """The incumbent's own full total order over the deduplicated pool.

    Calls the unmodified incumbent with the production ``quality_by_strategy``
    (empty) and a single bucket equal to the distinct ticket count, so the
    bucket returned *is* the complete ranked order rather than a prefix.
    """
    distinct = {tuple(sorted(raw)) for candidate in candidates for raw in candidate.tickets}
    if not distinct:
        raise ValueError("EMPTY_CANDIDATE_POOL")
    return tuple(build_portfolio(candidates, {}, bucket_sizes=(len(distinct),))[len(distinct)])


def build_marginal_redundancy_portfolio(
    candidates: Sequence[StrategyCandidate],
    budgets: Sequence[int] = SUPPORTED_K,
) -> MarginalRedundancyPortfolio:
    """Rank the pre-draw pool by marginal redundancy against the selected prefix.

    :param candidates: The canonical 11-stream pre-draw pool. Only the emitted
        tickets are read; no stream metadata influences the order.
    :param budgets: Requested K budgets; every value must be supported by the
        canonical constructor (5, 10, 20).
    :raises ValueError: If a budget is unsupported, or the distinct pool is
        smaller than the largest requested budget.
    """
    requested = tuple(sorted(set(budgets)))
    unsupported = [k for k in requested if k not in SUPPORTED_K]
    if unsupported:
        raise ValueError(f"UNSUPPORTED_BUDGET: {unsupported}")
    if not requested:
        raise ValueError("NO_BUDGET_REQUESTED")

    base_order = incumbent_base_order(candidates)
    if len(base_order) < max(requested):
        raise ValueError(f"POOL_TOO_SMALL: {len(base_order)} distinct tickets < K{max(requested)}")

    tickets_by_k = {
        k: tuple(construct_b649_candidate_set_low_overlap_v1(base_order, k)) for k in requested
    }

    # The canonical constructor is prefix-nested in ticket_count; assert it here
    # rather than assuming it, so a donor change can never silently produce
    # non-nested K-buckets under a fixed-K comparison.
    for smaller, larger in pairwise(requested):
        if tickets_by_k[larger][:smaller] != tickets_by_k[smaller]:
            raise ValueError("NON_NESTED_CANDIDATE_BUDGETS")

    return MarginalRedundancyPortfolio(
        candidate_name=CANDIDATE_NAME,
        candidate_version=CANDIDATE_VERSION,
        base_order=base_order,
        tickets_by_k=tickets_by_k,
    )


def candidate_identity() -> dict[str, object]:
    """The frozen candidate definition, for verbatim inclusion in artifacts."""
    return {
        "CANDIDATE_NAME": CANDIDATE_NAME,
        "CANDIDATE_VERSION": CANDIDATE_VERSION,
        "INPUT_AUTHORITY": {
            "pool": "tools.b649_operational_prediction_loop.STRATEGY_STREAMS (11 enabled streams)",
            "base_order": BASE_ORDER_AUTHORITY,
            "selection": SELECTION_AUTHORITY,
            "selection_objective": (B649_CANDIDATE_SET_LOW_OVERLAP_V1_METADATA.SELECTION_OBJECTIVE),
        },
        "PRE_DRAW_FEATURES_USED": list(PRE_DRAW_FEATURES_USED),
        "RANK_FORMULA": RANK_FORMULA,
        "TIE_BREAK_RULE": TIE_BREAK_RULE,
        "SUPPORTED_K": list(SUPPORTED_K),
        "DETERMINISM_RULE": DETERMINISM_RULE,
        "OUTCOME_FIELDS_USED": OUTCOME_FIELDS_USED,
    }
