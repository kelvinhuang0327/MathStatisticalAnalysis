"""Target-native port of the frozen BIG_LOTTO Anti-Consensus donor.

The donor is ``lottery_api/models/anti_consensus_strategy.py`` at legacy
commit ``49a25effa62fc24f40789c16be6f11bdfb41a4a9`` (blob
``09406d20d8aeb96c832928234a794a4ed9c23406``, SHA-256
``a454ddd26cef405db5e9b4b4f5d2c0f5e1df14d291bbd0505d45be36a2cecc80``).
Its complete candidate construction, score, retry, RNG-call order, stable
score ordering, and six-ticket cardinality are retained by
``legacy_history_native_portfolios_wave2._anti_consensus``.

The donor used NumPy's module-global, unseeded ``RandomState``. Its historical
pre-state was not retained, so one historical ticket set cannot be replayed.
That state selected samples only: it did not choose branches, parameters,
populations, retry counts, fallbacks, or ticket count. This adapter therefore
keeps the donor's legacy NumPy MT19937 permutation semantics behind an
execution-local seed seam. Seed zero is the explicit target default used by
direct replay callers; production portfolio generation replaces it through
``with_seed``. Neither path mutates module-global RNG state.

The donor accepted history but did not read it for number selection. Target
history is still validated and gated to one strictly prior causal row so the
retained input contract fails closed without introducing future data.
"""

from __future__ import annotations

from typing import Protocol

from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters.base import (
    CausalDrawRow,
    InvalidOutput,
    PortfolioBetAdapter,
)

_STRATEGY_ID = "legacy_biglotto__anti_consensus_strategy__a454ddd26cef"
_MIN_NUMBER = 1
_MAX_NUMBER = 49
_PICK_COUNT = 6
_NATIVE_TICKET_COUNT = 6
_DEFAULT_TARGET_SEED = 0
_MAX_RANDOM_STATE_SEED = 2**32 - 1


class _ChoiceWithoutReplacementRng(Protocol):
    """The donor's only stochastic operation, injected in execution order."""

    def choice_without_replacement(
        self,
        values: list[int],
        size: int,
    ) -> list[int]: ...


