"""Faithful ports of four frozen BIG_LOTTO history-native methods."""

from __future__ import annotations

import hashlib
import math
import random
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from typing import Final

from lottolab.application.strategy_preserving_20_ticket import Ticket

HISTORY_NATIVE_PROTOCOL = "legacy_history_native/v1"
DEFAULT_HISTORY_NATIVE_USER_SEED = "biglotto-full-universe-history-native-v1"
OPTIMIZED_ENSEMBLE_METHOD_ID = "lottery_api/models/optimized_ensemble.py"
SOCIAL_WISDOM_METHOD_ID = "lottery_api/models/social_wisdom_predictor.py"
QUICK_ML_METHOD_ID = "tools/quick_ml_predict.py"
EXHAUSTIVE_AUDIT_METHOD_ID = "tools/big_lotto_exhaustive_audit.py"
OPTIMIZED_ENSEMBLE_SOURCE_SHA256 = (
    "e05e0fde22d7a477cfa64f7562dec853a95eaa5e200764531eefe8158df887a2"
)
SOCIAL_WISDOM_SOURCE_SHA256 = (
    "a00829b5d875cb8202c3bbd90ad7202fa6b95f568e3e8d821a6cdbffe6a95e3b"
)
QUICK_ML_SOURCE_SHA256 = (
    "8b7ba0b52e2dfcb7bd39997be9dbfab90a81f6e44c3fcf269ac5c9ddaa266d80"
)
EXHAUSTIVE_AUDIT_SOURCE_SHA256 = (
    "694d353b7ca230af6a860f5ef8977fdecbab031a30ad4e6c51b3d0c0f98b910c"
)
SUPPORTED_HISTORY_NATIVE_METHODS = (
    OPTIMIZED_ENSEMBLE_METHOD_ID,
    SOCIAL_WISDOM_METHOD_ID,
    QUICK_ML_METHOD_ID,
    EXHAUSTIVE_AUDIT_METHOD_ID,
)
SOURCE_SHA256_BY_HISTORY_NATIVE_METHOD: Final = {
    OPTIMIZED_ENSEMBLE_METHOD_ID: OPTIMIZED_ENSEMBLE_SOURCE_SHA256,
    SOCIAL_WISDOM_METHOD_ID: SOCIAL_WISDOM_SOURCE_SHA256,
    QUICK_ML_METHOD_ID: QUICK_ML_SOURCE_SHA256,
    EXHAUSTIVE_AUDIT_METHOD_ID: EXHAUSTIVE_AUDIT_SOURCE_SHA256,
}
NATIVE_TICKET_COUNT_BY_HISTORY_NATIVE_METHOD: Final = {
    OPTIMIZED_ENSEMBLE_METHOD_ID: 1,
    SOCIAL_WISDOM_METHOD_ID: 8,
    QUICK_ML_METHOD_ID: 2,
    EXHAUSTIVE_AUDIT_METHOD_ID: 3,
}
MINIMUM_HISTORY_BY_HISTORY_NATIVE_METHOD: Final = {
    OPTIMIZED_ENSEMBLE_METHOD_ID: 1,
    SOCIAL_WISDOM_METHOD_ID: 1,
    QUICK_ML_METHOD_ID: 1,
    EXHAUSTIVE_AUDIT_METHOD_ID: 50,
}
RANDOM_PROTOCOL_BY_HISTORY_NATIVE_METHOD: Final = {
    OPTIMIZED_ENSEMBLE_METHOD_ID: "NONE_DETERMINISTIC",
    SOCIAL_WISDOM_METHOD_ID: "numpy.random.RandomState(MT19937)",
    QUICK_ML_METHOD_ID: "NONE_DETERMINISTIC",
    EXHAUSTIVE_AUDIT_METHOD_ID: "random.Random(MT19937)",
}
QUICK_ML_PATTERN_SLICE_REASON = "FROZEN_SOURCE_PATTERN_SLICE_INDEX_ERROR"

_MIN_NUMBER = 1
_MAX_NUMBER = 49
_PICK_COUNT = 6


