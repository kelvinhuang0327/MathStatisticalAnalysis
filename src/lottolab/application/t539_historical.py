"""Application-owned read models for the T539 Wave 1 Strategy Analysis vertical.

The models in this module are deliberately independent of SQLite and FastAPI.
The read-only repository and the HTTP adapter translate their own storage and
wire representations into these immutable, lottery-scoped records.

T539 replays the sealed Wave 1 DAILY_539 run directly from its own flat
schema (``run_metadata``/``source_draws``/``strategy_coverage``/
``prediction_tickets``/``prediction_scores``/``failure_ledger``/
``target_completion``) rather than the shared ``historical_*`` projection
P638 reads; there is no forwarding step for this vertical.
"""

from __future__ import annotations

from dataclasses import dataclass

T539_LOTTERY_TYPE = "DAILY_539"
T539_REPLAY_SORT = (
    "target_draw_date:asc",
    "target_draw_id:int_asc",
    "strategy_id:asc",
    "strategy_version:asc",
)
T539_STRATEGY_SORT = ("strategy_id:asc", "strategy_version:asc")
T539_ALLOWED_TARGET_STATUSES = ("SUCCESS", "FAILED")


class T539HistoricalQueryError(RuntimeError):
    """Base class for sanitized T539 historical-query failures."""


class T539HistoricalResultsUnavailableError(T539HistoricalQueryError):
    """The configured T539 Wave 1 analysis database is unavailable."""


@dataclass(frozen=True, slots=True)
class T539RunSummary:
    run_id: str
    schema_version: str
    lottery_type: str
    source_endpoint: str
    source_sha256: str
    as_of_date: str
    adapter_source_commit: str
    status: str
    strategy_count: int
    draw_count: int
    eligible_target_count: int
    ticket_count: int
    failure_count: int
    first_draw_id: str | None
    first_draw_date: str | None
    last_draw_id: str | None
    last_draw_date: str | None


@dataclass(frozen=True, slots=True)
class T539RunPage:
    items: tuple[T539RunSummary, ...]
    total_count: int
    limit: int
    offset: int


@dataclass(frozen=True, slots=True)
class T539StrategyRecord:
    run_id: str
    strategy_id: str
    strategy_version: str
    native_ticket_count: int
    min_history: int
    first_eligible_target_draw_id: str | None
    expected_target_draw_count: int
    processed_target_draw_count: int
    successful_target_draw_count: int
    failed_target_draw_count: int
    status: str
    ticket_count: int
    winning_ticket_count: int
    hit_distribution: tuple[tuple[int, int], ...]
    first_target_draw_date: str | None
    last_target_draw_date: str | None


@dataclass(frozen=True, slots=True)
class T539StrategyPage:
    run_id: str
    items: tuple[T539StrategyRecord, ...]
    total_count: int
    limit: int
    offset: int


@dataclass(frozen=True, slots=True)
class T539TicketRecord:
    ticket_position: int
    predicted_numbers: tuple[int, ...]
    actual_numbers: tuple[int, ...]
    hit_numbers: tuple[int, ...]
    hits: int
    is_winner: bool
    prize_tier: str | None
    prize_tier_order: int | None
    prize_amount: int | None


@dataclass(frozen=True, slots=True)
class T539ReplayRecord:
    target_id: str
    run_id: str
    strategy_id: str
    strategy_version: str
    target_draw_id: str
    target_draw_date: str | None
    cutoff_draw_id: str | None
    cutoff_draw_date: str | None
    status: str
    native_ticket_count: int
    tickets: tuple[T539TicketRecord, ...]


T539TargetDetail = T539ReplayRecord


@dataclass(frozen=True, slots=True)
class T539ReplayQuery:
    strategy_id: str | None = None
    date_from: str | None = None
    date_to: str | None = None
    status: str | None = None
    limit: int = 50
    offset: int = 0


@dataclass(frozen=True, slots=True)
class T539ReplayPage:
    run_id: str
    items: tuple[T539ReplayRecord, ...]
    total_count: int
    limit: int
    offset: int


@dataclass(frozen=True, slots=True)
class T539StrategyMetrics:
    run_id: str
    strategy_id: str | None
    target_count: int
    ticket_count: int
    winning_ticket_count: int
    winning_target_count: int
    hit_distribution: tuple[tuple[int, int], ...]
    prize_tier_counts: tuple[tuple[str, int], ...]
    first_target_draw_date: str | None
    last_target_draw_date: str | None


@dataclass(frozen=True, slots=True)
class T539RankingRecord:
    """One strategy's official-prize historical performance, all 8 always present.

    Ranking describes past replay only; it never predicts future winning.
    """

    run_id: str
    rank: int
    strategy_id: str
    strategy_version: str
    native_ticket_count: int
    eligible_target_count: int
    winning_target_count: int
    winning_target_rate: float
    total_ticket_count: int
    winning_ticket_count: int
    ticket_winning_rate: float
    prize_tier_counts: tuple[tuple[str, int], ...]
    highest_prize_tier_achieved: str | None
    first_eligible_draw: str | None
    last_eligible_draw: str | None
    prize_rule_version: str
    prize_rule_provenance: str


@dataclass(frozen=True, slots=True)
class T539RankingPage:
    run_id: str
    items: tuple[T539RankingRecord, ...]


@dataclass(frozen=True, slots=True)
class T539CoverageExecutedEntry:
    """One of the exactly eight strategies replayed and ranked in Wave 1."""

    strategy_id: str
    strategy_version: str
    native_ticket_count: int
    min_history: int
    selection_reason: str


@dataclass(frozen=True, slots=True)
class T539CoverageBlockedEntry:
    """One catalog identity deferred out of Wave 1, never executed or ranked."""

    strategy_id: str
    reason_code: str
    reason: str


@dataclass(frozen=True, slots=True)
class T539CoverageLedger:
    """The complete Wave 1 DAILY_539 strategy coverage ledger.

    ``coverage_complete`` is always ``False`` while any blocked identity
    remains unresolved: Wave 1 never claims to cover every historical T539
    strategy, only the eight it actually replayed and ranked.
    """

    run_id: str
    executed: tuple[T539CoverageExecutedEntry, ...]
    blocked: tuple[T539CoverageBlockedEntry, ...]
    coverage_complete: bool
