"""K=1..8 disjoint-portfolio theorems for OFFICIAL_ANY_PRIZE and M3_PLUS.

The reduced lotteries enumerate exchanges directly. The B649 examples count
only the paired outcomes of one exchange, not the full 6/49 outcome space.
"""

from __future__ import annotations

from collections.abc import Sequence
from fractions import Fraction
from itertools import combinations
from math import comb

import pytest

from lottolab.application.b649_sealed_geometry_portfolio import (
    SEALED_GEOMETRY_METHOD_VERSION,
    SEALED_GEOMETRY_PORTFOLIOS,
)
from lottolab.research.b649_k1_k8_global_optimality import (
    M3_PLUS_DENOMINATOR,
    M3_PLUS_DISJOINT_PAIR_OUTCOMES,
    M3_PLUS_SINGLE_OUTCOMES,
    MAX_CERTIFIED_TICKET_COUNT,
    OFFICIAL_ANY_PRIZE_DENOMINATOR,
    OFFICIAL_ANY_PRIZE_DISJOINT_PAIR_OUTCOMES,
    OFFICIAL_ANY_PRIZE_SINGLE_OUTCOMES,
    POOL_SIZE,
    TICKET_SIZE,
    PrizeEvent,
    TheoremInputError,
    TheoremStatus,
    certify_portfolio,
    exchange_paired_coverage,
    global_upper_bound,
    independent_disjoint_pair_outcome_count,
    independent_disjoint_triple_outcome_count,
    independent_single_outcome_count,
    outcome_space_size,
)
from lottolab.research.b649_official_any_prize_exact import evaluate_single_ticket_closed_form

type Ticket = tuple[int, ...]

K5_ANY = Fraction(547495, 3579191)
K5_M3_PLUS = Fraction(54130, 582659)
EVENTS = (PrizeEvent.OFFICIAL_ANY_PRIZE, PrizeEvent.M3_PLUS)


def test_closed_form_matches_independent_binomial_counts() -> None:
    assert outcome_space_size(PrizeEvent.OFFICIAL_ANY_PRIZE) == comb(49, 6) * 43
    assert outcome_space_size(PrizeEvent.M3_PLUS) == comb(49, 6)
    assert outcome_space_size(PrizeEvent.OFFICIAL_ANY_PRIZE) == OFFICIAL_ANY_PRIZE_DENOMINATOR
    assert outcome_space_size(PrizeEvent.M3_PLUS) == M3_PLUS_DENOMINATOR
    assert (
        independent_single_outcome_count(PrizeEvent.OFFICIAL_ANY_PRIZE)
        == OFFICIAL_ANY_PRIZE_SINGLE_OUTCOMES
        == 18_611_432
    )
    assert (
        independent_disjoint_pair_outcome_count(PrizeEvent.OFFICIAL_ANY_PRIZE)
        == OFFICIAL_ANY_PRIZE_DISJOINT_PAIR_OUTCOMES
        == 107_800
    )
    assert (
        independent_single_outcome_count(PrizeEvent.M3_PLUS) == M3_PLUS_SINGLE_OUTCOMES == 260_624
    )
    assert (
        independent_disjoint_pair_outcome_count(PrizeEvent.M3_PLUS)
        == M3_PLUS_DISJOINT_PAIR_OUTCOMES
        == 400
    )
    assert independent_disjoint_triple_outcome_count(PrizeEvent.OFFICIAL_ANY_PRIZE) == 0
    assert independent_disjoint_triple_outcome_count(PrizeEvent.M3_PLUS) == 0
    single_any = Fraction(OFFICIAL_ANY_PRIZE_SINGLE_OUTCOMES, OFFICIAL_ANY_PRIZE_DENOMINATOR)
    assert single_any == evaluate_single_ticket_closed_form()


@pytest.mark.parametrize("event", EVENTS)
@pytest.mark.parametrize("ticket_count", range(1, 9))
def test_k1_through_k8_upper_bound_is_the_pair_inclusion_exclusion(
    event: PrizeEvent, ticket_count: int
) -> None:
    single = independent_single_outcome_count(event)
    pair = independent_disjoint_pair_outcome_count(event)
    bound = global_upper_bound(event, ticket_count)

    assert bound.status is TheoremStatus.GLOBAL_OPTIMUM_CERTIFIED
    assert bound.numerator == single * ticket_count - pair * comb(ticket_count, 2)
    assert bound.denominator == outcome_space_size(event)
    assert bound.numerator is not None and bound.denominator is not None
    assert bound.probability == Fraction(bound.numerator, bound.denominator)


