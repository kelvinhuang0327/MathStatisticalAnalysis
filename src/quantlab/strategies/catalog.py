"""Read-only strategy catalog: metadata lookup without importing adapters."""

from __future__ import annotations

from collections.abc import Iterable, Iterator

from quantlab.domain.lottery.draws import LotteryType
from quantlab.domain.lottery.strategies import LifecycleStatus, StrategyDescriptor


class DuplicateStrategyIdError(ValueError):
    pass


class StrategyCatalog:
    def __init__(self, descriptors: Iterable[StrategyDescriptor]) -> None:
        self._by_id: dict[str, StrategyDescriptor] = {}
        for descriptor in descriptors:
            if descriptor.strategy_id in self._by_id:
                raise DuplicateStrategyIdError(descriptor.strategy_id)
            self._by_id[descriptor.strategy_id] = descriptor

    def __iter__(self) -> Iterator[StrategyDescriptor]:
        return iter(self._by_id.values())

    def __len__(self) -> int:
        return len(self._by_id)

    def get(self, strategy_id: str) -> StrategyDescriptor:
        return self._by_id[strategy_id]

    def list(
        self,
        *,
        lottery_type: LotteryType | None = None,
        lifecycle_status: LifecycleStatus | None = None,
    ) -> tuple[StrategyDescriptor, ...]:
        return tuple(
            descriptor
            for descriptor in self._by_id.values()
            if (lottery_type is None or lottery_type in descriptor.lottery_types)
            and (lifecycle_status is None or descriptor.lifecycle_status is lifecycle_status)
        )


def production_catalog() -> StrategyCatalog:
    """Production descriptors land here during migration batch 2 (P600A),
    each carrying provenance back to the legacy task/PR that validated it."""
    return StrategyCatalog(())
