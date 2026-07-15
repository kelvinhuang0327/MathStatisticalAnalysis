"""Use case: list strategy metadata for any consumer (API, CLI, frontend)."""

from __future__ import annotations

from quantlab.application.dto import StrategyView
from quantlab.domain.lottery.draws import LotteryType
from quantlab.domain.lottery.strategies import LifecycleStatus
from quantlab.strategies.catalog import StrategyCatalog


class ListStrategies:
    def __init__(self, catalog: StrategyCatalog) -> None:
        self._catalog = catalog

    def execute(
        self,
        *,
        lottery_type: LotteryType | None = None,
        lifecycle_status: LifecycleStatus | None = None,
    ) -> tuple[StrategyView, ...]:
        descriptors = self._catalog.list(
            lottery_type=lottery_type, lifecycle_status=lifecycle_status
        )
        return tuple(StrategyView.from_descriptor(d) for d in descriptors)
