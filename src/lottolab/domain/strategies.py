"""Strategy identity and lifecycle.

``StrategyDescriptor`` is the single source of truth for strategy metadata:
catalogs, registries, APIs and docs all derive from it. One descriptor per
strategy — duplicating this data elsewhere is a migration-acceptance failure.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from lottolab.domain.draws import LotteryType


class LifecycleStatus(StrEnum):
    IDEA = "IDEA"
    OBSERVATION = "OBSERVATION"
    ONLINE = "ONLINE"
    REJECTED = "REJECTED"
    RETIRED = "RETIRED"


EXECUTABLE_STATUSES: frozenset[LifecycleStatus] = frozenset({LifecycleStatus.ONLINE})


@dataclass(frozen=True, slots=True)
class StrategyDescriptor:
    strategy_id: str
    strategy_name: str
    version: str
    lottery_types: tuple[LotteryType, ...]
    lifecycle_status: LifecycleStatus
    executable: bool
    adapter_path: str | None = None
    min_history: int = 1
    provenance: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.executable and self.lifecycle_status not in EXECUTABLE_STATUSES:
            raise ValueError(
                f"{self.strategy_id}: only {sorted(EXECUTABLE_STATUSES)} strategies "
                f"may be executable, got {self.lifecycle_status}"
            )
        if self.executable and not self.adapter_path:
            raise ValueError(f"{self.strategy_id}: executable strategy requires adapter_path")
