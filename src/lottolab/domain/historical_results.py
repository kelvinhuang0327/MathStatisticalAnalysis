"""BLHQ R1: pure domain model for the historical-results projection.

Immutable, hash-verified snapshots of legacy or synthetic backtest output.
This module imports nothing else from ``lottolab`` — it is the foundation
every other historical-results layer depends on, never the reverse.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType


class HistoricalLotteryType(StrEnum):
    """Closed internal lottery identifiers for historical-results V2."""

    DAILY_539 = "DAILY_539"
    BIG_LOTTO = "BIG_LOTTO"
    POWER_LOTTO = "POWER_LOTTO"


@dataclass(frozen=True, slots=True)
class HistoricalLotteryMechanics:
    """Pure number mechanics required to normalize one historical lottery."""

    main_number_count: int
    main_number_min: int
    main_number_max: int
    main_numbers_unique: bool
    special_number_count: int
    special_number_min: int | None
    special_number_max: int | None
    special_numbers_unique: bool
    special_numbers_required: bool
    main_special_overlap_allowed: bool


HISTORICAL_LOTTERY_MECHANICS: Mapping[HistoricalLotteryType, HistoricalLotteryMechanics] = (
    MappingProxyType(
        {
            HistoricalLotteryType.DAILY_539: HistoricalLotteryMechanics(
                main_number_count=5,
                main_number_min=1,
                main_number_max=39,
                main_numbers_unique=True,
                special_number_count=0,
                special_number_min=None,
                special_number_max=None,
                special_numbers_unique=True,
                special_numbers_required=False,
                main_special_overlap_allowed=False,
            ),
            HistoricalLotteryType.BIG_LOTTO: HistoricalLotteryMechanics(
                main_number_count=6,
                main_number_min=1,
                main_number_max=49,
                main_numbers_unique=True,
                special_number_count=1,
                special_number_min=1,
                special_number_max=49,
                special_numbers_unique=True,
                special_numbers_required=True,
                main_special_overlap_allowed=False,
            ),
            HistoricalLotteryType.POWER_LOTTO: HistoricalLotteryMechanics(
                main_number_count=6,
                main_number_min=1,
                main_number_max=38,
                main_numbers_unique=True,
                special_number_count=1,
                special_number_min=1,
                special_number_max=8,
                special_numbers_unique=True,
                special_numbers_required=True,
                main_special_overlap_allowed=True,
            ),
        }
    )
)


class HistoricalSourceKind(StrEnum):
    LEGACY_ORDERED20_EXPORT = "LEGACY_ORDERED20_EXPORT"
    SYNTHETIC_TEST_ONLY = "SYNTHETIC_TEST_ONLY"


class HistoricalIdentityKind(StrEnum):
    REAL = "REAL"
    SYNTHETIC_TEST_ONLY = "SYNTHETIC_TEST_ONLY"


class HistoricalGovernanceStatus(StrEnum):
    ONLINE = "ONLINE"
    UNKNOWN = "UNKNOWN"
    REJECTED = "REJECTED"
    RETIRED = "RETIRED"
    DELETED = "DELETED"
    CANDIDATE = "CANDIDATE"


class HistoricalRunStatus(StrEnum):
    """Mirrors the ``historical_result_run.status`` column's closed value set."""

    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


@dataclass(frozen=True, slots=True)
class HistoricalSourceDescriptor:
    source_kind: HistoricalSourceKind
    source_repository: str
    source_commit_oid: str
    source_artifact_sha256: str
    legacy_run_id: str | None


@dataclass(frozen=True, slots=True)
class HistoricalDatasetDescriptor:
    dataset_identity: str
    dataset_sha256: str
    lottery_type: HistoricalLotteryType


@dataclass(frozen=True, slots=True)
class HistoricalStrategyDescriptor:
    strategy_id: str
    effective_strategy_id: str
    strategy_version: str
    replicate: int
    identity_kind: HistoricalIdentityKind
    governance_status: HistoricalGovernanceStatus
    alias_of_strategy_id: str | None
    equivalence_group: str | None
    nested_prefix_supported: bool
    descriptor_sha256: str


@dataclass(frozen=True, slots=True)
class HistoricalDrawSnapshot:
    """``draw_number`` is a normalized integer; never compare it as text."""

    draw_number: int
    draw_date: str
    main_numbers: tuple[int, ...]
    special_numbers: tuple[int, ...]
    draw_sha256: str


@dataclass(frozen=True, slots=True)
class HistoricalTicket:
    portfolio_position: int
    main_numbers: tuple[int, ...]
    special_numbers: tuple[int, ...]
    main_hit_count: int
    special_hit: bool
    ticket_sha256: str
    legacy_row_id: str | None
    legacy_storage_bet_index: int | None


@dataclass(frozen=True, slots=True)
class HistoricalPortfolio:
    strategy_id: str
    strategy_version: str
    replicate: int
    target_draw_number: int
    cutoff_draw_number: int
    constructor_identifier: str
    source_record_locator: str | None
    tickets: tuple[HistoricalTicket, ...]
    portfolio_sha256: str
    prefix10_sha256: str
    prefix15_sha256: str


@dataclass(frozen=True, slots=True)
class HistoricalRunImport:
    """The complete normalized import; exists only when verification is PASS."""

    contract_version: str
    generated_at: str
    manifest_sha256: str
    import_identity_sha256: str
    source: HistoricalSourceDescriptor
    dataset: HistoricalDatasetDescriptor
    strategy_descriptors: tuple[HistoricalStrategyDescriptor, ...]
    draw_snapshots: tuple[HistoricalDrawSnapshot, ...]
    portfolios: tuple[HistoricalPortfolio, ...]


@dataclass(frozen=True, slots=True)
class HistoricalImportCommitResult:
    """Outcome of one repository-level commit attempt, successful or audited-failed."""

    run_id: str
    status: HistoricalRunStatus
    import_identity_sha256: str
    manifest_sha256: str
    is_idempotent_replay: bool
    completed_at: str | None
    error_code: str | None
    error_summary: str | None