def test_k5_bounds_match_the_sealed_portfolio_exactly() -> None:
    sealed = SEALED_GEOMETRY_PORTFOLIOS[5]
    any_bound = global_upper_bound(PrizeEvent.OFFICIAL_ANY_PRIZE, 5)
    m3_bound = global_upper_bound(PrizeEvent.M3_PLUS, 5)

    assert any_bound.probability == K5_ANY == sealed.official_any_prize_probability
    assert m3_bound.probability == K5_M3_PLUS == sealed.m3_plus_probability
    assert any_bound.numerator == 5 * 18_611_432 - 10 * 107_800
    assert m3_bound.numerator == 5 * 260_624 - 10 * 400
    assert certify_portfolio(PrizeEvent.OFFICIAL_ANY_PRIZE, sealed.tickets) is (
        TheoremStatus.GLOBAL_OPTIMUM_CERTIFIED
    )
    assert certify_portfolio(PrizeEvent.M3_PLUS, sealed.tickets) is (
        TheoremStatus.GLOBAL_OPTIMUM_CERTIFIED
    )
    assert sealed.tickets == (
        (1, 2, 3, 4, 5, 6),
        (7, 8, 9, 10, 11, 12),
        (13, 14, 15, 16, 17, 18),
        (19, 20, 21, 22, 23, 24),
        (25, 26, 27, 28, 29, 30),
    )
    assert sealed.portfolio_sha256 == (
        "ec858fe04075ee40931366c05617ad7d04d934c5f72ac35c9b74c26ba91f8d87"
    )
    assert SEALED_GEOMETRY_METHOD_VERSION == "8.0.0"


def test_overlap_below_k9_still_leaves_an_unused_label() -> None:
    assert TICKET_SIZE * MAX_CERTIFIED_TICKET_COUNT <= POOL_SIZE - 1
    for ticket_count in range(1, MAX_CERTIFIED_TICKET_COUNT + 1):
        assert TICKET_SIZE * ticket_count - 1 <= POOL_SIZE - 1


@pytest.mark.parametrize(
    ("pool_size", "ticket_size", "draw_size", "threshold", "event", "portfolio_size"),
    [
        (8, 2, 3, 2, PrizeEvent.M3_PLUS, 2),
        (8, 2, 3, 2, PrizeEvent.M3_PLUS, 3),
        (7, 2, 2, 2, PrizeEvent.OFFICIAL_ANY_PRIZE, 2),
        (7, 2, 2, 2, PrizeEvent.OFFICIAL_ANY_PRIZE, 3),
    ],
)
def test_reduced_model_exchange_is_exhaustive_and_matches_direct_counts(
    pool_size: int,
    ticket_size: int,
    draw_size: int,
    threshold: int,
    event: PrizeEvent,
    portfolio_size: int,
) -> None:
    span = draw_size if event is PrizeEvent.M3_PLUS else draw_size + 1
    assert threshold * 3 > span
    universe = list(combinations(range(1, pool_size + 1), ticket_size))
    best = 0
    disjoint_value = None
    checked_exchanges = 0
    for chosen in combinations(universe, portfolio_size):
        tickets = tuple(ticket for ticket in chosen)
        coverage = _full_coverage(event, tickets, pool_size, draw_size, threshold)
        best = max(best, coverage)
        if _labels_disjoint(tickets):
            disjoint_value = coverage if disjoint_value is None else disjoint_value
            assert coverage == disjoint_value
        used = {number for ticket in tickets for number in ticket}
        unused = [number for number in range(1, pool_size + 1) if number not in used]
        for ticket_index, ticket in enumerate(tickets):
            for remove in ticket:
                for insert in unused:
                    direct = _direct_paired_coverage(
                        event,
                        tickets,
                        ticket_index,
                        remove,
                        insert,
                        pool_size,
                        draw_size,
                        threshold,
                    )
                    counted = exchange_paired_coverage(
                        event,
                        tickets,
                        ticket_index=ticket_index,
                        remove=remove,
                        insert=insert,
                        pool_size=pool_size,
                        ticket_size=ticket_size,
                        draw_size=draw_size,
                        threshold=threshold,
                    )
                    assert (counted.before, counted.after) == direct
                    assert counted.does_not_decrease
                    checked_exchanges += 1
    assert disjoint_value is not None
    assert disjoint_value == best
    assert checked_exchanges > 0


