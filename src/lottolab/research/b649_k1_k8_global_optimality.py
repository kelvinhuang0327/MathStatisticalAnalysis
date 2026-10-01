"""Global optimality of pairwise-disjoint B649 portfolios for K=1..8.

Two events are proved separately. They share the exchange lemma and do not
share an outcome space:

- ``OFFICIAL_ANY_PRIZE`` counts outcomes ``(main draw, special)``. A ticket
  wins when it contains at least three members of that seven-number set.
- ``M3_PLUS`` counts 6-subsets. A ticket wins when at least three of its
  numbers lie in the main draw. The special is not part of this event.

The argument is about union coverage, the number of outcomes in which at
least one ticket wins. It is not a sum of per-ticket successes.

Exchange lemma. Suppose one ticket contains ``x`` and no ticket contains
``y``. Replace that copy of ``x`` with ``y``. Outcomes that contain both of
``x, y``, or neither, are unchanged. The remaining outcomes pair as
``E_x`` and ``E_y``. No other ticket contains ``y``, so any other ticket that
wins ``E_y`` also wins ``E_x``. The edited ticket's success swaps between the
two sides. The number of covered outcomes in the pair therefore does not
decrease.

For ``K <= 8`` a portfolio that still repeats a label uses at most ``6K - 1``
labels, hence at most 47 of the 49 numbers, so an unused ``y`` exists. Repeat
the exchange until the portfolio is pairwise disjoint. Coverage never falls,
so every portfolio is at most the disjoint value.

On a pairwise-disjoint portfolio three tickets cannot win together: the event
would need three disjoint 3-subsets of a 6-set (``M3_PLUS``) or of a 7-set
(``OFFICIAL_ANY_PRIZE``). Inclusion-exclusion therefore stops after pairs, and
the closed forms below are exact. Every pairwise-disjoint portfolio attains
the same value. The optimum is not claimed to be unique: an overlapping
portfolio may tie, and this module does not certify it either way.

``K >= 9`` is outside the unused-label step. This theorem returns
``GLOBAL_OPTIMUM_UNKNOWN_BY_THIS_THEOREM`` and does not extend the formula.
"""

from __future__ import annotations

import enum
from collections.abc import Sequence
from dataclasses import dataclass
from fractions import Fraction
from math import comb
from typing import Final

type Ticket = tuple[int, ...]

POOL_SIZE: Final = 49
TICKET_SIZE: Final = 6
DRAW_SIZE: Final = 6
THRESHOLD: Final = 3
MAX_CERTIFIED_TICKET_COUNT: Final = 8

OFFICIAL_ANY_PRIZE_SINGLE_OUTCOMES: Final = 18_611_432
OFFICIAL_ANY_PRIZE_DISJOINT_PAIR_OUTCOMES: Final = 107_800
OFFICIAL_ANY_PRIZE_DENOMINATOR: Final = 601_304_088
M3_PLUS_SINGLE_OUTCOMES: Final = 260_624
M3_PLUS_DISJOINT_PAIR_OUTCOMES: Final = 400
M3_PLUS_DENOMINATOR: Final = 13_983_816


class PrizeEvent(enum.StrEnum):
    """The two events proved by this theorem. They are not interchangeable."""

    OFFICIAL_ANY_PRIZE = "OFFICIAL_ANY_PRIZE"
    M3_PLUS = "M3_PLUS"


class TheoremStatus(enum.StrEnum):
    """Certificate issued by this theorem, not a search result."""

    GLOBAL_OPTIMUM_CERTIFIED = "GLOBAL_OPTIMUM_CERTIFIED"
    NOT_CERTIFIED = "NOT_CERTIFIED"
    GLOBAL_OPTIMUM_UNKNOWN_BY_THIS_THEOREM = "GLOBAL_OPTIMUM_UNKNOWN_BY_THIS_THEOREM"


class TheoremInputError(ValueError):
    """A ticket, portfolio, or K outside the theorem's legal inputs."""


@dataclass(frozen=True, slots=True)
class GlobalUpperBound:
    """Exact upper bound for one event, or an explicit unknown for ``K >= 9``."""

    event: PrizeEvent
    ticket_count: int
    status: TheoremStatus
    numerator: int | None = None
    denominator: int | None = None

    @property
    def probability(self) -> Fraction:
        """Reduced probability. Raises when this theorem supplies no bound."""

        if self.numerator is None or self.denominator is None:
            raise TheoremInputError(
                "this theorem does not supply a numeric bound for this ticket count"
            )
        return Fraction(self.numerator, self.denominator)


