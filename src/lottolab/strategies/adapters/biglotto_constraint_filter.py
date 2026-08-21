"""Target-native port of the frozen constraint-filter predictor.

The donor is ``lottery_api/models/constraint_filter_predictor.py`` at
``49a25effa62fc24f40789c16be6f11bdfb41a4a9`` (sha256
``3a85b3995002a9c66c50643e2b52a3cdc853c8e858242c7f335ce8736d576c85``).
Its semantics were recovered in
``lottolab.application.legacy_history_native_portfolios_wave2._constraint_filter``.
This adapter copies that producer (and the NumPy ``RandomState`` seam it
needs) into the strategy layer so production generate does not import
application code.

The donor reads newest-first history. The adapter contract supplies
oldest-first causal rows, so the producer reverses them at the edge and
keeps the donor's trailing-100 frequency/gap weights, sum / odd-even /
zone / consecutive / tail-digit constraints, 1000-attempt NumPy sample,
``random.Random`` fallback, and complementary second ticket. RNG follows
the wave2 reconstruction seed protocol (not CLI ``--seed``).
"""

from __future__ import annotations

import hashlib
import random
from collections import Counter

from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters.base import (
    CausalDrawRow,
    InvalidOutput,
    PortfolioBetAdapter,
)

_STRATEGY_ID = "legacy_biglotto__constraint_filter_predictor__3a85b3995002"
_MIN_NUMBER = 1
_MAX_NUMBER = 49
_PICK_COUNT = 6
_REPLICATE_ID = 0
_HISTORY_NATIVE_WAVE2_PROTOCOL = "legacy_history_native_wave2/v1"
_HISTORY_NATIVE_WAVE2_DEFAULT_USER_SEED = "biglotto-full-universe-history-native-wave2-v1"
_CONSTRAINT_FILTER_METHOD_ID = "lottery_api/models/constraint_filter_predictor.py"
_CONSTRAINT_FILTER_SOURCE_SHA256 = (
    "3a85b3995002a9c66c50643e2b52a3cdc853c8e858242c7f335ce8736d576c85"
)
_ZONES = ((1, 10), (11, 20), (21, 30), (31, 40), (41, 49))


class _LegacyNumpyRandomState:
    """Minimal NumPy ``RandomState`` MT19937 used by the wave2 reconstruction.

    Byte-identical re-transcription of
    ``lottolab.application.legacy_history_native_portfolios.LegacyNumpyRandomState``
    (the methods this donor actually calls), copied rather than imported so
    the strategy layer does not depend on application code.
    """

    _STATE_SIZE = 624
    _PERIOD_OFFSET = 397
    _MATRIX_A = 0x9908B0DF
    _UPPER_MASK = 0x80000000
    _LOWER_MASK = 0x7FFFFFFF

    def __init__(self, seed: int) -> None:
        self._state = [0] * self._STATE_SIZE
        self._state[0] = seed & 0xFFFFFFFF
        for index in range(1, self._STATE_SIZE):
            previous = self._state[index - 1]
            self._state[index] = (1812433253 * (previous ^ (previous >> 30)) + index) & 0xFFFFFFFF
        self._index = self._STATE_SIZE

    def _twist(self) -> None:
        for index in range(self._STATE_SIZE):
            combined = (self._state[index] & self._UPPER_MASK) | (
                self._state[(index + 1) % self._STATE_SIZE] & self._LOWER_MASK
            )
            value = self._state[(index + self._PERIOD_OFFSET) % self._STATE_SIZE] ^ (combined >> 1)
            if combined & 1:
                value ^= self._MATRIX_A
            self._state[index] = value
        self._index = 0

    def _next_uint32(self) -> int:
        if self._index >= self._STATE_SIZE:
            self._twist()
        value = self._state[self._index]
        self._index += 1
        value ^= value >> 11
        value ^= (value << 7) & 0x9D2C5680
        value ^= (value << 15) & 0xEFC60000
        value ^= value >> 18
        return value & 0xFFFFFFFF

    def _double(self) -> float:
        first = self._next_uint32() >> 5
        second = self._next_uint32() >> 6
        return (first * 67108864.0 + second) / 9007199254740992.0

    def _interval(self, maximum: int) -> int:
        if maximum < 0:
            raise ValueError("maximum must be non-negative")
        if maximum == 0:
            return 0
        mask = maximum
        mask |= mask >> 1
        mask |= mask >> 2
        mask |= mask >> 4
        mask |= mask >> 8
        mask |= mask >> 16
        while True:
            value = self._next_uint32() & mask
            if value <= maximum:
                return value

    def permutation(self, values: list[int]) -> list[int]:
        result = list(values)
        for index in range(len(result) - 1, 0, -1):
            swap_index = self._interval(index)
            result[index], result[swap_index] = result[swap_index], result[index]
        return result

    def choice_without_replacement(
        self,
        values: list[int],
        size: int,
        *,
        probabilities: list[float] | None = None,
    ) -> list[int]:
        if size < 0 or size > len(values):
            raise ValueError("sample size is outside the population")
        if probabilities is None:
            indices = self.permutation(list(range(len(values))))[:size]
            return [values[index] for index in indices]
        if len(probabilities) != len(values):
            raise ValueError("probability vector length must match population")
        if sum(value > 0.0 for value in probabilities) < size:
            raise ValueError("fewer positive probabilities than sample size")
        remaining_probabilities = list(probabilities)
        found: list[int] = []
        while len(found) < size:
            sample_count = size - len(found)
            for index in found:
                remaining_probabilities[index] = 0.0
            cumulative: list[float] = []
            running = 0.0
            for probability in remaining_probabilities:
                running += probability
                cumulative.append(running)
            if running <= 0.0:
                raise ValueError("probabilities must contain positive mass")
            cumulative = [value / running for value in cumulative]
            new_indices: list[int] = []
            for _ in range(sample_count):
                sample = self._double()
                index = 0
                while index < len(cumulative) and cumulative[index] <= sample:
                    index += 1
                if index >= len(cumulative):
                    index = len(cumulative) - 1
                if index not in new_indices:
                    new_indices.append(index)
            found.extend(new_indices)
        return [values[index] for index in found]