@pytest.mark.parametrize("event", EVENTS)
@pytest.mark.parametrize("ticket_count", (5, 6, 7, 8))
def test_one_b649_exchange_does_not_decrease_paired_coverage(
    event: PrizeEvent, ticket_count: int
) -> None:
    tickets, ticket_index, remove, insert = _one_shared_label_portfolio(ticket_count)
    result = exchange_paired_coverage(
        event,
        tickets,
        ticket_index=ticket_index,
        remove=remove,
        insert=insert,
    )

    assert result.does_not_decrease
    assert result.before > 0
    assert certify_portfolio(event, tickets) is TheoremStatus.NOT_CERTIFIED


@pytest.mark.parametrize("event", EVENTS)
def test_relabeling_a_disjoint_k5_preserves_paired_coverage(event: PrizeEvent) -> None:
    sealed = SEALED_GEOMETRY_PORTFOLIOS[5].tickets
    result = exchange_paired_coverage(
        event,
        sealed,
        ticket_index=4,
        remove=30,
        insert=49,
    )

    assert result.before == result.after
    assert result.does_not_decrease


@pytest.mark.parametrize("event", EVENTS)
def test_chained_k5_exchange_does_not_decrease_paired_coverage(event: PrizeEvent) -> None:
    tickets = (
        (1, 2, 3, 4, 5, 6),
        (1, 7, 8, 9, 10, 11),
        (7, 12, 13, 14, 15, 16),
        (17, 18, 19, 20, 21, 22),
        (23, 24, 25, 26, 27, 28),
    )
    result = exchange_paired_coverage(
        event,
        tickets,
        ticket_index=0,
        remove=1,
        insert=49,
    )

    assert result.does_not_decrease
    assert certify_portfolio(event, tickets) is TheoremStatus.NOT_CERTIFIED


@pytest.mark.parametrize("event", EVENTS)
def test_illegal_tickets_and_k0_are_rejected(event: PrizeEvent) -> None:
    legal = ((1, 2, 3, 4, 5, 6),)
    with pytest.raises(TheoremInputError):
        certify_portfolio(event, ())
    with pytest.raises(TheoremInputError):
        global_upper_bound(event, 0)
    with pytest.raises(TheoremInputError):
        certify_portfolio(event, [(1, 2, 3, 4, 5, 5)])
    with pytest.raises(TheoremInputError):
        certify_portfolio(event, [(0, 1, 2, 3, 4, 5)])
    with pytest.raises(TheoremInputError):
        certify_portfolio(event, [(1, 2, 3, 4, 5, 50)])
    with pytest.raises(TheoremInputError):
        certify_portfolio(event, [(1, 2, 3, 4, 5)])
    with pytest.raises(TheoremInputError):
        certify_portfolio(event, [(1, 2, 3, 4, 5, True)])
    with pytest.raises(TheoremInputError):
        exchange_paired_coverage(
            event,
            legal,
            ticket_index=0,
            remove=1,
            insert=1,
        )
    with pytest.raises(TheoremInputError):
        exchange_paired_coverage(
            event,
            legal,
            ticket_index=0,
            remove=1,
            insert=2,
        )


@pytest.mark.parametrize("event", EVENTS)
def test_k9_and_overlapping_k5_are_not_certified_as_optima(event: PrizeEvent) -> None:
    overlapping = (
        (1, 2, 3, 4, 5, 6),
        (1, 7, 8, 9, 10, 11),
        (12, 13, 14, 15, 16, 17),
        (18, 19, 20, 21, 22, 23),
        (24, 25, 26, 27, 28, 29),
    )
    nine = tuple(tuple(range(6 * index + 1, 6 * index + 7)) for index in range(8))
    nine = (*nine, (1, 2, 3, 4, 5, 49))
    unknown = global_upper_bound(event, 9)

    assert certify_portfolio(event, overlapping) is TheoremStatus.NOT_CERTIFIED
    assert certify_portfolio(event, nine) is TheoremStatus.GLOBAL_OPTIMUM_UNKNOWN_BY_THIS_THEOREM
    assert unknown.status is TheoremStatus.GLOBAL_OPTIMUM_UNKNOWN_BY_THIS_THEOREM
    assert unknown.numerator is None
    assert unknown.denominator is None
    with pytest.raises(TheoremInputError):
        _ = unknown.probability
    disjoint_eight = tuple(tuple(range(6 * index + 1, 6 * index + 7)) for index in range(8))
    assert certify_portfolio(event, disjoint_eight) is TheoremStatus.GLOBAL_OPTIMUM_CERTIFIED
    assert global_upper_bound(event, 8).status is TheoremStatus.GLOBAL_OPTIMUM_CERTIFIED