class _LegacyNumpyRandomState:
    """Minimal NumPy ``RandomState`` MT19937 permutation compatibility.

    This is the uniform, no-replacement subset of the retained wave-2
    reconstruction's ``LegacyNumpyRandomState``. ``RandomState.choice`` with
    ``replace=False`` and no probability vector permutes positional indices
    and takes the requested prefix; the implementation below preserves that
    exact operation rather than translating it to ``random.sample``.
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
    ) -> list[int]:
        if size < 0 or size > len(values):
            raise ValueError("sample size is outside the population")
        indices = self.permutation(list(range(len(values))))[:size]
        return [values[index] for index in indices]


def _ticket(numbers: list[int]) -> tuple[int, ...]:
    values = tuple(sorted(numbers))
    if (
        len(values) != _PICK_COUNT
        or len(set(values)) != _PICK_COUNT
        or any(
            type(number) is not int or not _MIN_NUMBER <= number <= _MAX_NUMBER for number in values
        )
    ):
        raise InvalidOutput(f"{_STRATEGY_ID}: Anti-Consensus ticket is not a legal 6-of-49 set")
    return values


def _is_arithmetic_sequence(numbers: list[int]) -> bool:
    if len(numbers) < 3:
        return False
    differences = [numbers[index + 1] - numbers[index] for index in range(len(numbers) - 1)]
    return len(set(differences)) == 1


def _anti_consensus_score(numbers: list[int]) -> float:
    """Donor consensus score; lower scores are more anti-consensus."""

    birthday_count = sum(number <= 31 for number in numbers)
    score = birthday_count / len(numbers) * 50
    score += sum(number in {6, 8, 9, 18, 28, 38} for number in numbers) * 10
    score -= sum(number in {4, 13, 14} for number in numbers) * 5
    sorted_numbers = sorted(numbers)
    score += (
        sum(
            sorted_numbers[index + 1] - sorted_numbers[index] == 1
            for index in range(len(sorted_numbers) - 1)
        )
        * 15
    )
    symmetry_count = sum(50 - number in numbers for number in numbers)
    score += symmetry_count / 2 * 10
    if _is_arithmetic_sequence(sorted_numbers):
        score += 30
    tails = [number % 10 for number in numbers]
    score += (len(tails) - len(set(tails))) * 8
    odd_count = sum(number % 2 == 1 for number in numbers)
    if odd_count == 0 or odd_count == len(numbers):
        score += 20
    if sum(numbers) % 10 == 0:
        score += 15
    return score


def _has_common_patterns(numbers: list[int]) -> bool:
    sorted_numbers = sorted(numbers)
    if any(
        sorted_numbers[index + 1] - sorted_numbers[index] == 1
        for index in range(len(sorted_numbers) - 1)
    ):
        return True
    if _is_arithmetic_sequence(sorted_numbers):
        return True
    odd_count = sum(number % 2 == 1 for number in numbers)
    return odd_count == 0 or odd_count == len(numbers)


def _anti_consensus_tickets(
    rng: _ChoiceWithoutReplacementRng,
) -> tuple[tuple[int, ...], ...]:
    """Execute every donor RNG call in its retained order."""

    results: list[tuple[float, tuple[int, ...]]] = []
    large_numbers = list(range(32, _MAX_NUMBER + 1))
    for _ in range(3):
        selected = rng.choice_without_replacement(large_numbers, _PICK_COUNT)
        results.append((_anti_consensus_score(selected), _ticket(selected)))

    unlucky_heavy = list({4, 13, 14})
    remaining = [
        number for number in range(_MIN_NUMBER, _MAX_NUMBER + 1) if number not in unlucky_heavy
    ]
    for _ in range(3):
        selected = rng.choice_without_replacement(unlucky_heavy, 2)
        needed = _PICK_COUNT - len(selected)
        candidates = [number for number in remaining if number >= 32]
        if len(candidates) < needed:
            candidates = remaining
        selected.extend(rng.choice_without_replacement(candidates, needed))
        results.append((_anti_consensus_score(selected), _ticket(selected)))

    for _ in range(3):
        best_score = float("inf")
        best_numbers: list[int] | None = None
        for _attempt in range(1000):
            selected = rng.choice_without_replacement(list(range(1, 32)), 2)
            selected.extend(
                rng.choice_without_replacement(
                    list(range(32, _MAX_NUMBER + 1)),
                    4,
                )
            )
            consensus = _anti_consensus_score(selected)
            if _has_common_patterns(selected):
                continue
            if consensus < best_score:
                best_score = consensus
                best_numbers = selected
        if best_numbers is not None:
            results.append((best_score, _ticket(best_numbers)))

    results.sort(key=lambda item: item[0])
    return tuple(ticket for _score, ticket in results[:_NATIVE_TICKET_COUNT])


class BigLottoAntiConsensusStrategyAdapter(PortfolioBetAdapter):
    """Seeded, exact-cardinality six-ticket Anti-Consensus portfolio."""

    strategy_id = _STRATEGY_ID
    strategy_name = "大樂透 Anti-Consensus 6注"
    strategy_version = "v0.1"
    min_history = 1
    supported_lottery_types = (LotteryType.BIG_LOTTO,)
    native_ticket_count = _NATIVE_TICKET_COUNT

    def __init__(self, *, rng_seed: int = _DEFAULT_TARGET_SEED) -> None:
        if type(rng_seed) is not int or not 0 <= rng_seed <= _MAX_RANDOM_STATE_SEED:
            raise InvalidOutput(
                f"{self.strategy_id}: rng_seed must be an integer in [0..{_MAX_RANDOM_STATE_SEED}]"
            )
        self._rng_seed = rng_seed

    def with_seed(self, seed: int) -> BigLottoAntiConsensusStrategyAdapter:
        """Return a call-local adapter configured with one explicit seed."""

        return BigLottoAntiConsensusStrategyAdapter(rng_seed=seed)

    def _predict_all(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[tuple[int, ...], ...]:
        del history, lottery_type
        rng = _LegacyNumpyRandomState(self._rng_seed)
        return _anti_consensus_tickets(rng)


__all__ = ["BigLottoAntiConsensusStrategyAdapter"]
