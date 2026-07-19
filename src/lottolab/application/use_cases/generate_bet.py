"""Internal use case for one injected, DB-free strategy prediction."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import cast

from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters.base import (
    BetAdapter,
    CausalDrawRow,
    InsufficientHistory,
    InvalidOutput,
    RejectPrediction,
    UnsupportedLotteryType,
)
from lottolab.strategies.catalog import StrategyCatalog, UnknownStrategyError


class GenerateOneBetStatus(StrEnum):
    OK = "OK"
    REJECTED = "REJECTED"
    INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"
    STRATEGY_UNAVAILABLE = "STRATEGY_UNAVAILABLE"
    INVALID_OUTPUT = "INVALID_OUTPUT"
    REPLAY_ERROR = "REPLAY_ERROR"


class GenerateOneBetReason(StrEnum):
    REJECTED_BY_STRATEGY = "REJECTED_BY_STRATEGY"
    INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"
    UNKNOWN_STRATEGY = "UNKNOWN_STRATEGY"
    ADAPTER_NOT_INJECTED = "ADAPTER_NOT_INJECTED"
    UNSUPPORTED_LOTTERY_TYPE = "UNSUPPORTED_LOTTERY_TYPE"
    INVALID_OUTPUT = "INVALID_OUTPUT"
    REPLAY_ERROR = "REPLAY_ERROR"


class AdapterIdentityMismatchError(ValueError):
    """An injected adapter does not match its canonical catalog descriptor."""


@dataclass(frozen=True, slots=True)
class GenerateOneBetInput:
    strategy_id: str
    lottery_type: LotteryType
    history: tuple[CausalDrawRow, ...]


@dataclass(frozen=True, slots=True)
class GenerateOneBetResult:
    status: GenerateOneBetStatus
    numbers: tuple[int, ...] | None
    special_number: None
    reason_code: GenerateOneBetReason | None

    def __post_init__(self) -> None:
        if self.status is GenerateOneBetStatus.OK:
            if self.numbers is None or self.reason_code is not None:
                raise ValueError("OK results require numbers and no reason code")
        elif self.numbers is not None or self.reason_code is None:
            raise ValueError("non-OK results require a reason code and no numbers")


class GenerateOneBet:
    """Resolve an injected adapter and convert every outcome to a closed result."""

    def __init__(self, catalog: StrategyCatalog, adapters: Mapping[str, BetAdapter]) -> None:
        adapter_snapshot: dict[str, BetAdapter] = {}
        runtime_entries = cast(Mapping[object, object], adapters)
        for candidate_id, candidate_adapter in runtime_entries.items():
            if type(candidate_id) is not str or not isinstance(candidate_adapter, BetAdapter):
                raise AdapterIdentityMismatchError("adapter mapping contains an invalid entry")
            strategy_id = candidate_id
            adapter = candidate_adapter
            adapter_snapshot[strategy_id] = adapter
            try:
                descriptor = catalog.get(strategy_id)
            except UnknownStrategyError as exc:
                raise AdapterIdentityMismatchError(
                    f"{strategy_id}: adapter has no catalog descriptor"
                ) from exc
            actual_identity = (
                adapter.strategy_id,
                adapter.strategy_name,
                adapter.strategy_version,
            )
            expected_identity = (
                descriptor.strategy_id,
                descriptor.strategy_name,
                descriptor.version,
            )
            if strategy_id != adapter.strategy_id or actual_identity != expected_identity:
                raise AdapterIdentityMismatchError(
                    f"{strategy_id}: adapter identity does not match the catalog"
                )

        self._catalog = catalog
        self._adapters: Mapping[str, BetAdapter] = MappingProxyType(adapter_snapshot)

    def execute(self, request: GenerateOneBetInput) -> GenerateOneBetResult:
        try:
            descriptor = self._catalog.get(request.strategy_id)
        except UnknownStrategyError:
            return self._failure(
                GenerateOneBetStatus.STRATEGY_UNAVAILABLE,
                GenerateOneBetReason.UNKNOWN_STRATEGY,
            )

        adapter = self._adapters.get(request.strategy_id)
        if adapter is None:
            return self._failure(
                GenerateOneBetStatus.STRATEGY_UNAVAILABLE,
                GenerateOneBetReason.ADAPTER_NOT_INJECTED,
            )
        if type(request.lottery_type) is not LotteryType or (
            request.lottery_type not in descriptor.lottery_types
        ):
            return self._failure(
                GenerateOneBetStatus.STRATEGY_UNAVAILABLE,
                GenerateOneBetReason.UNSUPPORTED_LOTTERY_TYPE,
            )

        try:
            numbers, special_number = adapter.get_one_bet(
                request.history,
                request.lottery_type,
            )
        except RejectPrediction:
            return self._failure(
                GenerateOneBetStatus.REJECTED,
                GenerateOneBetReason.REJECTED_BY_STRATEGY,
            )
        except InsufficientHistory:
            return self._failure(
                GenerateOneBetStatus.INSUFFICIENT_HISTORY,
                GenerateOneBetReason.INSUFFICIENT_HISTORY,
            )
        except UnsupportedLotteryType:
            return self._failure(
                GenerateOneBetStatus.STRATEGY_UNAVAILABLE,
                GenerateOneBetReason.UNSUPPORTED_LOTTERY_TYPE,
            )
        except InvalidOutput:
            return self._failure(
                GenerateOneBetStatus.INVALID_OUTPUT,
                GenerateOneBetReason.INVALID_OUTPUT,
            )
        except Exception:
            return self._failure(
                GenerateOneBetStatus.REPLAY_ERROR,
                GenerateOneBetReason.REPLAY_ERROR,
            )

        return GenerateOneBetResult(
            status=GenerateOneBetStatus.OK,
            numbers=numbers,
            special_number=special_number,
            reason_code=None,
        )

    @staticmethod
    def _failure(
        status: GenerateOneBetStatus,
        reason: GenerateOneBetReason,
    ) -> GenerateOneBetResult:
        return GenerateOneBetResult(
            status=status,
            numbers=None,
            special_number=None,
            reason_code=reason,
        )


__all__ = [
    "AdapterIdentityMismatchError",
    "GenerateOneBet",
    "GenerateOneBetInput",
    "GenerateOneBetReason",
    "GenerateOneBetResult",
    "GenerateOneBetStatus",
]
