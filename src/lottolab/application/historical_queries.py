"""BLHQ R2: application-owned read models and queries for historical results.

Read-only counterpart to ``domain.historical_results``'s write-side import
model. This module imports nothing from ``lottolab.interfaces`` or
``lottolab.infrastructure`` and never touches ``sqlite3``/FastAPI: query
repositories return these DTOs, never raw persistence rows.
"""

from __future__ import annotations

from dataclasses import dataclass

MIN_PAGE_LIMIT = 1
MAX_PAGE_LIMIT = 200
DEFAULT_PAGE_LIMIT = 50
DEFAULT_PAGE_OFFSET = 0
TICKET_COUNT_CHOICES: tuple[int, ...] = (10, 15, 20)

HISTORICAL_RUN_SORT = ("completed_at:desc", "run_id:desc")
HISTORICAL_STRATEGY_SORT = ("strategy_id:asc", "strategy_version:asc", "replicate:asc")
HISTORICAL_REPLAY_SORT = (
    "target_draw_date:asc",
    "target_draw_number:int_asc",
    "strategy_id:asc",
    "strategy_version:asc",
    "replicate:asc",
    "portfolio_id:asc",
)


class HistoricalQueryApplicationError(RuntimeError):
    """Base class for sanitized historical-query application failures."""


class InvalidHistoricalQueryError(HistoricalQueryApplicationError):
    """Pagination or ``ticket_count`` parameters failed validation."""


class HistoricalResultsUnavailableError(HistoricalQueryApplicationError):
    """Configured historical-results storage exists but could not be read safely."""


@dataclass(frozen=True, slots=True)
class HistoricalRunQuery:
    limit: int = DEFAULT_PAGE_LIMIT
    offset: int = DEFAULT_PAGE_OFFSET


@dataclass(frozen=True, slots=True)
class HistoricalRunSummary:
    run_id: str
    import_identity_sha256: str
    manifest_sha256: str
    contract_version: str
    source_kind: str
    source_repository: str
    source_commit_oid: str
    source_artifact_sha256: str
    dataset_identity: str
    dataset_sha256: str
    legacy_run_id: str | None
    lottery_type: str
    started_at: str
    completed_at: str


@dataclass(frozen=True, slots=True)
class HistoricalRunPage:
    items: tuple[HistoricalRunSummary, ...]
    total_count: int
    limit: int
    offset: int
    sort: tuple[str, ...] = HISTORICAL_RUN_SORT


@dataclass(frozen=True, slots=True)
class HistoricalStrategySummary:
    strategy_snapshot_id: str
    strategy_id: str
    effective_strategy_id: str
    strategy_version: str
    replicate: int
    identity_kind: str
    governance_status: str
    alias_of_strategy_id: str | None
    equivalence_group: str | None
    nested_prefix_supported: bool
    ticket_count: int
    evaluated_draws: int
    complete_portfolios: int
    m4plus_hit_count: int


@dataclass(frozen=True, slots=True)
class HistoricalStrategySummaryList:
    run_id: str
    ticket_count: int
    items: tuple[HistoricalStrategySummary, ...]
    sort: tuple[str, ...] = HISTORICAL_STRATEGY_SORT


@dataclass(frozen=True, slots=True)
class HistoricalDrawIdentity:
    draw_number: str
    draw_date: str
    main_numbers: tuple[int, ...]
    special_numbers: tuple[int, ...]
    draw_sha256: str


@dataclass(frozen=True, slots=True)
class HistoricalTicketRecord:
    portfolio_position: int
    main_numbers: tuple[int, ...]
    special_numbers: tuple[int, ...]
    main_hit_count: int
    special_hit: bool
    ticket_sha256: str
    legacy_row_id: str | None
    legacy_storage_bet_index: int | None


@dataclass(frozen=True, slots=True)
class HistoricalPortfolioRecord:
    portfolio_id: str
    run_id: str
    strategy_snapshot_id: str
    strategy_id: str
    effective_strategy_id: str
    strategy_version: str
    replicate: int
    constructor_identifier: str
    source_record_locator: str | None
    portfolio_sha256: str
    prefix10_sha256: str
    prefix15_sha256: str
    target_draw: HistoricalDrawIdentity
    cutoff_draw: HistoricalDrawIdentity
    requested_ticket_count: int
    m4plus: bool
    tickets: tuple[HistoricalTicketRecord, ...]


@dataclass(frozen=True, slots=True)
class HistoricalReplayQuery:
    strategy_id: str
    ticket_count: int
    m4plus_only: bool = False
    limit: int = DEFAULT_PAGE_LIMIT
    offset: int = DEFAULT_PAGE_OFFSET


@dataclass(frozen=True, slots=True)
class HistoricalReplayPage:
    run_id: str
    strategy_id: str
    ticket_count: int
    items: tuple[HistoricalPortfolioRecord, ...]
    total_count: int
    limit: int
    offset: int
    sort: tuple[str, ...] = HISTORICAL_REPLAY_SORT
