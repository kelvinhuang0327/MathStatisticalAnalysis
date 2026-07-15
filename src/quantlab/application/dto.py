"""API-facing DTOs. Domain objects never cross the interface boundary directly."""

from __future__ import annotations

from pydantic import BaseModel

from quantlab.domain.lottery.strategies import StrategyDescriptor


class StrategyView(BaseModel):
    strategy_id: str
    strategy_name: str
    version: str
    lottery_types: list[str]
    lifecycle_status: str
    executable: bool

    @classmethod
    def from_descriptor(cls, descriptor: StrategyDescriptor) -> StrategyView:
        return cls(
            strategy_id=descriptor.strategy_id,
            strategy_name=descriptor.strategy_name,
            version=descriptor.version,
            lottery_types=[str(t) for t in descriptor.lottery_types],
            lifecycle_status=str(descriptor.lifecycle_status),
            executable=descriptor.executable,
        )
