"""Typed, fail-closed contract for DB-free strategy bet adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import ClassVar, cast

from lottolab.domain.draws import LotteryType
from lottolab.domain.lottery_rules import BIG_LOTTO_RULE_CONTRACT


class BetAdapterError(Exception):
    """Base class for expected adapter outcomes."""


class RejectPrediction(BetAdapterError):
    """The strategy deliberately declines to emit a prediction."""


class UnsupportedLotteryType(BetAdapterError):
    """The adapter does not support the requested lottery type."""


class InvalidOutput(BetAdapterError):
    """Input or strategy output violates the adapter contract."""


class InsufficientHistory(BetAdapterError):
    """The strategy requires more causal history than it received."""


@dataclass(frozen=True, slots=True)
class CausalDrawRow:
    """One immutable draw strictly preceding the draw being predicted."""

    draw: str
    date: str
    numbers: tuple[int, ...]


def _validated_biglotto_numbers(numbers: object, strategy_id: str) -> tuple[int, ...]:
    """Validate exact integers against the authoritative BIG_LOTTO contract."""

    rule = BIG_LOTTO_RULE_CONTRACT
    if type(numbers) is not tuple:
        raise InvalidOutput(f"{strategy_id}: expected a number tuple")
    raw_numbers = cast(tuple[object, ...], numbers)
    if len(raw_numbers) != rule.main_number_count:
        raise InvalidOutput(
            f"{strategy_id}: expected {rule.main_number_count} numbers, "
            f"got {len(raw_numbers)}"
        )
    if not all(type(number) is int for number in raw_numbers):
        raise InvalidOutput(f"{strategy_id}: numbers must be exact built-in integers")
    validated = cast(tuple[int, ...], raw_numbers)
    if not all(rule.main_number_min <= number <= rule.main_number_max for number in validated):
        raise InvalidOutput(
            f"{strategy_id}: numbers out of range "
            f"[{rule.main_number_min}..{rule.main_number_max}]"
        )
    if rule.main_numbers_unique and len(set(validated)) != rule.main_number_count:
        raise InvalidOutput(f"{strategy_id}: duplicate numbers")
    return tuple(sorted(validated))


def _require_history_tuple(history: object, strategy_id: str) -> tuple[object, ...]:
    """Reject every history container except an exact built-in tuple."""

    if type(history) is not tuple:
        raise InvalidOutput(f"{strategy_id}: expected a history tuple")
    return cast(tuple[object, ...], history)


def validated_history(history: object, strategy_id: str) -> tuple[CausalDrawRow, ...]:
    """Return canonical immutable rows without coercing legacy values."""

    rows = _require_history_tuple(history, strategy_id)
    validated: list[CausalDrawRow] = []
    for index, candidate in enumerate(rows):
        if type(candidate) is not CausalDrawRow:
            raise InvalidOutput(f"{strategy_id}: history row {index} is not a CausalDrawRow")
        row = candidate
        if type(row.draw) is not str or not row.draw:
            raise InvalidOutput(
                f"{strategy_id}: history row {index} draw must be a non-empty string"
            )
        if type(row.date) is not str or not row.date:
            raise InvalidOutput(
                f"{strategy_id}: history row {index} date must be a non-empty string"
            )
        validated.append(
            CausalDrawRow(
                draw=row.draw,
                date=row.date,
                numbers=_validated_biglotto_numbers(row.numbers, strategy_id),
            )
        )
    return tuple(validated)


class BetAdapter(ABC):
    """Template implementing the donor gate order for one canonical bet."""

    strategy_id: ClassVar[str]
    strategy_name: ClassVar[str]
    strategy_version: ClassVar[str]
    min_history: ClassVar[int]
    supported_lottery_types: ClassVar[tuple[LotteryType, ...]]

    def get_one_bet(
        self,
        history: object,
        lottery_type: LotteryType,
    ) -> tuple[tuple[int, ...], None]:
        if (
            type(lottery_type) is not LotteryType
            or lottery_type not in self.supported_lottery_types
        ):
            raise UnsupportedLotteryType(
                f"{self.strategy_id} does not support the requested lottery type"
            )

        raw_history = _require_history_tuple(history, self.strategy_id)
        canonical_history = validated_history(
            self._history_window(raw_history),
            self.strategy_id,
        )
        if len(canonical_history) < self.min_history:
            raise InsufficientHistory(
                f"{self.strategy_id}: needs {self.min_history} draws, "
                f"got {len(canonical_history)}"
            )

        predicted = self._predict(canonical_history, lottery_type)
        validated = _validated_biglotto_numbers(predicted, self.strategy_id)
        return validated, None

    def _history_window(self, history: tuple[object, ...]) -> tuple[object, ...]:
        """Select rows that are causally visible to this adapter before row validation."""

        return history

    @abstractmethod
    def _predict(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[int, ...]:
        """Return one untrusted prediction for base-class output validation."""


__all__ = [
    "BetAdapter",
    "BetAdapterError",
    "CausalDrawRow",
    "InsufficientHistory",
    "InvalidOutput",
    "RejectPrediction",
    "UnsupportedLotteryType",
]
