"""Replay portfolios from the frozen FeatureLibrary-based BIG_LOTTO programs."""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from itertools import combinations, pairwise

from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters import biglotto_quad_strike as quad
from lottolab.strategies.adapters.base import CausalDrawRow, PortfolioBetAdapter
from lottolab.strategies.adapters.biglotto_constraint_filter import _numpy_pairwise_sum

type History = tuple[CausalDrawRow, ...]
type Vector = tuple[float, ...]
type Portfolio = tuple[tuple[int, ...], ...]

NUMBERS = range(1, 50)


def _normalize(values: Vector) -> Vector:
    mean = _numpy_pairwise_sum(list(values)) / len(values)
    centered = [x - mean for x in values]
    std = math.sqrt(_numpy_pairwise_sum([x * x for x in centered]) / len(values))
    return tuple(x / std for x in centered) if std else values


def _rank(values: Vector) -> tuple[int, ...]:
    return tuple(i + 1 for i in reversed(quad._legacy_numpy_argsort(values)))


def _frequency(history: History, window: int) -> Vector:
    rows = history[-window:]
    counts = Counter(n for row in rows for n in row.numbers)
    return tuple(counts[n] / len(rows) for n in NUMBERS)


def _fourier(bits: tuple[float, ...]) -> float:
    packed = quad._pocketfft_real_packed(bits)
    bins = [
        (packed[i], packed[i + 1] if i + 1 < len(packed) else 0.0) for i in range(1, len(packed), 2)
    ]
    mags = tuple(quad._legacy_complex_magnitude(x, y) for x, y in bins)
    top = quad._legacy_numpy_argsort(mags)[-3:][::-1]
    total = 0.0
    for i in top:
        real, imag = bins[i]
        total += mags[i] * max(0.0, math.cos(math.atan2(imag, real)))
    return total


def _lag_two(bits: tuple[float, ...]) -> float:
    recent = bits[-50:]
    if len(recent) <= 2:
        return 0.0
    n = len(recent) - 2
    x_mean, y_mean = sum(recent[2:]) / n, sum(recent[:-2]) / n
    x = [v - x_mean for v in recent[2:]]
    y = [v - y_mean for v in recent[:-2]]
    if not 0 < x_mean < 1 or not 0 < y_mean < 1:
        return 0.0
    # The source BLAS accumulates the sample covariance with fused multiply-add.
    # corrcoef then divides by each sample deviation in turn.
    xx = xy = yy = 0.0
    for a, b in zip(x, y, strict=True):
        xx = math.fma(a, a, xx)
        xy = math.fma(a, b, xy)
        yy = math.fma(b, b, yy)
    scale = 1.0 / (n - 1)
    return max(-1.0, min(1.0, (xy * scale / math.sqrt(xx * scale)) / math.sqrt(yy * scale)))


@dataclass(frozen=True)
class _Signals:
    fourier: Vector
    lag: Vector
    markov: Vector
    deviation: Vector
    hot: Vector
    cold: Vector
    zonal: Vector

    def triple(self) -> Vector:
        return _normalize(
            tuple(f + l - d for f, l, d in zip(self.fourier, self.lag, self.deviation, strict=True))
        )


