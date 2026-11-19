"""Replay the seven Big Lotto selectors in frozen Wave 60 declaration order."""

from collections import Counter
from random import Random

from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters.base import CausalDrawRow, PortfolioBetAdapter

_NUMBERS = range(1, 50)
_ODDS = range(1, 50, 2)
_EVENS = range(2, 50, 2)
_PRIMES = (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47)
_COMPOSITES = tuple(n for n in range(2, 50) if n not in _PRIMES)


def _section(rng: Random, count: int, ranked: list[int]) -> list[tuple[int, ...]]:
    tickets: list[tuple[int, ...]] = []

    # Random orthogonal and zone split.
    used: set[int] = set()
    for _ in range(count):
        ticket = tuple(sorted(rng.sample([n for n in _NUMBERS if n not in used], 6)))
        tickets.append(ticket)
        used.update(ticket)

    width = 49 // count
    for i in range(count):
        start = i * width + 1
        stop = 50 if i == count - 1 else start + width
        tickets.append(tuple(sorted(rng.sample(range(start, stop), 6))))

    # Hot/cold split uses stable frequency ties in ascending number order.
    tickets.extend((tuple(sorted(ranked[:6])), tuple(sorted(ranked[-6:]))))
    if count == 3:
        middle = len(ranked) // 3
        tickets.append(tuple(sorted(ranked[middle : middle + 6])))

    # Odd/even split.
    tickets.extend((tuple(sorted(rng.sample(_ODDS, 6))), tuple(sorted(rng.sample(_EVENS, 6)))))
    if count == 3:
        tickets.append(tuple(sorted(rng.sample(_ODDS, 3) + rng.sample(_EVENS, 3))))

    # Consecutive spread uses fixed-width blocks even in the final zone.
    for i in range(count):
        start = i * width + 1
        mid = start + width // 2
        fixed = [start, start + 1, mid, mid + 1]
        remaining = [n for n in range(start, start + width) if n not in fixed]
        tickets.append(tuple(sorted(fixed + rng.sample(remaining, 2))))

    # Prime/composite split, followed by the six source Fibonacci offsets.
    tickets.append(tuple(sorted(rng.sample(_PRIMES, 6))))
    tickets.append(tuple(sorted(rng.sample(_COMPOSITES, 6))))
    if count == 3:
        tickets.append(tuple(sorted(rng.sample(_PRIMES[:10], 3) + rng.sample(_COMPOSITES[:10], 3))))
    for i in range(count):
        tickets.append(tuple(1 + i * 3 + offset for offset in (1, 2, 3, 5, 8, 13)))
    return tickets


class FrozenOrthogonalDiversification(PortfolioBetAdapter):
    strategy_id = "legacy_biglotto__orthogonal_diversification_benchmark__ce068c676ca5"
    strategy_version = "legacy-source-49a25effa62f-ce068c676ca5"
    strategy_name = "大樂透 正交分散基準"
    min_history = 1
    native_ticket_count = 35
    supported_lottery_types = (LotteryType.BIG_LOTTO,)

    def _predict_all(
        self, history: tuple[CausalDrawRow, ...], lottery_type: LotteryType
    ) -> tuple[tuple[int, ...], ...]:
        frequency = Counter(n for draw in history[-50:] for n in draw.numbers)
        ranked = sorted(_NUMBERS, key=frequency.__getitem__, reverse=True)
        # A target starts at seed 42. The three-bet section consumes the same stream.
        rng = Random(42)
        return tuple(_section(rng, 2, ranked) + _section(rng, 3, ranked))
