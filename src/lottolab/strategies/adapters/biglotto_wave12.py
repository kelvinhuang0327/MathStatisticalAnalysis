"""BigLotto native-strategy wave 12: thin ports of three frozen legacy
BACKTESTED methods (donor commit ``49a25effa62fc24f40789c16be6f11bdfb41a4a9``,
the same frozen snapshot as waves 1-11). No algorithm was changed, tuned, or
"improved" during the port.

* ``legacy_biglotto__social_wisdom_predictor__a00829b5d875`` -- donor
  ``lottery_api/models/social_wisdom_predictor.py``,
  ``SocialWisdomPredictor.generate_8_bets``. Eight tickets: a fixed
  "unpopular score" table (birthday numbers 1-31 penalized, 32-49 favored,
  extra penalties for lucky/round numbers, extra bonus for 42-49) blended
  with the trailing-50-draw historical frequency (recent-first), perturbed
  by four independent NumPy ``RandomState`` Gaussian draws per ticket
  (0.65/0.35 and 0.45/0.55 unpopular/frequency blends for the last four
  tickets, pure unpopular score plus noise for the first four), each ticket
  taking the top-6 by NumPy's legacy indirect-argsort order. Never closes:
  every causal history of length >= 1 produces exactly 8 tickets.
* ``legacy_biglotto__negative_selection_biglotto__98f860c52cc2`` -- donor
  ``lottery_api/models/negative_selection_biglotto.py``,
  ``EnhancedNegativeSelection.predict(num_bets=4)``. Up to 8 tickets: a base
  negative-selection pass (exclude numbers hot in the trailing 10 draws or
  cold across the trailing 100, weighted NumPy ``RandomState`` sampling
  without replacement over 400 candidates, zone/parity/sum/run structural
  filtering, greedy pairwise-diversity selection) run twice against the
  *same* RNG stream -- 4 "base" tickets, then 2 "enhanced-negative" tickets
  from a second, smaller (200-candidate) pass -- followed by up to 2 more
  deterministic co-occurrence-cluster tickets appended only if not already
  present. Native ticket count is data-dependent (the donor's own
  deduplication can drop the enhanced tail); ``native_ticket_count`` below
  is pinned at the donor's nominal maximum of 8, so a rarer under-count run
  closes via the base adapter's own strict count check (``InvalidOutput``)
  rather than an invented pad -- the same treatment wave 9's cluster-cover
  short bets receive from ``_ticket``.
* ``legacy_biglotto__quick_ml_predict__8b7ba0b52e2d`` -- donor
  ``tools/quick_ml_predict.py``, ``QuickMLPredictor.predict_advanced_ensemble``
  plus ``predict_smart_hybrid``. Two tickets, recent-first history. The
  donor's own "historical pattern matching" component
  (``for i in range(3, len(df) - 1): pattern = df.iloc[i:i+3]``) performs a
  three-row positional access against a slice that is only two rows wide on
  its final iteration for every history of length >= 5 -- an ``IndexError``
  in the original pandas source, reproduced here as a deterministic frozen
  closure raised *before* any computation for every history >= 5 draws.
  This is a genuine, audited, frozen-source defect (the catalog's own
  status_reason records only 4 causal executions ever reached ``OK``) --
  preserved verbatim per this wave's contract, never "fixed" or removed.

Donor-exact logic for all three is re-derived inline here rather than
imported from ``lottolab.application.legacy_history_native_portfolios`` /
``lottolab.application.legacy_history_native_portfolios_wave3`` (the
frozen-source reference oracles these three were audited against, per
``strategies/data/biglotto_full_strategy_catalog_v1.json``): ``strategies``
importing ``application`` is a structural layer violation
``tests/architecture/test_dependency_rules.py`` forbids, exactly the same
boundary wave 9's and wave 11's docstrings document for their own inline
re-derivations. ``LegacyNumpyRandomState`` / ``_legacy_numpy_argsort`` below
are byte-identical re-transcriptions of the reference oracle's own classes
of the same name (NumPy legacy ``RandomState`` MT19937 + Gaussian polar
method + argsort introsort) -- copied, not imported, for the same reason.

**Seed protocol.** Social-wisdom and quick-ml are frozen-seeded via a
SHA-256 digest of ``protocol | method_id | source_sha256 |
target_draw_number | replicate_id | user_seed`` (the reference oracle's own
``_seed`` function, reproduced verbatim below via ``_seed_integer``) using
``protocol="legacy_history_native/v1"`` and
``user_seed="biglotto-full-universe-history-native-v1"`` -- the exact
constants wave 11's own history-native exhaustive-audit port reuses from
the same reference oracle file, since both are "audited against" that one
oracle. Negative-selection reuses its own oracle's
``protocol="legacy_history_native_wave3/v1"`` and
``user_seed="biglotto-full-universe-history-native-wave3-v1"`` instead. All
three feed the resulting seed integer into NumPy's legacy ``RandomState``
(social-wisdom, negative-selection) or need no randomness at all
(quick-ml is ``NONE_DETERMINISTIC`` per the oracle's own protocol map, so no
seed is derived for it). The oracles' request objects accept an explicit
``target_draw_number`` (the future draw being predicted); this framework's
``PortfolioBetAdapter._predict_all(history, lottery_type)`` contract has no
such slot, so ``_target_after_causal_cutoff`` reproduces wave 8/11's
identical-purpose helper to synthesize a deterministic request identity
from the causal history's own last draw -- never the wall clock, a random
draw, or any I/O -- so the seed stays a pure function of ``history`` alone,
replicate_id fixed at ``0`` and user_seed fixed at each oracle's own
published default.
"""

