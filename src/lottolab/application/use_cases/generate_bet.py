"""Internal use case for one injected, DB-free strategy prediction."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import cast

from lottolab.domain.draws import LotteryType
from lottolab.domain.strategies import ResponseShape
from lottolab.strategies.adapters.base import (
    BetAdapter,
    CausalDrawRow,
    InsufficientHistory,
    InvalidOutput,
    PortfolioBetAdapter,
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
    WRONG_RESPONSE_PATH = "WRONG_RESPONSE_PATH"


class GenerateOneBetReason(StrEnum):
    REJECTED_BY_STRATEGY = "REJECTED_BY_STRATEGY"
    INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"
    UNKNOWN_STRATEGY = "UNKNOWN_STRATEGY"
    ADAPTER_NOT_INJECTED = "ADAPTER_NOT_INJECTED"
    UNSUPPORTED_LOTTERY_TYPE = "UNSUPPORTED_LOTTERY_TYPE"
    INVALID_OUTPUT = "INVALID_OUTPUT"
    REPLAY_ERROR = "REPLAY_ERROR"
    STRATEGY_IS_PORTFOLIO = "STRATEGY_IS_PORTFOLIO"


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
    special_number: int | None
    reason_code: GenerateOneBetReason | None

    def __post_init__(self) -> None:
        if self.status is GenerateOneBetStatus.OK:
            if self.numbers is None or self.reason_code is not None:
                raise ValueError("OK results require numbers and no reason code")
        elif self.numbers is not None or self.reason_code is None:
            raise ValueError("non-OK results require a reason code and no numbers")


@dataclass(frozen=True, slots=True)
class GenerateOneBetExecution:
    """Internal execution detail paired with the unchanged public legal result."""

    legal_bet: GenerateOneBetResult
    emitted_main_numbers: tuple[int, ...] | None
    strategy_version: str | None

    def __post_init__(self) -> None:
        if self.legal_bet.status is GenerateOneBetStatus.OK:
            if (
                type(self.emitted_main_numbers) is not tuple
                or not self.emitted_main_numbers
                or type(self.strategy_version) is not str
                or not self.strategy_version
            ):
                raise ValueError("OK executions require emitted_main_numbers and strategy_version")
        elif self.emitted_main_numbers is not None or self.strategy_version is not None:
            raise ValueError("non-OK executions must not expose an emission identity")


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
        return self.execute_with_emission(request).legal_bet

    def execute_with_emission(
        self,
        request: GenerateOneBetInput,
    ) -> GenerateOneBetExecution:
        """Return one adapter execution with its pre-canonical emitted order."""

        try:
            descriptor = self._catalog.get(request.strategy_id)
        except UnknownStrategyError:
            return self._failure_execution(
                GenerateOneBetStatus.STRATEGY_UNAVAILABLE,
                GenerateOneBetReason.UNKNOWN_STRATEGY,
            )

        if descriptor.response_shape is ResponseShape.PORTFOLIO:
            return self._failure_execution(
                GenerateOneBetStatus.WRONG_RESPONSE_PATH,
                GenerateOneBetReason.STRATEGY_IS_PORTFOLIO,
            )

        adapter = self._adapters.get(request.strategy_id)
        if adapter is None:
            return self._failure_execution(
                GenerateOneBetStatus.STRATEGY_UNAVAILABLE,
                GenerateOneBetReason.ADAPTER_NOT_INJECTED,
            )
        if type(request.lottery_type) is not LotteryType or (
            request.lottery_type not in descriptor.lottery_types
        ):
            return self._failure_execution(
                GenerateOneBetStatus.STRATEGY_UNAVAILABLE,
                GenerateOneBetReason.UNSUPPORTED_LOTTERY_TYPE,
            )

        try:
            adapter_execution = adapter.get_one_bet_with_emission(
                request.history,
                request.lottery_type,
            )
        except RejectPrediction:
            return self._failure_execution(
                GenerateOneBetStatus.REJECTED,
                GenerateOneBetReason.REJECTED_BY_STRATEGY,
            )
        except InsufficientHistory:
            return self._failure_execution(
                GenerateOneBetStatus.INSUFFICIENT_HISTORY,
                GenerateOneBetReason.INSUFFICIENT_HISTORY,
            )
        except UnsupportedLotteryType:
            return self._failure_execution(
                GenerateOneBetStatus.STRATEGY_UNAVAILABLE,
                GenerateOneBetReason.UNSUPPORTED_LOTTERY_TYPE,
            )
        except InvalidOutput:
            return self._failure_execution(
                GenerateOneBetStatus.INVALID_OUTPUT,
                GenerateOneBetReason.INVALID_OUTPUT,
            )
        except Exception:
            return self._failure_execution(
                GenerateOneBetStatus.REPLAY_ERROR,
                GenerateOneBetReason.REPLAY_ERROR,
            )

        return GenerateOneBetExecution(
            legal_bet=GenerateOneBetResult(
                status=GenerateOneBetStatus.OK,
                numbers=adapter_execution.legal_main_numbers,
                special_number=adapter_execution.special_number,
                reason_code=None,
            ),
            emitted_main_numbers=adapter_execution.emitted_main_numbers,
            strategy_version=descriptor.version,
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

    @classmethod
    def _failure_execution(
        cls,
        status: GenerateOneBetStatus,
        reason: GenerateOneBetReason,
    ) -> GenerateOneBetExecution:
        return GenerateOneBetExecution(
            legal_bet=cls._failure(status, reason),
            emitted_main_numbers=None,
            strategy_version=None,
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
        rows.append(CausalDrawRow(draw=draw, date=date, numbers=tuple(cast("list[int]", numbers))))
    return tuple(rows)


def render_result_json(result: GenerateOneBetResult, *, strategy_id: str, seed: int) -> str:
    """Render a canonical, machine-readable single-bet result.

    ``seed`` is caller-provided bookkeeping metadata: it is echoed verbatim
    in the ``seed`` field and never influences ``result``, which is fully
    determined upstream by strategy_id and causal history.
    """

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


def instantiate_adapter(strategy_id: str, adapter_class: object) -> BetAdapter:
    """Instantiate one catalog adapter through the canonical type guard."""

    return _instantiated_adapter(strategy_id, adapter_class)


def build_production_generate_one_bet() -> GenerateOneBet:
    """Compose the production catalog with its single-ticket executable adapters.

    PORTFOLIO strategies are excluded here — their adapters are not
    ``BetAdapter`` subclasses and must never be reachable through this
    one-ticket path (see :class:`GeneratePortfolio`). Imports
    :class:`ExecutableRegistry` lazily so importing this module never loads
    or mutates it — see ``test_import_does_not_load_or_mutate_executable_registry``.
    """

    from lottolab.strategies.executable_registry import ExecutableRegistry

    catalog = production_catalog()
    registry = ExecutableRegistry(catalog)
    adapters: dict[str, BetAdapter] = {
        strategy_id: _instantiated_adapter(strategy_id, registry.load_adapter(strategy_id))
        for strategy_id in registry.executable_ids()
        if catalog.get(strategy_id).response_shape is ResponseShape.SINGLE_TICKET
    }
    return GenerateOneBet(catalog, adapters)


class GeneratePortfolioStatus(StrEnum):
    OK = "OK"
    INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"
    STRATEGY_UNAVAILABLE = "STRATEGY_UNAVAILABLE"
    INVALID_OUTPUT = "INVALID_OUTPUT"
    REPLAY_ERROR = "REPLAY_ERROR"
    WRONG_RESPONSE_PATH = "WRONG_RESPONSE_PATH"


class GeneratePortfolioReason(StrEnum):
    INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"
    UNKNOWN_STRATEGY = "UNKNOWN_STRATEGY"
    ADAPTER_NOT_INJECTED = "ADAPTER_NOT_INJECTED"
    UNSUPPORTED_LOTTERY_TYPE = "UNSUPPORTED_LOTTERY_TYPE"
    INVALID_OUTPUT = "INVALID_OUTPUT"
    REPLAY_ERROR = "REPLAY_ERROR"
    STRATEGY_IS_NOT_PORTFOLIO = "STRATEGY_IS_NOT_PORTFOLIO"


@dataclass(frozen=True, slots=True)
class GeneratePortfolioResult:
    """The complete, ordered native ticket set — never truncated to one ticket."""

    status: GeneratePortfolioStatus
    numbers: tuple[tuple[int, ...], ...] | None
    special_number: int | None
    reason_code: GeneratePortfolioReason | None

    def __post_init__(self) -> None:
        if self.status is GeneratePortfolioStatus.OK:
            if self.numbers is None or self.reason_code is not None:
                raise ValueError("OK results require numbers and no reason code")
        elif self.numbers is not None or self.reason_code is None:
            raise ValueError("non-OK results require a reason code and no numbers")


@dataclass(frozen=True, slots=True)
class GeneratePortfolioExecution:
    """Internal execution detail paired with the unchanged public legal result."""

    legal_bets: GeneratePortfolioResult
    emitted_all_numbers: tuple[tuple[int, ...], ...] | None
    strategy_version: str | None

    def __post_init__(self) -> None:
        if self.legal_bets.status is GeneratePortfolioStatus.OK:
            if (
                type(self.emitted_all_numbers) is not tuple
                or not self.emitted_all_numbers
                or type(self.strategy_version) is not str
                or not self.strategy_version
            ):
                raise ValueError("OK executions require emitted_all_numbers and strategy_version")
        elif self.emitted_all_numbers is not None or self.strategy_version is not None:
            raise ValueError("non-OK executions must not expose an emission identity")


class GeneratePortfolio:
    """Resolve an injected portfolio adapter and convert every outcome to a closed result.

    Mirrors :class:`GenerateOneBet`'s structure exactly, but for PORTFOLIO
    strategies: the complete, ordered native ticket set is always returned
    together — this path never exposes only the first ticket.
    """

    def __init__(
        self, catalog: StrategyCatalog, adapters: Mapping[str, PortfolioBetAdapter]
    ) -> None:
        adapter_snapshot: dict[str, PortfolioBetAdapter] = {}
        runtime_entries = cast(Mapping[object, object], adapters)
        for candidate_id, candidate_adapter in runtime_entries.items():
            if type(candidate_id) is not str or not isinstance(
                candidate_adapter, PortfolioBetAdapter
            ):
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
                adapter.native_ticket_count,
                adapter.native_ticket_count_bounds(),
            )
            expected_identity = (
                descriptor.strategy_id,
                descriptor.strategy_name,
                descriptor.version,
                descriptor.native_ticket_count,
                descriptor.native_ticket_count_bounds,
            )
            if strategy_id != adapter.strategy_id or actual_identity != expected_identity:
                raise AdapterIdentityMismatchError(
                    f"{strategy_id}: adapter identity does not match the catalog"
                )

        self._catalog = catalog
        self._adapters: Mapping[str, PortfolioBetAdapter] = MappingProxyType(adapter_snapshot)

    def execute(self, request: GenerateOneBetInput) -> GeneratePortfolioResult:
        return self.execute_with_emission(request).legal_bets

    def execute_with_emission(
        self,
        request: GenerateOneBetInput,
    ) -> GeneratePortfolioExecution:
        """Return one adapter execution with its pre-canonical emitted order."""

        try:
            descriptor = self._catalog.get(request.strategy_id)
        except UnknownStrategyError:
            return self._failure_execution(
                GeneratePortfolioStatus.STRATEGY_UNAVAILABLE,
                GeneratePortfolioReason.UNKNOWN_STRATEGY,
            )

        if descriptor.response_shape is not ResponseShape.PORTFOLIO:
            return self._failure_execution(
                GeneratePortfolioStatus.WRONG_RESPONSE_PATH,
                GeneratePortfolioReason.STRATEGY_IS_NOT_PORTFOLIO,
            )

        adapter = self._adapters.get(request.strategy_id)
        if adapter is None:
            return self._failure_execution(
                GeneratePortfolioStatus.STRATEGY_UNAVAILABLE,
                GeneratePortfolioReason.ADAPTER_NOT_INJECTED,
            )
        if type(request.lottery_type) is not LotteryType or (
            request.lottery_type not in descriptor.lottery_types
        ):
            return self._failure_execution(
                GeneratePortfolioStatus.STRATEGY_UNAVAILABLE,
                GeneratePortfolioReason.UNSUPPORTED_LOTTERY_TYPE,
            )

        try:
            executions = adapter.get_bets_with_emission(
                request.history,
                request.lottery_type,
            )
        except InsufficientHistory:
            return self._failure_execution(
                GeneratePortfolioStatus.INSUFFICIENT_HISTORY,
                GeneratePortfolioReason.INSUFFICIENT_HISTORY,
            )
        except UnsupportedLotteryType:
            return self._failure_execution(
                GeneratePortfolioStatus.STRATEGY_UNAVAILABLE,
                GeneratePortfolioReason.UNSUPPORTED_LOTTERY_TYPE,
            )
        except InvalidOutput:
            return self._failure_execution(
                GeneratePortfolioStatus.INVALID_OUTPUT,
                GeneratePortfolioReason.INVALID_OUTPUT,
            )
        except Exception:
            return self._failure_execution(
                GeneratePortfolioStatus.REPLAY_ERROR,
                GeneratePortfolioReason.REPLAY_ERROR,
            )

        return GeneratePortfolioExecution(
            legal_bets=GeneratePortfolioResult(
                status=GeneratePortfolioStatus.OK,
                numbers=tuple(execution.legal_main_numbers for execution in executions),
                special_number=None,
                reason_code=None,
            ),
            emitted_all_numbers=tuple(execution.emitted_main_numbers for execution in executions),
            strategy_version=descriptor.version,
        )

    @staticmethod
    def _failure(
        status: GeneratePortfolioStatus,
        reason: GeneratePortfolioReason,
    ) -> GeneratePortfolioResult:
        return GeneratePortfolioResult(
            status=status,
            numbers=None,
            special_number=None,
            reason_code=reason,
        )

    @classmethod
    def _failure_execution(
        cls,
        status: GeneratePortfolioStatus,
        reason: GeneratePortfolioReason,
    ) -> GeneratePortfolioExecution:
        return GeneratePortfolioExecution(
            legal_bets=cls._failure(status, reason),
            emitted_all_numbers=None,
            strategy_version=None,
        )


def _instantiated_portfolio_adapter(strategy_id: str, adapter_class: object) -> PortfolioBetAdapter:
    if not (isinstance(adapter_class, type) and issubclass(adapter_class, PortfolioBetAdapter)):
        raise AdapterIdentityMismatchError(
            f"{strategy_id}: adapter_path does not resolve to a PortfolioBetAdapter subclass"
        )
    adapter_factory = cast(Callable[..., PortfolioBetAdapter], adapter_class)
    if getattr(adapter_class, "requires_wave26_authority", False) is True:
        return adapter_factory(wave26_authority=_generate_wave26_portfolio)
    return adapter_factory()


def instantiate_portfolio_adapter(strategy_id: str, adapter_class: object) -> PortfolioBetAdapter:
    """Instantiate one portfolio adapter through the canonical type guard."""

    return _instantiated_portfolio_adapter(strategy_id, adapter_class)


def _generate_wave26_portfolio(
    method_id: str,
    target_draw_number: str,
    history: tuple[CausalDrawRow, ...],
) -> tuple[tuple[int, ...], ...]:
    """Translate canonical adapter rows into the application-owned Wave26 request."""

    from lottolab.application.legacy_history_native_portfolios import LegacyHistoryDraw
    from lottolab.application.legacy_source_native_portfolios_wave26 import (
        LegacySourceNativeWave26Request,
        generate_legacy_source_native_wave26_portfolio,
    )
    from lottolab.application.strategy_preserving_20_ticket import Ticket

    legacy_history = tuple(
        LegacyHistoryDraw(draw_number=row.draw, numbers=cast(Ticket, row.numbers))
        for row in history
    )
    return generate_legacy_source_native_wave26_portfolio(
        LegacySourceNativeWave26Request(
            legacy_method_id=method_id,
            target_draw_number=target_draw_number,
            history=legacy_history,
        )
    ).tickets


def build_production_generate_portfolio() -> GeneratePortfolio:
    """Compose the production catalog with its portfolio executable adapters.

    SINGLE_TICKET strategies are excluded here — see
    :func:`build_production_generate_one_bet` for their path. Imports
    :class:`ExecutableRegistry` lazily for the same reason that function does.
    """

    from lottolab.strategies.executable_registry import ExecutableRegistry

    catalog = production_catalog()
    registry = ExecutableRegistry(catalog)
    adapters: dict[str, PortfolioBetAdapter] = {
        strategy_id: _instantiated_portfolio_adapter(
            strategy_id, registry.load_adapter(strategy_id)
        )
        for strategy_id in registry.executable_ids()
        if catalog.get(strategy_id).response_shape is ResponseShape.PORTFOLIO
    }
    return GeneratePortfolio(catalog, adapters)


def run_cli_generate_bet(*, strategy_id: str, seed: int, history_json: str) -> tuple[str, bool]:
    """Parse, execute, and render one CLI bet request.

    Returns ``(json_text, ok)``; ``ok`` is false for every non-``OK`` status
    so the caller can select a fail-closed process exit code. May raise
    :class:`HistoryParseError` for malformed input, by design left to the
    caller so it can be reported the same way as other CLI input errors.
    ``seed`` is metadata-only: it is echoed in the output and is never
    passed to the resolved adapter or used to influence execution.

    Fails closed with ``WRONG_RESPONSE_PATH``/``STRATEGY_IS_PORTFOLIO`` for a
    PORTFOLIO strategy_id — use :func:`run_cli_generate_portfolio` instead.
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


