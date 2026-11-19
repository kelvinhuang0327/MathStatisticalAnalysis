"""The ten positional configurations of the frozen BIG_LOTTO enhancement backtest."""

from __future__ import annotations

import math
from collections import Counter
from functools import lru_cache
from itertools import pairwise

from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters import biglotto_quad_strike as quad
from lottolab.strategies.adapters.base import CausalDrawRow, PortfolioBetAdapter
from lottolab.strategies.adapters.biglotto_composite_quick_predict_5bet import (
    _markov_orthogonal_bet,
)
from lottolab.strategies.adapters.biglotto_constraint_filter import _numpy_pairwise_sum

type History = tuple[CausalDrawRow, ...]
type Ticket = tuple[int, ...]
type Portfolio = tuple[Ticket, ...]
NUMBERS = range(1, 50)


def _used(bets: Portfolio) -> set[int]:
    return {n for ticket in bets for n in ticket}


@lru_cache(maxsize=32)
def _base(history: History) -> Portfolio:
    first = quad._fourier_rhythm_ticket(history)
    cold = quad._cold_numbers_ticket(history, frozenset(first))
    tail = quad._tail_balance_ticket(history, frozenset(first + cold))
    return first, cold, tail, _markov_orthogonal_bet(history, set(first + cold + tail), 30)


def _fill(ranked: list[int], used: set[int]) -> Ticket:
    bet = ranked[:6]
    if len(bet) < 6:
        bet.extend([n for n in NUMBERS if n not in used and n not in bet][: 6 - len(bet)])
    return tuple(sorted(bet))


def _consecutive(bets: Portfolio, history: History, freq: Counter[int]) -> Portfolio:
    pairs = Counter(
        (n, m) for row in history[-30:] for n, m in pairwise(sorted(row.numbers)) if m == n + 1
    )
    used = _used(bets)
    result = []
    for ticket in bets:
        moves = [(n, v) for n in ticket for v in (n - 1, n + 1) if 1 <= v <= 49 and v not in used]
        if moves:
            anchor, new = max(moves, key=lambda move: pairs[tuple(sorted(move))])
            if pairs[tuple(sorted((anchor, new)))] >= 2:
                weak = min((n for n in ticket if n != anchor), key=freq.__getitem__)
                ticket = tuple(sorted([n for n in ticket if n != weak] + [new]))
                used.add(new)
        result.append(ticket)
    return tuple(result)


def _diverse(history: History, base: Portfolio, rank: list[int], freq: Counter[int]) -> Portfolio:
    zones = [set(rank[:12]), set(rank[12:24]), set(rank[24:37]), set(rank[37:])]
    bets = []
    used: set[int] = set()
    for i, zone in enumerate(zones):
        if i == 0:
            original = base[0]
        elif i == 1:
            original = quad._cold_numbers_ticket(history, frozenset(used))
        elif i == 2:
            original = quad._tail_balance_ticket(history, frozenset(used))
        else:
            original = _markov_orthogonal_bet(history, used, 30)
        kept = sorted(n for n in original if n in zone)
        extras = sorted(
            (n for n in zone if n not in used and n not in kept),
            key=freq.__getitem__,
            reverse=i == 0,
        )
        bet = tuple(sorted((kept + extras)[:6]))
        bets.append(bet)
        used.update(bet)
    return tuple(bets)


def _learned(history: History, base: Portfolio) -> Portfolio:
    wins = [0] * 4
    for i in range(len(history) - 20, len(history)):
        for j, ticket in enumerate(_base(history[:i])):
            wins[j] += len(set(ticket).intersection(history[i].numbers)) >= 3
    weights = [max(0.5, min(2.0, 0.7 + count / 20 * 15)) for count in wins]
    scores: Counter[int] = Counter()
    for n in base[0]:
        scores[n] += weights[0] * 3
    freq = Counter(n for row in history[-100:] for n in row.numbers)
    for i, n in enumerate(sorted(NUMBERS, key=freq.__getitem__)[:12]):
        scores[n] += weights[1] * (2 - i * 0.1)
    for n in quad._tail_balance_ticket(history, frozenset()):
        scores[n] += weights[2] * 2
    for n in _markov_orthogonal_bet(history, set(), 30):
        scores[n] += weights[3] * 2
    ranks = sorted(scores, key=scores.__getitem__, reverse=True)
    bets = []
    used: set[int] = set()
    for _ in range(4):
        bet = _fill([n for n in ranks if n not in used], used)
        bets.append(bet)
        used.update(bet)
    return tuple(bets)


def _sequence(history: History, base: Portfolio) -> Portfolio:
    scores: Counter[int] = Counter()
    for i, row in enumerate(reversed(history[-100:])):
        for n in row.numbers:
            scores[n] += math.exp(-i / 20)
    recent = history[-30:]
    previous, last = map(set, (history[-2].numbers, history[-1].numbers))
    for a, b, c in zip(recent, recent[1:], recent[2:], strict=False):
        weight = 0.5 * len(previous.intersection(a.numbers)) * len(last.intersection(b.numbers))
        for n in c.numbers:
            scores[n] += weight
    used = _used(base[:3])
    for n in NUMBERS:
        streak = sum(n in row.numbers for row in history[-3:])
        if streak >= 2:
            scores[n] += streak * 0.3
    return *base[:3], _fill(
        sorted((n for n in NUMBERS if n not in used), key=scores.__getitem__, reverse=True), used
    )


class Enhancements(PortfolioBetAdapter):
    strategy_id = "legacy_biglotto__backtest_biglotto_enhancements__b0bf78ef7e32"
    strategy_name = "TS3 enhancements, ten source configurations"
    strategy_version = "legacy-source-49a25effa62f-b0bf78ef7e32"
    supported_lottery_types = (LotteryType.BIG_LOTTO,)
    native_ticket_count = 42
    min_history = 649

    def _predict_all(self, history: History, lottery_type: LotteryType) -> Portfolio:
        base = _base(history)
        freq = Counter(n for row in history[-30:] for n in row.numbers)
        rank = sorted(NUMBERS, key=freq.__getitem__, reverse=True)
        hot = set(rank[:10])
        hot_regime = (
            _numpy_pairwise_sum([len(hot.intersection(row.numbers)) / 6 for row in history[-10:]])
            / 10
            >= 0.45
        )
        last_seen = {n: i for i, row in enumerate(history) for n in row.numbers}
        adaptive = base
        if hot_regime:
            used = _used(base[:3])
            gray = sorted(
                (n for n in rank[12:30] if n not in used),
                key=lambda n: len(history) - last_seen.get(n, 0),
            )
            adaptive = *base[:3], _fill(gray, used)
        diverse = _diverse(history, base, rank, freq)
        injected = _consecutive(base, history, freq)

        def anti(bets: Portfolio) -> Ticket:
            used = _used(bets)
            gray = (n for n in rank[14:35] if n not in used)
            scored = sorted(
                gray,
                key=lambda n: 1 / (abs(len(history) - last_seen.get(n, 0) - 8) + 1) + 0.1 * freq[n],
                reverse=True,
            )
            return _fill(scored, used)

        return (
            *base,
            *adaptive,
            *injected,
            *diverse,
            *base,
            anti(base),
            *_learned(history, base),
            *_sequence(history, base),
            *_consecutive(adaptive, history, freq),
            *(diverse if hot_regime else injected),
            *injected,
            anti(injected),
        )