from __future__ import annotations

import hashlib
import math
from collections import Counter, defaultdict
from itertools import combinations

from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters.base import CausalDrawRow, PortfolioBetAdapter

_MIN_NUMBER = 1
_MAX_NUMBER = 49
_PICK_COUNT = 6
_REPLICATE_ID = 0

_HISTORY_NATIVE_PROTOCOL = "legacy_history_native/v1"
_HISTORY_NATIVE_DEFAULT_USER_SEED = "biglotto-full-universe-history-native-v1"
_SOCIAL_WISDOM_METHOD_ID = "lottery_api/models/social_wisdom_predictor.py"
_SOCIAL_WISDOM_SOURCE_SHA256 = "a00829b5d875cb8202c3bbd90ad7202fa6b95f568e3e8d821a6cdbffe6a95e3b"
_QUICK_ML_METHOD_ID = "tools/quick_ml_predict.py"
_QUICK_ML_SOURCE_SHA256 = "8b7ba0b52e2dfcb7bd39997be9dbfab90a81f6e44c3fcf269ac5c9ddaa266d80"
_QUICK_ML_PATTERN_SLICE_REASON = "FROZEN_SOURCE_PATTERN_SLICE_INDEX_ERROR"

_HISTORY_NATIVE_WAVE3_PROTOCOL = "legacy_history_native_wave3/v1"
_HISTORY_NATIVE_WAVE3_DEFAULT_USER_SEED = "biglotto-full-universe-history-native-wave3-v1"
_NEGATIVE_SELECTION_METHOD_ID = "lottery_api/models/negative_selection_biglotto.py"
_NEGATIVE_SELECTION_SOURCE_SHA256 = (
    "98f860c52cc2f01552690b7903679961a263909fae844896860442909dca1294"
)


class Wave12FrozenSourceError(ValueError):
    """A frozen wave-12 donor deterministically closes for this causal history."""

    def __init__(self, reason_code: str) -> None:
        super().__init__(reason_code)
        self.reason_code = reason_code


def _ticket(numbers: list[int]) -> tuple[int, ...]:
    values = tuple(sorted(numbers))
    if (
        len(values) != _PICK_COUNT
        or len(set(values)) != _PICK_COUNT
        or any(
            type(number) is not int or not _MIN_NUMBER <= number <= _MAX_NUMBER for number in values
        )
    ):
        raise Wave12FrozenSourceError("FROZEN_SOURCE_INVALID_TICKET")
    return values


