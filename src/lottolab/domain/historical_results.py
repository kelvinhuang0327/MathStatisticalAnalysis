"""BLHQ R1: pure domain model for the historical-results projection.

Immutable, hash-verified snapshots of legacy or synthetic backtest output.
This module imports nothing else from ``lottolab`` — it is the foundation
every other historical-results layer depends on, never the reverse.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class HistoricalLotteryType(StrEnum):
    """R1 supports exactly one lottery type; the wire contract pins the value."""

    BIG_LOTTO = "BIG_LOTTO"


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
