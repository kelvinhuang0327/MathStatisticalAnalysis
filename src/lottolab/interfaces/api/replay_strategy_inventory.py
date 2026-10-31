"""Read-only query API for the cross-source Replay strategy inventory."""

# pyright: reportUnusedFunction=false
# (route handlers are registered by FastAPI decorators, not called by name)

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query
from pydantic import BaseModel, ConfigDict, Field

from lottolab.application.replay_strategy_inventory import load_replay_strategy_inventory
from lottolab.domain.draws import LotteryType
from lottolab.domain.replay_strategy_inventory import (
    ReplayDataStatus,
    ReplayExecutionCapability,
    ReplayLifecycleStatus,
    ReplayStrategyAdapterMapping,
    ReplayStrategyBindingEvidence,
    ReplayStrategyIdentityMapping,
    ReplayStrategyInventory,
    ReplayStrategyInventoryItem,
    ReplayStrategySourceCount,
)
from lottolab.interfaces.api.draw_data import ApiValidationErrorResponse
from lottolab.interfaces.api.strategy_catalog import API_PREFIX

_MAX_STRATEGY_ID_LENGTH = 200


class ReplayStrategyIdentityMappingView(BaseModel):
    """One source identity retained behind an indexed strategy version."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_kind: str
    source_locator: str
    strategy_id: str
    strategy_version: str | None
    mapping_kind: str
    source_status: str | None


class ReplayStrategyAdapterMappingView(BaseModel):
    """Exact replay adapter and implementation identity, when executable."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    replay_adapter: str
    implementation_locator: str
    strategy_id: str
    strategy_version: str


class ReplayStrategyBindingEvidenceView(BaseModel):
    """Exact native Backfill identity and its source locator."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    lottery_type: LotteryType
    strategy_id: str
    strategy_version: str
    source_kind: str
    source_locator: str


class ReplayStrategyInventoryItemView(BaseModel):
    """Public strategy row with lifecycle, data and execution facts split."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    lottery_type: LotteryType
    strategy_id: str
    display_name: str
    strategy_version: str | None
    source_kind: str
    source_locator: str
    lifecycle_status: ReplayLifecycleStatus
    replay_data_status: ReplayDataStatus
    execution_capability: ReplayExecutionCapability
    reconstructable: bool | None
    wrapper_callable: bool | None
    backfill_native_binding: bool | None
    backfill_runnable: bool
    execution_block_reason: str | None
    reconstruction_reason: str
    historical_data_count: int = Field(ge=0)
    historical_execution_count: int = Field(ge=0)
    alias_or_identity_mapping: tuple[ReplayStrategyIdentityMappingView, ...]
    adapter_mapping: ReplayStrategyAdapterMappingView | None
    backfill_native_binding_sources: tuple[ReplayStrategyBindingEvidenceView, ...]
    source_statuses: tuple[str, ...]


class ReplayStrategySourceCountView(BaseModel):
    """Raw and unique identity conservation for one source inventory."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_kind: str
    source_identity_count: int = Field(ge=0)
    source_row_count: int = Field(ge=0)
    evidence_file_count: int = Field(ge=0)


class ReplayStrategyExecutableIdentityView(BaseModel):
    """Full lottery/id/version denominator identity for replay/backfill."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    lottery_type: LotteryType
    strategy_id: str
    strategy_version: str