class LegacyNumpyRandomState:
    """Minimal NumPy ``RandomState`` MT19937 + legacy Gaussian compatibility."""

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
            self._state[index] = (
                1812433253 * (previous ^ (previous >> 30)) + index
            ) & 0xFFFFFFFF
        self._index = self._STATE_SIZE
        self._has_gauss = False
        self._cached_gauss = 0.0

    def _twist(self) -> None:
        for index in range(self._STATE_SIZE):
            combined = (
                self._state[index] & self._UPPER_MASK
            ) | (
                self._state[(index + 1) % self._STATE_SIZE]
                & self._LOWER_MASK
            )
            value = self._state[
                (index + self._PERIOD_OFFSET) % self._STATE_SIZE
            ] ^ (combined >> 1)
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

    def _standard_normal(self) -> float:
        if self._has_gauss:
            self._has_gauss = False
            return self._cached_gauss
        while True:
            first = 2.0 * self._double() - 1.0
            second = 2.0 * self._double() - 1.0
            radius_squared = first * first + second * second
            if radius_squared < 1.0 and radius_squared != 0.0:
                scale = math.sqrt(
                    -2.0 * math.log(radius_squared) / radius_squared
                )
                self._cached_gauss = first * scale
                self._has_gauss = True
                return second * scale

    def normal(self, location: float, scale: float, size: int) -> list[float]:
        return [
            location + scale * self._standard_normal()
            for _ in range(size)
        ]

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
            result[index], result[swap_index] = (
                result[swap_index],
                result[index],
            )
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


def _legacy_numpy_argsort(values: list[float]) -> list[int]:
    """Port NumPy's legacy float64 indirect introsort for small arrays."""

    indices = list(range(len(values)))
    if len(indices) < 2:
            return indices
    stack: list[tuple[int, int, int]] = []
    lower = 0
    upper = len(indices) - 1
    depth = (len(indices).bit_length() - 1) * 2
    while True:
        if depth < 0:
            raise AssertionError("unexpected introsort heap fallback")
        while upper - lower > 15:
            middle = lower + ((upper - lower) >> 1)
            if values[indices[middle]] < values[indices[lower]]:
                indices[middle], indices[lower] = (
                    indices[lower],
                    indices[middle],
                )
            if values[indices[upper]] < values[indices[middle]]:
                indices[upper], indices[middle] = (
                    indices[middle],
                    indices[upper],
                )
            if values[indices[middle]] < values[indices[lower]]:
                indices[middle], indices[lower] = (
                    indices[lower],
                    indices[middle],
                )
            pivot = values[indices[middle]]
            left = lower
            right = upper - 1
            indices[middle], indices[right] = indices[right], indices[middle]
            while True:
                left += 1
                while values[indices[left]] < pivot:
                    left += 1
                right -= 1
                while pivot < values[indices[right]]:
                    right -= 1
                if left >= right:
                    break
                indices[left], indices[right] = indices[right], indices[left]
            pivot_slot = upper - 1
            indices[left], indices[pivot_slot] = (
                indices[pivot_slot],
                indices[left],
            )
            depth -= 1
            if left - lower < upper - left:
                stack.append((left + 1, upper, depth))
                upper = left - 1
            else:
                stack.append((lower, left - 1, depth))
                lower = left + 1

        for position in range(lower + 1, upper + 1):
            value_index = indices[position]
            cursor = position
            previous = position - 1
            while (
                cursor > lower
                and values[value_index] < values[indices[previous]]
            ):
                indices[cursor] = indices[previous]
                cursor -= 1
                previous -= 1
            indices[cursor] = value_index
        if not stack:
            break
        lower, upper, depth = stack.pop()
    return indices


def legacy_numpy_argsort(values: list[float]) -> list[int]:
    """Expose the frozen NumPy-2.0 indirect ordering used by legacy ports."""

    return _legacy_numpy_argsort(values)


class LegacyHistoryNativeError(ValueError):
    """A request cannot satisfy the frozen history-native contract."""


class LegacyHistoryNativeSourceError(LegacyHistoryNativeError):
    """The frozen source deterministically fails for this causal history."""

    def __init__(self, reason_code: str) -> None:
        super().__init__(reason_code)
        self.reason_code = reason_code


@dataclass(frozen=True, slots=True)
class LegacyHistoryDraw:
    draw_number: str
    numbers: Ticket


