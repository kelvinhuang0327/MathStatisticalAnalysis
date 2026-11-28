"""Score preserved Big Lotto tickets with the historical issue boundary."""

from collections.abc import Iterable
from typing import TypedDict, cast

BOUNDARY = 103000081
TIERS = {(6, False): 'FIRST', (5, True): 'SECOND', (5, False): 'THIRD',
         (4, True): 'FOURTH', (4, False): 'FIFTH', (3, True): 'SIXTH',
         (3, False): 'GENERAL', (2, True): 'SEVENTH'}


class TicketScore(TypedDict):
    zone1_hits: int
    zone2_hit: bool
    prize_tier: str | None
    is_winner: bool


def _numbers(values: object, count: int) -> set[int]:
    if not isinstance(values, (list, tuple)):
        raise ValueError('incorrect number count')
    numbers = cast(list[int] | tuple[int, ...], values)
    if len(numbers) != count:
        raise ValueError('incorrect number count')
    if any(type(v) is not int or not 1 <= v <= 49 for v in numbers) or len(set(numbers)) != count:
        raise ValueError('invalid or repeated number')
    return set(numbers)


def score_ticket(issue: str | int, ticket: object, winning: object, special: object) -> TicketScore:
    if not str(issue).isdigit() or int(issue) <= 0:
        raise ValueError('invalid issue')
    selected = _numbers(ticket, 6)
    drawn = _numbers(winning, 6)
    if type(special) is not int or not 1 <= special <= 49 or special in drawn:
        raise ValueError('invalid special number')
    hits = len(selected & drawn)
    special_hit = special in selected
    tier = TIERS.get((hits, special_hit))
    if tier == 'SEVENTH' and int(issue) < BOUNDARY:
        tier = None
    return {
        'zone1_hits': hits,
        'zone2_hit': special_hit,
        'prize_tier': tier,
        'is_winner': tier is not None,
    }


def score_tickets(
    issue: str | int,
    tickets: Iterable[object],
    winning: object,
    special: object,
) -> list[TicketScore]:
    return [score_ticket(issue, ticket, winning, special) for ticket in tickets]