def _ticket(numbers: list[int]) -> tuple[int, ...]:
    values = tuple(sorted(numbers))
    if (
        len(values) != _PICK_COUNT
        or len(set(values)) != _PICK_COUNT
        or any(not _MIN_NUMBER <= number <= _MAX_NUMBER for number in values)
    ):
        raise InvalidOutput(f"{_STRATEGY_ID}: constraint-filter ticket is not a legal 6-of-49 set")
    return values


def _target_after_causal_cutoff(history: tuple[CausalDrawRow, ...]) -> str:
    """Return a deterministic request identity absent from the causal history.

    Wave2 seed material is keyed off an externally supplied
    ``target_draw_number`` this adapter contract has no slot for, so this
    synthesizes one from the causal history's own last draw — never the wall
    clock, a random draw, or any I/O. Replicate id stays 0 and user_seed
    stays the reconstruction default, matching wave 8/11/12.
    """

    draw_ids = {row.draw for row in history}
    target = f"{history[-1].draw}:lottolab-constraint-filter-next-target"
    while target in draw_ids:
        target = f"{target}:next"
    return target


def _seed_integer(history: tuple[CausalDrawRow, ...]) -> int:
    material = "|".join(
        (
            _HISTORY_NATIVE_WAVE2_PROTOCOL,
            _CONSTRAINT_FILTER_METHOD_ID,
            _CONSTRAINT_FILTER_SOURCE_SHA256,
            _target_after_causal_cutoff(history),
            str(_REPLICATE_ID),
            str(_HISTORY_NATIVE_WAVE2_DEFAULT_USER_SEED),
        )
    )
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
    return int(digest, 16)


def _numpy_pairwise_sum(values: list[float]) -> float:
    if len(values) < 8:
        result = -0.0
        for value in values:
            result += value
        return result
    if len(values) <= 128:
        partial = list(values[:8])
        index = 8
        aligned_end = len(values) - (len(values) % 8)
        while index < aligned_end:
            for offset in range(8):
                partial[offset] += values[index + offset]
            index += 8
        result = ((partial[0] + partial[1]) + (partial[2] + partial[3])) + (
            (partial[4] + partial[5]) + (partial[6] + partial[7])
        )
        while index < len(values):
            result += values[index]
            index += 1
        return result
    midpoint = len(values) // 2
    midpoint -= midpoint % 8
    return _numpy_pairwise_sum(values[:midpoint]) + _numpy_pairwise_sum(values[midpoint:])