@dataclass(frozen=True, slots=True)
class LegacyHistoryNativeRequest:
    legacy_method_id: str
    target_draw_number: str
    history: tuple[LegacyHistoryDraw, ...]
    replicate_id: int = 0
    user_seed: str | int = DEFAULT_HISTORY_NATIVE_USER_SEED


@dataclass(frozen=True, slots=True)
class LegacyHistoryNativeMetadata:
    protocol: str
    legacy_method_id: str
    source_sha256: str
    target_draw_number: str
    replicate_id: int
    user_seed: str | int
    seed_material: str
    seed_digest: str
    seed_integer: int
    random_protocol: str
    randomness_used: bool
    history_draw_count: int
    history_first_draw_number: str
    history_cutoff_draw_number: str
    source_history_order: str
    native_ticket_count: int
    native_ticket_order: str
    native_duplicate_ticket_count: int
    candidate_k: None
    combination_count: None

    def canonical_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class LegacyHistoryNativeResult:
    tickets: tuple[Ticket, ...]
    metadata: LegacyHistoryNativeMetadata


def _ticket(numbers: list[int]) -> Ticket:
    values = tuple(sorted(numbers))
    if (
        len(values) != _PICK_COUNT
        or len(set(values)) != _PICK_COUNT
        or any(not _MIN_NUMBER <= number <= _MAX_NUMBER for number in values)
    ):
        raise LegacyHistoryNativeSourceError("FROZEN_SOURCE_INVALID_TICKET")
    return values


def _validate_request(request: LegacyHistoryNativeRequest) -> None:
    if request.legacy_method_id not in SOURCE_SHA256_BY_HISTORY_NATIVE_METHOD:
        raise LegacyHistoryNativeError("legacy method is outside the history-native batch")
    if (
        type(request.target_draw_number) is not str
        or not request.target_draw_number
    ):
        raise LegacyHistoryNativeError("target draw number must be non-empty")
    if type(request.replicate_id) is not int or request.replicate_id < 0:
        raise LegacyHistoryNativeError("replicate_id must be a non-negative integer")
    if type(request.user_seed) not in (str, int):
        raise LegacyHistoryNativeError("user_seed must be a string or integer")
    if not request.history:
        raise LegacyHistoryNativeError("causal history must not be empty")
    seen: set[str] = set()
    for draw in request.history:
        if not draw.draw_number or draw.draw_number in seen:
            raise LegacyHistoryNativeError("causal history draw identities are invalid")
        seen.add(draw.draw_number)
        _ticket(list(draw.numbers))


def _seed(request: LegacyHistoryNativeRequest) -> tuple[str, str, int]:
    source_sha256 = SOURCE_SHA256_BY_HISTORY_NATIVE_METHOD[
        request.legacy_method_id
    ]
    material = "|".join(
        (
            HISTORY_NATIVE_PROTOCOL,
            request.legacy_method_id,
            source_sha256,
            request.target_draw_number,
            str(request.replicate_id),
            str(request.user_seed),
        )
    )
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
    return material, digest, int(digest, 16)


def _optimized_ensemble(
    history: tuple[LegacyHistoryDraw, ...],
) -> tuple[Ticket, ...]:
    if len(history) < 20:
        return ((1, 2, 3, 4, 5, 6),)

    momentum_window = 5
    momentum = {number: 0.0 for number in range(1, _MAX_NUMBER + 1)}
    recent = history[-momentum_window:]
    for index, draw in enumerate(recent):
        weight = math.exp(index / momentum_window)
        for number in draw.numbers:
            momentum[number] += weight
    for number in history[-1].numbers:
        momentum[number] *= 1.2

    entropy_history = history[-150:]
    frequencies = Counter(
        number for draw in entropy_history for number in draw.numbers
    )
    target_frequency = len(entropy_history) * _PICK_COUNT / _MAX_NUMBER
    entropy = {
        number: 1.0 / (abs(frequencies.get(number, 0) - target_frequency) + 0.1)
        for number in range(1, _MAX_NUMBER + 1)
    }

    last_seen = {number: -1 for number in range(1, _MAX_NUMBER + 1)}
    for index, draw in enumerate(history):
        for number in draw.numbers:
            last_seen[number] = index
    current_index = len(history)
    lag_reversion: dict[int, float] = {}
    for number in range(1, _MAX_NUMBER + 1):
        lag = current_index - last_seen[number]
        if 6 <= lag <= 12:
            lag_reversion[number] = 1.5
        elif lag > 25:
            lag_reversion[number] = 1.25
        else:
            lag_reversion[number] = 1.0

    final_scores = [0.0] * (_MAX_NUMBER + 1)
    for number in range(1, _MAX_NUMBER + 1):
        final_scores[number] = (
            momentum[number] * 0.4
            + entropy[number] * 40.0 * 0.3
            + lag_reversion[number] * 0.2
        )
    ranked = [
        index + 1
        for index in _legacy_numpy_argsort(final_scores[1:])[::-1]
    ]
    return (
        _ticket(ranked[:_PICK_COUNT]),
    )