@lru_cache(maxsize=32)
def _signals(history: History) -> _Signals:
    """Compute the shared frozen features once for portfolios at the same cutoff."""
    zones = Counter((n - 1) // 10 for row in history for n in row.numbers)
    recent = history[-10:]
    zones10 = Counter((n - 1) // 10 for row in recent for n in row.numbers)
    zone_score = _normalize(
        tuple(
            zones[(n - 1) // 10] / (6 * len(history)) - zones10[(n - 1) // 10] / (6 * len(recent))
            for n in NUMBERS
        )
    )
    fourier, lags, markov, momentum = [], [], [], []
    for n in NUMBERS:
        bits = tuple(float(n in row.numbers) for row in history)
        fourier.append(_fourier(bits))
        lags.append(_lag_two(bits))
        transitions = [b for a, b in pairwise(bits[-30:]) if a == bits[-1]]
        markov.append(sum(transitions) / len(transitions) if transitions else 0.0)
        positions = [i for i, b in enumerate(bits) if b]
        momentum.append(2 * positions[-1] - positions[-2] - len(bits) if len(positions) >= 2 else 0)
    hot = _frequency(history, 100)
    expected = 6.0 / 49
    return _Signals(
        _normalize(tuple(fourier)),
        _normalize(tuple(lags)),
        _normalize(tuple(markov)),
        _normalize(tuple((x - expected) / expected for x in hot)),
        _normalize(hot),
        _normalize(tuple(-v for v in _frequency(history, 30))),
        _normalize(
            tuple(1.5 * z + g for z, g in zip(zone_score, _normalize(tuple(momentum)), strict=True))
        ),
    )


def _disjoint(vectors: tuple[Vector, ...], *, alternate: bool = False) -> Portfolio:
    pools = [iter(_rank(scores)) for scores in vectors]
    bets: list[list[int]] = [[] for _ in pools]
    used: set[int] = set()
    for _ in range(6 if alternate else 1):
        for bet, pool in zip(bets, pools, strict=True):
            for _ in range(1 if alternate else 6):
                number = next(n for n in pool if n not in used)
                used.add(number)
                bet.append(number)
    return tuple(tuple(sorted(ticket)) for ticket in bets)


class _SignalPortfolio(PortfolioBetAdapter):
    supported_lottery_types = (LotteryType.BIG_LOTTO,)
    min_history = 649


class EdgeSplicer(_SignalPortfolio):
    strategy_name = "Edge Splicer two- and three-bet configurations"
    strategy_id = "legacy_biglotto__edge_splicer__04d9e8bbfe76"
    strategy_version = "legacy-source-49a25effa62f-04d9e8bbfe76"
    native_ticket_count = 5

    def _predict_all(self, history: History, lottery_type: LotteryType) -> Portfolio:
        s = _signals(history)
        triple = s.triple()
        blend = tuple(0.6 * t + 0.4 * m for t, m in zip(triple, s.markov, strict=True))
        return *_disjoint((blend, s.cold)), *_disjoint((triple, s.markov, s.cold))


class EdgeSplicerV2(_SignalPortfolio):
    strategy_name = "Edge Splicer tri-axis round-robin"
    strategy_id = "legacy_biglotto__edge_splicer_v2__6b6e9d64da12"
    strategy_version = "legacy-source-49a25effa62f-6b6e9d64da12"
    native_ticket_count = 3

    def _predict_all(self, history: History, lottery_type: LotteryType) -> Portfolio:
        s = _signals(history)
        return _disjoint((s.triple(), s.markov, s.zonal), alternate=True)


class EdgeSplicerFive(_SignalPortfolio):
    strategy_name = "Edge Splicer five-dimensional matrix"
    strategy_id = "legacy_biglotto__edge_splicer_5bet__da1d1eed4d96"
    strategy_version = "legacy-source-49a25effa62f-da1d1eed4d96"
    native_ticket_count = 5

    def _predict_all(self, history: History, lottery_type: LotteryType) -> Portfolio:
        s = _signals(history)
        return _disjoint(
            (s.fourier, s.lag, s.markov, s.zonal, tuple(-x for x in s.hot)), alternate=True
        )


class StandardFive(_SignalPortfolio):
    strategy_name = "Original TS3, Markov and frequency round-robin"
    strategy_id = "legacy_biglotto__standard_ts3_5bet__527fed00a7c4"
    strategy_version = "legacy-source-49a25effa62f-527fed00a7c4"
    native_ticket_count = 5

    def _predict_all(self, history: History, lottery_type: LotteryType) -> Portfolio:
        s = _signals(history)
        return _disjoint(
            (s.fourier, s.lag, tuple(-x for x in s.deviation), s.markov, tuple(-x for x in s.hot)),
            alternate=True,
        )


class EvaluateCombinations(_SignalPortfolio):
    strategy_name = "Signal prefixes of two through five tickets"
    strategy_id = "legacy_biglotto__evaluate_combinations__d49d0787d0c6"
    strategy_version = "legacy-source-49a25effa62f-d49d0787d0c6"
    native_ticket_count = 14

    def _predict_all(self, history: History, lottery_type: LotteryType) -> Portfolio:
        s = _signals(history)
        five = _disjoint((s.triple(), s.markov, s.cold, s.hot, s.lag))
        return tuple(ticket for count in range(2, 6) for ticket in five[:count])


class GenerateTwoThree(_SignalPortfolio):
    strategy_name = "Two- and three-ticket orthogonal snake drafts"
    strategy_id = "legacy_biglotto__generate_2_3_bets__f8853b95f3c5"
    strategy_version = "legacy-source-49a25effa62f-f8853b95f3c5"
    native_ticket_count = 5
    min_history = 1

    def _predict_all(self, history: History, lottery_type: LotteryType) -> Portfolio:
        s = _signals(history)
        rank = _rank(
            tuple(
                h + 1.5 * m + l + 1.2 * f - 0.8 * d
                for h, m, l, f, d in zip(
                    s.hot, s.markov, s.lag, s.fourier, s.deviation, strict=True
                )
            )
        )
        result = []
        for count in (2, 3):
            bets: list[list[int]] = [[] for _ in range(count)]
            for i, n in enumerate(rank[: 6 * count]):
                dest = i % count if i // count % 2 == 0 else count - 1 - i % count
                bets[dest].append(n)
            result.extend(tuple(sorted(b)) for b in bets)
        return tuple(result)


class EvaluateConcentrator(_SignalPortfolio):
    strategy_name = "Two-ticket co-occurrence concentrator"
    strategy_id = "legacy_biglotto__evaluate_concentrator__d732e4dd594c"
    strategy_version = "legacy-source-49a25effa62f-d732e4dd594c"
    native_ticket_count = 2

    def _predict_all(self, history: History, lottery_type: LotteryType) -> Portfolio:
        s = _signals(history)
        rank = _rank(
            tuple(
                f + l - d + m - h
                for f, l, d, m, h in zip(
                    s.fourier, s.lag, s.deviation, s.markov, s.hot, strict=True
                )
            )
        )
        pool = set(rank[:15])
        pairs = Counter(
            pair for row in history[-100:] for pair in combinations(sorted(row.numbers), 2)
        )

        def co(a: int, b: int) -> int:
            return pairs[min(a, b), max(a, b)]

        first = [rank[0]]
        pool.remove(first[0])
        second = [min(pool, key=lambda n: co(n, first[0]))]
        pool.remove(second[0])
        for _ in range(5):
            for bet in (first, second):
                best = max(pool, key=lambda n, bet=bet: sum(co(n, k) for k in bet))
                bet.append(best)
                pool.remove(best)
        return tuple(sorted(first)), tuple(sorted(second))
