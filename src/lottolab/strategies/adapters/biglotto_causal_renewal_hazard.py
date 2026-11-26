"""Native BIG_LOTTO adapters for the fixed Renewal Hazard donor algorithm.

These are new implementation identities. Their strategy_version preserves the
method label only; it does not claim parity with any historical execution.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import ClassVar

from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters.base import CausalDrawRow, PortfolioBetAdapter

_HISTORY_WINDOW = 750
_NUMBER_COUNT = 49
_TICKET_SIZE = 6
_P0 = Fraction(6, 49)
_STRATEGY_VERSION = "FIXED_DISCRETE_RENEWAL_HAZARD_V1"
_IMPLEMENTATION_SUFFIX = "NATIVE_ADAPTER_20261124_R1"


@dataclass(frozen=True, slots=True)
class _RenewalHazardModel:
    risk: tuple[tuple[int, ...], ...]
    events: tuple[tuple[int, ...], ...]
    age_current: tuple[int | None, ...]
    age_bucket: tuple[int | None, ...]
    frequency: tuple[int, ...]
    hazards: tuple[tuple[Fraction, ...], ...]
    frequency_scores: tuple[Fraction, ...]
    age_hazards: tuple[Fraction, ...]
    scores: tuple[Fraction, ...]
    ranking: tuple[int, ...]


def _age_bucket(age: int) -> int:
    """Map a nonnegative current age to the donor's six fixed buckets."""

    if type(age) is not int or age < 0:
        raise ValueError("age must be a nonnegative exact integer")
    if age < 2:
        return age
    if age < 4:
        return 2
    if age < 8:
        return 3
    if age < 16:
        return 4
    return 5


def _risk_sequence(
    sequence: tuple[int, ...],
) -> tuple[tuple[int, ...], tuple[int, ...], int | None, int, tuple[Fraction, ...]]:
    """Count renewal exposure after the first observed hit, preserving left truncation."""

    risk = [0] * 6
    events = [0] * 6
    seen = False
    age: int | None = None
    frequency = 0

    for outcome in sequence:
        if type(outcome) is not int or outcome not in (0, 1):
            raise ValueError("sequence values must be exact binary integers")
        frequency += outcome
        if not seen:
            if outcome:
                seen = True
                age = 0
            continue

        if age is None:
            raise RuntimeError("seen renewal must have an age")
        bucket = _age_bucket(age)
        risk[bucket] += 1
        events[bucket] += outcome
        age = 0 if outcome else age + 1

    hazards = tuple(
        Fraction(49 * event + 240, 49 * (exposure + 40))
        for exposure, event in zip(risk, events, strict=True)
    )
    return tuple(risk), tuple(events), age, frequency, hazards


def _analyze(history: tuple[CausalDrawRow, ...]) -> _RenewalHazardModel:
    """Run the shared exact Fraction model on exactly the preceding 750 rows."""

    if len(history) != _HISTORY_WINDOW:
        raise ValueError(f"model requires exactly {_HISTORY_WINDOW} draws")

    sequences = [[0] * _HISTORY_WINDOW for _ in range(_NUMBER_COUNT)]
    for index, row in enumerate(history):
        for number in row.numbers:
            sequences[number - 1][index] = 1

    scans = [_risk_sequence(tuple(sequence)) for sequence in sequences]
    risk = tuple(scan[0] for scan in scans)
    events = tuple(scan[1] for scan in scans)
    ages = tuple(scan[2] for scan in scans)
    frequency = tuple(scan[3] for scan in scans)
    hazards = tuple(scan[4] for scan in scans)
    age_buckets = tuple(None if age is None else _age_bucket(age) for age in ages)

    frequency_scores = tuple(Fraction(49 * count + 600, 49 * 850) for count in frequency)
    age_hazards = tuple(
        _P0 if bucket is None else hazards[index][bucket]
        for index, bucket in enumerate(age_buckets)
    )
    scores = tuple(
        (frequency_score + age_hazard) / 2
        for frequency_score, age_hazard in zip(frequency_scores, age_hazards, strict=True)
    )
    ranking = tuple(
        sorted(range(1, _NUMBER_COUNT + 1), key=lambda number: (-scores[number - 1], number))
    )

    return _RenewalHazardModel(
        risk=risk,
        events=events,
        age_current=ages,
        age_bucket=age_buckets,
        frequency=frequency,
        hazards=hazards,
        frequency_scores=frequency_scores,
        age_hazards=age_hazards,
        scores=scores,
        ranking=ranking,
    )


