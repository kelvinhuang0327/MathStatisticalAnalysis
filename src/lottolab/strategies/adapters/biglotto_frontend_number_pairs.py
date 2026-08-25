"""Target-native port of the legacy frontend Number Pairs strategy.

The donor is ``LotteryNewMeraged/src/engine/strategies/NumberPairsStrategy.js``.
The frontend receives newest-first rows, while LottoLab causal histories are
oldest-first, so the adapter reverses the validated history before preserving
the donor's pair insertion order.  The donor's confidence, method, and report
fields have no counterpart in the native single-ticket response.
"""

from __future__ import annotations

import random
from typing import Final, Protocol

from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters.base import BetAdapter, CausalDrawRow

_STRATEGY_ID: Final = "legacy_biglotto__frontend_number_pairs_strategy__72ebb17b5a96"
_MIN_NUMBER: Final = 1
_MAX_NUMBER: Final = 49
_PICK_COUNT: Final = 6


class _RandomSource(Protocol):
    """The small random surface used by the donor's ``Math.random`` calls."""

    def random(self) -> float:
        """Return one unseeded value in the half-open interval [0, 1)."""

        ...


def _pair_key(first: int, second: int) -> tuple[int, int]:
    return (first, second) if first < second else (second, first)


def _co_occurrence_matrix(
    history: tuple[CausalDrawRow, ...],
) -> dict[tuple[int, int], int]:
    """Build the donor's insertion-ordered, all-history pair-count map."""

    matrix: dict[tuple[int, int], int] = {}
    for row in history:
        numbers = row.numbers
        for first_index in range(len(numbers)):
            for second_index in range(first_index + 1, len(numbers)):
                pair = _pair_key(numbers[first_index], numbers[second_index])
                matrix[pair] = matrix.get(pair, 0) + 1
    return matrix


def _top_pairs(
    matrix: dict[tuple[int, int], int],
    count: int,
) -> tuple[tuple[tuple[int, int], int], ...]:
    """Sort by descending count while retaining stable insertion-order ties."""

    return tuple(sorted(matrix.items(), key=lambda item: -item[1])[:count])


def _pair_count(matrix: dict[tuple[int, int], int], first: int, second: int) -> int:
    return matrix.get(_pair_key(first, second), 0)


class BigLottoFrontendNumberPairsAdapter(BetAdapter):
    """Reproduce ``NumberPairsStrategy.predict`` for one Big Lotto ticket."""

    strategy_id = _STRATEGY_ID
    strategy_name = "大樂透 Frontend Number Pairs Strategy"
    strategy_version = "v0.1"
    min_history = 1
    supported_lottery_types = (LotteryType.BIG_LOTTO,)

    def __init__(self, rng: _RandomSource | None = None) -> None:
        # The source uses the process-global, unseeded Math.random.  Keeping
        # the module as the default preserves that behavior; the narrow seam
        # makes exact donor parity testable without changing production input.
        self._rng: _RandomSource = random if rng is None else rng

    def _predict(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[int, ...]:
        """Apply the donor's newest-first pair seed and noisy affinity fill."""

        del lottery_type
        newest_first = tuple(reversed(history))
        matrix = _co_occurrence_matrix(newest_first)
        top_pairs = _top_pairs(matrix, 10)

        seed_pair, _seed_count = top_pairs[
            int(self._rng.random() * min(5, len(top_pairs)))
        ]
        selected = list(seed_pair)

        while len(selected) < _PICK_COUNT:
            best_candidate = -1
            max_affinity = -1.0

            for candidate in range(_MIN_NUMBER, _MAX_NUMBER + 1):
                if candidate in selected:
                    continue

                affinity = sum(
                    _pair_count(matrix, candidate, selected_number)
                    for selected_number in selected
                )
                affinity *= 0.9 + self._rng.random() * 0.2

                # The donor uses strict greater-than, so the first candidate
                # in numeric range wins an exact noisy-affinity tie.
                if affinity > max_affinity:
                    max_affinity = affinity
                    best_candidate = candidate

            if best_candidate != -1:
                selected.append(best_candidate)
                continue

            # Valid Big Lotto history always leaves a candidate, but preserve
            # the donor's defensive random fill branch exactly.
            while True:
                candidate = _MIN_NUMBER + int(
                    self._rng.random() * (_MAX_NUMBER - _MIN_NUMBER + 1)
                )
                if candidate not in selected:
                    selected.append(candidate)
                    break

        return tuple(sorted(selected))
