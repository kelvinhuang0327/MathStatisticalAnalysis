"""Cross-family redundancy-pruned ensemble V1 candidate batch R1.

Each of the nine frozen candidates unions the native matched-budget portfolios
of the three retained families.  MULTISCALE_FREQUENCY is frozen-pruned and is
never imported or called.  There is no rank fusion, randomness, I/O, runtime
fallback, or production catalog registration.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from itertools import islice, pairwise
from types import MappingProxyType, ModuleType
from typing import Final, cast

from lottolab.research import (
    biglotto_conditional_cooccurrence_multi_ticket_candidate_batch_r1 as _cooccurrence,
)
from lottolab.research import (
    biglotto_graph_network_multi_ticket_candidate_batch_r1 as _graph_network,
)
from lottolab.research import (
    biglotto_multiscale_omission_pressure_multi_ticket_candidate_batch_r1 as _omission,
)

type Ticket = tuple[int, int, int, int, int, int]
type HistoryInput = Sequence[object] | Iterable[object]
type TicketPortfolio = tuple[Ticket, ...]
type ParentProducer = Callable[[HistoryInput, int], object]

HYPOTHESIS_VERSION: Final[str] = "V1"
HYPOTHESIS_ID: Final[str] = "XFAM_H_REDUNDANCY_PRUNED_ENSEMBLE"
NEW_FAMILY_ID: Final[str] = "CROSS_FAMILY_REDUNDANCY_PRUNED_ENSEMBLE_V1"
LOTTERY_TYPE: Final[str] = "BIG_LOTTO"
PICK_COUNT: Final[int] = 6
NUMBER_DOMAIN: Final[tuple[int, int]] = (1, 49)
MINIMUM_HISTORY: Final[int] = 751
CAUSAL_CUTOFF_RULE: Final[str] = "STRICTLY_PRIOR_HISTORY_EXCLUSIVE_TARGET_INDEX"
DETERMINISM_CLASS: Final[str] = "PURE_DETERMINISTIC_NO_RNG"
RNG_SEMANTICS: Final[str] = "NONE"
FALLBACK: Final[str] = "NO_RUNTIME_FALLBACK"
AGGREGATION: Final[str] = "UNION_OF_RETAINED_NATIVE_TICKETS_AT_MATCHED_BUDGET"
UNION_ORDER_RULE: Final[str] = (
    "RETAINED_FAMILY_ID_ASCENDING_THEN_NATIVE_PARENT_ORDER;"
    "EXACT_DUPLICATE_TUPLES_FIRST_OCCURRENCE_WINS"
)
TICKET_CARDINALITY_RULE: Final[str] = (
    "UNION_OF_RETAINED_NATIVE_TICKETS_AT_MATCHED_BUDGET;"
    "EXACT_DUPLICATE_TUPLES_DEDUPLICATED;COMPUTED_AT_CONSTRUCTION"
)

RETAINED_FAMILY_IDS: Final[tuple[str, str, str]] = (
    "CONDITIONAL_COOCCURRENCE",
    "GRAPH_NETWORK",
    "MULTISCALE_OMISSION_PRESSURE",
)
PRUNED_FAMILY_ID: Final[str] = "MULTISCALE_FREQUENCY"
CONSTRUCTOR_IDS: Final[tuple[str, str, str]] = (
    "B649_CANDIDATE_SET_LOW_OVERLAP_V1",
    "B649_CANDIDATE_SET_EXPOSURE_BALANCED_V1",
    "B649_CANDIDATE_SET_HYBRID_DIVERSITY_V1",
)
TICKET_BUDGETS: Final[tuple[int, int, int]] = (5, 10, 20)

_FAMILY_SLUGS: Final[Mapping[str, str]] = MappingProxyType(
    {
        "CONDITIONAL_COOCCURRENCE": "conditional_cooccurrence",
        "GRAPH_NETWORK": "graph_network",
        "MULTISCALE_OMISSION_PRESSURE": "multiscale_omission_pressure",
    }
)
_CONSTRUCTOR_SYMBOL_SLUGS: Final[Mapping[str, str]] = MappingProxyType(
    {
        "B649_CANDIDATE_SET_LOW_OVERLAP_V1": "low_overlap",
        "B649_CANDIDATE_SET_EXPOSURE_BALANCED_V1": "exposure_balanced",
        "B649_CANDIDATE_SET_HYBRID_DIVERSITY_V1": "hybrid_diversity",
    }
)
_PARENT_MODULES: Final[Mapping[str, ModuleType]] = MappingProxyType(
    {
        "CONDITIONAL_COOCCURRENCE": _cooccurrence,
        "GRAPH_NETWORK": _graph_network,
        "MULTISCALE_OMISSION_PRESSURE": _omission,
    }
)


class RequiredParentUnavailableError(ValueError):
    """Raised when a retained parent is missing or cannot be used as specified."""


def _constructor_symbol_slug(constructor_id: str) -> str:
    try:
        return _CONSTRUCTOR_SYMBOL_SLUGS[constructor_id]
    except KeyError as error:
        raise ValueError(f"unsupported constructor: {constructor_id!r}") from error


def _implementation_symbol(constructor_id: str, ticket_budget: int) -> str:
    return (
        "produce_b649_cross_family_redundancy_pruned_ensemble_v1_"
        f"{_constructor_symbol_slug(constructor_id)}_k{ticket_budget}"
    )


IMPLEMENTATION_SYMBOLS: Final[tuple[str, ...]] = tuple(
    _implementation_symbol(constructor_id, ticket_budget)
    for constructor_id in CONSTRUCTOR_IDS
    for ticket_budget in TICKET_BUDGETS
)


def _validate_ticket(raw_ticket: object, location: str) -> Ticket:
    if type(raw_ticket) is not tuple:
        raise ValueError(f"{location} must be an immutable tuple of six integers")
    values = cast(tuple[object, ...], raw_ticket)
    if len(values) != PICK_COUNT:
        raise ValueError(f"{location} must contain exactly {PICK_COUNT} numbers")
    if not all(type(number) is int for number in values):
        raise ValueError(f"{location} must contain only integers")
    numbers = cast(tuple[int, ...], values)
    if any(number < NUMBER_DOMAIN[0] or number > NUMBER_DOMAIN[1] for number in numbers):
        raise ValueError(f"{location} contains a number outside 1..49")
    if any(left >= right for left, right in pairwise(numbers)):
        raise ValueError(f"{location} must be strictly ascending with no duplicates")
    return cast(Ticket, numbers)


def _validate_parent_portfolio(
    raw_portfolio: object, family_id: str, ticket_budget: int
) -> TicketPortfolio:
    if isinstance(raw_portfolio, Mapping | str | bytes):
        raise ValueError(
            f"retained parent {family_id} did not emit a ticket portfolio; "
            "refusing to substitute another family"
        )
    try:
        raw_tickets = tuple(cast(Iterable[object], raw_portfolio))
    except TypeError as error:
        raise ValueError(
            f"retained parent {family_id} did not emit a ticket portfolio; "
            "refusing to substitute another family"
        ) from error
    if len(raw_tickets) != ticket_budget:
        raise ValueError(
            f"retained parent {family_id} must emit exactly budget={ticket_budget} "
            f"tickets; received {len(raw_tickets)}"
        )
    tickets = tuple(
        _validate_ticket(raw_ticket, f"retained parent {family_id}[{index}]")
        for index, raw_ticket in enumerate(raw_tickets)
    )
    if len(set(tickets)) != len(tickets):
        raise ValueError(f"retained parent {family_id} emitted duplicate tickets")
    return tickets


def _read_prior_prefix(history: HistoryInput, target_index: int) -> tuple[object, ...]:
    if type(target_index) is not int or target_index < 0:
        raise ValueError("target_index must be a non-negative integer")
    try:
        if isinstance(history, Sequence):
            if target_index > len(history):
                raise ValueError("target_index must not exceed history length")
            return tuple(history[:target_index])
        prefix = tuple(islice(iter(history), target_index))
        if len(prefix) != target_index:
            raise ValueError("target_index must not exceed history length")
        return prefix
    except ValueError:
        raise
    except (TypeError, IndexError) as error:
        raise ValueError("history must supply a finite chronological prefix") from error


def _parent_producer_name(family_id: str, constructor_id: str, ticket_budget: int) -> str:
    try:
        family_slug = _FAMILY_SLUGS[family_id]
    except KeyError as error:
        raise RequiredParentUnavailableError(
            f"unknown retained family {family_id}; refusing to substitute another family"
        ) from error
    return (
        f"produce_b649_{family_slug}_multiticket_"
        f"{_constructor_symbol_slug(constructor_id)}_v1_k{ticket_budget}"
    )


def _parent_producer(
    family_id: str, constructor_id: str, ticket_budget: int
) -> ParentProducer:
    try:
        module = _PARENT_MODULES[family_id]
    except KeyError as error:
        raise RequiredParentUnavailableError(
            f"retained parent module unavailable: {family_id}; "
            "refusing to substitute another family"
        ) from error
    name = _parent_producer_name(family_id, constructor_id, ticket_budget)
    try:
        producer = getattr(module, name)
    except AttributeError as error:
        raise RequiredParentUnavailableError(
            f"retained parent producer unavailable: {family_id} {name}; "
            "refusing to substitute another family"
        ) from error
    if not callable(producer):
        raise RequiredParentUnavailableError(
            f"retained parent producer unavailable: {family_id} {name}; "
            "refusing to substitute another family"
        )
    return cast(ParentProducer, producer)


def union_retained_native_tickets_at_matched_budget(
    parent_portfolios: Mapping[str, object], ticket_budget: int
) -> TicketPortfolio:
    """Union retained native tickets in family-id order; first exact tuple wins."""

    if ticket_budget not in TICKET_BUDGETS:
        raise ValueError(f"unsupported ticket budget: {ticket_budget}")
    missing = [family_id for family_id in RETAINED_FAMILY_IDS if family_id not in parent_portfolios]
    if missing:
        raise RequiredParentUnavailableError(
            "missing retained parent "
            f"{missing[0]}; refusing to substitute another family"
        )

    seen: set[Ticket] = set()
    union: list[Ticket] = []
    for family_id in RETAINED_FAMILY_IDS:
        tickets = _validate_parent_portfolio(
            parent_portfolios[family_id], family_id, ticket_budget
        )
        for ticket in tickets:
            if ticket in seen:
                continue
            seen.add(ticket)
            union.append(ticket)

    if not ticket_budget <= len(union) <= ticket_budget * len(RETAINED_FAMILY_IDS):
        raise ValueError("union cardinality violates retained-family budget bounds")
    return tuple(union)


def _produce_matched_budget_union(
    constructor_id: str,
    ticket_budget: int,
    history: HistoryInput,
    target_index: int,
) -> TicketPortfolio:
    if constructor_id not in CONSTRUCTOR_IDS:
        raise ValueError(f"unsupported constructor: {constructor_id!r}")
    if ticket_budget not in TICKET_BUDGETS:
        raise ValueError(f"unsupported ticket budget: {ticket_budget}")
    prior_history = _read_prior_prefix(history, target_index)
    parent_portfolios: dict[str, object] = {}
    for family_id in RETAINED_FAMILY_IDS:
        producer = _parent_producer(family_id, constructor_id, ticket_budget)
        parent_portfolios[family_id] = producer(prior_history, target_index)
    return union_retained_native_tickets_at_matched_budget(parent_portfolios, ticket_budget)


def produce_b649_cross_family_redundancy_pruned_ensemble_v1_low_overlap_k5(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    return _produce_matched_budget_union(
        "B649_CANDIDATE_SET_LOW_OVERLAP_V1", 5, history, target_index
    )


def produce_b649_cross_family_redundancy_pruned_ensemble_v1_low_overlap_k10(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    return _produce_matched_budget_union(
        "B649_CANDIDATE_SET_LOW_OVERLAP_V1", 10, history, target_index
    )


def produce_b649_cross_family_redundancy_pruned_ensemble_v1_low_overlap_k20(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    return _produce_matched_budget_union(
        "B649_CANDIDATE_SET_LOW_OVERLAP_V1", 20, history, target_index
    )


def produce_b649_cross_family_redundancy_pruned_ensemble_v1_exposure_balanced_k5(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    return _produce_matched_budget_union(
        "B649_CANDIDATE_SET_EXPOSURE_BALANCED_V1", 5, history, target_index
    )


def produce_b649_cross_family_redundancy_pruned_ensemble_v1_exposure_balanced_k10(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    return _produce_matched_budget_union(
        "B649_CANDIDATE_SET_EXPOSURE_BALANCED_V1", 10, history, target_index
    )


def produce_b649_cross_family_redundancy_pruned_ensemble_v1_exposure_balanced_k20(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    return _produce_matched_budget_union(
        "B649_CANDIDATE_SET_EXPOSURE_BALANCED_V1", 20, history, target_index
    )


def produce_b649_cross_family_redundancy_pruned_ensemble_v1_hybrid_diversity_k5(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    return _produce_matched_budget_union(
        "B649_CANDIDATE_SET_HYBRID_DIVERSITY_V1", 5, history, target_index
    )


def produce_b649_cross_family_redundancy_pruned_ensemble_v1_hybrid_diversity_k10(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    return _produce_matched_budget_union(
        "B649_CANDIDATE_SET_HYBRID_DIVERSITY_V1", 10, history, target_index
    )


def produce_b649_cross_family_redundancy_pruned_ensemble_v1_hybrid_diversity_k20(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    return _produce_matched_budget_union(
        "B649_CANDIDATE_SET_HYBRID_DIVERSITY_V1", 20, history, target_index
    )


__all__ = [
    "AGGREGATION",
    "CAUSAL_CUTOFF_RULE",
    "CONSTRUCTOR_IDS",
    "DETERMINISM_CLASS",
    "FALLBACK",
    "HYPOTHESIS_ID",
    "HYPOTHESIS_VERSION",
    "IMPLEMENTATION_SYMBOLS",
    "LOTTERY_TYPE",
    "MINIMUM_HISTORY",
    "NEW_FAMILY_ID",
    "NUMBER_DOMAIN",
    "PICK_COUNT",
    "PRUNED_FAMILY_ID",
    "RETAINED_FAMILY_IDS",
    "RNG_SEMANTICS",
    "TICKET_BUDGETS",
    "TICKET_CARDINALITY_RULE",
    "UNION_ORDER_RULE",
    "RequiredParentUnavailableError",
    "produce_b649_cross_family_redundancy_pruned_ensemble_v1_exposure_balanced_k5",
    "produce_b649_cross_family_redundancy_pruned_ensemble_v1_exposure_balanced_k10",
    "produce_b649_cross_family_redundancy_pruned_ensemble_v1_exposure_balanced_k20",
    "produce_b649_cross_family_redundancy_pruned_ensemble_v1_hybrid_diversity_k5",
    "produce_b649_cross_family_redundancy_pruned_ensemble_v1_hybrid_diversity_k10",
    "produce_b649_cross_family_redundancy_pruned_ensemble_v1_hybrid_diversity_k20",
    "produce_b649_cross_family_redundancy_pruned_ensemble_v1_low_overlap_k5",
    "produce_b649_cross_family_redundancy_pruned_ensemble_v1_low_overlap_k10",
    "produce_b649_cross_family_redundancy_pruned_ensemble_v1_low_overlap_k20",
    "union_retained_native_tickets_at_matched_budget",
]