def _unpopular_scores() -> list[float]:
    scores = [1.0] * _MAX_NUMBER
    for number in range(1, _MAX_NUMBER + 1):
        base_score = 1.0
        if number <= 31:
            if number == 1:
                base_score *= 0.3
            elif number in (7, 8):
                base_score *= 0.35
            elif number == 9:
                base_score *= 0.4
            else:
                base_score *= 0.5
        else:
            base_score *= 1.5
        if number in (6, 16, 18, 26, 28, 36, 38, 46, 48):
            base_score *= 0.7
        if number in (10, 20, 30, 40):
            base_score *= 0.6
        if 42 <= number <= 49:
            base_score *= 1.8
        scores[number - 1] = base_score
    total = sum(scores)
    return [score / total for score in scores]


def _historical_frequency_recent_first(
    recent_first_history: tuple[LegacyHistoryDraw, ...],
) -> list[float]:
    frequency = [0.0] * _MAX_NUMBER
    for draw in recent_first_history[:50]:
        for number in draw.numbers:
            frequency[number - 1] += 1
    total = sum(frequency)
    if total > 0:
        return [value / total for value in frequency]
    return [1.0 / _MAX_NUMBER] * _MAX_NUMBER


def _social_wisdom(
    history: tuple[LegacyHistoryDraw, ...],
    *,
    seed_integer: int,
) -> tuple[Ticket, ...]:
    recent_first = tuple(reversed(history))
    unpopular = _unpopular_scores()
    historical_frequency = _historical_frequency_recent_first(recent_first)
    rng = LegacyNumpyRandomState(seed_integer % (2**32))
    tickets: list[Ticket] = []

    for index in range(4):
        noise = rng.normal(0, 0.1, _MAX_NUMBER)
        scores = [
            max(0.0, score + noise_item * (index + 1))
            for score, noise_item in zip(unpopular, noise, strict=True)
        ]
        total = sum(scores)
        scores = [score / total for score in scores]
        top_indices = _legacy_numpy_argsort(scores)[-_PICK_COUNT:]
        tickets.append(_ticket([int(item + 1) for item in top_indices]))

    for index in range(2):
        noise = rng.normal(0, 0.15, _MAX_NUMBER)
        scores = [
            max(
                0.0,
                0.65 * unpopular_item
                + 0.35 * frequency_item
                + noise_item * (index + 1),
            )
            for unpopular_item, frequency_item, noise_item in zip(
                unpopular,
                historical_frequency,
                noise,
                strict=True,
            )
        ]
        total = sum(scores)
        scores = [score / total for score in scores]
        top_indices = _legacy_numpy_argsort(scores)[-_PICK_COUNT:]
        tickets.append(_ticket([int(item + 1) for item in top_indices]))

    for index in range(2):
        noise = rng.normal(0, 0.2, _MAX_NUMBER)
        scores = [
            max(
                0.0,
                0.45 * unpopular_item
                + 0.55 * frequency_item
                + noise_item * (index + 1),
            )
            for unpopular_item, frequency_item, noise_item in zip(
                unpopular,
                historical_frequency,
                noise,
                strict=True,
            )
        ]
        total = sum(scores)
        scores = [score / total for score in scores]
        top_indices = _legacy_numpy_argsort(scores)[-_PICK_COUNT:]
        tickets.append(_ticket([int(item + 1) for item in top_indices]))
    return tuple(tickets)