def _constraint_passes(numbers: list[int]) -> bool:
    odd_count = sum(number % 2 == 1 for number in numbers)
    if not 2 <= odd_count <= 4:
        return False
    zones_covered = {
        index
        for number in numbers
        for index, (low, high) in enumerate(_ZONES)
        if low <= number <= high
    }
    if len(zones_covered) < 3:
        return False
    if not 120 <= sum(numbers) <= 180:
        return False
    sorted_numbers = sorted(numbers)
    longest = 1
    current = 1
    for index in range(1, len(sorted_numbers)):
        if sorted_numbers[index] == sorted_numbers[index - 1] + 1:
            current += 1
            longest = max(longest, current)
        else:
            current = 1
    if longest > 2:
        return False
    return len({number % 10 for number in numbers}) >= 4


def _constraint_weights(recent_first: tuple[CausalDrawRow, ...]) -> dict[int, float]:
    recent = recent_first[:100]
    frequency = Counter(number for draw in recent for number in draw.numbers)
    last_seen = {number: 100 for number in range(1, 50)}
    for index, draw in enumerate(recent):
        for number in draw.numbers:
            if last_seen[number] == 100:
                last_seen[number] = index
    maximum_frequency = max(frequency.values()) if frequency else 1
    weights: dict[int, float] = {}
    for number in range(1, 50):
        frequency_score = frequency.get(number, 0) / maximum_frequency
        gap = last_seen[number]
        if gap < 8:
            gap_score = gap / 8 * 0.5
        elif gap <= 15:
            gap_score = 1.0
        else:
            gap_score = max(0.3, 0.9 ** ((gap - 15) / 5))
        weights[number] = 0.5 * frequency_score + 0.5 * gap_score
    return weights


def _constraint_combination(
    weights: dict[int, float],
    numpy_rng: _LegacyNumpyRandomState,
    python_rng: random.Random,
) -> tuple[int, ...]:
    numbers = list(weights)
    raw_probabilities = [weights[number] for number in numbers]
    total = _numpy_pairwise_sum(raw_probabilities)
    probabilities = [value / total for value in raw_probabilities]
    for _ in range(1000):
        selected = numpy_rng.choice_without_replacement(
            numbers,
            _PICK_COUNT,
            probabilities=probabilities,
        )
        if _constraint_passes(selected):
            return _ticket(selected)
    return _ticket(python_rng.sample(numbers, _PICK_COUNT))


def _constraint_filter_bets(
    history: tuple[CausalDrawRow, ...],
) -> tuple[tuple[int, ...], tuple[int, ...]]:
    """Return the donor-exact ordered pair of main-number tickets."""

    recent_first = tuple(reversed(history))
    weights = _constraint_weights(recent_first)
    seed_integer = _seed_integer(history)
    numpy_rng = _LegacyNumpyRandomState(seed_integer % (2**32))
    python_rng = random.Random()
    python_rng.seed(seed_integer, version=2)
    tickets: list[tuple[int, ...]] = []
    all_used: set[int] = set()
    for bet_index in range(2):
        adjusted = {
            number: (weight if bet_index == 0 else weight * (0.3 if number in all_used else 1.2))
            for number, weight in weights.items()
        }
        ticket = _constraint_combination(adjusted, numpy_rng, python_rng)
        tickets.append(ticket)
        all_used.update(ticket)
    first, second = tickets
    return (first, second)


class BigLottoConstraintFilterPredictorAdapter(PortfolioBetAdapter):
    """Seeded two-ticket port of ``constraint_filter_predictor``."""

    strategy_id = _STRATEGY_ID
    strategy_name = "大樂透 Constraint Filter Predictor 2注"
    strategy_version = "v0.1"
    min_history = 1
    supported_lottery_types = (LotteryType.BIG_LOTTO,)
    native_ticket_count = 2

    def _predict_all(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[tuple[int, ...], ...]:
        return _constraint_filter_bets(history)


__all__ = ["BigLottoConstraintFilterPredictorAdapter"]