def test_sealed_k5_wording_records_a_proven_optimum_without_new_numbers() -> None:
    import lottolab.application.b649_sealed_geometry_portfolio as sealed

    document = sealed.__doc__ or ""
    assert "proven" in document
    assert "not unique" in document
    assert "best-known" not in document
    assert "neither K10 nor K20 is a proven global optimum" in document
    assert SEALED_GEOMETRY_PORTFOLIOS[10].official_any_prize_probability == Fraction(
        536005, 1827672
    )
    assert SEALED_GEOMETRY_PORTFOLIOS[20].official_any_prize_probability == Fraction(
        44748523, 85900584
    )


def _one_shared_label_portfolio(ticket_count: int) -> tuple[tuple[Ticket, ...], int, int, int]:
    tickets = [tuple(range(6 * index + 1, 6 * index + 7)) for index in range(ticket_count - 1)]
    used = {number for ticket in tickets for number in ticket}
    fresh = [number for number in range(1, POOL_SIZE + 1) if number not in used]
    tickets.append((1, *fresh[:5]))
    return tuple(tickets), ticket_count - 1, 1, fresh[5]


def _labels_disjoint(tickets: Sequence[Ticket]) -> bool:
    seen: set[int] = set()
    for ticket in tickets:
        numbers = set(ticket)
        if seen & numbers:
            return False
        seen.update(numbers)
    return True


def _full_coverage(
    event: PrizeEvent,
    tickets: Sequence[Ticket],
    pool_size: int,
    draw_size: int,
    threshold: int,
) -> int:
    sets = [set(ticket) for ticket in tickets]
    if event is PrizeEvent.M3_PLUS:
        return sum(
            1
            for draw in combinations(range(1, pool_size + 1), draw_size)
            if _hits_threshold(sets, set(draw), threshold)
        )
    total = 0
    for main in combinations(range(1, pool_size + 1), draw_size):
        main_set = set(main)
        for special in range(1, pool_size + 1):
            if special in main_set:
                continue
            if _hits_threshold(sets, main_set | {special}, threshold):
                total += 1
    return total


def _direct_paired_coverage(
    event: PrizeEvent,
    tickets: Sequence[Ticket],
    ticket_index: int,
    remove: int,
    insert: int,
    pool_size: int,
    draw_size: int,
    threshold: int,
) -> tuple[int, int]:
    before = [set(ticket) for ticket in tickets]
    after = [set(ticket) for ticket in tickets]
    after[ticket_index] = (after[ticket_index] - {remove}) | {insert}
    ground = [number for number in range(1, pool_size + 1) if number not in {remove, insert}]
    if event is PrizeEvent.M3_PLUS:
        return (
            _cover_m3_family(before, ground, remove, insert, draw_size, threshold),
            _cover_m3_family(after, ground, remove, insert, draw_size, threshold),
        )
    return (
        _cover_any_family(before, ground, remove, insert, draw_size, threshold),
        _cover_any_family(after, ground, remove, insert, draw_size, threshold),
    )


def _cover_m3_family(
    tickets: Sequence[set[int]],
    ground: Sequence[int],
    remove: int,
    insert: int,
    draw_size: int,
    threshold: int,
) -> int:
    covered = 0
    for rest in combinations(ground, draw_size - 1):
        for included in (remove, insert):
            if _hits_threshold(tickets, set(rest) | {included}, threshold):
                covered += 1
    return covered


def _cover_any_family(
    tickets: Sequence[set[int]],
    ground: Sequence[int],
    remove: int,
    insert: int,
    draw_size: int,
    threshold: int,
) -> int:
    covered = 0
    for rest in combinations(ground, draw_size):
        for included in (remove, insert):
            seven = set(rest) | {included}
            if _hits_threshold(tickets, seven, threshold):
                covered += len(seven)
    return covered


def _hits_threshold(tickets: Sequence[set[int]], outcome: set[int], threshold: int) -> bool:
    return any(len(ticket & outcome) >= threshold for ticket in tickets)
