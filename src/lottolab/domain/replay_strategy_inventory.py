"""Identity and status model for the unified Replay strategy inventory.

The inventory deliberately keeps source lifecycle, retained replay data, and
execution capability as independent facts.  A source catalog row alone never
proves that historical predictions are stored or that an adapter can run.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from lottolab.domain.draws import LotteryType


class ReplayLifecycleStatus(StrEnum):
    """Observed registration lifecycle or explicit source-only classification."""

    ONLINE = "ONLINE"
    OBSERVATION = "OBSERVATION"
    OFFLINE = "OFFLINE"
    REJECTED = "REJECTED"
    ARTIFACT_ONLY = "ARTIFACT_ONLY"
    CODE_ONLY = "CODE_ONLY"
    UNREGISTERED_IDENTIFIED = "UNREGISTERED_IDENTIFIED"
    IDEA = "IDEA"
    RETIRED = "RETIRED"


class ReplayDataStatus(StrEnum):
    """Availability of replay predictions or source evidence for an identity."""

    HAS_HISTORY = "HAS_HISTORY"
    REBUILDABLE = "REBUILDABLE"
    RECONSTRUCTABLE = "REBUILDABLE"  # Backwards-compatible enum alias.
    NO_HISTORY = "NO_HISTORY"
    ARTIFACT_ONLY = "ARTIFACT_ONLY"
    CODE_ONLY = "CODE_ONLY"
    REJECTED = "REJECTED"


class ReplayExecutionCapability(StrEnum):
    """Whether Replay Engine has an exact, usable strategy binding."""

    EXECUTABLE = "EXECUTABLE"
    UNAVAILABLE = "UNAVAILABLE"
    ARTIFACT_ONLY = "ARTIFACT_ONLY"


@dataclass(frozen=True, slots=True)
class ReplayStrategyIdentityMapping:
    """One original source identity retained beside its canonical index row."""

    source_kind: str
    source_locator: str
    strategy_id: str
    strategy_version: str | None
    mapping_kind: str
    source_status: str | None = None

    def __post_init__(self) -> None:
        for field_name in ("source_kind", "source_locator", "strategy_id", "mapping_kind"):
            value = getattr(self, field_name)
            if type(value) is not str or not value.strip():
                raise ValueError(f"{field_name} must be a non-blank string")
        if self.strategy_version is not None and (
            type(self.strategy_version) is not str or not self.strategy_version.strip()
        ):
            raise ValueError("strategy_version must be non-blank when supplied")
        if self.source_status is not None and (
            type(self.source_status) is not str or not self.source_status.strip()
        ):
            raise ValueError("source_status must be non-blank when supplied")


@dataclass(frozen=True, slots=True)
class ReplayStrategyAdapterMapping:
    """Deterministic identity and implementation route accepted by Replay Engine."""

    replay_adapter: str
    implementation_locator: str
    strategy_id: str
    strategy_version: str

    def __post_init__(self) -> None:
        for field_name in (
            "replay_adapter",
            "implementation_locator",
            "strategy_id",
            "strategy_version",
        ):
            value = getattr(self, field_name)
            if type(value) is not str or not value.strip():
                raise ValueError(f"{field_name} must be a non-blank string")


@dataclass(frozen=True, slots=True)
class ReplayStrategyBindingEvidence:
    """One exact native engine binding and the source that proves it."""

    lottery_type: LotteryType
    strategy_id: str
    strategy_version: str
    source_kind: str
    source_locator: str

    def __post_init__(self) -> None:
        if type(self.lottery_type) is not LotteryType:
            raise ValueError("lottery_type must be a LotteryType")
        for field_name in (
            "strategy_id",
            "strategy_version",
            "source_kind",
            "source_locator",
        ):
            value = getattr(self, field_name)
            if type(value) is not str or not value.strip():
                raise ValueError(f"{field_name} must be a non-blank string")

    @property
    def identity(self) -> tuple[LotteryType, str, str]:
        return (self.lottery_type, self.strategy_id, self.strategy_version)


@dataclass(frozen=True, slots=True)
class ReplayStrategyInventoryItem:
    """One strategy version and all source facts explicitly mapped to it."""

    lottery_type: LotteryType
    strategy_id: str
    display_name: str
    strategy_version: str | None
    source_kind: str
    source_locator: str
    lifecycle_status: ReplayLifecycleStatus
    replay_data_status: ReplayDataStatus
    execution_capability: ReplayExecutionCapability
    reconstruction_reason: str
    historical_data_count: int
    alias_or_identity_mapping: tuple[ReplayStrategyIdentityMapping, ...]
    adapter_mapping: ReplayStrategyAdapterMapping | None = None
    source_statuses: tuple[str, ...] = ()
    historical_execution_count: int = 0
    reconstructable: bool | None = None
    wrapper_callable: bool | None = None
    backfill_native_binding: bool | None = None
    execution_block_reason: str | None = None
    backfill_native_binding_sources: tuple[ReplayStrategyBindingEvidence, ...] = ()

    def __post_init__(self) -> None:
        if type(self.lottery_type) is not LotteryType:
            raise ValueError("lottery_type must be a LotteryType")
        for field_name in (
            "strategy_id",
            "display_name",
            "source_kind",
            "source_locator",
            "reconstruction_reason",
        ):
            value = getattr(self, field_name)
            if type(value) is not str or not value.strip():
                raise ValueError(f"{field_name} must be a non-blank string")
        if self.strategy_version is not None and (
            type(self.strategy_version) is not str or not self.strategy_version.strip()
        ):
            raise ValueError("strategy_version must be non-blank when supplied")
        for field_name, enum_type in (
            ("lifecycle_status", ReplayLifecycleStatus),
            ("replay_data_status", ReplayDataStatus),
            ("execution_capability", ReplayExecutionCapability),
        ):
            if type(getattr(self, field_name)) is not enum_type:
                raise ValueError(f"{field_name} must be a {enum_type.__name__}")
        for field_name in ("historical_data_count", "historical_execution_count"):
            value = getattr(self, field_name)
            if type(value) is not int or value < 0:
                raise ValueError(f"{field_name} must be a non-negative integer")
        if type(self.alias_or_identity_mapping) is not tuple or not self.alias_or_identity_mapping:
            raise ValueError("alias_or_identity_mapping must retain at least the primary source")
        if not all(
            type(item) is ReplayStrategyIdentityMapping for item in self.alias_or_identity_mapping
        ):
            raise ValueError("alias_or_identity_mapping contains an invalid source identity")
        if self.execution_capability is ReplayExecutionCapability.EXECUTABLE:
            if type(self.adapter_mapping) is not ReplayStrategyAdapterMapping:
                raise ValueError("EXECUTABLE strategies require a concrete adapter_mapping")
            if (
                self.adapter_mapping.strategy_id != self.strategy_id
                or self.adapter_mapping.strategy_version != self.strategy_version
            ):
                raise ValueError("adapter_mapping identity must exactly match the strategy version")
        if (
            self.replay_data_status is ReplayDataStatus.HAS_HISTORY
            and self.historical_data_count == 0
        ):
            raise ValueError("HAS_HISTORY requires at least one retained historical data row")
        for field_name in (
            "reconstructable",
            "wrapper_callable",
            "backfill_native_binding",
        ):
            value = getattr(self, field_name)
            if value is not None and type(value) is not bool:
                raise ValueError(f"{field_name} must be a bool or None for UNKNOWN")
        if self.execution_block_reason is not None and (
            type(self.execution_block_reason) is not str or not self.execution_block_reason.strip()
        ):
            raise ValueError("execution_block_reason must be non-blank when supplied")
        if type(self.backfill_native_binding_sources) is not tuple or not all(
            type(source) is ReplayStrategyBindingEvidence
            for source in self.backfill_native_binding_sources
        ):
            raise ValueError("backfill_native_binding_sources must be a tuple of binding evidence")
        if self.backfill_native_binding:
            if not self.backfill_native_binding_sources:
                raise ValueError("native binding requires source identity evidence")
            if any(
                source.identity != (self.lottery_type, self.strategy_id, self.strategy_version)
                for source in self.backfill_native_binding_sources
            ):
                raise ValueError("native binding evidence identity must exactly match the item")
        elif self.backfill_native_binding_sources:
            raise ValueError("binding evidence is only valid for a verified native binding")

    @property
    def backfill_runnable(self) -> bool:
        """Return whether all independent requirements for a Backfill run hold."""

        return (
            self.reconstructable is True
            and self.wrapper_callable is True
            and self.backfill_native_binding is True
            and self.execution_block_reason is None
        )


@dataclass(frozen=True, slots=True)
class ReplayStrategySourceCount:
    """Conservation counts for one enumerated source inventory."""

    source_kind: str
    source_identity_count: int
    source_row_count: int
    evidence_file_count: int = 0

    def __post_init__(self) -> None:
        if type(self.source_kind) is not str or not self.source_kind.strip():
            raise ValueError("source_kind must be a non-blank string")
        if type(self.source_identity_count) is not int or self.source_identity_count < 0:
            raise ValueError("source_identity_count must be a non-negative integer")
        if type(self.source_row_count) is not int or self.source_row_count < 0:
            raise ValueError("source_row_count must be a non-negative integer")
        if self.source_identity_count > self.source_row_count:
            raise ValueError("source identity count cannot exceed its raw source row count")
        if type(self.evidence_file_count) is not int or self.evidence_file_count < 0:
            raise ValueError("evidence_file_count must be a non-negative integer")


type SourceIdentity = tuple[LotteryType, str, str | None]


@dataclass(frozen=True, slots=True)
class ReplayStrategyInventory:
    """Immutable, deterministic index with explicit source-count accounting."""

    items: tuple[ReplayStrategyInventoryItem, ...]
    source_counts: tuple[ReplayStrategySourceCount, ...]
    unresolved_source_count: int = 0
    source_integrity_issues: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if type(self.items) is not tuple or not all(
            type(item) is ReplayStrategyInventoryItem for item in self.items
        ):
            raise ValueError("items must be an exact tuple of ReplayStrategyInventoryItem")
        identities = tuple(
            (item.lottery_type, item.strategy_id, item.strategy_version) for item in self.items
        )
        if len(identities) != len(set(identities)):
            raise ValueError("inventory contains a duplicate lottery/id/version identity")
        if type(self.source_counts) is not tuple or not all(
            type(item) is ReplayStrategySourceCount for item in self.source_counts
        ):
            raise ValueError("source_counts must be an exact tuple of ReplayStrategySourceCount")
        if type(self.unresolved_source_count) is not int or self.unresolved_source_count < 0:
            raise ValueError("unresolved_source_count must be a non-negative integer")
        if type(self.source_integrity_issues) is not tuple or not all(
            type(issue) is str and issue.strip() for issue in self.source_integrity_issues
        ):
            raise ValueError("source_integrity_issues must be a tuple of non-blank strings")

    @property
    def total_discovered_strategies(self) -> int:
        """Return the conserved source-identity rows before cross-source merging."""

        return sum(source.source_identity_count for source in self.source_counts)

    @property
    def total_unique_strategies(self) -> int:
        return len(self.items)

    @property
    def executable_items(self) -> tuple[ReplayStrategyInventoryItem, ...]:
        return tuple(
            item
            for item in self.items
            if item.execution_capability is ReplayExecutionCapability.EXECUTABLE
        )

    def query(
        self,
        *,
        lottery_type: LotteryType | None = None,
        strategy_id: str | None = None,
        replay_data_status: ReplayDataStatus | None = None,
    ) -> tuple[ReplayStrategyInventoryItem, ...]:
        """Filter by independent identity and data facts in stable index order."""

        if strategy_id is not None and (type(strategy_id) is not str or not strategy_id.strip()):
            raise ValueError("strategy_id filter must be a non-blank string")
        return tuple(
            item
            for item in self.items
            if (lottery_type is None or item.lottery_type is lottery_type)
            and (strategy_id is None or item.strategy_id == strategy_id)
            and (replay_data_status is None or item.replay_data_status is replay_data_status)
        )