def _mean(values: list[int] | list[float]) -> float:
    return sum(values) / len(values)


def _population_standard_deviation(values: list[int]) -> float:
    average = _mean(values)
    return math.sqrt(
        sum((value - average) ** 2 for value in values) / len(values)
    )


def _quick_ml_advanced(
    recent_first: tuple[LegacyHistoryDraw, ...],
) -> Ticket:
    scores: defaultdict[int, float] = defaultdict(float)
    for weight, period in zip(
        (0.4, 0.3, 0.2, 0.1),
        (10, 20, 30, 50),
        strict=True,
    ):
        frequency = Counter(
            number
            for draw in recent_first[: min(period, len(recent_first))]
            for number in draw.numbers
        )
        maximum = max(frequency.values()) if frequency else 1
        for number, count in frequency.items():
            scores[number] += count / maximum * weight * 15

    for number in range(1, _MAX_NUMBER + 1):
        missing = 0
        for draw in recent_first:
            if number in draw.numbers:
                break
            missing += 1
        if missing > 0:
            scores[number] += min(missing / 10, 2.5) * 12

    for number in range(1, _MAX_NUMBER + 1):
        appearances = [
            index
            for index, draw in enumerate(recent_first)
            if number in draw.numbers
        ]
        if len(appearances) >= 3:
            intervals = [
                appearances[index] - appearances[index + 1]
                for index in range(len(appearances) - 1)
            ]
            average_interval = _mean(intervals)
            standard_deviation = _population_standard_deviation(intervals)
            current_missing = appearances[0] if appearances else len(recent_first)
            if abs(current_missing - average_interval) < standard_deviation:
                scores[number] += 10

    recent_numbers = [
        number for draw in recent_first[:5] for number in draw.numbers
    ]
    for number in range(1, _MAX_NUMBER + 1):
        if number - 1 in recent_numbers or number + 1 in recent_numbers:
            scores[number] += 8

    recent_odd_counts = [
        sum(1 for number in draw.numbers if number % 2 == 1)
        for draw in recent_first[:20]
    ]
    average_odd = _mean(recent_odd_counts)
    for number in range(1, _MAX_NUMBER + 1):
        if (
            number % 2 == 1 and average_odd > _PICK_COUNT / 2
        ) or (
            number % 2 == 0 and average_odd < _PICK_COUNT / 2
        ):
            scores[number] += 8

    zone_size = _MAX_NUMBER // 3
    zone_counts = [0, 0, 0]
    for draw in recent_first[:10]:
        for number in draw.numbers:
            zone = min((number - 1) // zone_size, 2)
            zone_counts[zone] += 1
    average_zone = _mean(zone_counts)
    for number in range(1, _MAX_NUMBER + 1):
        zone = min((number - 1) // zone_size, 2)
        if zone_counts[zone] < average_zone:
            scores[number] += 8

    recent_sums = [sum(draw.numbers) for draw in recent_first[:20]]
    _mean(recent_sums)
    _population_standard_deviation(recent_sums)
    temporary_top = sorted(
        scores.items(),
        key=lambda item: item[1],
        reverse=True,
    )[: _PICK_COUNT * 2]
    for number, _score in temporary_top:
        scores[number] += 7

    recent_acs: list[int] = []
    for draw in recent_first[:20]:
        numbers = sorted(draw.numbers)
        differences = [
            numbers[index + 1] - numbers[index]
            for index in range(len(numbers) - 1)
        ]
        recent_acs.append(len(set(differences)))
    average_ac = _mean(recent_acs)
    if average_ac > _PICK_COUNT - 2:
        for number in range(1, _MAX_NUMBER + 1):
            if number % 7 == 0:
                scores[number] += 7

    recent_pattern = recent_first[:3]
    try:
        for index in range(3, len(recent_first) - 1):
            pattern = recent_first[index : index + 3]
            similarity = 0.0
            for position in range(3):
                intersection = len(
                    set(pattern[position].numbers)
                    & set(recent_pattern[position].numbers)
                )
                similarity += intersection / _PICK_COUNT
            similarity /= 3
            if similarity > 0.25:
                next_numbers = recent_first[index + 3].numbers
                for number in next_numbers:
                    scores[number] += similarity * 15
    except IndexError as exc:
        raise LegacyHistoryNativeSourceError(
            QUICK_ML_PATTERN_SLICE_REASON
        ) from exc

    for number in range(1, _MAX_NUMBER + 1):
        probability = 0.0
        for index, draw in enumerate(recent_first[:30]):
            if number in draw.numbers:
                probability += 0.9**index * 10
        scores[number] += probability

    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    return _ticket([number for number, _score in ranked[:_PICK_COUNT]])


def _quick_ml_hybrid(
    recent_first: tuple[LegacyHistoryDraw, ...],
) -> Ticket:
    frequency = Counter(
        number for draw in recent_first[:30] for number in draw.numbers
    )
    hot_numbers = [
        number for number, _count in frequency.most_common(int(_MAX_NUMBER * 0.3))
    ]
    warm_numbers = [
        number for number, _count in frequency.most_common(int(_MAX_NUMBER * 0.6))
    ][len(hot_numbers) :]

    missing_scores: dict[int, int] = {}
    for number in range(1, _MAX_NUMBER + 1):
        missing = 0
        for draw in recent_first:
            if number in draw.numbers:
                break
            missing += 1
        missing_scores[number] = missing
    cold_numbers = [
        number
        for number, _missing in sorted(
            missing_scores.items(),
            key=lambda item: item[1],
            reverse=True,
        )[: int(_MAX_NUMBER * 0.3)]
    ]

    hot_count = int(_PICK_COUNT * 0.5)
    warm_count = int(_PICK_COUNT * 0.3)
    cold_count = _PICK_COUNT - hot_count - warm_count
    predicted = (
        hot_numbers[:hot_count]
        + warm_numbers[:warm_count]
        + cold_numbers[:cold_count]
    )
    used = set(predicted)
    remaining = list(set(range(1, _MAX_NUMBER + 1)) - used)
    predicted.extend(remaining[: _PICK_COUNT - len(predicted)])
    return _ticket(predicted[:_PICK_COUNT])


def _quick_ml(
    history: tuple[LegacyHistoryDraw, ...],
) -> tuple[Ticket, ...]:
    if len(history) >= 5:
        # Frozen ``range(3, len(df) - 1)`` reaches a three-row positional
        # access on a two-row tail slice for every history of length >= 5.
        raise LegacyHistoryNativeSourceError(
            QUICK_ML_PATTERN_SLICE_REASON
        )
    recent_first = tuple(reversed(history))
    return (
        _quick_ml_advanced(recent_first),
        _quick_ml_hybrid(recent_first),
    )


def _exhaustive_audit(
    history: tuple[LegacyHistoryDraw, ...],
    *,
    seed_integer: int,
) -> tuple[Ticket, ...]:
    if len(history) < 50:
        raise LegacyHistoryNativeError("exhaustive audit requires 50 history draws")
    frequency = Counter(
        number for draw in history[-50:] for number in draw.numbers
    )
    ranked = sorted(
        range(1, _MAX_NUMBER + 1),
        key=lambda number: frequency.get(number, 0),
        reverse=True,
    )
    hot_pool = ranked[:15]
    cold_pool = ranked[-15:]
    rng = random.Random()
    rng.seed(seed_integer, version=2)
    hot = rng.sample(hot_pool, _PICK_COUNT)
    cold = rng.sample(cold_pool, _PICK_COUNT)
    used = set(hot) | set(cold)
    candidate_pool = [
        number for number in range(1, _MAX_NUMBER + 1) if number not in used
    ]
    orthogonal = rng.sample(candidate_pool, _PICK_COUNT)
    return (_ticket(hot), _ticket(cold), _ticket(orthogonal))


def generate_legacy_history_native_portfolio(
    request: LegacyHistoryNativeRequest,
) -> LegacyHistoryNativeResult:
    """Generate source-ordered native tickets from strictly prior history."""

    _validate_request(request)
    minimum_history = MINIMUM_HISTORY_BY_HISTORY_NATIVE_METHOD[
        request.legacy_method_id
    ]
    if len(request.history) < minimum_history:
        raise LegacyHistoryNativeError(
            f"method requires at least {minimum_history} history draws"
        )
    seed_material, seed_digest, seed_integer = _seed(request)
    if request.legacy_method_id == OPTIMIZED_ENSEMBLE_METHOD_ID:
        tickets = _optimized_ensemble(request.history)
    elif request.legacy_method_id == SOCIAL_WISDOM_METHOD_ID:
        tickets = _social_wisdom(request.history, seed_integer=seed_integer)
    elif request.legacy_method_id == QUICK_ML_METHOD_ID:
        tickets = _quick_ml(request.history)
    else:
        tickets = _exhaustive_audit(
            request.history,
            seed_integer=seed_integer,
        )
    expected_count = NATIVE_TICKET_COUNT_BY_HISTORY_NATIVE_METHOD[
        request.legacy_method_id
    ]
    if len(tickets) != expected_count:
        raise LegacyHistoryNativeSourceError(
            "FROZEN_SOURCE_NATIVE_TICKET_COUNT_CHANGED"
        )
    random_protocol = RANDOM_PROTOCOL_BY_HISTORY_NATIVE_METHOD[
        request.legacy_method_id
    ]
    return LegacyHistoryNativeResult(
        tickets=tickets,
        metadata=LegacyHistoryNativeMetadata(
            protocol=HISTORY_NATIVE_PROTOCOL,
            legacy_method_id=request.legacy_method_id,
            source_sha256=SOURCE_SHA256_BY_HISTORY_NATIVE_METHOD[
                request.legacy_method_id
            ],
            target_draw_number=request.target_draw_number,
            replicate_id=request.replicate_id,
            user_seed=request.user_seed,
            seed_material=seed_material,
            seed_digest=seed_digest,
            seed_integer=seed_integer,
            random_protocol=random_protocol,
            randomness_used=random_protocol != "NONE_DETERMINISTIC",
            history_draw_count=len(request.history),
            history_first_draw_number=request.history[0].draw_number,
            history_cutoff_draw_number=request.history[-1].draw_number,
            source_history_order=(
                "RECENT_FIRST"
                if request.legacy_method_id
                in (SOCIAL_WISDOM_METHOD_ID, QUICK_ML_METHOD_ID)
                else "OLDEST_FIRST"
            ),
            native_ticket_count=len(tickets),
            native_ticket_order="FROZEN_SOURCE_ENTRYPOINT_ORDER",
            native_duplicate_ticket_count=len(tickets) - len(set(tickets)),
            candidate_k=None,
            combination_count=None,
        ),
    )


__all__ = [
    "DEFAULT_HISTORY_NATIVE_USER_SEED",
    "EXHAUSTIVE_AUDIT_METHOD_ID",
    "EXHAUSTIVE_AUDIT_SOURCE_SHA256",
    "HISTORY_NATIVE_PROTOCOL",
    "MINIMUM_HISTORY_BY_HISTORY_NATIVE_METHOD",
    "NATIVE_TICKET_COUNT_BY_HISTORY_NATIVE_METHOD",
    "OPTIMIZED_ENSEMBLE_METHOD_ID",
    "OPTIMIZED_ENSEMBLE_SOURCE_SHA256",
    "QUICK_ML_METHOD_ID",
    "QUICK_ML_PATTERN_SLICE_REASON",
    "QUICK_ML_SOURCE_SHA256",
    "RANDOM_PROTOCOL_BY_HISTORY_NATIVE_METHOD",
    "SOCIAL_WISDOM_METHOD_ID",
    "SOCIAL_WISDOM_SOURCE_SHA256",
    "SOURCE_SHA256_BY_HISTORY_NATIVE_METHOD",
    "SUPPORTED_HISTORY_NATIVE_METHODS",
    "LegacyHistoryDraw",
    "LegacyHistoryNativeError",
    "LegacyHistoryNativeMetadata",
    "LegacyHistoryNativeRequest",
    "LegacyHistoryNativeResult",
    "LegacyHistoryNativeSourceError",
    "LegacyNumpyRandomState",
    "generate_legacy_history_native_portfolio",
    "legacy_numpy_argsort",
]
