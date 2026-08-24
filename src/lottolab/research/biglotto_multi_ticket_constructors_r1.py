"""Deterministic candidate-set-bounded BigLotto portfolio constructors.

The three constructors in this module select from an already-generated,
caller-supplied ordered candidate pool.  They never generate legal tickets,
enumerate winning draws, read outcome data, or use a fitted or empirical
score.  The source order of the candidate pool is the final authority for
every lexicographic tie.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from itertools import pairwise
from types import MappingProxyType
from typing import Final, cast

type Ticket = tuple[int, int, int, int, int, int]
type TicketPortfolio = tuple[Ticket, ...]
type Constructor = Callable[[Iterable[object], int], TicketPortfolio]

VERSION: Final[str] = "v1"
SUPPORTED_TICKET_COUNTS: Final[tuple[int, int, int]] = (5, 10, 20)
LOTTERY_TYPE: Final[str] = "BIG_LOTTO"
PICK_COUNT: Final[int] = 6
NUMBER_DOMAIN: Final[tuple[int, int]] = (1, 49)
DETERMINISM_CLASS: Final[str] = "PURE_DETERMINISTIC_NO_RNG"
OUTPUT_ORDER: Final[str] = "GREEDY_SELECTION_ORDER"


@dataclass(frozen=True, slots=True)
class ConstructorMetadata:
    """Immutable authority metadata for one constructor family."""

    CONSTRUCTOR_ID: str
    VERSION: str
    SUPPORTED_TICKET_COUNTS: tuple[int, int, int]
    LOTTERY_TYPE: str
    PICK_COUNT: int
    NUMBER_DOMAIN: tuple[int, int]
    DETERMINISM_CLASS: str
    SELECTION_OBJECTIVE: str
    OUTPUT_ORDER: str


B649_CANDIDATE_SET_LOW_OVERLAP_V1_METADATA: Final[ConstructorMetadata] = (
    ConstructorMetadata(
        CONSTRUCTOR_ID="B649_CANDIDATE_SET_LOW_OVERLAP_V1",
        VERSION=VERSION,
        SUPPORTED_TICKET_COUNTS=SUPPORTED_TICKET_COUNTS,
        LOTTERY_TYPE=LOTTERY_TYPE,
        PICK_COUNT=PICK_COUNT,
        NUMBER_DOMAIN=NUMBER_DOMAIN,
        DETERMINISM_CLASS=DETERMINISM_CLASS,
        SELECTION_OBJECTIVE=(
            "lexicographic_minimum(MAX_OVERLAP, TOTAL_OVERLAP, ORIGINAL_RANK)"
        ),
        OUTPUT_ORDER=OUTPUT_ORDER,
    )
)
B649_CANDIDATE_SET_EXPOSURE_BALANCED_V1_METADATA: Final[ConstructorMetadata] = (
    ConstructorMetadata(
        CONSTRUCTOR_ID="B649_CANDIDATE_SET_EXPOSURE_BALANCED_V1",
        VERSION=VERSION,
        SUPPORTED_TICKET_COUNTS=SUPPORTED_TICKET_COUNTS,
        LOTTERY_TYPE=LOTTERY_TYPE,
        PICK_COUNT=PICK_COUNT,
        NUMBER_DOMAIN=NUMBER_DOMAIN,
        DETERMINISM_CLASS=DETERMINISM_CLASS,
        SELECTION_OBJECTIVE=(
            "lexicographic_minimum(EXPOSURE_VECTOR_AFTER_ADDING_CANDIDATE, ORIGINAL_RANK)"
        ),
        OUTPUT_ORDER=OUTPUT_ORDER,
    )
)
B649_CANDIDATE_SET_HYBRID_DIVERSITY_V1_METADATA: Final[ConstructorMetadata] = (
    ConstructorMetadata(
        CONSTRUCTOR_ID="B649_CANDIDATE_SET_HYBRID_DIVERSITY_V1",
        VERSION=VERSION,
        SUPPORTED_TICKET_COUNTS=SUPPORTED_TICKET_COUNTS,
        LOTTERY_TYPE=LOTTERY_TYPE,
        PICK_COUNT=PICK_COUNT,
        NUMBER_DOMAIN=NUMBER_DOMAIN,
        DETERMINISM_CLASS=DETERMINISM_CLASS,
        SELECTION_OBJECTIVE=(
            "lexicographic_minimum(MAX_OVERLAP, EXPOSURE_VECTOR_AFTER_ADDING_CANDIDATE, "
            "TOTAL_OVERLAP, ORIGINAL_RANK)"
        ),
        OUTPUT_ORDER=OUTPUT_ORDER,
    )
)

# Short metadata aliases keep the three families easy to discover without
# creating a second metadata representation.
LOW_OVERLAP_METADATA: Final[ConstructorMetadata] = (
    B649_CANDIDATE_SET_LOW_OVERLAP_V1_METADATA
)
EXPOSURE_BALANCED_METADATA: Final[ConstructorMetadata] = (
    B649_CANDIDATE_SET_EXPOSURE_BALANCED_V1_METADATA
)
HYBRID_DIVERSITY_METADATA: Final[ConstructorMetadata] = (
    B649_CANDIDATE_SET_HYBRID_DIVERSITY_V1_METADATA
)

CONSTRUCTOR_METADATA: Final[Mapping[str, ConstructorMetadata]] = MappingProxyType(
    {
        metadata.CONSTRUCTOR_ID: metadata
        for metadata in (
            B649_CANDIDATE_SET_LOW_OVERLAP_V1_METADATA,
            B649_CANDIDATE_SET_EXPOSURE_BALANCED_V1_METADATA,
            B649_CANDIDATE_SET_HYBRID_DIVERSITY_V1_METADATA,
        )
    }
)


def _validate_ticket_count(ticket_count: int) -> None:
    if type(ticket_count) is not int or ticket_count not in SUPPORTED_TICKET_COUNTS:
        raise ValueError(
            "ticket_count must be one of the supported native budgets "
            f"{SUPPORTED_TICKET_COUNTS}"
        )


def _validate_ticket(raw_ticket: object, original_rank: int) -> Ticket:
    if not isinstance(raw_ticket, tuple):
        raise ValueError(
            f"candidate_tickets[{original_rank}] must be an immutable tuple of six integers"
        )
    ticket_values = cast(tuple[object, ...], raw_ticket)
    if len(ticket_values) != PICK_COUNT:
        raise ValueError(
            f"candidate_tickets[{original_rank}] must contain exactly {PICK_COUNT} numbers"
        )

    numbers: list[int] = []
    for position, raw_number in enumerate(ticket_values):
        if type(raw_number) is not int:
            raise ValueError(
                f"candidate_tickets[{original_rank}][{position}] must be an integer"
            )
        numbers.append(raw_number)

    ticket = cast(Ticket, tuple(numbers))
    lower, upper = NUMBER_DOMAIN
    if any(number < lower or number > upper for number in ticket):
        raise ValueError(
            f"candidate_tickets[{original_rank}] contains a number outside {lower}..{upper}"
        )
    if any(left >= right for left, right in pairwise(ticket)):
        raise ValueError(
            f"candidate_tickets[{original_rank}] must be strictly ascending with no duplicates"
        )
    return ticket


def _validate_candidate_pool(
    candidate_tickets: Iterable[object], ticket_count: int
) -> tuple[tuple[Ticket, ...], tuple[frozenset[int], ...]]:
    _validate_ticket_count(ticket_count)
    try:
        raw_candidates = tuple(candidate_tickets)
    except TypeError as error:
        raise ValueError("candidate_tickets must be an ordered finite sequence") from error

    candidates: list[Ticket] = []
    seen: set[Ticket] = set()
    for original_rank, raw_ticket in enumerate(raw_candidates):
        ticket = _validate_ticket(raw_ticket, original_rank)
        if ticket in seen:
            raise ValueError(f"candidate_tickets contains duplicate ticket {ticket!r}")
        seen.add(ticket)
        candidates.append(ticket)

    if len(candidates) < ticket_count:
        raise ValueError(
            f"candidate_tickets must contain at least {ticket_count} legal tickets; "
            f"received {len(candidates)}"
        )

    candidate_tuple = tuple(candidates)
    return candidate_tuple, tuple(frozenset(ticket) for ticket in candidate_tuple)


def _overlap_key(
    candidate_numbers: frozenset[int], selected_numbers: list[frozenset[int]], original_rank: int
) -> tuple[int, int, int]:
    overlaps = [len(candidate_numbers & selected) for selected in selected_numbers]
    return (max(overlaps, default=0), sum(overlaps), original_rank)


def _exposure_vector_after_addition(
    exposure_counts: list[int], candidate: Ticket
) -> tuple[int, ...]:
    provisional_counts = exposure_counts.copy()
    for number in candidate:
        provisional_counts[number - 1] += 1
    return tuple(sorted(provisional_counts, reverse=True))


def _add_to_exposure_counts(exposure_counts: list[int], ticket: Ticket) -> None:
    for number in ticket:
        exposure_counts[number - 1] += 1


def _select_low_overlap(
    candidates: tuple[Ticket, ...],
    candidate_numbers: tuple[frozenset[int], ...],
    ticket_count: int,
) -> TicketPortfolio:
    selected: list[Ticket] = []
    selected_numbers: list[frozenset[int]] = []
    selected_indices: set[int] = set()

    for _ in range(ticket_count):
        best_index: int | None = None
        best_key: tuple[int, int, int] | None = None
        for original_rank, numbers in enumerate(candidate_numbers):
            if original_rank in selected_indices:
                continue
            key = _overlap_key(numbers, selected_numbers, original_rank)
            if best_key is None or key < best_key:
                best_key = key
                best_index = original_rank

        if best_index is None:
            raise RuntimeError("validated candidate pool could not satisfy ticket_count")
        selected_indices.add(best_index)
        selected.append(candidates[best_index])
        selected_numbers.append(candidate_numbers[best_index])

    return tuple(selected)


def _select_exposure_balanced(
    candidates: tuple[Ticket, ...], ticket_count: int
) -> TicketPortfolio:
    selected: list[Ticket] = []
    selected_indices: set[int] = set()
    exposure_counts = [0] * (NUMBER_DOMAIN[1] - NUMBER_DOMAIN[0] + 1)

    for _ in range(ticket_count):
        best_index: int | None = None
        best_key: tuple[tuple[int, ...], int] | None = None
        for original_rank, candidate in enumerate(candidates):
            if original_rank in selected_indices:
                continue
            vector = _exposure_vector_after_addition(exposure_counts, candidate)
            key = (vector, original_rank)
            if best_key is None or key < best_key:
                best_key = key
                best_index = original_rank

        if best_index is None:
            raise RuntimeError("validated candidate pool could not satisfy ticket_count")
        selected_indices.add(best_index)
        chosen = candidates[best_index]
        selected.append(chosen)
        _add_to_exposure_counts(exposure_counts, chosen)

    return tuple(selected)


def _select_hybrid_diversity(
    candidates: tuple[Ticket, ...],
    candidate_numbers: tuple[frozenset[int], ...],
    ticket_count: int,
) -> TicketPortfolio:
    selected: list[Ticket] = []
    selected_numbers: list[frozenset[int]] = []
    selected_indices: set[int] = set()
    exposure_counts = [0] * (NUMBER_DOMAIN[1] - NUMBER_DOMAIN[0] + 1)

    for _ in range(ticket_count):
        best_index: int | None = None
        best_key: tuple[int, tuple[int, ...], int, int] | None = None
        for original_rank, numbers in enumerate(candidate_numbers):
            if original_rank in selected_indices:
                continue
            candidate = candidates[original_rank]
            maximum, total, _ = _overlap_key(numbers, selected_numbers, original_rank)
            vector = _exposure_vector_after_addition(exposure_counts, candidate)
            key = (maximum, vector, total, original_rank)
            if best_key is None or key < best_key:
                best_key = key
                best_index = original_rank

        if best_index is None:
            raise RuntimeError("validated candidate pool could not satisfy ticket_count")
        selected_indices.add(best_index)
        chosen = candidates[best_index]
        selected.append(chosen)
        selected_numbers.append(candidate_numbers[best_index])
        _add_to_exposure_counts(exposure_counts, chosen)

    return tuple(selected)


def construct_b649_candidate_set_low_overlap_v1(
    candidate_tickets: Iterable[object], ticket_count: int
) -> TicketPortfolio:
    """Select a low-overlap portfolio from the caller's ordered candidate set."""

    candidates, candidate_numbers = _validate_candidate_pool(candidate_tickets, ticket_count)
    return _select_low_overlap(candidates, candidate_numbers, ticket_count)