def render_portfolio_result_json(
    result: GeneratePortfolioResult, *, strategy_id: str, seed: int
) -> str:
    """Render a canonical, machine-readable complete-portfolio result.

    ``numbers`` is the full ordered native ticket set — never truncated.
    ``seed`` is caller-provided bookkeeping metadata, as in
    :func:`render_result_json`.
    """

    payload: dict[str, object] = {
        "strategy_id": strategy_id,
        "lottery_type": LotteryType.BIG_LOTTO.value,
        "seed": seed,
        "status": result.status.value,
        "numbers": (
            [list(ticket) for ticket in result.numbers] if result.numbers is not None else None
        ),
        "reason_code": result.reason_code.value if result.reason_code is not None else None,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def run_cli_generate_portfolio(
    *, strategy_id: str, seed: int, history_json: str
) -> tuple[str, bool]:
    """Parse, execute, and render one CLI portfolio (multi-ticket) request.

    Returns ``(json_text, ok)``, mirroring :func:`run_cli_generate_bet`.
    Fails closed with ``WRONG_RESPONSE_PATH``/``STRATEGY_IS_NOT_PORTFOLIO``
    for a SINGLE_TICKET strategy_id — use :func:`run_cli_generate_bet` instead.
    """

    history = parse_history_json(history_json)
    use_case = build_production_generate_portfolio()
    result = use_case.execute(
        GenerateOneBetInput(
            strategy_id=strategy_id,
            lottery_type=LotteryType.BIG_LOTTO,
            history=history,
        )
    )
    return (
        render_portfolio_result_json(result, strategy_id=strategy_id, seed=seed),
        result.status is GeneratePortfolioStatus.OK,
    )


__all__ = [
    "AdapterIdentityMismatchError",
    "GenerateOneBet",
    "GenerateOneBetExecution",
    "GenerateOneBetInput",
    "GenerateOneBetReason",
    "GenerateOneBetResult",
    "GenerateOneBetStatus",
    "GeneratePortfolio",
    "GeneratePortfolioExecution",
    "GeneratePortfolioReason",
    "GeneratePortfolioResult",
    "GeneratePortfolioStatus",
    "HistoryParseError",
    "build_production_generate_one_bet",
    "build_production_generate_portfolio",
    "instantiate_adapter",
    "instantiate_portfolio_adapter",
    "parse_history_json",
    "render_portfolio_result_json",
    "render_result_json",
    "run_cli_generate_bet",
    "run_cli_generate_portfolio",
]
