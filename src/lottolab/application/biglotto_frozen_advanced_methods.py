"""Replay the five local BIG_LOTTO selectors from the frozen Wave 63 benchmark."""

import math
import random
from collections import Counter
from contextlib import suppress
from itertools import combinations
from typing import Protocol

from lottolab.application.legacy_history_native_portfolios import LegacyNumpyRandomState
from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters.base import CausalDrawRow, InvalidOutput, PortfolioBetAdapter

type History = tuple[tuple[int, ...], ...]
_NUMBERS = range(1, 50)
_PICK = 6


class _Selector(Protocol):
    def predict(self, history: History) -> tuple[int, ...]: ...


class _ContextualBandit:
    def train(self, history: History) -> None:
        """The donor's range(200, len(history)) is empty for every Wave 63 training slice."""

    def predict(self, history: History) -> tuple[int, ...]:
        return tuple(_NUMBERS[:_PICK])  # Zero-score ties retain ascending number order.


def _binary_kendall_tau(left: int, right: int, joint: int) -> float:
    # Each vector is exactly 100 entries, padded with zero for a short prefix.
    # The donor skips constant columns. SciPy 1.12 tau-b divides by the two
    # roots separately, in ascending number order, then clips rounding error.
    if left in (0, 100) or right in (0, 100):
        return 0.0
    numerator = 100 * joint - left * right
    tau = numerator / math.sqrt(left * (100 - left)) / math.sqrt(right * (100 - right))
    return min(1.0, max(-1.0, tau))


class _CopulaAnalyzer:
    def __init__(self) -> None:
        self.tau = [[0.0] * 50 for _ in range(50)]

    def train(self, history: History) -> None:
        occurrences = [0] * 50
        for index, row in enumerate(history[:100]):
            bit = 1 << index
            for number in row:
                occurrences[number] |= bit
        counts = [mask.bit_count() for mask in occurrences]
        for left, right in combinations(_NUMBERS, 2):
            joint = (occurrences[left] & occurrences[right]).bit_count()
            value = _binary_kendall_tau(counts[left], counts[right], joint)
            self.tau[left][right] = self.tau[right][left] = value

    def predict(self, history: History) -> tuple[int, ...]:
        counts = Counter(number for row in history[:50] for number in row)
        candidates = [number for number, _ in counts.most_common()]
        if not candidates:
            return (1,)
        selected = [candidates.pop(0)]
        scores = [0.0] * 50
        while candidates and len(selected) < _PICK:
            # The reference adds tau values left to right in selection order.
            # Equal sums retain the Counter's recent-first encounter order.
            for number in candidates:
                scores[number] += self.tau[number][selected[-1]]
            best = max(candidates, key=scores.__getitem__)
            selected.append(best)
            candidates.remove(best)
        return tuple(sorted(selected))


class _AnomalyDetector:
    def __init__(self) -> None:
        self.expected: dict[int, float] | None = None

    def train(self, history: History) -> None:
        counts = Counter(number for row in history for number in row)
        total = counts.total()
        self.expected = {number: counts[number] / total for number in _NUMBERS}

    def predict(self, history: History) -> tuple[int, ...]:
        expected = self.expected
        if expected is None:
            return tuple(_NUMBERS[:_PICK])
        recent = Counter(number for row in history[:30] for number in row)
        ranked = sorted(_NUMBERS, key=lambda n: expected[n] - recent[n] / (30 * 6), reverse=True)
        return tuple(ranked[:_PICK])


class _GraphCooccurrence:
    def __init__(self) -> None:
        self.adjacency = [Counter[int]() for _ in _NUMBERS]

    def train(self, history: History) -> None:
        for row in history[:100]:
            for left, right in combinations(row, 2):
                self.adjacency[left - 1][right - 1] += 1
                self.adjacency[right - 1][left - 1] += 1

    def predict(self, history: History) -> tuple[int, ...]:
        # In the donor expression, 0.85 * trans.T is evaluated before @.
        # Its NumPy 1.26.2 ARM OpenBLAS kernel accumulates one fused multiply-add
        # per source column in order. Positive zero-weight edges have no effect.
        transitions: list[list[tuple[int, float]]] = []
        for neighbors in self.adjacency:
            total = neighbors.total()
            transitions.append([(n, 0.85 * (count / total)) for n, count in neighbors.items()])
        rank = [1.0 / 49] * 49
        base = (1.0 - 0.85) / 49
        for _ in range(20):
            incoming = [0.0] * 49
            for source_rank, edges in zip(rank, transitions, strict=True):
                for number, coefficient in edges:
                    incoming[number] = math.fma(coefficient, source_rank, incoming[number])
            rank = [base + value for value in incoming]
        ranked = sorted(_NUMBERS, key=lambda n: rank[n - 1], reverse=True)
        return tuple(ranked[:_PICK])


class _AttentionScorer:
    def predict(self, history: History) -> tuple[int, ...]:
        scores = [0.0] * 50
        for age, row in enumerate(history[:100]):
            weight = 0.95**age
            for number in row:
                scores[number] += weight
        ranked = sorted(_NUMBERS, key=scores.__getitem__, reverse=True)
        return tuple(ranked[:_PICK])


_METHODS: tuple[type[_Selector], ...] = (
    _ContextualBandit,
    _CopulaAnalyzer,
    _AnomalyDetector,
    _GraphCooccurrence,
    _AttentionScorer,
)


class FrozenAdvancedMethodsBenchmark(PortfolioBetAdapter):
    strategy_id = "legacy_biglotto__advanced_methods_benchmark__87ee0d15033c"
    strategy_version = "legacy-source-49a25effa62f-87ee0d15033c"
    strategy_name = "大樂透 Advanced Methods Benchmark"
    min_history = 1
    native_ticket_count = 25
    supported_lottery_types = (LotteryType.BIG_LOTTO,)

    def _history_window(self, history: tuple[object, ...]) -> tuple[object, ...]:
        return history[-1000:]

    def _predict_all(
        self, history: tuple[CausalDrawRow, ...], lottery_type: LotteryType
    ) -> tuple[tuple[int, ...], ...]:
        recent = tuple(row.numbers for row in reversed(history))
        training = recent[:200]
        python_rng = random.Random(42)
        # Wave 63 resets both local streams. Only the exception fallback draws randomness.
        LegacyNumpyRandomState(42)
        portfolio = []
        for bets in (2, 3):
            for selector_class in _METHODS:
                selector = selector_class()
                train = getattr(selector, "train", None)
                if train is not None:
                    with suppress(Exception):
                        train(training)
                for _ in range(bets):
                    try:
                        selected = selector.predict(recent)
                    except Exception:
                        selected = tuple(python_rng.sample(_NUMBERS, _PICK))
                    ticket = tuple(sorted(int(n) for n in selected))
                    if (
                        len(ticket) != _PICK
                        or len(set(ticket)) != _PICK
                        or ticket[0] < 1
                        or ticket[-1] > 49
                    ):
                        raise InvalidOutput("illegal advanced-method source ticket")
                    portfolio.append(ticket)
        return tuple(portfolio)