@dataclass(frozen=True, slots=True)
class ExchangePairedCoverage:
    """Union coverage of the outcomes that contain exactly one of the exchanged labels."""

    before: int
    after: int

    @property
    def does_not_decrease(self) -> bool:
        return self.after >= self.before


def outcome_space_size(event: PrizeEvent) -> int:
    """Independent size of the outcome space. Not the closed-form constant."""

    _require_event(event)
    main_draws = comb(POOL_SIZE, DRAW_SIZE)
    if event is PrizeEvent.M3_PLUS:
        return main_draws
    return main_draws * (POOL_SIZE - DRAW_SIZE)


def independent_single_outcome_count(event: PrizeEvent) -> int:
    """Winning outcomes of one ticket, counted from binomial coefficients."""

    _require_event(event)
    if event is PrizeEvent.M3_PLUS:
        return _m3_single_count()
    return _any_single_count()


def independent_disjoint_pair_outcome_count(event: PrizeEvent) -> int:
    """Outcomes in which two fixed disjoint tickets both win."""

    _require_event(event)
    if event is PrizeEvent.M3_PLUS:
        return _m3_disjoint_pair_count()
    return _any_disjoint_pair_count()


def independent_disjoint_triple_outcome_count(event: PrizeEvent) -> int:
    """Outcomes in which three fixed disjoint tickets all win.

    The region enumeration is the witness that this term is zero, so
    inclusion-exclusion of a pairwise-disjoint portfolio stops after pairs.
    """

    _require_event(event)
    if event is PrizeEvent.M3_PLUS:
        return _m3_disjoint_triple_count()
    return _any_disjoint_triple_count()


def global_upper_bound(event: PrizeEvent, ticket_count: int) -> GlobalUpperBound:
    """Certified maximum for ``K=1..8``. ``K >= 9`` stays unknown.

    The numerator is ``single * K - pair * C(K, 2)`` over that event's
    outcome space. ``GLOBAL_OPTIMUM_CERTIFIED`` here means the number is the
    maximum and that every legal pairwise-disjoint portfolio attains it.
    """

    _require_event(event)
    if type(ticket_count) is not int or ticket_count < 1:
        raise TheoremInputError("ticket_count must be a positive integer")
    if ticket_count > MAX_CERTIFIED_TICKET_COUNT:
        return GlobalUpperBound(
            event=event,
            ticket_count=ticket_count,
            status=TheoremStatus.GLOBAL_OPTIMUM_UNKNOWN_BY_THIS_THEOREM,
        )
    single, pair, denominator = _closed_form_parts(event)
    numerator = single * ticket_count - pair * comb(ticket_count, 2)
    return GlobalUpperBound(
        event=event,
        ticket_count=ticket_count,
        status=TheoremStatus.GLOBAL_OPTIMUM_CERTIFIED,
        numerator=numerator,
        denominator=denominator,
    )


def certify_portfolio(event: PrizeEvent, tickets: Sequence[Sequence[int]]) -> TheoremStatus:
    """Certify a legal pairwise-disjoint portfolio of size 1..8.

    An overlapping portfolio of that size returns ``NOT_CERTIFIED``. Overlap
    does not by itself receive a negative certificate: a tie with the disjoint
    value remains possible, and this function does not evaluate it.
    ``K >= 9`` returns ``GLOBAL_OPTIMUM_UNKNOWN_BY_THIS_THEOREM`` even when
    the tickets are legal.
    """

    _require_event(event)
    normalized = _validate_tickets(tickets, pool_size=POOL_SIZE, ticket_size=TICKET_SIZE)
    if len(normalized) > MAX_CERTIFIED_TICKET_COUNT:
        return TheoremStatus.GLOBAL_OPTIMUM_UNKNOWN_BY_THIS_THEOREM
    if _pairwise_disjoint(normalized):
        return TheoremStatus.GLOBAL_OPTIMUM_CERTIFIED
    return TheoremStatus.NOT_CERTIFIED


