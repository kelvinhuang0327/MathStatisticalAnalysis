"""Typed, fail-closed contract for DB-free strategy bet adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import ClassVar, cast

from lottolab.domain.draws import LotteryType
from lottolab.domain.lottery_rules import (
    LOTTERY_RULE_CONTRACTS,
    LotteryRuleContract,
    resolve_lottery_rule_contract,
)


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


class SourceNativePortfolioClosure(BetAdapterError):
    """The donor legitimately closed a portfolio below its advertised maximum."""

    def __init__(
        self,
        *,
        strategy_id: str,
        expected_ticket_count: int,
        actual_ticket_count: int,
    ) -> None:
        self.strategy_id = strategy_id
        self.expected_ticket_count = expected_ticket_count
        self.actual_ticket_count = actual_ticket_count
        super().__init__(
            f"{strategy_id}: source-native portfolio closure emitted "
            f"{actual_ticket_count} of {expected_ticket_count} native tickets"
        )


@dataclass(frozen=True, slots=True)
class CausalDrawRow:
    """One immutable draw strictly preceding the draw being predicted."""

    draw: str
    date: str
    numbers: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class BetAdapterExecution:
    """One producer execution before and after legal-ticket canonicalization."""

    emitted_main_numbers: tuple[int, ...]
    legal_main_numbers: tuple[int, ...]
    special_number: int | None


def _resolved_rule(lottery_type: LotteryType, strategy_id: str) -> LotteryRuleContract:
    """Resolve the one active, primary rule contract for a supported lottery type."""

    rule = resolve_lottery_rule_contract(lottery_type, LOTTERY_RULE_CONTRACTS)
    if rule is None:
        raise UnsupportedLotteryType(
            f"{strategy_id}: no active primary rule contract for {lottery_type}"
        )
    return rule


def _validated_lottery_numbers(
    numbers: object,
    strategy_id: str,
    rule: LotteryRuleContract,
) -> tuple[int, ...]:
    """Validate exact integers against one authoritative native lottery rule contract."""

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


def _validated_special_number(
    value: object,
    strategy_id: str,
    rule: LotteryRuleContract,
    *,
    main_numbers: tuple[int, ...],
) -> int | None:
    """Validate one optional special/second-zone number against its native rule.

    Presence is always optional here regardless of the rule's
    ``special_number_required`` flag: that flag describes the lottery's own
    drawn result (every BIG_LOTTO draw has one), not whether a strategy's
    predicted ticket must include one (BIG_LOTTO strategies legitimately
    never do). A concrete value, once given, is still fully validated.
    """

    if value is None:
        return None
    if rule.special_number_count == 0:
        raise InvalidOutput(f"{strategy_id}: special_number is not defined for this lottery")
    if type(value) is not int:
        raise InvalidOutput(f"{strategy_id}: special_number must be an exact built-in integer")
    if not rule.special_number_min <= value <= rule.special_number_max:
        raise InvalidOutput(
            f"{strategy_id}: special_number out of range "
            f"[{rule.special_number_min}..{rule.special_number_max}]"
        )
    if not rule.main_special_overlap_allowed and value in main_numbers:
        raise InvalidOutput(f"{strategy_id}: special_number must not overlap main numbers")
    return value


def _require_history_tuple(history: object, strategy_id: str) -> tuple[object, ...]:
    """Reject every history container except an exact built-in tuple."""

    if type(history) is not tuple:
        raise InvalidOutput(f"{strategy_id}: expected a history tuple")
    return cast(tuple[object, ...], history)


def validated_history(
    history: object,
    strategy_id: str,
    *,
    lottery_type: LotteryType = LotteryType.BIG_LOTTO,
) -> tuple[CausalDrawRow, ...]:
    """Return canonical immutable rows without coercing legacy values.

    ``lottery_type`` selects the native rule contract used to validate each
    row's main numbers. It defaults to ``BIG_LOTTO`` so every existing
    two-argument call site keeps its exact prior behavior. ``CausalDrawRow``
    carries only primary numbers by design (see
    ``lottolab.domain.replay_history.ReplayCausalDrawRow`` for the separate,
    dataset-specific type that carries second-zone history).
    """

    rule = _resolved_rule(lottery_type, strategy_id)
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
        validated_numbers = _validated_lottery_numbers(row.numbers, strategy_id, rule)
        validated.append(
            CausalDrawRow(
                draw=row.draw,
                date=row.date,
                numbers=validated_numbers,
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
    ) -> tuple[tuple[int, ...], int | None]:
        execution = self.get_one_bet_with_emission(history, lottery_type)
        return execution.legal_main_numbers, execution.special_number

    def get_one_bet_with_emission(
        self,
        history: object,
        lottery_type: LotteryType,
    ) -> BetAdapterExecution:
        """Execute the producer once and retain its tuple before legal sorting."""

        if (
            type(lottery_type) is not LotteryType
            or lottery_type not in self.supported_lottery_types
        ):
            raise UnsupportedLotteryType(
                f"{self.strategy_id} does not support the requested lottery type"
            )
        rule = _resolved_rule(lottery_type, self.strategy_id)

        raw_history = _require_history_tuple(history, self.strategy_id)
        canonical_history = validated_history(
            self._history_window(raw_history),
            self.strategy_id,
            lottery_type=lottery_type,
        )
        if len(canonical_history) < self.min_history:
            raise InsufficientHistory(
                f"{self.strategy_id}: needs {self.min_history} draws, "
                f"got {len(canonical_history)}"
            )

        predicted = self._predict(canonical_history, lottery_type)
        validated = _validated_lottery_numbers(predicted, self.strategy_id, rule)
        predicted_special = self._predict_special_number(
            canonical_history, lottery_type, validated
        )
        validated_special = _validated_special_number(
            predicted_special,
            self.strategy_id,
            rule,
            main_numbers=validated,
        )
        return BetAdapterExecution(
            emitted_main_numbers=predicted,
            legal_main_numbers=validated,
            special_number=validated_special,
        )

    def _history_window(self, history: tuple[object, ...]) -> tuple[object, ...]:
        """Select rows that are causally visible to this adapter before row validation."""

        return history

    def _predict_special_number(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
        main_numbers: tuple[int, ...],
    ) -> int | None:
        """Return this producer's untrusted special number, or ``None`` when not applicable.

        The default preserves every existing single-ticket adapter's output
        exactly ``None``. A native adapter for a lottery whose own ticket
        includes a second-zone/special number (for example POWER_LOTTO)
        overrides this hook instead of changing :meth:`_predict`.
        """

        return None

    @abstractmethod
    def _predict(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[int, ...]:
        """Return one untrusted prediction for base-class output validation."""


class PortfolioBetAdapter(ABC):
    """Template for one strategy identity whose native output is an ordered,
    bounded set of one or more causally-computed tickets (a "portfolio").

    Kept entirely separate from :class:`BetAdapter` so the eight shipped
    single-ticket adapters are untouched by this contract's existence. Native
    ticket order and positional duplicates are preserved exactly as emitted;
    this class only canonicalizes each ticket's own number ordering for legal
    validation, never reorders or deduplicates across tickets. Existing
    adapters declare one exact ``native_ticket_count``; variable-size adapters
    additionally declare a finite minimum and maximum.
    """

    strategy_id: ClassVar[str]
    strategy_name: ClassVar[str]
    strategy_version: ClassVar[str]
    min_history: ClassVar[int]
    supported_lottery_types: ClassVar[tuple[LotteryType, ...]]
    native_ticket_count: ClassVar[int]
    minimum_native_ticket_count: ClassVar[int | None] = None
    maximum_native_ticket_count: ClassVar[int | None] = None

    @classmethod
    def native_ticket_count_bounds(cls) -> tuple[int, int]:
        """Resolve and validate this adapter's bounded cardinality declaration."""

        native_count = cls.native_ticket_count
        minimum = (
            native_count
            if cls.minimum_native_ticket_count is None
            else cls.minimum_native_ticket_count
        )
        maximum = (
            native_count
            if cls.maximum_native_ticket_count is None
            else cls.maximum_native_ticket_count
        )
        if (
            type(native_count) is not int
            or type(minimum) is not int
            or type(maximum) is not int
            or minimum < 1
            or minimum > maximum
            or native_count != maximum
        ):
            raise InvalidOutput(
                f"{cls.strategy_id}: invalid bounded native ticket-count declaration"
            )
        return minimum, maximum

    def get_bets(
        self,
        history: object,
        lottery_type: LotteryType,
    ) -> tuple[tuple[int, ...], ...]:
        executions = self.get_bets_with_emission(history, lottery_type)
        return tuple(execution.legal_main_numbers for execution in executions)

    def get_bets_with_emission(
        self,
        history: object,
        lottery_type: LotteryType,
    ) -> tuple[BetAdapterExecution, ...]:
        """Execute the producer once and retain each ticket's pre-canonical tuple."""

        if (
            type(lottery_type) is not LotteryType
            or lottery_type not in self.supported_lottery_types
        ):
            raise UnsupportedLotteryType(
                f"{self.strategy_id} does not support the requested lottery type"
            )
        rule = _resolved_rule(lottery_type, self.strategy_id)

        raw_history = _require_history_tuple(history, self.strategy_id)
        canonical_history = validated_history(
            self._history_window(raw_history),
            self.strategy_id,
            lottery_type=lottery_type,
        )
        if len(canonical_history) < self.min_history:
            raise InsufficientHistory(
                f"{self.strategy_id}: needs {self.min_history} draws, "
                f"got {len(canonical_history)}"
            )

        predicted = self._predict_all(canonical_history, lottery_type)
        if type(predicted) is not tuple:
            raise InvalidOutput(f"{self.strategy_id}: expected a tuple of tickets")
        minimum_count, maximum_count = self.native_ticket_count_bounds()
        if not minimum_count <= len(predicted) <= maximum_count:
            if minimum_count == maximum_count:
                expectation = str(minimum_count)
            else:
                expectation = f"between {minimum_count} and {maximum_count}"
            raise InvalidOutput(
                f"{self.strategy_id}: expected {expectation} native tickets, "
                f"got {len(predicted)}"
            )

        validated_tickets = tuple(
            _validated_lottery_numbers(ticket, self.strategy_id, rule) for ticket in predicted
        )
        predicted_specials = self._predict_special_numbers(
            canonical_history, lottery_type, validated_tickets
        )
        if type(predicted_specials) is not tuple or len(predicted_specials) != len(
            validated_tickets
        ):
            raise InvalidOutput(
                f"{self.strategy_id}: expected one special number per native ticket"
            )
        return tuple(
            BetAdapterExecution(
                emitted_main_numbers=ticket,
                legal_main_numbers=validated_ticket,
                special_number=_validated_special_number(
                    special,
                    self.strategy_id,
                    rule,
                    main_numbers=validated_ticket,
                ),
            )
            for ticket, validated_ticket, special in zip(
                predicted, validated_tickets, predicted_specials, strict=True
            )
        )

    def _history_window(self, history: tuple[object, ...]) -> tuple[object, ...]:
        """Select rows that are causally visible to this adapter before row validation."""

        return history

    def _predict_special_numbers(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
        tickets: tuple[tuple[int, ...], ...],
    ) -> tuple[int | None, ...]:
        """Return this producer's untrusted special number per ticket, or all-``None``.

        The default preserves every existing portfolio adapter's output
        exactly ``None`` for each ticket; see
        :meth:`BetAdapter._predict_special_number` for the single-ticket
        equivalent and when a native adapter would override this instead.
        """

        return tuple(None for _ in tickets)

    @abstractmethod
    def _predict_all(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[tuple[int, ...], ...]:
        """Return the untrusted, ordered native ticket set for base-class validation."""


__all__ = [
    "BetAdapter",
    "BetAdapterError",
    "BetAdapterExecution",
    "CausalDrawRow",
    "InsufficientHistory",
    "InvalidOutput",
    "PortfolioBetAdapter",
    "RejectPrediction",
    "SourceNativePortfolioClosure",
    "UnsupportedLotteryType",
]
