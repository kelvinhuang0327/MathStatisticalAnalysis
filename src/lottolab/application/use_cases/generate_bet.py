"""Internal use case for one injected, DB-free strategy prediction."""

from __future__ import annotations

import json
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
from lottolab.strategies.catalog import StrategyCatalog, UnknownStrategyError, production_catalog


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


class HistoryParseError(ValueError):
    """CLI-supplied history JSON does not match the canonical row shape."""


def parse_history_json(raw: str) -> tuple[CausalDrawRow, ...]:
    """Parse a JSON array of ``{draw, date, numbers}`` rows into causal history.

    Only shape is checked here; rule validity (range, count, uniqueness) is
    the adapter's job via :func:`lottolab.strategies.adapters.base.validated_history`.
    """

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HistoryParseError(f"history is not valid JSON: {exc}") from exc
    if not isinstance(parsed, list):
        raise HistoryParseError("history JSON must be a list of draw rows")

    rows: list[CausalDrawRow] = []
    for index, item in enumerate(cast("list[object]", parsed)):
        if not isinstance(item, dict):
            raise HistoryParseError(f"history row {index} must be an object")
        record = cast("dict[str, object]", item)
        draw = record.get("draw")
        date = record.get("date")
        numbers = record.get("numbers")
        if not isinstance(draw, str) or not draw:
            raise HistoryParseError(f"history row {index}: draw must be a non-empty string")
        if not isinstance(date, str) or not date:
            raise HistoryParseError(f"history row {index}: date must be a non-empty string")
        if not isinstance(numbers, list) or not all(
            type(number) is int for number in cast("list[object]", numbers)
        ):
            raise HistoryParseError(f"history row {index}: numbers must be a list of integers")
        rows.append(
            CausalDrawRow(draw=draw, date=date, numbers=tuple(cast("list[int]", numbers)))
        )
    return tuple(rows)


def render_result_json(result: GenerateOneBetResult, *, strategy_id: str, seed: int) -> str:
    """Render a canonical, machine-readable single-bet result."""

    payload: dict[str, object] = {
        "strategy_id": strategy_id,
        "lottery_type": LotteryType.BIG_LOTTO.value,
        "seed": seed,
        "status": result.status.value,
        "numbers": list(result.numbers) if result.numbers is not None else None,
        "reason_code": result.reason_code.value if result.reason_code is not None else None,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _instantiated_adapter(strategy_id: str, adapter_class: object) -> BetAdapter:
    if not (isinstance(adapter_class, type) and issubclass(adapter_class, BetAdapter)):
        raise AdapterIdentityMismatchError(
            f"{strategy_id}: adapter_path does not resolve to a BetAdapter subclass"
        )
    return adapter_class()


def build_production_generate_one_bet() -> GenerateOneBet:
    """Compose the production catalog with its executable adapters.

    Imports :class:`ExecutableRegistry` lazily so importing this module never
    loads or mutates it — see ``test_import_does_not_load_or_mutate_executable_registry``.
    """

    from lottolab.strategies.executable_registry import ExecutableRegistry

    catalog = production_catalog()
    registry = ExecutableRegistry(catalog)
    adapters: dict[str, BetAdapter] = {
        strategy_id: _instantiated_adapter(strategy_id, registry.load_adapter(strategy_id))
        for strategy_id in registry.executable_ids()
    }
    return GenerateOneBet(catalog, adapters)


def run_cli_generate_bet(*, strategy_id: str, seed: int, history_json: str) -> tuple[str, bool]:
    """Parse, execute, and render one CLI bet request.

    Returns ``(json_text, ok)``; ``ok`` is false for every non-``OK`` status
    so the caller can select a fail-closed process exit code. May raise
    :class:`HistoryParseError` for malformed input, by design left to the
    caller so it can be reported the same way as other CLI input errors.
    """

    history = parse_history_json(history_json)
    use_case = build_production_generate_one_bet()
    result = use_case.execute(
        GenerateOneBetInput(
            strategy_id=strategy_id,
            lottery_type=LotteryType.BIG_LOTTO,
            history=history,
        )
    )
    return (
        render_result_json(result, strategy_id=strategy_id, seed=seed),
        result.status is GenerateOneBetStatus.OK,
    )


__all__ = [
    "AdapterIdentityMismatchError",
    "GenerateOneBet",
    "GenerateOneBetInput",
    "GenerateOneBetReason",
    "GenerateOneBetResult",
    "GenerateOneBetStatus",
    "HistoryParseError",
    "build_production_generate_one_bet",
    "parse_history_json",
    "render_result_json",
    "run_cli_generate_bet",
]