def exchange_paired_coverage(
    event: PrizeEvent,
    tickets: Sequence[Sequence[int]],
    *,
    ticket_index: int,
    remove: int,
    insert: int,
    pool_size: int = POOL_SIZE,
    ticket_size: int = TICKET_SIZE,
    draw_size: int = DRAW_SIZE,
    threshold: int = THRESHOLD,
) -> ExchangePairedCoverage:
    """Exact paired-outcome coverage before and after one legal exchange.

    ``insert`` must be unused by every ticket. Only outcomes that contain
    exactly one of ``remove`` and ``insert`` are counted; the other outcomes
    do not change. ``M3_PLUS`` counts main draws. ``OFFICIAL_ANY_PRIZE`` counts
    ``(main, special)`` outcomes whose seven-number set contains exactly one
    of the two labels. Reduced lotteries may override the dimensions; the
    K=1..8 certificate itself is only for the B649 parameters.
    """

    _require_event(event)
    _require_dimensions(
        pool_size=pool_size,
        ticket_size=ticket_size,
        draw_size=draw_size,
        threshold=threshold,
        event=event,
    )
    normalized = _validate_tickets(tickets, pool_size=pool_size, ticket_size=ticket_size)
    if type(ticket_index) is not int or not 0 <= ticket_index < len(normalized):
        raise TheoremInputError("ticket_index is outside the portfolio")
    if type(remove) is not int or type(insert) is not int:
        raise TheoremInputError("exchanged labels must be ints")
    if remove not in normalized[ticket_index]:
        raise TheoremInputError("remove must belong to the edited ticket")
    if not 1 <= insert <= pool_size or insert == remove:
        raise TheoremInputError("insert must be a different label in the pool")
    if any(insert in ticket for ticket in normalized):
        raise TheoremInputError("insert must be unused by the whole portfolio")

    before = tuple(frozenset(ticket) for ticket in normalized)
    after_tickets: list[frozenset[int]] = []
    for index, ticket in enumerate(before):
        if index == ticket_index:
            after_tickets.append((ticket - {remove}) | {insert})
        else:
            after_tickets.append(ticket)
    after = tuple(after_tickets)
    if event is PrizeEvent.M3_PLUS:
        rest_size = draw_size - 1
        multiplier = 1
    else:
        rest_size = draw_size
        multiplier = draw_size + 1
    ground_size = pool_size - 2
    if rest_size > ground_size:
        raise TheoremInputError("paired draw does not fit in the pool without the two labels")

    def family(portfolio: tuple[frozenset[int], ...]) -> int:
        covered = _covered_rest_count(
            portfolio,
            included=remove,
            excluded=insert,
            rest_size=rest_size,
            threshold=threshold,
            pool_size=pool_size,
        )
        covered += _covered_rest_count(
            portfolio,
            included=insert,
            excluded=remove,
            rest_size=rest_size,
            threshold=threshold,
            pool_size=pool_size,
        )
        return covered * multiplier

    return ExchangePairedCoverage(before=family(before), after=family(after))


def _require_event(event: PrizeEvent) -> None:
    if type(event) is not PrizeEvent:
        raise TheoremInputError("event must be a PrizeEvent")


def _require_dimensions(
    *,
    pool_size: int,
    ticket_size: int,
    draw_size: int,
    threshold: int,
    event: PrizeEvent,
) -> None:
    if (
        type(pool_size) is not int
        or type(ticket_size) is not int
        or type(draw_size) is not int
        or type(threshold) is not int
    ):
        raise TheoremInputError("lottery dimensions must be ints")
    if not 1 <= ticket_size <= pool_size:
        raise TheoremInputError("ticket_size must fit in the pool")
    if not 1 <= draw_size <= pool_size:
        raise TheoremInputError("draw_size must fit in the pool")
    limit = draw_size if event is PrizeEvent.M3_PLUS else draw_size + 1
    if not 1 <= threshold <= limit:
        raise TheoremInputError("threshold must be attainable in one outcome")


