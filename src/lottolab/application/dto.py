"""API-facing DTOs. Domain objects never cross the interface boundary directly."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from lottolab.domain.draws import LotteryType
from lottolab.domain.strategies import LifecycleStatus, StrategyDescriptor


class StrategyView(BaseModel):
    model_config = ConfigDict(frozen=True)

    strategy_id: str
    display_name: str
    version: str
    supported_lottery_types: list[LotteryType]
    minimum_history: int = Field(ge=1)
    lifecycle_status: LifecycleStatus
    executable: bool

    @classmethod
    def from_descriptor(cls, descriptor: StrategyDescriptor) -> StrategyView:
        return cls(
            strategy_id=descriptor.strategy_id,
            display_name=descriptor.strategy_name,
            version=descriptor.version,
            supported_lottery_types=list(descriptor.lottery_types),
            minimum_history=descriptor.min_history,
            lifecycle_status=descriptor.lifecycle_status,
            executable=descriptor.executable,
        )
