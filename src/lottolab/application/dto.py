"""API-facing DTOs. Domain objects never cross the interface boundary directly."""

from __future__ import annotations

from typing import Annotated, Literal

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


NonNegativeCount = Annotated[int, Field(ge=0)]
StrategyEvidenceUnavailableReason = Literal[
    "NO_CANONICAL_STRATEGY_EVALUATION_EVIDENCE"
]


class StrategyOverviewItem(BaseModel):
    """Canonical descriptor metadata exposed by the overview query."""

    model_config = ConfigDict(frozen=True)

    strategy_id: str
    display_name: str
    version: str
    supported_lottery_types: tuple[LotteryType, ...]
    minimum_history: int = Field(ge=1)
    lifecycle_status: LifecycleStatus
    executable: bool
    provenance: tuple[str, ...]

    @classmethod
    def from_descriptor(cls, descriptor: StrategyDescriptor) -> StrategyOverviewItem:
        return cls(
            strategy_id=descriptor.strategy_id,
            display_name=descriptor.strategy_name,
            version=descriptor.version,
            supported_lottery_types=descriptor.lottery_types,
            minimum_history=descriptor.min_history,
            lifecycle_status=descriptor.lifecycle_status,
            executable=descriptor.executable,
            provenance=descriptor.provenance,
        )


class StrategyOverviewSummary(BaseModel):
    """Counts over only the descriptors returned by the current query."""

    model_config = ConfigDict(frozen=True)

    total: NonNegativeCount
    executable_count: NonNegativeCount
    metadata_only_count: NonNegativeCount
    lifecycle_counts: dict[LifecycleStatus, NonNegativeCount]
    lottery_type_counts: dict[LotteryType, NonNegativeCount]


class StrategyOverviewCapabilities(BaseModel):
    """Truthful evidence availability at the current LottoLab migration boundary."""

    model_config = ConfigDict(frozen=True)

    evaluation_metrics_available: Literal[False]
    d3_status_available: Literal[False]
    best_strategy_ranking_available: Literal[False]
    unavailable_reason_codes: tuple[StrategyEvidenceUnavailableReason, ...]


class StrategyOverviewResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    items: tuple[StrategyOverviewItem, ...]
    summary: StrategyOverviewSummary
    capabilities: StrategyOverviewCapabilities