def _validate_tickets(
    tickets: Sequence[Sequence[int]],
    *,
    pool_size: int,
    ticket_size: int,
) -> tuple[Ticket, ...]:
    if isinstance(tickets, (str, bytes)):
        raise TheoremInputError("portfolio must be a sequence of tickets")
    if len(tickets) < 1:
        raise TheoremInputError("portfolio must contain at least one ticket")
    normalized: list[Ticket] = []
    for ticket in tickets:
        if isinstance(ticket, (str, bytes)):
            raise TheoremInputError(f"illegal ticket: {ticket!r}")
        if (
            len(ticket) != ticket_size
            or len(set(ticket)) != ticket_size
            or any(type(number) is not int or not 1 <= number <= pool_size for number in ticket)
        ):
            raise TheoremInputError(f"illegal ticket: {tuple(ticket)}")
        normalized.append(tuple(sorted(ticket)))
    return tuple(normalized)


def _pairwise_disjoint(tickets: tuple[Ticket, ...]) -> bool:
    seen: set[int] = set()
    for ticket in tickets:
        numbers = set(ticket)
        if seen & numbers:
            return False
        seen.update(numbers)
    return True


def _closed_form_parts(event: PrizeEvent) -> tuple[int, int, int]:
    if event is PrizeEvent.OFFICIAL_ANY_PRIZE:
        return (
            OFFICIAL_ANY_PRIZE_SINGLE_OUTCOMES,
            OFFICIAL_ANY_PRIZE_DISJOINT_PAIR_OUTCOMES,
            OFFICIAL_ANY_PRIZE_DENOMINATOR,
        )
    return (
        M3_PLUS_SINGLE_OUTCOMES,
        M3_PLUS_DISJOINT_PAIR_OUTCOMES,
        M3_PLUS_DENOMINATOR,
    )


def _m3_single_count() -> int:
    outside = POOL_SIZE - TICKET_SIZE
    return sum(
        comb(TICKET_SIZE, hits) * comb(outside, DRAW_SIZE - hits)
        for hits in range(THRESHOLD, TICKET_SIZE + 1)
    )


def _m3_disjoint_pair_count() -> int:
    outside_size = POOL_SIZE - 2 * TICKET_SIZE
    total = 0
    for hits_a in range(TICKET_SIZE + 1):
        for hits_b in range(TICKET_SIZE + 1):
            outside = DRAW_SIZE - hits_a - hits_b
            if outside < 0 or outside > outside_size:
                continue
            if hits_a >= THRESHOLD and hits_b >= THRESHOLD:
                total += (
                    comb(TICKET_SIZE, hits_a)
                    * comb(TICKET_SIZE, hits_b)
                    * comb(outside_size, outside)
                )
    return total


def _m3_disjoint_triple_count() -> int:
    outside_size = POOL_SIZE - 3 * TICKET_SIZE
    total = 0
    for hits_a in range(TICKET_SIZE + 1):
        for hits_b in range(TICKET_SIZE + 1):
            for hits_c in range(TICKET_SIZE + 1):
                outside = DRAW_SIZE - hits_a - hits_b - hits_c
                if outside < 0 or outside > outside_size:
                    continue
                if hits_a >= THRESHOLD and hits_b >= THRESHOLD and hits_c >= THRESHOLD:
                    total += (
                        comb(TICKET_SIZE, hits_a)
                        * comb(TICKET_SIZE, hits_b)
                        * comb(TICKET_SIZE, hits_c)
                        * comb(outside_size, outside)
                    )
    return total


def _any_single_count() -> int:
    """(main, special) outcomes in which one ticket meets the seven-set threshold."""

    outside = POOL_SIZE - TICKET_SIZE
    total = 0
    for hits in range(TICKET_SIZE + 1):
        if DRAW_SIZE - hits > outside:
            continue
        ways = comb(TICKET_SIZE, hits) * comb(outside, DRAW_SIZE - hits)
        if hits >= THRESHOLD:
            total += ways * outside
        elif hits == THRESHOLD - 1:
            total += ways * (TICKET_SIZE - hits)
    return total