class ReplayStrategyInventoryResponse(BaseModel):
    """Filtered strategy rows plus unfiltered inventory counts and executable IDs."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    total_discovered_strategies: int = Field(ge=0)
    total_unique_strategies: int = Field(ge=0)
    total_executable: int = Field(ge=0)
    total_backfill_runnable: int = Field(ge=0)
    total_reconstructable: int = Field(ge=0)
    total_has_history: int = Field(ge=0)
    total_no_history: int = Field(ge=0)
    total_artifact_only: int = Field(ge=0)
    total_code_only: int = Field(ge=0)
    total_rejected: int = Field(ge=0)
    total_unregistered_identified: int = Field(ge=0)
    unresolved_source_count: int = Field(ge=0)
    lifecycle_status_counts: dict[str, int]
    source_status_counts: dict[str, int]
    replay_data_status_counts: dict[str, int]
    execution_capability_counts: dict[str, int]
    backfill_native_binding_counts: dict[str, int]
    source_counts: tuple[ReplayStrategySourceCountView, ...]
    source_integrity_issues: tuple[str, ...]
    executable_strategy_ids: tuple[ReplayStrategyExecutableIdentityView, ...]
    backfill_runnable_strategy_ids: tuple[ReplayStrategyExecutableIdentityView, ...]
    applied_filters: dict[str, str | None]
    strategy_count: int = Field(ge=0)
    strategies: tuple[ReplayStrategyInventoryItemView, ...]


def _identity_mapping_view(
    mapping: ReplayStrategyIdentityMapping,
) -> ReplayStrategyIdentityMappingView:
    return ReplayStrategyIdentityMappingView(
        source_kind=mapping.source_kind,
        source_locator=mapping.source_locator,
        strategy_id=mapping.strategy_id,
        strategy_version=mapping.strategy_version,
        mapping_kind=mapping.mapping_kind,
        source_status=mapping.source_status,
    )


def _adapter_mapping_view(
    mapping: ReplayStrategyAdapterMapping | None,
) -> ReplayStrategyAdapterMappingView | None:
    if mapping is None:
        return None
    return ReplayStrategyAdapterMappingView(
        replay_adapter=mapping.replay_adapter,
        implementation_locator=mapping.implementation_locator,
        strategy_id=mapping.strategy_id,
        strategy_version=mapping.strategy_version,
    )


def _binding_evidence_view(
    evidence: ReplayStrategyBindingEvidence,
) -> ReplayStrategyBindingEvidenceView:
    return ReplayStrategyBindingEvidenceView(
        lottery_type=evidence.lottery_type,
        strategy_id=evidence.strategy_id,
        strategy_version=evidence.strategy_version,
        source_kind=evidence.source_kind,
        source_locator=evidence.source_locator,
    )


def _item_view(item: ReplayStrategyInventoryItem) -> ReplayStrategyInventoryItemView:
    return ReplayStrategyInventoryItemView(
        lottery_type=item.lottery_type,
        strategy_id=item.strategy_id,
        display_name=item.display_name,
        strategy_version=item.strategy_version,
        source_kind=item.source_kind,
        source_locator=item.source_locator,
        lifecycle_status=item.lifecycle_status,
        replay_data_status=item.replay_data_status,
        execution_capability=item.execution_capability,
        reconstructable=item.reconstructable,
        wrapper_callable=item.wrapper_callable,
        backfill_native_binding=item.backfill_native_binding,
        backfill_runnable=item.backfill_runnable,
        execution_block_reason=item.execution_block_reason,
        reconstruction_reason=item.reconstruction_reason,
        historical_data_count=item.historical_data_count,
        historical_execution_count=item.historical_execution_count,
        alias_or_identity_mapping=tuple(
            _identity_mapping_view(mapping) for mapping in item.alias_or_identity_mapping
        ),
        adapter_mapping=_adapter_mapping_view(item.adapter_mapping),
        backfill_native_binding_sources=tuple(
            _binding_evidence_view(evidence) for evidence in item.backfill_native_binding_sources
        ),
        source_statuses=item.source_statuses,
    )


def _source_count_view(count: ReplayStrategySourceCount) -> ReplayStrategySourceCountView:
    return ReplayStrategySourceCountView(
        source_kind=count.source_kind,
        source_identity_count=count.source_identity_count,
        source_row_count=count.source_row_count,
        evidence_file_count=count.evidence_file_count,
    )


def _response(
    inventory: ReplayStrategyInventory,
    *,
    lottery_type: LotteryType | None,
    strategy_id: str | None,
    replay_data_status: ReplayDataStatus | None,
) -> ReplayStrategyInventoryResponse:
    rows = inventory.query(
        lottery_type=lottery_type,
        strategy_id=strategy_id,
        replay_data_status=replay_data_status,
    )
    return ReplayStrategyInventoryResponse(
        total_discovered_strategies=inventory.total_discovered_strategies,
        total_unique_strategies=inventory.total_unique_strategies,
        total_executable=len(inventory.executable_items),
        total_backfill_runnable=sum(item.backfill_runnable for item in inventory.items),
        total_reconstructable=sum(
            item.replay_data_status is ReplayDataStatus.RECONSTRUCTABLE for item in inventory.items
        ),
        total_has_history=sum(
            item.replay_data_status is ReplayDataStatus.HAS_HISTORY for item in inventory.items
        ),
        total_no_history=sum(
            item.replay_data_status is ReplayDataStatus.NO_HISTORY for item in inventory.items
        ),
        total_artifact_only=sum(
            item.replay_data_status is ReplayDataStatus.ARTIFACT_ONLY for item in inventory.items
        ),
        total_code_only=sum(
            item.replay_data_status is ReplayDataStatus.CODE_ONLY for item in inventory.items
        ),
        total_rejected=sum(
            item.replay_data_status is ReplayDataStatus.REJECTED for item in inventory.items
        ),
        total_unregistered_identified=sum(
            item.lifecycle_status is ReplayLifecycleStatus.UNREGISTERED_IDENTIFIED
            for item in inventory.items
        ),
        unresolved_source_count=inventory.unresolved_source_count,
        lifecycle_status_counts={
            status.value: sum(item.lifecycle_status is status for item in inventory.items)
            for status in ReplayLifecycleStatus
        },
        source_status_counts={
            status: sum(status in item.source_statuses for item in inventory.items)
            for status in sorted(
                {
                    source_status
                    for item in inventory.items
                    for source_status in item.source_statuses
                }
            )
        },
        replay_data_status_counts={
            status.value: sum(item.replay_data_status is status for item in inventory.items)
            for status in ReplayDataStatus
        },
        execution_capability_counts={
            capability.value: sum(
                item.execution_capability is capability for item in inventory.items
            )
            for capability in ReplayExecutionCapability
        },
        backfill_native_binding_counts={
            status: sum(item.backfill_native_binding is value for item in inventory.items)
            for status, value in (("BOUND", True), ("UNBOUND", False), ("UNKNOWN", None))
        },
        source_counts=tuple(_source_count_view(item) for item in inventory.source_counts),
        source_integrity_issues=inventory.source_integrity_issues,
        executable_strategy_ids=tuple(
            ReplayStrategyExecutableIdentityView(
                lottery_type=item.lottery_type,
                strategy_id=item.strategy_id,
                strategy_version=item.strategy_version,
            )
            for item in inventory.executable_items
            if item.strategy_version is not None
        ),
        backfill_runnable_strategy_ids=tuple(
            ReplayStrategyExecutableIdentityView(
                lottery_type=item.lottery_type,
                strategy_id=item.strategy_id,
                strategy_version=item.strategy_version,
            )
            for item in inventory.items
            if item.backfill_runnable and item.strategy_version is not None
        ),
        applied_filters={
            "lottery_type": None if lottery_type is None else lottery_type.value,
            "strategy_id": strategy_id,
            "replay_data_status": (
                None if replay_data_status is None else replay_data_status.value
            ),
        },
        strategy_count=len(rows),
        strategies=tuple(_item_view(item) for item in rows),
    )


def create_replay_strategy_inventory_router(
    inventory: ReplayStrategyInventory | None = None,
) -> APIRouter:
    """Create a read-only API router over an injected or packaged inventory."""

    resolved_inventory = inventory or load_replay_strategy_inventory()
    router = APIRouter(
        prefix=f"{API_PREFIX}/replay-strategy-inventory",
        tags=["replay-strategy-inventory"],
    )

    @router.get(
        "",
        response_model=ReplayStrategyInventoryResponse,
        responses={422: {"model": ApiValidationErrorResponse}},
    )
    def list_replay_strategies(
        lottery_type: Annotated[LotteryType | None, Query()] = None,
        strategy_id: Annotated[
            str | None,
            Query(min_length=1, max_length=_MAX_STRATEGY_ID_LENGTH),
        ] = None,
        replay_data_status: Annotated[ReplayDataStatus | None, Query()] = None,
    ) -> ReplayStrategyInventoryResponse:
        return _response(
            resolved_inventory,
            lottery_type=lottery_type,
            strategy_id=strategy_id,
            replay_data_status=replay_data_status,
        )

    return router


__all__ = ["create_replay_strategy_inventory_router"]