def _target_after_causal_cutoff(history: tuple[CausalDrawRow, ...]) -> str:
    """Return a deterministic request identity absent from the causal history.

    See the module docstring's "Seed protocol" section: the frozen donors'
    seed material is keyed off an externally supplied ``target_draw_number``
    this framework's adapter contract has no slot for, so this synthesizes
    one from the causal history's own last draw, exactly reproducing wave
    8/11's ``_target_after_causal_cutoff`` pattern.
    """
    draw_ids = {row.draw for row in history}
    target = f"{history[-1].draw}:lottolab-wave12-next-target"
    while target in draw_ids:
        target = f"{target}:next"
    return target


def _seed_integer(
    *,
    protocol: str,
    method_id: str,
    source_sha256: str,
    target_draw_number: str,
    user_seed: str,
) -> int:
    """Re-derive the frozen SHA-256 seed-material protocol inline.

    Byte-identical to the reference oracles' own ``_seed`` functions
    (``legacy_history_native_portfolios.py`` /
    ``legacy_history_native_portfolios_wave3.py``), copied rather than
    imported per the module docstring's layer-boundary note.
    """
    material = "|".join(
        (protocol, method_id, source_sha256, target_draw_number, str(_REPLICATE_ID), user_seed)
    )
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
    return int(digest, 16)