def _tickets_for_rank(ranking: tuple[int, ...], ticket_count: int) -> tuple[tuple[int, ...], ...]:
    """Group the first 6*K ranked numbers and sort only within each ticket."""

    if type(ticket_count) is not int or ticket_count not in (2, 3, 5):
        raise ValueError("ticket_count must be one of the fixed K values 2, 3, or 5")
    return tuple(
        tuple(sorted(ranking[offset : offset + _TICKET_SIZE]))
        for offset in range(0, _TICKET_SIZE * ticket_count, _TICKET_SIZE)
    )


class _BigLottoCausalRenewalHazardAdapter(PortfolioBetAdapter):
    """Shared adapter mechanics; subclasses own distinct strategy identities."""

    strategy_name: ClassVar[str] = "大樂透固定 Renewal Hazard 原生候選"
    strategy_version: ClassVar[str] = _STRATEGY_VERSION
    min_history: ClassVar[int] = _HISTORY_WINDOW
    supported_lottery_types: ClassVar[tuple[LotteryType, ...]] = (LotteryType.BIG_LOTTO,)

    def _history_window(self, history: tuple[object, ...]) -> tuple[object, ...]:
        # The caller supplies only draws before its target; retain its last 750.
        return history[-_HISTORY_WINDOW:]

    def _predict_all(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[tuple[int, ...], ...]:
        if lottery_type is not LotteryType.BIG_LOTTO:
            raise ValueError("Renewal Hazard supports BIG_LOTTO only")
        model = _analyze(history)
        return _tickets_for_rank(model.ranking, self.native_ticket_count)


class BigLottoCausalRenewalHazardK2Adapter(_BigLottoCausalRenewalHazardAdapter):
    strategy_id = "research_causal_renewal_hazard_k2"
    strategy_name = "大樂透 Renewal Hazard K2"
    implementation_identity = f"{strategy_id}:{_IMPLEMENTATION_SUFFIX}"
    native_ticket_count = 2


class BigLottoCausalRenewalHazardK3Adapter(_BigLottoCausalRenewalHazardAdapter):
    strategy_id = "research_causal_renewal_hazard_k3"
    strategy_name = "大樂透 Renewal Hazard K3"
    implementation_identity = f"{strategy_id}:{_IMPLEMENTATION_SUFFIX}"
    native_ticket_count = 3


class BigLottoCausalRenewalHazardK5Adapter(_BigLottoCausalRenewalHazardAdapter):
    strategy_id = "research_causal_renewal_hazard_k5"
    strategy_name = "大樂透 Renewal Hazard K5"
    implementation_identity = f"{strategy_id}:{_IMPLEMENTATION_SUFFIX}"
    native_ticket_count = 5


ADAPTER_TYPES_BY_K: dict[int, type[_BigLottoCausalRenewalHazardAdapter]] = {
    2: BigLottoCausalRenewalHazardK2Adapter,
    3: BigLottoCausalRenewalHazardK3Adapter,
    5: BigLottoCausalRenewalHazardK5Adapter,
}

__all__ = [
    "ADAPTER_TYPES_BY_K",
    "BigLottoCausalRenewalHazardK2Adapter",
    "BigLottoCausalRenewalHazardK3Adapter",
    "BigLottoCausalRenewalHazardK5Adapter",
]