def construct_b649_candidate_set_exposure_balanced_v1(
    candidate_tickets: Iterable[object], ticket_count: int
) -> TicketPortfolio:
    """Select an exposure-balanced portfolio from the caller's ordered candidate set."""

    candidates, _ = _validate_candidate_pool(candidate_tickets, ticket_count)
    return _select_exposure_balanced(candidates, ticket_count)


def construct_b649_candidate_set_hybrid_diversity_v1(
    candidate_tickets: Iterable[object], ticket_count: int
) -> TicketPortfolio:
    """Select a hybrid diversity portfolio from the caller's ordered candidate set."""

    candidates, candidate_numbers = _validate_candidate_pool(candidate_tickets, ticket_count)
    return _select_hybrid_diversity(candidates, candidate_numbers, ticket_count)


# The shorter names are aliases of the same three frozen constructor families;
# they do not create alternate selection behavior.
construct_low_overlap_portfolio = construct_b649_candidate_set_low_overlap_v1
construct_exposure_balanced_portfolio = construct_b649_candidate_set_exposure_balanced_v1
construct_hybrid_diversity_portfolio = construct_b649_candidate_set_hybrid_diversity_v1


CONSTRUCTORS: Final[Mapping[str, Constructor]] = MappingProxyType(
    {
        "B649_CANDIDATE_SET_LOW_OVERLAP_V1": construct_b649_candidate_set_low_overlap_v1,
        "B649_CANDIDATE_SET_EXPOSURE_BALANCED_V1": (
            construct_b649_candidate_set_exposure_balanced_v1
        ),
        "B649_CANDIDATE_SET_HYBRID_DIVERSITY_V1": (
            construct_b649_candidate_set_hybrid_diversity_v1
        ),
    }
)


__all__ = [
    "B649_CANDIDATE_SET_EXPOSURE_BALANCED_V1_METADATA",
    "B649_CANDIDATE_SET_HYBRID_DIVERSITY_V1_METADATA",
    "B649_CANDIDATE_SET_LOW_OVERLAP_V1_METADATA",
    "CONSTRUCTORS",
    "CONSTRUCTOR_METADATA",
    "DETERMINISM_CLASS",
    "EXPOSURE_BALANCED_METADATA",
    "HYBRID_DIVERSITY_METADATA",
    "LOTTERY_TYPE",
    "LOW_OVERLAP_METADATA",
    "NUMBER_DOMAIN",
    "OUTPUT_ORDER",
    "PICK_COUNT",
    "SUPPORTED_TICKET_COUNTS",
    "VERSION",
    "ConstructorMetadata",
    "Ticket",
    "TicketPortfolio",
    "construct_b649_candidate_set_exposure_balanced_v1",
    "construct_b649_candidate_set_hybrid_diversity_v1",
    "construct_b649_candidate_set_low_overlap_v1",
    "construct_exposure_balanced_portfolio",
    "construct_hybrid_diversity_portfolio",
    "construct_low_overlap_portfolio",
]