def _any_disjoint_pair_count() -> int:
    outside_size = POOL_SIZE - 2 * TICKET_SIZE
    total = 0
    for hits_a in range(TICKET_SIZE + 1):
        for hits_b in range(TICKET_SIZE + 1):
            outside = DRAW_SIZE - hits_a - hits_b
            if outside < 0 or outside > outside_size:
                continue
            ways = (
                comb(TICKET_SIZE, hits_a) * comb(TICKET_SIZE, hits_b) * comb(outside_size, outside)
            )
            remaining = (
                TICKET_SIZE - hits_a,
                TICKET_SIZE - hits_b,
                outside_size - outside,
            )
            for region, count in enumerate(remaining):
                if count == 0:
                    continue
                total_a = hits_a + (1 if region == 0 else 0)
                total_b = hits_b + (1 if region == 1 else 0)
                if total_a >= THRESHOLD and total_b >= THRESHOLD:
                    total += ways * count
    return total


def _any_disjoint_triple_count() -> int:
    outside_size = POOL_SIZE - 3 * TICKET_SIZE
    total = 0
    for hits_a in range(TICKET_SIZE + 1):
        for hits_b in range(TICKET_SIZE + 1):
            for hits_c in range(TICKET_SIZE + 1):
                outside = DRAW_SIZE - hits_a - hits_b - hits_c
                if outside < 0 or outside > outside_size:
                    continue
                ways = (
                    comb(TICKET_SIZE, hits_a)
                    * comb(TICKET_SIZE, hits_b)
                    * comb(TICKET_SIZE, hits_c)
                    * comb(outside_size, outside)
                )
                hits = (hits_a, hits_b, hits_c)
                remaining = (
                    TICKET_SIZE - hits_a,
                    TICKET_SIZE - hits_b,
                    TICKET_SIZE - hits_c,
                    outside_size - outside,
                )
                for region, count in enumerate(remaining):
                    if count == 0:
                        continue
                    totals = [hits[index] + (1 if region == index else 0) for index in range(3)]
                    if all(total_hits >= THRESHOLD for total_hits in totals):
                        total += ways * count
    return total


def _covered_rest_count(
    tickets: tuple[frozenset[int], ...],
    *,
    included: int,
    excluded: int,
    rest_size: int,
    threshold: int,
    pool_size: int,
) -> int:
    """Rest-subsets whose draw, rest plus ``included``, is covered by at least one ticket."""

    bonuses = tuple(1 if included in ticket else 0 for ticket in tickets)
    bucket_counts: dict[tuple[int, ...], int] = {}
    width = len(tickets)
    for number in range(1, pool_size + 1):
        if number in (included, excluded):
            continue
        signature = tuple(1 if number in ticket else 0 for ticket in tickets)
        bucket_counts[signature] = bucket_counts.get(signature, 0) + 1
    buckets = tuple(bucket_counts.items())
    covered = 0

    def walk(index: int, remaining: int, ways: int, hits: tuple[int, ...]) -> None:
        nonlocal covered
        if remaining == 0:
            won = any(
                hits[ticket_index] + bonuses[ticket_index] >= threshold
                for ticket_index in range(width)
            )
            if won:
                covered += ways
            return
        if index == len(buckets):
            return
        signature, available = buckets[index]
        for take in range(min(available, remaining) + 1):
            next_hits = hits
            if take:
                next_hits = tuple(
                    hits[ticket_index] + take * signature[ticket_index]
                    for ticket_index in range(width)
                )
            walk(index + 1, remaining - take, ways * comb(available, take), next_hits)

    walk(0, rest_size, 1, tuple(0 for _ in tickets))
    return covered


__all__ = [
    "DRAW_SIZE",
    "M3_PLUS_DENOMINATOR",
    "M3_PLUS_DISJOINT_PAIR_OUTCOMES",
    "M3_PLUS_SINGLE_OUTCOMES",
    "MAX_CERTIFIED_TICKET_COUNT",
    "OFFICIAL_ANY_PRIZE_DENOMINATOR",
    "OFFICIAL_ANY_PRIZE_DISJOINT_PAIR_OUTCOMES",
    "OFFICIAL_ANY_PRIZE_SINGLE_OUTCOMES",
    "POOL_SIZE",
    "THRESHOLD",
    "TICKET_SIZE",
    "ExchangePairedCoverage",
    "GlobalUpperBound",
    "PrizeEvent",
    "TheoremInputError",
    "TheoremStatus",
    "certify_portfolio",
    "exchange_paired_coverage",
    "global_upper_bound",
    "independent_disjoint_pair_outcome_count",
    "independent_disjoint_triple_outcome_count",
    "independent_single_outcome_count",
    "outcome_space_size",
]
