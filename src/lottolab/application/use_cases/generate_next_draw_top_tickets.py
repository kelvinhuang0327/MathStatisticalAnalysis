"""Execute the already-ranked top strategies of one bucket against current
causal history to produce real native tickets "as of right now" (P2).

Takes ranked strategy_ids and causal history as plain inputs; performs no
ranking itself (that is ``BuildNextDrawRecommendationBucket``'s job) and no
I/O. Every produced ticket is validated by the same donor-preserving adapter
contract (``BetAdapter``/``PortfolioBetAdapter``) already used for
backtesting -- never a separately re-implemented execution path.
"""

from __future__ import annotations

from enum import StrEnum

from lottolab.application.use_cases.generate_bet import instantiate_portfolio_adapter
from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters.base import (
    BetAdapter,
    BetAdapterError,
    CausalDrawRow,
    PortfolioBetAdapter,
)
from lottolab.strategies.catalog import StrategyCatalog
from lottolab.strategies.executable_registry import ExecutableRegistry, NotExecutableError


class TicketGenerationStatus(StrEnum):
    OK = "OK"
    DECLINED = "DECLINED"
    UNREACHABLE = "UNREACHABLE"


class GeneratedTicketSet:
    __slots__ = ("strategy_id", "status", "tickets", "detail")

    def __init__(
        self,
        *,
        strategy_id: str,
        status: TicketGenerationStatus,
        tickets: tuple[tuple[int, ...], ...],
        detail: str = "",
    ) -> None:
        self.strategy_id = strategy_id
        self.status = status
        self.tickets = tickets
        self.detail = detail


class GenerateNextDrawTopTickets:
    """Generate real tickets for a small, already-selected set of strategy_ids."""

    def __init__(self, catalog: StrategyCatalog) -> None:
        self._catalog = catalog
        self._registry = ExecutableRegistry(catalog)

    def execute(
        self,
        strategy_ids: tuple[str, ...],
        *,
        lottery_type: LotteryType,
        causal_history: tuple[CausalDrawRow, ...],
    ) -> tuple[GeneratedTicketSet, ...]:
        results = []
        for strategy_id in strategy_ids:
            results.append(self._one(strategy_id, lottery_type, causal_history))
        return tuple(results)

    def _one(
        self,
        strategy_id: str,
        lottery_type: LotteryType,
        causal_history: tuple[CausalDrawRow, ...],
    ) -> GeneratedTicketSet:
        try:
            adapter_cls = self._registry.load_adapter(strategy_id)
        except NotExecutableError as exc:
            return GeneratedTicketSet(
                strategy_id=strategy_id,
                status=TicketGenerationStatus.UNREACHABLE,
                tickets=(),
                detail=str(exc),
            )

        is_portfolio = isinstance(adapter_cls, type) and issubclass(adapter_cls, PortfolioBetAdapter)
        is_bet = isinstance(adapter_cls, type) and issubclass(adapter_cls, BetAdapter)
        if not is_portfolio and not is_bet:
            return GeneratedTicketSet(
                strategy_id=strategy_id,
                status=TicketGenerationStatus.UNREACHABLE,
                tickets=(),
                detail="adapter_path does not resolve to a known adapter base class",
            )

        try:
            if is_portfolio:
                adapter = instantiate_portfolio_adapter(strategy_id, adapter_cls)
                tickets = adapter.get_bets(causal_history, lottery_type)
            else:
                adapter = adapter_cls()
                main, _special = adapter.get_one_bet(causal_history, lottery_type)
                tickets = (main,)
        except BetAdapterError as exc:
            return GeneratedTicketSet(
                strategy_id=strategy_id,
                status=TicketGenerationStatus.DECLINED,
                tickets=(),
                detail=str(exc),
            )
        except Exception as exc:  # noqa: BLE001 -- a donor crash must not break the whole response
            return GeneratedTicketSet(
                strategy_id=strategy_id,
                status=TicketGenerationStatus.UNREACHABLE,
                tickets=(),
                detail=f"{type(exc).__name__}: {exc}",
            )

        return GeneratedTicketSet(
            strategy_id=strategy_id,
            status=TicketGenerationStatus.OK,
            tickets=tickets,
        )


__all__ = [
    "GenerateNextDrawTopTickets",
    "GeneratedTicketSet",
    "TicketGenerationStatus",
]