class LegacyNumpyRandomState:
    """Minimal NumPy ``RandomState`` MT19937 + legacy Gaussian compatibility.

    Byte-identical re-transcription of the reference oracle's own class of
    the same name in ``legacy_history_native_portfolios.py`` -- copied, not
    imported, per the module docstring's layer-boundary note.
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
        self._has_gauss = False
        self._cached_gauss = 0.0

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

    def _standard_normal(self) -> float:
        if self._has_gauss:
            self._has_gauss = False
            return self._cached_gauss
        while True:
            first = 2.0 * self._double() - 1.0
            second = 2.0 * self._double() - 1.0
            radius_squared = first * first + second * second
            if radius_squared < 1.0 and radius_squared != 0.0:
                scale = math.sqrt(-2.0 * math.log(radius_squared) / radius_squared)
                self._cached_gauss = first * scale
                self._has_gauss = True
                return second * scale

    def normal(self, location: float, scale: float, size: int) -> list[float]:
        return [location + scale * self._standard_normal() for _ in range(size)]

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


def _legacy_numpy_argsort(values: list[float]) -> list[int]:
    """Port NumPy's legacy float64 indirect introsort for small arrays.

    Byte-identical re-transcription of the reference oracle's own
    ``_legacy_numpy_argsort`` -- copied, not imported, per the module
    docstring's layer-boundary note.
    """
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
                indices[middle], indices[lower] = indices[lower], indices[middle]
            if values[indices[upper]] < values[indices[middle]]:
                indices[upper], indices[middle] = indices[middle], indices[upper]
            if values[indices[middle]] < values[indices[lower]]:
                indices[middle], indices[lower] = indices[lower], indices[middle]
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
            indices[left], indices[pivot_slot] = indices[pivot_slot], indices[left]
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
            while cursor > lower and values[value_index] < values[indices[previous]]:
                indices[cursor] = indices[previous]
                cursor -= 1
                previous -= 1
            indices[cursor] = value_index
        if not stack:
            break
        lower, upper, depth = stack.pop()
    return indices


# ─── legacy_biglotto__social_wisdom_predictor__a00829b5d875 ───────────────


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


def _historical_frequency_recent_first(recent_first: tuple[CausalDrawRow, ...]) -> list[float]:
    frequency = [0.0] * _MAX_NUMBER
    for draw in recent_first[:50]:
        for number in draw.numbers:
            frequency[number - 1] += 1
    total = sum(frequency)
    if total > 0:
        return [value / total for value in frequency]
    return [1.0 / _MAX_NUMBER] * _MAX_NUMBER


def _social_wisdom(
    history: tuple[CausalDrawRow, ...],
    *,
    seed_integer: int,
) -> tuple[tuple[int, ...], ...]:
    recent_first = tuple(reversed(history))
    unpopular = _unpopular_scores()
    historical_frequency = _historical_frequency_recent_first(recent_first)
    rng = LegacyNumpyRandomState(seed_integer % (2**32))
    tickets: list[tuple[int, ...]] = []

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
            max(0.0, 0.65 * unpopular_item + 0.35 * frequency_item + noise_item * (index + 1))
            for unpopular_item, frequency_item, noise_item in zip(
                unpopular, historical_frequency, noise, strict=True
            )
        ]
        total = sum(scores)
        scores = [score / total for score in scores]
        top_indices = _legacy_numpy_argsort(scores)[-_PICK_COUNT:]
        tickets.append(_ticket([int(item + 1) for item in top_indices]))

    for index in range(2):
        noise = rng.normal(0, 0.2, _MAX_NUMBER)
        scores = [
            max(0.0, 0.45 * unpopular_item + 0.55 * frequency_item + noise_item * (index + 1))
            for unpopular_item, frequency_item, noise_item in zip(
                unpopular, historical_frequency, noise, strict=True
            )
        ]
        total = sum(scores)
        scores = [score / total for score in scores]
        top_indices = _legacy_numpy_argsort(scores)[-_PICK_COUNT:]
        tickets.append(_ticket([int(item + 1) for item in top_indices]))
    return tuple(tickets)


# ─── legacy_biglotto__quick_ml_predict__8b7ba0b52e2d ──────────────────────


def _mean(values: list[int] | list[float]) -> float:
    return sum(values) / len(values)


def _population_standard_deviation(values: list[int]) -> float:
    average = _mean(values)
    return math.sqrt(sum((value - average) ** 2 for value in values) / len(values))


def _quick_ml_advanced(recent_first: tuple[CausalDrawRow, ...]) -> tuple[int, ...]:
    scores: defaultdict[int, float] = defaultdict(float)
    for weight, period in zip((0.4, 0.3, 0.2, 0.1), (10, 20, 30, 50), strict=True):
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
        appearances = [index for index, draw in enumerate(recent_first) if number in draw.numbers]
        if len(appearances) >= 3:
            intervals = [
                appearances[index] - appearances[index + 1] for index in range(len(appearances) - 1)
            ]
            average_interval = _mean(intervals)
            standard_deviation = _population_standard_deviation(intervals)
            current_missing = appearances[0] if appearances else len(recent_first)
            if abs(current_missing - average_interval) < standard_deviation:
                scores[number] += 10

    recent_numbers = [number for draw in recent_first[:5] for number in draw.numbers]
    for number in range(1, _MAX_NUMBER + 1):
        if number - 1 in recent_numbers or number + 1 in recent_numbers:
            scores[number] += 8

    recent_odd_counts = [
        sum(1 for number in draw.numbers if number % 2 == 1) for draw in recent_first[:20]
    ]
    average_odd = _mean(recent_odd_counts)
    for number in range(1, _MAX_NUMBER + 1):
        if (number % 2 == 1 and average_odd > _PICK_COUNT / 2) or (
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

    temporary_top = sorted(scores.items(), key=lambda item: item[1], reverse=True)[
        : _PICK_COUNT * 2
    ]
    for number, _score in temporary_top:
        scores[number] += 7

    recent_acs: list[int] = []
    for draw in recent_first[:20]:
        numbers = sorted(draw.numbers)
        differences = [numbers[index + 1] - numbers[index] for index in range(len(numbers) - 1)]
        recent_acs.append(len(set(differences)))
    average_ac = _mean(recent_acs)
    if average_ac > _PICK_COUNT - 2:
        for number in range(1, _MAX_NUMBER + 1):
            if number % 7 == 0:
                scores[number] += 7

    recent_pattern = recent_first[:3]
    for index in range(3, len(recent_first) - 1):
        pattern = recent_first[index : index + 3]
        similarity = 0.0
        for position in range(3):
            intersection = len(
                set(pattern[position].numbers) & set(recent_pattern[position].numbers)
            )
            similarity += intersection / _PICK_COUNT
        similarity /= 3
        if similarity > 0.25:
            next_numbers = recent_first[index + 3].numbers
            for number in next_numbers:
                scores[number] += similarity * 15

    for number in range(1, _MAX_NUMBER + 1):
        probability = 0.0
        for index, draw in enumerate(recent_first[:30]):
            if number in draw.numbers:
                probability += 0.9**index * 10
        scores[number] += probability

    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    return _ticket([number for number, _score in ranked[:_PICK_COUNT]])


def _quick_ml_hybrid(recent_first: tuple[CausalDrawRow, ...]) -> tuple[int, ...]:
    frequency = Counter(number for draw in recent_first[:30] for number in draw.numbers)
    hot_numbers = [number for number, _count in frequency.most_common(int(_MAX_NUMBER * 0.3))]
    warm_numbers = [number for number, _count in frequency.most_common(int(_MAX_NUMBER * 0.6))][
        len(hot_numbers) :
    ]

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
            missing_scores.items(), key=lambda item: item[1], reverse=True
        )[: int(_MAX_NUMBER * 0.3)]
    ]

    hot_count = int(_PICK_COUNT * 0.5)
    warm_count = int(_PICK_COUNT * 0.3)
    cold_count = _PICK_COUNT - hot_count - warm_count
    predicted = hot_numbers[:hot_count] + warm_numbers[:warm_count] + cold_numbers[:cold_count]
    used = set(predicted)
    remaining = list(set(range(1, _MAX_NUMBER + 1)) - used)
    predicted.extend(remaining[: _PICK_COUNT - len(predicted)])
    return _ticket(predicted[:_PICK_COUNT])


def _quick_ml(history: tuple[CausalDrawRow, ...]) -> tuple[tuple[int, ...], ...]:
    if len(history) >= 5:
        # Frozen ``range(3, len(df) - 1)`` reaches a three-row positional
        # access on a two-row tail slice for every history of length >= 5
        # (see module docstring). Preserved verbatim, never "fixed".
        raise Wave12FrozenSourceError(_QUICK_ML_PATTERN_SLICE_REASON)
    recent_first = tuple(reversed(history))
    return (_quick_ml_advanced(recent_first), _quick_ml_hybrid(recent_first))


# ─── legacy_biglotto__negative_selection_biglotto__98f860c52cc2 ───────────


def _negative_candidate_pool(history: tuple[CausalDrawRow, ...]) -> set[int]:
    all_numbers = set(range(_MIN_NUMBER, _MAX_NUMBER + 1))
    recent_frequency = Counter(number for draw in history[-10:] for number in draw.numbers)
    long_frequency = Counter(number for draw in history[-100:] for number in draw.numbers)
    exclude_hot = {number for number, count in recent_frequency.items() if count >= 3}
    exclude_cold = {number for number in all_numbers if long_frequency.get(number, 0) < 3}
    candidate_pool = all_numbers - exclude_hot - exclude_cold
    if len(candidate_pool) < 20:
        candidate_pool = all_numbers - exclude_hot
    return candidate_pool


def _negative_generate_candidates(
    pool: set[int],
    history: tuple[CausalDrawRow, ...],
    num_candidates: int,
    numpy_rng: LegacyNumpyRandomState,
) -> list[list[int]]:
    pool_list = list(pool)
    long_frequency = Counter(number for draw in history[-100:] for number in draw.numbers)
    average_frequency = sum(long_frequency.values()) / len(long_frequency) if long_frequency else 1
    weights = {
        number: 1.0
        + max(0.0, (average_frequency - long_frequency.get(number, 0)) / average_frequency * 0.5)
        for number in pool_list
    }
    total_weight = sum(weights.values())
    probabilities = [weights[number] / total_weight for number in pool_list]
    return [
        sorted(
            numpy_rng.choice_without_replacement(
                pool_list, _PICK_COUNT, probabilities=probabilities
            )
        )
        for _ in range(num_candidates)
    ]


def _negative_structural_filter(candidates: list[list[int]]) -> list[list[int]]:
    filtered: list[list[int]] = []
    for numbers in candidates:
        zones = [0, 0, 0]
        for number in numbers:
            if number <= 16:
                zones[0] += 1
            elif number <= 33:
                zones[1] += 1
            else:
                zones[2] += 1
        if max(zones) >= 5 or min(zones) == 0:
            continue
        odd_count = sum(number % 2 == 1 for number in numbers)
        if odd_count <= 1 or odd_count >= 5:
            continue
        total = sum(numbers)
        if total < 100 or total > 200:
            continue
        maximum_consecutive = 1
        current_consecutive = 1
        for index in range(1, len(numbers)):
            if numbers[index] - numbers[index - 1] == 1:
                current_consecutive += 1
                maximum_consecutive = max(maximum_consecutive, current_consecutive)
            else:
                current_consecutive = 1
        if maximum_consecutive >= 4:
            continue
        filtered.append(numbers)
    if len(filtered) < 10:
        return candidates[:100]
    return filtered


def _negative_select_best(candidates: list[list[int]], num_bets: int) -> list[list[int]]:
    if len(candidates) <= num_bets:
        return candidates
    selected = [candidates[0]]
    for _ in range(num_bets - 1):
        best_candidate: list[int] | None = None
        best_diversity = -1
        for candidate in candidates:
            if candidate in selected:
                continue
            minimum_difference = min(len(set(candidate) - set(existing)) for existing in selected)
            if minimum_difference > best_diversity:
                best_diversity = minimum_difference
                best_candidate = candidate
        if best_candidate is not None:
            selected.append(best_candidate)
    return selected


def _negative_base(
    history: tuple[CausalDrawRow, ...],
    num_bets: int,
    numpy_rng: LegacyNumpyRandomState,
) -> list[list[int]]:
    pool = _negative_candidate_pool(history)
    candidates = _negative_generate_candidates(pool, history, num_bets * 100, numpy_rng)
    return _negative_select_best(_negative_structural_filter(candidates), num_bets)


def _negative_cluster(history: tuple[CausalDrawRow, ...], num_bets: int) -> list[list[int]]:
    cooccurrence: Counter[tuple[int, int]] = Counter()
    for draw in history[-100:]:
        cooccurrence.update(combinations(sorted(draw.numbers), 2))
    number_scores: Counter[int] = Counter()
    for (first, second), count in cooccurrence.items():
        number_scores[first] += count
        number_scores[second] += count
    centers = [number for number, _count in number_scores.most_common(num_bets)]
    predictions: list[list[int]] = []
    used: set[tuple[int, ...]] = set()
    for anchor in centers:
        candidates: Counter[int] = Counter()
        for (first, second), count in cooccurrence.items():
            if first == anchor:
                candidates[second] += count
            elif second == anchor:
                candidates[first] += count
        selected = [anchor]
        for number, _count in candidates.most_common(_PICK_COUNT - 1):
            if number not in selected:
                selected.append(number)
            if len(selected) >= _PICK_COUNT:
                break
        while len(selected) < _PICK_COUNT:
            for number in range(_MIN_NUMBER, _MAX_NUMBER + 1):
                if number not in selected:
                    selected.append(number)
                    break
        prediction = sorted(selected[:_PICK_COUNT])
        identity = tuple(prediction)
        if identity not in used:
            predictions.append(prediction)
            used.add(identity)
    return predictions[:num_bets]


def _negative_selection(
    history: tuple[CausalDrawRow, ...],
    *,
    seed_integer: int,
) -> tuple[tuple[int, ...], ...]:
    numpy_rng = LegacyNumpyRandomState(seed_integer % (2**32))
    base = _negative_base(history, 4, numpy_rng)
    enhanced_negative = _negative_base(history, 2, numpy_rng)
    enhanced = list(enhanced_negative)
    for prediction in _negative_cluster(history, 2):
        if prediction not in enhanced:
            enhanced.append(prediction)
    return tuple(_ticket(numbers) for numbers in [*base, *enhanced[:4]])


# ─── Adapters ───────────────────────────────────────────────────────────


class BigLottoSocialWisdomPredictorAdapter(PortfolioBetAdapter):
    """History-native "avoid the crowd" 8-ticket generator; never closes for
    any causal history of length >= 1 (see module docstring)."""

    strategy_id = "legacy_biglotto__social_wisdom_predictor__a00829b5d875"
    strategy_name = "大樂透社群智慧預測器（8注）"  # noqa: RUF001
    strategy_version = "v0.1"
    min_history = 1
    supported_lottery_types = (LotteryType.BIG_LOTTO,)
    native_ticket_count = 8

    def _predict_all(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[tuple[int, ...], ...]:
        seed_integer = _seed_integer(
            protocol=_HISTORY_NATIVE_PROTOCOL,
            method_id=_SOCIAL_WISDOM_METHOD_ID,
            source_sha256=_SOCIAL_WISDOM_SOURCE_SHA256,
            target_draw_number=_target_after_causal_cutoff(history),
            user_seed=_HISTORY_NATIVE_DEFAULT_USER_SEED,
        )
        return _social_wisdom(history, seed_integer=seed_integer)


class BigLottoNegativeSelectionBiglottoAdapter(PortfolioBetAdapter):
    """History-native negative-selection + co-occurrence-cluster generator;
    nominal 8 tickets (4 base + up to 4 enhanced), data-dependent short runs
    close via the base adapter's own strict ticket-count check (see module
    docstring)."""

    strategy_id = "legacy_biglotto__negative_selection_biglotto__98f860c52cc2"
    strategy_name = "大樂透負向篩選（增強版）"  # noqa: RUF001
    strategy_version = "v0.1"
    min_history = 1
    supported_lottery_types = (LotteryType.BIG_LOTTO,)
    native_ticket_count = 8

    def _predict_all(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[tuple[int, ...], ...]:
        seed_integer = _seed_integer(
            protocol=_HISTORY_NATIVE_WAVE3_PROTOCOL,
            method_id=_NEGATIVE_SELECTION_METHOD_ID,
            source_sha256=_NEGATIVE_SELECTION_SOURCE_SHA256,
            target_draw_number=_target_after_causal_cutoff(history),
            user_seed=_HISTORY_NATIVE_WAVE3_DEFAULT_USER_SEED,
        )
        return _negative_selection(history, seed_integer=seed_integer)


class BigLottoQuickMlPredictAdapter(PortfolioBetAdapter):
    """History-native 2-ticket ensemble/hybrid generator; deterministically
    closes (frozen source pattern-slice ``IndexError``) for every causal
    history of length >= 5 (see module docstring). No randomness: the
    reference oracle's own protocol map records this method as
    ``NONE_DETERMINISTIC``."""

    strategy_id = "legacy_biglotto__quick_ml_predict__8b7ba0b52e2d"
    strategy_name = "大樂透快速機器學習預測（2注）"  # noqa: RUF001
    strategy_version = "v0.1"
    min_history = 1
    supported_lottery_types = (LotteryType.BIG_LOTTO,)
    native_ticket_count = 2

    def _predict_all(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[tuple[int, ...], ...]:
        return _quick_ml(history)


__all__ = [
    "BigLottoNegativeSelectionBiglottoAdapter",
    "BigLottoQuickMlPredictAdapter",
    "BigLottoSocialWisdomPredictorAdapter",
    "Wave12FrozenSourceError",
]
